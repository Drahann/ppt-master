from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .account_pool import AccountLease
from .config import Settings


RUNNER_SCRIPT = Path("skills/ppt-master/scripts/api_ppt.py")


@dataclass
class RunnerResult:
    job_id: str
    status: str
    project_path: Path
    native_pptx_path: Path
    svg_pptx_path: Path | None
    title: str
    slide_count: int
    usage_summary: dict[str, Any]


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
    *,
    source_md_path: Path,
    report_id: str,
    title: str,
    settings: Settings,
    working_dir: Path,
    account_lease: AccountLease | None,
    svg_workers: int,
    svg_batch_size: int,
    qwen_model: str | None,
    notes_model: str | None,
    claude_effort: str | None,
) -> RunnerResult:
    job_id = build_job_id(report_id)
    working_dir.mkdir(parents=True, exist_ok=True)

    project_name = build_project_name(report_id, title)
    command = [
        sys.executable,
        str(settings.repo_root / RUNNER_SCRIPT),
        "generate",
        str(source_md_path),
        "--project-name",
        project_name,
        "--projects-dir",
        str(settings.project_base_dir),
        "--format",
        settings.canvas_format,
        "--style",
        settings.style,
        "--renderer",
        settings.renderer,
        "--planner-provider",
        settings.planner_provider,
        "--notes-provider",
        settings.notes_provider,
        "--qwen-base-url",
        settings.qwen_base_url,
        "--qwen-model",
        qwen_model or settings.qwen_model,
        "--qwen-max-tokens",
        str(settings.qwen_max_tokens),
        "--deepseek-base-url",
        account_lease.base_url if account_lease and account_lease.base_url else settings.deepseek_base_url,
        "--deepseek-model",
        account_lease.deepseek_model if account_lease and account_lease.deepseek_model else settings.deepseek_model,
        "--claude-model",
        account_lease.claude_model if account_lease and account_lease.claude_model else settings.claude_model,
        "--claude-flash-model",
        account_lease.claude_flash_model if account_lease and account_lease.claude_flash_model else settings.claude_flash_model,
        "--claude-effort",
        claude_effort or settings.claude_effort,
        "--claude-timeout",
        str(settings.claude_timeout),
        "--claude-retries",
        str(settings.claude_retries),
        "--svg-workers",
        str(svg_workers),
        "--svg-batch-size",
        str(svg_batch_size),
    ]
    if settings.cache_prime:
        command.append("--cache-prime")

    request_payload = {
        "job_id": job_id,
        "report_id": report_id,
        "project_name": project_name,
        "source_md_path": str(source_md_path),
        "command": _redact_command(command),
        "account_id": account_lease.account_id if account_lease else None,
        "svg_workers": svg_workers,
        "svg_batch_size": svg_batch_size,
    }
    (working_dir / "runner_request.json").write_text(json.dumps(request_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    child_env = dict(os.environ)
    qwen_api_key = child_env.get("DASHSCOPE_API_KEY") or child_env.get("QWEN_API_KEY") or child_env.get("PPT_API_QWEN_API_KEY")
    if qwen_api_key:
        child_env.setdefault("DASHSCOPE_API_KEY", qwen_api_key)
        child_env.setdefault("QWEN_API_KEY", qwen_api_key)
    if account_lease is not None:
        child_env["DEEPSEEK_API_KEY"] = account_lease.api_key
        child_env["ANTHROPIC_AUTH_TOKEN"] = account_lease.api_key
        if account_lease.base_url:
            child_env["ANTHROPIC_BASE_URL"] = account_lease.base_url
    child_env.setdefault("PYTHONIOENCODING", "utf-8")

    completed = subprocess.run(
        command,
        cwd=settings.repo_root,
        env=child_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=settings.runner_timeout_seconds,
        check=False,
    )
    (working_dir / "runner.stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
    (working_dir / "runner.stderr.txt").write_text(completed.stderr or "", encoding="utf-8")

    payload = _load_runner_payload(completed.stdout, completed.stderr)
    if completed.returncode != 0 or payload.get("ok") is not True:
        raise RuntimeError(payload.get("error") or completed.stderr.strip() or completed.stdout.strip() or "PPT runner failed")

    project_path = Path(payload["project_path"])
    native_pptx_path = Path(payload["pptx_path"])
    svg_pptx_raw = payload.get("svg_pptx_path")
    svg_pptx_path = Path(svg_pptx_raw) if svg_pptx_raw else None
    if not native_pptx_path.exists():
        raise RuntimeError(f"runner reported missing PPTX: {native_pptx_path}")

    return RunnerResult(
        job_id=job_id,
        status="succeeded",
        project_path=project_path,
        native_pptx_path=native_pptx_path,
        svg_pptx_path=svg_pptx_path,
        title=title,
        slide_count=int(payload.get("slides") or _read_slide_count(project_path)),
        usage_summary=_read_usage_summary(project_path),
    )


def _redact_command(command: list[str]) -> list[str]:
    redacted = []
    redact_next = False
    for item in command:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        redacted.append(item)
        if item in {"--deepseek-api-key", "--qwen-api-key"}:
            redact_next = True
    return redacted


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
    raise RuntimeError((stderr or stdout or "runner did not produce a readable JSON result").strip())


def _read_slide_count(project_path: Path) -> int:
    svg_final = project_path / "svg_final"
    if svg_final.exists():
        return len(list(svg_final.glob("*.svg")))
    return 0


def _read_usage_summary(project_path: Path) -> dict[str, Any]:
    usage_path = project_path / "logs" / "usage.jsonl"
    summary = {
        "claude_svg_entries": 0,
        "claude_svg_ok": 0,
        "claude_svg_failed": 0,
        "qwen_plan_tokens": 0,
        "qwen_notes_tokens": 0,
    }
    if not usage_path.exists():
        return summary
    for line in usage_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        label = item.get("label")
        if label == "claude_svg":
            summary["claude_svg_entries"] += 1
            if item.get("ok") is True:
                summary["claude_svg_ok"] += 1
            elif item.get("ok") is False:
                summary["claude_svg_failed"] += 1
        elif label == "qwen_plan":
            summary["qwen_plan_tokens"] = _usage_total_tokens(item.get("usage"))
        elif label == "qwen_notes":
            summary["qwen_notes_tokens"] = _usage_total_tokens(item.get("usage"))
    return summary


def _usage_total_tokens(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    total = usage.get("total_tokens")
    if isinstance(total, int):
        return total
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    try:
        return int(prompt) + int(completion)
    except (TypeError, ValueError):
        return 0
