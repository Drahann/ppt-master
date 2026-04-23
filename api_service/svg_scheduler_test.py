from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from api_service.account_pool import (
    AccountLease,
    AccountPoolEntry,
    RedisAccountPool,
    classify_account_error,
)
from api_service.svg_scheduler import compute_scheduler_grants
from api_service.svg_scheduler import _merge_worker_request_credentials


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_SCRIPTS_DIR = REPO_ROOT / "skills" / "ppt-master" / "scripts"
if str(RUNNER_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_SCRIPTS_DIR))

from qwen_ppt_runner import SlidePlanEntry, split_plan_into_batches  # type: ignore  # noqa: E402


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        removed = 0
        for key in keys:
            removed += 1 if self.values.pop(key, None) is not None else 0
            removed += 1 if self.hashes.pop(key, None) is not None else 0
            removed += 1 if self.zsets.pop(key, None) is not None else 0
        return removed

    def exists(self, key):
        return key in self.values or key in self.hashes or key in self.zsets

    def expire(self, key, seconds):
        return True

    def hset(self, name, key=None, value=None, mapping=None):
        bucket = self.hashes.setdefault(name, {})
        if mapping is not None:
            for item_key, item_value in mapping.items():
                bucket[str(item_key)] = str(item_value)
            return len(mapping)
        bucket[str(key)] = str(value)
        return 1

    def hget(self, name, key):
        return self.hashes.get(name, {}).get(str(key))

    def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    def hincrby(self, name, key, amount):
        bucket = self.hashes.setdefault(name, {})
        current = int(float(bucket.get(str(key), "0")))
        current += int(amount)
        bucket[str(key)] = str(current)
        return current

    def hdel(self, name, *keys):
        bucket = self.hashes.setdefault(name, {})
        removed = 0
        for key in keys:
            if str(key) in bucket:
                del bucket[str(key)]
                removed += 1
        return removed

    def hmget(self, name, keys):
        bucket = self.hashes.get(name, {})
        return [bucket.get(str(key)) for key in keys]

    def zadd(self, name, mapping):
        bucket = self.zsets.setdefault(name, {})
        for member, score in mapping.items():
            bucket[str(member)] = float(score)
        return len(mapping)

    def zrange(self, name, start, end):
        items = [member for member, _score in sorted(self.zsets.get(name, {}).items(), key=lambda item: (item[1], item[0]))]
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    def zrangebyscore(self, name, min_score, max_score):
        low = self._score(min_score, float("-inf"))
        high = self._score(max_score, float("inf"))
        return [
            member
            for member, score in sorted(self.zsets.get(name, {}).items(), key=lambda item: (item[1], item[0]))
            if low <= score <= high
        ]

    def zrem(self, name, *members):
        bucket = self.zsets.setdefault(name, {})
        removed = 0
        for member in members:
            if str(member) in bucket:
                del bucket[str(member)]
                removed += 1
        return removed

    def zremrangebyscore(self, name, min_score, max_score):
        low = self._score(min_score, float("-inf"))
        high = self._score(max_score, float("inf"))
        members = [member for member, score in self.zsets.get(name, {}).items() if low <= score <= high]
        return self.zrem(name, *members)

    @staticmethod
    def _score(value, fallback):
        if value in {"-inf", "+inf"}:
            return float(value.replace("+", ""))
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback


