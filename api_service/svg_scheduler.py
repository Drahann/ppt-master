from __future__ import annotations

import json
import logging
import math
import os
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .account_pool import AccountLease, RedisAccountPool, account_result_retryable


logger = logging.getLogger(__name__)

SVG_SCHEDULER_PENDING_KEY_SUFFIX = "svg_scheduler:pending"
SVG_SCHEDULER_RUNNING_KEY_SUFFIX = "svg_scheduler:running"
SVG_SCHEDULER_RECENT_KEY_SUFFIX = "svg_scheduler:recent"
SVG_SCHEDULER_JOB_GRANTS_KEY_SUFFIX = "svg_scheduler:job_grants"
SVG_SCHEDULER_TASK_KEY_PREFIX = "svg_scheduler:task:"
SVG_SCHEDULER_ANCHOR_KEY_PREFIX = "svg_scheduler:anchor_done:"
SVG_SCHEDULER_HEARTBEAT_KEY_PREFIX = "svg_scheduler:heartbeat:"

SVG_TASK_PENDING = "pending"
SVG_TASK_RUNNING = "running"
SVG_TASK_SUCCEEDED = "succeeded"
SVG_TASK_FAILED = "failed"
SVG_TASK_TERMINAL = {SVG_TASK_SUCCEEDED, SVG_TASK_FAILED}


@dataclass(frozen=True)
class SvgBatchTask:
    task_id: str
    owner_job_id: str
    report_id: str
    batch_index: int
    total_batches: int
    requested_workers: int
    worker_request_path: str
    enqueued_at: float
    requires_anchor: bool = False
    status: str = SVG_TASK_PENDING
    started_at: float | None = None
    finished_at: float | None = None
    session_id: str | None = None
    error: str | None = None
    worker_name: str | None = None
    account_id: str | None = None
    account_lease_id: str | None = None
    account_retry_count: int = 0
    scheduler_owner: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SvgBatchTask":
        return cls(
            task_id=str(payload["task_id"]),
            owner_job_id=str(payload["owner_job_id"]),
            report_id=str(payload.get("report_id") or payload["owner_job_id"]),
            batch_index=int(payload["batch_index"]),
            total_batches=int(payload["total_batches"]),
            requested_workers=max(1, int(payload["requested_workers"])),
            worker_request_path=str(payload["worker_request_path"]),
            enqueued_at=float(payload.get("enqueued_at") or 0.0),
            requires_anchor=bool(payload.get("requires_anchor")),
            status=str(payload.get("status") or SVG_TASK_PENDING),
            started_at=_safe_float(payload.get("started_at")),
            finished_at=_safe_float(payload.get("finished_at")),
            session_id=_safe_str(payload.get("session_id")),
            error=_safe_str(payload.get("error")),
            worker_name=_safe_str(payload.get("worker_name")),
            account_id=_safe_str(payload.get("account_id")),
            account_lease_id=_safe_str(payload.get("account_lease_id")),
            account_retry_count=_safe_int(payload.get("account_retry_count")),
            scheduler_owner=_safe_str(payload.get("scheduler_owner")),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "owner_job_id": self.owner_job_id,
            "report_id": self.report_id,
            "batch_index": self.batch_index,
            "total_batches": self.total_batches,
            "requested_workers": self.requested_workers,
            "worker_request_path": self.worker_request_path,
            "enqueued_at": self.enqueued_at,
            "requires_anchor": self.requires_anchor,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "session_id": self.session_id,
            "error": self.error,
            "worker_name": self.worker_name,
            "account_id": self.account_id,
            "account_lease_id": self.account_lease_id,
            "account_retry_count": self.account_retry_count,
            "scheduler_owner": self.scheduler_owner,
        }


@dataclass(frozen=True)
class SchedulerDecision:
    runnable_jobs: int
    pending_batches: int
    running_batches: int
    total_slots: int
    base_share: int
    remainder_slots: int
    granted_slots_by_job: dict[str, int]
    underutilized_slots: int
    queue_wait_p50: float
    queue_wait_p95: float


def scheduler_enabled_from_env() -> bool:
    raw = os.getenv("PPT_API_SVG_SCHEDULER_ENABLED")
    if raw is None:
        return False
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def svg_scheduler_owner_from_env() -> str:
    raw = os.getenv("PPT_API_SVG_SCHEDULER_OWNER") or os.getenv("PPT_SERVER_ID")
    owner = (raw or "").strip()
    return owner or socket.gethostname()


