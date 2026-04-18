#!/usr/bin/env python3
"""Automate PPT Master generation with Qwen Code CLI.

Usage:
    python3 skills/ppt-master/scripts/qwen_ppt_runner.py <request.json>
"""

from __future__ import annotations

import json
import io
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import get_close_matches
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from config import REPO_ROOT, PROJECTS_DIR
    from project_manager import ProjectManager
except ImportError:
    TOOLS_DIR = Path(__file__).resolve().parent
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    from config import REPO_ROOT, PROJECTS_DIR  # type: ignore
    from project_manager import ProjectManager  # type: ignore


COMPLETION_SENTINEL_PREFIX = "PPT_RUN_COMPLETE:"
SPEC_COMPLETION_SENTINEL_PREFIX = "PPT_SPEC_COMPLETE:"
REVIEW_COMPLETION_SENTINEL_PREFIX = "PPT_SPEC_REVIEW_COMPLETE:"
SVG_BATCH_COMPLETION_SENTINEL_PREFIX = "PPT_SVG_BATCH_COMPLETE:"
NOTES_COMPLETION_SENTINEL_PREFIX = "PPT_NOTES_COMPLETE:"
DEFAULT_CANVAS_FORMAT = "ppt169"
DEFAULT_PROJECT_BASE_DIR = "projects"
DEFAULT_QWEN_MODEL = "qwen3.6-plus"
DEFAULT_REVIEW_MODEL = "qwen3.6-plus"
DEFAULT_MAX_FOLLOW_UPS = 8
QWEN_CALL_TIMEOUT_SECONDS = 60 * 60
QWEN_CHAT_ROOT = Path.home() / ".qwen" / "projects"
QWEN_DEBUG_ROOT = Path.home() / ".qwen" / "debug"
RUNNER_DIRNAME = "runner"
LOG_FILENAME = "runner.log"
SVG_QUALITY_REPORT_FILENAME = "svg_quality_report.txt"
SVG_ANCHOR_CONTEXT_FILENAME = "svg_anchor_context.json"
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
BATCH_SIZE = 8
BATCH_MODE_THRESHOLD = 15
DEFAULT_PARALLEL_BATCH_WORKERS = 4
QWEN_ALLOWED_TOOLS = (
    "edit",
    "write_file",
    "run_shell_command",
)

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
        "expand_h2_titles": ["鍒涙柊鎶€鏈?, "浜т笟楠岃瘉"],
        "expand_rule": "each_h3_one_slide_no_parent_h2_slide",
    },
}

RESOURCE_ONLY_H2_TITLES = {
    "鐩稿叧鍥剧墖淇℃伅",
    "鍥剧墖淇℃伅",
    "鐩稿叧鍥惧儚淇℃伅",
    "鍙傝€冨浘鐗?,
    "鍥剧墖璧勬簮",
    "鍥惧儚璧勬簮",
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

REVIEW_FOCUS_SLIDES = (
    "甯傚満瀹氫綅",
    "鎺ㄥ箍妯″紡",
    "鍟嗕笟妯″紡",
    "璐㈠姟瑙勫垝",
    "鐩堝埄鍒嗘瀽",
    "鍥㈤槦缁撴瀯",
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
    "璇风‘璁?,
    "璇峰厛纭",
    "纭璁捐瑙勬牸",
    "鍏」纭",
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


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


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


def append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_iso()}] {message}\n")


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


