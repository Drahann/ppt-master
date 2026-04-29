"""Shared paths and configuration for PPT automation."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent
SKILL_DIR = TOOLS_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from project_utils import CANVAS_FORMATS, normalize_canvas_format  # noqa: E402

DEFAULT_BASE_URL = "https://api.deepseek.com/anthropic"
DEFAULT_MODEL = "deepseek-v4-pro"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen3.6-plus"
QWEN_MAX_TOKENS = 65536
QWEN_TIMEOUT = 900
CLAUDE_MODEL = "deepseek-v4-pro[1m]"
CLAUDE_FLASH_MODEL = "deepseek-v4-flash"


def normalized_format(canvas_format: str) -> str:
    """Normalize and validate a canvas format key."""
    normalized = normalize_canvas_format(canvas_format)
    if normalized not in CANVAS_FORMATS:
        available = ", ".join(sorted(CANVAS_FORMATS))
        raise ValueError(f"Unsupported canvas format: {canvas_format} (available: {available})")
    return normalized


def canvas_dimensions(canvas_format: str) -> tuple[int, int, str, dict[str, str]]:
    """Return width, height, normalized format, and canvas metadata."""
    normalized = normalized_format(canvas_format)
    canvas = CANVAS_FORMATS[normalized]
    parts = canvas["viewbox"].split()
    return int(parts[2]), int(parts[3]), normalized, canvas
