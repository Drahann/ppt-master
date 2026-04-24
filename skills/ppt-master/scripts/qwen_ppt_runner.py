#!/usr/bin/env python3
"""Automate PPT Master generation with Qwen Code CLI.

Usage:
    python3 skills/ppt-master/scripts/qwen_ppt_runner.py <request.json>
"""

from __future__ import annotations

import json
import io
import hashlib
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from difflib import get_close_matches
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_service.svg_scheduler import RedisSvgSchedulerStore as RedisSvgSchedulerStoreType

try:
    from config import REPO_ROOT, PROJECTS_DIR
    from project_manager import ProjectManager
except ImportError:
    TOOLS_DIR = Path(__file__).resolve().parent
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    from config import REPO_ROOT, PROJECTS_DIR  # type: ignore
    from project_manager import ProjectManager  # type: ignore

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from api_service.svg_scheduler import (
        RedisSvgSchedulerStore,
        SVG_TASK_FAILED,
        SVG_TASK_SUCCEEDED,
        SvgBatchTask,
        build_svg_scheduler_task_id,
        scheduler_enabled_from_env,
        svg_scheduler_owner_from_env,
    )
except Exception:  # pragma: no cover - fallback when api_service import is unavailable
    RedisSvgSchedulerStore = None  # type: ignore[assignment]
    SvgBatchTask = None  # type: ignore[assignment]
    build_svg_scheduler_task_id = None  # type: ignore[assignment]
    scheduler_enabled_from_env = None  # type: ignore[assignment]
    svg_scheduler_owner_from_env = None  # type: ignore[assignment]
    SVG_TASK_SUCCEEDED = "succeeded"
    SVG_TASK_FAILED = "failed"

try:
    from api_service.account_pool import AccountLease, RedisAccountPool, load_account_pool_entries
except Exception:  # pragma: no cover - runner can operate without the API package import
    AccountLease = None  # type: ignore[assignment]
    RedisAccountPool = None  # type: ignore[assignment]
    load_account_pool_entries = None  # type: ignore[assignment]


COMPLETION_SENTINEL_PREFIX = "PPT_RUN_COMPLETE:"
SPEC_COMPLETION_SENTINEL_PREFIX = "PPT_SPEC_COMPLETE:"
REVIEW_COMPLETION_SENTINEL_PREFIX = "PPT_SPEC_REVIEW_COMPLETE:"
SVG_BATCH_COMPLETION_SENTINEL_PREFIX = "PPT_SVG_BATCH_COMPLETE:"
NOTES_COMPLETION_SENTINEL_PREFIX = "PPT_NOTES_COMPLETE:"
DEFAULT_CANVAS_FORMAT = "ppt169"
DEFAULT_PROJECT_BASE_DIR = "projects"
DEFAULT_QWEN_MODEL = "qwen3.6-plus"
DEFAULT_REVIEW_MODEL = "qwen3.6-plus"
LANGUAGE_CONSISTENCY_RULE = (
    "- Language lock: Infer the source-document language from the received JSON/imported source markdown; "
    "all PPT-visible content, design_spec.md content, SVG text, and speaker notes must use that same language. "
    "Do not translate to another language unless the source explicitly requests translation."
)
DEFAULT_MAX_FOLLOW_UPS = 8
QWEN_CALL_TIMEOUT_SECONDS = 60 * 60
QWEN_SVG_BATCH_TURN_TIMEOUT_SECONDS = 30 * 60
DIRECT_NOTES_TIMEOUT_SECONDS = 10 * 60
DIRECT_NOTES_MAX_TOKENS = 12000
DIRECT_SPEC_TIMEOUT_SECONDS = 15 * 60
DIRECT_SPEC_MAX_TOKENS = 32000
SKILL_PACK_DIRNAME = "skill_packs"
QWEN_CHAT_ROOT = Path.home() / ".qwen" / "projects"
QWEN_DEBUG_ROOT = Path.home() / ".qwen" / "debug"
RUNNER_DIRNAME = "runner"
LOG_FILENAME = "runner.log"
USAGE_SUMMARY_FILENAME = "usage_summary.json"
LIVE_USAGE_FILENAME_SUFFIX = ".live_usage.json"
SVG_QUALITY_REPORT_FILENAME = "svg_quality_report.txt"
SVG_ANCHOR_CONTEXT_FILENAME = "svg_anchor_context.json"
SOURCE_IMAGE_REFERENCE_FILENAME = "source_image_reference.json"
QWEN_PROJECT_GUIDE_PATH = REPO_ROOT / "QWEN.md"
QWEN_SKILL_ROOT = REPO_ROOT / ".qwen" / "skills" / "ppt-master"
QWEN_SKILL_WRAPPER_PATH = QWEN_SKILL_ROOT / "SKILL.md"
QWEN_REPO_SKILL_PATH = QWEN_SKILL_ROOT / "references" / "repo_skill.md"
QWEN_STRATEGIST_REFERENCE_PATH = QWEN_SKILL_ROOT / "references" / "strategist.md"
QWEN_EXECUTOR_REFERENCE_PATH = QWEN_SKILL_ROOT / "references" / "executor-base.md"
QWEN_EXECUTOR_CONSULTANT_PATH = QWEN_SKILL_ROOT / "references" / "executor-consultant.md"
QWEN_EXECUTOR_GENERAL_PATH = QWEN_SKILL_ROOT / "references" / "executor-general.md"
QWEN_SHARED_STANDARDS_PATH = QWEN_SKILL_ROOT / "references" / "shared-standards.md"
QWEN_IMAGE_LAYOUT_REFERENCE_PATH = QWEN_SKILL_ROOT / "references" / "image-layout-spec.md"
SVG_DESIGN_COOKBOOK_PATH = QWEN_SKILL_ROOT / "references" / "svg_design_cookbook.md"
QWEN_DESIGN_SPEC_REFERENCE_PATH = QWEN_SKILL_ROOT / "templates" / "design_spec_reference.md"
QWEN_CHARTS_INDEX_PATH = QWEN_SKILL_ROOT / "templates" / "charts" / "charts_index.json"
QWEN_SPEC_REVIEW_SKILL_PATH = REPO_ROOT / ".qwen" / "skills" / "ppt-spec-review" / "SKILL.md"
# AI-read reference files now live under .qwen; runtime scripts/assets remain under skills/ppt-master.
CHARTS_INDEX_PATH = QWEN_CHARTS_INDEX_PATH
DESIGN_SPEC_REFERENCE_PATH = QWEN_DESIGN_SPEC_REFERENCE_PATH
STRATEGIST_REFERENCE_PATH = QWEN_STRATEGIST_REFERENCE_PATH
EXECUTOR_REFERENCE_PATH = QWEN_EXECUTOR_REFERENCE_PATH
EXECUTOR_CONSULTANT_PATH = QWEN_EXECUTOR_CONSULTANT_PATH
EXECUTOR_GENERAL_PATH = QWEN_EXECUTOR_GENERAL_PATH
SHARED_STANDARDS_PATH = QWEN_SHARED_STANDARDS_PATH
IMAGE_LAYOUT_REFERENCE_PATH = QWEN_IMAGE_LAYOUT_REFERENCE_PATH
ICON_LIBRARY_DIR = REPO_ROOT / "skills" / "ppt-master" / "templates" / "icons" / "chunk"
DEFAULT_ICON_LIBRARY = "chunk"
ICON_COVERAGE_RATIO = 0.75
ICON_COVERAGE_MIN_SLIDES = 12
COOKBOOK_REREAD_INTERVAL = 8
BATCH_SIZE = 6
BATCH_MODE_THRESHOLD = 15
DEFAULT_PARALLEL_BATCH_WORKERS = 3
DEFAULT_BATCH_PARTITION = "anchor_even"
RAMP_BATCH_SIZES = (2, 3, 4, 5, 6, 7, 8)
ANCHOR_BATCH_SIZE = 2
ANCHOR_EVEN_TARGET_GROUP_SIZE = 6
ANCHOR_EVEN_MAX_FOLLOWUP_GROUPS = 5
DEFAULT_LLM_SLOT_LIMITS = {
    "spec": 4,
    "svg": 10,
    "notes": 8,
    "postprocess": 4,
    "generic": 4,
}
LLM_SLOT_STALE_SECONDS = 6 * 60 * 60
LLM_SLOT_WAIT_TIMEOUT_SECONDS = 2 * 60 * 60
SVG_FAIR_SHARE_DELAY_SECONDS = 8
REDIS_CLIENT = None
REDIS_CLIENT_LOCK = Lock()
RUNNER_ACCOUNT_POOL = None
RUNNER_ACCOUNT_POOL_LOCK = Lock()
QWEN_TURN_START_LOCK = Lock()
QWEN_TURN_LAST_START: dict[str, float] = {}
BATCH_PARTITION_REPEAT_SENTINEL = "+"
QWEN_ALLOWED_TOOLS = (
    "edit",
    "write_file",
    "run_shell_command",
)
USAGE_SUMMARY_LOCK = Lock()

DEFAULT_RULES: dict[str, Any] = {
    "template_mode": "free",
    "include_cover": True,
    "include_ending": True,
    "include_toc": False,
    "include_section_headers": False,
    "content_density": "moderately_high",
    "faithful_to_source": True,
    "highlight_key_points": True,
    "pagination": {
        "default": "each_h2_one_slide",
        "expand_h2_titles": ["创新技术", "产业验证"],
        "expand_rule": "each_h3_one_slide_no_parent_h2_slide",
    },
}

RESOURCE_ONLY_H2_TITLES = {
    "相关图片信息",
    "图片信息",
    "相关图像信息",
    "参考图片",
    "图片资源",
    "图像资源",
}

DESIGN_SPEC_REQUIRED_HEADERS = (
    "## I. Project Information",
    "## II. Canvas Specification",
    "## III. Visual Theme",
    "## IV. Typography System",
    "## V. Layout Principles",
    "## VI. Icon Usage",
    "## VII. Visualization Reference List",
    "## VIII. Image Resource List",
    "## IX. Content Outline",
    "## X. Speaker Notes Requirements",
    "## XI. Technical Constraints Reminder",
)

GENERIC_CHART_TOKENS = {
    "visualization_type",
    "custom_layout",
}

REVIEW_REPORT_FILENAME = "spec_review_report.json"
REVIEW_INPUT_FILENAME = "spec_review_input.json"
SPEC_REPAIR_REPORT_FILENAME = "spec_repair_report.json"

REVIEW_FOCUS_SLIDES = (
    "市场定位",
    "推广模式",
    "商业模式",
    "财务规划",
    "盈利分析",
    "团队结构",
)

TEMPLATE_BLOCKING_PATTERNS = (
    "A) Use an existing template",
    "B) Free design",
    "B) No template",
    "Which approach would you prefer",
)

CONFIRMATION_BLOCKING_PATTERNS = (
    "Eight Confirmations",
    "confirm the design spec",
    "请确认",
    "请先确认",
    "确认设计规格",
    "八项确认",
)

@dataclass
class SlidePlanEntry:
    index: int
    filename: str
    heading: str
    kind: str
    source_h2: str | None
    source_h3: str | None
    absorb_parent_intro: bool = False

    @property
    def note_heading(self) -> str:
        return Path(self.filename).stem


@dataclass
class QwenCallResult:
    returncode: int
    stdout: str
    stderr: str
    usage: dict[str, Any] | None = None
    timed_out: bool = False


@dataclass
class SvgBudgetLease:
    lease_id: str
    estimated_worker_tpm: int
    estimated_tokens: int
    estimated_duration_seconds: int
    active_tpm_after: int
    budget_tpm: int
    completion_bucket_after: int
    completion_bucket_limit: int
    completion_bucket_key: str
    live_window_tpm_after: int = 0
    startup_reserve_tpm: int = 0
    admission_mode: str = "estimated"


@dataclass(frozen=True)
class PreparedSvgBatch:
    batch_index: int
    batch_plan: list[SlidePlanEntry]
    prompt_path: Path
    batch_slide_plan_path: Path
    prompt_text: str
    requires_anchor: bool = False


@dataclass
class RunOutput:
    job_id: str
    status: str
    project_path: str | None
    qwen_session_id: str | None
    native_pptx_path: str | None
    svg_pptx_path: str | None
    log_path: str | None
    error: str | None


class RunnerError(RuntimeError):
    """Raised when the runner cannot complete successfully."""


@dataclass
class MarkdownH3:
    title: str
    body_lines: list[str]


@dataclass
class MarkdownH2:
    title: str
    intro_lines: list[str]
    children: list[MarkdownH3]


@dataclass
class TurnUsageSummary:
    api_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    thoughts_tokens: int = 0
    total_tokens: int = 0
    tool_tokens: int = 0
    models: list[str] | None = None

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["models"] = sorted(set(self.models or []))
        return payload


