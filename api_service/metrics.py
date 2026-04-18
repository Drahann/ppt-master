"""Job metrics collection for ppt-master-api.

Provides a thread-safe singleton that tracks active/completed/failed jobs,
per-job timing, and system resource utilization.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobRecord:
    """One tracked job."""

    job_id: str
    report_id: str
    title: str
    start_time: float
    end_time: float | None = None
    status: str = "running"  # running | succeeded | failed
    error: str | None = None
    slide_count: int = 0
    peak_rss_mb: float = 0.0

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 1)


class JobMetrics:
    """Thread-safe metrics store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self._boot_time = time.time()
        self._total_completed = 0
        self._total_failed = 0

    # ── lifecycle ──

    def start_job(self, job_id: str, report_id: str, title: str) -> None:
        with self._lock:
            self._jobs[job_id] = JobRecord(
                job_id=job_id,
                report_id=report_id,
                title=title,
                start_time=time.time(),
            )

    def finish_job(self, job_id: str, slide_count: int = 0) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec:
                rec.status = "succeeded"
                rec.end_time = time.time()
                rec.slide_count = slide_count
                self._total_completed += 1

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec:
                rec.status = "failed"
                rec.end_time = time.time()
                rec.error = error
                self._total_failed += 1

    # ── queries ──

    def snapshot(self, max_concurrent: int) -> dict[str, Any]:
        """Return a JSON-serialisable metrics snapshot."""
        with self._lock:
            active = [j for j in self._jobs.values() if j.status == "running"]
            recent = sorted(
                (j for j in self._jobs.values() if j.status != "running"),
                key=lambda j: j.end_time or 0,
                reverse=True,
            )[:20]

        cpu_percent, mem_rss_mb, mem_total_mb, mem_percent = _system_stats()

        return {
            "uptime_seconds": round(time.time() - self._boot_time, 0),
            "system": {
                "cpu_percent": cpu_percent,
                "mem_rss_mb": mem_rss_mb,
                "mem_total_mb": mem_total_mb,
                "mem_percent": mem_percent,
                "pid": os.getpid(),
            },
            "jobs": {
                "max_concurrent": max_concurrent,
                "active_count": len(active),
                "slots_available": max(0, max_concurrent - len(active)),
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "active": [_job_to_dict(j) for j in active],
                "recent": [_job_to_dict(j) for j in recent],
            },
        }

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == "running")


# ── module-level singleton ──
metrics = JobMetrics()


def _job_to_dict(j: JobRecord) -> dict[str, Any]:
    return {
        "job_id": j.job_id,
        "report_id": j.report_id,
        "title": j.title[:60],
        "status": j.status,
        "elapsed_seconds": j.elapsed_seconds,
        "slide_count": j.slide_count,
        "error": j.error[:120] if j.error else None,
    }


def _system_stats() -> tuple[float, float, float, float]:
    """Best-effort system resource stats."""
    cpu_percent = 0.0
    mem_rss_mb = 0.0
    mem_total_mb = 0.0
    mem_percent = 0.0
    try:
        import psutil

        proc = psutil.Process(os.getpid())
        cpu_percent = proc.cpu_percent(interval=0.1)
        mem_info = proc.memory_info()
        mem_rss_mb = round(mem_info.rss / 1024 / 1024, 1)
        vmem = psutil.virtual_memory()
        mem_total_mb = round(vmem.total / 1024 / 1024, 0)
        mem_percent = vmem.percent
    except ImportError:
        # psutil not available — fallback to /proc on Linux
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        mem_rss_mb = round(int(line.split()[1]) / 1024, 1)
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total_mb = round(int(line.split()[1]) / 1024, 0)
                    elif line.startswith("MemAvailable:"):
                        avail = int(line.split()[1]) / 1024
                        if mem_total_mb:
                            mem_percent = round((1 - avail / mem_total_mb) * 100, 1)
        except Exception:
            pass
    except Exception:
        pass
    return cpu_percent, mem_rss_mb, mem_total_mb, mem_percent
