from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from .config import load_settings
from .job_store import RedisJobStore, RedisJobStoreError
from .markdown_assets import process_markdown_images
from .metrics import metrics
from .models import CallbackResult as CallbackResultModel
from .models import GeneratePptRequest, GeneratePptResponse, NormalizedRequest, ReportRequest, ReportResponse
from .runner import derive_title, execute_runner
from .storage import build_result_zip, notify_report_server, sanitize_title, upload_to_cos


logger = logging.getLogger(__name__)
settings = load_settings()
settings.project_base_dir.mkdir(parents=True, exist_ok=True)
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.llm_slot_dir.mkdir(parents=True, exist_ok=True)
settings.metrics_export_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="ppt-master-api", version="1.0.0")
job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
execution_semaphore = threading.BoundedSemaphore(settings.max_concurrent_jobs)
worker_stop_event = threading.Event()
worker_threads: list[threading.Thread] = []
metrics_export_stop_event = threading.Event()
metrics_export_thread: threading.Thread | None = None
job_store_error: str | None = None
try:
    job_store = RedisJobStore.from_settings(settings)
except RedisJobStoreError as exc:
    job_store = None
    job_store_error = str(exc)


_DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")


def _llm_slot_snapshot() -> dict[str, dict[str, int | str]]:
    svg_effective_limit = _effective_svg_limit()
    limits = {
        "spec": settings.llm_spec_slots,
        "svg": svg_effective_limit,
        "notes": settings.llm_notes_slots,
        "postprocess": settings.postprocess_slots,
    }
    snapshot: dict[str, dict[str, int | str]] = {}
    for stage, limit in limits.items():
        redis_active = _redis_slot_active(stage, limit)
        if redis_active is not None:
            active, waiting = redis_active
            snapshot[stage] = {
                "active": active,
                "waiting": waiting,
                "limit": limit,
                "available": max(0, limit - active),
                "backend": "redis",
            }
        else:
            stage_dir = settings.llm_slot_dir / stage
            active = len(list(stage_dir.glob("*.slot"))) if stage_dir.exists() else 0
            snapshot[stage] = {
                "active": active,
                "waiting": 0,
                "limit": limit,
                "available": max(0, limit - active),
                "backend": "file",
                "dir": str(stage_dir),
            }
    return snapshot


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "cosEnabled": settings.cos_enabled,
        "projectBaseDir": str(settings.project_base_dir),
        "jobsDir": str(settings.jobs_dir),
        "maxConcurrentJobs": settings.max_concurrent_jobs,
        "batchPartition": settings.batch_partition,
        "llmSlots": {
            "spec": settings.llm_spec_slots,
            "svg": settings.llm_svg_slots,
            "notes": settings.llm_notes_slots,
            "postprocess": settings.postprocess_slots,
        },
        "redis": {
            "configured": bool(settings.redis_url),
            "available": _redis_available(),
            "error": job_store_error,
            "keyPrefix": settings.redis_key_prefix,
        },
        "asyncWorkers": len(worker_threads),
        "metricsExport": {
            "enabled": settings.metrics_export_enabled,
            "dir": str(settings.metrics_export_dir),
            "intervalSeconds": settings.metrics_export_interval_seconds,
            "retentionFiles": settings.metrics_export_retention_files,
            "archiveIdleIntervals": settings.metrics_export_archive_idle_intervals,
        },
    }