class ComputeSchedulerGrantsTests(unittest.TestCase):
    def test_distributes_base_share_and_remainder_without_wasting_slots(self) -> None:
        requested = {f"job_{index:02d}": 7 for index in range(25)}
        demand = {f"job_{index:02d}": 6 for index in range(25)}
        oldest = {job_id: float(index) for index, job_id in enumerate(requested)}
        history = {job_id: 0 for job_id in requested}

        decision = compute_scheduler_grants(
            total_slots=72,
            job_requested_workers=requested,
            job_total_demand=demand,
            job_oldest_pending_at=oldest,
            historical_grants=history,
        )

        grants = decision.granted_slots_by_job
        self.assertEqual(decision.base_share, 2)
        self.assertEqual(decision.remainder_slots, 22)
        self.assertEqual(sum(grants.values()), 72)
        self.assertEqual(sum(1 for value in grants.values() if value == 3), 22)
        self.assertEqual(sum(1 for value in grants.values() if value == 2), 3)
        self.assertEqual(decision.underutilized_slots, 0)

    def test_respects_requested_workers_and_exhausted_batches(self) -> None:
        requested = {
            "job_a": 7,
            "job_b": 7,
            "job_c": 2,
        }
        demand = {
            "job_a": 1,
            "job_b": 4,
            "job_c": 2,
        }
        oldest = {
            "job_a": 1.0,
            "job_b": 2.0,
            "job_c": 3.0,
        }
        history = {
            "job_a": 10,
            "job_b": 2,
            "job_c": 1,
        }

        decision = compute_scheduler_grants(
            total_slots=10,
            job_requested_workers=requested,
            job_total_demand=demand,
            job_oldest_pending_at=oldest,
            historical_grants=history,
        )

        self.assertEqual(decision.granted_slots_by_job["job_a"], 1)
        self.assertEqual(decision.granted_slots_by_job["job_b"], 4)
        self.assertEqual(decision.granted_slots_by_job["job_c"], 2)
        self.assertEqual(sum(decision.granted_slots_by_job.values()), 7)
        self.assertEqual(decision.underutilized_slots, 3)

    def test_requested_worker_limit_caps_distribution(self) -> None:
        requested = {
            "job_a": 1,
            "job_b": 3,
            "job_c": 7,
        }
        demand = {
            "job_a": 6,
            "job_b": 6,
            "job_c": 6,
        }
        oldest = {
            "job_a": 1.0,
            "job_b": 2.0,
            "job_c": 3.0,
        }
        history = {
            "job_a": 0,
            "job_b": 0,
            "job_c": 0,
        }

        decision = compute_scheduler_grants(
            total_slots=10,
            job_requested_workers=requested,
            job_total_demand=demand,
            job_oldest_pending_at=oldest,
            historical_grants=history,
        )

        self.assertEqual(decision.granted_slots_by_job["job_a"], 1)
        self.assertEqual(decision.granted_slots_by_job["job_b"], 3)
        self.assertEqual(decision.granted_slots_by_job["job_c"], 6)
        self.assertEqual(sum(decision.granted_slots_by_job.values()), 10)


