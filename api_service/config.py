from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    host: str
    port: int
    project_base_dir: Path
    jobs_dir: Path
    keep_job_files: bool
    max_concurrent_jobs: int
    async_worker_count: int
    runner_timeout_seconds: int
    default_response_mode: str
    default_callback_mode: str
    redis_url: str | None
    redis_key_prefix: str
    canvas_format: str
    style: str
    renderer: str
    planner_provider: str
    notes_provider: str
    qwen_base_url: str
    qwen_model: str
    qwen_notes_model: str | None
    qwen_max_tokens: int
    qwen_timeout: int
    deepseek_base_url: str
    deepseek_model: str
    svg_model: str
    svg_repair_model: str
    svg_timeout: int
    svg_retries: int
    svg_workers: int
    svg_batch_size: int
    cache_prime: bool
    runner_start_stagger_enabled: bool
    runner_start_stagger_seconds: float
    runner_start_jitter_seconds: float
    runner_start_stagger_scope: str
    account_pool_file: str | None
    account_pool_json: str | None
    require_account_pool: bool
    account_lease_timeout_seconds: int
    cos_secret_id: str
    cos_secret_key: str
    cos_region: str
    cos_bucket: str
    report_callback_url: str | None
    metrics_export_enabled: bool
    metrics_export_dir: Path
    metrics_export_interval_seconds: int

    @property
    def cos_enabled(self) -> bool:
        return bool(self.cos_secret_id and self.cos_secret_key and self.cos_bucket)


def _choice(name: str, default: str, allowed: set[str]) -> str:
    value = (os.getenv(name) or default).strip().lower()
    return value if value in allowed else default


def load_settings() -> Settings:
    project_base_dir = Path(os.getenv("PPT_API_PROJECT_BASE_DIR", str(REPO_ROOT / "projects"))).expanduser()
    jobs_dir = Path(os.getenv("PPT_API_JOBS_DIR", str(REPO_ROOT / "tmp" / "api-jobs"))).expanduser()
    max_jobs = max(1, _env_int("PPT_API_MAX_CONCURRENT_JOBS", 20))
    metrics_export_dir = Path(os.getenv("PPT_API_METRICS_EXPORT_DIR", str(project_base_dir / "metrics"))).expanduser()
    return Settings(
        repo_root=REPO_ROOT,
        host=os.getenv("PPT_API_HOST", "0.0.0.0"),
        port=_env_int("PPT_API_PORT", 3000),
        project_base_dir=project_base_dir,
        jobs_dir=jobs_dir,
        keep_job_files=_env_bool("PPT_API_KEEP_JOB_FILES", True),
        max_concurrent_jobs=max_jobs,
        async_worker_count=max(1, _env_int("PPT_API_ASYNC_WORKERS", max_jobs)),
        runner_timeout_seconds=max(60, _env_int("PPT_API_RUNNER_TIMEOUT_SECONDS", 7200)),
        default_response_mode=_choice("PPT_API_DEFAULT_RESPONSE_MODE", "async", {"sync", "async"}),
        default_callback_mode=_choice("PPT_API_DEFAULT_CALLBACK_MODE", "auto", {"auto", "defer", "none"}),
        redis_url=((os.getenv("PPT_REDIS_URL") or os.getenv("REDIS_URL") or "").strip() or None),
        redis_key_prefix=(os.getenv("PPT_REDIS_KEY_PREFIX", "ppt-deepseek") or "ppt-deepseek").strip().strip(":") or "ppt-deepseek",
        canvas_format=os.getenv("PPT_API_CANVAS_FORMAT", "ppt169").strip() or "ppt169",
        style=_choice("PPT_API_STYLE", "general", {"general", "consultant", "consultant-top"}),
        renderer=_choice("PPT_API_RENDERER", "deepseek", {"deepseek", "local"}),
        planner_provider=_choice("PPT_API_PLANNER_PROVIDER", "qwen", {"deepseek", "qwen"}),
        notes_provider=_choice("PPT_API_NOTES_PROVIDER", "qwen", {"deepseek", "qwen"}),
        qwen_base_url=os.getenv("PPT_API_QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip(),
        qwen_model=os.getenv("PPT_API_QWEN_MODEL", "qwen3.6-plus").strip() or "qwen3.6-plus",
        qwen_notes_model=((os.getenv("PPT_API_QWEN_NOTES_MODEL") or "").strip() or None),
        qwen_max_tokens=max(1024, _env_int("PPT_API_QWEN_MAX_TOKENS", 65536)),
        qwen_timeout=max(60, _env_int("PPT_API_QWEN_TIMEOUT", 900)),
        deepseek_base_url=os.getenv("PPT_API_DEEPSEEK_BASE_URL", "https://api.deepseek.com/anthropic").strip(),
        deepseek_model=os.getenv("PPT_API_DEEPSEEK_MODEL", "deepseek-v4-pro").strip() or "deepseek-v4-pro",
        svg_model=os.getenv("PPT_API_SVG_MODEL", "deepseek-v4-pro[1m]").strip() or "deepseek-v4-pro[1m]",
        svg_repair_model=os.getenv("PPT_API_SVG_REPAIR_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash",
        svg_timeout=max(60, _env_int("PPT_API_SVG_TIMEOUT", 1200)),
        svg_retries=max(0, _env_int("PPT_API_SVG_RETRIES", 1)),
        svg_workers=max(1, _env_int("PPT_API_SVG_WORKERS", 18)),
        svg_batch_size=max(1, _env_int("PPT_API_SVG_BATCH_SIZE", 3)),
        cache_prime=_env_bool("PPT_API_CACHE_PRIME", True),
        runner_start_stagger_enabled=_env_bool("PPT_API_RUNNER_START_STAGGER_ENABLED", True),
        runner_start_stagger_seconds=max(0.0, _env_float("PPT_API_RUNNER_START_STAGGER_SECONDS", 4.0)),
        runner_start_jitter_seconds=max(0.0, _env_float("PPT_API_RUNNER_START_JITTER_SECONDS", 12.0)),
        runner_start_stagger_scope=_choice("PPT_API_RUNNER_START_STAGGER_SCOPE", "global", {"global", "account"}),
        account_pool_file=((os.getenv("PPT_API_DEEPSEEK_ACCOUNT_POOL_FILE") or os.getenv("PPT_API_ACCOUNT_POOL_FILE") or "").strip() or None),
        account_pool_json=((os.getenv("PPT_API_DEEPSEEK_ACCOUNT_POOL_JSON") or os.getenv("PPT_API_ACCOUNT_POOL_JSON") or "").strip() or None),
        require_account_pool=_env_bool("PPT_API_REQUIRE_ACCOUNT_POOL", True),
        account_lease_timeout_seconds=max(1, _env_int("PPT_API_ACCOUNT_LEASE_TIMEOUT_SECONDS", 7200)),
        cos_secret_id=os.getenv("COS_SECRET_ID", "").strip(),
        cos_secret_key=os.getenv("COS_SECRET_KEY", "").strip(),
        cos_region=os.getenv("COS_REGION", "ap-shanghai").strip() or "ap-shanghai",
        cos_bucket=os.getenv("COS_BUCKET", "").strip(),
        report_callback_url=((os.getenv("REPORT_CALLBACK_URL") or os.getenv("REPORT_URL") or "").strip() or None),
        metrics_export_enabled=_env_bool("PPT_API_METRICS_EXPORT_ENABLED", True),
        metrics_export_dir=metrics_export_dir,
        metrics_export_interval_seconds=max(5, _env_int("PPT_API_METRICS_EXPORT_INTERVAL_SECONDS", 30)),
    )
