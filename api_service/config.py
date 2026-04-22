from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BATCH_PARTITION_DEFAULT = "anchor_even"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_valid_batch_partition(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return False
    if normalized in {"fixed", "ramp", "ramp_2_3_4_5_6_7_8", "anchor_even"}:
        return True
    if normalized.endswith("+"):
        normalized = normalized[:-1]
    parts = normalized.split("+")
    return bool(parts) and all(part.isdigit() and int(part) > 0 for part in parts)


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
    svg_scheduler_enabled: bool
    default_response_mode: str
    default_callback_mode: str
    metrics_export_enabled: bool
    metrics_export_dir: Path
    metrics_export_interval_seconds: int
    metrics_export_retention_files: int
    metrics_export_archive_idle_intervals: bool

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
    batch_partition = (os.getenv("PPT_API_BATCH_PARTITION", BATCH_PARTITION_DEFAULT) or BATCH_PARTITION_DEFAULT).strip().lower()
    if not _is_valid_batch_partition(batch_partition):
        batch_partition = BATCH_PARTITION_DEFAULT
    default_response_mode = (os.getenv("PPT_API_DEFAULT_RESPONSE_MODE", "sync") or "sync").strip().lower()
    if default_response_mode not in {"sync", "async"}:
        default_response_mode = "sync"
    default_callback_mode = (os.getenv("PPT_API_DEFAULT_CALLBACK_MODE", "auto") or "auto").strip().lower()
    if default_callback_mode not in {"auto", "defer", "none"}:
        default_callback_mode = "auto"
    metrics_export_dir = Path(
        os.getenv("PPT_API_METRICS_EXPORT_DIR", str(project_base_dir / "metrics"))
    ).expanduser()
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
        svg_scheduler_enabled=_env_bool("PPT_API_SVG_SCHEDULER_ENABLED", True),
        default_response_mode=default_response_mode,
        default_callback_mode=default_callback_mode,
        metrics_export_enabled=_env_bool("PPT_API_METRICS_EXPORT_ENABLED", True),
        metrics_export_dir=metrics_export_dir,
        metrics_export_interval_seconds=max(1, _env_int("PPT_API_METRICS_EXPORT_INTERVAL_SECONDS", 30)),
        metrics_export_retention_files=max(50, _env_int("PPT_API_METRICS_EXPORT_RETENTION_FILES", 2000)),
        metrics_export_archive_idle_intervals=_env_bool("PPT_API_METRICS_EXPORT_ARCHIVE_IDLE_INTERVALS", False),
    )