def scheduler_key(key_prefix: str, suffix: str) -> str:
    normalized = (key_prefix or "ppt").strip().strip(":") or "ppt"
    return f"{normalized}:{suffix}"


def svg_scheduler_task_key(key_prefix: str, task_id: str) -> str:
    return scheduler_key(key_prefix, f"{SVG_SCHEDULER_TASK_KEY_PREFIX}{task_id}")


def svg_scheduler_anchor_key(key_prefix: str, owner_job_id: str) -> str:
    return scheduler_key(key_prefix, f"{SVG_SCHEDULER_ANCHOR_KEY_PREFIX}{owner_job_id}")


def svg_scheduler_heartbeat_key(key_prefix: str, task_id: str) -> str:
    return scheduler_key(key_prefix, f"{SVG_SCHEDULER_HEARTBEAT_KEY_PREFIX}{task_id}")


def build_svg_scheduler_task_id(owner_job_id: str, batch_index: int) -> str:
    return f"{owner_job_id}_batch_{batch_index + 1:02d}_{uuid.uuid4().hex[:8]}"


def compute_scheduler_grants(
    total_slots: int,
    job_requested_workers: dict[str, int],
    job_total_demand: dict[str, int],
    job_oldest_pending_at: dict[str, float],
    historical_grants: dict[str, int],
) -> SchedulerDecision:
    eligible_jobs = [
        job_id
        for job_id, demand in job_total_demand.items()
        if demand > 0 and job_requested_workers.get(job_id, 0) > 0
    ]
    if total_slots <= 0 or not eligible_jobs:
        return SchedulerDecision(
            runnable_jobs=0,
            pending_batches=0,
            running_batches=0,
            total_slots=max(0, total_slots),
            base_share=0,
            remainder_slots=0,
            granted_slots_by_job={},
            underutilized_slots=max(0, total_slots),
            queue_wait_p50=0.0,
            queue_wait_p95=0.0,
        )

    runnable_jobs = len(eligible_jobs)
    base_share = total_slots // runnable_jobs
    grants_by_job: dict[str, int] = {}
    used_slots = 0
    for job_id in eligible_jobs:
        job_cap = max(0, min(job_requested_workers[job_id], job_total_demand[job_id]))
        grant = min(job_cap, base_share)
        grants_by_job[job_id] = grant
        used_slots += grant

    mathematical_remainder = total_slots % runnable_jobs
    remaining_slots = max(0, total_slots - used_slots)

    def priority(job_id: str) -> tuple[float, int, str]:
        return (
            historical_grants.get(job_id, 0),
            job_oldest_pending_at.get(job_id, math.inf),
            job_id,
        )

    while remaining_slots > 0:
        candidates = [
            job_id
            for job_id in eligible_jobs
            if grants_by_job.get(job_id, 0) < min(job_requested_workers[job_id], job_total_demand[job_id])
        ]
        if not candidates:
            break
        progressed = False
        for job_id in sorted(candidates, key=priority):
            if remaining_slots <= 0:
                break
            job_cap = min(job_requested_workers[job_id], job_total_demand[job_id])
            if grants_by_job[job_id] >= job_cap:
                continue
            grants_by_job[job_id] += 1
            remaining_slots -= 1
            progressed = True
        if not progressed:
            break

    return SchedulerDecision(
        runnable_jobs=runnable_jobs,
        pending_batches=0,
        running_batches=0,
        total_slots=max(0, total_slots),
        base_share=base_share,
        remainder_slots=mathematical_remainder,
        granted_slots_by_job=grants_by_job,
        underutilized_slots=max(0, remaining_slots),
        queue_wait_p50=0.0,
        queue_wait_p95=0.0,
    )


