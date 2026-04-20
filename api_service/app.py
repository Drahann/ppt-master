from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from .config import load_settings
from .markdown_assets import process_markdown_images
from .metrics import metrics
from .models import CallbackResult as CallbackResultModel
from .models import GeneratePptRequest, GeneratePptResponse, NormalizedRequest, ReportRequest, ReportResponse
from .runner import derive_title, execute_runner
from .storage import build_result_zip, notify_report_server, sanitize_title, upload_to_cos


settings = load_settings()
settings.project_base_dir.mkdir(parents=True, exist_ok=True)
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.llm_slot_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="ppt-master-api", version="1.0.0")
job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)


_DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")


def _llm_slot_snapshot() -> dict[str, dict[str, int | str]]:
    limits = {
        "spec": settings.llm_spec_slots,
        "svg": settings.llm_svg_slots,
        "notes": settings.llm_notes_slots,
        "postprocess": settings.postprocess_slots,
    }
    snapshot: dict[str, dict[str, int | str]] = {}
    for stage, limit in limits.items():
        stage_dir = settings.llm_slot_dir / stage
        active = len(list(stage_dir.glob("*.slot"))) if stage_dir.exists() else 0
        snapshot[stage] = {
            "active": active,
            "limit": limit,
            "available": max(0, limit - active),
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
    }


@app.get("/metrics")
def get_metrics() -> dict:
    """Real-time performance metrics JSON."""
    payload = metrics.snapshot(settings.max_concurrent_jobs)
    payload["llmSlots"] = _llm_slot_snapshot()
    return payload


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


@app.post("/api/report-to-ppt", response_model=ReportResponse)
async def report_to_ppt(request: ReportRequest):
    async with job_semaphore:
        try:
            payload = await asyncio.to_thread(_process_request, _normalize_report_to_ppt_request(request))
            return ReportResponse(**payload)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc), "reportId": request.reportId})


@app.post("/api/generate-ppt", response_model=GeneratePptResponse)
async def generate_ppt(request: GeneratePptRequest):
    async with job_semaphore:
        try:
            payload = await asyncio.to_thread(_process_request, _normalize_generate_ppt_request(request))
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


def _process_request(request: NormalizedRequest) -> dict[str, object]:
    title = request.title or derive_title(request.content, request.report_id)
    job_dir = _build_job_dir(request.report_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_id = job_dir.name

    metrics.start_job(job_id, request.report_id, title or "untitled")
    try:
        processed_markdown, image_warnings = process_markdown_images(request.content, job_dir)
        source_md_path = job_dir / "source.md"
        source_md_path.write_text(processed_markdown, encoding="utf-8")
        if image_warnings:
            (job_dir / "image_warnings.txt").write_text("\n".join(image_warnings) + "\n", encoding="utf-8")

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
        ppt_url = upload_to_cos(zip_buffer, cos_path, settings)

        callback_result = notify_report_server(
            report_id=request.report_id,
            file_url=request.file_url,
            word_url=request.word_url,
            ppt_url=ppt_url,
            callback_url=(request.callback_url or settings.report_callback_url),
        )

        if not settings.keep_job_files:
            shutil.rmtree(job_dir, ignore_errors=True)

        metrics.finish_job(job_id, runner_result.slide_count)
        return {
            "success": True,
            "reportId": request.report_id,
            "pptUrl": ppt_url,
            "slideCount": runner_result.slide_count,
            "title": runner_result.title,
            "callback": CallbackResultModel(success=callback_result.success, error=callback_result.error).model_dump(),
        }
    except Exception as exc:
        metrics.fail_job(job_id, str(exc))
        raise


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
