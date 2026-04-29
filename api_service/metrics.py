from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobRecord:
    job_id: str
    report_id: str
    title: str
    start_time: float
    end_time: float | None = None
    status: str = "running"
    error: str | None = None
    slide_count: int = 0
    current_stage: str = "accepted"
    stage_started_at: float | None = None
    stage_durations: dict[str, float] = field(default_factory=dict)
    queue_wait_seconds: float = 0.0
    response_mode: str = "async"
    callback_mode: str = "auto"
    worker_name: str | None = None
    account_id: str | None = None
    requested_slots: int = 0
    last_event: str | None = None

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 1)

    @property
    def current_stage_elapsed_seconds(self) -> float:
        if self.stage_started_at is None:
            return 0.0
        end = self.end_time or time.time()
        return round(max(0.0, end - self.stage_started_at), 1)


class JobMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self._boot_time = time.time()
        self._total_completed = 0
        self._total_failed = 0

    def start_job(
        self,
        job_id: str,
        report_id: str,
        title: str,
        *,
        queue_wait_seconds: float = 0.0,
        response_mode: str = "async",
        callback_mode: str = "auto",
        worker_name: str | None = None,
        account_id: str | None = None,
        requested_slots: int = 0,
    ) -> None:
        with self._lock:
            self._jobs[job_id] = JobRecord(
                job_id=job_id,
                report_id=report_id,
                title=title,
                start_time=time.time(),
                current_stage="started",
                stage_started_at=time.time(),
                queue_wait_seconds=round(max(0.0, queue_wait_seconds), 1),
                response_mode=response_mode,
                callback_mode=callback_mode,
                worker_name=worker_name,
                account_id=account_id,
                requested_slots=requested_slots,
                last_event="job_started",
            )

    def finish_job(self, job_id: str, slide_count: int = 0) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec:
                _finalize_stage_duration(rec)
                rec.status = "succeeded"
                rec.end_time = time.time()
                rec.slide_count = slide_count
                rec.current_stage = "succeeded"
                rec.last_event = "job_succeeded"
                self._total_completed += 1

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec:
                _finalize_stage_duration(rec)
                rec.status = "failed"
                rec.end_time = time.time()
                rec.error = error
                rec.current_stage = "failed"
                rec.last_event = error[:200]
                self._total_failed += 1

    def update_job_stage(self, job_id: str, stage: str, *, event: str | None = None) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                return
            if rec.current_stage != stage:
                _finalize_stage_duration(rec)
                rec.current_stage = stage
                rec.stage_started_at = time.time()
            rec.last_event = event or stage

    def snapshot(self, max_concurrent: int) -> dict[str, Any]:
        with self._lock:
            active = [j for j in self._jobs.values() if j.status == "running"]
            recent = sorted((j for j in self._jobs.values() if j.status != "running"), key=lambda j: j.end_time or 0, reverse=True)[:20]
            stage_counts: dict[str, int] = {}
            for job in active:
                stage_counts[job.current_stage] = stage_counts.get(job.current_stage, 0) + 1
        cpu_percent, mem_rss_mb, mem_total_mb, mem_percent, child_count = _system_stats()
        return {
            "uptime_seconds": round(time.time() - self._boot_time, 0),
            "system": {
                "cpu_percent": cpu_percent,
                "mem_rss_mb": mem_rss_mb,
                "mem_total_mb": mem_total_mb,
                "mem_percent": mem_percent,
                "child_processes": child_count,
                "pid": os.getpid(),
            },
            "jobs": {
                "max_concurrent": max_concurrent,
                "active_count": len(active),
                "slots_available": max(0, max_concurrent - len(active)),
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "stage_counts": stage_counts,
                "active": [_job_to_dict(j) for j in active],
                "recent": [_job_to_dict(j) for j in recent],
            },
        }


metrics = JobMetrics()


def _job_to_dict(j: JobRecord) -> dict[str, Any]:
    return {
        "job_id": j.job_id,
        "report_id": j.report_id,
        "title": j.title[:80],
        "status": j.status,
        "current_stage": j.current_stage,
        "current_stage_elapsed_seconds": j.current_stage_elapsed_seconds,
        "elapsed_seconds": j.elapsed_seconds,
        "slide_count": j.slide_count,
        "queue_wait_seconds": j.queue_wait_seconds,
        "response_mode": j.response_mode,
        "callback_mode": j.callback_mode,
        "worker_name": j.worker_name,
        "account_id": j.account_id,
        "requested_slots": j.requested_slots,
        "last_event": j.last_event[:160] if j.last_event else None,
        "stage_durations": {key: round(value, 1) for key, value in sorted(j.stage_durations.items())},
        "error": j.error[:160] if j.error else None,
    }


def _finalize_stage_duration(record: JobRecord) -> None:
    if record.stage_started_at is None or not record.current_stage:
        return
    elapsed = max(0.0, time.time() - record.stage_started_at)
    record.stage_durations[record.current_stage] = round(record.stage_durations.get(record.current_stage, 0.0) + elapsed, 1)


def _system_stats() -> tuple[float, float, float, float, int]:
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        proc = psutil.Process(os.getpid())
        tree_rss = proc.memory_info().rss
        children = proc.children(recursive=True)
        for child in children:
            try:
                tree_rss += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        vmem = psutil.virtual_memory()
        return cpu_percent, round(tree_rss / 1024 / 1024, 1), round(vmem.total / 1024 / 1024, 0), vmem.percent, len(children)
    except Exception:
        return 0.0, 0.0, 0.0, 0.0, 0

