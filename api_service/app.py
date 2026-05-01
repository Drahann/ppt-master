from __future__ import annotations

import asyncio
import json
import logging
import random
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from .account_pool import AccountPoolConfigError, RedisAccountPool, load_account_pool_entries
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
settings.metrics_export_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ppt-master-claude-api", version="1.0.0")
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

account_pool: RedisAccountPool | None = None
account_pool_error: str | None = None
account_pool_initialized = False

_DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")


def _ensure_account_pool() -> RedisAccountPool | None:
    global account_pool, account_pool_error, account_pool_initialized
    if account_pool_initialized:
        return account_pool
    account_pool_initialized = True
    if job_store is None:
        return None
    try:
        accounts = load_account_pool_entries()
        if accounts:
            account_pool = RedisAccountPool(
                job_store.client,
                accounts,
                key_prefix=settings.redis_key_prefix,
                lease_ttl_seconds=settings.runner_timeout_seconds + 600,
            )
            logger.info("Configured DeepSeek/Claude account pool with %s accounts", len(accounts))
    except AccountPoolConfigError as exc:
        account_pool_error = str(exc)
        logger.error("Invalid account pool configuration: %s", exc)
    except Exception as exc:
        account_pool_error = str(exc)
        logger.exception("Failed to initialize account pool: %s", exc)
    return account_pool


@app.get("/healthz")
def healthz() -> dict[str, object]:
    pool = _ensure_account_pool()
    return {
        "ok": True,
        "service": "ppt-master-claude-api",
        "cosEnabled": settings.cos_enabled,
        "projectBaseDir": str(settings.project_base_dir),
        "jobsDir": str(settings.jobs_dir),
        "maxConcurrentJobs": settings.max_concurrent_jobs,
        "asyncWorkers": len(worker_threads),
        "runner": {
            "renderer": settings.renderer,
            "plannerProvider": settings.planner_provider,
            "notesProvider": settings.notes_provider,
            "svgWorkers": settings.svg_workers,
            "svgBatchSize": settings.svg_batch_size,
            "claudeEffort": settings.claude_effort,
            "cachePrime": settings.cache_prime,
            "startStagger": {
                "enabled": settings.runner_start_stagger_enabled,
                "seconds": settings.runner_start_stagger_seconds,
                "jitterSeconds": settings.runner_start_jitter_seconds,
                "scope": settings.runner_start_stagger_scope,
            },
        },
        "redis": {
            "configured": bool(settings.redis_url),
            "available": _redis_available(),
            "error": job_store_error,
            "keyPrefix": settings.redis_key_prefix,
        },
        "apiKeyPool": {
            "configured": bool(pool is not None),
            "enabled": bool(pool is not None),
            "error": account_pool_error,
            "required": settings.require_account_pool,
            "policy": "job lease: max 2 jobs / 24 svg slots per account by default",
        },
    }


@app.get("/metrics")
def get_metrics() -> dict[str, object]:
    return _build_metrics_payload()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return _DASHBOARD_HTML


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request, exc: RequestValidationError) -> JSONResponse:
    missing_fields = ["/".join(str(item) for item in err.get("loc", [])[1:]) for err in exc.errors()]
    message = "Invalid request body"
    if missing_fields:
        message = f"Missing or invalid field(s): {', '.join(missing_fields)}"
    return JSONResponse(status_code=400, content={"error": message})


@app.on_event("startup")
def start_workers() -> None:
    if job_store is not None and not worker_threads:
        try:
            job_store.ping()
        except Exception as exc:
            global job_store_error
            job_store_error = str(exc)
        _ensure_account_pool()
        for index in range(settings.async_worker_count):
            thread = threading.Thread(target=_async_worker_loop, name=f"ppt-async-worker-{index + 1}", daemon=True)
            thread.start()
            worker_threads.append(thread)
            logger.info("Started async worker thread %s", thread.name)
    _start_metrics_exporter()
    _snapshot_metrics_to_disk("startup")


