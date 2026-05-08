"""SVG generation, prompt files, and direct DeepSeek API execution."""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape as xml_escape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .config import DEFAULT_BASE_URL, SVG_MODEL, SVG_REPAIR_MODEL, canvas_dimensions
from .cookbook import Cookbook
from .errors import GenerationError
from .parser import Deck, Slide
from .planner import ICON_INVENTORY, build_deck_context_prefix, build_design_plan_prompt, build_notes_prompt, call_deepseek_anthropic
from .usage import UsageLogger
from clean_svg_entities import clean_svg_entities

SVG_SYNTAX_REPAIR_SYSTEM = (
    "You repair SVG XML syntax only. Return exactly one complete SVG document and no prose."
)
SVG_GENERATION_SYSTEM = (
    "You are PPT Master SVG renderer. Return exactly one complete valid SVG document and no prose."
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
                                "color_role",
                                "density_plan",
                                "card_anatomy",
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
- Use font-family values exactly from spec_lock typography. Do not invent `Noto Sans SC` or other unlisted font names; primary SVG export should stay on PPT-safe stacks such as Microsoft YaHei / Arial.
- Use inline SVG attributes only.
- Forbidden: `<style>`, `class`, `<foreignObject>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, `<mask>`, HTML named entities, `<g opacity>`, `<image opacity>`, and `clip-path` outside simple image crops.
- `clip-path` is allowed only on `<image>` for simple photo/avatar crops, and only with a matching single-shape `<clipPath>` in `<defs>`. Never use clip-path on shapes, groups, text, charts, or decorative overlays.
- Light-canvas theme only: the root background must be `#FFFFFF` or near-white. Controlled color rails, soft-tint cards, chart regions, image overlays, and small/medium section accents are allowed when text contrast remains strong; avoid large saturated color blocks. Do not use dark full-slide backgrounds, GitHub-dark palette, or neon-on-black styling.
- Keep the deck theme continuous through locked compact palette, typography, spacing, page chrome, and component grammar. The primary accent should recur across the deck, but it does not need to dominate every slide; use the current page spec to choose one leading accent and one supporting accent from spec_lock/cookbook.
- XML reserved characters in text must be escaped.
- Text wrapping and inline emphasis must use `<text>` and `<tspan>` only. Never use HTML `<span>`; write `<tspan fill="#..." font-weight="...">...</tspan>`.
- Group related elements with plain `<g>`; never use `<g opacity>`.
- Use the current page source Markdown as the source of visible content. The global manifest is only for deck context.
- Follow the current slide's `layout_signature`, `visual_structure`, and `visual_guidance` from Design Plan JSON. These are soft structure instructions, not exact coordinates.
- Treat `visual_guidance` as the aesthetic execution brief: implement its card geometry, label placement, chart skin, decorative motif, whitespace rhythm, and accent hierarchy instead of falling back to a generic card page.
- Apply current-page spec fields deliberately:
  - `rhythm` controls macro pacing and visual weight; `content_density` and `density_plan` control visible text volume.
  - `layout_signature` is the page blueprint; draw that structure before adding details.
  - `composition` defines reading order and major regions.
  - `visual_structure` names the visible primitives to create.
  - `why_this_layout` explains the slide's emphasis; preserve that emphasis.
  - `visual_metaphor` should appear as a visible but controlled motif, not a distracting illustration.
  - `color_role` names the leading accent and supporting accent for this page; apply those colors to hierarchy, headers, chips, one chart series, connector lines, or callouts rather than defaulting everything to primary blue. Keep neutral surfaces dominant.
  - `density_plan` is the visible information and component-density budget; follow its requested cards, labels, captions, metric chips, evidence phrases, and blank-space control unless it would cause collisions.
  - `card_anatomy` is mandatory when cards exist; build those internal structures instead of drawing identical blank rectangles with centered text.
  - `icon_plan` should be implemented with `<use data-icon="...">` placeholders when icons add meaning.
  - `chart_or_diagram` chooses the visualization geometry; restyle it in the locked theme rather than swapping to a generic card grid.
  - `content_density` decides how much text to keep visible and how aggressively to summarize.
- Text density execution:
  - `low`: 1-2 visible text units; use only for intentional breathing, quote, cover, or closing pages.
  - `medium`: normal content page; usually keep a headline plus 4-6 visible content units with short body phrases, labels, captions, or metric explanations.
  - `high`: evidence-rich page; use compact typography and strong grouping to keep 5-7 content units readable.
  - `showcase`: visual-dominant page; keep the hero visual large, but include supporting specs, labels, or metric chips so it does not feel empty.
- Page fullness execution: normal content pages should use about 75-85% of the safe content area with meaningful components. Fill empty quadrants with relevant diagrams, comparison strips, metric chips, captions, callout bands, or image/diagram panels; do not add decorative clutter or text collisions.
- Card creativity execution: preserve shared card outer geometry from spec_lock/cookbook, but vary card interiors by role. Combine header badges, side rails, corner numbers, icon pockets, metric chips, micro-chart strips, nested callout bands, status dots, or connector notches. Do not make a row of cards differ only by text.
- If the current page uses a real data chart, wrap it in `<g id="chartArea">` and include a `<!-- chart-plot-area: ... -->` marker before the first data mark.
- Avoid collapsing specific layout guidance into a generic two-column card page. If the plan asks for a chart, matrix, roadmap, dashboard, network, architecture, product view, or profile wall, build that visible structure.
- Produce a polished slide, not a plain document dump: strong hierarchy, intentional whitespace, aligned panels/cards/diagrams, deliberate color roles, and no text collisions.
- If a slide is dense, summarize into key phrases and speaker-note-level detail rather than overfilling the canvas; do not over-compress medium/high pages into a few sparse labels.
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


def build_current_page_spec_excerpt(project_path: Path, slide: Slide) -> str:
    """Extract the current slide's spec tail so recency reinforces page execution."""

    page_key = f"P{slide.index:02d}"
    payload: dict[str, Any] = {
        "page": page_key,
        "svg_filename": slide.svg_filename,
        "design_plan_slide": {},
        "spec_lock_page": {},
    }

    design_path = project_path / "design_plan.json"
    if design_path.exists():
        try:
            design_data = json.loads(design_path.read_text(encoding="utf-8", errors="replace"))
            for item in design_data.get("slides", []):
                if not isinstance(item, dict):
                    continue
                if item.get("index") == slide.index or item.get("svg_filename") == slide.svg_filename:
                    payload["design_plan_slide"] = item
                    break
        except Exception:
            payload["design_plan_slide"] = {}

    lock_path = project_path / "spec_lock.json"
    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8", errors="replace"))
            chart_rules = lock_data.get("chart_rules", {}) if isinstance(lock_data, dict) else {}
            style_anchor = lock_data.get("style_anchor", {}) if isinstance(lock_data, dict) else {}
            theme_color_policy = lock_data.get("theme_color_policy", {}) if isinstance(lock_data, dict) else {}
            page_rhythm = lock_data.get("page_rhythm", {}) if isinstance(lock_data, dict) else {}
            payload["spec_lock_page"] = {
                "page_rhythm": page_rhythm.get(page_key) if isinstance(page_rhythm, dict) else None,
                "shape_language": lock_data.get("shape_language", {}),
                "spacing": lock_data.get("spacing", {}),
                "style_anchor_repeat": style_anchor.get("repeat") if isinstance(style_anchor, dict) else None,
                "style_anchor_vary": style_anchor.get("vary") if isinstance(style_anchor, dict) else None,
                "theme_color_policy": theme_color_policy,
                "chart_rules_style": chart_rules.get("style") if isinstance(chart_rules, dict) else None,
                "chart_rules_selection_policy": chart_rules.get("selection_policy") if isinstance(chart_rules, dict) else None,
                "svg_forbidden": (lock_data.get("svg_rules") or {}).get("forbid", []) if isinstance(lock_data.get("svg_rules"), dict) else [],
            }
        except Exception:
            payload["spec_lock_page"] = {}

    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_svg_prompt(prefix: str, slide: Slide, current_page_spec: str | None = None) -> str:
    page_spec = current_page_spec or "{}"
    return f"""{prefix}

Current page task:
- Write only this slide SVG: `{slide.svg_filename}`
- Slide number: P{slide.index:02d}
- Slide title: {slide.title}

Current page source Markdown:
```markdown
{slide.raw_markdown}
```

Current page design/spec excerpt JSON:
{page_spec}
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
        page_spec = build_current_page_spec_excerpt(project_path, slide)
        (page_dir / f"{slide.stem}.md").write_text(build_svg_prompt(prefix, slide, page_spec), encoding="utf-8")


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
        raise GenerationError("DeepSeek SVG output did not contain a complete <svg> document.")
    return normalize_svg_text(normalized_text[start : end + len("</svg>")])


def extract_svg(text: str) -> str:
    svg = extract_svg_document(text)
    try:
        ET.fromstring(svg)
    except ET.ParseError as exc:
        raise GenerationError(f"DeepSeek SVG output contained invalid SVG XML: {exc}") from exc
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


def group_slide_jobs(slides: list[Slide], batch_size: int) -> list[tuple[int, Slide]]:
    size = max(1, batch_size)
    return [((index // size) + 1, slide) for index, slide in enumerate(slides)]


def group_jobs_by_batch(jobs: list[tuple[int, Slide]]) -> dict[int, list[Slide]]:
    grouped: dict[int, list[Slide]] = {}
    for batch_index, slide in jobs:
        grouped.setdefault(batch_index, []).append(slide)
    return grouped


def generate_deepseek_svg_slide(
    *,
    slide: Slide,
    project_path: Path,
    prefix: str,
    api_key: str,
    base_url: str,
    svg_model: str,
    svg_repair_model: str,
    svg_timeout: int,
    svg_retries: int,
    logger: UsageLogger | None,
    batch_index: int | None = None,
) -> None:
    output_path = project_path / "svg_output" / slide.svg_filename
    if output_path.exists() and output_path.stat().st_size > 0:
        if logger:
            logger.log("deepseek_svg", slide=slide.svg_filename, ok=True, skipped=True, batch=batch_index)
        return
    prompt = build_svg_prompt(prefix, slide, build_current_page_spec_excerpt(project_path, slide))
    attempts = max(1, svg_retries + 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        text = ""
        usage: dict[str, Any] = {}
        duration = 0.0
        try:
            started = time.perf_counter()
            text, usage = call_deepseek_anthropic(
                api_key=api_key,
                base_url=base_url,
                model=svg_model,
                prompt=prompt,
                system=SVG_GENERATION_SYSTEM,
                max_tokens=32000,
                timeout=svg_timeout,
            )
            duration = time.perf_counter() - started
            syntax_repaired_by_api = False
            syntax_repair_usage: dict[str, Any] | None = None
            try:
                svg = extract_svg(text)
            except Exception as exc:
                if is_svg_xml_syntax_error(exc):
                    repair_prompt = ""
                    repair_response = ""
                    try:
                        repair_prompt = build_svg_syntax_repair_prompt(extract_svg_document(text), str(exc))
                        repair_response, syntax_repair_usage = call_deepseek_anthropic(
                            api_key=api_key,
                            base_url=base_url,
                            model=svg_repair_model,
                            prompt=repair_prompt,
                            system=SVG_SYNTAX_REPAIR_SYSTEM,
                            max_tokens=16000,
                            timeout=svg_timeout,
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
                                    "model": svg_repair_model,
                                    "usage": syntax_repair_usage,
                                },
                            )
                            logger.log(
                                "deepseek_svg_syntax_repair",
                                slide=slide.svg_filename,
                                ok=True,
                                attempt=attempt,
                                model=svg_repair_model,
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
                                    "model": svg_repair_model,
                                    "usage": syntax_repair_usage,
                                },
                            )
                            logger.log(
                                "deepseek_svg_syntax_repair",
                                slide=slide.svg_filename,
                                ok=False,
                                attempt=attempt,
                                model=svg_repair_model,
                                error=str(repair_exc),
                            )
                if not syntax_repaired_by_api:
                    svg = ""
                if not syntax_repaired_by_api and logger:
                    logger.log_transcript(
                        "deepseek_svg",
                        system=SVG_GENERATION_SYSTEM,
                        prompt=prompt,
                        response=text,
                        metadata={
                            "slide": slide.svg_filename,
                            "ok": False,
                            "validated_svg": False,
                            "validation_error": str(exc),
                            "duration_seconds": round(duration, 3),
                            "usage": usage,
                            "model": svg_model,
                            "batch": batch_index,
                            "attempt": attempt,
                            "syntax_repaired_by_api": syntax_repaired_by_api,
                            "syntax_repair_model": svg_repair_model if syntax_repaired_by_api else None,
                            "syntax_repair_usage": syntax_repair_usage,
                        },
                    )
                if not syntax_repaired_by_api:
                    raise
            if logger:
                logger.log_transcript(
                    "deepseek_svg",
                    system=SVG_GENERATION_SYSTEM,
                    prompt=prompt,
                    response=text,
                    metadata={
                        "slide": slide.svg_filename,
                        "ok": True,
                        "validated_svg": True,
                        "duration_seconds": round(duration, 3),
                        "usage": usage,
                        "model": svg_model,
                        "batch": batch_index,
                        "attempt": attempt,
                        "syntax_repaired_by_api": syntax_repaired_by_api,
                        "syntax_repair_model": svg_repair_model if syntax_repaired_by_api else None,
                        "syntax_repair_usage": syntax_repair_usage,
                    },
                )
            output_path.write_text(svg, encoding="utf-8")
            if logger:
                logger.log(
                    "deepseek_svg",
                    slide=slide.svg_filename,
                    ok=True,
                    usage=usage,
                    duration_seconds=round(duration, 3),
                    prompt_chars=len(prompt),
                    output_chars=len(text),
                    model=svg_model,
                    batch=batch_index,
                    attempt=attempt,
                    syntax_repaired_by_api=syntax_repaired_by_api,
                    syntax_repair_model=svg_repair_model if syntax_repaired_by_api else None,
                )
            return
        except Exception as exc:
            last_error = exc
            (project_path / "logs" / f"deepseek_{slide.stem}.attempt{attempt}.error.txt").write_text(str(exc), encoding="utf-8")
            if logger:
                logger.log(
                    "deepseek_svg",
                    slide=slide.svg_filename,
                    ok=False,
                    error=str(exc),
                    prompt_chars=len(prompt),
                    output_chars=len(text),
                    model=svg_model,
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
    svg_model: str = SVG_MODEL,
    svg_repair_model: str = SVG_REPAIR_MODEL,
    svg_timeout: int = 600,
    svg_retries: int = 1,
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

    resolved_key = deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not resolved_key:
        raise GenerationError("DeepSeek API key is required for direct SVG generation.")

    prefix = build_svg_prompt_prefix(project_path, deck, canvas_format, style, cookbook)
    if cache_prime:
        prime_prompt = prefix
        started = time.perf_counter()
        try:
            text, usage = call_deepseek_anthropic(
                api_key=resolved_key,
                base_url=deepseek_base_url,
                model=svg_model,
                prompt=prime_prompt,
                system=SVG_GENERATION_SYSTEM,
                max_tokens=8,
                timeout=min(svg_timeout, 180),
            )
            duration = time.perf_counter() - started
            if logger:
                logger.log_transcript(
                    "deepseek_svg_cache_prime",
                    system=SVG_GENERATION_SYSTEM,
                    prompt=prime_prompt,
                    response=text,
                    metadata={
                        "ok": True,
                        "duration_seconds": round(duration, 3),
                        "usage": usage,
                        "model": svg_model,
                        "scope": "common_prefix",
                    },
                )
                logger.log(
                    "deepseek_svg_cache_prime",
                    ok=True,
                    usage=usage,
                    duration_seconds=round(duration, 3),
                    prompt_chars=len(prime_prompt),
                    output_chars=len(text),
                    model=svg_model,
                    scope="common_prefix",
                )
        except Exception as exc:
            if logger:
                logger.log(
                    "deepseek_svg_cache_prime",
                    ok=False,
                    error=str(exc),
                    prompt_chars=len(prime_prompt),
                    model=svg_model,
                    scope="common_prefix",
                )
    workers = max(1, svg_workers)
    jobs = group_slide_jobs(deck.slides, svg_batch_size)
    if not jobs:
        return
    batches = group_jobs_by_batch(jobs)
    if logger:
        logger.log(
            "deepseek_parallel",
            workers=workers,
            batch_size=svg_batch_size,
            batches=len(batches),
            slides=len(deck.slides),
            scheduler="slide",
        )
        for batch_index, slides in batches.items():
            logger.log(
                "deepseek_batch",
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
                generate_deepseek_svg_slide,
                slide=slide,
                project_path=project_path,
                prefix=prefix,
                api_key=resolved_key,
                base_url=deepseek_base_url,
                svg_model=svg_model,
                svg_repair_model=svg_repair_model,
                svg_timeout=svg_timeout,
                svg_retries=svg_retries,
                logger=logger,
                batch_index=batch_index,
            ): batch_index
            for batch_index, slide in jobs
        }
        for future in as_completed(futures):
            batch_index = futures[future]
            future.result()
            remaining_by_batch[batch_index] -= 1
            if logger and remaining_by_batch[batch_index] == 0:
                logger.log(
                    "deepseek_batch",
                    batch=batch_index,
                    ok=True,
                    event="finish",
                    scheduler="slide",
                    slides=len(batches[batch_index]),
                )
