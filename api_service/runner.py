from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings


RUNNER_SCRIPT = Path("skills/ppt-master/scripts/qwen_ppt_runner.py")


@dataclass
class RunnerResult:
    job_id: str
    status: str
    project_path: Path
    native_pptx_path: Path
    svg_pptx_path: Path | None
    log_path: Path | None
    title: str
    slide_count: int


def derive_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return fallback


def build_job_id(report_id: str) -> str:
    token = re.sub(r"[^0-9A-Za-z_-]+", "_", report_id).strip("_") or "report"
    return f"{token}_{uuid.uuid4().hex[:8]}"


def build_project_name(report_id: str, title: str) -> str:
    base = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", title).strip("_")
    if not base:
        base = re.sub(r"[^0-9A-Za-z_-]+", "_", report_id).strip("_") or "presentation"
    return base[:60]


def execute_runner(
    source_md_path: Path,
    report_id: str,
    title: str,
    settings: Settings,
    working_dir: Path,
    batch_mode: str | None = None,
    batch_size: int | None = None,
    parallel_batch_workers: int | None = None,
    batch_partition: str | None = None,
    spec_model: str | None = None,
    notes_model: str | None = None,
) -> RunnerResult:
    job_id = build_job_id(report_id)
    working_dir.mkdir(parents=True, exist_ok=True)

    request_payload: dict[str, Any] = {
        "job_id": job_id,
        "source_md_path": str(source_md_path),
        "project_name": build_project_name(report_id, title),
        "canvas_format": settings.canvas_format,
        "project_base_dir": str(settings.project_base_dir),
    }
    if settings.qwen_model:
        request_payload["model"] = settings.qwen_model
    effective_spec_model = spec_model or settings.qwen_spec_model or settings.qwen_model
    if effective_spec_model:
        request_payload["spec_model"] = effective_spec_model
    if settings.qwen_review_model:
        request_payload["review_model"] = settings.qwen_review_model
    effective_notes_model = notes_model or settings.qwen_notes_model
    if effective_notes_model:
        request_payload["notes_model"] = effective_notes_model
    if batch_mode:
        request_payload["batch_mode"] = batch_mode
    if batch_size is not None:
        request_payload["batch_size"] = batch_size
    if parallel_batch_workers is not None:
        request_payload["parallel_batch_workers"] = parallel_batch_workers
    if batch_partition:
        request_payload["batch_partition"] = batch_partition

    request_path = working_dir / "runner_request.json"
    request_path.write_text(json.dumps(request_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    command = [sys.executable, str(settings.repo_root / RUNNER_SCRIPT), str(request_path)]
    completed = subprocess.run(
        command,
        cwd=settings.repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=settings.runner_timeout_seconds,
        check=False,
    )

    payload = _load_runner_payload(completed.stdout, completed.stderr)
    if completed.returncode != 0 or payload.get("status") != "succeeded":
        raise RuntimeError(payload.get("error") or completed.stderr.strip() or completed.stdout.strip() or "Runner failed")

    project_path = Path(payload["project_path"])
    native_pptx_path = Path(payload["native_pptx_path"])
    svg_pptx_raw = payload.get("svg_pptx_path")
    svg_pptx_path = Path(svg_pptx_raw) if svg_pptx_raw else None
    log_raw = payload.get("log_path")
    log_path = Path(log_raw) if log_raw else None

    return RunnerResult(
        job_id=job_id,
        status="succeeded",
        project_path=project_path,
        native_pptx_path=native_pptx_path,
        svg_pptx_path=svg_pptx_path,
        log_path=log_path,
        title=title,
        slide_count=_read_slide_count(project_path),
    )


def _load_runner_payload(stdout: str, stderr: str) -> dict[str, Any]:
    stdout = (stdout or "").strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            for index, char in enumerate(stdout):
                if char != "{":
                    continue
                try:
                    return json.loads(stdout[index:])
                except json.JSONDecodeError:
                    continue
    raise RuntimeError(stderr.strip() or stdout or "Runner did not produce a readable JSON result")


def _read_slide_count(project_path: Path) -> int:
    slide_plan_path = project_path / "runner" / "slide_plan.json"
    if slide_plan_path.exists():
        try:
            payload = json.loads(slide_plan_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return len(payload)
        except Exception:
            pass

    svg_final = project_path / "svg_final"
    if svg_final.exists():
        return len(list(svg_final.glob("*.svg")))
    return 0
