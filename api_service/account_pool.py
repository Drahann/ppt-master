from __future__ import annotations

import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ACCOUNT_MAX_JOBS = 2
DEFAULT_ACCOUNT_SLOT_CAPACITY = 24
DEFAULT_LEASE_TTL_SECONDS = 3 * 60 * 60
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 120
DEFAULT_TRANSIENT_COOLDOWN_SECONDS = 30


class AccountPoolConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AccountPoolEntry:
    account_id: str
    api_key: str
    base_url: str | None = None
    deepseek_model: str | None = None
    svg_model: str | None = None
    svg_repair_model: str | None = None
    max_concurrent_jobs: int = DEFAULT_ACCOUNT_MAX_JOBS
    slot_capacity: int = DEFAULT_ACCOUNT_SLOT_CAPACITY
    enabled: bool = True

    @property
    def redis_id(self) -> str:
        safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", self.account_id).strip("._-")
        return safe or uuid.uuid5(uuid.NAMESPACE_URL, self.account_id).hex

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "base_url": self.base_url,
            "deepseek_model": self.deepseek_model,
            "svg_model": self.svg_model,
            "svg_repair_model": self.svg_repair_model,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "slot_capacity": self.slot_capacity,
            "enabled_config": self.enabled,
        }


@dataclass(frozen=True)
class AccountLease:
    lease_id: str
    account_id: str
    api_key: str
    base_url: str | None
    deepseek_model: str | None
    svg_model: str | None
    svg_repair_model: str | None
    slots: int
    expires_at: float


def load_account_pool_entries(env: dict[str, str] | None = None) -> list[AccountPoolEntry]:
    env = env or os.environ
    raw = (env.get("PPT_API_DEEPSEEK_ACCOUNT_POOL_JSON") or env.get("PPT_API_ACCOUNT_POOL_JSON") or "").strip()
    if not raw:
        file_raw = (env.get("PPT_API_DEEPSEEK_ACCOUNT_POOL_FILE") or env.get("PPT_API_ACCOUNT_POOL_FILE") or "").strip()
        if file_raw:
            raw = Path(file_raw).expanduser().read_text(encoding="utf-8")
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AccountPoolConfigError(f"account pool JSON is invalid: {exc}") from exc
    items = payload.get("accounts") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise AccountPoolConfigError("account pool must be a JSON list or an object with accounts[]")

    accounts: list[AccountPoolEntry] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AccountPoolConfigError(f"account pool item #{index + 1} must be an object")
        account_id = _required_str(item, "account_id", index)
        api_key = _required_str(item, "api_key", index)
        if account_id in seen:
            raise AccountPoolConfigError(f"duplicate account_id: {account_id}")
        seen.add(account_id)
        accounts.append(
            AccountPoolEntry(
                account_id=account_id,
                api_key=api_key,
                base_url=_optional_str(item.get("base_url")),
                deepseek_model=_optional_str(item.get("deepseek_model") or item.get("model")),
                svg_model=_optional_str(item.get("svg_model")),
                svg_repair_model=_optional_str(item.get("svg_repair_model")),
                max_concurrent_jobs=_safe_int(item.get("max_concurrent_jobs"), DEFAULT_ACCOUNT_MAX_JOBS, minimum=1),
                slot_capacity=_safe_int(item.get("slot_capacity"), DEFAULT_ACCOUNT_SLOT_CAPACITY, minimum=1),
                enabled=_safe_bool(item.get("enabled"), True),
            )
        )
    return accounts


def classify_error(error: str | None) -> str:
    text = (error or "").lower()
    if not text:
        return "success"
    if "401" in text or "unauthorized" in text or "invalid api key" in text or "authentication" in text:
        return "auth_failed"
    if "429" in text or "rate limit" in text or "too many requests" in text or "quota exceeded" in text:
        return "rate_limited"
    if "timeout" in text or "timed out" in text or "connection reset" in text or re.search(r"\b5\d\d\b", text):
        return "transient"
    return "failed"


