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
    qwen_spec_model: str | None
    qwen_review_model: str | None
    qwen_notes_model: str | None
    batch_mode: str
    batch_size: int
    parallel_batch_workers: int
    batch_partition: str
    llm_slot_dir: Path
    llm_spec_slots: int
    llm_svg_slots: int
    llm_notes_slots: int
    postprocess_slots: int
    cos_secret_id: str
    cos_secret_key: str
    cos_region: str
    cos_bucket: str
    report_callback_url: str | None
    redis_url: str | None
    redis_key_prefix: str
    async_worker_count: int
    default_response_mode: str
    default_callback_mode: str

    @property
    def cos_enabled(self) -> bool:
        return bool(self.cos_secret_id and self.cos_secret_key and self.cos_bucket)


def load_settings() -> Settings:
    project_base_dir = Path(os.getenv("PPT_API_PROJECT_BASE_DIR", str(REPO_ROOT / "projects"))).expanduser()
    jobs_dir = Path(os.getenv("PPT_API_JOBS_DIR", str(REPO_ROOT / "tmp" / "api-jobs"))).expanduser()
    max_concurrent_jobs = max(1, _env_int("PPT_API_MAX_CONCURRENT_JOBS", 15))
    batch_mode = (os.getenv("PPT_API_BATCH_MODE", "parallel") or "parallel").strip().lower()
    if batch_mode not in {"auto", "always", "never", "parallel"}:
        batch_mode = "auto"
    batch_partition = (os.getenv("PPT_API_BATCH_PARTITION", "ramp_2_3_4_5_6_7_8") or "ramp_2_3_4_5_6_7_8").strip().lower()
    if batch_partition not in {"fixed", "ramp", "2+3+4+5+6+7+8", "ramp_2_3_4_5_6_7_8"}:
        batch_partition = "ramp_2_3_4_5_6_7_8"
    default_response_mode = (os.getenv("PPT_API_DEFAULT_RESPONSE_MODE", "sync") or "sync").strip().lower()
    if default_response_mode not in {"sync", "async"}:
        default_response_mode = "sync"
    default_callback_mode = (os.getenv("PPT_API_DEFAULT_CALLBACK_MODE", "auto") or "auto").strip().lower()
    if default_callback_mode not in {"auto", "defer", "none"}:
        default_callback_mode = "auto"
    return Settings(
        repo_root=REPO_ROOT,
        host=os.getenv("PPT_API_HOST", "0.0.0.0"),
        port=_env_int("PPT_API_PORT", 3000),
        max_concurrent_jobs=max_concurrent_jobs,
        runner_timeout_seconds=max(60, _env_int("PPT_API_RUNNER_TIMEOUT_SECONDS", 7200)),
        canvas_format=os.getenv("PPT_API_CANVAS_FORMAT", "ppt169"),
        project_base_dir=project_base_dir,
        jobs_dir=jobs_dir,
        keep_job_files=os.getenv("PPT_API_KEEP_JOB_FILES", "1").strip().lower() not in {"0", "false", "no"},
        qwen_model=(os.getenv("PPT_API_QWEN_MODEL") or "").strip() or None,
        qwen_spec_model=(os.getenv("PPT_API_QWEN_SPEC_MODEL") or "").strip() or None,
        qwen_review_model=(os.getenv("PPT_API_QWEN_REVIEW_MODEL") or "").strip() or None,
        qwen_notes_model=(os.getenv("PPT_API_QWEN_NOTES_MODEL") or "").strip() or None,
        batch_mode=batch_mode,
        batch_size=max(1, _env_int("PPT_API_BATCH_SIZE", 5)),
        parallel_batch_workers=max(1, _env_int("PPT_API_PARALLEL_BATCH_WORKERS", 3)),
        batch_partition=batch_partition,
        llm_slot_dir=Path(os.getenv("PPT_API_LLM_SLOT_DIR", str(REPO_ROOT / "tmp" / "llm-slots"))).expanduser(),
        llm_spec_slots=max(1, _env_int("PPT_API_LLM_SPEC_SLOTS", 4)),
        llm_svg_slots=max(1, _env_int("PPT_API_LLM_SVG_SLOTS", 10)),
        llm_notes_slots=max(1, _env_int("PPT_API_LLM_NOTES_SLOTS", 8)),
        postprocess_slots=max(1, _env_int("PPT_API_POSTPROCESS_SLOTS", 4)),
        cos_secret_id=os.getenv("COS_SECRET_ID", "").strip(),
        cos_secret_key=os.getenv("COS_SECRET_KEY", "").strip(),
        cos_region=os.getenv("COS_REGION", "ap-shanghai").strip() or "ap-shanghai",
        cos_bucket=os.getenv("COS_BUCKET", "").strip(),
        report_callback_url=((os.getenv("REPORT_CALLBACK_URL") or os.getenv("REPORT_URL") or "").strip() or None),
        redis_url=((os.getenv("PPT_REDIS_URL") or os.getenv("REDIS_URL") or "").strip() or None),
        redis_key_prefix=(os.getenv("PPT_REDIS_KEY_PREFIX", "ppt") or "ppt").strip().strip(":") or "ppt",
        async_worker_count=max(1, _env_int("PPT_API_ASYNC_WORKERS", max_concurrent_jobs)),
        default_response_mode=default_response_mode,
        default_callback_mode=default_callback_mode,
    )
