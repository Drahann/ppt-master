from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, is_dataclass
from typing import Any

from .config import Settings


class RedisJobStoreError(RuntimeError):
    pass


class RedisJobStore:
    """Redis-backed job queue and status store for PPT generation."""

    def __init__(self, redis_url: str, *, key_prefix: str = "ppt") -> None:
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - depends on deployment env
            raise RedisJobStoreError("redis package is not installed") from exc

        self.redis_url = redis_url
        self.key_prefix = key_prefix.strip().strip(":") or "ppt"
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.pending_queue_key = self.key("jobs:pending")
        self.recent_key = self.key("jobs:recent")
        self.running_key = self.key("jobs:running")

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedisJobStore | None":
        if not settings.redis_url:
            return None
        return cls(settings.redis_url, key_prefix=settings.redis_key_prefix)

    def key(self, suffix: str) -> str:
        return f"{self.key_prefix}:{suffix}"

    def job_key(self, job_id: str) -> str:
        return self.key(f"jobs:{job_id}")

    def ping(self) -> bool:
        return bool(self.client.ping())

    def create_job(self, request: Any, *, title: str | None = None) -> str:
        job_id = f"job_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}"
        now = time.time()
        request_payload = asdict(request) if is_dataclass(request) else dict(request)
        record = {
            "job_id": job_id,
            "report_id": request_payload.get("report_id"),
            "title": title,
            "status": "accepted",
            "stage": "accepted",
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "request": request_payload,
            "result": None,
            "error": None,
        }
        self.client.set(self.job_key(job_id), json.dumps(record, ensure_ascii=False))
        self.client.lpush(self.recent_key, job_id)
        self.client.ltrim(self.recent_key, 0, 99)
        self.enqueue(job_id)
        return job_id

    def enqueue(self, job_id: str) -> None:
        record = self.get_job(job_id)
        if record is None:
            raise RedisJobStoreError(f"unknown job_id: {job_id}")
        if record.get("status") == "cancelled":
            return
        record["status"] = "queued"
        record["stage"] = "queued"
        record["updated_at"] = time.time()
        self._write(record)
        self.client.rpush(self.pending_queue_key, job_id)

    def dequeue(self, timeout_seconds: int = 2) -> str | None:
        item = self.client.blpop(self.pending_queue_key, timeout=timeout_seconds)
        if item is None:
            return None
        _queue_name, job_id = item
        return str(job_id)

    def mark_running(self, job_id: str, *, stage: str = "running") -> dict[str, Any] | None:
        record = self.get_job(job_id)
        if record is None:
            return None
        if record.get("status") == "cancelled":
            return record
        now = time.time()
        record["status"] = "running"
        record["stage"] = stage
        record["started_at"] = record.get("started_at") or now
        record["updated_at"] = now
        self.client.sadd(self.running_key, job_id)
        self._write(record)
        return record

    def update_stage(self, job_id: str, stage: str) -> None:
        record = self.get_job(job_id)
        if record is None:
            return
        record["stage"] = stage
        record["updated_at"] = time.time()
        self._write(record)

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        record = self.get_job(job_id)
        if record is None:
            return
        now = time.time()
        record["status"] = "succeeded"
        record["stage"] = "succeeded"
        record["updated_at"] = now
        record["finished_at"] = now
        record["result"] = result
        record["error"] = None
        self.client.srem(self.running_key, job_id)
        self._write(record)

    def fail(self, job_id: str, error: str) -> None:
        record = self.get_job(job_id)
        if record is None:
            return
        now = time.time()
        record["status"] = "failed"
        record["stage"] = "failed"
        record["updated_at"] = now
        record["finished_at"] = now
        record["error"] = error
        self.client.srem(self.running_key, job_id)
        self._write(record)

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        record = self.get_job(job_id)
        if record is None:
            return None
        if record.get("status") in {"succeeded", "failed"}:
            return record
        now = time.time()
        record["status"] = "cancelled"
        record["stage"] = "cancelled"
        record["updated_at"] = now
        record["finished_at"] = record.get("finished_at") or now
        self.client.srem(self.running_key, job_id)
        self._write(record)
        return record

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        raw = self.client.get(self.job_key(job_id))
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RedisJobStoreError(f"job record is not valid JSON: {job_id}") from exc
        return payload if isinstance(payload, dict) else None

    def snapshot(self) -> dict[str, Any]:
        pending_ids = [str(item) for item in self.client.lrange(self.pending_queue_key, 0, 49)]
        running_ids = [str(item) for item in self.client.smembers(self.running_key)]
        recent_ids = [str(item) for item in self.client.lrange(self.recent_key, 0, 19)]
        pending_records = self._load_records(pending_ids)
        running_records = self._load_records(running_ids)
        recent_records = self._load_records(recent_ids)
        status_counts: dict[str, int] = {}
        stage_counts: dict[str, int] = {}
        now = time.time()
        for record in pending_records + running_records:
            status = str(record.get("status") or "unknown")
            stage = str(record.get("stage") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        oldest_pending_seconds = 0.0
        if pending_records:
            oldest_created_at = min(float(record.get("created_at") or now) for record in pending_records)
            oldest_pending_seconds = round(max(0.0, now - oldest_created_at), 1)
        return {
            "enabled": True,
            "pending": self.client.llen(self.pending_queue_key),
            "running": self.client.scard(self.running_key),
            "recent": recent_ids,
            "pending_records": pending_records,
            "running_records": running_records,
            "recent_records": recent_records,
            "status_counts": status_counts,
            "stage_counts": stage_counts,
            "oldest_pending_seconds": oldest_pending_seconds,
        }

    def _write(self, record: dict[str, Any]) -> None:
        self.client.set(self.job_key(str(record["job_id"])), json.dumps(record, ensure_ascii=False))

    def _load_records(self, job_ids: list[str]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for job_id in job_ids:
            record = self.get_job(job_id)
            if record is not None:
                records.append(
                    {
                        "job_id": record.get("job_id"),
                        "report_id": record.get("report_id"),
                        "title": record.get("title"),
                        "status": record.get("status"),
                        "stage": record.get("stage"),
                        "created_at": record.get("created_at"),
                        "updated_at": record.get("updated_at"),
                        "started_at": record.get("started_at"),
                        "finished_at": record.get("finished_at"),
                        "error": record.get("error"),
                    }
                )
        records.sort(key=lambda item: float(item.get("created_at") or 0))
        return records
