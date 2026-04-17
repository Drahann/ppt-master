from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    host: str
    port: int
    max_concurrent_jobs: int
    runner_timeout_seconds: int
    canvas_format: str
    project_base_dir: Path
    jobs_dir: Path
    keep_job_files: bool
    qwen_model: str | None
    qwen_review_model: str | None
    batch_mode: str
    batch_size: int
    cos_secret_id: str
    cos_secret_key: str
    cos_region: str
    cos_bucket: str
    report_callback_url: str | None

    @property
    def cos_enabled(self) -> bool:
        return bool(self.cos_secret_id and self.cos_secret_key and self.cos_bucket)


def load_settings() -> Settings:
    project_base_dir = Path(os.getenv("PPT_API_PROJECT_BASE_DIR", str(REPO_ROOT / "projects"))).expanduser()
    jobs_dir = Path(os.getenv("PPT_API_JOBS_DIR", str(REPO_ROOT / "tmp" / "api-jobs"))).expanduser()
    batch_mode = (os.getenv("PPT_API_BATCH_MODE", "auto") or "auto").strip().lower()
    if batch_mode not in {"auto", "always", "never"}:
        batch_mode = "auto"
    return Settings(
        repo_root=REPO_ROOT,
        host=os.getenv("PPT_API_HOST", "0.0.0.0"),
        port=_env_int("PPT_API_PORT", 3000),
        max_concurrent_jobs=max(1, _env_int("PPT_API_MAX_CONCURRENT_JOBS", 1)),
        runner_timeout_seconds=max(60, _env_int("PPT_API_RUNNER_TIMEOUT_SECONDS", 7200)),
        canvas_format=os.getenv("PPT_API_CANVAS_FORMAT", "ppt169"),
        project_base_dir=project_base_dir,
        jobs_dir=jobs_dir,
        keep_job_files=os.getenv("PPT_API_KEEP_JOB_FILES", "1").strip().lower() not in {"0", "false", "no"},
        qwen_model=(os.getenv("PPT_API_QWEN_MODEL") or "").strip() or None,
        qwen_review_model=(os.getenv("PPT_API_QWEN_REVIEW_MODEL") or "").strip() or None,
        batch_mode=batch_mode,
        batch_size=max(1, _env_int("PPT_API_BATCH_SIZE", 8)),
        cos_secret_id=os.getenv("COS_SECRET_ID", "").strip(),
        cos_secret_key=os.getenv("COS_SECRET_KEY", "").strip(),
        cos_region=os.getenv("COS_REGION", "ap-shanghai").strip() or "ap-shanghai",
        cos_bucket=os.getenv("COS_BUCKET", "").strip(),
        report_callback_url=((os.getenv("REPORT_CALLBACK_URL") or os.getenv("REPORT_URL") or "").strip() or None),
    )
