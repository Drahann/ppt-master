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


DEFAULT_ACCOUNT_TPM_LIMIT = 5_000_000
DEFAULT_ACCOUNT_TARGET_UTILIZATION = 0.9
DEFAULT_ACCOUNT_MAX_PARALLEL_TURNS = 10
DEFAULT_ACCOUNT_LIVE_WINDOW_SECONDS = 60
DEFAULT_ACCOUNT_LEASE_TTL_SECONDS = 60 * 60
DEFAULT_ACCOUNT_RATE_LIMIT_COOLDOWN_SECONDS = 60
DEFAULT_ACCOUNT_TRANSIENT_COOLDOWN_SECONDS = 30

ACCOUNT_RESULT_SUCCESS = "success"
ACCOUNT_RESULT_RATE_LIMITED = "rate_limited"
ACCOUNT_RESULT_AUTH_FAILED = "auth_failed"
ACCOUNT_RESULT_TRANSIENT = "transient"
ACCOUNT_RESULT_FAILED = "failed"
RETRYABLE_ACCOUNT_RESULTS = {ACCOUNT_RESULT_RATE_LIMITED, ACCOUNT_RESULT_TRANSIENT}


class AccountPoolConfigError(ValueError):
    """Raised when account pool configuration is present but invalid."""


@dataclass(frozen=True)
class AccountPoolEntry:
    account_id: str
    api_key: str
    base_url: str | None = None
    model: str | None = None
    tpm_limit: int = DEFAULT_ACCOUNT_TPM_LIMIT
    target_utilization: float = DEFAULT_ACCOUNT_TARGET_UTILIZATION
    max_parallel_turns: int = DEFAULT_ACCOUNT_MAX_PARALLEL_TURNS
    enabled: bool = True

    @property
    def redis_id(self) -> str:
        safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", self.account_id).strip("._-")
        return safe or uuid.uuid5(uuid.NAMESPACE_URL, self.account_id).hex

    @property
    def tpm_budget(self) -> int:
        return max(1, int(self.tpm_limit * self.target_utilization))

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "base_url": self.base_url,
            "model": self.model,
            "tpm_limit": self.tpm_limit,
            "target_utilization": self.target_utilization,
            "max_parallel_turns": self.max_parallel_turns,
            "enabled_config": self.enabled,
        }


@dataclass(frozen=True)
class AccountLease:
    lease_id: str
    account_id: str
    api_key: str
    base_url: str | None
    model: str | None
    expires_at: float

    def worker_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "account_id": self.account_id,
            "account_lease_id": self.lease_id,
            "api_key": self.api_key,
        }
        if self.base_url:
            payload["base_url"] = self.base_url
        if self.model:
            payload["model"] = self.model
        return payload


