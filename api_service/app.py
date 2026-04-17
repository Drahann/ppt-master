from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import load_settings
from .markdown_assets import process_markdown_images
from .models import CallbackResult as CallbackResultModel
from .models import ReportRequest, ReportResponse
from .runner import derive_title, execute_runner
from .storage import build_result_zip, notify_report_server, sanitize_title, upload_to_cos


settings = load_settings()
settings.project_base_dir.mkdir(parents=True, exist_ok=True)
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="ppt-master-api", version="1.0.0")
job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "cosEnabled": settings.cos_enabled,
        "projectBaseDir": str(settings.project_base_dir),
        "jobsDir": str(settings.jobs_dir),
        "maxConcurrentJobs": settings.max_concurrent_jobs,
    }


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
            payload = await asyncio.to_thread(_process_request, request)
            return ReportResponse(**payload)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc), "reportId": request.reportId})


def _process_request(request: ReportRequest) -> dict[str, object]:
    title = derive_title(request.content, request.reportId)
    job_dir = _build_job_dir(request.reportId)
    job_dir.mkdir(parents=True, exist_ok=True)

    processed_markdown, image_warnings = process_markdown_images(request.content, job_dir)
    source_md_path = job_dir / "source.md"
    source_md_path.write_text(processed_markdown, encoding="utf-8")
    if image_warnings:
        (job_dir / "image_warnings.txt").write_text("\n".join(image_warnings) + "\n", encoding="utf-8")

    runner_result = execute_runner(
        source_md_path=source_md_path,
        report_id=request.reportId,
        title=title,
        settings=settings,
        working_dir=job_dir,
        batch_mode=(request.batchMode or settings.batch_mode),
        batch_size=(request.batchSize or settings.batch_size),
    )

    notes_path = runner_result.project_path / "notes" / "total.md"
    zip_buffer = build_result_zip(runner_result.native_pptx_path, notes_path, runner_result.title)

    safe_title = sanitize_title(runner_result.title)
    cos_path = f"ppt/{request.reportId}/{safe_title}.zip"
    ppt_url = upload_to_cos(zip_buffer, cos_path, settings)

    callback_result = notify_report_server(
        report_id=request.reportId,
        file_url=request.fileUrl,
        ppt_url=ppt_url,
        callback_url=(request.callbackUrl or settings.report_callback_url),
    )

    if not settings.keep_job_files:
        shutil.rmtree(job_dir, ignore_errors=True)

    return {
        "success": True,
        "reportId": request.reportId,
        "pptUrl": ppt_url,
        "slideCount": runner_result.slide_count,
        "title": runner_result.title,
        "callback": CallbackResultModel(success=callback_result.success, error=callback_result.error).model_dump(),
    }


def _build_job_dir(report_id: str) -> Path:
    token = sanitize_title(report_id)
    return settings.jobs_dir / f"{token}_{int(time.time() * 1000)}"
