"""SVG generation, prompt files, and Claude Code execution."""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape as xml_escape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .config import CLAUDE_FLASH_MODEL, CLAUDE_MODEL, DEFAULT_BASE_URL, REPO_ROOT, canvas_dimensions
from .errors import GenerationError
from .parser import Deck, Slide
from .planner import ICON_INVENTORY, build_deck_context_prefix, build_design_plan_prompt, build_notes_prompt
from .usage import UsageLogger
from clean_svg_entities import clean_svg_entities


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


def build_svg_prompt_prefix(project_path: Path, deck: Deck, canvas_format: str, style: str) -> str:
    _, _, _, canvas = canvas_dimensions(canvas_format)
    common_prefix = build_deck_context_prefix(deck, canvas_format, style)
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
- Keep the deck theme continuous: the locked primary accent (`#1D4ED8` unless spec_lock says otherwise) must be the dominant non-neutral accent on every slide. Teal, amber, and extra colors may add richness, but they must not make one slide feel like a green/orange/other-theme page.
- XML reserved characters in text must be escaped.
- Text wrapping must use `<text>` and `<tspan>`.
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


def build_svg_batch_prompt(prefix: str, slides: list[Slide], *, repair_reason: str | None = None) -> str:
    slide_blocks: list[str] = []
    for slide in slides:
        slide_blocks.append(
            f"""FILE: {slide.svg_filename}
Slide number: P{slide.index:02d}
Slide title: {slide.title}
Current page source Markdown:
```markdown
{slide.raw_markdown}
```"""
        )
    repair_block = ""
    if repair_reason:
        repair_block = f"""

Continuation/repair context:
{repair_reason}
Generate only the files listed below. Do not repeat files that already succeeded.
"""
    return f"""{prefix}

Current batch task:
- Write exactly {len(slides)} complete SVG documents, one for each requested file below.
- Return no prose, no markdown fences, and no progress notes.
- Use this exact repeated output format for each file:
FILE: filename.svg
<svg ...>...</svg>
END_FILE
- Each SVG must be complete, standalone, XML-valid, and must use the correct slide content.
- Do not merge multiple slides into one SVG.
{repair_block}
Requested files:

{chr(10).join(slide_blocks)}
"""


def write_prompt_files(project_path: Path, deck: Deck, canvas_format: str, style: str) -> None:
    prompt_dir = project_path / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "design_plan_prompt.md").write_text(build_design_plan_prompt(deck, canvas_format, style), encoding="utf-8")
    (prompt_dir / "notes_prompt.md").write_text(build_notes_prompt(deck, canvas_format, style), encoding="utf-8")
    prefix = build_svg_prompt_prefix(project_path, deck, canvas_format, style)
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


def extract_svg(text: str) -> str:
    normalized_text = normalize_svg_text(text)
    start = normalized_text.find("<svg")
    end = normalized_text.rfind("</svg>")
    if start < 0 or end < 0:
        raise GenerationError("Claude output did not contain a complete <svg> document.")
    svg = normalize_svg_text(normalized_text[start : end + len("</svg>")])
    try:
        ET.fromstring(svg)
    except ET.ParseError as exc:
        raise GenerationError(f"Claude output contained invalid SVG XML: {exc}") from exc
    return svg


def extract_svg_documents(text: str) -> list[str]:
    """Extract every complete SVG document from a model response."""

    normalized_text = normalize_svg_text(text)
    documents: list[str] = []
    cursor = 0
    while True:
        start = normalized_text.find("<svg", cursor)
        if start < 0:
            break
        end = normalized_text.find("</svg>", start)
        if end < 0:
            break
        end += len("</svg>")
        documents.append(extract_svg(normalized_text[start:end]))
        cursor = end
    return documents


def normalize_svg_filename(value: str) -> str:
    cleaned = value.strip().strip("`").strip()
    cleaned = cleaned.replace("\\", "/").split("/")[-1]
    return cleaned.strip()