def account_pool_env_configured(env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    return bool(
        (env.get("PPT_API_QWEN_ACCOUNT_POOL_JSON") or "").strip()
        or (env.get("PPT_API_QWEN_ACCOUNT_POOL_FILE") or "").strip()
    )


def load_account_pool_entries(env: dict[str, str] | None = None) -> list[AccountPoolEntry]:
    env = env or os.environ
    raw = (env.get("PPT_API_QWEN_ACCOUNT_POOL_JSON") or "").strip()
    if not raw:
        file_raw = (env.get("PPT_API_QWEN_ACCOUNT_POOL_FILE") or "").strip()
        if file_raw:
            raw = Path(file_raw).expanduser().read_text(encoding="utf-8")
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AccountPoolConfigError(f"PPT_API_QWEN_ACCOUNT_POOL_JSON is not valid JSON: {exc}") from exc

    if isinstance(payload, dict):
        accounts_payload = payload.get("accounts")
    else:
        accounts_payload = payload
    if not isinstance(accounts_payload, list):
        raise AccountPoolConfigError("Qwen account pool config must be a JSON list or an object with accounts[]")

    accounts: list[AccountPoolEntry] = []
    seen: set[str] = set()
    for index, item in enumerate(accounts_payload):
        if not isinstance(item, dict):
            raise AccountPoolConfigError(f"Qwen account pool item #{index + 1} must be an object")
        account_id = _required_str(item, "account_id", index)
        api_key = _required_str(item, "api_key", index)
        if account_id in seen:
            raise AccountPoolConfigError(f"Duplicate Qwen account_id in pool: {account_id}")
        seen.add(account_id)
        accounts.append(
            AccountPoolEntry(
                account_id=account_id,
                api_key=api_key,
                base_url=_optional_str(item.get("base_url")),
                model=_optional_str(item.get("model")),
                tpm_limit=_safe_int(item.get("tpm_limit"), DEFAULT_ACCOUNT_TPM_LIMIT, minimum=1),
                target_utilization=_safe_float(
                    item.get("target_utilization"),
                    DEFAULT_ACCOUNT_TARGET_UTILIZATION,
                    minimum=0.01,
                    maximum=1.0,
                ),
                max_parallel_turns=_safe_int(
                    item.get("max_parallel_turns"),
                    DEFAULT_ACCOUNT_MAX_PARALLEL_TURNS,
                    minimum=1,
                ),
                enabled=_safe_bool(item.get("enabled"), True),
            )
        )
    return accounts


def classify_account_error(error: str | None) -> str:
    text = (error or "").strip().lower()
    if not text:
        return ACCOUNT_RESULT_SUCCESS
    if (
        "401" in text
        or "unauthorized" in text
        or "invalid api key" in text
        or "invalid_api_key" in text
        or "authentication" in text
        or "auth failed" in text
        or "鉴权" in text
    ):
        return ACCOUNT_RESULT_AUTH_FAILED
    if (
        "429" in text
        or "rate limit" in text
        or "ratelimit" in text
        or "too many requests" in text
        or "quota exceeded" in text
        or "限流" in text
    ):
        return ACCOUNT_RESULT_RATE_LIMITED
    if (
        "timeout" in text
        or "timed out" in text
        or "connection reset" in text
        or "temporarily unavailable" in text
        or re.search(r"\b5\d\d\b", text)
    ):
        return ACCOUNT_RESULT_TRANSIENT
    return ACCOUNT_RESULT_FAILED


def account_result_retryable(result: str) -> bool:
    return result in RETRYABLE_ACCOUNT_RESULTS


class RedisAccountPool:
    def __init__(
        self,
        client: Any,
        accounts: Iterable[AccountPoolEntry],
        *,
        key_prefix: str = "ppt",
        live_window_seconds: int | None = None,
        lease_ttl_seconds: int | None = None,
        rate_limit_cooldown_seconds: int | None = None,
        transient_cooldown_seconds: int | None = None,
    ) -> None:
        self.client = client
        self.accounts = list(accounts)
        self.accounts_by_id = {account.account_id: account for account in self.accounts}
        self.accounts_by_redis_id = {account.redis_id: account for account in self.accounts}
        self.key_prefix = key_prefix.strip().strip(":") or "ppt"
        self.live_window_seconds = max(5, live_window_seconds or _env_int("PPT_API_QWEN_ACCOUNT_POOL_WINDOW_SECONDS", DEFAULT_ACCOUNT_LIVE_WINDOW_SECONDS))
        self.lease_ttl_seconds = max(60, lease_ttl_seconds or _env_int("PPT_API_QWEN_ACCOUNT_LEASE_TTL_SECONDS", DEFAULT_ACCOUNT_LEASE_TTL_SECONDS))
        self.rate_limit_cooldown_seconds = max(
            1,
            rate_limit_cooldown_seconds
            or _env_int("PPT_API_QWEN_ACCOUNT_RATE_LIMIT_COOLDOWN_SECONDS", DEFAULT_ACCOUNT_RATE_LIMIT_COOLDOWN_SECONDS),
        )
        self.transient_cooldown_seconds = max(
            1,
            transient_cooldown_seconds
            or _env_int("PPT_API_QWEN_ACCOUNT_TRANSIENT_COOLDOWN_SECONDS", DEFAULT_ACCOUNT_TRANSIENT_COOLDOWN_SECONDS),
        )
        self.accounts_key = self._key("qwen_account_pool:accounts")
        self.lock_key = self._key("qwen_account_pool:lock")
        self.global_stats_key = self._key("qwen_account_pool:stats")
        self.sync_accounts()

    @property
    def configured(self) -> bool:
        return bool(self.accounts)

    def sync_accounts(self) -> None:
        for account in self.accounts:
            self.client.hset(
                self.accounts_key,
                account.redis_id,
                json.dumps(account.safe_metadata(), ensure_ascii=False),
            )
            state_key = self._state_key(account)
            self.client.hset(
                state_key,
                mapping={
                    "account_id": account.account_id,
                    "enabled_config": "1" if account.enabled else "0",
                    "tpm_limit": str(account.tpm_limit),
                    "target_utilization": f"{account.target_utilization:.6f}",
                    "max_parallel_turns": str(account.max_parallel_turns),
                },
            )
            if self.client.hget(state_key, "disabled") is None:
                self.client.hset(state_key, "disabled", "0")

    def acquire(
        self,
        *,
        label: str,
        owner_task_id: str | None = None,
        worker_request_path: str | None = None,
        estimated_tokens: int = 0,
    ) -> AccountLease | None:
        if not self.accounts:
            return None

        with self._pool_lock() as locked:
            if not locked:
                self.client.hincrby(self.global_stats_key, "denied", 1)
                return None
            self.sync_accounts()
            now = time.time()
            candidates: list[tuple[int, int, float, str, AccountPoolEntry]] = []
            denied_accounts: list[AccountPoolEntry] = []
            for account in self.accounts:
                runtime = self._runtime(account, now=now)
                if self._is_runtime_available(account, runtime, now=now, estimated_tokens=estimated_tokens):
                    candidates.append(
                        (
                            int(runtime["live_tpm_60s"]),
                            int(runtime["active_leases"]),
                            float(runtime["last_used_at"]),
                            account.account_id,
                            account,
                        )
                    )
                else:
                    denied_accounts.append(account)

            if not candidates:
                self.client.hincrby(self.global_stats_key, "denied", 1)
                for account in denied_accounts:
                    self.client.hincrby(self._state_key(account), "denied", 1)
                return None

            _live_tpm, _active, _last_used, _account_id, account = sorted(candidates)[0]
            lease_id = f"{account.redis_id}:{os.getpid()}:{uuid.uuid4().hex}"
            expires_at = now + self.lease_ttl_seconds
            self.client.hset(
                self._lease_key(lease_id),
                mapping={
                    "lease_id": lease_id,
                    "account_id": account.account_id,
                    "label": label,
                    "owner_task_id": owner_task_id or "",
                    "worker_request_path": worker_request_path or "",
                    "created_at": f"{now:.6f}",
                    "expires_at": f"{expires_at:.6f}",
                    "estimated_tokens": str(max(0, int(estimated_tokens))),
                },
            )
            self.client.expire(self._lease_key(lease_id), self.lease_ttl_seconds)
            self.client.zadd(self._leases_key(account), {lease_id: expires_at})
            self.client.expire(self._leases_key(account), self.lease_ttl_seconds)
            self.client.hset(
                self._state_key(account),
                mapping={
                    "last_used_at": f"{now:.6f}",
                    "last_lease_id": lease_id,
                },
            )
            self.client.hincrby(self._state_key(account), "granted", 1)
            self.client.hincrby(self.global_stats_key, "granted", 1)
            return AccountLease(
                lease_id=lease_id,
                account_id=account.account_id,
                api_key=account.api_key,
                base_url=account.base_url,
                model=account.model,
                expires_at=expires_at,
            )

    def release(
        self,
        lease: AccountLease,
        *,
        usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> str:
        account = self.accounts_by_id.get(lease.account_id)
        result = classify_account_error(error)
        if account is not None:
            total_tokens = _usage_total_tokens(usage)
            if total_tokens > 0:
                self.record_usage(account.account_id, total_tokens, lease_id=lease.lease_id)
            self.report_result(account.account_id, result=result, error=error)
            self.client.zrem(self._leases_key(account), lease.lease_id)
        self.client.delete(self._lease_key(lease.lease_id))
        return result

    def record_usage(self, account_id: str, total_tokens: int, *, lease_id: str | None = None) -> None:
        account = self.accounts_by_id.get(account_id)
        if account is None or total_tokens <= 0:
            return
        now = time.time()
        self._cleanup_live_tokens(account, now)
        member = f"{int(total_tokens)}|{lease_id or 'manual'}|{uuid.uuid4().hex}"
        self.client.zadd(self._live_key(account), {member: now})
        self.client.expire(self._live_key(account), self.live_window_seconds * 3)
        self.client.hset(self._state_key(account), "last_usage_at", f"{now:.6f}")

    def report_result(self, account_id: str, *, result: str, error: str | None = None) -> None:
        account = self.accounts_by_id.get(account_id)
        if account is None:
            return
        now = time.time()
        updates = {
            "last_result": result,
            "last_error": (error or "")[:500],
            "last_result_at": f"{now:.6f}",
        }
        if result == ACCOUNT_RESULT_AUTH_FAILED:
            updates["disabled"] = "1"
        elif result == ACCOUNT_RESULT_RATE_LIMITED:
            updates["cooldown_until"] = f"{now + self.rate_limit_cooldown_seconds:.6f}"
        elif result == ACCOUNT_RESULT_TRANSIENT:
            updates["cooldown_until"] = f"{now + self.transient_cooldown_seconds:.6f}"
        elif result == ACCOUNT_RESULT_SUCCESS:
            updates["last_error"] = ""
        self.client.hset(self._state_key(account), mapping=updates)

    def snapshot(self) -> dict[str, Any]:
        if not self.accounts:
            return {"enabled": False, "configured": False, "accounts": []}
        now = time.time()
        accounts = []
        for account in self.accounts:
            runtime = self._runtime(account, now=now)
            accounts.append(
                {
                    "account_id": account.account_id,
                    "model": account.model,
                    "base_url": account.base_url,
                    "live_tpm_60s": runtime["live_tpm_60s"],
                    "active_leases": runtime["active_leases"],
                    "cooldown_until": runtime["cooldown_until"],
                    "enabled": runtime["enabled"],
                    "granted": runtime["granted"],
                    "denied": runtime["denied"],
                    "last_error": runtime["last_error"],
                    "tpm_limit": account.tpm_limit,
                    "target_utilization": account.target_utilization,
                    "max_parallel_turns": account.max_parallel_turns,
                }
            )
        stats = self.client.hgetall(self.global_stats_key) or {}
        return {
            "enabled": True,
            "configured": True,
            "window_seconds": self.live_window_seconds,
            "lease_ttl_seconds": self.lease_ttl_seconds,
            "granted": _safe_int(stats.get("granted"), 0),
            "denied": _safe_int(stats.get("denied"), 0),
            "accounts": accounts,
        }

    def _runtime(self, account: AccountPoolEntry, *, now: float) -> dict[str, Any]:
        self._cleanup_expired_leases(account, now)
        live_tpm = self._live_tpm(account, now)
        active_leases = len(self.client.zrangebyscore(self._leases_key(account), now, "+inf"))
        state = self.client.hgetall(self._state_key(account)) or {}
        disabled = _safe_bool(state.get("disabled"), False)
        config_enabled = _safe_bool(state.get("enabled_config"), account.enabled)
        cooldown_until = _safe_float(state.get("cooldown_until"), 0.0)
        return {
            "live_tpm_60s": live_tpm,
            "active_leases": active_leases,
            "cooldown_until": cooldown_until if cooldown_until > now else None,
            "enabled": account.enabled and config_enabled and not disabled,
            "granted": _safe_int(state.get("granted"), 0),
            "denied": _safe_int(state.get("denied"), 0),
            "last_error": str(state.get("last_error") or ""),
            "last_used_at": _safe_float(state.get("last_used_at"), 0.0),
        }

    def _is_runtime_available(
        self,
        account: AccountPoolEntry,
        runtime: dict[str, Any],
        *,
        now: float,
        estimated_tokens: int,
    ) -> bool:
        if not runtime["enabled"]:
            return False
        cooldown_until = runtime.get("cooldown_until")
        if cooldown_until and float(cooldown_until) > now:
            return False
        if int(runtime["active_leases"]) >= account.max_parallel_turns:
            return False
        if int(runtime["live_tpm_60s"]) + max(0, int(estimated_tokens)) >= account.tpm_budget:
            return False
        return True

    def _live_tpm(self, account: AccountPoolEntry, now: float) -> int:
        self._cleanup_live_tokens(account, now)
        total = 0
        for member in self.client.zrange(self._live_key(account), 0, -1):
            token_text = str(member).split("|", 1)[0]
            total += _safe_int(token_text, 0)
        return max(0, total)

    def _cleanup_live_tokens(self, account: AccountPoolEntry, now: float) -> None:
        self.client.zremrangebyscore(self._live_key(account), "-inf", f"{now - self.live_window_seconds:.6f}")

    def _cleanup_expired_leases(self, account: AccountPoolEntry, now: float) -> None:
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
        return self._key(f"qwen_account_pool:account:{account.redis_id}:state")

    def _live_key(self, account: AccountPoolEntry) -> str:
        return self._key(f"qwen_account_pool:account:{account.redis_id}:live_tokens")

    def _leases_key(self, account: AccountPoolEntry) -> str:
        return self._key(f"qwen_account_pool:account:{account.redis_id}:leases")

    def _lease_key(self, lease_id: str) -> str:
        return self._key(f"qwen_account_pool:lease:{lease_id}")


def _required_str(item: dict[str, Any], field: str, index: int) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AccountPoolConfigError(f"Qwen account pool item #{index + 1} missing required string: {field}")
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _env_int(name: str, default: int) -> int:
    return _safe_int(os.getenv(name), default, minimum=1)


def _safe_int(value: Any, default: int, *, minimum: int | None = None) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _safe_float(
    value: Any,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _safe_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _usage_total_tokens(usage: dict[str, Any] | None) -> int:
    if not isinstance(usage, dict):
        return 0
    total = _safe_int(usage.get("total_tokens"), 0)
    if total > 0:
        return total
    return _safe_int(usage.get("prompt_tokens"), 0) + _safe_int(usage.get("completion_tokens"), 0)