@app.on_event("shutdown")
def stop_workers() -> None:
    worker_stop_event.set()
    for thread in worker_threads:
        thread.join(timeout=2)
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
    svg_workers = request.svg_workers or settings.svg_workers
    svg_batch_size = request.svg_batch_size or settings.svg_batch_size
    account_lease = None
    pool = _ensure_account_pool()
    account_error: str | None = None

    try:
        if pool is None and settings.require_account_pool:
            detail = f": {account_pool_error}" if account_pool_error else ""
            raise RuntimeError(f"DeepSeek/Claude account pool is required{detail}")
        if pool is not None:
            _update_job_stage(metric_job_id, job_id, "account_pool", event="waiting_for_deepseek_account")
            account_lease = pool.acquire(
                requested_slots=svg_workers,
                owner_job_id=metric_job_id,
                label=f"{request.report_id}:{title}",
                timeout_seconds=settings.account_lease_timeout_seconds,
            )
            if account_lease is None:
                raise RuntimeError("No DeepSeek/Claude account lease available before timeout")

        metrics.start_job(
            metric_job_id,
            request.report_id,
            title or "untitled",
            queue_wait_seconds=queue_wait_seconds,
            response_mode=request.response_mode,
            callback_mode=request.callback_mode,
            worker_name=threading.current_thread().name,
            account_id=account_lease.account_id if account_lease else None,
            requested_slots=svg_workers,
        )
        logger.info(
            "Starting PPT job job_id=%s report_id=%s account=%s svg_workers=%s svg_batch_size=%s",
            metric_job_id,
            request.report_id,
            account_lease.account_id if account_lease else None,
            svg_workers,
            svg_batch_size,
        )
        with execution_semaphore:
            _update_job_stage(metric_job_id, job_id, "preparing", event="processing_markdown")
            processed_markdown, image_warnings = process_markdown_images(request.content, job_dir)
            source_md_path = job_dir / "source.md"
            source_md_path.write_text(processed_markdown, encoding="utf-8")
            if image_warnings:
                (job_dir / "image_warnings.txt").write_text("\n".join(image_warnings) + "\n", encoding="utf-8")

            _apply_runner_start_delay(metric_job_id, job_id, account_lease.account_id if account_lease else None)
            _update_job_stage(metric_job_id, job_id, "runner", event="api_ppt_generate_started")
            runner_result = execute_runner(
                source_md_path=source_md_path,
                report_id=request.report_id,
                title=title,
                settings=settings,
                working_dir=job_dir,
                account_lease=account_lease,
                svg_workers=svg_workers,
                svg_batch_size=svg_batch_size,
                qwen_model=request.qwen_model,
                notes_model=request.notes_model,
                claude_effort=request.claude_effort,
            )

            notes_path = runner_result.project_path / "notes" / "total.md"
            zip_buffer = build_result_zip(
                runner_result.native_pptx_path,
                notes_path,
                runner_result.title,
                runner_result.source_han_native_pptx_path,
            )
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
            return {
                "success": True,
                "reportId": request.report_id,
                "pptUrl": ppt_url,
                "slideCount": runner_result.slide_count,
                "title": runner_result.title,
                "callback": CallbackResultModel(success=callback_result.success, error=callback_result.error).model_dump(),
                "account": account_lease.account_id if account_lease else None,
                "usage": runner_result.usage_summary,
            }
    except Exception as exc:
        account_error = str(exc)
        metrics.fail_job(metric_job_id, str(exc))
        logger.exception("PPT job failed job_id=%s report_id=%s error=%s", metric_job_id, request.report_id, exc)
        raise
    finally:
        if account_lease is not None and pool is not None:
            pool.release(account_lease, error=account_error)


def _enqueue_async_request(request: NormalizedRequest, *, report_style: bool) -> JSONResponse | ReportResponse | GeneratePptResponse:
    if job_store is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "Redis job store is not configured", "detail": job_store_error})
    try:
        title = request.title or derive_title(request.content, request.report_id)
        job_id = job_store.create_job(request, title=title)
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
        _run_async_job(job_id)


def _run_async_job(job_id: str) -> None:
    assert job_store is not None
    record = job_store.mark_running(job_id, stage="running")
    if record is None or record.get("status") == "cancelled":
        return
    try:
        request = NormalizedRequest(**record["request"])
        payload = _process_request(request, job_id=job_id)
        job_store.complete(job_id, payload)
        _snapshot_metrics_to_disk("job_complete")
    except Exception as exc:
        job_store.fail(job_id, str(exc))
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


def _apply_runner_start_delay(metric_job_id: str, queue_job_id: str | None, account_id: str | None) -> float:
    if not settings.runner_start_stagger_enabled:
        return 0.0

    base_seconds = max(0.0, settings.runner_start_stagger_seconds)
    jitter_seconds = random.uniform(0.0, max(0.0, settings.runner_start_jitter_seconds))
    redis_delay = _reserve_runner_start_slot(account_id, base_seconds) if job_store is not None else base_seconds
    delay = max(0.0, redis_delay + jitter_seconds)
    if delay <= 0:
        return 0.0

    _update_job_stage(
        metric_job_id,
        queue_job_id,
        "runner_stagger",
        event=f"delay_seconds={delay:.2f};redis_delay={redis_delay:.2f};jitter={jitter_seconds:.2f}",
    )
    logger.info("Runner start stagger job_id=%s account=%s delay=%.2fs", metric_job_id, account_id, delay)
    time.sleep(delay)
    return delay