def resolve_qwen_cli_auth_args() -> list[str]:
    auth_type = (os.getenv("PPT_API_QWEN_AUTH_TYPE") or "").strip()
    api_key = (os.getenv("PPT_API_QWEN_API_KEY") or "").strip()
    base_url = (os.getenv("PPT_API_QWEN_BASE_URL") or "").strip()

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
    batch_mode = (request.get("batch_mode") or "auto")
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
    model = request.get("model")
    request["model"] = model.strip() if isinstance(model, str) and model.strip() else DEFAULT_QWEN_MODEL
    review_model = request.get("review_model")
    if isinstance(review_model, str) and review_model.strip():
        request["review_model"] = review_model.strip()
    else:
        request["review_model"] = DEFAULT_REVIEW_MODEL
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
        (("鍒涙柊", "鎶€鏈?, "tech", "鐮斿彂", "绠楁硶", "绯荤粺"), ["lightbulb", "microchip", "bolt", "cog"]),
        (("浜т笟", "甯傚満", "鍟嗕笟", "business", "杩愯惀", "鎺ㄥ箍"), ["building", "chart-bar", "target", "money"]),
        (("璐㈠姟", "鐩堝埄", "鏀剁泭", "finance", "profit"), ["money", "coin", "chart-pie", "chart-line"]),
        (("鍥㈤槦", "涓撳", "鏁欏笀", "缁勭粐", "team"), ["users", "user", "book-open", "star"]),
        (("鑳屾櫙", "鐜扮姸", "璋冪爺", "鍒嗘瀽", "research"), ["book-open", "chart-line", "globe", "chart-bar"]),
        (("楠岃瘉", "瀹夊叏", "椋庨櫓", "quality"), ["shield-check", "shield", "chart-line", "target"]),
        (("钀藉湴", "瀹炴柦", "roadmap", "瑙勫垝", "鎺ㄨ繘"), ["rocket", "target-arrow", "calendar", "link"]),
        (("鐢熸€?, "鍗忓悓", "鍚堜綔", "缃戠粶", "platform"), ["link", "globe", "building", "users"]),
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


def build_slide_content_digest(plan: list[SlidePlanEntry], sections: list[MarkdownH2]) -> list[dict[str, Any]]:
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
                "heading": "灏侀潰",
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
                "heading": "缁撳熬椤?,
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
) -> QwenCallResult:
    command = resolve_qwen_launcher()
    command.extend(resolve_qwen_cli_auth_args())
    if resume:
        command.extend(["--resume", session_id])
    else:
        command.extend(["--session-id", session_id])
    command.extend(["--prompt", "", "--chat-recording", "--approval-mode", "yolo"])
    for tool_name in QWEN_ALLOWED_TOOLS:
        command.extend(["--allowed-tools", tool_name])
    if model:
        command.extend(["--model", model])

    safe_command = redact_sensitive_command_parts(command)
    append_log(log_path, f"Starting qwen turn {turn_index}: {' '.join(safe_command)} (prompt via stdin, {len(prompt)} chars)")
    completed = subprocess.run(
        command,
        cwd=repo_root,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=QWEN_CALL_TIMEOUT_SECONDS,
        check=False,
    )

    (runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.stdout.txt").write_text(
        completed.stdout,
        encoding="utf-8",
    )
    (runner_dir / f"{artifact_prefix}_turn_{turn_index:02d}.stderr.txt").write_text(
        completed.stderr,
        encoding="utf-8",
    )
    append_log(
        log_path,
        f"Finished qwen turn {turn_index} with rc={completed.returncode}; stdout={len(completed.stdout)} chars stderr={len(completed.stderr)} chars",
    )
    return QwenCallResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


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
    plan: list[SlidePlanEntry],
    runner_dir: Path,
) -> tuple[Path, Path, Path, Path, set[str]]:
    sections = parse_markdown_structure(imported_markdown_path)
    chart_reference = build_chart_template_reference()
    available_icons = load_available_icons()
    icon_reference = build_icon_candidate_reference(plan, available_icons)
    slide_digest = build_slide_content_digest(plan, sections)

    chart_reference_path = runner_dir / "available_chart_templates.json"
    icon_reference_path = runner_dir / "available_icon_candidates.json"
    icon_inventory_path = runner_dir / "available_icon_inventory.json"
    slide_digest_path = runner_dir / "slide_content_digest.json"

    write_json(chart_reference_path, chart_reference)
    write_json(icon_reference_path, icon_reference)
    write_json(
        icon_inventory_path,
        [f"{DEFAULT_ICON_LIBRARY}/{name}" for name in sorted(available_icons)],
    )
    write_json(slide_digest_path, slide_digest)

    valid_chart_keys = {item["key"] for item in chart_reference if isinstance(item, dict) and "key" in item}
    return slide_digest_path, chart_reference_path, icon_reference_path, icon_inventory_path, valid_chart_keys


def execute_batched_svg_generation(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    icon_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
    log_path: Path,
) -> list[str]:
    batches = split_plan_into_batches(plan, int(request.get("batch_size", BATCH_SIZE)))
    session_ids: list[str] = []

    for batch_index, batch_plan in enumerate(batches):
        batch_slide_plan_path = runner_dir / f"slide_plan.batch_{batch_index + 1:02d}.json"
        write_json(batch_slide_plan_path, [asdict(entry) for entry in batch_plan])

        batch_digest_path = runner_dir / f"slide_content_digest.batch_{batch_index + 1:02d}.json"
        write_batch_reference_file(slide_digest_path, batch_digest_path, batch_plan)

        batch_icon_reference_path = runner_dir / f"available_icon_candidates.batch_{batch_index + 1:02d}.json"
        write_batch_reference_file(icon_reference_path, batch_icon_reference_path, batch_plan)

        prev_last_svg_path: Path | None = None
        if batch_index > 0:
            prev_last_svg_path = project_path / "svg_output" / batches[batch_index - 1][-1].filename
            if not prev_last_svg_path.exists():
                prev_last_svg_path = None

        batch_prompt = build_batch_svg_prompt(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            batch_slide_plan_path=batch_slide_plan_path,
            batch_digest_path=batch_digest_path,
            batch_icon_reference_path=batch_icon_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
            batch_plan=batch_plan,
            batch_index=batch_index,
            total_batches=len(batches),
            prev_last_svg_path=prev_last_svg_path,
        )
        (runner_dir / f"svg_batch_{batch_index + 1:02d}_prompt.txt").write_text(batch_prompt, encoding="utf-8")

        session_id = execute_qwen_stage(
            stage_name=f"svg_batch_{batch_index + 1}",
            artifact_prefix=f"svg_batch_{batch_index + 1:02d}",
            initial_prompt=batch_prompt,
            completion_sentinel_prefix=SVG_BATCH_COMPLETION_SENTINEL_PREFIX,
            state_checker=lambda bp=batch_plan: check_batch_state(project_path, bp, plan),
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
        )
        session_ids.append(session_id)

    return session_ids


def execute_parallel_svg_generation(
    request: dict[str, Any],
    project_path: Path,
    slide_plan_path: Path,
    slide_digest_path: Path,
    icon_reference_path: Path,
    svg_anchor_context_path: Path,
    executor_style_path: Path,
    plan: list[SlidePlanEntry],
    runner_dir: Path,
    log_path: Path,
) -> list[str]:
    batches = split_plan_into_batches(plan, int(request.get("batch_size", BATCH_SIZE)))
    max_workers = min(len(batches), int(request.get("parallel_batch_workers", DEFAULT_PARALLEL_BATCH_WORKERS)))
    append_log(
        log_path,
        f"Launching parallel SVG batches: total_batches={len(batches)} workers={max_workers}",
    )

    batch_artifacts: list[tuple[int, list[SlidePlanEntry], Path, Path, str]] = []
    for batch_index, batch_plan in enumerate(batches):
        batch_slide_plan_path = runner_dir / f"slide_plan.batch_{batch_index + 1:02d}.json"
        write_json(batch_slide_plan_path, [asdict(entry) for entry in batch_plan])

        batch_digest_path = runner_dir / f"slide_content_digest.batch_{batch_index + 1:02d}.json"
        write_batch_reference_file(slide_digest_path, batch_digest_path, batch_plan)

        batch_icon_reference_path = runner_dir / f"available_icon_candidates.batch_{batch_index + 1:02d}.json"
        write_batch_reference_file(icon_reference_path, batch_icon_reference_path, batch_plan)

        batch_prompt = build_batch_svg_prompt(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            batch_slide_plan_path=batch_slide_plan_path,
            batch_digest_path=batch_digest_path,
            batch_icon_reference_path=batch_icon_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
            batch_plan=batch_plan,
            batch_index=batch_index,
            total_batches=len(batches),
            prev_last_svg_path=None,
        )
        prompt_path = runner_dir / f"svg_batch_{batch_index + 1:02d}_prompt.txt"
        prompt_path.write_text(batch_prompt, encoding="utf-8")
        batch_artifacts.append(
            (
                batch_index,
                batch_plan,
                prompt_path,
                batch_slide_plan_path,
                batch_prompt,
            )
        )

    session_by_index: dict[int, str] = {}

    def run_single_parallel_batch(
        batch_index: int,
        batch_plan: list[SlidePlanEntry],
        batch_prompt: str,
    ) -> str:
        return execute_qwen_stage(
            stage_name=f"svg_batch_{batch_index + 1}",
            artifact_prefix=f"svg_batch_{batch_index + 1:02d}",
            initial_prompt=batch_prompt,
            completion_sentinel_prefix=SVG_BATCH_COMPLETION_SENTINEL_PREFIX,
            state_checker=lambda bp=batch_plan: check_batch_state(project_path, bp, plan),
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
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(run_single_parallel_batch, batch_index, batch_plan, batch_prompt): batch_index
            for batch_index, batch_plan, _prompt_path, _batch_slide_plan_path, batch_prompt in batch_artifacts
        }
        for future in as_completed(future_map):
            batch_index = future_map[future]
            session_by_index[batch_index] = future.result()
            append_log(log_path, f"Parallel SVG batch {batch_index + 1} completed")

    return [session_by_index[index] for index in sorted(session_by_index)]


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
    baseline_content_page = content_entries[0].filename if content_entries else None
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
    slide_plan_path = runner_dir / "slide_plan.json"
    write_json(slide_plan_path, [asdict(entry) for entry in plan])
    (
        slide_digest_path,
        chart_reference_path,
        icon_reference_path,
        icon_inventory_path,
        valid_chart_keys,
    ) = build_runner_reference_files(
        imported_markdown_path,
        plan,
        runner_dir,
    )
    spec_prompt = build_spec_bootstrap_prompt(
        request,
        project_path,
        imported_markdown_path,
        slide_plan_path,
        slide_digest_path,
        chart_reference_path,
        icon_reference_path,
        plan,
    )
    (runner_dir / "spec_prompt.txt").write_text(spec_prompt, encoding="utf-8")

    spec_session_id = execute_qwen_stage(
        stage_name="spec_generation",
        artifact_prefix="spec",
        initial_prompt=spec_prompt,
        completion_sentinel_prefix=SPEC_COMPLETION_SENTINEL_PREFIX,
        state_checker=lambda: check_spec_state(project_path, plan, valid_chart_keys),
        continue_prompt_builder=lambda errors: build_spec_continue_prompt(request, project_path, plan, errors),
        confirmation_prompt_builder=lambda _errors: build_spec_confirmation_prompt(plan, request),
        model=request.get("model"),
        runner_dir=runner_dir,
        log_path=log_path,
    )

    review_report_path = runner_dir / REVIEW_REPORT_FILENAME
    review_input_path = runner_dir / REVIEW_INPUT_FILENAME
    write_json(
        review_input_path,
        build_spec_review_input(
            project_path,
            plan,
            valid_chart_keys,
            icon_reference_path,
            icon_inventory_path,
        ),
    )
    review_prompt = build_review_bootstrap_prompt(
        request,
        project_path,
        review_input_path,
        review_report_path,
    )
    (runner_dir / "review_prompt.txt").write_text(review_prompt, encoding="utf-8")

    review_session_id = execute_qwen_stage(
        stage_name="spec_review",
        artifact_prefix="review",
        initial_prompt=review_prompt,
        completion_sentinel_prefix=REVIEW_COMPLETION_SENTINEL_PREFIX,
        state_checker=lambda: check_review_state(project_path, plan, valid_chart_keys, review_report_path),
        continue_prompt_builder=lambda errors: build_review_continue_prompt(project_path, review_report_path, errors),
        confirmation_prompt_builder=lambda errors: build_review_continue_prompt(project_path, review_report_path, errors),
        model=request.get("review_model"),
        runner_dir=runner_dir,
        log_path=log_path,
    )

    cleanup_pre_execution_outputs(project_path, log_path)
    executor_style_path = select_executor_style_reference(project_path)
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
        svg_anchor_context_path,
        executor_style_path,
        plan,
    )
    (runner_dir / "bootstrap_prompt.txt").write_text(svg_prompt, encoding="utf-8")

    batch_mode = str(request.get("batch_mode", "auto"))
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
            f"workers={int(request.get('parallel_batch_workers', DEFAULT_PARALLEL_BATCH_WORKERS))}",
        )
        svg_batch_session_ids = execute_parallel_svg_generation(
            request=request,
            project_path=project_path,
            slide_plan_path=slide_plan_path,
            slide_digest_path=slide_digest_path,
            icon_reference_path=icon_reference_path,
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
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
            svg_anchor_context_path=svg_anchor_context_path,
            executor_style_path=executor_style_path,
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
    )
    (runner_dir / "notes_prompt.txt").write_text(notes_prompt, encoding="utf-8")
    notes_session_id = execute_qwen_stage(
        stage_name="notes_generation",
        artifact_prefix="notes",
        initial_prompt=notes_prompt,
        completion_sentinel_prefix=NOTES_COMPLETION_SENTINEL_PREFIX,
        state_checker=lambda: check_notes_state(project_path, plan),
        continue_prompt_builder=lambda errors: build_notes_continue_prompt(project_path, plan, errors),
        confirmation_prompt_builder=lambda errors: build_notes_continue_prompt(project_path, plan, errors),
        model=request.get("model"),
        runner_dir=runner_dir,
        log_path=log_path,
    )

    # 鈹€鈹€ SVG Quality Check (deterministic script, no AI call) 鈹€鈹€
    svg_review_session_ids: list[str] = []
    svg_review_session_id = "skipped_script_only"
    svg_quality_report_path = runner_dir / SVG_QUALITY_REPORT_FILENAME
    append_log(log_path, "Running deterministic SVG quality check (no AI review)")
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

    # 鈹€鈹€ SVG Auto Repair (deterministic fixes for charts, icons, syntax) 鈹€鈹€
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
            "svg_review_session_id": svg_review_session_id,
            "svg_review_batch_sessions": svg_review_session_ids,
        },
    )
    return svg_review_session_id


def run_post_processing(project_path: Path, log_path: Path) -> tuple[Path, Path]:
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