class RedisAccountPoolTests(unittest.TestCase):
    def test_selects_lowest_live_tpm_account(self) -> None:
        client = FakeRedis()
        pool = RedisAccountPool(
            client,
            [
                AccountPoolEntry("account-a", "key-a", tpm_limit=1000),
                AccountPoolEntry("account-b", "key-b", tpm_limit=1000),
                AccountPoolEntry("account-c", "key-c", tpm_limit=1000),
            ],
            key_prefix="test",
        )
        pool.record_usage("account-a", 700)
        pool.record_usage("account-b", 200)

        lease = pool.acquire(label="batch-1")

        self.assertIsNotNone(lease)
        assert lease is not None
        self.assertEqual(lease.account_id, "account-c")
        self.assertEqual(lease.api_key, "key-c")

    def test_tpm_budget_excludes_saturated_account(self) -> None:
        client = FakeRedis()
        pool = RedisAccountPool(
            client,
            [
                AccountPoolEntry("saturated", "key-a", tpm_limit=100, target_utilization=0.9),
                AccountPoolEntry("available", "key-b", tpm_limit=100, target_utilization=0.9),
            ],
            key_prefix="test",
        )
        pool.record_usage("saturated", 90)

        lease = pool.acquire(label="batch-1")

        self.assertIsNotNone(lease)
        assert lease is not None
        self.assertEqual(lease.account_id, "available")

    def test_release_records_usage_and_clears_active_lease(self) -> None:
        client = FakeRedis()
        pool = RedisAccountPool(
            client,
            [AccountPoolEntry("account-a", "key-a", tpm_limit=1000)],
            key_prefix="test",
        )
        lease = pool.acquire(label="batch-1")
        assert lease is not None

        result = pool.release(lease, usage={"total_tokens": 123})
        snapshot = pool.snapshot()

        self.assertEqual(result, "success")
        self.assertEqual(snapshot["accounts"][0]["live_tpm_60s"], 0)
        self.assertEqual(snapshot["accounts"][0]["active_leases"], 0)

    def test_release_can_record_usage_when_legacy_release_accounting_is_enabled(self) -> None:
        previous = os.environ.get("PPT_API_QWEN_ACCOUNT_POOL_RECORD_RELEASE_USAGE")
        os.environ["PPT_API_QWEN_ACCOUNT_POOL_RECORD_RELEASE_USAGE"] = "1"
        try:
            client = FakeRedis()
            pool = RedisAccountPool(
                client,
                [AccountPoolEntry("account-a", "key-a", tpm_limit=1000)],
                key_prefix="test",
            )
            lease = pool.acquire(label="batch-1")
            assert lease is not None

            pool.release(lease, usage={"total_tokens": 123})
            snapshot = pool.snapshot()

            self.assertEqual(snapshot["accounts"][0]["live_tpm_60s"], 123)
        finally:
            if previous is None:
                os.environ.pop("PPT_API_QWEN_ACCOUNT_POOL_RECORD_RELEASE_USAGE", None)
            else:
                os.environ["PPT_API_QWEN_ACCOUNT_POOL_RECORD_RELEASE_USAGE"] = previous

    def test_rate_limit_cooldown_and_auth_disable_account(self) -> None:
        client = FakeRedis()
        pool = RedisAccountPool(
            client,
            [AccountPoolEntry("account-a", "key-a", tpm_limit=1000)],
            key_prefix="test",
            rate_limit_cooldown_seconds=30,
        )
        lease = pool.acquire(label="batch-1")
        assert lease is not None

        result = pool.release(lease, error="HTTP 429: rate limit")
        cooldown_snapshot = pool.snapshot()["accounts"][0]

        self.assertEqual(result, "rate_limited")
        self.assertIsNotNone(cooldown_snapshot["cooldown_until"])
        self.assertIsNone(pool.acquire(label="batch-2"))

        pool.report_result(
            "account-a",
            result=classify_account_error("401 unauthorized"),
            error="401 unauthorized",
        )
        disabled_snapshot = pool.snapshot()["accounts"][0]

        self.assertFalse(disabled_snapshot["enabled"])


class SvgSchedulerAccountLeaseTests(unittest.TestCase):
    def test_worker_request_credentials_are_merged_without_dropping_existing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request_path = Path(temp_dir) / "worker.json"
            request_path.write_text(
                '{"mode": "svg_batch_worker", "batch_index": 0}\n',
                encoding="utf-8",
            )
            lease = AccountLease(
                lease_id="lease-1",
                account_id="account-a",
                api_key="secret-key",
                base_url="https://example.test/v1",
                model="qwen-test",
                expires_at=time.time() + 60,
            )

            _merge_worker_request_credentials(request_path, lease)
            payload = json.loads(request_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["mode"], "svg_batch_worker")
            self.assertEqual(payload["account_id"], "account-a")
            self.assertEqual(payload["account_lease_id"], "lease-1")
            self.assertEqual(payload["api_key"], "secret-key")
            self.assertEqual(payload["base_url"], "https://example.test/v1")
            self.assertEqual(payload["model"], "qwen-test")


class AnchorEvenBatchingTests(unittest.TestCase):
    def test_anchor_even_splits_32_pages_into_expected_groups(self) -> None:
        plan = [
            SlidePlanEntry(
                index=index + 1,
                filename=f"slide_{index + 1:02d}.svg",
                heading=f"slide-{index + 1}",
                kind="content",
                source_h2=None,
                source_h3=None,
            )
            for index in range(32)
        ]

        batches = split_plan_into_batches(plan, 5, "anchor_even")

        self.assertEqual([len(batch) for batch in batches], [2, 6, 6, 6, 6, 6])
        self.assertEqual(batches[0][0].filename, "slide_01.svg")
        self.assertEqual(batches[-1][-1].filename, "slide_32.svg")


if __name__ == "__main__":
    unittest.main()