def parse_svg_batch_output(text: str, slides: list[Slide]) -> tuple[dict[str, str], dict[str, str]]:
    """Parse a batch response into validated SVGs keyed by expected filename.

    The preferred model contract uses `FILE: name.svg` markers. If the model
    omits markers but returns the right number of SVG documents, fall back to
    assigning documents by requested slide order.
    """

    expected = {slide.svg_filename: slide for slide in slides}
    parsed: dict[str, str] = {}
    errors: dict[str, str] = {}
    marker_pattern = re.compile(r"(?im)^\s*FILE:\s*`?([^`\r\n]+?\.svg)`?\s*$")
    matches = list(marker_pattern.finditer(text))

    for index, match in enumerate(matches):
        filename = normalize_svg_filename(match.group(1))
        if filename not in expected:
            continue
        segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.end() : segment_end]
        try:
            parsed[filename] = extract_svg(segment)
        except Exception as exc:
            errors[filename] = str(exc)

    if not parsed and not matches:
        try:
            documents = extract_svg_documents(text)
        except Exception as exc:
            documents = []
            errors["__batch__"] = str(exc)
        if len(documents) == len(slides):
            parsed = {slide.svg_filename: svg for slide, svg in zip(slides, documents)}
        elif documents:
            for slide, svg in zip(slides, documents):
                parsed[slide.svg_filename] = svg
            if len(documents) < len(slides):
                for slide in slides[len(documents) :]:
                    errors[slide.svg_filename] = "Batch output did not include this SVG document."

    for slide in slides:
        if slide.svg_filename not in parsed and slide.svg_filename not in errors:
            errors[slide.svg_filename] = "Batch output did not include this SVG document."
    return parsed, errors


def parse_claude_json_output(stdout: str) -> tuple[str, dict[str, Any]]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout, {}
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


def run_claude_print(command: list[str], *, prompt: str, cwd: Path, env: dict[str, str], timeout: int) -> tuple[str, str, int, float]:
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
            stdout, stderr = process.communicate(prompt, timeout=timeout)
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


def chunk_slides(slides: list[Slide], batch_size: int) -> list[list[Slide]]:
    size = max(1, batch_size)
    return [slides[index : index + size] for index in range(0, len(slides), size)]


def generate_claude_slide(
    *,
    slide: Slide,
    project_path: Path,
    prefix: str,
    claude_exe: str,
    env: dict[str, str],
    claude_timeout: int,
    claude_retries: int,
    logger: UsageLogger | None,
    batch_index: int | None = None,
) -> None:
    output_path = project_path / "svg_output" / slide.svg_filename
    if output_path.exists() and output_path.stat().st_size > 0:
        if logger:
            logger.log("claude_svg", slide=slide.svg_filename, ok=True, skipped=True, batch=batch_index)
        return
    prompt = build_svg_prompt(prefix, slide)
    claude_env = scoped_claude_env(env, f"batch_{batch_index or 0:02d}")
    attempts = max(1, claude_retries + 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
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
                prompt=prompt,
                cwd=project_path,
                env=claude_env,
                timeout=claude_timeout,
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
                        },
                    )
                raise GenerationError(f"Claude SVG generation failed for {slide.svg_filename}: {(stderr or stdout).strip()}")
            text, usage = parse_claude_json_output(stdout)
            try:
                svg = extract_svg(text)
            except Exception as exc:
                if logger:
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
                        },
                    )
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


def generate_claude_batch(
    *,
    slides: list[Slide],
    batch_index: int,
    project_path: Path,
    prefix: str,
    claude_exe: str,
    env: dict[str, str],
    claude_timeout: int,
    claude_retries: int,
    logger: UsageLogger | None,
) -> None:
    if logger:
        logger.log(
            "claude_batch",
            batch=batch_index,
            ok=True,
            event="start",
            slides=[slide.svg_filename for slide in slides],
        )
    for slide in slides:
        generate_claude_slide(
            slide=slide,
            project_path=project_path,
            prefix=prefix,
            claude_exe=claude_exe,
            env=env,
            claude_timeout=claude_timeout,
            claude_retries=claude_retries,
            logger=logger,
            batch_index=batch_index,
        )
    if logger:
        logger.log("claude_batch", batch=batch_index, ok=True, event="finish", slides=len(slides))


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
    prefix = build_svg_prompt_prefix(project_path, deck, canvas_format, style)
    if cache_prime:
        prime_prompt = build_deck_context_prefix(deck, canvas_format, style)
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
    batches = chunk_slides(deck.slides, svg_batch_size)
    if logger:
        logger.log("claude_parallel", workers=workers, batch_size=svg_batch_size, batches=len(batches), slides=len(deck.slides))
    if workers == 1 or len(batches) <= 1:
        for batch_index, slides in enumerate(batches, start=1):
            generate_claude_batch(
                slides=slides,
                batch_index=batch_index,
                project_path=project_path,
                prefix=prefix,
                claude_exe=claude_exe,
                env=env,
                claude_timeout=claude_timeout,
                claude_retries=claude_retries,
                logger=logger,
            )
        return

    with ThreadPoolExecutor(max_workers=min(workers, len(batches))) as executor:
        futures = [
            executor.submit(
                generate_claude_batch,
                slides=slides,
                batch_index=batch_index,
                project_path=project_path,
                prefix=prefix,
                claude_exe=claude_exe,
                env=env,
                claude_timeout=claude_timeout,
                claude_retries=claude_retries,
                logger=logger,
            )
            for batch_index, slides in enumerate(batches, start=1)
        ]
        for future in as_completed(futures):
            future.result()