class RedisAccountPool:
    """Redis-backed DeepSeek account pool.

    A lease is held for the whole PPT job. With the default 12 SVG workers,
    each account's 24-slot capacity naturally admits two concurrent jobs.
    """

    def __init__(
        self,
        client: Any,
        accounts: Iterable[AccountPoolEntry],
        *,
        key_prefix: str = "ppt-deepseek",
        lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
        rate_limit_cooldown_seconds: int = DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        transient_cooldown_seconds: int = DEFAULT_TRANSIENT_COOLDOWN_SECONDS,
    ) -> None:
        self.client = client
        self.accounts = list(accounts)
        self.accounts_by_id = {account.account_id: account for account in self.accounts}
        self.key_prefix = key_prefix.strip().strip(":") or "ppt-deepseek"
        self.lease_ttl_seconds = max(60, lease_ttl_seconds)
        self.rate_limit_cooldown_seconds = max(1, rate_limit_cooldown_seconds)
        self.transient_cooldown_seconds = max(1, transient_cooldown_seconds)
        self.accounts_key = self._key("account_pool:accounts")
        self.stats_key = self._key("account_pool:stats")
        self.lock_key = self._key("account_pool:lock")
        self.sync_accounts()

    @property
    def configured(self) -> bool:
        return bool(self.accounts)

    def sync_accounts(self) -> None:
        for account in self.accounts:
            self.client.hset(self.accounts_key, account.redis_id, json.dumps(account.safe_metadata(), ensure_ascii=False))
            state_key = self._state_key(account)
            self.client.hset(
                state_key,
                mapping={
                    "account_id": account.account_id,
                    "enabled_config": "1" if account.enabled else "0",
                    "max_concurrent_jobs": str(account.max_concurrent_jobs),
                    "slot_capacity": str(account.slot_capacity),
                },
            )
            if self.client.hget(state_key, "disabled") is None:
                self.client.hset(state_key, "disabled", "0")

    def acquire(
        self,
        *,
        requested_slots: int,
        owner_job_id: str,
        label: str,
        timeout_seconds: int = 0,
    ) -> AccountLease | None:
        requested_slots = max(1, requested_slots)
        deadline = time.time() + max(0, timeout_seconds)
        while True:
            lease = self._try_acquire(requested_slots=requested_slots, owner_job_id=owner_job_id, label=label)
            if lease is not None:
                return lease
            if timeout_seconds <= 0 or time.time() >= deadline:
                return None
            time.sleep(1.0)

    def release(self, lease: AccountLease, *, error: str | None = None) -> str:
        account = self.accounts_by_id.get(lease.account_id)
        result = classify_error(error)
        if account is not None:
            self.client.zrem(self._leases_key(account), lease.lease_id)
            updates = {
                "last_result": result,
                "last_error": (error or "")[:500],
                "last_result_at": f"{time.time():.6f}",
            }
            if result == "auth_failed":
                updates["disabled"] = "1"
            elif result == "rate_limited":
                updates["cooldown_until"] = f"{time.time() + self.rate_limit_cooldown_seconds:.6f}"
            elif result == "transient":
                updates["cooldown_until"] = f"{time.time() + self.transient_cooldown_seconds:.6f}"
            elif result == "success":
                updates["last_error"] = ""
            self.client.hset(self._state_key(account), mapping=updates)
        self.client.delete(self._lease_key(lease.lease_id))
        return result

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        accounts = []
        for account in self.accounts:
            runtime = self._runtime(account, now=now)
            accounts.append(
                {
                    "account_id": account.account_id,
                    "active_jobs": runtime["active_jobs"],
                    "active_slots": runtime["active_slots"],
                    "available_jobs": max(0, account.max_concurrent_jobs - int(runtime["active_jobs"])),
                    "available_slots": max(0, account.slot_capacity - int(runtime["active_slots"])),
                    "max_concurrent_jobs": account.max_concurrent_jobs,
                    "slot_capacity": account.slot_capacity,
                    "enabled": runtime["enabled"],
                    "cooldown_until": runtime["cooldown_until"],
                    "last_error": runtime["last_error"],
                    "granted": runtime["granted"],
                    "denied": runtime["denied"],
                }
            )
        stats = self.client.hgetall(self.stats_key) or {}
        return {
            "enabled": bool(self.accounts),
            "configured": bool(self.accounts),
            "lease_ttl_seconds": self.lease_ttl_seconds,
            "granted": _safe_int(stats.get("granted"), 0),
            "denied": _safe_int(stats.get("denied"), 0),
            "accounts": accounts,
        }

    def _try_acquire(self, *, requested_slots: int, owner_job_id: str, label: str) -> AccountLease | None:
        if not self.accounts:
            return None
        with self._pool_lock() as locked:
            if not locked:
                self.client.hincrby(self.stats_key, "denied", 1)
                return None
            self.sync_accounts()
            now = time.time()
            candidates: list[tuple[int, int, float, str, AccountPoolEntry]] = []
            denied: list[AccountPoolEntry] = []
            for account in self.accounts:
                runtime = self._runtime(account, now=now)
                if self._available(account, runtime, now=now, requested_slots=requested_slots):
                    candidates.append(
                        (
                            int(runtime["active_slots"]),
                            int(runtime["active_jobs"]),
                            float(runtime["last_used_at"]),
                            account.account_id,
                            account,
                        )
                    )
                else:
                    denied.append(account)
            if not candidates:
                self.client.hincrby(self.stats_key, "denied", 1)
                for account in denied:
                    self.client.hincrby(self._state_key(account), "denied", 1)
                return None

            _active_slots, _active_jobs, _last_used, _id, account = sorted(candidates)[0]
            lease_id = f"{account.redis_id}:{os.getpid()}:{uuid.uuid4().hex}"
            expires_at = now + self.lease_ttl_seconds
            self.client.hset(
                self._lease_key(lease_id),
                mapping={
                    "lease_id": lease_id,
                    "account_id": account.account_id,
                    "owner_job_id": owner_job_id,
                    "label": label,
                    "slots": str(requested_slots),
                    "created_at": f"{now:.6f}",
                    "expires_at": f"{expires_at:.6f}",
                },
            )
            self.client.expire(self._lease_key(lease_id), self.lease_ttl_seconds)
            self.client.zadd(self._leases_key(account), {lease_id: expires_at})
            self.client.expire(self._leases_key(account), self.lease_ttl_seconds)
            self.client.hset(self._state_key(account), "last_used_at", f"{now:.6f}")
            self.client.hincrby(self._state_key(account), "granted", 1)
            self.client.hincrby(self.stats_key, "granted", 1)
            return AccountLease(
                lease_id=lease_id,
                account_id=account.account_id,
                api_key=account.api_key,
                base_url=account.base_url,
                deepseek_model=account.deepseek_model,
                svg_model=account.svg_model,
                svg_repair_model=account.svg_repair_model,
                slots=requested_slots,
                expires_at=expires_at,
            )

    def _available(self, account: AccountPoolEntry, runtime: dict[str, Any], *, now: float, requested_slots: int) -> bool:
        if not runtime["enabled"]:
            return False
        cooldown = runtime.get("cooldown_until")
        if cooldown and float(cooldown) > now:
            return False
        if int(runtime["active_jobs"]) >= account.max_concurrent_jobs:
            return False
        if int(runtime["active_slots"]) + requested_slots > account.slot_capacity:
            return False
        return True

    def _runtime(self, account: AccountPoolEntry, *, now: float) -> dict[str, Any]:
        self._cleanup_expired(account, now)
        lease_ids = [str(item) for item in self.client.zrangebyscore(self._leases_key(account), now, "+inf")]
        active_slots = 0
        for lease_id in lease_ids:
            payload = self.client.hgetall(self._lease_key(lease_id)) or {}
            active_slots += _safe_int(payload.get("slots"), 0)
        state = self.client.hgetall(self._state_key(account)) or {}
        disabled = _safe_bool(state.get("disabled"), False)
        enabled_config = _safe_bool(state.get("enabled_config"), account.enabled)
        cooldown_until = _safe_float(state.get("cooldown_until"), 0.0)
        return {
            "active_jobs": len(lease_ids),
            "active_slots": active_slots,
            "cooldown_until": cooldown_until if cooldown_until > now else None,
            "enabled": account.enabled and enabled_config and not disabled,
            "last_error": str(state.get("last_error") or ""),
            "last_used_at": _safe_float(state.get("last_used_at"), 0.0),
            "granted": _safe_int(state.get("granted"), 0),
            "denied": _safe_int(state.get("denied"), 0),
        }

    def _cleanup_expired(self, account: AccountPoolEntry, now: float) -> None:
        leases_key = self._leases_key(account)
        expired = [str(item) for item in self.client.zrangebyscore(leases_key, "-inf", now)]
        for lease_id in expired:
            self.client.delete(self._lease_key(lease_id))
        if expired:
            self.client.zremrangebyscore(leases_key, "-inf", now)

    @contextmanager
    def _pool_lock(self):
        token = uuid.uuid4().hex
        deadline = time.time() + 2.0
        locked = False
        while time.time() < deadline:
            if self.client.set(self.lock_key, token, nx=True, ex=5):
                locked = True
                break
            time.sleep(0.05)
        try:
            yield locked
        finally:
            if locked:
                try:
                    if self.client.get(self.lock_key) == token:
                        self.client.delete(self.lock_key)
                except Exception:
                    pass

    def _key(self, suffix: str) -> str:
        return f"{self.key_prefix}:{suffix}"

    def _state_key(self, account: AccountPoolEntry) -> str:
        return self._key(f"account_pool:account:{account.redis_id}:state")

    def _leases_key(self, account: AccountPoolEntry) -> str:
        return self._key(f"account_pool:account:{account.redis_id}:leases")

    def _lease_key(self, lease_id: str) -> str:
        return self._key(f"account_pool:lease:{lease_id}")


def _required_str(item: dict[str, Any], field: str, index: int) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AccountPoolConfigError(f"account pool item #{index + 1} missing required string: {field}")
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_int(value: Any, default: int, *, minimum: int | None = None) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