class RedisSvgSchedulerStore:
    def __init__(self, client: Any, *, key_prefix: str = "ppt") -> None:
        self.client = client
        self.key_prefix = key_prefix.strip().strip(":") or "ppt"
        self.pending_key = scheduler_key(self.key_prefix, SVG_SCHEDULER_PENDING_KEY_SUFFIX)
        self.running_key = scheduler_key(self.key_prefix, SVG_SCHEDULER_RUNNING_KEY_SUFFIX)
        self.recent_key = scheduler_key(self.key_prefix, SVG_SCHEDULER_RECENT_KEY_SUFFIX)
        self.job_grants_key = scheduler_key(self.key_prefix, SVG_SCHEDULER_JOB_GRANTS_KEY_SUFFIX)

    def enqueue_task(self, task: SvgBatchTask) -> None:
        payload = task.to_payload()
        self.client.set(svg_scheduler_task_key(self.key_prefix, task.task_id), json.dumps(payload, ensure_ascii=False))
        self.client.zadd(self.pending_key, {task.task_id: task.enqueued_at})

    def get_task(self, task_id: str) -> SvgBatchTask | None:
        raw = self.client.get(svg_scheduler_task_key(self.key_prefix, task_id))
        if not raw:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        return SvgBatchTask.from_payload(payload)

    def list_pending_tasks(self) -> list[SvgBatchTask]:
        task_ids = [str(item) for item in self.client.zrange(self.pending_key, 0, -1)]
        return self._load_tasks(task_ids)

    def list_running_tasks(self) -> list[SvgBatchTask]:
        task_ids = [str(item) for item in self.client.zrange(self.running_key, 0, -1)]
        return self._load_tasks(task_ids)

    def list_recent_tasks(self, limit: int = 200) -> list[SvgBatchTask]:
        task_ids = [str(item) for item in self.client.lrange(self.recent_key, 0, max(0, limit - 1))]
        return self._load_tasks(task_ids)

    def mark_running(
        self,
        task_id: str,
        *,
        worker_name: str | None = None,
        account_id: str | None = None,
        account_lease_id: str | None = None,
    ) -> SvgBatchTask | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        now = time.time()
        updated = SvgBatchTask(
            **{
                **task.to_payload(),
                "status": SVG_TASK_RUNNING,
                "started_at": now,
                "worker_name": worker_name,
                "account_id": account_id,
                "account_lease_id": account_lease_id,
            }
        )
        self._write_task(updated)
        self.client.zrem(self.pending_key, task_id)
        self.client.zadd(self.running_key, {task_id: now})
        return updated

    def mark_completed(self, task_id: str, *, session_id: str | None = None) -> SvgBatchTask | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        now = time.time()
        updated = SvgBatchTask(
            **{
                **task.to_payload(),
                "status": SVG_TASK_SUCCEEDED,
                "finished_at": now,
                "session_id": session_id,
                "error": None,
            }
        )
        self._finalize_task(updated)
        if updated.batch_index == 0:
            self.client.set(svg_scheduler_anchor_key(self.key_prefix, updated.owner_job_id), "1")
        return updated

    def mark_failed(self, task_id: str, error: str) -> SvgBatchTask | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        now = time.time()
        updated = SvgBatchTask(
            **{
                **task.to_payload(),
                "status": SVG_TASK_FAILED,
                "finished_at": now,
                "error": error,
            }
        )
        self._finalize_task(updated)
        return updated

    def requeue_task(self, task_id: str, error: str) -> SvgBatchTask | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        now = time.time()
        updated = SvgBatchTask(
            **{
                **task.to_payload(),
                "status": SVG_TASK_PENDING,
                "started_at": None,
                "finished_at": None,
                "session_id": None,
                "error": error,
                "worker_name": None,
                "account_id": None,
                "account_lease_id": None,
                "account_retry_count": task.account_retry_count + 1,
            }
        )
        self._write_task(updated)
        self.client.zrem(self.running_key, task.task_id)
        self.client.zadd(self.pending_key, {task.task_id: now})
        return updated

    def anchor_completed(self, owner_job_id: str) -> bool:
        return bool(self.client.exists(svg_scheduler_anchor_key(self.key_prefix, owner_job_id)))

    def increment_job_grants(self, owner_job_id: str) -> int:
        return int(self.client.hincrby(self.job_grants_key, owner_job_id, 1))

    def get_job_grants(self, owner_job_ids: list[str]) -> dict[str, int]:
        if not owner_job_ids:
            return {}
        payload = self.client.hmget(self.job_grants_key, owner_job_ids)
        return {
            owner_job_id: _safe_int(value)
            for owner_job_id, value in zip(owner_job_ids, payload, strict=False)
        }

    def clear_job_state(self, owner_job_id: str) -> None:
        self.client.delete(svg_scheduler_anchor_key(self.key_prefix, owner_job_id))
        self.client.hdel(self.job_grants_key, owner_job_id)

    def write_task_heartbeat(self, task_id: str, owner: str, ttl_seconds: int) -> None:
        self.client.set(svg_scheduler_heartbeat_key(self.key_prefix, task_id), owner, ex=max(1, int(ttl_seconds)))

    def task_heartbeat_alive(self, task_id: str) -> bool:
        return bool(self.client.exists(svg_scheduler_heartbeat_key(self.key_prefix, task_id)))

    def delete_task_heartbeat(self, task_id: str) -> None:
        self.client.delete(svg_scheduler_heartbeat_key(self.key_prefix, task_id))

    def clear_svg_budget_leases_for_task(self, task: SvgBatchTask) -> int:
        runner_dir = _read_worker_request_runner_dir(task.worker_request_path)
        if not runner_dir:
            return 0
        label_prefix = f"{Path(runner_dir).name}:svg_batch_{task.batch_index + 1:02d}_turn_"
        leases_key = scheduler_key(self.key_prefix, "svg:budget:leases")
        removed = 0
        for lease_id in [str(item) for item in self.client.zrange(leases_key, 0, -1)]:
            lease_key = scheduler_key(self.key_prefix, f"svg:budget:lease:{lease_id}")
            payload = self.client.hgetall(lease_key) or {}
            if str(payload.get("runner_dir") or "") != runner_dir:
                continue
            if not str(payload.get("label") or "").startswith(label_prefix):
                continue
            self.client.zrem(leases_key, lease_id)
            self.client.delete(lease_key)
            removed += 1
        return removed

    def clear_llm_slots_for_task(self, task: SvgBatchTask, *, stage: str, max_slots: int) -> int:
        runner_dir = _read_worker_request_runner_dir(task.worker_request_path)
        if not runner_dir:
            return 0
        label_prefix = f"svg_batch_{task.batch_index + 1:02d}_turn_"
        removed = 0
        for index in range(1, max(1, int(max_slots)) + 1):
            slot_key = scheduler_key(self.key_prefix, f"llm:slot:{stage}:{index:03d}")
            meta_key = scheduler_key(self.key_prefix, f"llm:slotmeta:{stage}:{index:03d}")
            payload = _load_slotmeta_payload(self.client.get(meta_key))
            if not payload:
                continue
            if str(payload.get("runner_dir") or "") != runner_dir:
                continue
            if not str(payload.get("label") or "").startswith(label_prefix):
                continue
            token = str(payload.get("token") or "")
            if not token or self.client.get(slot_key) == token:
                self.client.delete(slot_key)
            self.client.delete(meta_key)
            removed += 1
        return removed

    def fail_pending_tasks_for_job(self, owner_job_id: str, error: str) -> None:
        for task in self.list_pending_tasks():
            if task.owner_job_id != owner_job_id:
                continue
            self.mark_failed(task.task_id, error)

    def _finalize_task(self, task: SvgBatchTask) -> None:
        self._write_task(task)
        self.client.zrem(self.pending_key, task.task_id)
        self.client.zrem(self.running_key, task.task_id)
        self.delete_task_heartbeat(task.task_id)
        self.client.lpush(self.recent_key, task.task_id)
        self.client.ltrim(self.recent_key, 0, 499)

    def _write_task(self, task: SvgBatchTask) -> None:
        payload = task.to_payload()
        self.client.set(svg_scheduler_task_key(self.key_prefix, task.task_id), json.dumps(payload, ensure_ascii=False))

    def _load_tasks(self, task_ids: list[str]) -> list[SvgBatchTask]:
        tasks: list[SvgBatchTask] = []
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task is not None:
                tasks.append(task)
        tasks.sort(key=lambda item: (item.enqueued_at, item.batch_index, item.task_id))
        return tasks