@dataclass
class LiveUsageSnapshot:
    stage: str
    label: str
    session_id: str
    window_seconds: int
    poll_seconds: float
    log_interval_seconds: float
    cumulative: TurnUsageSummary
    rolling_tpm_60s: int = 0
    last_event_epoch: float | None = None
    observed_events: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "label": self.label,
            "session_id": self.session_id,
            "window_seconds": self.window_seconds,
            "poll_seconds": self.poll_seconds,
            "log_interval_seconds": self.log_interval_seconds,
            "rolling_tpm_60s": self.rolling_tpm_60s,
            "last_event_epoch": self.last_event_epoch,
            "observed_events": self.observed_events,
            "cumulative": self.cumulative.to_json(),
        }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RunnerError(f"Request file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"Invalid JSON in request file: {path} ({exc})") from exc


def read_json_value(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RunnerError(f"Request file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"Invalid JSON in request file: {path} ({exc})") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_slide_plan_entries(path: Path) -> list[SlidePlanEntry]:
    payload = read_json_value(path)
    if not isinstance(payload, list):
        raise RunnerError(f"Invalid slide plan payload: {path}")
    entries: list[SlidePlanEntry] = []
    for item in payload:
        if not isinstance(item, dict):
            raise RunnerError(f"Invalid slide plan entry in {path}: {item!r}")
        entries.append(SlidePlanEntry(**item))
    return entries


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_project_base_dir(request: dict[str, Any]) -> Path:
    base_dir = Path(request["project_base_dir"])
    if not base_dir.is_absolute():
        base_dir = REPO_ROOT / base_dir
    return base_dir


def ensure_clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_svg_directory(src_dir: Path, dst_dir: Path) -> None:
    ensure_clean_directory(dst_dir)
    for svg_path in sorted(src_dir.glob("*.svg")):
        copy_file(svg_path, dst_dir / svg_path.name)


def build_compact_skill_excerpt(path: Path) -> str:
    content = read_text(path)
    lines = content.splitlines()
    kept: list[str] = []
    in_code_block = False
    important_tokens = (
        "must",
        "must not",
        "do not",
        "don't",
        "never",
        "always",
        "only",
        "required",
        "forbidden",
        "exact",
        "lock",
        "theme",
        "icon",
        "chart",
        "svg",
        "notes",
        "title",
        "footer",
        "header",
        "canvas",
        "page",
        "layout",
        "review",
        "valid",
        "xml",
        "emoji",
        "cache",
    )

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue

        lower = stripped.lower()
        keep_line = False
        if stripped.startswith("#"):
            keep_line = True
        elif re.match(r"^[-*+]\s+", stripped):
            keep_line = True
        elif re.match(r"^\d+[.)]\s+", stripped):
            keep_line = True
        elif stripped.startswith("|") and stripped.endswith("|"):
            keep_line = True
        elif "`" in stripped:
            keep_line = True
        elif len(stripped) <= 180 and any(token in lower for token in important_tokens):
            keep_line = True

        if keep_line:
            kept.append(stripped)

    compact = "\n".join(kept).strip()
    if not compact:
        compact = "\n".join(lines[:200]).strip()
    return compact


def write_skill_pack(
    runner_dir: Path,
    pack_name: str,
    source_paths: list[Path],
    critical_rules: list[str] | None = None,
    compact: bool = True,
) -> tuple[Path, str]:
    skill_pack_dir = runner_dir / SKILL_PACK_DIRNAME
    skill_pack_dir.mkdir(parents=True, exist_ok=True)
    pack_path = skill_pack_dir / pack_name

    sections: list[str] = [
        f"# {pack_name}",
        "",
        (
            "This is a compact local skill pack generated to reduce repeated static-context reads."
            if compact
            else "This is a full local skill pack generated without compression for maximum SVG execution fidelity."
        ),
        "",
    ]
    if critical_rules:
        sections.extend(
            [
                "## Critical Rules",
                *[f"- {rule}" for rule in critical_rules],
                "",
            ]
        )
    for path in source_paths:
        sections.extend(
            [
                f"## Source: {path.name}",
                f"Path: {path}",
                "",
                build_compact_skill_excerpt(path) if compact else path.read_text(encoding="utf-8", errors="replace"),
                "",
            ]
        )

    pack_text = "\n".join(sections).strip() + "\n"
    pack_path.write_text(pack_text, encoding="utf-8")
    return pack_path, hash_text(pack_text)


def project_needs_image_layout_rules(project_path: Path) -> bool:
    image_suffixes = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".svg"}
    images_dir = project_path / "images"
    if images_dir.exists():
        for path in images_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in image_suffixes:
                return True

    design_spec_path = project_path / "design_spec.md"
    if not design_spec_path.exists():
        return False
    content = design_spec_path.read_text(encoding="utf-8", errors="replace")
    image_tokens = (
        "../images/",
        "/images/",
        "<image",
        "image resource",
        "图片资源",
        "图片引用",
        "image layout",
    )
    return any(token in content.lower() for token in image_tokens)


def write_executor_skill_pack(
    runner_dir: Path,
    project_path: Path,
    executor_style_path: Path,
    critical_rules: list[str],
) -> tuple[Path, str]:
    """Write the SVG executor pack.

    The cookbook is the quality anchor and remains full-text. Generic workflow
    docs are intentionally omitted from the SVG stage to reduce repeated CLI
    context without weakening visual rules.
    """
    skill_pack_dir = runner_dir / SKILL_PACK_DIRNAME
    skill_pack_dir.mkdir(parents=True, exist_ok=True)
    pack_path = skill_pack_dir / "executor_skill_pack.md"

    compact_sources: list[Path] = [
        QWEN_EXECUTOR_REFERENCE_PATH,
        executor_style_path,
        QWEN_SHARED_STANDARDS_PATH,
    ]
    if project_needs_image_layout_rules(project_path):
        compact_sources.append(QWEN_IMAGE_LAYOUT_REFERENCE_PATH)

    sections: list[str] = [
        "# executor_skill_pack.md",
        "",
        "This is a lean SVG-only executor pack. It keeps the SVG Design Cookbook in full and compresses or omits non-critical workflow context.",
        "",
        "## Context Policy",
        "- The full `svg_design_cookbook.md` below is the primary visual-quality reference.",
        "- Generic workflow files such as `AGENTS.md`, `QWEN.md`, `SKILL.md`, and `repo_skill.md` are intentionally not included in this SVG stage pack.",
        "- Do not read unrelated repository, archive, template, or historical project files unless a prompt explicitly names them.",
        "- Use `design_spec.md`, the current batch plan/digest, icon candidates, and `svg_anchor_context.json` as the deck-specific sources of truth.",
        "",
        "## Critical Rules",
        *[f"- {rule}" for rule in critical_rules],
        "",
    ]

    for path in compact_sources:
        sections.extend(
            [
                f"## Compact Source: {path.name}",
                f"Path: {path}",
                "",
                build_compact_skill_excerpt(path),
                "",
            ]
        )

    sections.extend(
        [
            f"## Full Source: {SVG_DESIGN_COOKBOOK_PATH.name}",
            f"Path: {SVG_DESIGN_COOKBOOK_PATH}",
            "",
            SVG_DESIGN_COOKBOOK_PATH.read_text(encoding="utf-8", errors="replace"),
            "",
        ]
    )

    pack_text = "\n".join(sections).strip() + "\n"
    pack_path.write_text(pack_text, encoding="utf-8")
    return pack_path, hash_text(pack_text)


def write_deterministic_review_report(
    project_path: Path,
    review_input_path: Path,
    review_report_path: Path,
    review_errors: list[str],
) -> None:
    review_payload = {
        "status": "passed" if not review_errors else "needs_ai_review",
        "summary": (
            "Deterministic review passed; skipped AI review to reduce cost."
            if not review_errors
            else "Deterministic review found issues; AI review is required."
        ),
        "issues_found": review_errors,
        "issues_fixed": [],
        "remaining_risks": [],
        "review_input_path": str(review_input_path),
        "design_spec_path": str(project_path / "design_spec.md"),
    }
    write_json(review_report_path, review_payload)


def is_resource_only_heading(title: str) -> bool:
    normalized = re.sub(r"\s+", "", title).strip()
    return normalized in RESOURCE_ONLY_H2_TITLES


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def collect_salient_lines(lines: list[str], limit: int = 8) -> list[str]:
    items: list[str] = []
    for raw in lines:
        text = normalize_line(raw)
        if not text:
            continue
        if text.startswith("#"):
            continue
        if text.startswith("```") or text.startswith("~~~"):
            continue
        if text in {"-", "*"}:
            continue
        text = re.sub(r"^[-*+]\s*", "", text)
        text = re.sub(r"^\d+[.)]\s*", "", text)
        if not text:
            continue
        if text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def extract_markdown_table_value(content: str, label: str) -> str | None:
    pattern = re.compile(
        rf"^\|\s*\*\*{re.escape(label)}\*\*\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return None
    value = match.group(1).strip()
    value = value.strip("`")
    return value or None


def extract_color_scheme(content: str) -> dict[str, str]:
    colors: dict[str, str] = {}
    pattern = re.compile(
        r"^\|\s*\*\*(.+?)\*\*\s*\|\s*`?(#[0-9A-Fa-f]{6})`?\s*\|",
        re.MULTILINE,
    )
    for role, value in pattern.findall(content):
        colors[role.strip()] = value.strip()
    return colors


def load_chart_catalog() -> dict[str, dict[str, Any]]:
    payload = read_json(CHARTS_INDEX_PATH)
    charts = payload.get("charts")
    if not isinstance(charts, dict):
        raise RunnerError(f"Invalid charts index file: {CHARTS_INDEX_PATH}")
    return charts


def load_chart_categories() -> dict[str, Any]:
    payload = read_json(CHARTS_INDEX_PATH)
    categories = payload.get("categories")
    if not isinstance(categories, dict):
        raise RunnerError(f"Invalid chart categories in: {CHARTS_INDEX_PATH}")
    return categories


def load_available_icons() -> set[str]:
    if not ICON_LIBRARY_DIR.exists():
        raise RunnerError(f"Icon library directory not found: {ICON_LIBRARY_DIR}")
    return {path.stem for path in ICON_LIBRARY_DIR.glob("*.svg")}


def contains_emoji(text: str) -> bool:
    return bool(
        re.search(
            "["
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FAFF"
            "\u2600-\u26FF"
            "\u2700-\u27BF"
            "]",
            text,
        )
    )

def ensure_qwen_available() -> None:
    try:
        resolve_qwen_launcher()
    except RunnerError:
        raise RunnerError("qwen CLI is not available in PATH")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sanitize_token(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value.strip())
    safe = safe.strip("._")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe or "job"


def is_valid_batch_partition(value: str | None) -> bool:
    partition = (value or "").strip().lower()
    if not partition:
        return False
    if partition in {"fixed", "ramp", "ramp_2_3_4_5_6_7_8", "anchor_even"}:
        return True
    candidate = partition[:-1] if partition.endswith(BATCH_PARTITION_REPEAT_SENTINEL) else partition
    parts = candidate.split("+")
    return bool(parts) and all(part.isdigit() and int(part) > 0 for part in parts)


def parse_numeric_batch_partition(partition: str) -> tuple[list[int], bool]:
    normalized = partition.strip().lower()
    repeat_last = normalized.endswith(BATCH_PARTITION_REPEAT_SENTINEL)
    if repeat_last:
        normalized = normalized[:-1]
    sizes = [int(item) for item in normalized.split("+") if item]
    if not sizes or any(size <= 0 for size in sizes):
        raise RunnerError(f"Invalid numeric batch_partition: {partition}")
    return sizes, repeat_last


def split_anchor_even_batch_sizes(total_pages: int) -> list[int]:
    if total_pages <= 0:
        return []
    if total_pages <= ANCHOR_BATCH_SIZE:
        return [total_pages]

    remaining = total_pages - ANCHOR_BATCH_SIZE
    followup_groups = max(1, math.ceil(remaining / ANCHOR_EVEN_TARGET_GROUP_SIZE))
    followup_groups = min(ANCHOR_EVEN_MAX_FOLLOWUP_GROUPS, followup_groups)

    base = remaining // followup_groups
    remainder = remaining % followup_groups
    sizes = [ANCHOR_BATCH_SIZE]
    for index in range(followup_groups):
        size = base + (1 if index < remainder else 0)
        if size > 0:
            sizes.append(size)
    return sizes


def append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_iso()}] {message}\n")


def safe_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed >= 0 else 0


def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def is_svg_batch_artifact(artifact_prefix: str) -> bool:
    return artifact_prefix.startswith("svg_batch_")


def qwen_turn_timeout_seconds(stage: str, artifact_prefix: str) -> int:
    if stage == "svg" and is_svg_batch_artifact(artifact_prefix):
        return env_int(
            "PPT_API_QWEN_SVG_BATCH_TURN_TIMEOUT_SECONDS",
            QWEN_SVG_BATCH_TURN_TIMEOUT_SECONDS,
            minimum=60,
        )
    return env_int("PPT_API_QWEN_CALL_TIMEOUT_SECONDS", QWEN_CALL_TIMEOUT_SECONDS, minimum=60)


def terminate_qwen_process(process: subprocess.Popen[str], log_path: Path, label: str) -> None:
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        return
    except Exception as exc:
        append_log(log_path, f"Failed to terminate timed-out qwen process for {label}: {exc}")
        try:
            process.kill()
        except Exception:
            pass


def llm_slot_dir() -> Path:
    raw = (os.getenv("PPT_API_LLM_SLOT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return REPO_ROOT / "tmp" / "llm-slots"


def llm_slot_limit(stage: str) -> int:
    normalized = stage if stage in DEFAULT_LLM_SLOT_LIMITS else "generic"
    env_names = {
        "spec": "PPT_API_LLM_SPEC_SLOTS",
        "svg": "PPT_API_LLM_SVG_SLOTS",
        "notes": "PPT_API_LLM_NOTES_SLOTS",
        "postprocess": "PPT_API_POSTPROCESS_SLOTS",
        "generic": "PPT_API_LLM_GENERIC_SLOTS",
    }
    static_limit = env_int(env_names[normalized], DEFAULT_LLM_SLOT_LIMITS[normalized], minimum=1)
    if normalized == "svg":
        return redis_dynamic_svg_limit(static_limit)
    return static_limit


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float, *, minimum: float | None = None, maximum: float | None = None) -> float:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = float(raw)
        except ValueError:
            value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def live_usage_enabled(stage: str) -> bool:
    if not env_bool("PPT_API_LIVE_USAGE_ENABLED", True):
        return False
    if stage == "svg":
        return True
    return env_bool("PPT_API_LIVE_USAGE_ALL_STAGES", False)


def live_usage_poll_seconds() -> float:
    return env_float("PPT_API_LIVE_USAGE_POLL_SECONDS", 10.0, minimum=1.0, maximum=60.0)


def live_usage_log_interval_seconds() -> float:
    return env_float("PPT_API_LIVE_USAGE_LOG_INTERVAL_SECONDS", 60.0, minimum=5.0, maximum=300.0)


def live_tpm_window_seconds() -> int:
    default_window = env_int("PPT_API_LLM_PACING_WINDOW_SECONDS", 60, minimum=5)
    return env_int("PPT_API_LIVE_TPM_WINDOW_SECONDS", default_window, minimum=5)


def live_tpm_admission_enabled(stage: str) -> bool:
    return stage == "svg" and env_bool("PPT_API_LIVE_TPM_ADMISSION_ENABLED", True)


def live_tpm_bypass_completion_guard(stage: str) -> bool:
    return stage == "svg" and env_bool("PPT_API_SVG_LIVE_TPM_BYPASS_COMPLETION_GUARD", True)


def live_tpm_startup_reserve_seconds(stage: str) -> float:
    if stage != "svg":
        return env_float("PPT_API_LIVE_TPM_STARTUP_RESERVE_SECONDS", 10.0, minimum=1.0, maximum=60.0)
    return env_float("PPT_API_SVG_LIVE_TPM_STARTUP_RESERVE_SECONDS", 15.0, minimum=1.0, maximum=60.0)


def redis_url() -> str | None:
    return ((os.getenv("PPT_REDIS_URL") or os.getenv("REDIS_URL") or "").strip() or None)


def redis_key_prefix() -> str:
    return (os.getenv("PPT_REDIS_KEY_PREFIX", "ppt") or "ppt").strip().strip(":") or "ppt"


def redis_key(suffix: str) -> str:
    return f"{redis_key_prefix()}:{suffix}"


def scheduler_owner_key() -> str:
    if svg_scheduler_owner_from_env is not None:
        return str(svg_scheduler_owner_from_env())
    raw = os.getenv("PPT_API_SVG_SCHEDULER_OWNER") or os.getenv("PPT_SERVER_ID")
    return (raw or "").strip() or socket.gethostname()


def get_runner_redis_client(log_path: Path | None = None):
    global REDIS_CLIENT
    url = redis_url()
    if not url:
        return None
    with REDIS_CLIENT_LOCK:
        if REDIS_CLIENT is not None:
            return REDIS_CLIENT
        try:
            import redis

            client = redis.Redis.from_url(url, decode_responses=True)
            client.ping()
            REDIS_CLIENT = client
            return REDIS_CLIENT
        except Exception as exc:
            if log_path is not None:
                append_log(log_path, f"Redis unavailable for runner scheduling; falling back to file slots: {exc}")
            return None


def centralized_svg_scheduler_enabled(log_path: Path | None = None) -> bool:
    if scheduler_enabled_from_env is None or RedisSvgSchedulerStore is None:
        return False
    if not scheduler_enabled_from_env():
        return False
    return get_runner_redis_client(log_path) is not None


def get_svg_scheduler_store(log_path: Path | None = None) -> RedisSvgSchedulerStoreType | None:
    if RedisSvgSchedulerStore is None:
        return None
    client = get_runner_redis_client(log_path)
    if client is None:
        return None
    return RedisSvgSchedulerStore(client, key_prefix=redis_key_prefix())


def get_runner_account_pool(log_path: Path | None = None):
    global RUNNER_ACCOUNT_POOL
    if RedisAccountPool is None or load_account_pool_entries is None:
        return None
    client = get_runner_redis_client(log_path)
    if client is None:
        return None
    try:
        accounts = load_account_pool_entries()
    except Exception as exc:
        if log_path is not None:
            append_log(log_path, f"Qwen account pool unavailable in runner: {exc}")
        return None
    if not accounts:
        return None
    with RUNNER_ACCOUNT_POOL_LOCK:
        if RUNNER_ACCOUNT_POOL is None:
            RUNNER_ACCOUNT_POOL = RedisAccountPool(client, accounts, key_prefix=redis_key_prefix())
        else:
            RUNNER_ACCOUNT_POOL.sync_accounts()
        return RUNNER_ACCOUNT_POOL


def redis_dynamic_svg_limit(default_limit: int) -> int:
    budget_tpm = env_int("PPT_API_LLM_BUDGET_TPM", 0, minimum=0)
    if budget_tpm <= 0:
        return default_limit
    client = get_runner_redis_client()
    if client is None:
        return default_limit
    try:
        observed_tpm = float(client.get(redis_key("llm:ewma:svg:tpm")) or 0)
    except Exception:
        return default_limit
    if observed_tpm <= 0:
        return default_limit
    utilization = env_float("PPT_API_LLM_TARGET_UTILIZATION", 0.75, minimum=0.1, maximum=1.0)
    hard_max = env_int("PPT_API_LLM_HARD_MAX_SVG_CONCURRENCY", default_limit, minimum=1)
    min_limit = env_int("PPT_API_LLM_MIN_SVG_CONCURRENCY", 1, minimum=1)
    calculated = math.floor((budget_tpm * utilization) / observed_tpm)
    return max(min_limit, min(hard_max, calculated))


def redis_svg_worker_tpm_estimate(client=None) -> int:
    client = client or get_runner_redis_client()
    default_worker_tpm = env_int("PPT_API_LLM_DEFAULT_SVG_WORKER_TPM", 150000, minimum=1)
    observed_worker_tpm = 0.0
    if client is not None:
        try:
            observed_worker_tpm = float(client.get(redis_key("llm:ewma:svg:tpm")) or 0)
        except Exception:
            observed_worker_tpm = 0.0
    worker_tpm = observed_worker_tpm if observed_worker_tpm > 0 else float(default_worker_tpm)
    safety_factor = env_float("PPT_API_LLM_PACING_SAFETY_FACTOR", 1.15, minimum=1.0, maximum=3.0)
    return max(1, math.ceil(worker_tpm * safety_factor))


def redis_svg_duration_estimate(client=None) -> int:
    client = client or get_runner_redis_client()
    default_seconds = env_int("PPT_API_LLM_DEFAULT_SVG_DURATION_SECONDS", 600, minimum=1)
    observed_seconds = 0.0
    if client is not None:
        try:
            observed_seconds = float(client.get(redis_key("llm:ewma:svg:duration_seconds")) or 0)
        except Exception:
            observed_seconds = 0.0
    return max(1, math.ceil(observed_seconds if observed_seconds > 0 else default_seconds))


def redis_svg_turn_token_estimate(client=None, *, worker_tpm: int | None = None, duration_seconds: int | None = None) -> int:
    client = client or get_runner_redis_client()
    observed_tokens = 0.0
    if client is not None:
        try:
            observed_tokens = float(client.get(redis_key("llm:ewma:svg:tokens")) or 0)
        except Exception:
            observed_tokens = 0.0
    if observed_tokens > 0:
        return max(1, math.ceil(observed_tokens))
    worker_tpm = worker_tpm if worker_tpm is not None else redis_svg_worker_tpm_estimate(client)
    duration_seconds = duration_seconds if duration_seconds is not None else redis_svg_duration_estimate(client)
    return max(1, math.ceil(worker_tpm * (duration_seconds / 60)))


def redis_stage_token_estimate(stage: str, client=None, *, window_seconds: int = 60) -> int:
    client = client or get_runner_redis_client()
    env_name = {
        "svg": "PPT_API_LLM_DEFAULT_SVG_RESERVE_TOKENS",
        "spec": "PPT_API_LLM_DEFAULT_SPEC_RESERVE_TOKENS",
        "notes": "PPT_API_LLM_DEFAULT_NOTES_RESERVE_TOKENS",
    }.get(stage, "PPT_API_LLM_DEFAULT_RESERVE_TOKENS")
    default_tokens = env_int(env_name, 700000 if stage == "svg" else 100000, minimum=1)
    safety_factor = env_float("PPT_API_LLM_PACING_SAFETY_FACTOR", 1.15, minimum=1.0, maximum=3.0)
    if stage == "svg" and env_bool("PPT_API_LLM_PACING_USE_WORKER_TPM", True):
        worker_tpm = redis_svg_worker_tpm_estimate(client)
        window_factor = max(window_seconds, 1) / 60
        return max(1, math.ceil(worker_tpm * window_factor))
    if client is None:
        return max(1, math.ceil(default_tokens * safety_factor))
    try:
        observed = float(client.get(redis_key(f"llm:ewma:{stage}:tokens")) or 0)
    except Exception:
        return max(1, math.ceil(default_tokens * safety_factor))
    if observed <= 0:
        return max(1, math.ceil(default_tokens * safety_factor))
    return max(1, math.ceil(observed * safety_factor))


def qwen_account_pool_stage_reserve_tpm(stage: str, client=None) -> int:
    normalized = stage if stage in {"svg", "spec", "notes"} else "generic"
    stage_key = normalized.upper()
    stage_override = env_int(f"PPT_API_QWEN_ACCOUNT_POOL_{stage_key}_STARTUP_RESERVE_TPM", 0, minimum=0)
    if stage_override > 0:
        return stage_override
    global_override = env_int("PPT_API_QWEN_ACCOUNT_POOL_STARTUP_RESERVE_TPM", 0, minimum=0)
    if global_override > 0:
        return global_override
    client = client or get_runner_redis_client()
    if normalized == "svg":
        reserve_seconds = env_float(
            "PPT_API_QWEN_ACCOUNT_POOL_SVG_STARTUP_RESERVE_SECONDS",
            env_float("PPT_API_SVG_LIVE_TPM_STARTUP_RESERVE_SECONDS", 15.0, minimum=1.0, maximum=60.0),
            minimum=1.0,
            maximum=60.0,
        )
        return max(1, math.ceil(redis_svg_worker_tpm_estimate(client) * (reserve_seconds / 60.0)))
    return redis_stage_token_estimate(normalized, client, window_seconds=live_tpm_window_seconds())


def acquire_runner_account_lease(
    *,
    stage: str,
    label: str,
    runner_dir: Path,
    log_path: Path | None = None,
) -> tuple[Any | None, Any | None]:
    pool = get_runner_account_pool(log_path)
    if pool is None or not getattr(pool, "configured", False):
        return None, None

    client = get_runner_redis_client(log_path)
    reserve_tpm = qwen_account_pool_stage_reserve_tpm(stage, client)
    wait_timeout = env_int("PPT_API_QWEN_ACCOUNT_POOL_WAIT_TIMEOUT_SECONDS", LLM_SLOT_WAIT_TIMEOUT_SECONDS, minimum=60)
    retry_seconds = env_float("PPT_API_QWEN_ACCOUNT_POOL_RETRY_SECONDS", 2.0, minimum=0.2, maximum=30.0)
    started = time.time()
    last_wait_log = 0.0

    while True:
        lease = pool.acquire(
            label=f"{stage}:{label}",
            owner_task_id=label,
            worker_request_path=str(runner_dir),
            estimated_tokens=reserve_tpm,
            reserved_tpm=reserve_tpm,
            stage=stage,
        )
        if lease is not None:
            if log_path is not None:
                append_log(
                    log_path,
                    f"Acquired Qwen account lease for {stage}: account_id={lease.account_id} "
                    f"reserve_tpm={reserve_tpm} label={label}",
                )
            return pool, lease

        if time.time() - started > wait_timeout:
            raise RunnerError(f"Timed out waiting for Qwen account pool after {wait_timeout}s: stage={stage} label={label}")
        if log_path is not None and time.time() - last_wait_log >= 30:
            append_log(
                log_path,
                f"Waiting for Qwen account pool: stage={stage} reserve_tpm={reserve_tpm} label={label}",
            )
            last_wait_log = time.time()
        time.sleep(retry_seconds)


def wait_for_redis_tpm_budget(client, stage: str, *, label: str, log_path: Path | None = None) -> None:
    if not env_bool("PPT_API_LLM_TPM_PACING_ENABLED", True):
        return
    if stage != "svg" and not env_bool("PPT_API_LLM_TPM_PACING_ALL_STAGES", False):
        return

    budget_tpm = env_int("PPT_API_LLM_BUDGET_TPM", 0, minimum=0)
    if budget_tpm <= 0:
        return
    utilization = env_float("PPT_API_LLM_TARGET_UTILIZATION", 0.75, minimum=0.1, maximum=1.0)
    window_seconds = env_int("PPT_API_LLM_PACING_WINDOW_SECONDS", 60, minimum=5)
    budget_window = max(1, int(budget_tpm * utilization * (window_seconds / 60)))
    reserve_tokens = redis_stage_token_estimate(stage, client, window_seconds=window_seconds)
    reserve_tokens = min(reserve_tokens, budget_window)
    pacing_key = redis_key(f"llm:pacing:{stage}")
    wait_timeout = env_int("PPT_API_LLM_SLOT_WAIT_TIMEOUT_SECONDS", LLM_SLOT_WAIT_TIMEOUT_SECONDS, minimum=60)
    started = time.time()
    last_wait_log = 0.0

    reserve_script = """
    redis.call('zremrangebyscore', KEYS[1], '-inf', ARGV[2])
    local members = redis.call('zrange', KEYS[1], 0, -1)
    local total = 0
    for _, member in ipairs(members) do
      local token_text = string.match(member, '^(%d+)|')
      if token_text then
        total = total + tonumber(token_text)
      end
    end
    local estimate = tonumber(ARGV[4])
    local budget = tonumber(ARGV[3])
    if total + estimate <= budget then
      redis.call('zadd', KEYS[1], ARGV[1], ARGV[5])
      redis.call('expire', KEYS[1], tonumber(ARGV[6]) * 2)
      return {1, total + estimate, budget}
    end
    return {0, total, budget}
    """

    while True:
        now = time.time()
        cutoff = now - window_seconds
        member = f"{reserve_tokens}|{os.getpid()}|{uuid.uuid4().hex}"
        try:
            result = client.eval(
                reserve_script,
                1,
                pacing_key,
                f"{now:.6f}",
                f"{cutoff:.6f}",
                str(budget_window),
                str(reserve_tokens),
                member,
                str(window_seconds),
            )
        except Exception as exc:
            if log_path is not None:
                append_log(log_path, f"Redis TPM pacing unavailable for {stage}; continuing without pacing: {exc}")
            return

        allowed = bool(result and int(result[0]) == 1)
        current_total = int(result[1]) if result and len(result) > 1 else 0
        if allowed:
            if log_path is not None:
                append_log(
                    log_path,
                    f"Reserved Redis TPM budget for {stage}: reserve={reserve_tokens} "
                    f"window_used={current_total}/{budget_window} label={label}",
                )
            return

        if time.time() - started > wait_timeout:
            raise RunnerError(
                f"Timed out waiting for Redis TPM pacing after {wait_timeout}s: stage={stage} label={label}"
            )
        if log_path is not None and time.time() - last_wait_log >= 30:
            append_log(
                log_path,
                f"Waiting for Redis TPM pacing: stage={stage} "
                f"used={current_total}/{budget_window} reserve={reserve_tokens} label={label}",
            )
            last_wait_log = time.time()
        time.sleep(2)


@contextmanager
def acquire_svg_budget_lease(
    stage: str,
    *,
    label: str,
    runner_dir: Path,
    log_path: Path | None = None,
):
    if stage != "svg" or not env_bool("PPT_API_SVG_BUDGET_LEASE_ENABLED", True):
        yield None
        return

    client = get_runner_redis_client(log_path)
    if client is None:
        yield None
        return

    budget_tpm = env_int("PPT_API_LLM_BUDGET_TPM", 0, minimum=0)
    if budget_tpm <= 0:
        yield None
        return
    utilization = env_float("PPT_API_LLM_TARGET_UTILIZATION", 0.75, minimum=0.1, maximum=1.0)
    active_budget = max(1, int(budget_tpm * utilization))
    completion_utilization = env_float("PPT_API_SVG_COMPLETION_BUCKET_UTILIZATION", 1.0, minimum=0.1, maximum=2.0)
    completion_budget = max(1, int(budget_tpm * completion_utilization))
    completion_guard_enabled = env_bool("PPT_API_SVG_COMPLETION_GUARD_ENABLED", True)
    worker_tpm = redis_svg_worker_tpm_estimate(client)
    live_admission_enabled = live_tpm_admission_enabled(stage)
    completion_guard_bypassed = live_tpm_bypass_completion_guard(stage) if live_admission_enabled else False
    live_window_seconds = live_tpm_window_seconds()
    startup_reserve_tpm = max(1, math.ceil(worker_tpm * (live_tpm_startup_reserve_seconds(stage) / 60.0)))
    duration_seconds = redis_svg_duration_estimate(client)
    estimated_tokens = redis_svg_turn_token_estimate(
        client,
        worker_tpm=worker_tpm,
        duration_seconds=duration_seconds,
    )
    ttl_seconds = max(
        env_int("PPT_API_SVG_BUDGET_LEASE_TTL_SECONDS", 3600, minimum=60),
        duration_seconds * 3,
    )
    wait_timeout = env_int("PPT_API_SVG_BUDGET_LEASE_WAIT_TIMEOUT_SECONDS", LLM_SLOT_WAIT_TIMEOUT_SECONDS, minimum=60)
    retry_seconds = env_float("PPT_API_SVG_BUDGET_LEASE_RETRY_SECONDS", 2.0, minimum=0.2, maximum=30.0)
    started = time.time()
    last_wait_log = 0.0
    lease_id: str | None = None
    lease: SvgBudgetLease | None = None

    acquire_script = """
    local now = tonumber(ARGV[1])
    local lease_id = ARGV[2]
    local label = ARGV[3]
    local runner_dir = ARGV[4]
    local estimated_tpm = tonumber(ARGV[5])
    local estimated_tokens = tonumber(ARGV[6])
    local estimated_duration = tonumber(ARGV[7])
    local active_budget = tonumber(ARGV[8])
    local completion_budget = tonumber(ARGV[9])
    local ttl = tonumber(ARGV[10])
    local completion_enabled = tonumber(ARGV[11])
    local live_window_seconds = tonumber(ARGV[12])
    local startup_reserve = tonumber(ARGV[13])
    local live_enabled = tonumber(ARGV[14])
    local completion_bypass = tonumber(ARGV[15])
    local completion_bucket_epoch = tostring(math.floor((now + estimated_duration) / 60) * 60)
    local completion_key = KEYS[4] .. completion_bucket_epoch

    local expired = redis.call('zrangebyscore', KEYS[1], '-inf', now)
    for _, expired_id in ipairs(expired) do
      redis.call('del', KEYS[2] .. expired_id)
    end
    if #expired > 0 then
      redis.call('zremrangebyscore', KEYS[1], '-inf', now)
    end

    local active_ids = redis.call('zrangebyscore', KEYS[1], now, '+inf')
    local active_tpm = 0
    for _, active_id in ipairs(active_ids) do
      local tpm_text = redis.call('hget', KEYS[2] .. active_id, 'estimated_worker_tpm')
      if tpm_text then
        active_tpm = active_tpm + tonumber(tpm_text)
      end
    end

    local live_total = 0
    if live_enabled == 1 then
      redis.call('zremrangebyscore', KEYS[6], '-inf', now - live_window_seconds)
      local live_members = redis.call('zrange', KEYS[6], 0, -1)
      for _, live_member in ipairs(live_members) do
        local token_text = string.match(live_member, '^(%d+)|')
        if token_text then
          live_total = live_total + tonumber(token_text)
        end
      end
    end

    local completion_current = 0
    if completion_enabled == 1 then
      completion_current = tonumber(redis.call('get', completion_key) or '0')
    end

    local accounted_tpm = active_tpm
    if live_enabled == 1 and live_total > accounted_tpm then
      accounted_tpm = live_total
    end

    local admission_allowed = 0
    if live_enabled == 1 then
      if accounted_tpm + startup_reserve <= active_budget then
        admission_allowed = 1
      end
    elseif active_tpm + estimated_tpm <= active_budget then
      admission_allowed = 1
    end

    local completion_allowed = 1
    if completion_enabled == 1 and completion_bypass == 0 and completion_current + estimated_tokens > completion_budget then
      completion_allowed = 0
    end

    if admission_allowed == 1 and completion_allowed == 1 then
      redis.call('hset', KEYS[2] .. lease_id,
        'lease_id', lease_id,
        'label', label,
        'runner_dir', runner_dir,
        'estimated_worker_tpm', estimated_tpm,
        'estimated_tokens', estimated_tokens,
        'estimated_duration_seconds', estimated_duration,
        'live_window_tpm_after', accounted_tpm + startup_reserve,
        'live_window_tpm_before', live_total,
        'startup_reserve_tpm', startup_reserve,
        'admission_mode', live_enabled == 1 and 'live' or 'estimated',
        'created_at', now,
        'expires_at', now + ttl,
        'completion_bucket_epoch', completion_bucket_epoch,
        'completion_key', completion_key
      )
      redis.call('expire', KEYS[2] .. lease_id, ttl)
      redis.call('zadd', KEYS[1], now + ttl, lease_id)
      redis.call('expire', KEYS[1], ttl)
      if completion_enabled == 1 and completion_bypass == 0 then
        redis.call('incrby', completion_key, estimated_tokens)
        redis.call('expire', completion_key, math.max(ttl, estimated_duration + 180))
        completion_current = completion_current + estimated_tokens
      end
      redis.call('incr', KEYS[3])
      return {1, active_tpm + estimated_tpm, active_budget, completion_current, completion_budget, completion_key, accounted_tpm + startup_reserve, live_total, startup_reserve}
    end
    redis.call('incr', KEYS[5])
    return {0, active_tpm, active_budget, completion_current, completion_budget, completion_key, accounted_tpm, live_total, startup_reserve}
    """

    release_script = """
    redis.call('zrem', KEYS[1], ARGV[1])
    return redis.call('del', KEYS[2] .. ARGV[1])
    """

    try:
        while lease is None:
            lease_id = f"{os.getpid()}:{uuid.uuid4().hex}"
            now = time.time()
            try:
                result = client.eval(
                    acquire_script,
                    6,
                    redis_key("svg:budget:leases"),
                    redis_key("svg:budget:lease:"),
                    redis_key("svg:budget:granted_starts"),
                    redis_key("svg:budget:completion:"),
                    redis_key("svg:budget:denied_starts"),
                    redis_live_stage_key(stage),
                    f"{now:.6f}",
                    lease_id,
                    label,
                    str(runner_dir),
                    str(worker_tpm),
                    str(estimated_tokens),
                    str(duration_seconds),
                    str(active_budget),
                    str(completion_budget),
                    str(ttl_seconds),
                    "1" if completion_guard_enabled else "0",
                    str(live_window_seconds),
                    str(startup_reserve_tpm),
                    "1" if live_admission_enabled else "0",
                    "1" if completion_guard_bypassed else "0",
                )
            except Exception as exc:
                if log_path is not None:
                    append_log(log_path, f"Redis SVG budget lease unavailable; falling back to legacy pacing: {exc}")
                yield None
                return

            allowed = bool(result and int(result[0]) == 1)
            active_tpm_after = int(result[1]) if result and len(result) > 1 else 0
            budget_after = int(result[2]) if result and len(result) > 2 else active_budget
            completion_after = int(result[3]) if result and len(result) > 3 else 0
            completion_limit = int(result[4]) if result and len(result) > 4 else completion_budget
            completion_key = str(result[5]) if result and len(result) > 5 else ""
            live_window_after = int(result[6]) if result and len(result) > 6 else 0
            live_window_before = int(result[7]) if result and len(result) > 7 else 0
            startup_reserve_after = int(result[8]) if result and len(result) > 8 else startup_reserve_tpm
            if allowed:
                lease = SvgBudgetLease(
                    lease_id=lease_id,
                    estimated_worker_tpm=worker_tpm,
                    estimated_tokens=estimated_tokens,
                    estimated_duration_seconds=duration_seconds,
                    active_tpm_after=active_tpm_after,
                    budget_tpm=budget_after,
                    completion_bucket_after=completion_after,
                    completion_bucket_limit=completion_limit,
                    completion_bucket_key=completion_key,
                    live_window_tpm_after=live_window_after,
                    startup_reserve_tpm=startup_reserve_after,
                    admission_mode="live" if live_admission_enabled else "estimated",
                )
                if log_path is not None:
                    append_log(
                        log_path,
                        "Acquired Redis SVG budget lease: "
                        f"lease={lease_id} tpm={worker_tpm} active={active_tpm_after}/{budget_after} "
                        f"live={live_window_before}->{live_window_after}/{budget_after} "
                        f"reserve={startup_reserve_after} mode={lease.admission_mode} "
                        f"tokens={estimated_tokens} duration={duration_seconds}s "
                        f"completion={completion_after}/{completion_limit} label={label}",
                    )
                break

            if time.time() - started > wait_timeout:
                raise RunnerError(
                    f"Timed out waiting for Redis SVG budget lease after {wait_timeout}s: {label}"
                )
            if log_path is not None and time.time() - last_wait_log >= 30:
                append_log(
                    log_path,
                    "Waiting for Redis SVG budget lease: "
                    f"active={active_tpm_after}/{budget_after} live={live_window_before}/{budget_after} "
                    f"reserve={startup_reserve_after} mode={'live' if live_admission_enabled else 'estimated'} "
                    f"completion={completion_after}/{completion_limit} "
                    f"estimate_tpm={worker_tpm} estimate_tokens={estimated_tokens} label={label}",
                )
                last_wait_log = time.time()
            time.sleep(retry_seconds)

        yield lease
    finally:
        if lease is not None:
            try:
                client.eval(
                    release_script,
                    2,
                    redis_key("svg:budget:leases"),
                    redis_key("svg:budget:lease:"),
                    lease.lease_id,
                )
                if log_path is not None:
                    append_log(log_path, f"Released Redis SVG budget lease: lease={lease.lease_id} label={label}")
            except Exception:
                pass


def qwen_turn_start_stagger_seconds(stage: str) -> float:
    if stage == "svg":
        fallback = env_float("PPT_API_QWEN_START_STAGGER_SECONDS", 0.0, minimum=0.0)
        return env_float("PPT_API_SVG_QWEN_START_STAGGER_SECONDS", fallback, minimum=0.0)
    if stage == "spec":
        fallback = env_float("PPT_API_QWEN_START_STAGGER_SECONDS", 0.0, minimum=0.0)
        return env_float("PPT_API_SPEC_QWEN_START_STAGGER_SECONDS", fallback, minimum=0.0)
    if stage == "notes":
        fallback = env_float("PPT_API_QWEN_START_STAGGER_SECONDS", 0.0, minimum=0.0)
        return env_float("PPT_API_NOTES_QWEN_START_STAGGER_SECONDS", fallback, minimum=0.0)
    if env_bool("PPT_API_QWEN_START_STAGGER_ALL_STAGES", False):
        return env_float("PPT_API_QWEN_START_STAGGER_SECONDS", 0.0, minimum=0.0)
    return 0.0


def redis_start_stagger_enabled(stage: str) -> bool:
    if not env_bool("PPT_API_QWEN_GLOBAL_START_STAGGER_ENABLED", True):
        return False
    if stage == "svg":
        return True
    return env_bool("PPT_API_QWEN_GLOBAL_START_STAGGER_ALL_STAGES", True)


def wait_for_redis_qwen_start(stage: str, *, label: str, delay_seconds: float, log_path: Path | None = None) -> bool:
    client = get_runner_redis_client(log_path)
    if client is None:
        return False
    key_stage = stage if env_bool("PPT_API_QWEN_START_STAGGER_PER_STAGE", True) else "global"
    last_key = redis_key(f"llm:start_stagger:{key_stage}:next_at")
    lock_key = redis_key(f"llm:start_stagger:{key_stage}:lock")
    token = f"{os.getpid()}:{uuid.uuid4().hex}"
    timeout_seconds = env_float("PPT_API_QWEN_START_STAGGER_LOCK_TIMEOUT_SECONDS", 10.0, minimum=1.0, maximum=60.0)
    started = time.time()
    scheduled_start = 0.0

    while time.time() - started <= timeout_seconds:
        try:
            if client.set(lock_key, token, nx=True, ex=5):
                try:
                    now = time.time()
                    last_start = float(client.get(last_key) or 0.0)
                    scheduled_start = max(now, last_start + delay_seconds)
                    client.set(last_key, f"{scheduled_start:.6f}", ex=max(60, int(delay_seconds * 120)))
                    break
                finally:
                    try:
                        if client.get(lock_key) == token:
                            client.delete(lock_key)
                    except Exception:
                        pass
        except Exception as exc:
            if log_path is not None:
                append_log(log_path, f"Redis qwen start stagger unavailable for {stage}; falling back to local stagger: {exc}")
            return False
        time.sleep(0.05)

    if scheduled_start <= 0:
        return False

    wait_seconds = max(0.0, scheduled_start - time.time())
    if wait_seconds > 0:
        if log_path is not None:
            append_log(
                log_path,
                f"Redis qwen start stagger for {stage}: waiting {wait_seconds:.1f}s "
                f"(delay={delay_seconds:.1f}s label={label})",
            )
        time.sleep(wait_seconds)
    return True


def wait_for_local_qwen_start(stage: str, *, label: str, log_path: Path | None = None) -> None:
    delay_seconds = qwen_turn_start_stagger_seconds(stage)
    if delay_seconds <= 0:
        return
    if redis_start_stagger_enabled(stage) and wait_for_redis_qwen_start(
        stage,
        label=label,
        delay_seconds=delay_seconds,
        log_path=log_path,
    ):
        return
    key = stage if env_bool("PPT_API_QWEN_START_STAGGER_PER_STAGE", True) else "global"
    with QWEN_TURN_START_LOCK:
        now = time.time()
        last_start = QWEN_TURN_LAST_START.get(key, 0.0)
        wait_seconds = max(0.0, last_start + delay_seconds - now)
        if wait_seconds > 0:
            if log_path is not None:
                append_log(
                    log_path,
                    f"Local qwen start stagger for {stage}: waiting {wait_seconds:.1f}s "
                    f"(delay={delay_seconds:.1f}s label={label})",
                )
            time.sleep(wait_seconds)
        QWEN_TURN_LAST_START[key] = time.time()


def wait_for_qwen_repair_turn_backoff(stage: str, *, label: str, turn_index: int, log_path: Path | None = None) -> None:
    if turn_index <= 1:
        return
    stage_key = stage.upper()
    delay_seconds = env_float(
        f"PPT_API_{stage_key}_QWEN_REPAIR_TURN_BACKOFF_SECONDS",
        env_float("PPT_API_QWEN_REPAIR_TURN_BACKOFF_SECONDS", 0.0, minimum=0.0),
        minimum=0.0,
    )
    if delay_seconds <= 0:
        return
    if log_path is not None:
        append_log(log_path, f"Qwen repair turn backoff for {stage}: waiting {delay_seconds:.1f}s label={label}")
    time.sleep(delay_seconds)


def stable_delay_seconds(label: str, max_seconds: int) -> int:
    if max_seconds <= 0:
        return 0
    digest = hashlib.sha256(label.encode("utf-8", errors="replace")).hexdigest()
    return int(digest[:8], 16) % (max_seconds + 1)


def wait_for_svg_start_jitter(stage: str, *, label: str, log_path: Path | None = None) -> None:
    if stage != "svg":
        return
    max_seconds = env_int("PPT_API_SVG_START_JITTER_SECONDS", 0, minimum=0)
    delay_seconds = stable_delay_seconds(label, max_seconds)
    if delay_seconds <= 0:
        return
    if log_path is not None:
        append_log(
            log_path,
            f"SVG start jitter for {label}: waiting {delay_seconds}s (max={max_seconds}s)",
        )
    time.sleep(delay_seconds)


def svg_job_dir() -> Path:
    return llm_slot_dir() / "svg_jobs"


def cleanup_stale_job_leases(job_dir: Path, stale_seconds: int) -> None:
    now = time.time()
    for job_file in job_dir.glob("*.job"):
        try:
            payload = json.loads(job_file.read_text(encoding="utf-8"))
        except Exception:
            try:
                if now - job_file.stat().st_mtime > 10:
                    job_file.unlink()
            except OSError:
                pass
            continue

        created_at = float(payload.get("created_at") or 0)
        pid = safe_int(payload.get("pid"))
        if (created_at and now - created_at > stale_seconds) or (pid and not pid_is_alive(pid)):
            try:
                job_file.unlink()
            except OSError:
                pass


def active_svg_job_count() -> int:
    jobs_dir = svg_job_dir()
    jobs_dir.mkdir(parents=True, exist_ok=True)
    stale_seconds = env_int("PPT_API_LLM_SLOT_STALE_SECONDS", LLM_SLOT_STALE_SECONDS, minimum=60)
    cleanup_stale_job_leases(jobs_dir, stale_seconds)
    return len(list(jobs_dir.glob("*.job")))


@contextmanager
def register_active_svg_job(job_id: str, runner_dir: Path, log_path: Path | None = None):
    jobs_dir = svg_job_dir()
    jobs_dir.mkdir(parents=True, exist_ok=True)
    stale_seconds = env_int("PPT_API_LLM_SLOT_STALE_SECONDS", LLM_SLOT_STALE_SECONDS, minimum=60)
    cleanup_stale_job_leases(jobs_dir, stale_seconds)
    lease_path = jobs_dir / f"{sanitize_token(job_id)}_{os.getpid()}.job"
    payload = {
        "pid": os.getpid(),
        "job_id": job_id,
        "runner_dir": str(runner_dir),
        "created_at": time.time(),
    }
    lease_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    if log_path is not None:
        append_log(log_path, f"Registered active SVG job lease: {lease_path}")
    try:
        yield
    finally:
        try:
            lease_path.unlink()
            if log_path is not None:
                append_log(log_path, f"Released active SVG job lease: {lease_path}")
        except OSError:
            pass


def effective_svg_worker_count(
    *,
    requested_workers: int,
    total_batches: int,
    log_path: Path | None = None,
) -> int:
    requested_workers = max(1, requested_workers)
    total_batches = max(1, total_batches)
    if not env_bool("PPT_API_SVG_FAIR_SHARE", True):
        return min(total_batches, requested_workers)

    svg_slots = llm_slot_limit("svg")
    active_jobs = max(1, active_svg_job_count())
    fair_workers = max(1, svg_slots // active_jobs)
    effective = min(total_batches, requested_workers, fair_workers)
    if log_path is not None:
        append_log(
            log_path,
            "SVG fair-share window: "
            f"svg_slots={svg_slots} active_svg_jobs={active_jobs} "
            f"requested={requested_workers} batches={total_batches} effective={effective}",
        )
    return effective


def infer_slot_stage(artifact_prefix: str) -> str:
    prefix = artifact_prefix.lower()
    if prefix.startswith("svg_batch") or prefix == "qwen":
        return "svg"
    if prefix.startswith("spec"):
        return "spec"
    if prefix.startswith("notes"):
        return "notes"
    return "generic"


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def cleanup_stale_slots(stage_dir: Path, stale_seconds: int) -> None:
    now = time.time()
    for slot_file in stage_dir.glob("*.slot"):
        try:
            payload = json.loads(slot_file.read_text(encoding="utf-8"))
        except Exception:
            try:
                if now - slot_file.stat().st_mtime > 10:
                    slot_file.unlink()
            except OSError:
                pass
            continue

        created_at = float(payload.get("created_at") or 0)
        pid = safe_int(payload.get("pid"))
        if (created_at and now - created_at > stale_seconds) or (pid and not pid_is_alive(pid)):
            try:
                slot_file.unlink()
            except OSError:
                pass


@contextmanager
def acquire_redis_resource_slot(
    client,
    stage: str,
    *,
    limit: int,
    label: str,
    runner_dir: Path,
    log_path: Path | None = None,
):
    stale_seconds = env_int("PPT_API_LLM_SLOT_STALE_SECONDS", LLM_SLOT_STALE_SECONDS, minimum=60)
    wait_timeout = env_int("PPT_API_LLM_SLOT_WAIT_TIMEOUT_SECONDS", LLM_SLOT_WAIT_TIMEOUT_SECONDS, minimum=60)
    started = time.time()
    last_wait_log = 0.0
    token = f"{os.getpid()}:{uuid.uuid4().hex}"
    acquired_key: str | None = None
    acquired_index: int | None = None
    waiting_key = redis_key(f"llm:waiting:{stage}")
    waiting_registered = False

    release_script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
    end
    return 0
    """

    try:
        client.incr(waiting_key)
        waiting_registered = True
    except Exception:
        waiting_registered = False

    try:
        while acquired_key is None:
            payload = json.dumps(
                {
                    "pid": os.getpid(),
                    "stage": stage,
                    "label": label,
                    "runner_dir": str(runner_dir),
                    "created_at": time.time(),
                    "token": token,
                },
                ensure_ascii=False,
            )
            for index in range(1, limit + 1):
                candidate = redis_key(f"llm:slot:{stage}:{index:03d}")
                try:
                    if client.set(candidate, token, nx=True, ex=stale_seconds):
                        client.set(redis_key(f"llm:slotmeta:{stage}:{index:03d}"), payload, ex=stale_seconds)
                        acquired_key = candidate
                        acquired_index = index
                        break
                except Exception as exc:
                    raise RunnerError(f"Redis slot acquisition failed: {exc}") from exc

            if acquired_key is not None:
                break
            if time.time() - started > wait_timeout:
                raise RunnerError(f"Timed out waiting for Redis {stage} slot after {wait_timeout}s: {label}")
            if log_path is not None and time.time() - last_wait_log >= 30:
                active = count_redis_stage_slots(client, stage, limit)
                append_log(log_path, f"Waiting for Redis {stage} slot: active={active}/{limit}; label={label}")
                last_wait_log = time.time()
            time.sleep(2)

        if waiting_registered:
            client.decr(waiting_key)
            waiting_registered = False
        if log_path is not None:
            append_log(log_path, f"Acquired Redis {stage} slot {acquired_index}/{limit} for {label}")
        yield
    finally:
        if waiting_registered:
            try:
                client.decr(waiting_key)
            except Exception:
                pass
        if acquired_key is not None:
            try:
                client.eval(release_script, 1, acquired_key, token)
                if acquired_index is not None:
                    client.delete(redis_key(f"llm:slotmeta:{stage}:{acquired_index:03d}"))
                if log_path is not None:
                    append_log(log_path, f"Released Redis {stage} slot for {label}")
            except Exception:
                pass


def count_redis_stage_slots(client, stage: str, limit: int) -> int:
    active = 0
    for index in range(1, limit + 1):
        try:
            if client.exists(redis_key(f"llm:slot:{stage}:{index:03d}")):
                active += 1
        except Exception:
            return active
    return active


@contextmanager
def acquire_resource_slot(
    stage: str,
    *,
    label: str,
    runner_dir: Path,
    log_path: Path | None = None,
    skip_tpm_pacing: bool = False,
):
    stage = stage if stage in DEFAULT_LLM_SLOT_LIMITS else "generic"
    limit = llm_slot_limit(stage)
    redis_client = get_runner_redis_client(log_path)
    if redis_client is not None:
        if not skip_tpm_pacing:
            wait_for_redis_tpm_budget(redis_client, stage, label=label, log_path=log_path)
        with acquire_redis_resource_slot(
            redis_client,
            stage,
            limit=limit,
            label=label,
            runner_dir=runner_dir,
            log_path=log_path,
        ):
            yield
        return

    slot_root = llm_slot_dir()
    stage_dir = slot_root / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    stale_seconds = env_int("PPT_API_LLM_SLOT_STALE_SECONDS", LLM_SLOT_STALE_SECONDS, minimum=60)
    wait_timeout = env_int("PPT_API_LLM_SLOT_WAIT_TIMEOUT_SECONDS", LLM_SLOT_WAIT_TIMEOUT_SECONDS, minimum=60)
    started = time.time()
    last_wait_log = 0.0
    slot_file: Path | None = None

    while slot_file is None:
        cleanup_stale_slots(stage_dir, stale_seconds)
        for index in range(1, limit + 1):
            candidate = stage_dir / f"{index:03d}.slot"
            payload = {
                "pid": os.getpid(),
                "stage": stage,
                "label": label,
                "runner_dir": str(runner_dir),
                "created_at": time.time(),
            }
            try:
                fd = os.open(str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
                handle.write("\n")
            slot_file = candidate
            if log_path is not None:
                append_log(log_path, f"Acquired {stage} slot {index}/{limit} for {label}")
            break

        if slot_file is not None:
            break
        if time.time() - started > wait_timeout:
            raise RunnerError(f"Timed out waiting for {stage} slot after {wait_timeout}s: {label}")
        if log_path is not None and time.time() - last_wait_log >= 30:
            active = len(list(stage_dir.glob("*.slot")))
            append_log(log_path, f"Waiting for {stage} slot: active={active}/{limit}; label={label}")
            last_wait_log = time.time()
        time.sleep(2)

    try:
        yield
    finally:
        if slot_file is not None:
            try:
                slot_file.unlink()
                if log_path is not None:
                    append_log(log_path, f"Released {stage} slot for {label}")
            except OSError:
                pass


def count_file_lines(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def read_chat_records_after_line(chat_path: Path | None, start_line: int) -> list[dict[str, Any]]:
    if chat_path is None or not chat_path.exists():
        return []

    records: list[dict[str, Any]] = []
    with chat_path.open("r", encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle, start=1):
            if index <= start_line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def merge_turn_usage(summaries: list[TurnUsageSummary]) -> TurnUsageSummary | None:
    if not summaries:
        return None

    merged = TurnUsageSummary(models=[])
    for summary in summaries:
        merged.api_calls += summary.api_calls
        merged.prompt_tokens += summary.prompt_tokens
        merged.completion_tokens += summary.completion_tokens
        merged.cached_tokens += summary.cached_tokens
        merged.thoughts_tokens += summary.thoughts_tokens
        merged.total_tokens += summary.total_tokens
        merged.tool_tokens += summary.tool_tokens
        merged.models.extend(summary.models or [])
    merged.models = sorted(set(merged.models))
    return merged


def accumulate_usage_summary(target: TurnUsageSummary, summary: TurnUsageSummary) -> None:
    target.api_calls += summary.api_calls
    target.prompt_tokens += summary.prompt_tokens
    target.completion_tokens += summary.completion_tokens
    target.cached_tokens += summary.cached_tokens
    target.thoughts_tokens += summary.thoughts_tokens
    target.total_tokens += summary.total_tokens
    target.tool_tokens += summary.tool_tokens
    target.models = sorted(set((target.models or []) + (summary.models or [])))


def parse_record_epoch(record: dict[str, Any], *, fallback: float | None = None) -> float:
    candidates = [
        record.get("timestamp"),
        record.get("createdAt"),
        record.get("created_at"),
        record.get("time"),
    ]
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            try:
                return float(text)
            except ValueError:
                pass
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            try:
                return datetime.fromisoformat(normalized).timestamp()
            except ValueError:
                continue
    return fallback if fallback is not None else time.time()


def usage_summary_from_ui_payload(payload: dict[str, Any]) -> TurnUsageSummary | None:
    if payload.get("event.name") != "qwen-code.api_response":
        return None
    return TurnUsageSummary(
        api_calls=1,
        prompt_tokens=safe_int(payload.get("input_token_count")),
        completion_tokens=safe_int(payload.get("output_token_count")),
        cached_tokens=safe_int(payload.get("cached_content_token_count")),
        thoughts_tokens=safe_int(payload.get("thoughts_token_count")),
        total_tokens=safe_int(payload.get("total_token_count")),
        tool_tokens=safe_int(payload.get("tool_token_count")),
        models=[str(payload.get("model"))] if payload.get("model") else [],
    )


def extract_usage_events_from_records(
    session_id: str,
    records: list[dict[str, Any]],
    *,
    fallback_epoch: float | None = None,
) -> list[tuple[float, TurnUsageSummary]]:
    events: list[tuple[float, TurnUsageSummary]] = []
    for record in records:
        if record.get("sessionId") != session_id:
            continue
        if record.get("type") != "system":
            continue
        if record.get("subtype") != "ui_telemetry":
            continue
        payload = ((record.get("systemPayload") or {}).get("uiEvent") or {})
        if not isinstance(payload, dict):
            continue
        summary = usage_summary_from_ui_payload(payload)
        if summary is None:
            continue
        event_epoch = parse_record_epoch(record, fallback=fallback_epoch)
        events.append((event_epoch, summary))
    return events


def summarize_usage_from_records(session_id: str, records: list[dict[str, Any]]) -> TurnUsageSummary | None:
    return merge_turn_usage([summary for _event_epoch, summary in extract_usage_events_from_records(session_id, records)])


def redis_live_stage_key(stage: str) -> str:
    return redis_key(f"llm:live:{stage}:tokens")


def redis_account_live_key(account_id: str) -> str:
    return redis_key(f"qwen_account_pool:account:{sanitize_token(account_id)}:live_tokens")


def record_live_stage_usage(
    stage: str,
    summary: TurnUsageSummary,
    *,
    event_epoch: float,
    session_id: str,
    label: str,
    account_id: str | None = None,
    log_path: Path | None = None,
) -> None:
    if summary.total_tokens <= 0:
        return
    client = get_runner_redis_client(log_path)
    if client is None:
        return
    window_seconds = live_tpm_window_seconds()
    member = f"{summary.total_tokens}|{sanitize_token(session_id)}|{sanitize_token(label)}|{uuid.uuid4().hex}"
    try:
        client.zremrangebyscore(redis_live_stage_key(stage), "-inf", f"{event_epoch - window_seconds:.6f}")
        client.zadd(redis_live_stage_key(stage), {member: event_epoch})
        client.expire(redis_live_stage_key(stage), window_seconds * 4)
        if account_id:
            account_key = redis_account_live_key(account_id)
            client.zremrangebyscore(account_key, "-inf", f"{event_epoch - window_seconds:.6f}")
            client.zadd(account_key, {member: event_epoch})
            client.expire(account_key, window_seconds * 4)
    except Exception as exc:
        if log_path is not None:
            append_log(log_path, f"Failed to record Redis live {stage} usage: {exc}")


def redis_live_stage_window_snapshot(
    stage: str,
    client=None,
    *,
    window_seconds: int | None = None,
) -> dict[str, int] | None:
    client = client or get_runner_redis_client()
    if client is None:
        return None
    window = window_seconds or live_tpm_window_seconds()
    now = time.time()
    try:
        client.zremrangebyscore(redis_live_stage_key(stage), "-inf", f"{now - window:.6f}")
        total = 0
        members = client.zrange(redis_live_stage_key(stage), 0, -1)
        for member in members:
            if not isinstance(member, str):
                continue
            token_text = member.split("|", 1)[0]
            try:
                total += int(token_text)
            except ValueError:
                continue
        return {
            "tokens": max(0, total),
            "events": len(members),
            "window_seconds": window,
        }
    except Exception:
        return None


def format_usage_summary(summary: TurnUsageSummary | None) -> str:
    if summary is None:
        return "usage unavailable"

    models = ",".join(summary.models or []) or "unknown"
    return (
        f"api_calls={summary.api_calls} "
        f"prompt={summary.prompt_tokens} "
        f"completion={summary.completion_tokens} "
        f"cached={summary.cached_tokens} "
        f"thoughts={summary.thoughts_tokens} "
        f"tool={summary.tool_tokens} "
        f"total={summary.total_tokens} "
        f"models={models}"
    )


def record_llm_observation(
    *,
    stage: str,
    model: str | None,
    usage: TurnUsageSummary | None,
    elapsed_seconds: float,
    log_path: Path | None = None,
) -> None:
    if usage is None or usage.total_tokens <= 0 or elapsed_seconds <= 0:
        return
    client = get_runner_redis_client(log_path)
    if client is None:
        return
    elapsed_minutes = max(elapsed_seconds / 60.0, 1 / 60.0)
    observed_tpm = usage.total_tokens / elapsed_minutes
    alpha = env_float("PPT_API_LLM_EWMA_ALPHA", 0.2, minimum=0.01, maximum=1.0)
    stage_key = redis_key(f"llm:ewma:{stage}:tpm")
    model_key = redis_key(f"llm:ewma:{stage}:{sanitize_token(model or 'unknown')}")
    try:
        old_value = float(client.get(stage_key) or 0)
        ewma = observed_tpm if old_value <= 0 else (alpha * observed_tpm + (1 - alpha) * old_value)
        client.set(stage_key, f"{ewma:.6f}")
        old_tokens = float(client.get(redis_key(f"llm:ewma:{stage}:tokens")) or 0)
        ewma_tokens = usage.total_tokens if old_tokens <= 0 else (alpha * usage.total_tokens + (1 - alpha) * old_tokens)
        client.set(redis_key(f"llm:ewma:{stage}:tokens"), f"{ewma_tokens:.6f}")
        old_duration = float(client.get(redis_key(f"llm:ewma:{stage}:duration_seconds")) or 0)
        ewma_duration = elapsed_seconds if old_duration <= 0 else (alpha * elapsed_seconds + (1 - alpha) * old_duration)
        client.set(redis_key(f"llm:ewma:{stage}:duration_seconds"), f"{ewma_duration:.6f}")
        client.hset(
            model_key,
            mapping={
                "model": model or "",
                "stage": stage,
                "observed_tpm": f"{observed_tpm:.6f}",
                "ewma_tpm": f"{ewma:.6f}",
                "ewma_tokens": f"{ewma_tokens:.6f}",
                "ewma_duration_seconds": f"{ewma_duration:.6f}",
                "total_tokens": usage.total_tokens,
                "elapsed_seconds": f"{elapsed_seconds:.3f}",
                "updated_at": f"{time.time():.3f}",
            },
        )
        if log_path is not None:
            append_log(log_path, f"Recorded Redis LLM EWMA stage={stage} observed_tpm={observed_tpm:.2f} ewma_tpm={ewma:.2f}")
    except Exception as exc:
        if log_path is not None:
            append_log(log_path, f"Failed to record Redis LLM EWMA: {exc}")


def update_usage_summary(
    runner_dir: Path,
    *,
    stage_name: str,
    artifact_prefix: str,
    turn_index: int,
    session_id: str,
    usage: TurnUsageSummary | None,
) -> None:
    usage_path = runner_dir / USAGE_SUMMARY_FILENAME
    turn_payload = {
        "stage_name": stage_name,
        "artifact_prefix": artifact_prefix,
        "turn_index": turn_index,
        "session_id": session_id,
        "usage": usage.to_json() if usage else None,
    }

    with USAGE_SUMMARY_LOCK:
        payload: dict[str, Any]
        if usage_path.exists():
            try:
                payload = json.loads(usage_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
        else:
            payload = {}

        turns = payload.get("turns")
        if not isinstance(turns, list):
            turns = []
        turns = [
            item
            for item in turns
            if not (
                isinstance(item, dict)
                and item.get("stage_name") == stage_name
                and item.get("artifact_prefix") == artifact_prefix
                and item.get("turn_index") == turn_index
                and item.get("session_id") == session_id
            )
        ]
        turns.append(turn_payload)
        turns.sort(
            key=lambda item: (
                str(item.get("stage_name", "")),
                str(item.get("artifact_prefix", "")),
                safe_int(item.get("turn_index")),
            )
        )

        stage_totals: dict[str, TurnUsageSummary] = {}
        overall = TurnUsageSummary(models=[])
        for item in turns:
            usage_payload = item.get("usage")
            if not isinstance(usage_payload, dict):
                continue
            summary = TurnUsageSummary(
                api_calls=safe_int(usage_payload.get("api_calls")),
                prompt_tokens=safe_int(usage_payload.get("prompt_tokens")),
                completion_tokens=safe_int(usage_payload.get("completion_tokens")),
                cached_tokens=safe_int(usage_payload.get("cached_tokens")),
                thoughts_tokens=safe_int(usage_payload.get("thoughts_tokens")),
                total_tokens=safe_int(usage_payload.get("total_tokens")),
                tool_tokens=safe_int(usage_payload.get("tool_tokens")),
                models=list(usage_payload.get("models") or []),
            )
            stage_key = str(item.get("stage_name") or "unknown")
            current = stage_totals.get(stage_key)
            if current is None:
                current = TurnUsageSummary(models=[])
                stage_totals[stage_key] = current
            current.api_calls += summary.api_calls
            current.prompt_tokens += summary.prompt_tokens
            current.completion_tokens += summary.completion_tokens
            current.cached_tokens += summary.cached_tokens
            current.thoughts_tokens += summary.thoughts_tokens
            current.total_tokens += summary.total_tokens
            current.tool_tokens += summary.tool_tokens
            current.models.extend(summary.models or [])

            overall.api_calls += summary.api_calls
            overall.prompt_tokens += summary.prompt_tokens
            overall.completion_tokens += summary.completion_tokens
            overall.cached_tokens += summary.cached_tokens
            overall.thoughts_tokens += summary.thoughts_tokens
            overall.total_tokens += summary.total_tokens
            overall.tool_tokens += summary.tool_tokens
            overall.models.extend(summary.models or [])

        payload["turns"] = turns
        payload["stage_totals"] = {
            key: value.to_json()
            for key, value in sorted(stage_totals.items(), key=lambda item: item[0])
        }
        payload["overall"] = overall.to_json()
        write_json(usage_path, payload)


def log_usage_overall(runner_dir: Path, log_path: Path) -> None:
    usage_path = runner_dir / USAGE_SUMMARY_FILENAME
    if not usage_path.exists():
        append_log(log_path, "Overall usage summary unavailable")
        return

    try:
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        append_log(log_path, f"Overall usage summary unreadable: {usage_path}")
        return

    overall_payload = payload.get("overall")
    if not isinstance(overall_payload, dict):
        append_log(log_path, f"Overall usage summary missing totals: {usage_path}")
        return

    summary = TurnUsageSummary(
        api_calls=safe_int(overall_payload.get("api_calls")),
        prompt_tokens=safe_int(overall_payload.get("prompt_tokens")),
        completion_tokens=safe_int(overall_payload.get("completion_tokens")),
        cached_tokens=safe_int(overall_payload.get("cached_tokens")),
        thoughts_tokens=safe_int(overall_payload.get("thoughts_tokens")),
        total_tokens=safe_int(overall_payload.get("total_tokens")),
        tool_tokens=safe_int(overall_payload.get("tool_tokens")),
        models=list(overall_payload.get("models") or []),
    )
    append_log(log_path, f"Overall usage summary {format_usage_summary(summary)}")


def resolve_qwen_launcher() -> list[str]:
    candidates = [
        shutil.which("qwen"),
        shutil.which("qwen.cmd"),
        shutil.which("qwen.exe"),
        shutil.which("qwen.ps1"),
    ]
    launcher = next((item for item in candidates if item), None)
    if launcher is None:
        raise RunnerError("qwen CLI is not available in PATH")

    launcher_path = Path(launcher)
    if launcher_path.suffix.lower() == ".ps1":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell is None:
            raise RunnerError("qwen.ps1 was found, but no PowerShell executable is available")
        return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher_path)]
    return [str(launcher_path)]


def normalize_qwen_credential_override(payload: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(payload, dict):
        return None
    api_key = str(payload.get("api_key") or "").strip()
    if not api_key:
        return None
    override = {
        "api_key": api_key,
        "account_id": str(payload.get("account_id") or "").strip(),
    }
    for key in ("base_url", "model", "auth_type"):
        value = str(payload.get(key) or "").strip()
        if value:
            override[key] = value
    return override


def resolve_qwen_cli_auth_args(credential_override: dict[str, str] | None = None) -> list[str]:
    credential_override = credential_override or {}
    api_key = (credential_override.get("api_key") or os.getenv("PPT_API_QWEN_API_KEY") or "").strip()
    base_url = (credential_override.get("base_url") or os.getenv("PPT_API_QWEN_BASE_URL") or "").strip()
    if credential_override.get("api_key"):
        auth_type = (credential_override.get("auth_type") or "openai").strip()
    else:
        auth_type = (os.getenv("PPT_API_QWEN_AUTH_TYPE") or "").strip()

    args: list[str] = []
    if auth_type:
        args.extend(["--auth-type", auth_type])
    if api_key:
        args.extend(["--openai-api-key", api_key])
    if base_url:
        args.extend(["--openai-base-url", base_url])

    if auth_type == "openai" and not api_key:
        raise RunnerError("PPT_API_QWEN_AUTH_TYPE=openai requires PPT_API_QWEN_API_KEY to be set")

    return args


def resolve_openai_compatible_endpoint(credential_override: dict[str, str] | None = None) -> tuple[str, str] | None:
    credential_override = credential_override or {}
    api_key = (credential_override.get("api_key") or os.getenv("PPT_API_QWEN_API_KEY") or "").strip()
    base_url = (credential_override.get("base_url") or os.getenv("PPT_API_QWEN_BASE_URL") or "").strip()
    if not api_key or not base_url:
        return None
    return api_key, base_url.rstrip("/") + "/chat/completions"


def redact_sensitive_command_parts(parts: list[str]) -> list[str]:
    redacted = list(parts)
    secret_flags = {"--openai-api-key"}
    for index, item in enumerate(redacted[:-1]):
        if item in secret_flags:
            redacted[index + 1] = "***"
    return redacted


def load_request(request_path: Path) -> dict[str, Any]:
    request = read_json(request_path)
    rules = deep_merge(DEFAULT_RULES, request.get("rules", {}))
    request["rules"] = rules

    required = ("job_id", "source_md_path", "project_name")
    for key in required:
        value = request.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RunnerError(f"Missing or invalid required field: {key}")

    source_md_path = Path(request["source_md_path"]).expanduser().resolve()
    if not source_md_path.exists() or not source_md_path.is_file():
        raise RunnerError(f"Markdown source not found: {source_md_path}")
    if source_md_path.suffix.lower() not in {".md", ".markdown"}:
        raise RunnerError(f"Source must be a Markdown file: {source_md_path}")

    request["source_md_path"] = str(source_md_path)
    request["canvas_format"] = request.get("canvas_format") or DEFAULT_CANVAS_FORMAT
    request["project_base_dir"] = request.get("project_base_dir") or DEFAULT_PROJECT_BASE_DIR
    if "model" in request and request["model"] is not None and not isinstance(request["model"], str):
        raise RunnerError("model must be null or a string")
    if "review_model" in request and request["review_model"] is not None and not isinstance(request["review_model"], str):
        raise RunnerError("review_model must be null or a string")
    if "spec_model" in request and request["spec_model"] is not None and not isinstance(request["spec_model"], str):
        raise RunnerError("spec_model must be null or a string")
    if "notes_model" in request and request["notes_model"] is not None and not isinstance(request["notes_model"], str):
        raise RunnerError("notes_model must be null or a string")
    batch_mode = (request.get("batch_mode") or "parallel")
    if not isinstance(batch_mode, str) or batch_mode not in {"auto", "always", "never", "parallel"}:
        raise RunnerError("batch_mode must be one of: auto, always, never, parallel")
    request["batch_mode"] = batch_mode
    batch_size = request.get("batch_size", BATCH_SIZE)
    if not isinstance(batch_size, int) or batch_size < 1:
        raise RunnerError("batch_size must be a positive integer")
    request["batch_size"] = batch_size
    parallel_batch_workers = request.get("parallel_batch_workers", DEFAULT_PARALLEL_BATCH_WORKERS)
    if not isinstance(parallel_batch_workers, int) or parallel_batch_workers < 1:
        raise RunnerError("parallel_batch_workers must be a positive integer")
    request["parallel_batch_workers"] = parallel_batch_workers
    batch_partition = (request.get("batch_partition") or DEFAULT_BATCH_PARTITION)
    if not isinstance(batch_partition, str):
        raise RunnerError("batch_partition must be a string")
    batch_partition = batch_partition.strip().lower() or DEFAULT_BATCH_PARTITION
    if not is_valid_batch_partition(batch_partition):
        raise RunnerError(
            "batch_partition must be one of: fixed, ramp, anchor_even, ramp_2_3_4_5_6_7_8, or a numeric sequence like 2+6+6+6+6+6+"
        )
    request["batch_partition"] = batch_partition
    model = request.get("model")
    request["model"] = model.strip() if isinstance(model, str) and model.strip() else DEFAULT_QWEN_MODEL
    spec_model = request.get("spec_model")
    if isinstance(spec_model, str) and spec_model.strip():
        request["spec_model"] = spec_model.strip()
    else:
        request["spec_model"] = request["model"]
    review_model = request.get("review_model")
    if isinstance(review_model, str) and review_model.strip():
        request["review_model"] = review_model.strip()
    else:
        request["review_model"] = DEFAULT_REVIEW_MODEL
    notes_model = request.get("notes_model")
    if isinstance(notes_model, str) and notes_model.strip():
        request["notes_model"] = notes_model.strip()
    else:
        request["notes_model"] = request["model"]
    return request


def parse_markdown_structure(markdown_path: Path) -> list[MarkdownH2]:
    lines = markdown_path.read_text(encoding="utf-8", errors="replace").splitlines()
    sections: list[MarkdownH2] = []
    current_h2: MarkdownH2 | None = None
    current_h3: MarkdownH3 | None = None
    in_fence = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if current_h3 is not None:
                current_h3.body_lines.append(line)
            elif current_h2 is not None:
                current_h2.intro_lines.append(line)
            continue

        if not in_fence:
            match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                if level == 2:
                    current_h2 = MarkdownH2(title=title, intro_lines=[], children=[])
                    current_h3 = None
                    sections.append(current_h2)
                    continue
                if level == 3 and current_h2 is not None:
                    current_h3 = MarkdownH3(title=title, body_lines=[])
                    current_h2.children.append(current_h3)
                    continue

        if current_h3 is not None:
            current_h3.body_lines.append(line)
        elif current_h2 is not None:
            current_h2.intro_lines.append(line)

    return sections


def build_section_lookup(sections: list[MarkdownH2]) -> dict[str, MarkdownH2]:
    return {section.title: section for section in sections}


def build_chart_template_reference() -> list[dict[str, Any]]:
    chart_catalog = load_chart_catalog()
    categories = load_chart_categories()
    category_lookup: dict[str, str] = {}
    for category_key, category_value in categories.items():
        if not isinstance(category_value, dict):
            continue
        label = str(category_value.get("label") or category_key)
        for chart_name in category_value.get("charts") or []:
            category_lookup[str(chart_name)] = label

    reference: list[dict[str, Any]] = []
    for key in sorted(chart_catalog):
        item = chart_catalog[key]
        reference.append(
            {
                "key": key,
                "label": item.get("label", key),
                "category": category_lookup.get(key, "Uncategorized"),
                "summary": item.get("summary", ""),
                "keywords": item.get("keywords", []),
                "template_path": f"templates/charts/{key}.svg",
            }
        )
    return reference


def score_chart_candidate(candidate: str, invalid_name: str) -> tuple[int, int, str]:
    invalid_tokens = set(invalid_name.split("_"))
    candidate_tokens = set(candidate.split("_"))
    overlap = len(invalid_tokens & candidate_tokens)
    same_prefix = int(candidate[:1] == invalid_name[:1])
    return (overlap, same_prefix, candidate)


def suggest_chart_replacements(invalid_name: str, valid_chart_keys: set[str], limit: int = 5) -> list[str]:
    close = get_close_matches(invalid_name, sorted(valid_chart_keys), n=limit, cutoff=0.3)
    token_ranked = sorted(
        valid_chart_keys,
        key=lambda candidate: score_chart_candidate(candidate, invalid_name),
        reverse=True,
    )
    selected: list[str] = []
    for candidate in [*close, *token_ranked]:
        if candidate not in selected:
            selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def choose_existing_icons(
    available_icons: set[str],
    preferred: list[str],
    fallback: list[str],
    limit: int = 4,
) -> list[str]:
    selected: list[str] = []
    for candidate in preferred + fallback:
        if candidate in available_icons and candidate not in selected:
            selected.append(candidate)
        if len(selected) >= limit:
            return selected

    for candidate in sorted(available_icons):
        if candidate not in selected:
            selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def suggest_icons_for_heading(heading: str, available_icons: set[str]) -> list[str]:
    text = heading.lower()
    keyword_map = [
        (("创新", "技术", "tech", "研发", "算法", "系统"), ["lightbulb", "microchip", "bolt", "cog"]),
        (("产业", "市场", "商业", "business", "运营", "推广"), ["building", "chart-bar", "target", "money"]),
        (("财务", "盈利", "收益", "finance", "profit"), ["money", "coin", "chart-pie", "chart-line"]),
        (("团队", "专家", "教师", "组织", "team"), ["users", "user", "book-open", "star"]),
        (("背景", "现状", "调研", "分析", "research"), ["book-open", "chart-line", "globe", "chart-bar"]),
        (("验证", "安全", "风险", "quality"), ["shield-check", "shield", "chart-line", "target"]),
        (("落地", "实施", "roadmap", "规划", "推进"), ["rocket", "target-arrow", "calendar", "link"]),
        (("生态", "协同", "合作", "网络", "platform"), ["link", "globe", "building", "users"]),
    ]
    fallback = ["chart-bar", "lightbulb", "target", "building", "users"]
    preferred: list[str] = []
    for keywords, candidates in keyword_map:
        if any(token in text for token in keywords):
            preferred.extend(candidates)
    return choose_existing_icons(available_icons, preferred, fallback)


def build_icon_candidate_reference(
    plan: list[SlidePlanEntry],
    available_icons: set[str],
) -> list[dict[str, Any]]:
    reference: list[dict[str, Any]] = []
    for entry in plan:
        if entry.kind != "content":
            continue
        icons = suggest_icons_for_heading(entry.heading, available_icons)
        reference.append(
            {
                "slide": entry.filename,
                "heading": entry.heading,
                "source_h2": entry.source_h2,
                "source_h3": entry.source_h3,
                "library": DEFAULT_ICON_LIBRARY,
                "candidates": [f"{DEFAULT_ICON_LIBRARY}/{icon_name}" for icon_name in icons],
            }
        )
    return reference


MARKDOWN_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)"
)
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=['\"](?P<src>[^'\"]+)['\"][^>]*>", re.IGNORECASE)


def clean_markdown_image_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    return target


def strip_url_suffix(target: str) -> str:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return target
    return target.split("#", 1)[0].split("?", 1)[0]


def find_image_refs_in_line(line: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for match in MARKDOWN_IMAGE_RE.finditer(line):
        refs.append(
            {
                "alt": match.group("alt").strip(),
                "target": clean_markdown_image_target(match.group("target")),
                "syntax": "markdown",
            }
        )
    for match in HTML_IMAGE_RE.finditer(line):
        refs.append(
            {
                "alt": "",
                "target": clean_markdown_image_target(match.group("src")),
                "syntax": "html",
            }
        )
    return refs


def path_relative_to_project(path: Path, project_path: Path) -> str:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_source_image_paths(
    *,
    markdown_path: Path,
    project_path: Path,
    target: str,
) -> dict[str, Any]:
    cleaned = strip_url_suffix(target)
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme and parsed.scheme not in {"file"}:
        return {
            "source": target,
            "source_path": None,
            "project_image": None,
            "svg_href": None,
            "exists": False,
            "remote": True,
        }

    local_target = urllib.parse.unquote(parsed.path if parsed.scheme == "file" else cleaned)
    source_path = (markdown_path.parent / local_target).resolve()
    image_name = source_path.name
    project_image_path = project_path / "images" / image_name
    return {
        "source": target,
        "source_path": path_relative_to_project(source_path, project_path),
        "project_image": f"images/{image_name}",
        "svg_href": f"../images/{image_name}",
        "exists": project_image_path.exists(),
        "remote": False,
    }


def find_slide_for_source_image(
    plan: list[SlidePlanEntry],
    source_h2: str,
    source_h3: str | None,
) -> SlidePlanEntry | None:
    if source_h3:
        for entry in plan:
            if entry.kind == "content" and entry.source_h2 == source_h2 and entry.source_h3 == source_h3:
                return entry
        for entry in plan:
            if entry.kind == "content" and entry.source_h2 == source_h2 and entry.source_h3 is None:
                return entry
        return None

    for entry in plan:
        if entry.kind == "content" and entry.source_h2 == source_h2 and entry.source_h3 is None:
            return entry
    for entry in plan:
        if entry.kind == "content" and entry.source_h2 == source_h2 and entry.absorb_parent_intro:
            return entry
    return None


def build_source_image_reference(
    *,
    imported_markdown_path: Path,
    project_path: Path,
    plan: list[SlidePlanEntry],
    sections: list[MarkdownH2],
) -> list[dict[str, Any]]:
    reference: list[dict[str, Any]] = []

    def add_refs(source_h2: str, source_h3: str | None, lines: list[str]) -> None:
        assigned_slide = find_slide_for_source_image(plan, source_h2, source_h3)
        for index, line in enumerate(lines):
            refs = find_image_refs_in_line(line)
            if not refs:
                continue
            context_window = lines[max(0, index - 2):index] + lines[index + 1:index + 3]
            context = collect_salient_lines(context_window, limit=3)
            for ref in refs:
                paths = resolve_source_image_paths(
                    markdown_path=imported_markdown_path,
                    project_path=project_path,
                    target=ref["target"],
                )
                payload: dict[str, Any] = {
                    "slide": assigned_slide.filename if assigned_slide else None,
                    "slide_index": assigned_slide.index if assigned_slide else None,
                    "heading": assigned_slide.heading if assigned_slide else None,
                    "source_h2": source_h2,
                    "source_h3": source_h3,
                    "alt": ref["alt"],
                    "markdown_target": ref["target"],
                    "syntax": ref["syntax"],
                    "context": context,
                    "required": assigned_slide is not None,
                    "layout_instruction": (
                        "Use an image-aware layout on this assigned slide and reference the exact project image. "
                        "Do not move this image to a different chapter."
                    ),
                }
                payload.update(paths)
                reference.append(payload)

    for section in sections:
        add_refs(section.title, None, section.intro_lines)
        for child in section.children:
            add_refs(section.title, child.title, child.body_lines)

    return reference


def attach_source_images_to_digest(
    digest: list[dict[str, Any]],
    source_image_reference: list[dict[str, Any]],
) -> None:
    images_by_slide: dict[str, list[dict[str, Any]]] = {}
    for item in source_image_reference:
        slide = item.get("slide")
        if not isinstance(slide, str) or not slide:
            continue
        images_by_slide.setdefault(slide, []).append(
            {
                "project_image": item.get("project_image"),
                "svg_href": item.get("svg_href"),
                "markdown_target": item.get("markdown_target"),
                "source_h2": item.get("source_h2"),
                "source_h3": item.get("source_h3"),
                "context": item.get("context", []),
                "layout_instruction": item.get("layout_instruction"),
            }
        )

    for item in digest:
        slide = item.get("slide")
        if isinstance(slide, str) and slide in images_by_slide:
            item["source_images"] = images_by_slide[slide]


def build_slide_content_digest(
    plan: list[SlidePlanEntry],
    sections: list[MarkdownH2],
    source_image_reference: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    section_lookup = build_section_lookup(sections)
    digest: list[dict[str, Any]] = []
    for entry in plan:
        if entry.kind == "cover":
            digest.append(
                {
                    "slide": entry.filename,
                    "heading": entry.heading,
                    "kind": entry.kind,
                    "key_points": ["Use the real project title from the source markdown, not the directory name."],
                }
            )
            continue
        if entry.kind == "ending":
            digest.append(
                {
                    "slide": entry.filename,
                    "heading": entry.heading,
                    "kind": entry.kind,
                    "key_points": ["Create a concise closing / thank-you page aligned with the deck style."],
                }
            )
            continue

        section = section_lookup.get(entry.source_h2 or "")
        points: list[str] = []
        if section is not None:
            if entry.source_h3:
                for child in section.children:
                    if child.title == entry.source_h3:
                        if entry.absorb_parent_intro:
                            points.extend(collect_salient_lines(section.intro_lines, limit=3))
                        points.extend(collect_salient_lines(child.body_lines, limit=8))
                        break
            else:
                points.extend(collect_salient_lines(section.intro_lines, limit=8))
                for child in section.children:
                    child_prefix = child.title
                    child_points = collect_salient_lines(child.body_lines, limit=2)
                    if child_points:
                        points.append(f"{child_prefix}: {'; '.join(child_points[:2])}")
                    else:
                        points.append(child_prefix)
                    if len(points) >= 8:
                        break
        digest.append(
            {
                "slide": entry.filename,
                "heading": entry.heading,
                "kind": entry.kind,
                "source_h2": entry.source_h2,
                "source_h3": entry.source_h3,
                "key_points": points[:8],
            }
        )
    if source_image_reference:
        attach_source_images_to_digest(digest, source_image_reference)
    return digest


def get_content_slides(plan: list[SlidePlanEntry]) -> list[SlidePlanEntry]:
    return [entry for entry in plan if entry.kind == "content"]


def build_slide_plan(request: dict[str, Any], markdown_path: Path) -> list[SlidePlanEntry]:
    sections = parse_markdown_structure(markdown_path)
    if not sections:
        raise RunnerError(f"No H2 headings found in markdown: {markdown_path}")

    rules = request["rules"]
    expand_titles = set(rules["pagination"]["expand_h2_titles"])
    include_cover = bool(rules["include_cover"])
    include_ending = bool(rules["include_ending"])

    raw_entries: list[dict[str, Any]] = []

    if include_cover:
        raw_entries.append(
            {
                "kind": "cover",
                "heading": "封面",
                "source_h2": None,
                "source_h3": None,
                "absorb_parent_intro": False,
            }
        )

    content_counter = 0
    for section in sections:
        if is_resource_only_heading(section.title):
            continue
        should_expand = section.title in expand_titles and section.children
        if should_expand:
            for idx, child in enumerate(section.children):
                content_counter += 1
                raw_entries.append(
                    {
                        "kind": "content",
                        "heading": child.title,
                        "source_h2": section.title,
                        "source_h3": child.title,
                        "absorb_parent_intro": idx == 0 and bool("".join(section.intro_lines).strip()),
                        "content_counter": content_counter,
                    }
                )
        else:
            content_counter += 1
            raw_entries.append(
                {
                    "kind": "content",
                    "heading": section.title,
                    "source_h2": section.title,
                    "source_h3": None,
                    "absorb_parent_intro": False,
                    "content_counter": content_counter,
                }
            )

    if include_ending:
        raw_entries.append(
            {
                "kind": "ending",
                "heading": "结尾页",
                "source_h2": None,
                "source_h3": None,
                "absorb_parent_intro": False,
            }
        )

    width = max(2, len(str(len(raw_entries))))
    plan: list[SlidePlanEntry] = []
    content_counter = 0
    for index, entry in enumerate(raw_entries, start=1):
        kind = entry["kind"]
        if kind == "cover":
            filename = f"slide_{index:0{width}d}_cover.svg"
        elif kind == "ending":
            filename = f"slide_{index:0{width}d}_ending.svg"
        else:
            content_counter += 1
            filename = f"slide_{index:0{width}d}_content_{content_counter:02d}.svg"
        plan.append(
            SlidePlanEntry(
                index=index,
                filename=filename,
                heading=entry["heading"],
                kind=kind,
                source_h2=entry["source_h2"],
                source_h3=entry["source_h3"],
                absorb_parent_intro=bool(entry["absorb_parent_intro"]),
            )
        )
    return plan


def find_chat_recording_path(session_id: str) -> Path | None:
    if not QWEN_CHAT_ROOT.exists():
        return None
    matches = list(QWEN_CHAT_ROOT.glob(f"*/chats/{session_id}.jsonl"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return matches[0]
    fallback = list(QWEN_CHAT_ROOT.rglob(f"{session_id}.jsonl"))
    if not fallback:
        return None
    fallback.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return fallback[0]


def wait_for_chat_recording_path(session_id: str, timeout_seconds: int = 10) -> Path | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        chat_path = find_chat_recording_path(session_id)
        if chat_path is not None:
            return chat_path
        time.sleep(0.25)
    return find_chat_recording_path(session_id)


def find_debug_log_path(session_id: str) -> Path | None:
    candidate = QWEN_DEBUG_ROOT / f"{session_id}.txt"
    if candidate.exists():
        return candidate
    return None


def extract_visible_text(parts: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for part in parts:
        if part.get("thought"):
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    return "\n\n".join(texts).strip()


def read_latest_assistant_message(chat_path: Path | None, session_id: str) -> str:
    if chat_path is None or not chat_path.exists():
        return ""

    latest_text = ""
    with chat_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("sessionId") != session_id:
                continue
            if record.get("type") != "assistant":
                continue
            message = record.get("message") or {}
            parts = message.get("parts") or []
            if not isinstance(parts, list):
                continue
            text = extract_visible_text(parts)
            if text:
                latest_text = text
    return latest_text


def turn_live_usage_path(runner_dir: Path, artifact_prefix: str, turn_index: int) -> Path:
    return runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}{LIVE_USAGE_FILENAME_SUFFIX}"


def write_live_usage_snapshot(path: Path, snapshot: LiveUsageSnapshot) -> None:
    write_json(path, snapshot.to_json())


def monitor_qwen_live_usage(
    process: subprocess.Popen[str],
    *,
    session_id: str,
    stage: str,
    label: str,
    runner_dir: Path,
    artifact_prefix: str,
    turn_index: int,
    initial_chat_path: Path | None,
    initial_line_count: int,
    account_id: str | None = None,
    log_path: Path | None = None,
) -> None:
    if not live_usage_enabled(stage):
        return

    chat_path = initial_chat_path
    last_line = initial_line_count
    poll_seconds = live_usage_poll_seconds()
    log_interval_seconds = live_usage_log_interval_seconds()
    window_seconds = live_tpm_window_seconds()
    snapshot_path = turn_live_usage_path(runner_dir, artifact_prefix, turn_index)
    cumulative = TurnUsageSummary(models=[])
    rolling_events: deque[tuple[float, int]] = deque()
    observed_events = 0
    last_log_at = 0.0
    last_event_epoch: float | None = None
    exit_seen_at: float | None = None

    while True:
        now = time.time()
        if chat_path is None:
            chat_path = find_chat_recording_path(session_id)
            if chat_path is not None:
                last_line = count_file_lines(chat_path)

        if chat_path is not None and chat_path.exists():
            current_line_count = count_file_lines(chat_path)
            if current_line_count > last_line:
                records = read_chat_records_after_line(chat_path, last_line)
                last_line = current_line_count
                for event_epoch, summary in extract_usage_events_from_records(session_id, records, fallback_epoch=now):
                    accumulate_usage_summary(cumulative, summary)
                    observed_events += 1
                    last_event_epoch = event_epoch
                    rolling_events.append((event_epoch, summary.total_tokens))
                    record_live_stage_usage(
                        stage,
                        summary,
                        event_epoch=event_epoch,
                        session_id=session_id,
                        label=label,
                        account_id=account_id,
                        log_path=log_path,
                    )
                while rolling_events and rolling_events[0][0] < now - window_seconds:
                    rolling_events.popleft()

        rolling_tpm = sum(tokens for _epoch, tokens in rolling_events)
        should_log = now - last_log_at >= log_interval_seconds
        snapshot = LiveUsageSnapshot(
            stage=stage,
            label=label,
            session_id=session_id,
            window_seconds=window_seconds,
            poll_seconds=poll_seconds,
            log_interval_seconds=log_interval_seconds,
            cumulative=cumulative,
            rolling_tpm_60s=rolling_tpm,
            last_event_epoch=last_event_epoch,
            observed_events=observed_events,
        )
        write_live_usage_snapshot(snapshot_path, snapshot)
        if should_log and observed_events:
            if log_path is not None:
                append_log(
                    log_path,
                    f"Live qwen usage for {label}: {format_usage_summary(cumulative)} "
                    f"rolling_tpm_60s={rolling_tpm} observed_events={observed_events}",
                )
            last_log_at = now

        if process.poll() is not None:
            if exit_seen_at is None:
                exit_seen_at = now
            if now - exit_seen_at >= max(1.0, poll_seconds * 2):
                break
        time.sleep(poll_seconds)


def collect_expected_svg_names(plan: list[SlidePlanEntry]) -> set[str]:
    return {entry.filename for entry in plan}


def parse_notes_headings(notes_path: Path) -> list[str]:
    if not notes_path.exists():
        return []
    headings: list[str] = []
    for line in notes_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            headings.append(line[2:].strip())
    return headings


def repair_notes_headings(
    project_path: Path,
    plan: list[SlidePlanEntry],
    *,
    log_path: Path | None = None,
) -> bool:
    notes_path = project_path / "notes" / "total.md"
    if not notes_path.exists():
        return False

    expected_note_headings = [entry.note_heading for entry in plan]
    content = notes_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    heading_indices = [idx for idx, line in enumerate(lines) if line.startswith("# ")]
    if len(heading_indices) != len(expected_note_headings):
        return False

    changed: list[dict[str, str]] = []
    for idx, expected_heading in zip(heading_indices, expected_note_headings):
        current_heading = lines[idx][2:].strip()
        if current_heading != expected_heading:
            lines[idx] = f"# {expected_heading}"
            changed.append({"from": current_heading, "to": expected_heading})

    if not changed:
        return False

    trailing_newline = "\n" if content.endswith("\n") else ""
    notes_path.write_text("\n".join(lines) + trailing_newline, encoding="utf-8")
    if log_path is not None:
        append_log(log_path, f"Notes repair: normalized headings {changed}")
    return True


def extract_markdown_section(content: str, header_prefix: str, next_header_prefix: str | None) -> str:
    start = content.find(header_prefix)
    if start == -1:
        return ""
    if next_header_prefix is None:
        return content[start:]
    end = content.find(next_header_prefix, start + len(header_prefix))
    if end == -1:
        return content[start:]
    return content[start:end]


def find_unknown_chart_references(design_spec_text: str, valid_chart_keys: set[str]) -> list[str]:
    section_vii = extract_markdown_section(
        design_spec_text,
        "## VII. Visualization Reference List",
        "## VIII. Image Resource List",
    )
    tokens = set(re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+\b", section_vii))
    path_tokens = set(re.findall(r"templates/charts/([a-z0-9_]+)\.svg", section_vii))
    return sorted(
        token
        for token in (tokens | path_tokens)
        if token not in valid_chart_keys
        and token not in GENERIC_CHART_TOKENS
        and not token.startswith("slide_")
    )


def extract_icon_refs_from_text(text: str) -> list[str]:
    refs = set(re.findall(rf"{re.escape(DEFAULT_ICON_LIBRARY)}/[a-z0-9-]+", text))
    return sorted(refs)


def find_invalid_icon_refs(text: str, available_icons: set[str]) -> list[str]:
    invalid: list[str] = []
    for ref in extract_icon_refs_from_text(text):
        icon_name = ref.split("/", 1)[1]
        if icon_name not in available_icons:
            invalid.append(ref)
    return invalid


def normalize_design_spec_icon_inventory(text: str) -> tuple[str, list[dict[str, str]]]:
    section = extract_markdown_section(
        text,
        "## VI. Icon Usage",
        "## VII. Visualization Reference List",
    )
    if not section:
        return text, []

    icon_placeholder_pattern = re.compile(
        r"`\{\{icon:((?:chunk|tabler-filled|tabler-outline)/[a-z0-9-]+)\}\}`"
    )
    fixes: list[dict[str, str]] = []

    def replace_placeholder(match: re.Match[str]) -> str:
        original = match.group(0)
        icon_ref = match.group(1)
        replacement = f"`{icon_ref}`"
        fixes.append({"invalid": original, "replacement": replacement})
        return replacement

    updated_section = icon_placeholder_pattern.sub(replace_placeholder, section)
    if updated_section == section:
        return text, []

    return text.replace(section, updated_section, 1), fixes


def score_icon_candidate(icon_name: str, invalid_name: str) -> tuple[int, int, str]:
    invalid_tokens = set(invalid_name.split("-"))
    candidate_tokens = set(icon_name.split("-"))
    overlap = len(invalid_tokens & candidate_tokens)
    same_prefix = int(icon_name[:1] == invalid_name[:1])
    return (overlap, same_prefix, icon_name)


def suggest_icon_replacements(invalid_ref: str, available_icons: set[str], limit: int = 5) -> list[str]:
    invalid_name = invalid_ref.split("/", 1)[1]
    close = get_close_matches(invalid_name, sorted(available_icons), n=limit, cutoff=0.3)
    token_ranked = sorted(
        available_icons,
        key=lambda candidate: score_icon_candidate(candidate, invalid_name),
        reverse=True,
    )
    selected: list[str] = []
    for candidate in [*close, *token_ranked]:
        ref = f"{DEFAULT_ICON_LIBRARY}/{candidate}"
        if ref not in selected:
            selected.append(ref)
        if len(selected) >= limit:
            break
    return selected


def choose_fallback_icon_ref(
    entry_filename: str,
    invalid_ref: str,
    used_icon_refs: set[str],
    available_icons: set[str],
) -> str:
    unused_refs = [
        f"{DEFAULT_ICON_LIBRARY}/{icon_name}"
        for icon_name in sorted(available_icons)
        if f"{DEFAULT_ICON_LIBRARY}/{icon_name}" not in used_icon_refs
    ]
    candidate_refs = unused_refs or [f"{DEFAULT_ICON_LIBRARY}/{icon_name}" for icon_name in sorted(available_icons)]
    if not candidate_refs:
        raise RunnerError(f"No available icons found in {ICON_LIBRARY_DIR}")

    digest = hashlib.sha256(f"{entry_filename}:{invalid_ref}".encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(candidate_refs)
    return candidate_refs[index]


def auto_repair_invalid_svg_icons(
    svg_path: Path,
    text: str,
    available_icons: set[str],
) -> tuple[str, list[tuple[str, str]]]:
    icon_refs = re.findall(r'data-icon="([^"]+)"', text)
    invalid_icon_refs: list[str] = []
    used_icon_refs = {
        ref
        for ref in icon_refs
        if ref.startswith(f"{DEFAULT_ICON_LIBRARY}/") and ref.split("/", 1)[1] in available_icons
    }

    for ref in icon_refs:
        if not ref.startswith(f"{DEFAULT_ICON_LIBRARY}/"):
            invalid_icon_refs.append(ref)
            continue
        icon_name = ref.split("/", 1)[1]
        if icon_name not in available_icons:
            invalid_icon_refs.append(ref)

    if not invalid_icon_refs:
        return text, []

    replacements: list[tuple[str, str]] = []
    updated_text = text
    for invalid_ref in sorted(set(invalid_icon_refs)):
        replacement_ref = choose_fallback_icon_ref(svg_path.name, invalid_ref, used_icon_refs, available_icons)
        updated_text = updated_text.replace(f'data-icon="{invalid_ref}"', f'data-icon="{replacement_ref}"')
        replacements.append((invalid_ref, replacement_ref))
        used_icon_refs.add(replacement_ref)

    if updated_text != text:
        svg_path.write_text(updated_text, encoding="utf-8")
    return updated_text, replacements


def load_svg_auto_repair_anchor(project_path: Path) -> dict[str, Any] | None:
    anchor_path = project_path / "runner" / "svg_anchor_context.json"
    if not anchor_path.exists():
        return None
    try:
        return json.loads(anchor_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def auto_repair_svg_before_validation(
    project_path: Path,
    svg_path: Path,
    anchor: dict[str, Any] | None,
    log_path: Path | None = None,
) -> dict[str, Any] | None:
    """Run deterministic SVG repair before deciding whether AI follow-up is needed."""
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    try:
        from svg_auto_repair import repair_svg_file  # type: ignore
    except Exception as exc:
        if log_path is not None:
            append_log(log_path, f"SVG pre-validation repair unavailable for {svg_path.name}: {exc}")
        return None

    try:
        report = repair_svg_file(svg_path, anchor, dry_run=False)
    except Exception as exc:
        if log_path is not None:
            append_log(log_path, f"SVG pre-validation repair failed for {svg_path.name}: {exc}")
        return None

    if log_path is not None and (report.get("modified") or not report.get("valid_xml", True)):
        repairs = report.get("repairs") or []
        repair_text = "; ".join(str(item) for item in repairs) if repairs else "no deterministic repair"
        append_log(
            log_path,
            f"SVG pre-validation repair {svg_path.name}: "
            f"modified={bool(report.get('modified'))} valid_xml={bool(report.get('valid_xml', True))}; "
            f"{repair_text}",
        )
    return report


def build_spec_review_input(
    project_path: Path,
    plan: list[SlidePlanEntry],
    valid_chart_keys: set[str],
    icon_reference_path: Path,
    icon_inventory_path: Path,
) -> dict[str, Any]:
    design_spec_path = project_path / "design_spec.md"
    if not design_spec_path.exists():
        return {
            "status": "missing_design_spec",
            "issues": ["design_spec.md is missing"],
        }

    content = design_spec_path.read_text(encoding="utf-8", errors="replace")
    available_icons = load_available_icons()
    invalid_icon_refs = find_invalid_icon_refs(content, available_icons)
    invalid_chart_refs = find_unknown_chart_references(content, valid_chart_keys)
    deterministic_issues = validate_design_spec(project_path, plan, valid_chart_keys, strict_icons=False)

    icon_replacements = [
        {
            "invalid_icon": ref,
            "suggested_replacements": suggest_icon_replacements(ref, available_icons),
        }
        for ref in invalid_icon_refs
    ]

    return {
        "design_spec_path": str(design_spec_path),
        "icon_candidate_path": str(icon_reference_path),
        "icon_inventory_path": str(icon_inventory_path),
        "review_focus_slides": list(REVIEW_FOCUS_SLIDES),
        "deterministic_issues": deterministic_issues,
        "invalid_icon_refs": icon_replacements,
        "unknown_chart_refs": invalid_chart_refs,
    }


def repair_design_spec(
    project_path: Path,
    valid_chart_keys: set[str],
    *,
    log_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    design_spec_path = project_path / "design_spec.md"
    report: dict[str, Any] = {
        "status": "missing_design_spec",
        "design_spec_path": str(design_spec_path),
        "icon_fixes": [],
        "icon_format_fixes": [],
        "chart_fixes": [],
    }
    if not design_spec_path.exists():
        if report_path is not None:
            write_json(report_path, report)
        return report

    content = design_spec_path.read_text(encoding="utf-8", errors="replace")
    updated = content
    available_icons = load_available_icons()

    icon_fixes: list[dict[str, str]] = []
    for invalid_ref in find_invalid_icon_refs(updated, available_icons):
        suggestions = suggest_icon_replacements(invalid_ref, available_icons, limit=1)
        replacement = suggestions[0] if suggestions else choose_fallback_icon_ref(
            design_spec_path.name,
            invalid_ref,
            set(extract_icon_refs_from_text(updated)),
            available_icons,
        )
        updated = updated.replace(invalid_ref, replacement)
        icon_fixes.append({"invalid": invalid_ref, "replacement": replacement})

    updated, icon_format_fixes = normalize_design_spec_icon_inventory(updated)

    section_header = "## VII. Visualization Reference List"
    next_header = "## VIII. Image Resource List"
    section_vii = extract_markdown_section(updated, section_header, next_header)
    chart_fixes: list[dict[str, str]] = []
    if section_vii:
        updated_section = section_vii
        for invalid_name in find_unknown_chart_references(updated, valid_chart_keys):
            suggestions = suggest_chart_replacements(invalid_name, valid_chart_keys, limit=1)
            if not suggestions:
                continue
            replacement = suggestions[0]
            updated_section = updated_section.replace(
                f"templates/charts/{invalid_name}.svg",
                f"templates/charts/{replacement}.svg",
            )
            updated_section = re.sub(
                rf"\b{re.escape(invalid_name)}\b",
                replacement,
                updated_section,
            )
            chart_fixes.append({"invalid": invalid_name, "replacement": replacement})
        if updated_section != section_vii:
            updated = updated.replace(section_vii, updated_section, 1)

    if updated != content:
        design_spec_path.write_text(updated, encoding="utf-8")
        if log_path is not None:
            if icon_fixes:
                append_log(log_path, f"Spec repair: fixed icon refs {icon_fixes}")
            if icon_format_fixes:
                append_log(log_path, f"Spec repair: normalized icon inventory format {icon_format_fixes}")
            if chart_fixes:
                append_log(log_path, f"Spec repair: fixed chart refs {chart_fixes}")
    elif log_path is not None:
        append_log(log_path, "Spec repair: no icon/chart fixes needed")

    report = {
        "status": "repaired" if updated != content else "clean",
        "design_spec_path": str(design_spec_path),
        "icon_fixes": icon_fixes,
        "icon_format_fixes": icon_format_fixes,
        "chart_fixes": chart_fixes,
    }
    if report_path is not None:
        write_json(report_path, report)
    return report


def load_source_image_reference(project_path: Path) -> list[dict[str, Any]]:
    path = project_path / RUNNER_DIRNAME / SOURCE_IMAGE_REFERENCE_FILENAME
    if not path.exists():
        return []
    try:
        payload = read_json_any(path)
    except RunnerError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def validate_source_images_in_design_spec(project_path: Path, design_spec_text: str) -> list[str]:
    errors: list[str] = []
    for item in load_source_image_reference(project_path):
        if not item.get("required"):
            continue
        project_image = item.get("project_image")
        if not isinstance(project_image, str) or not project_image:
            continue
        image_name = Path(project_image).name
        if project_image not in design_spec_text and image_name not in design_spec_text:
            slide_note = item.get("slide") or item.get("heading") or "assigned slide"
            errors.append(
                "design_spec.md is missing required source image "
                f"{project_image} for {slide_note}; add it to Section VIII and the slide layout"
            )
    return errors


def validate_design_spec(
    project_path: Path,
    plan: list[SlidePlanEntry],
    valid_chart_keys: set[str],
    *,
    strict_icons: bool,
) -> list[str]:
    design_spec_path = project_path / "design_spec.md"
    if not design_spec_path.exists():
        return ["Missing design_spec.md"]

    content = design_spec_path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []

    for header in DESIGN_SPEC_REQUIRED_HEADERS:
        if header not in content:
            errors.append(f"design_spec.md missing required section: {header}")

    if "### Part " not in content:
        errors.append("design_spec.md content outline is not grouped into Part chapters")

    icon_section = extract_markdown_section(
        content,
        "## VI. Icon Usage",
        "## VII. Visualization Reference List",
    )
    if f"`{DEFAULT_ICON_LIBRARY}/" not in icon_section:
        errors.append(f"design_spec.md does not lock the icon library to `{DEFAULT_ICON_LIBRARY}`")

    icon_mentions = re.findall(rf"`{re.escape(DEFAULT_ICON_LIBRARY)}/[^`]+`", icon_section)
    content_slide_count = len([entry for entry in plan if entry.kind == "content"])
    minimum_icon_rows = min(6, max(ICON_COVERAGE_MIN_SLIDES, math.ceil(content_slide_count * 0.3)))
    if len(icon_mentions) < minimum_icon_rows:
        errors.append(
            "design_spec.md icon inventory is too thin; "
            f"expected at least {minimum_icon_rows} `{DEFAULT_ICON_LIBRARY}/...` entries, got {len(icon_mentions)}"
        )

    unknown_chart_refs = find_unknown_chart_references(content, valid_chart_keys)
    if unknown_chart_refs:
        errors.append(
            "design_spec.md references unknown visualization templates: "
            + ", ".join(unknown_chart_refs)
        )

    errors.extend(validate_source_images_in_design_spec(project_path, content))

    if strict_icons:
        invalid_icon_refs = find_invalid_icon_refs(content, load_available_icons())
        if invalid_icon_refs:
            errors.append(
                "design_spec.md references invalid icon names: "
                + ", ".join(invalid_icon_refs)
            )

    return errors


def validate_svg_outputs(
    project_path: Path,
    plan: list[SlidePlanEntry],
    log_path: Path | None = None,
    *,
    emoji_as_error: bool = True,
) -> list[str]:
    svg_dir = project_path / "svg_output"
    errors: list[str] = []
    icon_slide_count = 0
    content_slide_count = 0
    available_icons = load_available_icons()
    repair_anchor = load_svg_auto_repair_anchor(project_path)

    for entry in plan:
        svg_path = svg_dir / entry.filename
        if not svg_path.exists():
            continue

        text = svg_path.read_text(encoding="utf-8", errors="replace")
        text, _icon_repairs = auto_repair_invalid_svg_icons(svg_path, text, available_icons)
        auto_repair_svg_before_validation(project_path, svg_path, repair_anchor, log_path)
        text = svg_path.read_text(encoding="utf-8", errors="replace")
        try:
            ET.fromstring(text)
        except ET.ParseError as exc:
            errors.append(f"Invalid SVG XML: {entry.filename} ({exc})")
            continue

        if contains_emoji(text):
            message = f"SVG contains emoji text instead of icon-library icons: {entry.filename}"
            if emoji_as_error:
                errors.append(message)
            elif log_path is not None:
                append_log(log_path, f"SVG emoji warning ignored for generation follow-up: {entry.filename}")

        icon_refs = re.findall(r'data-icon="([^"]+)"', text)
        invalid_icon_refs: list[str] = []
        for ref in icon_refs:
            if not ref.startswith(f"{DEFAULT_ICON_LIBRARY}/"):
                invalid_icon_refs.append(ref)
                continue
            icon_name = ref.split("/", 1)[1]
            if icon_name not in available_icons:
                invalid_icon_refs.append(ref)
        if invalid_icon_refs:
            errors.append(
                f"SVG uses invalid or non-existent icon refs in {entry.filename}: {', '.join(sorted(set(invalid_icon_refs)))}"
            )

        if entry.kind == "content":
            content_slide_count += 1
            if icon_refs:
                icon_slide_count += 1

    if content_slide_count:
        minimum_icon_slides = 1
        if icon_slide_count < minimum_icon_slides:
            errors.append(
                "Too few content SVGs use icon placeholders; "
                f"expected at least {minimum_icon_slides}, got {icon_slide_count}"
            )

    return errors


def check_svg_only_state(
    project_path: Path,
    plan: list[SlidePlanEntry],
    valid_chart_keys: set[str],
    runner_dir: Path,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    expected_svg_names = collect_expected_svg_names(plan)
    svg_dir = project_path / "svg_output"
    errors.extend(validate_design_spec(project_path, plan, valid_chart_keys, strict_icons=True))

    actual_svg_names = {path.name for path in svg_dir.glob("*.svg")}
    missing_svg = sorted(expected_svg_names - actual_svg_names)
    extra_svg = sorted(actual_svg_names - expected_svg_names)
    if missing_svg:
        errors.append(f"Missing SVG files: {', '.join(missing_svg)}")
    if extra_svg:
        errors.append(f"Unexpected SVG files: {', '.join(extra_svg)}")

    errors.extend(validate_svg_outputs(project_path, plan, runner_dir / "runner.log", emoji_as_error=False))
    errors.extend(run_svg_quality_check(project_path, runner_dir))
    return not errors, errors


def check_batch_state(
    project_path: Path,
    batch_plan: list[SlidePlanEntry],
    full_plan: list[SlidePlanEntry],
    log_path: Path | None = None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    svg_dir = project_path / "svg_output"
    expected_batch_names = collect_expected_svg_names(batch_plan)
    all_expected_names = collect_expected_svg_names(full_plan)
    actual_svg_names = {path.name for path in svg_dir.glob("*.svg")}

    missing_svg = sorted(expected_batch_names - actual_svg_names)
    extra_svg = sorted(actual_svg_names - all_expected_names)
    if missing_svg:
        errors.append(f"Missing batch SVG files: {', '.join(missing_svg)}")
    if extra_svg:
        errors.append(f"Unexpected SVG files: {', '.join(extra_svg)}")

    errors.extend(validate_svg_outputs(project_path, batch_plan, log_path, emoji_as_error=False))
    return not errors, errors


def check_notes_state(
    project_path: Path,
    plan: list[SlidePlanEntry],
    log_path: Path | None = None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    notes_path = project_path / "notes" / "total.md"
    if not notes_path.exists():
        errors.append("Missing notes/total.md")
        return False, errors

    repair_notes_headings(project_path, plan, log_path=log_path)
    expected_note_headings = [entry.note_heading for entry in plan]
    actual_note_headings = parse_notes_headings(notes_path)
    if actual_note_headings != expected_note_headings:
        errors.append(
            "notes/total.md headings do not exactly match slide filenames: "
            f"expected {expected_note_headings}, got {actual_note_headings}"
        )
    return not errors, errors


def check_spec_state(
    project_path: Path,
    plan: list[SlidePlanEntry],
    valid_chart_keys: set[str],
) -> tuple[bool, list[str]]:
    errors = validate_design_spec(project_path, plan, valid_chart_keys, strict_icons=False)
    return not errors, errors


def check_review_state(
    project_path: Path,
    plan: list[SlidePlanEntry],
    valid_chart_keys: set[str],
    review_report_path: Path,
) -> tuple[bool, list[str]]:
    errors = validate_design_spec(project_path, plan, valid_chart_keys, strict_icons=True)
    if not review_report_path.exists():
        errors.append(f"Missing {review_report_path.name}")
    else:
        try:
            payload = json.loads(review_report_path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {review_report_path.name}: {exc}")
        else:
            if not isinstance(payload, dict):
                errors.append(f"{review_report_path.name} must be a JSON object")
            else:
                if not payload.get("status"):
                    errors.append(f"{review_report_path.name} is missing status")
                if "summary" not in payload:
                    errors.append(f"{review_report_path.name} is missing summary")
    return not errors, errors


def build_sentinel_variants(prefix: str) -> set[str]:
    base = prefix.strip()
    return {
        base,
        base.replace("_", ""),
        base.replace("_", " "),
    }


def run_svg_quality_check(project_path: Path, runner_dir: Path) -> list[str]:
    """Run svg_quality_checker.py and return per-file error details.

    Instead of returning a single generic message, we parse the checker's
    JSON export and surface each individual error string so that
    ``deterministic_issues`` presented to the AI reviewer contains the
    precise coordinates and correction suggestions.
    """
    report_path = runner_dir / SVG_QUALITY_REPORT_FILENAME
    command = [
        sys.executable,
        str(REPO_ROOT / "skills" / "ppt-master" / "scripts" / "svg_quality_checker.py"),
        str(project_path),
        "--export",
        "--output",
        str(report_path),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode == 0:
        return []

    # Try to parse the exported report for detailed errors
    errors: list[str] = []
    try:
        report_text = report_path.read_text(encoding="utf-8", errors="replace")
        # The report format has lines like "  - Chart sector 2 inner start..."
        current_file = ""
        for line in report_text.splitlines():
            if line.startswith("[ERROR] Failed - "):
                current_file = line.split(" - ", 1)[1].strip()
            elif line.strip().startswith("- ") and current_file:
                error_detail = line.strip().removeprefix("- ").strip()
                errors.append(f"[{current_file}] {error_detail}")
    except Exception:
        pass

    if not errors:
        errors.append(f"svg_quality_checker reported SVG errors; see {report_path}")
    return errors


def is_recoverable_svg_notes_failure(
    stage_name: str,
    returncode: int,
    generation_errors: list[str],
) -> bool:
    if stage_name != "svg_generation" or returncode == 0:
        return False
    return bool(generation_errors) and all(item == "Missing notes/total.md" for item in generation_errors)


def select_executor_style_reference(project_path: Path) -> Path:
    design_spec_path = project_path / "design_spec.md"
    if not design_spec_path.exists():
        return QWEN_EXECUTOR_GENERAL_PATH

    content = design_spec_path.read_text(encoding="utf-8", errors="replace").lower()
    if any(token in content for token in ("consulting", "consultant", "mckinsey", "mbb")):
        return QWEN_EXECUTOR_CONSULTANT_PATH
    return QWEN_EXECUTOR_GENERAL_PATH


def classify_turn(
    stdout: str,
    stderr: str,
    latest_assistant_text: str,
    completion_sentinel_prefix: str = COMPLETION_SENTINEL_PREFIX,
) -> str:
    haystacks = [latest_assistant_text, stdout, stderr]
    sentinel_variants = build_sentinel_variants(completion_sentinel_prefix)
    if any(any(variant in text for variant in sentinel_variants) for text in haystacks):
        return "complete"

    combined = "\n".join(text for text in haystacks if text)
    stderr_lower = stderr.lower()
    stdout_lower = stdout.lower()
    if (
        "traceback" in stderr_lower
        or "exception" in stderr_lower
        or "[error]" in stderr_lower
        or "error:" in stderr_lower
        or "[error]" in stdout_lower
    ):
        return "error"

    if any(pattern in combined for pattern in TEMPLATE_BLOCKING_PATTERNS):
        return "template_blocked"
    if any(pattern in combined for pattern in CONFIRMATION_BLOCKING_PATTERNS):
        return "confirm_blocked"
    return "ordinary"


def build_slide_plan_text(plan: list[SlidePlanEntry]) -> str:
    lines: list[str] = []
    for entry in plan:
        source = []
        if entry.source_h2:
            source.append(f'H2="{entry.source_h2}"')
        if entry.source_h3:
            source.append(f'H3="{entry.source_h3}"')
        source_text = ", ".join(source) if source else "synthetic"
        absorb_note = ""
        if entry.absorb_parent_intro:
            absorb_note = " | must absorb intro text under parent H2 before the first H3"
        lines.append(
            f"- {entry.filename} | {entry.kind} | title: {entry.heading} | source: {source_text}{absorb_note}"
        )
    return "\n".join(lines)


def split_plan_into_batches(
    plan: list[SlidePlanEntry],
    batch_size: int,
    batch_partition: str | None = None,
) -> list[list[SlidePlanEntry]]:
    if not plan:
        return []

    partition = (batch_partition or "fixed").strip().lower()
    if partition in {"2+3+4+5+6+7+8", "ramp", "ramp_2_3_4_5_6_7_8"}:
        batches: list[list[SlidePlanEntry]] = []
        cursor = 0
        for size in RAMP_BATCH_SIZES:
            if cursor >= len(plan):
                break
            batches.append(plan[cursor : min(cursor + size, len(plan))])
            cursor += size
        if cursor < len(plan):
            batches.append(plan[cursor:])
        if len(batches) >= 2 and len(batches[-1]) == 1:
            batches[-2].extend(batches[-1])
            batches.pop()
        return batches

    if partition == "anchor_even":
        sizes = split_anchor_even_batch_sizes(len(plan))
        batches = []
        cursor = 0
        for size in sizes:
            if cursor >= len(plan):
                break
            batches.append(plan[cursor : min(cursor + size, len(plan))])
            cursor += size
        if cursor < len(plan):
            batches.append(plan[cursor:])
        if len(batches) >= 2 and len(batches[-1]) == 1:
            batches[-2].extend(batches[-1])
            batches.pop()
        return batches

    if partition != "fixed" and is_valid_batch_partition(partition):
        sizes, repeat_last = parse_numeric_batch_partition(partition)
        batches = []
        cursor = 0
        index = 0
        while cursor < len(plan):
            if index < len(sizes):
                size = sizes[index]
            elif repeat_last:
                size = sizes[-1]
            else:
                size = len(plan) - cursor
            batches.append(plan[cursor : min(cursor + size, len(plan))])
            cursor += size
            index += 1
        if len(batches) >= 2 and len(batches[-1]) == 1:
            batches[-2].extend(batches[-1])
            batches.pop()
        return batches

    return [plan[index : index + batch_size] for index in range(0, len(plan), batch_size)]


def read_json_any(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_batch_reference_file(
    source_path: Path,
    output_path: Path,
    batch_plan: list[SlidePlanEntry],
) -> Path:
    payload = read_json_any(source_path)
    batch_names = {entry.filename for entry in batch_plan}

    filtered = payload
    if isinstance(payload, list):
        filtered = [
            item
            for item in payload
            if not isinstance(item, dict)
            or item.get("slide") in batch_names
        ]
    elif isinstance(payload, dict):
        filtered = {
            key: value
            for key, value in payload.items()
            if not isinstance(value, dict)
            or value.get("slide") in batch_names
            or key in batch_names
        }

    write_json(output_path, filtered)
    return output_path


def build_spec_bootstrap_prompt(
    request: dict[str, Any],
    project_path: Path,
    imported_markdown_path: Path,
    strategist_skill_pack_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    chart_reference_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    plan: list[SlidePlanEntry],
) -> str:
    total_pages = len(plan)
    return f"""You are in the Strategist phase for an already-initialized PPT Master project.

Read these files before doing anything else:
1. {strategist_skill_pack_path}
2. {slide_plan_path}
3. {slide_digest_path}
4. {chart_reference_path}
5. {icon_reference_path}
6. {source_image_reference_path}
7. {imported_markdown_path}

Project boundaries:
- Project path: {project_path}
- Do not re-run `project_manager init` or `import-sources`
- Do not run `total_md_split.py`, `finalize_svg.py`, or `svg_to_pptx.py`
- Only produce or update:
  - {project_path / "design_spec.md"}
- Do NOT create any SVG files in this stage
- Do NOT create `notes/total.md` in this stage

Hard constraints:
- Use free design. Do not use a page template.
- For this local test run, use a light theme. Do not use a dark theme.
- Free design does NOT mean inventing arbitrary asset names. Visualization templates must come only from `{chart_reference_path}` and `templates/charts/`.
- Lock the icon library to `{DEFAULT_ICON_LIBRARY}`. Do not mix icon libraries.
- Use the icon candidates in `{icon_reference_path}` as the default icon source.
- Treat `{source_image_reference_path.name}` as the authoritative list of real source-document images. Each image is bound to the source chapter and assigned slide shown in that file.
- Every required source image must appear in Section VIII. Image Resource List with its exact `project_image` path, assigned slide, and purpose. Do not replace a real source image with an invented pending/placeholder image.
- Every slide listed in `{source_image_reference_path.name}` must choose an image-aware or mixed-media layout in Section IX and mention the exact source image path for that slide.
- Keep source images in their originating chapter/slide; do not move them to unrelated slides.
- Do not use emoji as visual bullets, markers, or pseudo-icons. Use only the locked icon library and normal SVG shapes.
- Use only icon names that actually exist in `{DEFAULT_ICON_LIBRARY}`.
- Content pages must include 1-3 semantic `data-icon="{DEFAULT_ICON_LIBRARY}/..."` placeholders by default. Only skip icons on a content page if that page is dominated by one primary chart or image.
- In `design_spec.md` section VI Recommended Icon List, the `Icon Path` cell must be a raw backticked path like `{DEFAULT_ICON_LIBRARY}/video-camera`; do not use `{{{{icon:{DEFAULT_ICON_LIBRARY}/video-camera}}}}` there.
- Do not invent new chart or icon names outside the reference files unless the real template catalog clearly requires a justified override.
- Keep the downstream SVG execution anchor-friendly: do not invent page-specific header/footer coordinate systems that would break a fixed top bar, title zone, icon zone, or footer zone across the deck.
- Follow the exact Design Spec template structure from `design_spec_reference.md` with sections I through XI.
- In the Design Spec content outline, group slides under `### Part N: ...` chapter headings.
- In the Design Spec icon inventory, include enough `{DEFAULT_ICON_LIBRARY}/...` icons for downstream execution.
- In the Design Spec visualization section, reference only real templates from `templates/charts/<name>.svg`.
- Treat resource-only sections such as image-resource notes as `VIII. Image Resource List`, not as standalone slides.
- Canvas format: {request["canvas_format"]}
- Total page count must be exactly {total_pages}
- No TOC page
- No section header / chapter divider page
- Must include cover and ending pages
- Content density should be moderately high
- Stay faithful to the source markdown and emphasize key points
{LANGUAGE_CONSISTENCY_RULE}
- For H2 `创新技术` and `产业验证`, do not create a parent H2 slide; create one slide per H3 instead.
- If those H2 sections contain intro text before the first H3, absorb that intro into the first child slide.
- For all other H2 sections, create one slide per H2 and absorb H3 details into that slide.

Output constraints:
- This stage must stop after a valid `design_spec.md` is written
- After writing `design_spec.md`, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

Exact slide plan:
{build_slide_plan_text(plan)}

Automation rules:
- If the skill flow still requires a blocking confirmation, ask only once; the caller will resume the same session
- Do not ask unrelated clarification questions
- When the design spec is complete, print exactly one final sentinel line:
{SPEC_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_spec_confirmation_prompt(plan: list[SlidePlanEntry], request: dict[str, Any]) -> str:
    return f"""Approved. Continue generation in the same session.

Keep these constraints locked:
- Template choice: B) Free design
- Theme: Light theme only
- Canvas: {request["canvas_format"]}
- Total page count: exactly {len(plan)}
- No TOC page
- No section header / chapter divider page
- Cover and ending pages are required
- Content density should stay moderately high
- Stay faithful to the source and highlight key points
{LANGUAGE_CONSISTENCY_RULE}
- Lock icon usage to `{DEFAULT_ICON_LIBRARY}` only
- Do not use emoji in the design spec
- Use only real visualization templates from `templates/charts/`
- Generate only `design_spec.md` in this stage
- Do not create SVG or notes files yet
- Do not stop again for another confirmation
- After writing `design_spec.md`, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

Finish `design_spec.md`, then print exactly one line:
{SPEC_COMPLETION_SENTINEL_PREFIX}
"""


def build_spec_continue_prompt(
    request: dict[str, Any],
    project_path: Path,
    plan: list[SlidePlanEntry],
    generation_errors: list[str],
    strategist_skill_pack_path: Path,
) -> str:
    bullet_errors = "\n".join(f"- {item}" for item in generation_errors)
    return f"""Continue this same task. Do not restart and do not recreate the project.

Project path: {project_path}
The current output is still failing these checks:
{bullet_errors}

Repair the existing files in place and keep all original hard constraints:
- Before repairing, re-read `{strategist_skill_pack_path.name}`
- free design
- light theme only
- no TOC page
- no section header page
- total page count must stay exactly {len(plan)}
- cover and ending pages are required
- stay faithful to the source and keep the content dense
{LANGUAGE_CONSISTENCY_RULE}
- keep icon usage locked to `{DEFAULT_ICON_LIBRARY}`
- do not use emoji in the design spec
- use only real visualization templates from `templates/charts/`
- do not create any SVG or notes files in this stage
- After repairing `design_spec.md`, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

When `design_spec.md` satisfies the checks, print exactly one line:
{SPEC_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_review_bootstrap_prompt(
    request: dict[str, Any],
    project_path: Path,
    review_input_path: Path,
    review_report_path: Path,
    review_skill_pack_path: Path,
) -> str:
    return f"""You are in the Design Spec review gate for PPT Master.

Read these files before doing anything else:
1. {review_skill_pack_path}
2. {project_path / "design_spec.md"}
3. {review_input_path}

Review boundaries:
- Project path: {project_path}
- You may edit only:
  - {project_path / "design_spec.md"}
  - {review_report_path}
- Do NOT create SVG files
- Do NOT create notes files
- Do NOT change the slide plan or page count

Review checklist:
1. All icon names in the design spec must exist in `{DEFAULT_ICON_LIBRARY}`
2. All chart template names must exist in `templates/charts/`
3. No emoji should appear in the design spec
4. Reassess these pages with extra care: {", ".join(REVIEW_FOCUS_SLIDES)}
5. Improve weak icon choices or weak visualization choices when a clearly better existing option fits
6. Keep the deck in light theme and free design
7. Preserve downstream anchorability: reviewed layouts should still support a stable header/title/icon/footer geometry across long sequential SVG generation
8. Preserve the language lock from the source document; do not translate design_spec.md or downstream visible content into another language

Output requirements:
- Repair `design_spec.md` if needed
- Write `{review_report_path.name}` as JSON with:
  - `status`
  - `summary`
  - `issues_found`
  - `issues_fixed`
  - `remaining_risks`
- After writing the required files, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.
- When review is complete, print exactly:
{REVIEW_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_review_continue_prompt(
    project_path: Path,
    review_report_path: Path,
    generation_errors: list[str],
    review_skill_pack_path: Path,
) -> str:
    bullet_errors = "\n".join(f"- {item}" for item in generation_errors)
    return f"""Continue the design-spec review gate.

Project path: {project_path}
The review is still failing these checks:
{bullet_errors}

Repair only:
- {project_path / "design_spec.md"}
- {review_report_path}
- Before repairing, re-read `{review_skill_pack_path.name}`

Do not generate SVG or notes in this stage.
After writing the required files, do not output any explanation, summary, file list, or confirmation text.
When review is complete, print exactly one line:
{REVIEW_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_svg_bootstrap_prompt(
    request: dict[str, Any],
    project_path: Path,
    imported_markdown_path: Path,
    slide_plan_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    executor_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
) -> str:
    total_pages = len(plan)
    exact_filenames = ", ".join(entry.filename for entry in plan)
    return f"""You are in the Executor phase for an already-initialized PPT Master project.

Read these files before doing anything else:
1. {executor_skill_pack_path}
2. {project_path / "design_spec.md"}
3. {slide_plan_path}
4. {icon_reference_path}
5. {source_image_reference_path}
6. {svg_anchor_context_path}
7. {imported_markdown_path}

Project boundaries:
- Project path: {project_path}
- Do not edit the slide plan
- Do not rewrite `design_spec.md` unless a minor fix is absolutely required for valid SVG generation
- Do not run `total_md_split.py`, `finalize_svg.py`, or `svg_to_pptx.py`
- Produce only:
  - {project_path / "svg_output"}
- Do NOT create `notes/total.md` in this stage

Executor constraints:
- Use the reviewed `design_spec.md` as the single source of truth
{LANGUAGE_CONSISTENCY_RULE}
- Keep free design and light theme
- Treat `{SVG_DESIGN_COOKBOOK_PATH.name}` as a mandatory SVG visual design guide after design-parameter confirmation
- Use the full cookbook copy embedded in `{executor_skill_pack_path.name}`; do not separately read generic workflow docs such as `AGENTS.md`, `QWEN.md`, `SKILL.md`, or `repo_skill.md` during SVG generation
- Treat `{svg_anchor_context_path.name}` as the immutable execution anchor for geometry, defs, icon placement, footer position, and filename consistency
- Treat `{executor_style_path.name}` as the style-specific visual execution guide for this deck
- Use only real `templates/charts/<name>.svg` references from the design spec
- Treat `{source_image_reference_path.name}` as the authoritative map from source-document images to assigned slides. When a slide is listed there, use the exact `svg_href` from that file and an image-aware layout unless the reviewed spec explicitly says the image is intentionally omitted.
- Lock icon usage to `{DEFAULT_ICON_LIBRARY}`
- Do not use emoji in SVG
- Emoji are forbidden everywhere in SVG output: title text, labels, badges, bullets, annotations, and decorative marks
- Never substitute emoji for icons. If an icon is needed, use `data-icon="{DEFAULT_ICON_LIBRARY}/..."` with a real icon name
- Never use characters like `✅`, `❌`, `📌`, `⭐`, `🚀`, `🎯`, `📊`, `🔹`, `🔸`, or similar pictographic glyphs
- Most content slides must include valid `data-icon="{DEFAULT_ICON_LIBRARY}/..."` placeholders
- Every SVG must be valid XML
- Generate pages sequentially in slide-plan order
- Re-read both `{SVG_DESIGN_COOKBOOK_PATH.name}` and `{svg_anchor_context_path.name}` after every {COOKBOOK_REREAD_INTERVAL} completed SVG pages, and immediately if visual quality starts drifting
- Total page count must be exactly {total_pages}
- No TOC page
- No section header page

Output constraints:
- Generate exactly these SVG files, no more and no fewer:
  {exact_filenames}
- Read chart templates before first use, then adapt them creatively instead of copying them verbatim
- Templates are structural references, not full-page presets; keep one clear primary visual structure per page and adapt the rest of the page to support it
- Use this re-anchor cadence during sequential generation: before slides {COOKBOOK_REREAD_INTERVAL + 1}, {COOKBOOK_REREAD_INTERVAL * 2 + 1}, {COOKBOOK_REREAD_INTERVAL * 3 + 1}, etc., pause internally, re-read both `{SVG_DESIGN_COOKBOOK_PATH.name}` and `{svg_anchor_context_path.name}`, check the fixed header/footer/defs/naming anchors internally, and then continue
- Never switch to a second naming convention mid-run. Every SVG filename and every notes heading must continue matching the exact stems in `{slide_plan_path.name}`
- After writing the SVG files, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

Exact slide plan:
{build_slide_plan_text(plan)}

When all SVGs are complete, print exactly one line:
{COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_batch_svg_prompt(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    batch_slide_plan_path: Path,
    batch_digest_path: Path,
    batch_icon_reference_path: Path,
    batch_source_image_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    executor_skill_pack_path: Path,
    batch_plan: list[SlidePlanEntry],
    batch_index: int,
    total_batches: int,
    prev_last_svg_path: Path | None,
) -> str:
    exact_filenames = ", ".join(entry.filename for entry in batch_plan)
    prev_anchor_block = ""
    if prev_last_svg_path is not None:
        prev_anchor_block = f"""
Previous-batch visual anchor:
- Read this completed SVG before generating the current batch: {prev_last_svg_path}
- Keep header/footer/defs/color roles consistent with that page
- Do not reuse the same main layout pattern for the first page of this batch if a clearly different layout can express the content better
"""

    return f"""You are in the Executor SVG batch phase for an already-initialized PPT Master project.

This is batch {batch_index + 1} of {total_batches}. Generate only this batch's SVG files.

Read these files before doing anything else:
1. {executor_skill_pack_path}
2. {project_path / "design_spec.md"}
3. {slide_plan_path}
4. {batch_slide_plan_path}
5. {batch_digest_path}
6. {batch_icon_reference_path}
7. {batch_source_image_reference_path}
8. {svg_anchor_context_path}

Project boundaries:
- Project path: {project_path}
- Generate only this batch's SVG files in `{project_path / "svg_output"}`
- Do NOT create or overwrite `notes/total.md` in this batch stage
- Do NOT rewrite `design_spec.md`
- Do NOT run `total_md_split.py`, `finalize_svg.py`, or `svg_to_pptx.py`

Executor constraints:
- Use the reviewed `design_spec.md` as the single source of truth
{LANGUAGE_CONSISTENCY_RULE}
- Keep free design and light theme
- Treat `{SVG_DESIGN_COOKBOOK_PATH.name}` as the mandatory visual execution guide
- Use the full cookbook copy embedded in `{executor_skill_pack_path.name}`; do not separately read generic workflow docs such as `AGENTS.md`, `QWEN.md`, `SKILL.md`, or `repo_skill.md` during SVG generation
- Treat `{svg_anchor_context_path.name}` as the immutable execution anchor
- Use only real `templates/charts/<name>.svg` references from the design spec
- Treat `{batch_source_image_reference_path.name}` as the source-bound image contract for this batch. For every listed slide, use the exact `svg_href` from that file and an image-aware layout unless the reviewed spec explicitly says the image is intentionally omitted.
- Lock icon usage to `{DEFAULT_ICON_LIBRARY}`
- Do not use emoji in SVG
- Emoji are forbidden everywhere in SVG output: title text, labels, badges, bullets, annotations, and decorative marks
- Never substitute emoji for icons. If an icon is needed, use `data-icon="{DEFAULT_ICON_LIBRARY}/..."` with a real icon name
- Never use characters like `✅`, `❌`, `📌`, `⭐`, `🚀`, `🎯`, `📊`, `🔹`, `🔸`, or similar pictographic glyphs
- Every SVG must be valid XML
- Generate pages sequentially within this batch in the order listed below
- Re-read both `{SVG_DESIGN_COOKBOOK_PATH.name}` and `{svg_anchor_context_path.name}` before the first page of this batch and again if visual quality starts drifting
{prev_anchor_block}
Batch output constraints:
- Generate exactly these SVG files for this batch, no more and no fewer:
  {exact_filenames}
- Do not rename files into another naming convention
- Do not touch already-completed SVG files from earlier batches unless absolutely necessary to repair a structural defect discovered during this batch
- After writing this batch's SVG files, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

Exact batch slide plan:
{build_slide_plan_text(batch_plan)}

When this batch's SVG files are complete, print exactly one line:
{SVG_BATCH_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_svg_confirmation_prompt(plan: list[SlidePlanEntry], request: dict[str, Any]) -> str:
    return f"""Approved. Continue the Executor phase.

Keep these constraints locked:
- Free design
- Light theme only
- Canvas: {request["canvas_format"]}
- Total page count: exactly {len(plan)}
- No TOC page
- No section header / chapter divider page
- Cover and ending pages are required
{LANGUAGE_CONSISTENCY_RULE}
- Lock icon usage to `{DEFAULT_ICON_LIBRARY}` only
- Do not use emoji in SVG
- Use only real visualization templates from `templates/charts/`
- Keep following the loaded executor style guide, image layout rules, and shared SVG standards
- Re-read both `{SVG_DESIGN_COOKBOOK_PATH.name}` and `svg_anchor_context.json` after every {COOKBOOK_REREAD_INTERVAL} completed SVG pages
- Most content slides must include valid `data-icon="{DEFAULT_ICON_LIBRARY}/..."` placeholders
- Generate only SVG in this stage
- After writing the SVG files, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

When done, print exactly one line:
{COMPLETION_SENTINEL_PREFIX}
"""


def build_batch_svg_confirmation_prompt(batch_plan: list[SlidePlanEntry], request: dict[str, Any]) -> str:
    return f"""Approved. Continue the current SVG batch.

Keep these constraints locked:
- Free design
- Light theme only
- Canvas: {request["canvas_format"]}
{LANGUAGE_CONSISTENCY_RULE}
- Lock icon usage to `{DEFAULT_ICON_LIBRARY}` only
- Do not use emoji in SVG
- Use only real visualization templates from `templates/charts/`
- Re-read both `{SVG_DESIGN_COOKBOOK_PATH.name}` and `svg_anchor_context.json` before continuing if quality drifted
- Generate only this batch's SVG files
- Do not write notes in this stage
- After writing this batch's SVG files, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

When done, print exactly one line:
{SVG_BATCH_COMPLETION_SENTINEL_PREFIX}
"""


def build_svg_continue_prompt(
    request: dict[str, Any],
    project_path: Path,
    plan: list[SlidePlanEntry],
    generation_errors: list[str],
    svg_anchor_context_path: Path,
) -> str:
    bullet_errors = "\n".join(f"- {item}" for item in generation_errors)
    notes_only_recovery = bool(generation_errors) and all(
        item == "Missing notes/total.md" for item in generation_errors
    )
    recovery_block = ""
    if notes_only_recovery:
        recovery_block = """- Existing SVG pages already passed the current structural checks.
- Do not rewrite existing SVG files unless you discover a concrete structural defect.
- Only create or repair `notes/total.md` so its headings exactly match the slide-plan SVG filenames.
"""
    return f"""Continue the Executor phase.

Project path: {project_path}
The current output is still failing these checks:
{bullet_errors}

Repair the SVG and notes outputs in place and keep all hard constraints:
- free design
- light theme only
- no TOC page
- no section header page
- total page count must stay exactly {len(plan)}
{LANGUAGE_CONSISTENCY_RULE}
- keep icon usage locked to `{DEFAULT_ICON_LIBRARY}`
- do not use emoji in SVG
- use only real visualization templates from `templates/charts/`
- keep following the loaded executor style guide, image layout rules, and shared SVG standards
- re-read both `{SVG_DESIGN_COOKBOOK_PATH.name}` and `{svg_anchor_context_path.name}` after every {COOKBOOK_REREAD_INTERVAL} completed SVG pages
- most content slides must contain valid `data-icon="{DEFAULT_ICON_LIBRARY}/..."` placeholders
- SVG filenames must exactly match the slide plan
- every SVG must remain valid XML
- before continuing after this interruption, re-read `{svg_anchor_context_path.name}` and check the immutable header/footer/defs/naming anchors internally; do not print that check
{recovery_block}
- After repairing the required files, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

When `svg_output` satisfies the checks, print exactly one line:
{COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_batch_svg_continue_prompt(
    request: dict[str, Any],
    project_path: Path,
    batch_plan: list[SlidePlanEntry],
    generation_errors: list[str],
    svg_anchor_context_path: Path,
) -> str:
    bullet_errors = "\n".join(f"- {item}" for item in generation_errors)
    return f"""Continue the current SVG batch.

Project path: {project_path}
The current batch output is still failing these checks:
{bullet_errors}

Repair only the current batch SVG files in place and keep all hard constraints:
- free design
- light theme only
{LANGUAGE_CONSISTENCY_RULE}
- lock icon usage to `{DEFAULT_ICON_LIBRARY}`
- do not use emoji in SVG
- use only real visualization templates from `templates/charts/`
- re-read both `{SVG_DESIGN_COOKBOOK_PATH.name}` and `{svg_anchor_context_path.name}` before continuing
- do not create or overwrite `notes/total.md` in this batch stage
- do not rename files into another naming convention
- every SVG must remain valid XML
- After repairing this batch's SVG files, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

Current batch slide plan:
{build_slide_plan_text(batch_plan)}

When this batch's SVG files satisfy the checks, print exactly one line:
{SVG_BATCH_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_notes_bootstrap_prompt(
    project_path: Path,
    imported_markdown_path: Path,
    slide_plan_path: Path,
    svg_anchor_context_path: Path,
    notes_skill_pack_path: Path,
) -> str:
    return f"""You are in the speaker-notes completion phase for PPT Master.

Read these files before doing anything else:
1. {notes_skill_pack_path}
2. {project_path / "design_spec.md"}
3. {slide_plan_path}
4. {svg_anchor_context_path}
5. {imported_markdown_path}

Project boundaries:
- Project path: {project_path}
- All SVG files are already generated in `{project_path / "svg_output"}`
- Do NOT rewrite SVG files in this stage
- Do NOT rewrite `design_spec.md`
- Produce only: {project_path / "notes" / "total.md"}

Notes requirements:
- Generate one unified `notes/total.md`
- Each page must start with `# <svg_stem>`
- H1 headings must exactly match the slide-plan SVG stems
{LANGUAGE_CONSISTENCY_RULE}
- Use the reviewed design spec and source markdown as the narrative source of truth
- Write coherent transitions across the full deck; do not treat batches as separate decks
- After writing `notes/total.md`, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

When notes are complete, print exactly one line:
{NOTES_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def build_notes_continue_prompt(
    project_path: Path,
    plan: list[SlidePlanEntry],
    generation_errors: list[str],
) -> str:
    bullet_errors = "\n".join(f"- {item}" for item in generation_errors)
    return f"""Continue the speaker-notes completion phase.

Project path: {project_path}
The notes output is still failing these checks:
{bullet_errors}

Repair only:
- {project_path / "notes" / "total.md"}

Keep these constraints locked:
- Do not rewrite SVG files
- Do not rewrite `design_spec.md`
- Notes headings must exactly match these SVG stems:
  {", ".join(entry.note_heading for entry in plan)}
{LANGUAGE_CONSISTENCY_RULE}
- After repairing `notes/total.md`, do not output any explanation, summary, file list, or confirmation text.
- The only allowed final assistant output is the sentinel line below.

When notes are complete, print exactly one line:
{NOTES_COMPLETION_SENTINEL_PREFIX} {project_path}
"""


def direct_notes_max_tokens() -> int:
    raw = (os.getenv("PPT_API_QWEN_NOTES_MAX_TOKENS") or "").strip()
    if not raw:
        return DIRECT_NOTES_MAX_TOKENS
    try:
        return max(1, min(int(raw), 16384))
    except ValueError:
        return DIRECT_NOTES_MAX_TOKENS


def direct_spec_max_tokens() -> int:
    raw = (os.getenv("PPT_API_QWEN_SPEC_MAX_TOKENS") or "").strip()
    if not raw:
        return DIRECT_SPEC_MAX_TOKENS
    try:
        return max(1, min(int(raw), 65536))
    except ValueError:
        return DIRECT_SPEC_MAX_TOKENS


def strip_markdown_model_output(text: str, sentinel_prefix: str | None = None) -> str:
    stripped = (text or "").strip()
    fence_match = re.match(r"^```(?:markdown|md)?\s*\n(?P<body>.*)\n```$", stripped, re.DOTALL | re.IGNORECASE)
    if fence_match:
        stripped = fence_match.group("body").strip()
    lines = [line.rstrip() for line in stripped.splitlines()]
    if sentinel_prefix:
        lines = [line for line in lines if not line.strip().startswith(sentinel_prefix)]
    return "\n".join(lines).strip() + "\n"


def strip_notes_model_output(text: str) -> str:
    return strip_markdown_model_output(text, NOTES_COMPLETION_SENTINEL_PREFIX)


def notes_usage_from_response(payload: dict[str, Any], model: str) -> TurnUsageSummary:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    prompt_tokens = safe_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
    completion_tokens = safe_int(usage.get("completion_tokens") or usage.get("output_tokens"))
    total_tokens = safe_int(usage.get("total_tokens")) or prompt_tokens + completion_tokens

    cached_tokens = safe_int(usage.get("cached_tokens"))
    for details_key in ("prompt_tokens_details", "input_tokens_details"):
        details = usage.get(details_key)
        if isinstance(details, dict):
            cached_tokens = max(cached_tokens, safe_int(details.get("cached_tokens")))

    thoughts_tokens = safe_int(usage.get("thoughts_tokens"))
    for details_key in ("completion_tokens_details", "output_tokens_details"):
        details = usage.get(details_key)
        if isinstance(details, dict):
            thoughts_tokens = max(
                thoughts_tokens,
                safe_int(details.get("reasoning_tokens") or details.get("thoughts_tokens")),
            )

    return TurnUsageSummary(
        api_calls=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        thoughts_tokens=thoughts_tokens,
        total_tokens=total_tokens,
        tool_tokens=0,
        models=[model],
    )


def direct_chat_usage_from_response(payload: dict[str, Any], model: str) -> TurnUsageSummary:
    return notes_usage_from_response(payload, model)


def call_openai_compatible_chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    runner_dir: Path,
    artifact_prefix: str,
    turn_index: int,
    log_path: Path | None = None,
    timeout_seconds: int = DIRECT_NOTES_TIMEOUT_SECONDS,
    credential_override: dict[str, str] | None = None,
) -> tuple[str, TurnUsageSummary, dict[str, Any]]:
    stage = infer_slot_stage(artifact_prefix)
    label = f"{artifact_prefix}_turn_{turn_index:02d}"
    managed_pool = None
    managed_lease = None
    effective_credential_override = credential_override
    usage: TurnUsageSummary | None = None
    release_error: str | None = None

    try:
        if effective_credential_override is None:
            managed_pool, managed_lease = acquire_runner_account_lease(
                stage=stage,
                label=label,
                runner_dir=runner_dir,
                log_path=log_path,
            )
            if managed_lease is not None:
                effective_credential_override = managed_lease.worker_payload()

        endpoint = resolve_openai_compatible_endpoint(effective_credential_override)
        if endpoint is None:
            raise RunnerError("Direct API requires PPT_API_QWEN_API_KEY and PPT_API_QWEN_BASE_URL")
        api_key, url = endpoint
        effective_model = (effective_credential_override or {}).get("model") or model

        request_payload = {
            "model": effective_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        request_path = runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.request.json"
        safe_payload = dict(request_payload)
        request_path.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        encoded = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        account_id = (effective_credential_override or {}).get("account_id")
        wait_for_qwen_repair_turn_backoff(stage, label=label, turn_index=turn_index, log_path=log_path)
        wait_for_local_qwen_start(stage, label=label, log_path=log_path)
        with acquire_resource_slot(
            stage,
            label=label,
            runner_dir=runner_dir,
            log_path=log_path,
        ):
            request_started = time.time()
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    response_text = response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                error_text = exc.read().decode("utf-8", errors="replace")
                raise RunnerError(f"Direct API HTTP {exc.code}: {error_text}") from exc
            except urllib.error.URLError as exc:
                raise RunnerError(f"Direct API request failed: {exc}") from exc
            elapsed_seconds = time.time() - request_started

        response_path = runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.response.json"
        response_path.write_text(response_text, encoding="utf-8")
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RunnerError(f"Direct API returned invalid JSON: {exc}") from exc

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RunnerError("Direct API returned no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RunnerError("Direct API returned empty content")

        usage = notes_usage_from_response(payload, effective_model)
        record_llm_observation(stage=stage, model=effective_model, usage=usage, elapsed_seconds=elapsed_seconds, log_path=log_path)
        record_live_stage_usage(
            stage,
            usage,
            event_epoch=time.time(),
            session_id=f"direct_{uuid.uuid4().hex}",
            label=label,
            account_id=account_id,
            log_path=log_path,
        )
        (runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.assistant.txt").write_text(content, encoding="utf-8")
        return content, usage, payload
    except Exception as exc:
        release_error = str(exc)
        raise
    finally:
        if managed_pool is not None and managed_lease is not None:
            try:
                managed_pool.release(
                    managed_lease,
                    usage=usage.to_json() if usage is not None else None,
                    error=release_error,
                )
            except Exception:
                pass


def build_direct_notes_messages(
    *,
    project_path: Path,
    imported_markdown_path: Path,
    slide_plan_path: Path,
    svg_anchor_context_path: Path,
    notes_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
    generation_errors: list[str] | None = None,
    current_notes: str | None = None,
) -> list[dict[str, str]]:
    errors_block = ""
    if generation_errors:
        errors_block = "Current notes failed these checks:\n" + "\n".join(f"- {item}" for item in generation_errors)
    current_notes_block = ""
    if current_notes:
        current_notes_block = f"\n\nExisting notes draft to repair:\n```markdown\n{current_notes}\n```"

    exact_headings = "\n".join(f"- {entry.note_heading}" for entry in plan)
    user_content = f"""Generate speaker notes directly as markdown.

Hard output contract:
- Return only the full contents of `notes/total.md`.
- Do not wrap the output in a code fence.
- Do not output explanations, summaries, file lists, or sentinel lines.
- Create exactly {len(plan)} H1 sections.
- Each H1 must be exactly `# <svg_stem>` and must appear in the exact order listed below.
- Do not create extra headings outside this list.
{LANGUAGE_CONSISTENCY_RULE}
- Use the source markdown and design spec as narrative context, but keep the notes concise and presentation-ready.
- Each slide should have 2-5 short paragraphs or bullets suitable for speaker delivery.

Exact H1 heading order:
{exact_headings}

{errors_block}

Notes skill pack:
```markdown
{notes_skill_pack_path.read_text(encoding="utf-8", errors="replace")}
```

Slide plan:
```json
{slide_plan_path.read_text(encoding="utf-8", errors="replace")}
```

SVG anchor context:
```json
{svg_anchor_context_path.read_text(encoding="utf-8", errors="replace")}
```

Design spec:
```markdown
{(project_path / "design_spec.md").read_text(encoding="utf-8", errors="replace")}
```

Source markdown:
```markdown
{imported_markdown_path.read_text(encoding="utf-8", errors="replace")}
```
{current_notes_block}
"""
    return [
        {
            "role": "system",
            "content": "You generate concise PPT speaker notes. You only return the markdown file content requested by the user.",
        },
        {"role": "user", "content": user_content},
    ]


def build_direct_spec_messages(
    *,
    request: dict[str, Any],
    project_path: Path,
    imported_markdown_path: Path,
    strategist_skill_pack_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    chart_reference_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    plan: list[SlidePlanEntry],
    generation_errors: list[str] | None = None,
    current_spec: str | None = None,
) -> list[dict[str, str]]:
    errors_block = ""
    if generation_errors:
        errors_block = "Current design_spec.md failed these checks:\n" + "\n".join(f"- {item}" for item in generation_errors)
    current_spec_block = ""
    if current_spec:
        current_spec_block = f"\n\nExisting design_spec.md draft to repair:\n```markdown\n{current_spec}\n```"

    user_content = f"""Generate `design_spec.md` directly as markdown.

Hard output contract:
- Return only the full contents of `design_spec.md`.
- Do not wrap the output in a code fence.
- Do not output explanations, summaries, file lists, or sentinel lines.
- Follow the exact Design Spec template structure from `design_spec_reference.md` with sections I through XI.
- Group content outline slides under `### Part N: ...` chapter headings.
- Total page count must be exactly {len(plan)}.
- Use free design, light theme only, no TOC page, no section header page.
- Include cover and ending pages.
- Lock icons to `{DEFAULT_ICON_LIBRARY}/...`; use only real icon names from the icon candidates.
- In section VI Recommended Icon List, write icon table cells as raw backticked paths like `{DEFAULT_ICON_LIBRARY}/video-camera`; do not use `{{{{icon:{DEFAULT_ICON_LIBRARY}/video-camera}}}}`.
- Reference only real chart templates from the chart reference.
- Treat source image references as mandatory source-bound assets: each required image must be listed in Section VIII with exact `project_image`, assigned slide, and purpose, and the matching slide in Section IX must use an image-aware or mixed-media layout that references that exact image path.
- Do not replace real source images with invented pending/placeholder image names, and do not move source images away from their originating chapter/slide.
- Do not use emoji in design_spec.md.
- Stay faithful to source markdown and keep content density moderately high.
{LANGUAGE_CONSISTENCY_RULE}

Canvas format: {request["canvas_format"]}
Project path: {project_path}

{errors_block}

Strategist skill pack:
```markdown
{strategist_skill_pack_path.read_text(encoding="utf-8", errors="replace")}
```

Slide plan:
```json
{slide_plan_path.read_text(encoding="utf-8", errors="replace")}
```

Slide content digest:
```json
{slide_digest_path.read_text(encoding="utf-8", errors="replace")}
```

Chart template reference:
```json
{chart_reference_path.read_text(encoding="utf-8", errors="replace")}
```

Icon candidates:
```json
{icon_reference_path.read_text(encoding="utf-8", errors="replace")}
```

Source image reference:
```json
{source_image_reference_path.read_text(encoding="utf-8", errors="replace")}
```

Source markdown:
```markdown
{imported_markdown_path.read_text(encoding="utf-8", errors="replace")}
```
{current_spec_block}
"""
    return [
        {
            "role": "system",
            "content": "You are a senior PPT strategist. You only return the requested markdown file content.",
        },
        {"role": "user", "content": user_content},
    ]


def execute_direct_spec_stage(
    *,
    request: dict[str, Any],
    project_path: Path,
    imported_markdown_path: Path,
    strategist_skill_pack_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    chart_reference_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    plan: list[SlidePlanEntry],
    valid_chart_keys: set[str],
    model: str,
    runner_dir: Path,
    log_path: Path,
) -> str | None:
    stage_name = "spec_generation"
    artifact_prefix = "spec_direct"
    spec_path = project_path / "design_spec.md"
    session_id = f"direct-{uuid.uuid4()}"
    stage_turn_usages: list[TurnUsageSummary] = []
    generation_errors: list[str] | None = None

    for turn_index in range(1, 3):
        messages = build_direct_spec_messages(
            request=request,
            project_path=project_path,
            imported_markdown_path=imported_markdown_path,
            strategist_skill_pack_path=strategist_skill_pack_path,
            slide_plan_path=slide_plan_path,
            slide_digest_path=slide_digest_path,
            chart_reference_path=chart_reference_path,
            icon_reference_path=icon_reference_path,
            source_image_reference_path=source_image_reference_path,
            plan=plan,
            generation_errors=generation_errors,
            current_spec=spec_path.read_text(encoding="utf-8", errors="replace") if spec_path.exists() else None,
        )
        append_log(
            log_path,
            f"Starting direct spec turn {turn_index}: model={model} max_tokens={direct_spec_max_tokens()}",
        )
        try:
            content, usage, _payload = call_openai_compatible_chat(
                model=model,
                messages=messages,
                max_tokens=direct_spec_max_tokens(),
                runner_dir=runner_dir,
                artifact_prefix=artifact_prefix,
                turn_index=turn_index,
                log_path=log_path,
                timeout_seconds=DIRECT_SPEC_TIMEOUT_SECONDS,
            )
        except RunnerError as exc:
            append_log(log_path, f"Direct spec turn {turn_index} failed: {exc}")
            return None

        stage_turn_usages.append(usage)
        append_log(log_path, f"direct spec turn {turn_index} usage {format_usage_summary(usage)}")
        update_usage_summary(
            runner_dir,
            stage_name=stage_name,
            artifact_prefix=artifact_prefix,
            turn_index=turn_index,
            session_id=session_id,
            usage=usage,
        )

        spec_path.write_text(strip_markdown_model_output(content, SPEC_COMPLETION_SENTINEL_PREFIX), encoding="utf-8")
        repair_design_spec(project_path, valid_chart_keys, log_path=log_path, report_path=runner_dir / SPEC_REPAIR_REPORT_FILENAME)
        state_complete, generation_errors = check_spec_state(project_path, plan, valid_chart_keys)
        append_log(
            log_path,
            f"direct spec turn {turn_index}: state_complete={state_complete}; generation_errors={generation_errors}",
        )
        if state_complete:
            append_log(
                log_path,
                f"{stage_name}: direct stage total usage {format_usage_summary(merge_turn_usage(stage_turn_usages))}",
            )
            append_log(log_path, f"{stage_name} completed successfully via direct API")
            return session_id

    return None


def execute_direct_notes_stage(
    *,
    project_path: Path,
    imported_markdown_path: Path,
    slide_plan_path: Path,
    svg_anchor_context_path: Path,
    notes_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
    model: str,
    runner_dir: Path,
    log_path: Path,
) -> str | None:
    stage_name = "notes_generation"
    artifact_prefix = "notes_direct"
    notes_path = project_path / "notes" / "total.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    session_id = f"direct-{uuid.uuid4()}"
    stage_turn_usages: list[TurnUsageSummary] = []
    generation_errors: list[str] | None = None

    for turn_index in range(1, 3):
        messages = build_direct_notes_messages(
            project_path=project_path,
            imported_markdown_path=imported_markdown_path,
            slide_plan_path=slide_plan_path,
            svg_anchor_context_path=svg_anchor_context_path,
            notes_skill_pack_path=notes_skill_pack_path,
            plan=plan,
            generation_errors=generation_errors,
            current_notes=notes_path.read_text(encoding="utf-8", errors="replace") if notes_path.exists() else None,
        )
        append_log(
            log_path,
            f"Starting direct notes turn {turn_index}: model={model} max_tokens={direct_notes_max_tokens()}",
        )
        try:
            content, usage, _payload = call_openai_compatible_chat(
                model=model,
                messages=messages,
                max_tokens=direct_notes_max_tokens(),
                runner_dir=runner_dir,
                artifact_prefix=artifact_prefix,
                turn_index=turn_index,
                log_path=log_path,
                timeout_seconds=DIRECT_NOTES_TIMEOUT_SECONDS,
            )
        except RunnerError as exc:
            append_log(log_path, f"Direct notes turn {turn_index} failed: {exc}")
            return None

        stage_turn_usages.append(usage)
        append_log(log_path, f"direct notes turn {turn_index} usage {format_usage_summary(usage)}")
        update_usage_summary(
            runner_dir,
            stage_name=stage_name,
            artifact_prefix=artifact_prefix,
            turn_index=turn_index,
            session_id=session_id,
            usage=usage,
        )

        notes_path.write_text(strip_notes_model_output(content), encoding="utf-8")
        state_complete, generation_errors = check_notes_state(project_path, plan, log_path=log_path)
        append_log(
            log_path,
            f"direct notes turn {turn_index}: state_complete={state_complete}; generation_errors={generation_errors}",
        )
        if state_complete:
            append_log(
                log_path,
                f"{stage_name}: direct stage total usage {format_usage_summary(merge_turn_usage(stage_turn_usages))}",
            )
            append_log(log_path, f"{stage_name} completed successfully via direct API")
            return session_id

    return None


def execute_qwen_stage(
    *,
    stage_name: str,
    artifact_prefix: str,
    initial_prompt: str,
    completion_sentinel_prefix: str,
    state_checker: Any,
    continue_prompt_builder: Any,
    confirmation_prompt_builder: Any,
    model: str | None,
    runner_dir: Path,
    log_path: Path,
    credential_override: dict[str, str] | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    follow_ups = 0
    turn_index = 1
    resume = False
    next_prompt = initial_prompt
    stage_turn_usages: list[TurnUsageSummary] = []

    while True:
        result = run_qwen_prompt(
            prompt=next_prompt,
            session_id=session_id,
            repo_root=REPO_ROOT,
            model=model,
            resume=resume,
            turn_index=turn_index,
            runner_dir=runner_dir,
            log_path=log_path,
            artifact_prefix=artifact_prefix,
            credential_override=credential_override,
        )
        turn_usage = None
        if isinstance(result.usage, dict):
            turn_usage = TurnUsageSummary(
                api_calls=safe_int(result.usage.get("api_calls")),
                prompt_tokens=safe_int(result.usage.get("prompt_tokens")),
                completion_tokens=safe_int(result.usage.get("completion_tokens")),
                cached_tokens=safe_int(result.usage.get("cached_tokens")),
                thoughts_tokens=safe_int(result.usage.get("thoughts_tokens")),
                total_tokens=safe_int(result.usage.get("total_tokens")),
                tool_tokens=safe_int(result.usage.get("tool_tokens")),
                models=list(result.usage.get("models") or []),
            )
        if turn_usage is not None:
            stage_turn_usages.append(turn_usage)
        append_log(
            log_path,
            f"{stage_name}: turn {turn_index} usage {format_usage_summary(turn_usage)}",
        )
        update_usage_summary(
            runner_dir,
            stage_name=stage_name,
            artifact_prefix=artifact_prefix,
            turn_index=turn_index,
            session_id=session_id,
            usage=turn_usage,
        )

        chat_path = wait_for_chat_recording_path(session_id)
        if chat_path is not None:
            append_log(log_path, f"{stage_name}: chat recording found at {chat_path}")
        debug_path = find_debug_log_path(session_id)
        if debug_path is not None:
            append_log(log_path, f"{stage_name}: Qwen debug log found at {debug_path}")
        latest_assistant_text = read_latest_assistant_message(chat_path, session_id)
        if latest_assistant_text:
            (runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.assistant.txt").write_text(
                latest_assistant_text,
                encoding="utf-8",
            )

        state_complete, generation_errors = state_checker()
        classification = classify_turn(
            result.stdout,
            result.stderr,
            latest_assistant_text,
            completion_sentinel_prefix=completion_sentinel_prefix,
        )
        recoverable_notes_failure = is_recoverable_svg_notes_failure(
            stage_name,
            result.returncode,
            generation_errors,
        )
        timed_out_recoverable = result.timed_out and stage_name.startswith("svg_batch_")
        if timed_out_recoverable:
            if state_complete:
                append_log(
                    log_path,
                    f"{stage_name}: timed-out turn produced valid batch outputs; accepting without sentinel",
                )
                classification = "complete"
            elif classification == "error":
                append_log(
                    log_path,
                    f"{stage_name}: timed-out turn classified as error; treating as incomplete so batch can repair",
                )
                classification = "ordinary"
        if recoverable_notes_failure and classification == "error":
            classification = "incomplete"
        append_log(
            log_path,
            f"{stage_name}: turn {turn_index} classified as {classification}; "
            f"state_complete={state_complete}; recoverable_notes_failure={recoverable_notes_failure}; "
            f"generation_errors={generation_errors}",
        )

        if result.returncode != 0 and not recoverable_notes_failure and not timed_out_recoverable:
            raise RunnerError(
                f"{stage_name} failed with rc={result.returncode}. "
                f"See {runner_dir / f'{artifact_prefix}_turn_{turn_index:02d}.stderr.txt'}"
            )

        if classification == "complete" and state_complete:
            append_log(
                log_path,
                f"{stage_name}: stage total usage {format_usage_summary(merge_turn_usage(stage_turn_usages))}",
            )
            append_log(log_path, f"{stage_name} completed successfully")
            return session_id

        if follow_ups >= DEFAULT_MAX_FOLLOW_UPS:
            raise RunnerError(
                f"Exceeded maximum qwen follow-up turns ({DEFAULT_MAX_FOLLOW_UPS}) during {stage_name}"
            )

        if classification == "error":
            raise RunnerError(
                f"{stage_name} reported an error before completion. "
                f"Latest assistant message: {latest_assistant_text[:500]}"
            )

        if classification in {"template_blocked", "confirm_blocked"}:
            next_prompt = confirmation_prompt_builder(generation_errors)
        else:
            next_prompt = continue_prompt_builder(generation_errors)

        follow_ups += 1
        turn_index += 1
        resume = True


def cleanup_pre_execution_outputs(project_path: Path, log_path: Path) -> None:
    svg_dir = project_path / "svg_output"
    if svg_dir.exists():
        for path in svg_dir.glob("*.svg"):
            path.unlink(missing_ok=True)
        append_log(log_path, f"Cleared pre-existing SVG outputs in {svg_dir}")
    notes_total = project_path / "notes" / "total.md"
    if notes_total.exists():
        notes_total.unlink(missing_ok=True)
        append_log(log_path, f"Removed pre-existing notes file {notes_total}")


def run_qwen_prompt(
    prompt: str,
    session_id: str,
    repo_root: Path,
    model: str | None,
    resume: bool,
    turn_index: int,
    runner_dir: Path,
    log_path: Path,
    artifact_prefix: str = "qwen",
    credential_override: dict[str, str] | None = None,
) -> QwenCallResult:
    stage = infer_slot_stage(artifact_prefix)
    label = f"{artifact_prefix}_turn_{turn_index:02d}"
    managed_pool = None
    managed_lease = None
    effective_credential_override = credential_override
    usage_summary: TurnUsageSummary | None = None
    usage_payload: dict[str, Any] | None = None
    release_error: str | None = None
    completed_stdout = ""
    completed_stderr = ""
    completed_returncode = 0
    elapsed_seconds = 0.0
    timed_out = False

    try:
        if effective_credential_override is None:
            managed_pool, managed_lease = acquire_runner_account_lease(
                stage=stage,
                label=label,
                runner_dir=runner_dir,
                log_path=log_path,
            )
            if managed_lease is not None:
                effective_credential_override = managed_lease.worker_payload()

        effective_model = (effective_credential_override or {}).get("model") or model
        command = resolve_qwen_launcher()
        command.extend(resolve_qwen_cli_auth_args(effective_credential_override))
        existing_chat_path = find_chat_recording_path(session_id)
        existing_chat_line_count = count_file_lines(existing_chat_path)
        if resume:
            command.extend(["--resume", session_id])
        else:
            command.extend(["--session-id", session_id])
        command.extend(["--prompt", "", "--chat-recording", "--approval-mode", "yolo"])
        for tool_name in QWEN_ALLOWED_TOOLS:
            command.extend(["--allowed-tools", tool_name])
        if effective_model:
            command.extend(["--model", effective_model])

        account_id = (effective_credential_override or {}).get("account_id")
        wait_for_qwen_repair_turn_backoff(stage, label=label, turn_index=turn_index, log_path=log_path)
        wait_for_local_qwen_start(stage, label=label, log_path=log_path)
        wait_for_svg_start_jitter(stage, label=f"{runner_dir.name}:{label}", log_path=log_path)
        safe_command = redact_sensitive_command_parts(command)
        account_note = ""
        if account_id:
            account_note = f" account_id={account_id}"
        append_log(log_path, f"Starting qwen turn {turn_index}:{account_note} {' '.join(safe_command)} (prompt via stdin, {len(prompt)} chars)")
        timeout_seconds = qwen_turn_timeout_seconds(stage, artifact_prefix)

        with acquire_svg_budget_lease(
            stage,
            label=f"{runner_dir.name}:{label}",
            runner_dir=runner_dir,
            log_path=log_path,
        ) as svg_budget_lease:
            with acquire_resource_slot(
                stage,
                label=label,
                runner_dir=runner_dir,
                log_path=log_path,
                skip_tpm_pacing=svg_budget_lease is not None,
            ):
                run_started = time.time()
                process = subprocess.Popen(
                    command,
                    cwd=repo_root,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    start_new_session=(os.name != "nt"),
                )
                monitor_thread: Thread | None = None
                if live_usage_enabled(stage):
                    monitor_thread = Thread(
                        target=monitor_qwen_live_usage,
                        kwargs={
                            "process": process,
                            "session_id": session_id,
                            "stage": stage,
                            "label": label,
                            "runner_dir": runner_dir,
                            "artifact_prefix": artifact_prefix,
                            "turn_index": turn_index,
                            "initial_chat_path": existing_chat_path,
                            "initial_line_count": existing_chat_line_count,
                            "account_id": account_id,
                            "log_path": log_path,
                        },
                        name=f"qwen-live-usage-{sanitize_token(label)}",
                        daemon=True,
                    )
                    monitor_thread.start()
                try:
                    stdout_text, stderr_text = process.communicate(input=prompt, timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    append_log(log_path, f"Qwen turn timed out after {timeout_seconds}s; terminating {label}")
                    terminate_qwen_process(process, log_path, label)
                    stdout_text, stderr_text = process.communicate()
                    timeout_message = (
                        f"Qwen turn timed out after {timeout_seconds}s: {label}. "
                        "Process was terminated; runner will validate partial outputs."
                    )
                    stderr_text = (stderr_text or "").rstrip()
                    stderr_text = f"{stderr_text}\n{timeout_message}\n" if stderr_text else f"{timeout_message}\n"
                    if monitor_thread is not None:
                        monitor_thread.join(timeout=max(2.0, live_usage_poll_seconds() * 3))
                elapsed_seconds = time.time() - run_started
                completed_stdout = stdout_text
                completed_stderr = stderr_text
                completed_returncode = 124 if timed_out else safe_int(process.returncode)
                if monitor_thread is not None:
                    monitor_thread.join(timeout=max(2.0, live_usage_poll_seconds() * 3))

        (runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.stdout.txt").write_text(
            completed_stdout,
            encoding="utf-8",
        )
        (runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.stderr.txt").write_text(
            completed_stderr,
            encoding="utf-8",
        )
        chat_path = wait_for_chat_recording_path(session_id)
        usage_summary = summarize_usage_from_records(
            session_id,
            read_chat_records_after_line(chat_path, existing_chat_line_count),
        )
        record_llm_observation(stage=stage, model=effective_model, usage=usage_summary, elapsed_seconds=elapsed_seconds, log_path=log_path)
        usage_payload = usage_summary.to_json() if usage_summary else None
        if usage_payload is not None:
            write_json(
                runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.usage.json",
                usage_payload,
            )
        if completed_returncode != 0:
            release_error = completed_stderr.strip() or completed_stdout.strip() or f"qwen exited with rc={completed_returncode}"
        append_log(
            log_path,
            f"Finished qwen turn {turn_index} with rc={completed_returncode}; stdout={len(completed_stdout)} chars stderr={len(completed_stderr)} chars; {format_usage_summary(usage_summary)}",
        )
        return QwenCallResult(
            returncode=completed_returncode,
            stdout=completed_stdout,
            stderr=completed_stderr,
            usage=usage_payload,
            timed_out=timed_out,
        )
    except Exception as exc:
        release_error = str(exc)
        raise
    finally:
        if managed_pool is not None and managed_lease is not None:
            try:
                managed_pool.release(managed_lease, usage=usage_payload, error=release_error)
            except Exception:
                pass


def run_python_tool(args: list[str], cwd: Path, log_path: Path) -> None:
    command = [sys.executable, *args]
    append_log(log_path, f"Running tool: {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.stdout.strip():
        append_log(log_path, f"Tool stdout:\n{completed.stdout.strip()}")
    if completed.stderr.strip():
        append_log(log_path, f"Tool stderr:\n{completed.stderr.strip()}")
    if completed.returncode != 0:
        raise RunnerError(f"Tool failed ({' '.join(args)}): {completed.stderr.strip() or completed.stdout.strip()}")


def find_export_outputs(project_path: Path) -> tuple[Path | None, Path | None]:
    exports_dir = project_path / "exports"
    if not exports_dir.exists():
        return None, None
    native: list[Path] = []
    svg: list[Path] = []
    for path in sorted(exports_dir.glob("*.pptx"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.name.endswith("_svg.pptx"):
            svg.append(path)
        else:
            native.append(path)
    return (native[0] if native else None, svg[0] if svg else None)


def create_project(request: dict[str, Any], manager: ProjectManager, log_path: Path) -> Path:
    base_dir = Path(request["project_base_dir"])
    if not base_dir.is_absolute():
        base_dir = REPO_ROOT / base_dir
    base_dir.mkdir(parents=True, exist_ok=True)

    base_name = sanitize_token(request["project_name"])
    for attempt in range(1, 100):
        candidate = base_name if attempt == 1 else f"{base_name}_{attempt}"
        try:
            capture = io.StringIO()
            with redirect_stdout(capture), redirect_stderr(capture):
                project_path = manager.init_project(
                    candidate,
                    request["canvas_format"],
                    base_dir=str(base_dir),
                )
            if capture.getvalue().strip():
                append_log(log_path, f"ProjectManager init output:\n{capture.getvalue().strip()}")
            append_log(log_path, f"Project initialized at {project_path}")
            return Path(project_path)
        except FileExistsError:
            continue
    raise RunnerError(f"Unable to allocate a unique project directory for {base_name}")


def import_markdown(request: dict[str, Any], project_path: Path, manager: ProjectManager, log_path: Path) -> Path:
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        summary = manager.import_sources(
            str(project_path),
            [request["source_md_path"]],
            copy=True,
        )
    if capture.getvalue().strip():
        append_log(log_path, f"ProjectManager import output:\n{capture.getvalue().strip()}")
    markdown_items = summary.get("markdown") or []
    if not markdown_items:
        raise RunnerError("Markdown import did not produce an imported markdown path")
    imported_markdown_path = Path(markdown_items[0])
    append_log(log_path, f"Imported markdown: {imported_markdown_path}")
    return imported_markdown_path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


def populate_images(project_path: Path, log_path: Path) -> int:
    """Copy image files from sources/ subdirectories into images/.

    The design pipeline expects user-provided images in ``<project>/images/``
    (referenced as ``../images/xxx.png`` inside ``svg_output/``).  However,
    ``import_sources`` only archives raw files into ``sources/`` and never
    populates ``images/``.  This function bridges the gap.
    """
    sources_dir = project_path / "sources"
    images_dir = project_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    if not sources_dir.exists():
        return 0
    copied = 0
    for path in sorted(sources_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        dest = images_dir / path.name
        if dest.exists():
            append_log(log_path, f"Image already exists, skipping: {path.name}")
            continue
        shutil.copy2(path, dest)
        copied += 1
        append_log(log_path, f"Copied image to images/: {path.name}")
    if copied:
        append_log(log_path, f"Populated {copied} image(s) into images/")
    else:
        append_log(log_path, "No images found in sources/ to populate")
    return copied


def build_runner_reference_files(
    imported_markdown_path: Path,
    project_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
) -> tuple[Path, Path, Path, Path, Path, set[str]]:
    sections = parse_markdown_structure(imported_markdown_path)
    chart_reference = build_chart_template_reference()
    available_icons = load_available_icons()
    icon_reference = build_icon_candidate_reference(plan, available_icons)
    source_image_reference = build_source_image_reference(
        imported_markdown_path=imported_markdown_path,
        project_path=project_path,
        plan=plan,
        sections=sections,
    )
    slide_digest = build_slide_content_digest(plan, sections, source_image_reference)

    chart_reference_path = runner_dir / "available_chart_templates.json"
    icon_reference_path = runner_dir / "available_icon_candidates.json"
    icon_inventory_path = runner_dir / "available_icon_inventory.json"
    source_image_reference_path = runner_dir / SOURCE_IMAGE_REFERENCE_FILENAME
    slide_digest_path = runner_dir / "slide_content_digest.json"

    write_json(chart_reference_path, chart_reference)
    write_json(icon_reference_path, icon_reference)
    write_json(
        icon_inventory_path,
        [f"{DEFAULT_ICON_LIBRARY}/{name}" for name in sorted(available_icons)],
    )
    write_json(source_image_reference_path, source_image_reference)
    write_json(slide_digest_path, slide_digest)

    valid_chart_keys = {item["key"] for item in chart_reference if isinstance(item, dict) and "key" in item}
    return (
        slide_digest_path,
        chart_reference_path,
        icon_reference_path,
        icon_inventory_path,
        source_image_reference_path,
        valid_chart_keys,
    )


def prepare_svg_batch_artifacts(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    executor_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
) -> tuple[list[list[SlidePlanEntry]], list[PreparedSvgBatch], bool]:
    batches = split_plan_into_batches(
        plan,
        int(request.get("batch_size", BATCH_SIZE)),
        str(request.get("batch_partition", "fixed")),
    )
    anchor_first = (os.getenv("PPT_API_SVG_ANCHOR_FIRST", "1").strip().lower() not in {"0", "false", "no"})
    anchor_svg_path: Path | None = None
    if anchor_first and len(batches) > 1:
        anchor_svg_path = project_path / "svg_output" / batches[0][-1].filename

    prepared: list[PreparedSvgBatch] = []
    for batch_index, batch_plan in enumerate(batches):
        batch_slide_plan_path = runner_dir / f"slide_plan.batch_{batch_index + 1:02d}.json"
        write_json(batch_slide_plan_path, [asdict(entry) for entry in batch_plan])

        batch_digest_path = runner_dir / f"slide_content_digest.batch_{batch_index + 1:02d}.json"
        write_batch_reference_file(slide_digest_path, batch_digest_path, batch_plan)

        batch_icon_reference_path = runner_dir / f"available_icon_candidates.batch_{batch_index + 1:02d}.json"
        write_batch_reference_file(icon_reference_path, batch_icon_reference_path, batch_plan)

        batch_source_image_reference_path = runner_dir / f"source_image_reference.batch_{batch_index + 1:02d}.json"
        write_batch_reference_file(source_image_reference_path, batch_source_image_reference_path, batch_plan)

        batch_prompt = build_batch_svg_prompt(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            batch_slide_plan_path=batch_slide_plan_path,
            batch_digest_path=batch_digest_path,
            batch_icon_reference_path=batch_icon_reference_path,
            batch_source_image_reference_path=batch_source_image_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
            executor_skill_pack_path=executor_skill_pack_path,
            batch_plan=batch_plan,
            batch_index=batch_index,
            total_batches=len(batches),
            prev_last_svg_path=anchor_svg_path if anchor_svg_path is not None and batch_index > 0 else None,
        )
        prompt_path = runner_dir / f"svg_batch_{batch_index + 1:02d}_prompt.txt"
        prompt_path.write_text(batch_prompt, encoding="utf-8")
        prepared.append(
            PreparedSvgBatch(
                batch_index=batch_index,
                batch_plan=batch_plan,
                prompt_path=prompt_path,
                batch_slide_plan_path=batch_slide_plan_path,
                prompt_text=batch_prompt,
                requires_anchor=bool(anchor_first and batch_index > 0),
            )
        )

    return batches, prepared, anchor_first


def execute_single_svg_batch(
    *,
    request: dict[str, Any],
    project_path: Path,
    full_plan: list[SlidePlanEntry],
    batch_plan: list[SlidePlanEntry],
    batch_index: int,
    batch_prompt: str,
    svg_anchor_context_path: Path,
    runner_dir: Path,
    log_path: Path,
    credential_override: dict[str, str] | None = None,
) -> str:
    return execute_qwen_stage(
        stage_name=f"svg_batch_{batch_index + 1}",
        artifact_prefix=f"svg_batch_{batch_index + 1:02d}",
        initial_prompt=batch_prompt,
        completion_sentinel_prefix=SVG_BATCH_COMPLETION_SENTINEL_PREFIX,
        state_checker=lambda bp=batch_plan: check_batch_state(project_path, bp, full_plan, log_path),
        continue_prompt_builder=lambda errors, bp=batch_plan: build_batch_svg_continue_prompt(
            request,
            project_path,
            bp,
            errors,
            svg_anchor_context_path,
        ),
        confirmation_prompt_builder=lambda _errors, bp=batch_plan: build_batch_svg_confirmation_prompt(bp, request),
        model=request.get("model"),
        runner_dir=runner_dir,
        log_path=log_path,
        credential_override=credential_override,
    )


def execute_batched_svg_generation(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    executor_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
    log_path: Path,
) -> list[str]:
    _batches, prepared_batches, _anchor_first = prepare_svg_batch_artifacts(
        request=request,
        project_path=project_path,
        slide_plan_path=slide_plan_path,
        slide_digest_path=slide_digest_path,
        icon_reference_path=icon_reference_path,
        source_image_reference_path=source_image_reference_path,
        svg_anchor_context_path=svg_anchor_context_path,
        executor_style_path=executor_style_path,
        executor_skill_pack_path=executor_skill_pack_path,
        plan=plan,
        runner_dir=runner_dir,
    )
    session_ids: list[str] = []

    for prepared in prepared_batches:
        session_id = execute_single_svg_batch(
            request=request,
            project_path=project_path,
            full_plan=plan,
            batch_plan=prepared.batch_plan,
            batch_index=prepared.batch_index,
            batch_prompt=prepared.prompt_text,
            svg_anchor_context_path=svg_anchor_context_path,
            runner_dir=runner_dir,
            log_path=log_path,
        )
        session_ids.append(session_id)

    return session_ids


def execute_parallel_svg_generation(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    executor_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
    log_path: Path,
) -> list[str]:
    if centralized_svg_scheduler_enabled(log_path):
        append_log(log_path, "Using centralized Redis SVG scheduler")
        return execute_parallel_svg_generation_centralized(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            slide_digest_path=slide_digest_path,
            icon_reference_path=icon_reference_path,
            source_image_reference_path=source_image_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
            executor_skill_pack_path=executor_skill_pack_path,
            plan=plan,
            runner_dir=runner_dir,
            log_path=log_path,
        )

    fair_delay = env_int("PPT_API_SVG_FAIR_SHARE_DELAY_SECONDS", SVG_FAIR_SHARE_DELAY_SECONDS, minimum=0)
    stage_stagger_window = env_int("PPT_API_SVG_STAGE_STAGGER_SECONDS", 0, minimum=0)
    stage_stagger = stable_delay_seconds(str(request.get("job_id") or project_path.name), stage_stagger_window)
    total_delay = fair_delay + stage_stagger
    if total_delay > 0:
        append_log(
            log_path,
            f"Staggering SVG stage start for {total_delay}s "
            f"(fair_share_delay={fair_delay}s stage_stagger={stage_stagger}s)",
        )
        time.sleep(total_delay)

    with register_active_svg_job(str(request.get("job_id") or project_path.name), runner_dir, log_path):
        return _execute_parallel_svg_generation_registered(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            slide_digest_path=slide_digest_path,
            icon_reference_path=icon_reference_path,
            source_image_reference_path=source_image_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
            executor_skill_pack_path=executor_skill_pack_path,
            plan=plan,
            runner_dir=runner_dir,
            log_path=log_path,
        )


def _execute_parallel_svg_generation_registered(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    executor_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
    log_path: Path,
) -> list[str]:
    batches, prepared_batches, anchor_first = prepare_svg_batch_artifacts(
        request=request,
        project_path=project_path,
        slide_plan_path=slide_plan_path,
        slide_digest_path=slide_digest_path,
        icon_reference_path=icon_reference_path,
        source_image_reference_path=source_image_reference_path,
        svg_anchor_context_path=svg_anchor_context_path,
        executor_style_path=executor_style_path,
        executor_skill_pack_path=executor_skill_pack_path,
        plan=plan,
        runner_dir=runner_dir,
    )
    requested_workers = int(request.get("parallel_batch_workers", DEFAULT_PARALLEL_BATCH_WORKERS))
    initial_workers = effective_svg_worker_count(
        requested_workers=requested_workers,
        total_batches=len(batches),
        log_path=log_path,
    )
    append_log(
        log_path,
        f"Launching parallel SVG batches: total_batches={len(batches)} requested_workers={requested_workers} initial_workers={initial_workers}",
    )

    session_by_index: dict[int, str] = {}
    remaining_batch_artifacts = list(prepared_batches)
    if anchor_first and len(prepared_batches) > 1:
        first_prepared = prepared_batches[0]
        append_log(log_path, f"Running anchor SVG batch {first_prepared.batch_index + 1} before parallel window")
        session_by_index[first_prepared.batch_index] = execute_single_svg_batch(
            request=request,
            project_path=project_path,
            full_plan=plan,
            batch_plan=first_prepared.batch_plan,
            batch_index=first_prepared.batch_index,
            batch_prompt=first_prepared.prompt_text,
            svg_anchor_context_path=svg_anchor_context_path,
            runner_dir=runner_dir,
            log_path=log_path,
        )
        append_log(log_path, f"Anchor SVG batch {first_prepared.batch_index + 1} completed")
        remaining_batch_artifacts = prepared_batches[1:]

    max_executor_workers = max(1, min(len(remaining_batch_artifacts), requested_workers))
    with ThreadPoolExecutor(max_workers=max_executor_workers) as executor:
        future_map: dict[Any, PreparedSvgBatch] = {}
        pending_batch_artifacts = list(remaining_batch_artifacts)
        batch_stagger = env_int("PPT_API_SVG_BATCH_STAGGER_SECONDS", 0, minimum=0)
        while pending_batch_artifacts or future_map:
            remaining_total = len(pending_batch_artifacts) + len(future_map)
            desired_inflight = effective_svg_worker_count(
                requested_workers=requested_workers,
                total_batches=max(1, remaining_total),
                log_path=log_path,
            )
            while pending_batch_artifacts and len(future_map) < desired_inflight:
                prepared = pending_batch_artifacts.pop(0)
                append_log(
                    log_path,
                    f"Submitting SVG batch {prepared.batch_index + 1} to executor "
                    f"(inflight={len(future_map) + 1}/{desired_inflight}, remaining={len(pending_batch_artifacts)})",
                )
                future = executor.submit(
                    execute_single_svg_batch,
                    request=request,
                    project_path=project_path,
                    full_plan=plan,
                    batch_plan=prepared.batch_plan,
                    batch_index=prepared.batch_index,
                    batch_prompt=prepared.prompt_text,
                    svg_anchor_context_path=svg_anchor_context_path,
                    runner_dir=runner_dir,
                    log_path=log_path,
                )
                future_map[future] = prepared
                if batch_stagger > 0 and pending_batch_artifacts and len(future_map) < desired_inflight:
                    time.sleep(batch_stagger)

            if not future_map:
                continue

            done, _pending = wait(tuple(future_map.keys()), return_when=FIRST_COMPLETED)
            for future in done:
                prepared = future_map.pop(future)
                session_by_index[prepared.batch_index] = future.result()
                append_log(log_path, f"Parallel SVG batch {prepared.batch_index + 1} completed")

    return [session_by_index[index] for index in sorted(session_by_index)]


def execute_parallel_svg_generation_centralized(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    icon_reference_path: Path,
    source_image_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    executor_skill_pack_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
    log_path: Path,
) -> list[str]:
    store = get_svg_scheduler_store(log_path)
    if store is None or SvgBatchTask is None or build_svg_scheduler_task_id is None:
        append_log(log_path, "Centralized SVG scheduler unavailable; falling back to local parallel scheduling")
        fair_delay = env_int("PPT_API_SVG_FAIR_SHARE_DELAY_SECONDS", SVG_FAIR_SHARE_DELAY_SECONDS, minimum=0)
        stage_stagger_window = env_int("PPT_API_SVG_STAGE_STAGGER_SECONDS", 0, minimum=0)
        stage_stagger = stable_delay_seconds(str(request.get("job_id") or project_path.name), stage_stagger_window)
        total_delay = fair_delay + stage_stagger
        if total_delay > 0:
            append_log(
                log_path,
                f"Staggering SVG stage start for {total_delay}s "
                f"(fair_share_delay={fair_delay}s stage_stagger={stage_stagger}s)",
            )
            time.sleep(total_delay)
        with register_active_svg_job(str(request.get("job_id") or project_path.name), runner_dir, log_path):
            return _execute_parallel_svg_generation_registered(
                request=request,
                project_path=project_path,
                slide_plan_path=slide_plan_path,
                slide_digest_path=slide_digest_path,
                icon_reference_path=icon_reference_path,
                source_image_reference_path=source_image_reference_path,
                svg_anchor_context_path=svg_anchor_context_path,
                executor_style_path=executor_style_path,
                executor_skill_pack_path=executor_skill_pack_path,
                plan=plan,
                runner_dir=runner_dir,
                log_path=log_path,
            )

    _batches, prepared_batches, _anchor_first = prepare_svg_batch_artifacts(
        request=request,
        project_path=project_path,
        slide_plan_path=slide_plan_path,
        slide_digest_path=slide_digest_path,
        icon_reference_path=icon_reference_path,
        source_image_reference_path=source_image_reference_path,
        svg_anchor_context_path=svg_anchor_context_path,
        executor_style_path=executor_style_path,
        executor_skill_pack_path=executor_skill_pack_path,
        plan=plan,
        runner_dir=runner_dir,
    )
    owner_job_id = str(request.get("job_id") or project_path.name)
    scheduler_owner = scheduler_owner_key()
    requested_workers = int(request.get("parallel_batch_workers", DEFAULT_PARALLEL_BATCH_WORKERS))
    append_log(
        log_path,
        f"Enqueueing centralized SVG batches: total_batches={len(prepared_batches)} "
        f"requested_workers={requested_workers} scheduler_owner={scheduler_owner}",
    )
    task_ids: list[str] = []
    task_id_to_batch_index: dict[str, int] = {}
    for prepared in prepared_batches:
        worker_request_path = runner_dir / f"svg_batch_{prepared.batch_index + 1:02d}.worker.json"
        write_json(
            worker_request_path,
            {
                "mode": "svg_batch_worker",
                "project_path": str(project_path),
                "runner_dir": str(runner_dir),
                "batch_index": prepared.batch_index,
            },
        )
        task_id = build_svg_scheduler_task_id(owner_job_id, prepared.batch_index)
        task = SvgBatchTask(
            task_id=task_id,
            owner_job_id=owner_job_id,
            report_id=str(request.get("report_id") or owner_job_id),
            batch_index=prepared.batch_index,
            total_batches=len(prepared_batches),
            requested_workers=requested_workers,
            worker_request_path=str(worker_request_path),
            enqueued_at=time.time() + (prepared.batch_index * 0.001),
            requires_anchor=prepared.requires_anchor,
            scheduler_owner=scheduler_owner,
        )
        store.enqueue_task(task)
        task_ids.append(task_id)
        task_id_to_batch_index[task_id] = prepared.batch_index
        append_log(
            log_path,
            f"Centralized SVG task enqueued: batch={prepared.batch_index + 1} task_id={task_id} requires_anchor={prepared.requires_anchor}",
        )

    sessions_by_index = wait_for_centralized_svg_tasks(
        store=store,
        task_ids=task_ids,
        task_id_to_batch_index=task_id_to_batch_index,
        owner_job_id=owner_job_id,
        log_path=log_path,
    )
    return [sessions_by_index[index] for index in sorted(sessions_by_index)]


def wait_for_centralized_svg_tasks(
    *,
    store: RedisSvgSchedulerStoreType,
    task_ids: list[str],
    task_id_to_batch_index: dict[str, int],
    owner_job_id: str,
    log_path: Path,
) -> dict[int, str]:
    timeout_seconds = env_int("PPT_API_SVG_BUDGET_LEASE_WAIT_TIMEOUT_SECONDS", LLM_SLOT_WAIT_TIMEOUT_SECONDS, minimum=60)
    started = time.time()
    sessions_by_index: dict[int, str] = {}
    remaining = set(task_ids)
    while remaining:
        if time.time() - started > timeout_seconds:
            store.fail_pending_tasks_for_job(owner_job_id, "Timed out waiting for centralized SVG batches")
            raise RunnerError(f"Timed out waiting for centralized SVG batches after {timeout_seconds}s")
        completed_this_round: list[str] = []
        for task_id in list(remaining):
            task = store.get_task(task_id)
            if task is None:
                continue
            if task.status == SVG_TASK_SUCCEEDED:
                completed_this_round.append(task_id)
                batch_index = task_id_to_batch_index[task_id]
                sessions_by_index[batch_index] = task.session_id or task.task_id
                append_log(log_path, f"Centralized SVG batch {batch_index + 1} completed via scheduler")
            elif task.status == SVG_TASK_FAILED:
                store.fail_pending_tasks_for_job(owner_job_id, task.error or f"Centralized SVG batch failed: {task_id}")
                store.clear_job_state(owner_job_id)
                raise RunnerError(task.error or f"Centralized SVG batch failed: {task_id}")
        for task_id in completed_this_round:
            remaining.discard(task_id)
        if remaining:
            time.sleep(1)
    store.clear_job_state(owner_job_id)
    return sessions_by_index


def usage_summary_for_stage(runner_dir: Path, stage_name: str) -> dict[str, Any] | None:
    usage_path = runner_dir / USAGE_SUMMARY_FILENAME
    if not usage_path.exists():
        return None
    try:
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    stage_totals = payload.get("stage_totals")
    if isinstance(stage_totals, dict) and isinstance(stage_totals.get(stage_name), dict):
        return stage_totals[stage_name]
    merged = TurnUsageSummary(models=[])
    found = False
    turns = payload.get("turns")
    if not isinstance(turns, list):
        return None
    for item in turns:
        if not isinstance(item, dict) or item.get("stage_name") != stage_name:
            continue
        usage_payload = item.get("usage")
        if not isinstance(usage_payload, dict):
            continue
        found = True
        merged.api_calls += safe_int(usage_payload.get("api_calls"))
        merged.prompt_tokens += safe_int(usage_payload.get("prompt_tokens"))
        merged.completion_tokens += safe_int(usage_payload.get("completion_tokens"))
        merged.cached_tokens += safe_int(usage_payload.get("cached_tokens"))
        merged.thoughts_tokens += safe_int(usage_payload.get("thoughts_tokens"))
        merged.total_tokens += safe_int(usage_payload.get("total_tokens"))
        merged.tool_tokens += safe_int(usage_payload.get("tool_tokens"))
        merged.models.extend(list(usage_payload.get("models") or []))
    return merged.to_json() if found else None


def execute_svg_batch_worker(worker_request_path: Path) -> dict[str, Any]:
    worker_request = read_json_value(worker_request_path)
    if not isinstance(worker_request, dict):
        raise RunnerError(f"Invalid SVG batch worker request: {worker_request_path}")
    runner_dir = Path(str(worker_request.get("runner_dir") or "")).expanduser().resolve()
    project_path = Path(str(worker_request.get("project_path") or "")).expanduser().resolve()
    batch_index = safe_int(worker_request.get("batch_index"))
    if not runner_dir.exists():
        raise RunnerError(f"Runner directory not found: {runner_dir}")
    if not project_path.exists():
        raise RunnerError(f"Project path not found: {project_path}")

    request = read_json(runner_dir / "request.json")
    credential_override = normalize_qwen_credential_override(worker_request)
    if credential_override is not None:
        request = dict(request)
        if credential_override.get("model"):
            request["model"] = credential_override["model"]
    full_plan = load_slide_plan_entries(runner_dir / "slide_plan.json")
    batch_plan = load_slide_plan_entries(runner_dir / f"slide_plan.batch_{batch_index + 1:02d}.json")
    prompt_path = runner_dir / f"svg_batch_{batch_index + 1:02d}_prompt.txt"
    batch_prompt = prompt_path.read_text(encoding="utf-8")
    svg_anchor_context_path = runner_dir / SVG_ANCHOR_CONTEXT_FILENAME
    log_path = runner_dir / LOG_FILENAME

    append_log(log_path, f"Centralized SVG worker starting batch {batch_index + 1} from {worker_request_path}")
    if credential_override is not None:
        append_log(
            log_path,
            f"Centralized SVG worker using account_id={credential_override.get('account_id') or 'unknown'} for batch {batch_index + 1}",
        )
    session_id = execute_single_svg_batch(
        request=request,
        project_path=project_path,
        full_plan=full_plan,
        batch_plan=batch_plan,
        batch_index=batch_index,
        batch_prompt=batch_prompt,
        svg_anchor_context_path=svg_anchor_context_path,
        runner_dir=runner_dir,
        log_path=log_path,
        credential_override=credential_override,
    )
    stage_name = f"svg_batch_{batch_index + 1}"
    return {
        "status": SVG_TASK_SUCCEEDED,
        "session_id": session_id,
        "batch_index": batch_index,
        "account_id": credential_override.get("account_id") if credential_override else None,
        "usage": usage_summary_for_stage(runner_dir, stage_name),
    }


def build_svg_anchor_context(
    project_path: Path,
    plan: list[SlidePlanEntry],
    executor_style_path: Path,
) -> dict[str, Any]:
    design_spec_path = project_path / "design_spec.md"
    design_spec_text = read_text(design_spec_path)
    colors = extract_color_scheme(design_spec_text)
    project_name = extract_markdown_table_value(design_spec_text, "Project Name") or project_path.name
    use_case = extract_markdown_table_value(design_spec_text, "Use Case")
    design_style = extract_markdown_table_value(design_spec_text, "Design Style")
    content_entries = [entry for entry in plan if entry.kind == "content"]
    content_titles = [entry.filename for entry in content_entries]
    anchor_pages = [entry.filename for entry in plan[: min(3, len(plan))]]
    reanchor_before = [
        plan[index].filename
        for index in range(COOKBOOK_REREAD_INTERVAL, len(plan), COOKBOOK_REREAD_INTERVAL)
    ]
    return {
        "project_name": project_name,
        "use_case": use_case,
        "design_style": design_style,
        "executor_style_reference": str(executor_style_path),
        "source_of_truth": {
            "design_spec": str(design_spec_path),
            "cookbook": str(SVG_DESIGN_COOKBOOK_PATH),
            "executor_base": str(QWEN_EXECUTOR_REFERENCE_PATH),
            "executor_style": str(executor_style_path),
        },
        "immutable_geometry": {
            "canvas": {"width": 1280, "height": 720, "viewBox": "0 0 1280 720"},
            "top_gradient_bar": {"y": 0, "height": 6},
            "title_bar": {"x": 60, "y": 40, "width": 6, "height": 36, "rx": 3},
            "title_text": {"x": 80, "y": 70, "font_size": 32},
            "title_icon": {"y": 46, "width": 30, "height": 30, "gap_from_title": 12},
            "content_min_y": 105,
            "footer": {"y": 690, "height": 30},
        },
        "immutable_defs": {
            "gradient_id": "headerGrad",
            "shadow_filter_id": "cardShadow",
            "shadow_filter_type": "five_step_gaussian_blur_chain",
            "forbidden_shadow_filter": "feDropShadow",
        },
        "color_roles": {
            "Background": colors.get("Background", "#F5F7FA"),
            "Secondary bg": colors.get("Secondary bg", "#FFFFFF"),
            "Primary": colors.get("Primary", "#1565C0"),
            "Accent": colors.get("Accent", "#FF8F00"),
            "Secondary accent": colors.get("Secondary accent", "#00838F"),
            "Body text": colors.get("Body text", "#263238"),
            "Secondary text": colors.get("Secondary text", "#546E7A"),
            "Tertiary text": colors.get("Tertiary text", "#90A4AE"),
            "Border/divider": colors.get("Border/divider", "#E0E4E8"),
        },
        "icon_rules": {
            "library": DEFAULT_ICON_LIBRARY,
            "title_icon_y": 46,
            "title_icon_size": 30,
            "title_icon_gap_from_text": 12,
            "title_icon_x_formula": "80 + (title_character_count * 30) + 12",
        },
        "naming_rules": {
            "must_match_slide_plan_exactly": True,
            "expected_svg_filenames": [entry.filename for entry in plan],
            "expected_note_headings": [entry.note_heading for entry in plan],
        },
        "anchor_pages": anchor_pages,
        "content_page_examples": content_titles[:3],
        "reanchor_policy": {
            "interval_pages": COOKBOOK_REREAD_INTERVAL,
            "checkpoints_before_svg": reanchor_before,
            "required_rereads": [
                SVG_DESIGN_COOKBOOK_PATH.name,
                SVG_ANCHOR_CONTEXT_FILENAME,
            ],
            "why": "Prevent context-window drift and keep header/footer/defs/naming consistent across long SVG runs.",
        },
    }


def execute_generation(
    request: dict[str, Any],
    project_path: Path,
    imported_markdown_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
    log_path: Path,
) -> str:
    slide_plan_payload = [asdict(entry) for entry in plan]
    slide_plan_path = runner_dir / "slide_plan.json"
    write_json(slide_plan_path, slide_plan_payload)
    (
        slide_digest_path,
        chart_reference_path,
        icon_reference_path,
        icon_inventory_path,
        source_image_reference_path,
        valid_chart_keys,
    ) = build_runner_reference_files(
        imported_markdown_path,
        project_path,
        plan,
        runner_dir,
    )

    strategist_skill_pack_path, strategist_skill_pack_hash = write_skill_pack(
        runner_dir,
        "strategist_skill_pack.md",
        [
            REPO_ROOT / "AGENTS.md",
            QWEN_PROJECT_GUIDE_PATH,
            QWEN_SKILL_WRAPPER_PATH,
            QWEN_REPO_SKILL_PATH,
            QWEN_STRATEGIST_REFERENCE_PATH,
            QWEN_DESIGN_SPEC_REFERENCE_PATH,
            SVG_DESIGN_COOKBOOK_PATH,
        ],
        critical_rules=[
            "Emoji are forbidden in design_spec.md and downstream SVG output.",
            f"Do not use emoji as bullets, labels, callouts, status markers, pseudo-icons, or decorative accents; use normal text or `{DEFAULT_ICON_LIBRARY}/...` icon placeholders instead.",
            f"If an icon is needed, use only real `{DEFAULT_ICON_LIBRARY}/...` names from the allowed icon inventory.",
        ],
    )
    notes_skill_pack_path, notes_skill_pack_hash = write_skill_pack(
        runner_dir,
        "notes_skill_pack.md",
        [
            REPO_ROOT / "AGENTS.md",
            QWEN_PROJECT_GUIDE_PATH,
            QWEN_SKILL_WRAPPER_PATH,
            QWEN_REPO_SKILL_PATH,
        ],
    )

    skill_pack_index: dict[str, dict[str, str]] = {
        "strategist": {"path": str(strategist_skill_pack_path), "hash": strategist_skill_pack_hash},
        "notes": {"path": str(notes_skill_pack_path), "hash": notes_skill_pack_hash},
    }
    write_json(runner_dir / "skill_pack_index.json", skill_pack_index)
    spec_prompt = build_spec_bootstrap_prompt(
        request,
        project_path,
        imported_markdown_path,
        strategist_skill_pack_path,
        slide_plan_path,
        slide_digest_path,
        chart_reference_path,
        icon_reference_path,
        source_image_reference_path,
        plan,
    )
    (runner_dir / "spec_prompt.txt").write_text(spec_prompt, encoding="utf-8")

    spec_model = str(request.get("spec_model") or request.get("model"))
    spec_session_id = execute_direct_spec_stage(
        request=request,
        project_path=project_path,
        imported_markdown_path=imported_markdown_path,
        strategist_skill_pack_path=strategist_skill_pack_path,
        slide_plan_path=slide_plan_path,
        slide_digest_path=slide_digest_path,
        chart_reference_path=chart_reference_path,
        icon_reference_path=icon_reference_path,
        source_image_reference_path=source_image_reference_path,
        plan=plan,
        valid_chart_keys=valid_chart_keys,
        model=spec_model,
        runner_dir=runner_dir,
        log_path=log_path,
    )
    if spec_session_id is None:
        append_log(log_path, "Direct spec generation unavailable or invalid; falling back to Qwen CLI")
        spec_session_id = execute_qwen_stage(
            stage_name="spec_generation",
            artifact_prefix="spec",
            initial_prompt=spec_prompt,
            completion_sentinel_prefix=SPEC_COMPLETION_SENTINEL_PREFIX,
            state_checker=lambda: check_spec_state(project_path, plan, valid_chart_keys),
            continue_prompt_builder=lambda errors: build_spec_continue_prompt(
                request,
                project_path,
                plan,
                errors,
                strategist_skill_pack_path,
            ),
            confirmation_prompt_builder=lambda _errors: build_spec_confirmation_prompt(plan, request),
            model=spec_model,
            runner_dir=runner_dir,
            log_path=log_path,
        )

    spec_repair_report_path = runner_dir / SPEC_REPAIR_REPORT_FILENAME
    repair_design_spec(
        project_path,
        valid_chart_keys,
        log_path=log_path,
        report_path=spec_repair_report_path,
    )
    strict_spec_errors = validate_design_spec(project_path, plan, valid_chart_keys, strict_icons=True)
    if strict_spec_errors:
        raise RunnerError(
            "Deterministic spec repair left unresolved issues: "
            + "; ".join(strict_spec_errors)
        )
    review_session_id = "disabled_deterministic"
    append_log(log_path, f"Deterministic spec repair passed; report saved to {spec_repair_report_path}")

    cleanup_pre_execution_outputs(project_path, log_path)
    executor_style_path = select_executor_style_reference(project_path)
    executor_critical_rules = [
        "Emoji are forbidden everywhere in SVG output.",
        f"Never substitute emoji for icons; use only `data-icon=\"{DEFAULT_ICON_LIBRARY}/...\"` with a real icon name from the inventory.",
        "Do not use pictographic Unicode characters in titles, labels, bullets, badges, captions, annotations, or decorative marks.",
        "If a bullet needs emphasis, use layout, color, weight, or a legal icon placeholder instead of emoji.",
    ]
    executor_skill_pack_path, executor_skill_pack_hash = write_executor_skill_pack(
        runner_dir,
        project_path,
        executor_style_path,
        executor_critical_rules,
    )
    skill_pack_index["executor"] = {"path": str(executor_skill_pack_path), "hash": executor_skill_pack_hash}
    write_json(runner_dir / "skill_pack_index.json", skill_pack_index)

    svg_anchor_context_path = runner_dir / SVG_ANCHOR_CONTEXT_FILENAME
    write_json(
        svg_anchor_context_path,
        build_svg_anchor_context(project_path, plan, executor_style_path),
    )
    write_json(
        runner_dir / "svg_executor_context.json",
        {
            "executor_base": str(QWEN_EXECUTOR_REFERENCE_PATH),
            "svg_design_cookbook": str(SVG_DESIGN_COOKBOOK_PATH),
            "svg_anchor_context": str(svg_anchor_context_path),
            "executor_style": str(executor_style_path),
            "shared_standards": str(QWEN_SHARED_STANDARDS_PATH),
            "image_layout": str(QWEN_IMAGE_LAYOUT_REFERENCE_PATH),
        },
    )

    svg_prompt = build_svg_bootstrap_prompt(
        request,
        project_path,
        imported_markdown_path,
        slide_plan_path,
        icon_reference_path,
        source_image_reference_path,
        svg_anchor_context_path,
        executor_style_path,
        executor_skill_pack_path,
        plan,
    )
    (runner_dir / "bootstrap_prompt.txt").write_text(svg_prompt, encoding="utf-8")

    batch_mode = str(request.get("batch_mode", "always"))
    batch_size = int(request.get("batch_size", BATCH_SIZE))
    use_parallel_svg = batch_mode == "parallel" or (
        batch_mode == "auto" and len(plan) > BATCH_MODE_THRESHOLD
    )
    use_batched_svg = batch_mode == "always"

    svg_session_id: str
    svg_batch_session_ids: list[str] = []
    if use_parallel_svg:
        append_log(
            log_path,
            "Using parallel batched SVG generation: "
            f"pages={len(plan)} batch_size={batch_size} "
            f"workers={int(request.get('parallel_batch_workers', DEFAULT_PARALLEL_BATCH_WORKERS))} "
            f"batch_partition={request.get('batch_partition', 'fixed')}",
        )
        svg_batch_session_ids = execute_parallel_svg_generation(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            slide_digest_path=slide_digest_path,
            icon_reference_path=icon_reference_path,
            source_image_reference_path=source_image_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
            executor_skill_pack_path=executor_skill_pack_path,
            plan=plan,
            runner_dir=runner_dir,
            log_path=log_path,
        )
        svg_session_id = svg_batch_session_ids[-1]
    elif use_batched_svg:
        append_log(
            log_path,
            f"Using batched serial SVG generation: pages={len(plan)} batch_size={batch_size} batch_mode={batch_mode}",
        )
        svg_batch_session_ids = execute_batched_svg_generation(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            slide_digest_path=slide_digest_path,
            icon_reference_path=icon_reference_path,
            source_image_reference_path=source_image_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
            executor_skill_pack_path=executor_skill_pack_path,
            plan=plan,
            runner_dir=runner_dir,
            log_path=log_path,
        )
        svg_session_id = svg_batch_session_ids[-1]
    else:
        append_log(
            log_path,
            f"Using single-session SVG generation: pages={len(plan)} batch_mode={batch_mode}",
        )
        svg_session_id = execute_qwen_stage(
            stage_name="svg_generation",
            artifact_prefix="qwen",
            initial_prompt=svg_prompt,
            completion_sentinel_prefix=COMPLETION_SENTINEL_PREFIX,
            state_checker=lambda: check_svg_only_state(project_path, plan, valid_chart_keys, runner_dir),
            continue_prompt_builder=lambda errors: build_svg_continue_prompt(
                request,
                project_path,
                plan,
                errors,
                svg_anchor_context_path,
            ),
            confirmation_prompt_builder=lambda _errors: build_svg_confirmation_prompt(plan, request),
            model=request.get("model"),
            runner_dir=runner_dir,
            log_path=log_path,
        )

    notes_prompt = build_notes_bootstrap_prompt(
        project_path=project_path,
        imported_markdown_path=imported_markdown_path,
        slide_plan_path=slide_plan_path,
        svg_anchor_context_path=svg_anchor_context_path,
        notes_skill_pack_path=notes_skill_pack_path,
    )
    (runner_dir / "notes_prompt.txt").write_text(notes_prompt, encoding="utf-8")

    notes_model = str(request.get("notes_model") or request.get("model"))
    notes_session_id = execute_direct_notes_stage(
        project_path=project_path,
        imported_markdown_path=imported_markdown_path,
        slide_plan_path=slide_plan_path,
        svg_anchor_context_path=svg_anchor_context_path,
        notes_skill_pack_path=notes_skill_pack_path,
        plan=plan,
        model=notes_model,
        runner_dir=runner_dir,
        log_path=log_path,
    )
    if notes_session_id is None:
        append_log(log_path, "Direct notes generation unavailable or invalid; falling back to Qwen CLI")
        notes_session_id = execute_qwen_stage(
            stage_name="notes_generation",
            artifact_prefix="notes",
            initial_prompt=notes_prompt,
            completion_sentinel_prefix=NOTES_COMPLETION_SENTINEL_PREFIX,
            state_checker=lambda: check_notes_state(project_path, plan, log_path=log_path),
            continue_prompt_builder=lambda errors: build_notes_continue_prompt(project_path, plan, errors),
            confirmation_prompt_builder=lambda errors: build_notes_continue_prompt(project_path, plan, errors),
            model=notes_model,
            runner_dir=runner_dir,
            log_path=log_path,
        )

    append_log(log_path, "Running deterministic SVG quality check (no AI review)")
    svg_quality_report_path = runner_dir / SVG_QUALITY_REPORT_FILENAME
    try:
        run_python_tool(
            [
                "skills/ppt-master/scripts/svg_quality_checker.py",
                str(project_path),
                "--export",
                "--output",
                str(svg_quality_report_path),
            ],
            cwd=REPO_ROOT,
            log_path=log_path,
        )
        append_log(log_path, f"SVG quality report saved to {svg_quality_report_path}")
    except Exception as exc:
        append_log(log_path, f"SVG quality check completed with issues: {exc}")

    append_log(log_path, "Running SVG auto repair (pie charts, title icons, syntax)")
    try:
        run_python_tool(
            [
                "skills/ppt-master/scripts/svg_auto_repair.py",
                str(project_path),
            ],
            cwd=REPO_ROOT,
            log_path=log_path,
        )
        append_log(log_path, "SVG auto repair completed")
    except Exception as exc:
        append_log(log_path, f"SVG auto repair finished with issues: {exc}")

    write_json(
        runner_dir / "stage_sessions.json",
        {
            "spec_session_id": spec_session_id,
            "review_session_id": review_session_id,
            "svg_session_id": svg_session_id,
            "svg_batch_sessions": svg_batch_session_ids,
            "notes_session_id": notes_session_id,
        },
    )
    log_usage_overall(runner_dir, log_path)
    return notes_session_id


def run_post_processing(project_path: Path, log_path: Path) -> tuple[Path, Path]:
    with acquire_resource_slot(
        "postprocess",
        label=f"postprocess_{project_path.name}",
        runner_dir=project_path / RUNNER_DIRNAME,
        log_path=log_path,
    ):
        run_python_tool(
            ["skills/ppt-master/scripts/total_md_split.py", str(project_path)],
            cwd=REPO_ROOT,
            log_path=log_path,
        )
        run_python_tool(
            ["skills/ppt-master/scripts/finalize_svg.py", str(project_path)],
            cwd=REPO_ROOT,
            log_path=log_path,
        )
        run_python_tool(
            ["skills/ppt-master/scripts/svg_to_pptx.py", str(project_path), "-s", "final"],
            cwd=REPO_ROOT,
            log_path=log_path,
        )
    native_pptx, svg_pptx = find_export_outputs(project_path)
    if native_pptx is None or svg_pptx is None:
        raise RunnerError("Post-processing completed but export outputs were not found in exports/")
    return native_pptx, svg_pptx


def build_failure_output(
    request: dict[str, Any],
    project_path: Path | None,
    session_id: str | None,
    log_path: Path | None,
    error: str,
) -> RunOutput:
    return RunOutput(
        job_id=request["job_id"],
        status="failed",
        project_path=str(project_path) if project_path else None,
        qwen_session_id=session_id,
        native_pptx_path=None,
        svg_pptx_path=None,
        log_path=str(log_path) if log_path else None,
        error=error,
    )


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--svg-batch-worker":
        worker_request_path = Path(sys.argv[2]).expanduser().resolve()
        ensure_qwen_available()
        try:
            payload = execute_svg_batch_worker(worker_request_path)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": SVG_TASK_FAILED,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)

    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    request_path = Path(sys.argv[1]).expanduser().resolve()
    request = load_request(request_path)
    ensure_qwen_available()

    manager = ProjectManager()
    temp_runner_dir = PROJECTS_DIR / sanitize_token(request["job_id"])
    temp_runner_dir.mkdir(parents=True, exist_ok=True)
    temp_log_path = temp_runner_dir / LOG_FILENAME
    project_path: Path | None = None
    session_id: str | None = None
    log_path: Path | None = temp_log_path

    try:
        append_log(temp_log_path, f"Starting job {request['job_id']} from request {request_path}")
        project_path = create_project(request, manager, temp_log_path)
        runner_dir = project_path / RUNNER_DIRNAME
        runner_dir.mkdir(parents=True, exist_ok=True)
        project_log_path = runner_dir / LOG_FILENAME
        if temp_log_path != project_log_path and temp_log_path.exists():
            project_log_path.write_text(temp_log_path.read_text(encoding="utf-8"), encoding="utf-8")
            try:
                temp_log_path.unlink()
            except OSError:
                pass
        log_path = project_log_path

        request_copy_path = runner_dir / "request.json"
        write_json(request_copy_path, request)
        append_log(log_path, f"Request copied to {request_copy_path}")

        imported_markdown_path = import_markdown(request, project_path, manager, log_path)
        populate_images(project_path, log_path)
        plan = build_slide_plan(request, imported_markdown_path)
        write_json(runner_dir / "slide_plan.json", [asdict(entry) for entry in plan])
        append_log(log_path, f"Built slide plan with {len(plan)} pages")

        session_id = execute_generation(
            request=request,
            project_path=project_path,
            imported_markdown_path=imported_markdown_path,
            plan=plan,
            runner_dir=runner_dir,
            log_path=log_path,
        )

        native_pptx, svg_pptx = run_post_processing(project_path, log_path)
        output = RunOutput(
            job_id=request["job_id"],
            status="succeeded",
            project_path=str(project_path),
            qwen_session_id=session_id,
            native_pptx_path=str(native_pptx),
            svg_pptx_path=str(svg_pptx),
            log_path=str(log_path),
            error=None,
        )
        write_json(runner_dir / "result.json", asdict(output))
        print(json.dumps(asdict(output), ensure_ascii=False, indent=2))
        return
    except Exception as exc:
        if log_path is not None:
            append_log(log_path, f"Job failed: {exc}")
        output = build_failure_output(
            request=request,
            project_path=project_path,
            session_id=session_id,
            log_path=log_path,
            error=str(exc),
        )
        if project_path is not None:
            runner_dir = project_path / RUNNER_DIRNAME
            runner_dir.mkdir(parents=True, exist_ok=True)
            write_json(runner_dir / "result.json", asdict(output))
        print(json.dumps(asdict(output), ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