def _reserve_runner_start_slot(account_id: str | None, base_seconds: float) -> float:
    if job_store is None or base_seconds <= 0:
        return 0.0

    key = _runner_start_gate_key(account_id)
    lock_key = f"{key}:lock"
    token = f"{threading.get_ident()}:{time.time():.6f}:{random.random():.12f}"
    deadline = time.time() + 3.0
    client = job_store.client
    locked = False

    while time.time() < deadline:
        if client.set(lock_key, token, nx=True, ex=10):
            locked = True
            break
        time.sleep(0.05)

    if not locked:
        return 0.0

    try:
        now = time.time()
        raw_next = client.get(key)
        try:
            next_allowed = float(raw_next) if raw_next else 0.0
        except (TypeError, ValueError):
            next_allowed = 0.0
        scheduled_at = max(now, next_allowed)
        client.set(key, f"{scheduled_at + base_seconds:.6f}", ex=max(3600, settings.runner_timeout_seconds))
        return max(0.0, scheduled_at - now)
    finally:
        try:
            if client.get(lock_key) == token:
                client.delete(lock_key)
        except Exception:
            pass


def _runner_start_gate_key(account_id: str | None) -> str:
    if job_store is None:
        return ""
    if settings.runner_start_stagger_scope == "account" and account_id:
        safe_account = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in account_id).strip("._-") or "unknown"
        return job_store.key(f"runner_start:account:{safe_account}")
    return job_store.key("runner_start:global")


def _account_pool_snapshot() -> dict[str, object]:
    pool = _ensure_account_pool()
    if pool is None:
        return {"enabled": False, "configured": False, "required": settings.require_account_pool, "error": account_pool_error}
    try:
        snapshot = pool.snapshot()
        snapshot["required"] = settings.require_account_pool
        return snapshot
    except Exception as exc:
        return {"enabled": True, "configured": True, "error": str(exc)}


def _build_metrics_payload() -> dict[str, object]:
    payload = metrics.snapshot(settings.max_concurrent_jobs)
    payload["redisJobs"] = _redis_job_snapshot()
    payload["apiKeyPool"] = _account_pool_snapshot()
    payload["runner"] = {
        "svg_workers": settings.svg_workers,
        "svg_batch_size": settings.svg_batch_size,
        "planner_provider": settings.planner_provider,
        "notes_provider": settings.notes_provider,
        "qwen_model": settings.qwen_model,
        "qwen_notes_model": settings.qwen_notes_model,
        "qwen_timeout": settings.qwen_timeout,
        "claude_model": settings.claude_model,
        "claude_flash_model": settings.claude_flash_model,
        "start_stagger": {
            "enabled": settings.runner_start_stagger_enabled,
            "seconds": settings.runner_start_stagger_seconds,
            "jitter_seconds": settings.runner_start_jitter_seconds,
            "scope": settings.runner_start_stagger_scope,
        },
    }
    payload["asyncWorkers"] = {
        "configured": settings.async_worker_count,
        "running": len(worker_threads),
        "stopped": worker_stop_event.is_set(),
    }
    payload["captured_at"] = datetime.now().isoformat(timespec="seconds")
    return payload


def _job_queue_wait_seconds(job_id: str | None) -> float:
    if not job_id or job_store is None:
        return 0.0
    try:
        record = job_store.get_job(job_id)
        created_at = float((record or {}).get("created_at") or 0)
        return round(max(0.0, time.time() - created_at), 1) if created_at > 0 else 0.0
    except Exception:
        return 0.0


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
        response_mode=(request.responseMode or settings.default_response_mode),
        callback_mode=(request.callbackMode or settings.default_callback_mode),
        svg_workers=request.svgWorkers or request.parallelBatchWorkers,
        svg_batch_size=request.svgBatchSize or request.batchSize,
        qwen_model=request.qwenModel or request.specModel,
        notes_model=request.notesModel,
        claude_effort=request.claudeEffort,
    )


def _normalize_generate_ppt_request(request: GeneratePptRequest) -> NormalizedRequest:
    return NormalizedRequest(
        report_id=request.report_id,
        content=request.content,
        file_url=request.fileUrl,
        word_url=request.wordUrl,
        title=_normalize_generate_title(request.title),
        callback_url=request.callbackUrl,
        response_mode=(request.responseMode or settings.default_response_mode),
        callback_mode=(request.callbackMode or settings.default_callback_mode),
        svg_workers=request.svgWorkers or request.parallelBatchWorkers,
        svg_batch_size=request.svgBatchSize or request.batchSize,
        qwen_model=request.qwenModel or request.specModel,
        notes_model=request.notesModel,
        claude_effort=request.claudeEffort,
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


def _start_metrics_exporter() -> None:
    global metrics_export_thread
    if not settings.metrics_export_enabled:
        return
    if metrics_export_thread is not None and metrics_export_thread.is_alive():
        return
    metrics_export_stop_event.clear()
    metrics_export_thread = threading.Thread(target=_metrics_export_loop, name="ppt-metrics-exporter", daemon=True)
    metrics_export_thread.start()


def _stop_metrics_exporter() -> None:
    global metrics_export_thread
    metrics_export_stop_event.set()
    if metrics_export_thread is not None:
        metrics_export_thread.join(timeout=2)
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
        latest_path = root / "latest.json"
        payload = _build_metrics_payload()
        payload["snapshot_reason"] = reason
        latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
