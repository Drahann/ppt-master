"""SVG generation, prompt files, and Claude Code execution."""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape as xml_escape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .config import CLAUDE_FLASH_MODEL, CLAUDE_MODEL, DEFAULT_BASE_URL, REPO_ROOT, canvas_dimensions
from .cookbook import Cookbook
from .errors import GenerationError
from .parser import Deck, Slide
from .planner import ICON_INVENTORY, build_deck_context_prefix, build_design_plan_prompt, build_notes_prompt, call_deepseek_anthropic
from .usage import UsageLogger
from clean_svg_entities import clean_svg_entities

SVG_SYNTAX_REPAIR_SYSTEM = (
    "You repair SVG XML syntax only. Return exactly one complete SVG document and no prose."
)


def stripped_markdown_lines(markdown: str) -> list[str]:
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"图片：\1", markdown)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in {"---", "***"} or line.startswith("#"):
            continue
        if set(line) <= {"|", ":", "-", " "}:
            continue
        if line.startswith("|") and line.endswith("|"):
            parts = [p.strip() for p in line.strip("|").split("|") if p.strip()]
            if parts:
                line = " / ".join(parts)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)
        if line:
            lines.append(line)
    return lines


def visual_len(text: str) -> int:
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in text)


def wrap_visual(text: str, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text.strip():
        if visual_len(current + ch) > width and current:
            lines.append(current)
            current = ch
            if len(lines) >= max_lines:
                break
        else:
            current += ch
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and visual_len(lines[-1]) > max(4, width - 2):
        lines[-1] = lines[-1].rstrip("，。；,. ") + "…"
    return lines


def svg_text_lines(
    x: int,
    y: int,
    lines: list[str],
    *,
    font_size: int,
    fill: str,
    line_height: int,
    weight: str | None = None,
    anchor: str | None = None,
) -> str:
    attrs = [
        f'x="{x}"',
        f'y="{y}"',
        f'font-size="{font_size}"',
        'font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif"',
        f'fill="{fill}"',
    ]
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if anchor:
        attrs.append(f'text-anchor="{anchor}"')
    content = [f"<text {' '.join(attrs)}>"]
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_height
        content.append(f'  <tspan x="{x}" dy="{dy}">{xml_escape(line)}</tspan>')
    content.append("</text>")
    return "\n".join(content)


def deterministic_svg(slide: Slide, deck: Deck, canvas_format: str) -> str:
    width, height, _, canvas = canvas_dimensions(canvas_format)
    lines = stripped_markdown_lines(slide.body)
    summary = lines[:6] or ["本页内容来自 Markdown 对应章节。"]
    title_lines = wrap_visual(slide.title, 28, 2)
    footer = f"{slide.index:02d} / {len(deck.slides):02d}"

    if slide.kind == "cover":
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{canvas['viewbox']}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>
  <rect x="72" y="76" width="10" height="568" rx="5" fill="#1D4ED8"/>
  <rect x="104" y="76" width="300" height="8" rx="4" fill="#F59E0B"/>
  <circle cx="1070" cy="168" r="92" fill="#E0F2FE" stroke="#CBD5E1" stroke-width="1"/>
  <circle cx="1115" cy="226" r="46" fill="#EEF2FF" stroke="#CBD5E1" stroke-width="1"/>
  <path d="M966 486 C1028 402 1114 392 1190 326" fill="none" stroke="#0F766E" stroke-width="4"/>
  <path d="M956 514 C1032 462 1118 460 1200 412" fill="none" stroke="#CBD5E1" stroke-width="2"/>
{svg_text_lines(112, 248, wrap_visual(slide.title, 18, 3), font_size=46, fill="#0F172A", line_height=58, weight="bold")}
  <text x="112" y="462" font-size="22" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#475569">{xml_escape(deck.title)}</text>
  <text x="112" y="548" font-size="15" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#1D4ED8">PPT Master Automation</text>
  <line x1="112" y1="574" x2="512" y2="574" stroke="#CBD5E1" stroke-width="1"/>
</svg>
"""

    if slide.kind == "closing":
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{canvas['viewbox']}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>
  <rect x="104" y="110" width="{width - 208}" height="{height - 220}" rx="20" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>
  <rect x="104" y="110" width="12" height="{height - 220}" rx="6" fill="#0F766E"/>
{svg_text_lines(width // 2, 314, wrap_visual(slide.title, 18, 2), font_size=50, fill="#0F172A", line_height=60, weight="bold", anchor="middle")}
  <text x="{width // 2}" y="396" font-size="22" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#475569">{xml_escape(deck.title)}</text>
  <circle cx="{width // 2 - 88}" cy="470" r="5" fill="#1D4ED8"/>
  <circle cx="{width // 2}" cy="470" r="5" fill="#0F766E"/>
  <circle cx="{width // 2 + 88}" cy="470" r="5" fill="#F59E0B"/>
</svg>
"""

    if slide.index % 2 == 1:
        blocks: list[str] = []
        y = 210
        for idx, item in enumerate(summary[:5], start=1):
            wrapped = wrap_visual(item, 48, 2)
            blocks.append(
                "\n".join(
                    [
                        f'<g id="point-{idx}">',
                        f'  <circle cx="92" cy="{y - 7}" r="13" fill="#E0F2FE" stroke="#1D4ED8" stroke-width="1.4"/>',
                        f'  <text x="92" y="{y - 1}" font-size="13" text-anchor="middle" font-weight="bold" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#1D4ED8">{idx}</text>',
                        svg_text_lines(122, y, wrapped, font_size=18, fill="#0F172A", line_height=27),
                        "</g>",
                    ]
                )
            )
            y += 86
        layout = f"""
  <rect x="52" y="128" width="{width - 104}" height="{height - 210}" rx="18" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>
  <rect x="52" y="128" width="8" height="{height - 210}" rx="4" fill="#1D4ED8"/>
{chr(10).join(blocks)}
"""
    else:
        left = [line for item in (summary[:3] or summary) for line in wrap_visual(item, 31, 2)][:6]
        right = [line for item in (summary[3:6] or summary[:3]) for line in wrap_visual(item, 31, 2)][:6]
        layout = f"""
  <g id="left-panel">
    <rect x="64" y="164" width="560" height="420" rx="16" fill="#EEF2FF" stroke="#CBD5E1" stroke-width="1"/>
    <text x="92" y="214" font-size="24" font-weight="bold" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#1D4ED8">关键信息</text>
{svg_text_lines(92, 242, left, font_size=17, fill="#0F172A", line_height=28)}
  </g>
  <g id="right-panel">
    <rect x="656" y="164" width="560" height="420" rx="16" fill="#E0F2FE" stroke="#CBD5E1" stroke-width="1"/>
    <text x="710" y="214" font-size="24" font-weight="bold" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#0F766E">支撑依据</text>
{svg_text_lines(710, 242, right, font_size=17, fill="#0F172A", line_height=28)}
  </g>
"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{canvas['viewbox']}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>
  <rect x="0" y="0" width="{width}" height="92" fill="#FFFFFF"/>
  <rect x="52" y="58" width="84" height="6" rx="3" fill="#F59E0B"/>
  <text x="52" y="48" font-size="13" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#475569">{xml_escape(deck.title)}</text>
{svg_text_lines(52, 112, title_lines, font_size=34, fill="#0F172A", line_height=42, weight="bold")}
{layout}
  <line x1="52" y1="{height - 54}" x2="{width - 52}" y2="{height - 54}" stroke="#CBD5E1" stroke-width="1"/>
  <text x="52" y="{height - 25}" font-size="13" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#475569">PPT Master Automation</text>
  <text x="{width - 52}" y="{height - 25}" font-size="13" text-anchor="end" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" fill="#475569">{footer}</text>
</svg>
"""


def deterministic_notes(deck: Deck) -> str:
    sections: list[str] = []
    for slide in deck.slides:
        lines = stripped_markdown_lines(slide.body)
        key_points = "；".join([line[:80] for line in lines[:3]]) or slide.title
        transition = "开场先交代本页主题。" if slide.index == 1 else "承接上一页，我们继续看下一组信息。"
        sections.extend(
            [
                f"# {slide.stem}",
                "",
                f"[过渡] {transition}",
                "",
                f"围绕“{slide.title}”，本页建议先给出结论，再用页面中的关键信息补充背景和证据。",
                "",
                f"要点：{key_points}",
                "",
                "时长：约 1 分钟",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def build_svg_prompt_prefix(
    project_path: Path,
    deck: Deck,
    canvas_format: str,
    style: str,
    cookbook: Cookbook | None = None,
) -> str:
    _, _, _, canvas = canvas_dimensions(canvas_format)
    common_prefix = build_deck_context_prefix(deck, canvas_format, style, cookbook)
    design_plan = ""
    design_path = project_path / "design_plan.json"
    if design_path.exists():
        try:
            design_data = json.loads(design_path.read_text(encoding="utf-8", errors="replace"))
            design_plan = json.dumps(
                {
                    "theme": design_data.get("theme", {}),
                    "art_direction": design_data.get("art_direction", {}),
                    "layout_system": design_data.get("layout_system", {}),
                    "component_system": design_data.get("component_system", {}),
                    "assets": design_data.get("assets", {}),
                    "cookbook": design_data.get("cookbook", {}),
                    "slides": [
                        {
                            key: slide.get(key)
                            for key in (
                                "index",
                                "title",
                                "kind",
                                "section_title",
                                "svg_filename",
                                "rhythm",
                                "layout",
                                "layout_family",
                                "layout_signature",
                                "intent",
                                "composition",
                                "visual_structure",
                                "why_this_layout",
                                "visual_metaphor",
                                "visual_guidance",
                                "icon_plan",
                                "chart_or_diagram",
                                "content_density",
                            )
                            if key in slide
                        }
                        for slide in design_data.get("slides", [])
                        if isinstance(slide, dict)
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        except Exception:
            design_plan = design_path.read_text(encoding="utf-8", errors="replace")[:12000]
    spec_lock = (project_path / "spec_lock.json").read_text(encoding="utf-8", errors="replace") if (project_path / "spec_lock.json").exists() else ""
    image_manifest = ""
    image_manifest_path = project_path / "images" / "image_manifest.json"
    if image_manifest_path.exists():
        image_manifest = image_manifest_path.read_text(encoding="utf-8", errors="replace")
    cookbook_svg_rules = ""
    if cookbook is not None:
        cookbook_svg_rules = f"""
Theme Cookbook SVG rules:
- Cookbook `{cookbook.id}` is active. Follow its typography, chrome, component geometry, decorative asset policy, chart skin, layout grammar, and forbidden drift rules.
- Treat named cookbook recipes as strong reference exemplars, not as a closed set. If `layout_family` is `g08_adapted_*` or otherwise cookbook-compatible, build the requested semantic structure using the cookbook's visual grammar.
- If `chart_or_diagram` names a catalog template, preserve that chart/diagram's semantic geometry and restyle it in the cookbook theme even when the cookbook does not list that exact template.
- Do not downgrade cookbook-compatible layouts into a generic card or two-column page.
- If spec_lock repeats cookbook tokens, spec_lock is the executable contract. If spec_lock is missing a cookbook detail, fall back to the cookbook text above.
"""
    return f"""{common_prefix}

Task family: SVG page generation.

Stable rules:
- Return exactly one complete SVG document and no prose.
- Do not use layout templates.
- Use `width="{canvas['viewbox'].split()[2]}" height="{canvas['viewbox'].split()[3]}" viewBox="{canvas['viewbox']}"`.
- Use only colors, fonts, icon inventory, and image filenames listed in spec_lock.json.
- Use inline SVG attributes only.
- Forbidden: `<style>`, `class`, `<foreignObject>`, `rgba()`, `clip-path`, `<script>`, `<animate*>`, `<textPath>`, `<mask>`, and HTML named entities.
- Light theme only: the root background must be `#FFFFFF` or near-white. Do not use dark theme, black/dark full-slide backgrounds, dark hero panels, GitHub-dark palette, or neon-on-black styling even if the model prefers a technology look.
- Keep the deck theme continuous: the locked primary accent from spec_lock/cookbook must be dominant on every slide. Extra colors may add richness, but they must not make one slide feel like a different theme.
- XML reserved characters in text must be escaped.
- Text wrapping and inline emphasis must use `<text>` and `<tspan>` only. Never use HTML `<span>`; write `<tspan fill="#..." font-weight="...">...</tspan>`.
- Group related elements with plain `<g>`; never use `<g opacity>`.
- Use the current page source Markdown as the source of visible content. The global manifest is only for deck context.
- Follow the current slide's `layout_signature`, `visual_structure`, and `visual_guidance` from Design Plan JSON. These are soft structure instructions, not exact coordinates.
- Avoid collapsing specific layout guidance into a generic two-column card page. If the plan asks for a chart, matrix, roadmap, dashboard, network, architecture, product view, or profile wall, build that visible structure.
- Produce a polished slide, not a plain document dump: strong hierarchy, intentional whitespace, aligned panels/cards/diagrams, restrained colors, and no text collisions.
- If a slide is dense, summarize into key phrases and speaker-note-level detail rather than overfilling the canvas.
- Keep SVG concise: target 7,000-12,000 characters, no comments, no duplicated hidden text, no verbose metadata.
- If current page source Markdown contains an image, use the downloaded local image when it helps the slide. Reference it with `<image href="../images/filename.ext" ... preserveAspectRatio="xMidYMid meet"/>`; do not reference external http(s), `/root/...`, or original source URLs.
- Prefer project icon placeholders instead of hand-drawn icons. Use syntax such as `<use data-icon="chunk-filled/rocket" x="100" y="100" width="32" height="32" fill="#1D4ED8"/>`; `finalize_svg.py` will embed the real icon.
- Available icon placeholders: {", ".join(ICON_INVENTORY)}.
- Current style: {style}

{cookbook_svg_rules}

Design Plan JSON:
{design_plan}

Spec Lock JSON:
{spec_lock}

Available Project Images JSON:
{image_manifest}
"""


def build_svg_prompt(prefix: str, slide: Slide) -> str:
    return f"""{prefix}

Current page task:
- Write only this slide SVG: `{slide.svg_filename}`
- Slide number: P{slide.index:02d}
- Slide title: {slide.title}

Current page source Markdown:
```markdown
{slide.raw_markdown}
```
"""


def claude_tool_mode() -> str:
    raw = os.environ.get("PPT_MASTER_CLAUDE_TOOLS", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return "readonly"
    if raw in {"read", "readonly"}:
        return "readonly"
    if raw in {"readwrite", "read-write", "rw"}:
        return "readwrite"
    if raw in {"", "0", "false", "no", "off", "none", "disabled"}:
        return "disabled"
    return "disabled"


def claude_tool_args(mode: str) -> list[str]:
    if mode == "readonly":
        return [
            "--tools",
            "Read",
            "--allowedTools",
            "Read",
            "--permission-mode",
            "acceptEdits",
        ]
    if mode == "readwrite":
        return [
            "--tools",
            "Read,Write",
            "--allowedTools",
            "Read,Write",
            "--permission-mode",
            "acceptEdits",
        ]
    return ["--tools="]


def claude_stream_enabled() -> bool:
    raw = os.environ.get("PPT_MASTER_CLAUDE_STREAM", "1").strip().lower()
    return raw not in {"0", "false", "no", "off", "disabled"}


def claude_output_format() -> str:
    return "stream-json" if claude_stream_enabled() else "json"


def claude_command(claude_exe: str, *, tool_args: list[str], output_format: str) -> list[str]:
    command = [
        claude_exe,
        "-p",
        "--output-format",
        output_format,
        "--input-format",
        "text",
    ]
    if output_format == "stream-json":
        command.append("--verbose")
        command.append("--include-partial-messages")
    command.extend(tool_args)
    return command


def tool_audit_filename(slide: Slide) -> str:
    return f"claude_tool_audit_{slide.stem}.json"


def append_tool_experiment_prompt(prompt: str, slide: Slide, tool_mode: str) -> str:
    audit_name = tool_audit_filename(slide)
    if tool_mode == "readonly":
        return f"""{prompt}

Restricted tool-access instructions:
- This run enables only the Claude Code `Read` tool for observability.
- You may use `Read` to inspect `design_plan.json`, `spec_lock.json`, `slide_manifest.json`, `prompts/svg_prefix.md`, or this slide's prompt file if it is necessary.
- Prefer the content already embedded in this prompt. Do not read files unless the embedded context is insufficient.
- You cannot write or edit files in this mode.
- The final response must contain exactly one complete SVG document and no prose, so the runner can validate and log usage normally.
"""
    return f"""{prompt}

Restricted tool-access instructions:
- This run intentionally enables only Claude Code `Read` and `Write` file tools to measure behavior. The `Edit` tool is not available.
- You may use `Read` to inspect `design_plan.json`, `spec_lock.json`, `slide_manifest.json`, `prompts/svg_prefix.md`, or this slide's prompt file if it helps.
- Use `Write` to save the final SVG to `svg_output/{slide.svg_filename}` before your final response.
- Use `Write` to save a JSON audit file at `logs/{audit_name}` with keys: `read_files`, `wrote_files`, `notes`.
- The final response must still contain exactly one complete SVG document and no prose, so the runner can validate and log usage normally.
"""


def write_prompt_files(
    project_path: Path,
    deck: Deck,
    canvas_format: str,
    style: str,
    cookbook: Cookbook | None = None,
) -> None:
    prompt_dir = project_path / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "design_plan_prompt.md").write_text(build_design_plan_prompt(deck, canvas_format, style, cookbook), encoding="utf-8")
    (prompt_dir / "notes_prompt.md").write_text(build_notes_prompt(deck, canvas_format, style, cookbook), encoding="utf-8")
    prefix = build_svg_prompt_prefix(project_path, deck, canvas_format, style, cookbook)
    (prompt_dir / "svg_prefix.md").write_text(prefix, encoding="utf-8")
    page_dir = prompt_dir / "svg_pages"
    page_dir.mkdir(exist_ok=True)
    for slide in deck.slides:
        (page_dir / f"{slide.stem}.md").write_text(build_svg_prompt(prefix, slide), encoding="utf-8")


def normalize_svg_text(svg: str) -> str:
    """Normalize common model output escapes before writing SVG files."""
    candidate = svg.strip()
    if '\\"' in candidate[:300] or "\\n" in candidate:
        try:
            decoded = json.loads(f'"{candidate}"')
            if isinstance(decoded, str) and "<svg" in decoded:
                candidate = decoded
        except json.JSONDecodeError:
            candidate = (
                candidate.replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace("\\/", "/")
            )
    return clean_svg_entities(candidate).strip() + "\n"


def extract_svg_document(text: str) -> str:
    normalized_text = normalize_svg_text(text)
    start = normalized_text.find("<svg")
    end = normalized_text.rfind("</svg>")
    if start < 0 or end < 0:
        raise GenerationError("Claude output did not contain a complete <svg> document.")
    return normalize_svg_text(normalized_text[start : end + len("</svg>")])


def extract_svg(text: str) -> str:
    svg = extract_svg_document(text)
    try:
        ET.fromstring(svg)
    except ET.ParseError as exc:
        raise GenerationError(f"Claude output contained invalid SVG XML: {exc}") from exc
    return svg


def is_svg_xml_syntax_error(exc: Exception) -> bool:
    return "contained invalid SVG XML" in str(exc)


def build_svg_syntax_repair_prompt(svg: str, error: str) -> str:
    return f"""Repair only XML/SVG syntax in the SVG below.

Rules:
- Return exactly one complete <svg>...</svg> document and no prose.
- Preserve the visual design, coordinates, colors, text, icons, and element order.
- Fix only malformed XML tag delimiters, missing inline text/tspan closers, broken <tspan> tags, and XML escaping.
- Do not redesign, summarize, translate, or add new content.
- Use SVG <text> and <tspan> only for inline text emphasis.

Parser error:
{error}

SVG to repair:
```svg
{svg}
```
"""


def parse_claude_json_output(stdout: str) -> tuple[str, dict[str, Any]]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        data = None
    if data is None:
        result_event: dict[str, Any] | None = None
        text_parts: list[str] = []
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "result":
                result_event = event
                continue
            if event.get("type") != "assistant":
                continue
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else event.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                        text_parts.append(str(item["text"]))
            elif isinstance(content, str):
                text_parts.append(content)
        if result_event:
            text = result_event.get("result") or result_event.get("text") or result_event.get("content")
            if isinstance(text, list):
                text = "\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in text)
            if text is None:
                text = "\n".join(text_parts) or stdout
            usage = result_event.get("usage", {}) if isinstance(result_event.get("usage"), dict) else {}
            return str(text), usage
        return ("\n".join(text_parts) if text_parts else stdout), {}
    if not isinstance(data, dict):
        return stdout, {}
    text = data.get("result") or data.get("text") or data.get("content") or stdout
    if isinstance(text, list):
        text = "\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in text)
    return str(text), data.get("usage", {}) if isinstance(data.get("usage"), dict) else {}


def truthy_env(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def claude_config_base(project_path: Path) -> Path:
    configured = os.environ.get("PPT_MASTER_CLAUDE_CONFIG_ROOT")
    base = Path(configured) if configured else REPO_ROOT / ".tmp" / "claude-code-config"
    path = base / project_path.name
    path.mkdir(parents=True, exist_ok=True)
    return path


def scoped_claude_env(env: dict[str, str], scope: str) -> dict[str, str]:
    share_config = env.get("PPT_MASTER_CLAUDE_SHARE_CONFIG") or os.environ.get("PPT_MASTER_CLAUDE_SHARE_CONFIG")
    if truthy_env(share_config):
        return env
    base = env.get("PPT_MASTER_CLAUDE_CONFIG_BASE")
    if not base:
        return env
    scope_mode = (
        env.get("PPT_MASTER_CLAUDE_CONFIG_SCOPE") or os.environ.get("PPT_MASTER_CLAUDE_CONFIG_SCOPE") or "job"
    ).strip().lower()
    if scope_mode in {"batch", "scope", "scoped"}:
        safe_scope = re.sub(r"[^A-Za-z0-9_.-]+", "_", scope).strip("_") or "default"
        config_dir = Path(base) / safe_scope
    else:
        config_dir = Path(base)
    config_dir.mkdir(parents=True, exist_ok=True)
    scoped = env.copy()
    scoped["CLAUDE_CONFIG_DIR"] = str(config_dir)
    return scoped


def is_claude_config_lock_error(text: str) -> bool:
    lowered = text.lower()
    return (
        "ebusy" in lowered
        and ".claude" in lowered
        and ("resource busy" in lowered or "locked" in lowered or "open" in lowered)
    )


def claude_lock_retries() -> int:
    raw = os.environ.get("PPT_MASTER_CLAUDE_LOCK_RETRIES", "5")
    try:
        return max(0, min(20, int(raw)))
    except ValueError:
        return 5


def run_claude_print(
    command: list[str],
    *,
    prompt: str,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    stream_log_path: Path | None = None,
) -> tuple[str, str, int, float]:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    started = time.perf_counter()
    lock_retry_logs: list[str] = []
    retries = claude_lock_retries()
    for lock_attempt in range(1, retries + 2):
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        try:
            if stream_log_path is None:
                stdout, stderr = process.communicate(prompt, timeout=timeout)
            else:
                stream_log_path.parent.mkdir(parents=True, exist_ok=True)
                stream_log_path.write_text("", encoding="utf-8")
                stderr_log_path = stream_log_path.with_name(f"{stream_log_path.stem}.stderr.log")
                stderr_log_path.write_text("", encoding="utf-8")
                stdout_chunks: list[str] = []
                stderr_chunks: list[str] = []

                def drain_output(pipe: Any, chunks: list[str], path: Path) -> None:
                    try:
                        for line in iter(pipe.readline, ""):
                            chunks.append(line)
                            with path.open("a", encoding="utf-8") as stream_fh:
                                stream_fh.write(line)
                    finally:
                        try:
                            pipe.close()
                        except Exception:
                            pass

                stdout_thread = threading.Thread(
                    target=drain_output,
                    args=(process.stdout, stdout_chunks, stream_log_path),
                    daemon=True,
                )
                stderr_thread = threading.Thread(
                    target=drain_output,
                    args=(process.stderr, stderr_chunks, stderr_log_path),
                    daemon=True,
                )
                stdout_thread.start()
                stderr_thread.start()
                if process.stdin is not None:
                    try:
                        process.stdin.write(prompt)
                        process.stdin.close()
                    except BrokenPipeError:
                        pass
                process.wait(timeout=timeout)
                stdout_thread.join(timeout=10)
                stderr_thread.join(timeout=10)
                stdout = "".join(stdout_chunks)
                stderr = "".join(stderr_chunks)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, text=True)
            else:
                process.kill()
            try:
                process.communicate(timeout=10)
            except Exception:
                pass
            raise GenerationError(f"Claude SVG generation timed out after {timeout}s") from exc

        combined = f"{stderr}\n{stdout}"
        if process.returncode == 0 or not is_claude_config_lock_error(combined) or lock_attempt > retries:
            if lock_retry_logs:
                retry_log = "\n".join(lock_retry_logs)
                stderr = f"{retry_log}\n{stderr}" if stderr else retry_log
            return stdout, stderr, process.returncode, time.perf_counter() - started

        lock_retry_logs.append(
            f"[ppt-master] Claude config lock retry {lock_attempt}/{retries}: "
            f"{(stderr or stdout).strip()[:500]}"
        )
        time.sleep(min(8.0, 0.75 * lock_attempt) + random.uniform(0.1, 0.6))


def group_slide_jobs(slides: list[Slide], batch_size: int) -> list[tuple[int, Slide]]:
    size = max(1, batch_size)
    return [((index // size) + 1, slide) for index, slide in enumerate(slides)]


def group_jobs_by_batch(jobs: list[tuple[int, Slide]]) -> dict[int, list[Slide]]:
    grouped: dict[int, list[Slide]] = {}
    for batch_index, slide in jobs:
        grouped.setdefault(batch_index, []).append(slide)
    return grouped


def generate_claude_slide(
    *,
    slide: Slide,
    project_path: Path,
    prefix: str,
    claude_exe: str,
    env: dict[str, str],
    claude_timeout: int,
    claude_retries: int,
    syntax_repair_api_key: str,
    syntax_repair_base_url: str,
    syntax_repair_model: str,
    logger: UsageLogger | None,
    batch_index: int | None = None,
    scope_id: str | None = None,
) -> None:
    output_path = project_path / "svg_output" / slide.svg_filename
    if output_path.exists() and output_path.stat().st_size > 0:
        if logger:
            logger.log("claude_svg", slide=slide.svg_filename, ok=True, skipped=True, batch=batch_index)
        return
    prompt = build_svg_prompt(prefix, slide)
    tool_mode = claude_tool_mode()
    tool_args = claude_tool_args(tool_mode)
    output_format = claude_output_format()
    if tool_mode != "disabled":
        prompt = append_tool_experiment_prompt(prompt, slide, tool_mode)
    claude_env = scoped_claude_env(env, scope_id or f"slide_{slide.index:02d}_{slide.stem}")
    attempts = max(1, claude_retries + 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        stream_log_path = (
            project_path / "logs" / "claude_stream" / f"{slide.stem}.attempt{attempt}.jsonl"
            if output_format == "stream-json"
            else None
        )
        if logger and stream_log_path is not None:
            logger.log(
                "claude_stream",
                event="start",
                slide=slide.svg_filename,
                batch=batch_index,
                attempt=attempt,
                output_format=output_format,
                tool_mode=tool_mode,
                stream_log=str(stream_log_path.relative_to(project_path)),
            )
        try:
            stdout, stderr, returncode, duration = run_claude_print(
                claude_command(claude_exe, tool_args=tool_args, output_format=output_format),
                prompt=prompt,
                cwd=project_path,
                env=claude_env,
                timeout=claude_timeout,
                stream_log_path=stream_log_path,
            )
            if returncode != 0:
                (project_path / "logs" / f"claude_{slide.stem}.attempt{attempt}.stderr.txt").write_text(stderr, encoding="utf-8")
                (project_path / "logs" / f"claude_{slide.stem}.attempt{attempt}.stdout.txt").write_text(stdout, encoding="utf-8")
                if logger:
                    logger.log_transcript(
                        "claude_svg",
                        prompt=prompt,
                        stdout=stdout,
                        stderr=stderr,
                        metadata={
                            "slide": slide.svg_filename,
                            "ok": False,
                            "returncode": returncode,
                            "duration_seconds": round(duration, 3),
                            "batch": batch_index,
                            "attempt": attempt,
                            "tool_mode": tool_mode,
                            "tool_args": tool_args,
                            "output_format": output_format,
                            "stream_log": str(stream_log_path.relative_to(project_path)) if stream_log_path else None,
                        },
                    )
                raise GenerationError(f"Claude SVG generation failed for {slide.svg_filename}: {(stderr or stdout).strip()}")
            text, usage = parse_claude_json_output(stdout)
            recovered_from_tool_write = False
            syntax_repaired_by_api = False
            syntax_repair_usage: dict[str, Any] | None = None
            try:
                svg = extract_svg(text)
            except Exception as exc:
                if tool_mode != "disabled" and output_path.exists() and output_path.stat().st_size > 0:
                    try:
                        svg = extract_svg(output_path.read_text(encoding="utf-8", errors="replace"))
                        recovered_from_tool_write = True
                    except Exception:
                        recovered_from_tool_write = False
                    if recovered_from_tool_write:
                        append_text = (
                            f"\n\n[runner recovered SVG from tool-written file: "
                            f"{output_path.relative_to(project_path)}]"
                        )
                        text = f"{text}{append_text}"
                if not recovered_from_tool_write and is_svg_xml_syntax_error(exc):
                    repair_prompt = ""
                    repair_response = ""
                    try:
                        repair_prompt = build_svg_syntax_repair_prompt(extract_svg_document(text), str(exc))
                        repair_response, syntax_repair_usage = call_deepseek_anthropic(
                            api_key=syntax_repair_api_key,
                            base_url=syntax_repair_base_url,
                            model=syntax_repair_model,
                            prompt=repair_prompt,
                            system=SVG_SYNTAX_REPAIR_SYSTEM,
                            max_tokens=16000,
                        )
                        svg = extract_svg(repair_response)
                        syntax_repaired_by_api = True
                        text = f"{text}\n\n[runner repaired SVG XML syntax via direct API]"
                        if logger:
                            logger.log_transcript(
                                "deepseek_svg_syntax_repair",
                                prompt=repair_prompt,
                                response=repair_response,
                                metadata={
                                    "slide": slide.svg_filename,
                                    "ok": True,
                                    "source_error": str(exc),
                                    "attempt": attempt,
                                    "model": syntax_repair_model,
                                    "usage": syntax_repair_usage,
                                },
                            )
                            logger.log(
                                "deepseek_svg_syntax_repair",
                                slide=slide.svg_filename,
                                ok=True,
                                attempt=attempt,
                                model=syntax_repair_model,
                                usage=syntax_repair_usage,
                                prompt_chars=len(repair_prompt),
                                output_chars=len(repair_response),
                            )
                    except Exception as repair_exc:
                        if logger:
                            logger.log_transcript(
                                "deepseek_svg_syntax_repair",
                                prompt=repair_prompt,
                                response=repair_response,
                                metadata={
                                    "slide": slide.svg_filename,
                                    "ok": False,
                                    "source_error": str(exc),
                                    "repair_error": str(repair_exc),
                                    "attempt": attempt,
                                    "model": syntax_repair_model,
                                    "usage": syntax_repair_usage,
                                },
                            )
                            logger.log(
                                "deepseek_svg_syntax_repair",
                                slide=slide.svg_filename,
                                ok=False,
                                attempt=attempt,
                                model=syntax_repair_model,
                                error=str(repair_exc),
                            )
                if not recovered_from_tool_write:
                    if not syntax_repaired_by_api:
                        svg = ""
                if not recovered_from_tool_write and not syntax_repaired_by_api and logger:
                    logger.log_transcript(
                        "claude_svg",
                        prompt=prompt,
                        response=text,
                        stdout=stdout,
                        stderr=stderr,
                        metadata={
                            "slide": slide.svg_filename,
                            "ok": False,
                            "returncode": returncode,
                            "validated_svg": False,
                            "validation_error": str(exc),
                            "duration_seconds": round(duration, 3),
                            "usage": usage,
                            "batch": batch_index,
                            "attempt": attempt,
                            "tool_mode": tool_mode,
                            "tool_args": tool_args,
                            "output_format": output_format,
                            "stream_log": str(stream_log_path.relative_to(project_path)) if stream_log_path else None,
                            "tool_audit": f"logs/{tool_audit_filename(slide)}" if tool_mode != "disabled" else None,
                            "syntax_repaired_by_api": syntax_repaired_by_api,
                            "syntax_repair_model": syntax_repair_model if syntax_repaired_by_api else None,
                            "syntax_repair_usage": syntax_repair_usage,
                        },
                    )
                if not recovered_from_tool_write and not syntax_repaired_by_api:
                    raise
            if logger:
                logger.log_transcript(
                    "claude_svg",
                    prompt=prompt,
                    response=text,
                    stdout=stdout,
                    stderr=stderr,
                    metadata={
                        "slide": slide.svg_filename,
                        "ok": True,
                        "returncode": returncode,
                        "validated_svg": True,
                        "duration_seconds": round(duration, 3),
                        "usage": usage,
                        "batch": batch_index,
                        "attempt": attempt,
                        "tool_mode": tool_mode,
                        "tool_args": tool_args,
                        "output_format": output_format,
                        "stream_log": str(stream_log_path.relative_to(project_path)) if stream_log_path else None,
                        "tool_audit": f"logs/{tool_audit_filename(slide)}" if tool_mode != "disabled" else None,
                        "recovered_from_tool_write": recovered_from_tool_write,
                        "syntax_repaired_by_api": syntax_repaired_by_api,
                        "syntax_repair_model": syntax_repair_model if syntax_repaired_by_api else None,
                        "syntax_repair_usage": syntax_repair_usage,
                    },
                )
            output_path.write_text(svg, encoding="utf-8")
            if logger:
                logger.log(
                    "claude_svg",
                    slide=slide.svg_filename,
                    ok=True,
                    usage=usage,
                    duration_seconds=round(duration, 3),
                    prompt_chars=len(prompt),
                    output_chars=len(stdout),
                    batch=batch_index,
                    attempt=attempt,
                    tool_mode=tool_mode,
                    output_format=output_format,
                    stream_log=str(stream_log_path.relative_to(project_path)) if stream_log_path else None,
                    tool_audit=f"logs/{tool_audit_filename(slide)}" if tool_mode != "disabled" else None,
                    recovered_from_tool_write=recovered_from_tool_write,
                    syntax_repaired_by_api=syntax_repaired_by_api,
                    syntax_repair_model=syntax_repair_model if syntax_repaired_by_api else None,
                )
            return
        except Exception as exc:
            last_error = exc
            (project_path / "logs" / f"claude_{slide.stem}.attempt{attempt}.error.txt").write_text(str(exc), encoding="utf-8")
            if logger:
                logger.log(
                    "claude_svg",
                    slide=slide.svg_filename,
                    ok=False,
                    error=str(exc),
                    prompt_chars=len(prompt),
                    batch=batch_index,
                    attempt=attempt,
                    retrying=attempt < attempts,
                )
            if attempt < attempts:
                time.sleep(min(30, 5 * attempt))
                continue
            raise last_error


def generate_svg_files(
    *,
    project_path: Path,
    deck: Deck,
    canvas_format: str,
    style: str,
    renderer: str,
    deepseek_api_key: str | None,
    deepseek_base_url: str = DEFAULT_BASE_URL,
    claude_model: str = CLAUDE_MODEL,
    claude_flash_model: str = CLAUDE_FLASH_MODEL,
    claude_effort: str = "high",
    claude_timeout: int = 600,
    claude_retries: int = 1,
    svg_workers: int = 1,
    svg_batch_size: int = 5,
    cache_prime: bool = False,
    cookbook: Cookbook | None = None,
    logger: UsageLogger | None = None,
) -> None:
    if renderer == "local":
        for slide in deck.slides:
            (project_path / "svg_output" / slide.svg_filename).write_text(
                deterministic_svg(slide, deck, canvas_format),
                encoding="utf-8",
            )
        return

    claude_exe = shutil.which("claude")
    if not claude_exe:
        raise GenerationError("Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code@latest")
    version = subprocess.run([claude_exe, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if version.returncode != 0:
        raise GenerationError("Claude Code CLI preflight failed. Install/update with: npm install -g @anthropic-ai/claude-code@latest")
    resolved_key = deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not resolved_key:
        raise GenerationError("DeepSeek API key is required for Claude SVG generation.")

    env = os.environ.copy()
    env.update(
        {
            "ANTHROPIC_BASE_URL": deepseek_base_url,
            "ANTHROPIC_AUTH_TOKEN": resolved_key,
            "ANTHROPIC_MODEL": claude_model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": claude_model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": claude_model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": claude_flash_model,
            "CLAUDE_CODE_SUBAGENT_MODEL": claude_flash_model,
            "CLAUDE_CODE_EFFORT_LEVEL": claude_effort,
        }
    )
    if not truthy_env(os.environ.get("PPT_MASTER_CLAUDE_SHARE_CONFIG")):
        env["PPT_MASTER_CLAUDE_CONFIG_BASE"] = str(claude_config_base(project_path))
    prefix = build_svg_prompt_prefix(project_path, deck, canvas_format, style, cookbook)
    if cache_prime:
        prime_prompt = build_deck_context_prefix(deck, canvas_format, style, cookbook)
        try:
            prime_env = scoped_claude_env(env, "cache_prime")
            stdout, stderr, returncode, duration = run_claude_print(
                [
                    claude_exe,
                    "-p",
                    "--output-format",
                    "json",
                    "--input-format",
                    "text",
                    "--tools=",
                ],
                prompt=prime_prompt,
                cwd=project_path,
                env=prime_env,
                timeout=min(claude_timeout, 180),
            )
            text, usage = parse_claude_json_output(stdout)
            if logger:
                logger.log_transcript(
                    "claude_cache_prime",
                    prompt=prime_prompt,
                    response=text,
                    stdout=stdout,
                    stderr=stderr,
                    metadata={
                        "ok": returncode == 0,
                        "returncode": returncode,
                        "duration_seconds": round(duration, 3),
                        "usage": usage,
                        "scope": "common_prefix",
                    },
                )
                logger.log(
                    "claude_cache_prime",
                    ok=returncode == 0,
                    usage=usage,
                    duration_seconds=round(duration, 3),
                    prompt_chars=len(prime_prompt),
                    output_chars=len(stdout),
                    stderr_chars=len(stderr),
                    scope="common_prefix",
                )
        except Exception as exc:
            if logger:
                logger.log("claude_cache_prime", ok=False, error=str(exc), prompt_chars=len(prime_prompt), scope="common_prefix")
    workers = max(1, svg_workers)
    jobs = group_slide_jobs(deck.slides, svg_batch_size)
    if not jobs:
        return
    batches = group_jobs_by_batch(jobs)
    if logger:
        logger.log(
            "claude_parallel",
            workers=workers,
            batch_size=svg_batch_size,
            batches=len(batches),
            slides=len(deck.slides),
            scheduler="slide",
        )
        for batch_index, slides in batches.items():
            logger.log(
                "claude_batch",
                batch=batch_index,
                ok=True,
                event="scheduled",
                scheduler="slide",
                slides=[slide.svg_filename for slide in slides],
            )

    remaining_by_batch = {batch_index: len(slides) for batch_index, slides in batches.items()}
    with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as executor:
        futures = {
            executor.submit(
                generate_claude_slide,
                slide=slide,
                project_path=project_path,
                prefix=prefix,
                claude_exe=claude_exe,
                env=env,
                claude_timeout=claude_timeout,
                claude_retries=claude_retries,
                syntax_repair_api_key=resolved_key,
                syntax_repair_base_url=deepseek_base_url,
                syntax_repair_model=claude_flash_model,
                logger=logger,
                batch_index=batch_index,
                scope_id=f"slide_{slide.index:02d}_{slide.stem}",
            ): batch_index
            for batch_index, slide in jobs
        }
        for future in as_completed(futures):
            batch_index = futures[future]
            future.result()
            remaining_by_batch[batch_index] -= 1
            if logger and remaining_by_batch[batch_index] == 0:
                logger.log(
                    "claude_batch",
                    batch=batch_index,
                    ok=True,
                    event="finish",
                    scheduler="slide",
                    slides=len(batches[batch_index]),
                )