@app.get("/metrics")
def get_metrics() -> dict:
    """Real-time performance metrics JSON."""
    return _build_metrics_payload()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Live performance dashboard."""
    return _DASHBOARD_HTML


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request, exc: RequestValidationError) -> JSONResponse:
    missing_fields = ["/".join(str(item) for item in err.get("loc", [])[1:]) for err in exc.errors()]
    message = "Invalid request body"
    if missing_fields:
        message = f"Missing or invalid field(s): {', '.join(missing_fields)}"
    return JSONResponse(status_code=400, content={"error": message})


@app.on_event("startup")
def start_async_workers() -> None:
    if job_store is not None:
        if worker_threads:
            return
        try:
            job_store.ping()
        except Exception as exc:
            global job_store_error
            job_store_error = str(exc)

        for index in range(settings.async_worker_count):
            thread = threading.Thread(
                target=_async_worker_loop,
                name=f"ppt-async-worker-{index + 1}",
                daemon=True,
            )
            thread.start()
            worker_threads.append(thread)
            logger.info("Started async worker thread %s", thread.name)
    _start_metrics_exporter()
    _snapshot_metrics_to_disk("startup")


@app.on_event("shutdown")
def stop_async_workers() -> None:
    worker_stop_event.set()
    for thread in worker_threads:
        thread.join(timeout=2)
        logger.info("Stopped async worker thread %s", thread.name)
    _stop_metrics_exporter()
    _snapshot_metrics_to_disk("shutdown")


@app.post("/api/report-to-ppt", response_model=ReportResponse)
async def report_to_ppt(request: ReportRequest):
    normalized = _normalize_report_to_ppt_request(request)
    if normalized.response_mode == "async":
        return _enqueue_async_request(normalized, report_style=True)
    async with job_semaphore:
        try:
            payload = await asyncio.to_thread(_process_request, normalized)
            return ReportResponse(**payload)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc), "reportId": request.reportId})


@app.post("/api/generate-ppt", response_model=GeneratePptResponse)
async def generate_ppt(request: GeneratePptRequest):
    normalized = _normalize_generate_ppt_request(request)
    if normalized.response_mode == "async":
        return _enqueue_async_request(normalized, report_style=False)
    async with job_semaphore:
        try:
            payload = await asyncio.to_thread(_process_request, normalized)
            return GeneratePptResponse(
                success=payload["success"],
                report_id=payload["reportId"],
                pptUrl=payload["pptUrl"],
                slideCount=payload["slideCount"],
                title=payload["title"],
                callback=payload["callback"],
            )
        except Exception as exc:
            return JSONResponse(status_code=500, content={"success": False, "error": str(exc), "report_id": request.report_id})


@app.get("/api/jobs/{job_id}", response_model=None)
def get_job(job_id: str) -> JSONResponse | dict[str, object]:
    if job_store is None:
        return JSONResponse(status_code=503, content={"error": "Redis job store is not configured", "detail": job_store_error})
    record = job_store.get_job(job_id)
    if record is None:
        return JSONResponse(status_code=404, content={"error": "job not found", "job_id": job_id})
    return record


@app.get("/api/jobs/{job_id}/artifacts", response_model=None)
def get_job_artifacts(job_id: str) -> JSONResponse | dict[str, object]:
    if job_store is None:
        return JSONResponse(status_code=503, content={"error": "Redis job store is not configured", "detail": job_store_error})
    record = job_store.get_job(job_id)
    if record is None:
        return JSONResponse(status_code=404, content={"error": "job not found", "job_id": job_id})
    return {"job_id": job_id, "status": record.get("status"), "result": record.get("result")}


@app.post("/api/jobs/{job_id}/cancel", response_model=None)
def cancel_job(job_id: str) -> JSONResponse | dict[str, object]:
    if job_store is None:
        return JSONResponse(status_code=503, content={"error": "Redis job store is not configured", "detail": job_store_error})
    record = job_store.cancel(job_id)
    if record is None:
        return JSONResponse(status_code=404, content={"error": "job not found", "job_id": job_id})
    return record


def _process_request(request: NormalizedRequest, job_id: str | None = None) -> dict[str, object]:
    title = request.title or derive_title(request.content, request.report_id)
    job_dir = settings.jobs_dir / job_id if job_id else _build_job_dir(request.report_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    metric_job_id = job_id or job_dir.name
    queue_wait_seconds = _job_queue_wait_seconds(job_id)

    metrics.start_job(
        metric_job_id,
        request.report_id,
        title or "untitled",
        queue_wait_seconds=queue_wait_seconds,
        response_mode=request.response_mode,
        callback_mode=request.callback_mode,
        worker_name=threading.current_thread().name,
    )
    logger.info(
        "Starting PPT job job_id=%s report_id=%s mode=%s callback_mode=%s queue_wait=%.1fs batch_mode=%s batch_size=%s parallel_batch_workers=%s batch_partition=%s",
        metric_job_id,
        request.report_id,
        request.response_mode,
        request.callback_mode,
        queue_wait_seconds,
        request.batch_mode or settings.batch_mode,
        request.batch_size or settings.batch_size,
        request.parallel_batch_workers or settings.parallel_batch_workers,
        request.batch_partition or settings.batch_partition,
    )
    try:
        with execution_semaphore:
            _update_job_stage(metric_job_id, job_id, "preparing", event="processing_markdown")
            processed_markdown, image_warnings = process_markdown_images(request.content, job_dir)
            source_md_path = job_dir / "source.md"
            source_md_path.write_text(processed_markdown, encoding="utf-8")
            if image_warnings:
                (job_dir / "image_warnings.txt").write_text("\n".join(image_warnings) + "\n", encoding="utf-8")
                logger.warning("Job %s produced %s markdown image warnings", metric_job_id, len(image_warnings))

            _update_job_stage(metric_job_id, job_id, "runner", event="runner_started")
            runner_result = execute_runner(
                source_md_path=source_md_path,
                report_id=request.report_id,
                title=title,
                settings=settings,
                working_dir=job_dir,
                batch_mode=(request.batch_mode or settings.batch_mode),
                batch_size=(request.batch_size or settings.batch_size),
                parallel_batch_workers=(request.parallel_batch_workers or settings.parallel_batch_workers),
                batch_partition=(request.batch_partition or settings.batch_partition),
                spec_model=request.spec_model,
                notes_model=request.notes_model,
            )

            notes_path = runner_result.project_path / "notes" / "total.md"
            zip_buffer = build_result_zip(runner_result.native_pptx_path, notes_path, runner_result.title)

            safe_title = sanitize_title(runner_result.title)
            cos_path = f"ppt/{request.report_id}/{safe_title}.zip"
            _update_job_stage(metric_job_id, job_id, "uploading", event=f"upload_to_cos:{cos_path}")
            ppt_url = upload_to_cos(zip_buffer, cos_path, settings)

            if request.callback_mode == "auto":
                _update_job_stage(metric_job_id, job_id, "callback", event="report_callback")
                callback_result = notify_report_server(
                    report_id=request.report_id,
                    file_url=request.file_url,
                    word_url=request.word_url,
                    ppt_url=ppt_url,
                    callback_url=(request.callback_url or settings.report_callback_url),
                )
            else:
                callback_result = CallbackResultModel(success=True, error=None)

            if not settings.keep_job_files:
                shutil.rmtree(job_dir, ignore_errors=True)

            metrics.finish_job(metric_job_id, runner_result.slide_count)
            logger.info(
                "Finished PPT job job_id=%s report_id=%s slide_count=%s ppt_url=%s callback_success=%s",
                metric_job_id,
                request.report_id,
                runner_result.slide_count,
                ppt_url,
                callback_result.success,
            )
            return {
                "success": True,
                "reportId": request.report_id,
                "pptUrl": ppt_url,
                "slideCount": runner_result.slide_count,
                "title": runner_result.title,
                "callback": CallbackResultModel(success=callback_result.success, error=callback_result.error).model_dump(),
            }
    except Exception as exc:
        metrics.fail_job(metric_job_id, str(exc))
        logger.exception("PPT job failed job_id=%s report_id=%s error=%s", metric_job_id, request.report_id, exc)
        raise


def _enqueue_async_request(request: NormalizedRequest, *, report_style: bool) -> JSONResponse | ReportResponse | GeneratePptResponse:
    if job_store is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "Redis job store is not configured", "detail": job_store_error})
    try:
        title = request.title or derive_title(request.content, request.report_id)
        job_id = job_store.create_job(request, title=title)
        logger.info(
            "Enqueued async PPT job job_id=%s report_id=%s callback_mode=%s batch_mode=%s batch_partition=%s",
            job_id,
            request.report_id,
            request.callback_mode,
            request.batch_mode or settings.batch_mode,
            request.batch_partition or settings.batch_partition,
        )
        _snapshot_metrics_to_disk("enqueue")
    except Exception as exc:
        return JSONResponse(status_code=503, content={"success": False, "error": str(exc)})

    payload = {
        "success": True,
        "pptUrl": None,
        "slideCount": 0,
        "title": title,
        "callback": None,
        "status": "queued",
        "job_id": job_id,
        "pollingUrl": f"/api/jobs/{job_id}",
    }
    if report_style:
        return ReportResponse(reportId=request.report_id, **payload)
    return GeneratePptResponse(report_id=request.report_id, **payload)


def _async_worker_loop() -> None:
    assert job_store is not None
    while not worker_stop_event.is_set():
        try:
            job_id = job_store.dequeue(timeout_seconds=2)
        except Exception as exc:
            global job_store_error
            job_store_error = str(exc)
            time.sleep(2)
            continue
        if not job_id:
            continue
        logger.info("Worker %s dequeued job_id=%s", threading.current_thread().name, job_id)
        _run_async_job(job_id)


def _run_async_job(job_id: str) -> None:
    assert job_store is not None
    record = job_store.mark_running(job_id, stage="running")
    if record is None or record.get("status") == "cancelled":
        return
    logger.info("Worker %s started job_id=%s report_id=%s", threading.current_thread().name, job_id, record.get("report_id"))
    try:
        request = NormalizedRequest(**record["request"])
        payload = _process_request(request, job_id=job_id)
        job_store.complete(job_id, payload)
        logger.info("Worker %s completed job_id=%s", threading.current_thread().name, job_id)
        _snapshot_metrics_to_disk("job_complete")
    except Exception as exc:
        job_store.fail(job_id, str(exc))
        logger.exception("Worker %s failed job_id=%s error=%s", threading.current_thread().name, job_id, exc)
        _snapshot_metrics_to_disk("job_fail")


def _update_job_stage(metric_job_id: str, queue_job_id: str | None, stage: str, *, event: str | None = None) -> None:
    metrics.update_job_stage(metric_job_id, stage, event=event)
    if queue_job_id and job_store is not None:
        try:
            job_store.update_stage(queue_job_id, stage)
        except Exception:
            pass
    _snapshot_metrics_to_disk(f"stage_{stage}")


def _redis_available() -> bool:
    if job_store is None:
        return False
    try:
        return job_store.ping()
    except Exception:
        return False


def _redis_job_snapshot() -> dict[str, object]:
    if job_store is None:
        return {"enabled": False, "error": job_store_error}
    try:
        return job_store.snapshot()
    except Exception as exc:
        return {"enabled": True, "error": str(exc)}


def _llm_budget_snapshot() -> dict[str, object]:
    try:
        configured_budget_tpm = int((os.getenv("PPT_API_LLM_BUDGET_TPM") or "0").strip() or "0")
    except ValueError:
        configured_budget_tpm = 0
    try:
        target_utilization = float((os.getenv("PPT_API_LLM_TARGET_UTILIZATION") or "0.75").strip() or "0.75")
    except ValueError:
        target_utilization = 0.75
    if job_store is None:
        return {
            "configured_budget_tpm": configured_budget_tpm,
            "target_utilization": target_utilization,
            "observed_svg_worker_tpm": None,
            "dynamic_svg_limit": settings.llm_svg_slots,
            "backend": "file",
        }
    try:
        observed_svg_worker_tpm_raw = job_store.client.get(f"{settings.redis_key_prefix}:llm:ewma:svg:tpm")
        observed_svg_worker_tpm = float(observed_svg_worker_tpm_raw) if observed_svg_worker_tpm_raw else None
    except Exception:
        observed_svg_worker_tpm = None
    try:
        observed_svg_tokens_raw = job_store.client.get(f"{settings.redis_key_prefix}:llm:ewma:svg:tokens")
        observed_svg_tokens = float(observed_svg_tokens_raw) if observed_svg_tokens_raw else None
    except Exception:
        observed_svg_tokens = None
    try:
        pacing_window_seconds = int((os.getenv("PPT_API_LLM_PACING_WINDOW_SECONDS") or "60").strip() or "60")
    except ValueError:
        pacing_window_seconds = 60
    dynamic_svg_limit = _effective_svg_limit(configured_budget_tpm, target_utilization, observed_svg_worker_tpm)
    try:
        live_window_seconds = int((os.getenv("PPT_API_LIVE_TPM_WINDOW_SECONDS") or str(pacing_window_seconds)).strip() or str(pacing_window_seconds))
    except ValueError:
        live_window_seconds = pacing_window_seconds
    live_svg_snapshot = _redis_live_stage_snapshot("svg", live_window_seconds)
    return {
        "configured_budget_tpm": configured_budget_tpm,
        "target_utilization": target_utilization,
        "observed_svg_worker_tpm": round(observed_svg_worker_tpm, 1) if observed_svg_worker_tpm else None,
        "observed_svg_turn_tokens": round(observed_svg_tokens, 1) if observed_svg_tokens else None,
        "dynamic_svg_limit": dynamic_svg_limit,
        "configured_svg_limit": settings.llm_svg_slots,
        "tpm_pacing_enabled": (os.getenv("PPT_API_LLM_TPM_PACING_ENABLED", "1").strip().lower() not in {"0", "false", "no"}),
        "pacing_window_seconds": pacing_window_seconds,
        "live_window_seconds": live_window_seconds,
        "live_svg_tpm_60s": (live_svg_snapshot or {}).get("tokens"),
        "live_svg_events_60s": (live_svg_snapshot or {}).get("events"),
        "backend": "redis",
    }


def _redis_live_stage_snapshot(stage: str, window_seconds: int) -> dict[str, object] | None:
    if job_store is None:
        return None
    key = f"{settings.redis_key_prefix}:llm:live:{stage}:tokens"
    now = time.time()
    cutoff = now - window_seconds
    try:
        job_store.client.zremrangebyscore(key, "-inf", f"{cutoff:.6f}")
        members = job_store.client.zrange(key, 0, -1)
        total = 0
        for member in members:
            token_text = str(member).split("|", 1)[0]
            try:
                total += int(token_text)
            except ValueError:
                continue
        return {
            "tokens": max(0, total),
            "events": len(members),
            "window_seconds": window_seconds,
        }
    except Exception:
        return None


def _redis_svg_budget_snapshot() -> dict[str, object]:
    if job_store is None:
        return {"enabled": False, "backend": "file"}
    prefix = settings.redis_key_prefix
    now = time.time()
    leases_key = f"{prefix}:svg:budget:leases"
    active_leases: list[dict[str, object]] = []
    completion_keys: set[str] = set()
    active_reserved_tpm = 0
    completion_peak_tokens = 0
    completion_peak_bucket = None
    try:
        lease_ids = [str(item) for item in job_store.client.zrangebyscore(leases_key, now, "+inf")]
        for lease_id in lease_ids[:100]:
            payload = job_store.client.hgetall(f"{prefix}:svg:budget:lease:{lease_id}")
            if not payload:
                continue
            estimated_worker_tpm = int(float(payload.get("estimated_worker_tpm") or 0))
            estimated_tokens = int(float(payload.get("estimated_tokens") or 0))
            active_reserved_tpm += estimated_worker_tpm
            completion_key = str(payload.get("completion_key") or "")
            if completion_key:
                completion_keys.add(completion_key)
            active_leases.append(
                {
                    "lease_id": lease_id,
                    "label": payload.get("label"),
                    "estimated_worker_tpm": estimated_worker_tpm,
                    "estimated_tokens": estimated_tokens,
                    "estimated_duration_seconds": int(float(payload.get("estimated_duration_seconds") or 0)),
                    "live_window_tpm_after": int(float(payload.get("live_window_tpm_after") or 0)),
                    "live_window_tpm_before": int(float(payload.get("live_window_tpm_before") or 0)),
                    "startup_reserve_tpm": int(float(payload.get("startup_reserve_tpm") or 0)),
                    "admission_mode": payload.get("admission_mode"),
                    "expires_at": float(payload.get("expires_at") or 0),
                    "completion_bucket_epoch": payload.get("completion_bucket_epoch"),
                }
            )
        for key in completion_keys:
            try:
                value = int(float(job_store.client.get(key) or 0))
            except Exception:
                value = 0
            if value > completion_peak_tokens:
                completion_peak_tokens = value
                completion_peak_bucket = str(key).split(":")[-1]
        denied = int(job_store.client.get(f"{prefix}:svg:budget:denied_starts") or 0)
        granted = int(job_store.client.get(f"{prefix}:svg:budget:granted_starts") or 0)
        return {
            "enabled": True,
            "backend": "redis",
            "active_leases": len(active_leases),
            "active_reserved_tpm": active_reserved_tpm,
            "active_leases_sample": active_leases[:20],
            "completion_bucket_peak_tokens": completion_peak_tokens,
            "completion_bucket_peak_epoch": completion_peak_bucket,
            "granted_starts": granted,
            "denied_starts": denied,
        }
    except Exception as exc:
        return {"enabled": True, "backend": "redis", "error": str(exc)}


def _redis_slot_active(stage: str, limit: int) -> tuple[int, int] | None:
    if job_store is None:
        return None
    try:
        prefix = settings.redis_key_prefix
        active = 0
        for index in range(1, limit + 1):
            if job_store.client.exists(f"{prefix}:llm:slot:{stage}:{index:03d}"):
                active += 1
        waiting_raw = job_store.client.get(f"{prefix}:llm:waiting:{stage}") or "0"
        return active, max(0, int(waiting_raw))
    except Exception:
        return None


def _job_queue_wait_seconds(job_id: str | None) -> float:
    if not job_id or job_store is None:
        return 0.0
    try:
        record = job_store.get_job(job_id)
        if not record:
            return 0.0
        created_at = float(record.get("created_at") or 0)
        started_at = time.time()
        if created_at <= 0:
            return 0.0
        return round(max(0.0, started_at - created_at), 1)
    except Exception:
        return 0.0


def _build_metrics_payload() -> dict:
    payload = metrics.snapshot(settings.max_concurrent_jobs)
    payload["llmSlots"] = _llm_slot_snapshot()
    payload["redisJobs"] = _redis_job_snapshot()
    payload["llmBudget"] = _llm_budget_snapshot()
    payload["svgBudget"] = _redis_svg_budget_snapshot()
    payload["asyncWorkers"] = {
        "configured": settings.async_worker_count,
        "running": len(worker_threads),
        "stopped": worker_stop_event.is_set(),
    }
    payload["captured_at"] = datetime.now().isoformat(timespec="seconds")
    return payload


def _start_metrics_exporter() -> None:
    global metrics_export_thread
    if not settings.metrics_export_enabled:
        return
    if metrics_export_thread is not None and metrics_export_thread.is_alive():
        return
    metrics_export_stop_event.clear()
    metrics_export_thread = threading.Thread(
        target=_metrics_export_loop,
        name="ppt-metrics-exporter",
        daemon=True,
    )
    metrics_export_thread.start()
    logger.info("Started metrics exporter thread %s", metrics_export_thread.name)


def _stop_metrics_exporter() -> None:
    global metrics_export_thread
    metrics_export_stop_event.set()
    if metrics_export_thread is not None:
        metrics_export_thread.join(timeout=2)
        logger.info("Stopped metrics exporter thread %s", metrics_export_thread.name)
        metrics_export_thread = None


def _metrics_export_loop() -> None:
    while not metrics_export_stop_event.is_set():
        _snapshot_metrics_to_disk("interval")
        metrics_export_stop_event.wait(settings.metrics_export_interval_seconds)


def _snapshot_metrics_to_disk(reason: str) -> None:
    if not settings.metrics_export_enabled:
        return
    try:
        root = settings.metrics_export_dir
        root.mkdir(parents=True, exist_ok=True)
        day_dir = root / datetime.now().strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        payload = _build_metrics_payload()
        payload["snapshot_reason"] = reason
        payload["export_dir"] = str(root)

        timestamp = datetime.now().strftime("%H%M%S_%f")
        archive_snapshot = not (
            reason == "interval"
            and not settings.metrics_export_archive_idle_intervals
            and _metrics_payload_is_idle(payload)
        )
        snapshot_path = day_dir / f"metrics_{timestamp}_{_safe_filename(reason)}.json"
        latest_path = root / "latest.json"

        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if archive_snapshot:
            snapshot_path.write_text(text, encoding="utf-8")
        latest_path.write_text(text, encoding="utf-8")
        if archive_snapshot:
            _prune_metrics_exports(root)
    except Exception as exc:
        logger.warning("Failed to export metrics snapshot: %s", exc)


def _metrics_payload_is_idle(payload: dict) -> bool:
    jobs = payload.get("jobs") or {}
    redis_jobs = payload.get("redisJobs") or {}
    slots = payload.get("llmSlots") or {}
    if jobs.get("active_count", 0):
        return False
    if redis_jobs.get("pending", 0) or redis_jobs.get("running", 0):
        return False
    for stage_payload in slots.values():
        if isinstance(stage_payload, dict) and (stage_payload.get("active", 0) or stage_payload.get("waiting", 0)):
            return False
    return True


def _prune_metrics_exports(root: Path) -> None:
    files = sorted(
        (path for path in root.rglob("metrics_*.json") if path.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for extra in files[settings.metrics_export_retention_files :]:
        try:
            extra.unlink()
        except OSError:
            pass


def _safe_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value.strip())
    return cleaned[:40] or "snapshot"


def _effective_svg_limit(
    configured_budget_tpm: int | None = None,
    target_utilization: float | None = None,
    observed_svg_worker_tpm: float | None = None,
) -> int:
    static_limit = settings.llm_svg_slots
    hard_max_raw = (os.getenv("PPT_API_LLM_HARD_MAX_SVG_CONCURRENCY") or "").strip()
    hard_max = static_limit
    if hard_max_raw:
        try:
            hard_max = max(1, int(hard_max_raw))
        except ValueError:
            hard_max = static_limit
    min_limit_raw = (os.getenv("PPT_API_LLM_MIN_SVG_CONCURRENCY") or "").strip()
    min_limit = 1
    if min_limit_raw:
        try:
            min_limit = max(1, int(min_limit_raw))
        except ValueError:
            min_limit = 1
    budget = configured_budget_tpm
    if budget is None:
        try:
            budget = int((os.getenv("PPT_API_LLM_BUDGET_TPM") or "0").strip() or "0")
        except ValueError:
            budget = 0
    utilization = target_utilization
    if utilization is None:
        try:
            utilization = float((os.getenv("PPT_API_LLM_TARGET_UTILIZATION") or "0.75").strip() or "0.75")
        except ValueError:
            utilization = 0.75
    observed = observed_svg_worker_tpm
    if observed is None and job_store is not None:
        try:
            observed_raw = job_store.client.get(f"{settings.redis_key_prefix}:llm:ewma:svg:tpm")
            observed = float(observed_raw) if observed_raw else None
        except Exception:
            observed = None
    if not budget or not observed or observed <= 0:
        return static_limit
    calculated = max(min_limit, int((budget * utilization) // observed))
    return min(hard_max, calculated)


def _build_job_dir(report_id: str) -> Path:
    token = sanitize_title(report_id)
    return settings.jobs_dir / f"{token}_{int(time.time() * 1000)}"


def _normalize_report_to_ppt_request(request: ReportRequest) -> NormalizedRequest:
    return NormalizedRequest(
        report_id=request.reportId,
        content=request.content,
        file_url=request.fileUrl,
        word_url=None,
        title=None,
        callback_url=request.callbackUrl,
        batch_mode=request.batchMode,
        batch_size=request.batchSize,
        parallel_batch_workers=request.parallelBatchWorkers,
        batch_partition=request.batchPartition,
        spec_model=(request.specModel.strip() if isinstance(request.specModel, str) and request.specModel.strip() else None),
        notes_model=(request.notesModel.strip() if isinstance(request.notesModel, str) and request.notesModel.strip() else None),
        response_mode=(request.responseMode or settings.default_response_mode),
        callback_mode=(request.callbackMode or settings.default_callback_mode),
    )


def _normalize_generate_ppt_request(request: GeneratePptRequest) -> NormalizedRequest:
    return NormalizedRequest(
        report_id=request.report_id,
        content=request.content,
        file_url=request.fileUrl,
        word_url=request.wordUrl,
        title=_normalize_generate_title(request.title),
        callback_url=request.callbackUrl,
        batch_mode=request.batchMode,
        batch_size=request.batchSize,
        parallel_batch_workers=request.parallelBatchWorkers,
        batch_partition=request.batchPartition,
        spec_model=(request.specModel.strip() if isinstance(request.specModel, str) and request.specModel.strip() else None),
        notes_model=(request.notesModel.strip() if isinstance(request.notesModel, str) and request.notesModel.strip() else None),
        response_mode=(request.responseMode or settings.default_response_mode),
        callback_mode=(request.callbackMode or settings.default_callback_mode),
    )


def _normalize_generate_title(raw_title) -> str | None:
    if raw_title is None:
        return None
    if isinstance(raw_title, str):
        return raw_title.strip() or None
    if isinstance(raw_title, list):
        if raw_title:
            first = raw_title[0]
            if isinstance(first, dict) and first.get("sub_answer"):
                text = str(first["sub_answer"]).strip()
                if text:
                    return text
        flattened = " - ".join(str(item).strip() for item in raw_title if str(item).strip())
        return flattened or None
    return str(raw_title).strip() or None
