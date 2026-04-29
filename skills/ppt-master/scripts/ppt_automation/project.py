"""Project artifact management for automation mode."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import CANVAS_FORMATS, canvas_dimensions, normalized_format
from .parser import Deck, safe_project_name


@dataclass
class RunResult:
    ok: bool
    project_path: str | None
    pptx_path: str | None = None
    svg_pptx_path: str | None = None
    quality_report_path: str | None = None
    quality: dict[str, int] | None = None
    slides: int = 0
    dry_run: bool = False
    renderer: str = "claude"
    warnings: list[str] | None = None
    result_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["quality"] = self.quality or {"errors": 0, "warnings": 0}
        payload["warnings"] = self.warnings or []
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def create_project(project_name: str, canvas_format: str, base_dir: Path) -> Path:
    normalized = normalized_format(canvas_format)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{safe_project_name(project_name)}_{normalized}_{timestamp}"
    project_path = base_dir / stem
    suffix = 2
    while project_path.exists():
        project_path = base_dir / f"{stem}_{suffix}"
        suffix += 1

    for rel in (
        "svg_output",
        "svg_final",
        "images",
        "notes",
        "templates",
        "sources",
        "exports",
        "prompts",
        "logs",
    ):
        (project_path / rel).mkdir(parents=True, exist_ok=True)

    canvas_info = CANVAS_FORMATS[normalized]
    (project_path / "README.md").write_text(
        "\n".join(
            [
                f"# {project_name}",
                "",
                "- Created by: PPT Master automation pipeline",
                f"- Canvas format: {normalized}",
                f"- Dimensions: {canvas_info['dimensions']}",
                f"- Created: {timestamp}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project_path


def write_source(project_path: Path, markdown: str) -> Path:
    path = project_path / "sources" / "input.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def write_manifest(project_path: Path, deck: Deck) -> tuple[Path, Path]:
    md_lines = [
        "# Slide Manifest",
        "",
        f"- Deck title: {deck.title}",
        f"- Slide count: {len(deck.slides)}",
        "- Rule: manifest includes an automatic cover slide, content slides, and an automatic closing slide.",
        "- Rule: normal level-2 Markdown headings (`##`) map to content slides.",
        "- Rule: under the `创新技术` level-2 section, each level-3 heading (`###`) maps to its own content slide.",
        "- Rule: content before the first level-2 heading is preserved as front matter, not merged into the cover slide.",
        "",
    ]
    if deck.front_matter:
        md_lines.extend(["## Deck Front Matter", "", deck.front_matter, ""])
    for slide in deck.slides:
        md_lines.extend(
            [
                f"## P{slide.index:02d} - {slide.title}",
                "",
                f"- slug: `{slide.slug}`",
                f"- svg: `{slide.svg_filename}`",
                f"- kind: `{slide.kind}`",
                f"- section_title: {slide.section_title or ''}",
                "",
                "### Original Markdown",
                "",
                "```markdown",
                slide.raw_markdown,
                "```",
                "",
            ]
        )

    md_path = project_path / "slide_manifest.md"
    json_path = project_path / "slide_manifest.json"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    json_path.write_text(json.dumps(deck.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_result(project_path: Path, result: RunResult) -> Path:
    result_path = project_path / "result.json"
    result.result_path = str(result_path)
    result_path.write_text(result.to_json(), encoding="utf-8")
    return result_path


def render_design_plan_markdown(plan: dict[str, Any]) -> str:
    canvas = as_mapping(plan.get("canvas"))
    theme = as_mapping(plan.get("theme"))
    colors = as_mapping(theme.get("colors"))
    slides = plan.get("slides", [])
    if not isinstance(slides, list):
        slides = []
    lines = [
        f"# {plan.get('project_name', plan.get('deck_title', 'PPT'))} - Automation Design Plan",
        "",
        "## Project",
        "",
        f"- Deck title: {plan.get('deck_title', '')}",
        f"- Style: {plan.get('style', '')}",
        f"- Canvas: {canvas.get('name', '')} ({canvas.get('dimensions', '')})",
        f"- viewBox: `{canvas.get('viewbox', '')}`",
        f"- Slide count: {len(slides)}",
        "",
        "## Theme",
        "",
    ]
    for key, value in colors.items():
        lines.append(f"- {key}: {value}")
    for section_name, field_name in (
        ("Art Direction", "art_direction"),
        ("Layout System", "layout_system"),
        ("Component System", "component_system"),
    ):
        section_value = plan.get(field_name)
        if section_value:
            lines.extend(["", f"## {section_name}"])
            lines.extend(render_value_lines(section_value))
    lines.extend(["", "## Slides", ""])
    for slide_item in slides:
        slide = as_mapping(slide_item)
        lines.extend(
            [
                f"### P{int(slide.get('index', 0)):02d} - {slide.get('title', '')}",
                "",
                f"- SVG: `{slide.get('svg_filename', '')}`",
                f"- Kind: {slide.get('kind', '')}",
                f"- Section: {slide.get('section_title', '') or ''}",
                f"- Rhythm: {slide.get('rhythm', 'dense')}",
                f"- Layout: {slide.get('layout', '')}",
                f"- Layout family: {slide.get('layout_family', '')}",
                f"- Layout signature: {slide.get('layout_signature', '')}",
                f"- Intent: {slide.get('intent', '')}",
                f"- Composition: {slide.get('composition', '')}",
                f"- Visual structure: {slide.get('visual_structure', '')}",
                f"- Why this layout: {slide.get('why_this_layout', '')}",
                f"- Visual metaphor: {slide.get('visual_metaphor', '')}",
                f"- Visual guidance: {slide.get('visual_guidance', '')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def render_value_lines(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [f"- {key}: {item}" for key, item in value.items()]
    if isinstance(value, list):
        return [f"- {item}" for item in value]
    if value is None:
        return []
    return [f"- {value}"]


def render_spec_lock_markdown(lock: dict[str, Any]) -> str:
    lines = ["# Execution Lock", ""]
    canvas = as_mapping(lock.get("canvas"))
    lines.extend(
        [
            "## canvas",
            f"- viewBox: {canvas.get('viewbox', '')}",
            f"- format: {canvas.get('name', canvas.get('format', ''))}",
            "",
            "## colors",
        ]
    )
    lines.extend(render_value_lines(lock.get("colors", {})))
    lines.extend(["", "## typography"])
    lines.extend(render_value_lines(lock.get("typography", {})))
    icons = lock.get("icons", {})
    lines.extend(["", "## icons"])
    if isinstance(icons, dict):
        lines.append(f"- library: {icons.get('library', '')}")
        inventory = icons.get("inventory", [])
        lines.append(f"- inventory: {', '.join(inventory) if isinstance(inventory, list) else inventory}")
        if "stroke_width" in icons:
            lines.append(f"- stroke_width: {icons['stroke_width']}")
    else:
        lines.extend(render_value_lines(icons))
    images = lock.get("images", {})
    if images:
        lines.extend(["", "## images"])
        lines.extend(render_value_lines(images))
    for section in ("spacing", "shape_language", "style_anchor", "theme_color_policy", "flex_rules", "icon_rules", "chart_rules", "svg_rules"):
        value = lock.get(section, {})
        if value:
            lines.extend(["", f"## {section}"])
            lines.extend(render_value_lines(value))
    lines.extend(["", "## page_rhythm"])
    lines.extend(render_value_lines(lock.get("page_rhythm", {})))
    lines.extend(["", "## forbidden"])
    lines.extend(render_value_lines(lock.get("forbidden", [])))
    return "\n".join(lines).strip() + "\n"


def write_plan_artifacts(project_path: Path, plan: dict[str, Any], lock: dict[str, Any]) -> None:
    write_json(project_path / "design_plan.json", plan)
    write_json(project_path / "spec_lock.json", lock)
    design_markdown = render_design_plan_markdown(plan)
    (project_path / "design_plan.md").write_text(design_markdown, encoding="utf-8")
    # Compatibility for existing tools and human-opened project files.
    (project_path / "design_spec.md").write_text(design_markdown, encoding="utf-8")
    (project_path / "spec_lock.md").write_text(render_spec_lock_markdown(lock), encoding="utf-8")


def basic_canvas_dict(canvas_format: str) -> dict[str, str]:
    _, _, normalized, canvas = canvas_dimensions(canvas_format)
    return {
        "format": normalized,
        "name": canvas["name"],
        "dimensions": canvas["dimensions"],
        "viewbox": canvas["viewbox"],
    }
