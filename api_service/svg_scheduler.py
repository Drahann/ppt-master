from __future__ import annotations

import json
import logging
import math
import os
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


logger = logging.getLogger(__name__)

SVG_SCHEDULER_PENDING_KEY_SUFFIX = "svg_scheduler:pending"
SVG_SCHEDULER_RUNNING_KEY_SUFFIX = "svg_scheduler:running"
SVG_SCHEDULER_RECENT_KEY_SUFFIX = "svg_scheduler:recent"
SVG_SCHEDULER_JOB_GRANTS_KEY_SUFFIX = "svg_scheduler:job_grants"
SVG_SCHEDULER_TASK_KEY_PREFIX = "svg_scheduler:task:"
SVG_SCHEDULER_ANCHOR_KEY_PREFIX = "svg_scheduler:anchor_done:"

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


def scheduler_key(key_prefix: str, suffix: str) -> str:
    normalized = (key_prefix or "ppt").strip().strip(":") or "ppt"
    return f"{normalized}:{suffix}"


def svg_scheduler_task_key(key_prefix: str, task_id: str) -> str:
    return scheduler_key(key_prefix, f"{SVG_SCHEDULER_TASK_KEY_PREFIX}{task_id}")


def svg_scheduler_anchor_key(key_prefix: str, owner_job_id: str) -> str:
    return scheduler_key(key_prefix, f"{SVG_SCHEDULER_ANCHOR_KEY_PREFIX}{owner_job_id}")


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
            job_oldest_pending_at.get(job_id, math.inf),
            historical_grants.get(job_id, 0),
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

    def mark_running(self, task_id: str, *, worker_name: str | None = None) -> SvgBatchTask | None:
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

    def fail_pending_tasks_for_job(self, owner_job_id: str, error: str) -> None:
        for task in self.list_pending_tasks():
            if task.owner_job_id != owner_job_id:
                continue
            self.mark_failed(task.task_id, error)

    def _finalize_task(self, task: SvgBatchTask) -> None:
        self._write_task(task)
        self.client.zrem(self.pending_key, task.task_id)
        self.client.zrem(self.running_key, task.task_id)
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
        poll_seconds: float = 1.0,
        max_workers: int = 32,
    ) -> None:
        self.store = store
        self.runner_script = runner_script
        self.slot_limit_resolver = slot_limit_resolver
        self.poll_seconds = max(0.2, poll_seconds)
        self.max_workers = max(1, max_workers)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._futures: dict[Future[dict[str, Any]], str] = {}
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

        pending_tasks = self.store.list_pending_tasks()
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
                job_oldest_pending_at.get(job_id, math.inf),
                historical_grants.get(job_id, 0),
                job_id,
            )
        )

        executor = self._executor
        if executor is None:
            return

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
                task = pending_for_job.pop(0)
                running_task = self.store.mark_running(task.task_id, worker_name="svg-scheduler")
                if running_task is None:
                    continue
                self.store.increment_job_grants(task.owner_job_id)
                future = executor.submit(_run_svg_batch_worker, self.runner_script, Path(running_task.worker_request_path))
                with self._lock:
                    self._futures[future] = task.task_id
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
            }

    def _collect_finished_futures(self) -> None:
        completed: list[tuple[Future[dict[str, Any]], str]] = []
        with self._lock:
            for future, task_id in list(self._futures.items()):
                if future.done():
                    completed.append((future, task_id))
                    del self._futures[future]
        for future, task_id in completed:
            try:
                payload = future.result()
            except Exception as exc:  # pragma: no cover - defensive logging
                self.store.mark_failed(task_id, str(exc))
                continue
            status = str(payload.get("status") or "")
            if status == SVG_TASK_SUCCEEDED:
                self.store.mark_completed(task_id, session_id=_safe_str(payload.get("session_id")))
            else:
                self.store.mark_failed(task_id, str(payload.get("error") or "svg batch worker failed"))


def _run_svg_batch_worker(runner_script: Path, worker_request_path: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(runner_script),
        "--svg-batch-worker",
        str(worker_request_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    payload = _load_worker_payload(completed.stdout, completed.stderr)
    if completed.returncode != 0:
        return {
            "status": SVG_TASK_FAILED,
            "error": payload.get("error") or completed.stderr.strip() or completed.stdout.strip(),
        }
    return payload


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