class SvgScheduler:
    def __init__(
        self,
        *,
        store: RedisSvgSchedulerStore,
        runner_script: Path,
        slot_limit_resolver: Callable[[], int],
        account_pool: RedisAccountPool | None = None,
        poll_seconds: float = 1.0,
        max_workers: int = 32,
    ) -> None:
        self.store = store
        self.runner_script = runner_script
        self.slot_limit_resolver = slot_limit_resolver
        self.account_pool = account_pool
        self.poll_seconds = max(0.2, poll_seconds)
        self.max_workers = max(1, max_workers)
        self.owner_key = svg_scheduler_owner_from_env()
        self.worker_id = f"{self.owner_key}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.heartbeat_seconds = max(10, _env_int("PPT_API_SVG_SCHEDULER_HEARTBEAT_SECONDS", 120))
        self.running_stale_seconds = max(
            self.heartbeat_seconds * 2,
            _env_int("PPT_API_SVG_SCHEDULER_RUNNING_STALE_SECONDS", 30 * 60),
        )
        self._stale_reaped_batches_total = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._futures: dict[Future[dict[str, Any]], tuple[str, AccountLease | None]] = {}
        self._last_snapshot: dict[str, Any] = {
            "enabled": True,
            "running": False,
            "runnable_jobs": 0,
            "pending_batches": 0,
            "running_batches": 0,
            "base_share": 0,
            "remainder_slots": 0,
            "granted_slots_by_job": {},
            "queue_wait_p50": 0.0,
            "queue_wait_p95": 0.0,
            "underutilized_slots": 0,
            "total_slots": 0,
            "account_id_counts": {},
            "account_pool_waiting_batches": 0,
            "owner_key": self.owner_key,
            "heartbeat_seconds": self.heartbeat_seconds,
            "running_stale_seconds": self.running_stale_seconds,
            "stale_reaped_batches": 0,
        }

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="svg-scheduler")
            self._thread = threading.Thread(target=self._run_loop, name="svg-scheduler-loop", daemon=True)
            self._thread.start()
            self._last_snapshot["running"] = True

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
        executor = self._executor
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=False)
        with self._lock:
            self._thread = None
            self._executor = None
            self._futures.clear()
            self._last_snapshot["running"] = False

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._last_snapshot)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("svg scheduler tick failed: %s", exc)
            self._stop_event.wait(self.poll_seconds)

    def _tick(self) -> None:
        self._collect_finished_futures()
        self._refresh_owned_heartbeats()

        pending_tasks = self._owned_pending_tasks()
        running_tasks = self.store.list_running_tasks()
        if self._reap_stale_running_tasks(running_tasks):
            pending_tasks = self._owned_pending_tasks()
            running_tasks = self.store.list_running_tasks()
        total_slots = max(1, int(self.slot_limit_resolver()))
        running_total = len(running_tasks)

        pending_by_job: dict[str, list[SvgBatchTask]] = {}
        for task in pending_tasks:
            if task.requires_anchor and not self.store.anchor_completed(task.owner_job_id):
                continue
            pending_by_job.setdefault(task.owner_job_id, []).append(task)
        for tasks in pending_by_job.values():
            tasks.sort(key=lambda item: (item.enqueued_at, item.batch_index, item.task_id))

        running_by_job: dict[str, list[SvgBatchTask]] = {}
        for task in running_tasks:
            running_by_job.setdefault(task.owner_job_id, []).append(task)

        job_ids = sorted(set(pending_by_job) | set(running_by_job))
        job_requested_workers: dict[str, int] = {}
        job_total_demand: dict[str, int] = {}
        job_oldest_pending_at: dict[str, float] = {}
        for job_id in job_ids:
            pending_for_job = pending_by_job.get(job_id, [])
            running_for_job = running_by_job.get(job_id, [])
            if pending_for_job:
                job_requested_workers[job_id] = max(task.requested_workers for task in pending_for_job + running_for_job)
                job_total_demand[job_id] = len(pending_for_job) + len(running_for_job)
                job_oldest_pending_at[job_id] = pending_for_job[0].enqueued_at

        runnable_job_ids = [job_id for job_id in job_ids if pending_by_job.get(job_id)]
        historical_grants = self.store.get_job_grants(runnable_job_ids)
        decision = compute_scheduler_grants(
            total_slots=total_slots,
            job_requested_workers=job_requested_workers,
            job_total_demand=job_total_demand,
            job_oldest_pending_at=job_oldest_pending_at,
            historical_grants=historical_grants,
        )

        available_slots = max(0, total_slots - running_total)
        queue_waits: list[float] = []
        now = time.time()
        for task in self.store.list_recent_tasks(limit=200) + running_tasks:
            if task.started_at is not None and task.started_at >= task.enqueued_at:
                queue_waits.append(task.started_at - task.enqueued_at)
        queue_wait_p50, queue_wait_p95 = _percentiles(queue_waits)

        launch_candidates = [
            job_id
            for job_id in runnable_job_ids
            if len(running_by_job.get(job_id, [])) < decision.granted_slots_by_job.get(job_id, 0)
        ]
        launch_candidates.sort(
            key=lambda job_id: (
                historical_grants.get(job_id, 0),
                len(running_by_job.get(job_id, [])),
                job_oldest_pending_at.get(job_id, math.inf),
                job_id,
            )
        )

        executor = self._executor
        if executor is None:
            return

        account_pool_waiting_batches = 0
        while available_slots > 0 and launch_candidates:
            progressed = False
            for job_id in list(launch_candidates):
                if available_slots <= 0:
                    break
                target = decision.granted_slots_by_job.get(job_id, 0)
                current_running = len(running_by_job.get(job_id, []))
                pending_for_job = pending_by_job.get(job_id, [])
                if current_running >= target or not pending_for_job:
                    launch_candidates.remove(job_id)
                    continue
                task = pending_for_job[0]
                try:
                    account_ready, account_lease = self._prepare_account_lease(task)
                except Exception as exc:
                    pending_for_job.pop(0)
                    self.store.mark_failed(task.task_id, f"Failed to prepare account lease: {exc}")
                    logger.exception("Failed to prepare account lease for svg task %s: %s", task.task_id, exc)
                    continue
                if not account_ready:
                    account_pool_waiting_batches += len(pending_tasks)
                    launch_candidates.clear()
                    break

                running_task = self.store.mark_running(
                    task.task_id,
                    worker_name="svg-scheduler",
                    account_id=account_lease.account_id if account_lease else None,
                    account_lease_id=account_lease.lease_id if account_lease else None,
                )
                if running_task is None:
                    if account_lease is not None and self.account_pool is not None:
                        self.account_pool.release(account_lease, error="task disappeared before worker launch")
                    continue
                pending_for_job.pop(0)
                self.store.increment_job_grants(task.owner_job_id)
                self.store.write_task_heartbeat(running_task.task_id, self.worker_id, self.heartbeat_seconds)
                try:
                    future = executor.submit(_run_svg_batch_worker, self.runner_script, Path(running_task.worker_request_path))
                except Exception as exc:
                    self.store.delete_task_heartbeat(running_task.task_id)
                    if account_lease is not None and self.account_pool is not None:
                        self.account_pool.release(account_lease, error=f"failed to submit svg worker: {exc}")
                    self.store.mark_failed(running_task.task_id, f"Failed to submit svg worker: {exc}")
                    logger.exception("Failed to submit svg worker for task %s: %s", running_task.task_id, exc)
                    continue
                with self._lock:
                    self._futures[future] = (task.task_id, account_lease)
                running_by_job.setdefault(job_id, []).append(running_task)
                current_running += 1
                available_slots -= 1
                progressed = True
                if current_running >= target or not pending_for_job:
                    if job_id in launch_candidates:
                        launch_candidates.remove(job_id)
            if not progressed:
                break

        current_running = self.store.list_running_tasks()

        with self._lock:
            self._last_snapshot = {
                "enabled": True,
                "running": True,
                "runnable_jobs": decision.runnable_jobs,
                "pending_batches": len(pending_tasks),
                "running_batches": len(current_running),
                "base_share": decision.base_share,
                "remainder_slots": decision.remainder_slots,
                "granted_slots_by_job": decision.granted_slots_by_job,
                "queue_wait_p50": round(queue_wait_p50, 1),
                "queue_wait_p95": round(queue_wait_p95, 1),
                "underutilized_slots": max(0, total_slots - len(current_running)),
                "total_slots": total_slots,
                "account_id_counts": self._account_id_counts(current_running),
                "account_pool_waiting_batches": account_pool_waiting_batches,
                "owner_key": self.owner_key,
                "heartbeat_seconds": self.heartbeat_seconds,
                "running_stale_seconds": self.running_stale_seconds,
                "stale_reaped_batches": self._stale_reaped_batches_total,
            }

    def _collect_finished_futures(self) -> None:
        completed: list[tuple[Future[dict[str, Any]], str, AccountLease | None]] = []
        with self._lock:
            for future, (task_id, account_lease) in list(self._futures.items()):
                if future.done():
                    completed.append((future, task_id, account_lease))
                    del self._futures[future]
        for future, task_id, account_lease in completed:
            account_result = None
            try:
                payload = future.result()
            except Exception as exc:  # pragma: no cover - defensive logging
                error = str(exc)
                if account_lease is not None and self.account_pool is not None:
                    account_result = self.account_pool.release(account_lease, error=error)
                self.store.mark_failed(task_id, error)
                continue
            status = str(payload.get("status") or "")
            error = str(payload.get("error") or "")
            if account_lease is not None and self.account_pool is not None:
                account_result = self.account_pool.release(
                    account_lease,
                    usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else None,
                    error=None if status == SVG_TASK_SUCCEEDED else error,
                )
            if status == SVG_TASK_SUCCEEDED:
                self.store.mark_completed(task_id, session_id=_safe_str(payload.get("session_id")))
            else:
                retry_limit = max(0, _env_int("PPT_API_QWEN_ACCOUNT_POOL_MAX_RETRIES", 2))
                current_task = self.store.get_task(task_id)
                retry_count = current_task.account_retry_count if current_task is not None else 0
                if (
                    account_result is not None
                    and account_result_retryable(account_result)
                    and retry_count < retry_limit
                ):
                    self.store.requeue_task(task_id, error or "svg batch worker failed with retryable account error")
                    logger.warning(
                        "Requeued svg task %s after retryable account error (%s), retry=%s/%s",
                        task_id,
                        account_result,
                        retry_count + 1,
                        retry_limit,
                    )
                else:
                    self.store.mark_failed(task_id, error or "svg batch worker failed")

    def _refresh_owned_heartbeats(self) -> None:
        with self._lock:
            task_ids = [task_id for _future, (task_id, _lease) in self._futures.items()]
        for task_id in task_ids:
            try:
                self.store.write_task_heartbeat(task_id, self.worker_id, self.heartbeat_seconds)
            except Exception as exc:  # pragma: no cover - Redis fault tolerance
                logger.warning("Failed to refresh svg task heartbeat task_id=%s: %s", task_id, exc)

    def _owned_running_task_ids(self) -> set[str]:
        with self._lock:
            return {task_id for _future, (task_id, _lease) in self._futures.items()}

    def _can_launch_task(self, task: SvgBatchTask) -> bool:
        return task.scheduler_owner is None or task.scheduler_owner == self.owner_key

    def _owned_pending_tasks(self) -> list[SvgBatchTask]:
        return [task for task in self.store.list_pending_tasks() if self._can_launch_task(task)]

    def _reap_stale_running_tasks(self, running_tasks: list[SvgBatchTask]) -> int:
        now = time.time()
        owned_task_ids = self._owned_running_task_ids()
        reaped = 0
        for task in running_tasks:
            if task.task_id in owned_task_ids:
                continue
            if self.store.task_heartbeat_alive(task.task_id):
                continue
            started_at = task.started_at or task.enqueued_at or now
            elapsed = now - started_at
            if elapsed < self.running_stale_seconds:
                continue
            error = (
                "Stale centralized SVG scheduler task reaped after "
                f"{elapsed:.0f}s without an active heartbeat"
            )
            self._release_stale_account_lease(task, error)
            removed_llm_slots = self.store.clear_llm_slots_for_task(
                task,
                stage="svg",
                max_slots=max(self.slot_limit_resolver(), _env_int("PPT_API_LLM_SVG_SLOTS", 10)),
            )
            removed_budget_leases = self.store.clear_svg_budget_leases_for_task(task)
            self.store.mark_failed(task.task_id, error)
            reaped += 1
            logger.warning(
                "Reaped stale svg task task_id=%s owner_job_id=%s batch=%s elapsed=%.1fs llm_slots=%s budget_leases=%s",
                task.task_id,
                task.owner_job_id,
                task.batch_index + 1,
                elapsed,
                removed_llm_slots,
                removed_budget_leases,
            )
        if reaped:
            self._stale_reaped_batches_total += reaped
        return reaped

    def _release_stale_account_lease(self, task: SvgBatchTask, error: str) -> None:
        if self.account_pool is None or not task.account_id or not task.account_lease_id:
            return
        try:
            lease = AccountLease(
                lease_id=task.account_lease_id,
                account_id=task.account_id,
                api_key="",
                base_url=None,
                model=None,
                expires_at=time.time(),
            )
            self.account_pool.release(lease, error=error)
        except Exception as exc:  # pragma: no cover - Redis fault tolerance
            logger.warning("Failed to release stale account lease task_id=%s lease_id=%s: %s", task.task_id, task.account_lease_id, exc)

    def _prepare_account_lease(self, task: SvgBatchTask) -> tuple[bool, AccountLease | None]:
        if self.account_pool is None or not self.account_pool.configured:
            return True, None
        startup_reserve_tpm = self._account_pool_svg_startup_reserve_tpm()
        lease = self.account_pool.acquire(
            label=f"{task.owner_job_id}:batch_{task.batch_index + 1}",
            owner_task_id=task.task_id,
            worker_request_path=task.worker_request_path,
            estimated_tokens=startup_reserve_tpm,
            reserved_tpm=startup_reserve_tpm,
            stage="svg",
        )
        if lease is None:
            return False, None
        try:
            _merge_worker_request_credentials(Path(task.worker_request_path), lease)
        except Exception:
            self.account_pool.release(lease, error="failed to write account credentials to worker request")
            raise
        return True, lease

    def _account_pool_svg_startup_reserve_tpm(self) -> int:
        override = _env_int("PPT_API_QWEN_ACCOUNT_POOL_SVG_STARTUP_RESERVE_TPM", 0)
        if override > 0:
            return override
        worker_tpm = _env_int("PPT_API_LLM_DEFAULT_SVG_WORKER_TPM", 125000)
        try:
            observed_raw = self.account_pool.client.get(f"{self.store.key_prefix}:llm:ewma:svg:tpm") if self.account_pool else None
            observed = float(observed_raw) if observed_raw else 0.0
            if observed > 0:
                worker_tpm = max(1, math.ceil(observed))
        except Exception:
            pass
        reserve_seconds = _env_float(
            "PPT_API_QWEN_ACCOUNT_POOL_SVG_STARTUP_RESERVE_SECONDS",
            _env_float("PPT_API_SVG_LIVE_TPM_STARTUP_RESERVE_SECONDS", 15.0),
        )
        return max(1, math.ceil(worker_tpm * (reserve_seconds / 60.0)))

    def _account_id_counts(self, running_tasks: list[SvgBatchTask]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in [*running_tasks, *self.store.list_recent_tasks(limit=500)]:
            if not task.account_id:
                continue
            counts[task.account_id] = counts.get(task.account_id, 0) + 1
        return dict(sorted(counts.items()))


def _run_svg_batch_worker(runner_script: Path, worker_request_path: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(runner_script),
        "--svg-batch-worker",
        str(worker_request_path),
    ]
    timeout_seconds = _svg_batch_worker_timeout_seconds()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)
        stdout, stderr = process.communicate()
        return {
            "status": SVG_TASK_FAILED,
            "error": f"SVG batch worker timed out after {timeout_seconds}s",
            "stdout_tail": (stdout or "")[-4000:],
            "stderr_tail": (stderr or "")[-4000:],
        }
    completed_returncode = process.returncode
    payload = _load_worker_payload(stdout or "", stderr or "")
    if completed_returncode != 0:
        failure_payload = dict(payload)
        failure_payload["status"] = SVG_TASK_FAILED
        failure_payload["error"] = payload.get("error") or (stderr or "").strip() or (stdout or "").strip()
        return failure_payload
    return payload


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        return
    except Exception:
        process.kill()


def _svg_batch_worker_timeout_seconds() -> int:
    default = _env_int("PPT_API_RUNNER_TIMEOUT_SECONDS", 2 * 60 * 60)
    return max(60, _env_int("PPT_API_SVG_BATCH_WORKER_TIMEOUT_SECONDS", default))


def _read_worker_request_runner_dir(worker_request_path: str) -> str | None:
    try:
        payload = json.loads(Path(worker_request_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    runner_dir = str(payload.get("runner_dir") or "").strip()
    return runner_dir or None


def _load_slotmeta_payload(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        payload = json.loads(str(raw))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _merge_worker_request_credentials(worker_request_path: Path, lease: AccountLease) -> None:
    payload = json.loads(worker_request_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"worker request is not an object: {worker_request_path}")
    payload.update(lease.worker_payload())
    worker_request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_worker_payload(stdout: str, stderr: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if text:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
    return {
        "status": SVG_TASK_FAILED,
        "error": (stderr or stdout or "worker returned unreadable payload").strip(),
    }


def _percentiles(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0], ordered[0]
    return statistics.median(ordered), _percentile(ordered, 0.95)


def _percentile(ordered: list[float], p: float) -> float:
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
