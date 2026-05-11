"""Design planning and direct DeepSeek calls."""

from __future__ import annotations

import json
import os
import re
import time
import http.client
import urllib.error
import urllib.request
from typing import Any

from .config import DEFAULT_BASE_URL, DEFAULT_MODEL, QWEN_BASE_URL, QWEN_MAX_TOKENS, QWEN_MODEL, QWEN_TIMEOUT, SKILL_DIR
from .cookbook import Cookbook, render_cookbook_context
from .errors import GenerationError
from .parser import Deck
from .project import basic_canvas_dict, write_plan_artifacts
from .usage import UsageLogger

DEEPSEEK_SYSTEM = "You are PPT Master automation engine. Follow the user task exactly."
DEFAULT_DEEPSEEK_PLAN_MAX_TOKENS = 120000
DEFAULT_SPEC_RETRIES = 2
DEFAULT_SPEC_RETRY_BACKOFF_SECONDS = 8.0


class SpecParseError(GenerationError):
    """Raised when a spec/planner response cannot be parsed reliably."""


DEFAULT_COLORS = {
    "bg": "#FFFFFF",
    "panel": "#F8FAFC",
    "muted_panel": "#E0F2FE",
    "soft_panel": "#EEF2FF",
    "primary": "#1D4ED8",
    "accent": "#0F766E",
    "secondary_accent": "#F59E0B",
    "accent_violet": "#7C3AED",
    "accent_cyan": "#0891B2",
    "text": "#0F172A",
    "text_secondary": "#475569",
    "border": "#CBD5E1",
}

ICON_INVENTORY = [
    "chunk-filled/rocket",
    "chunk-filled/lightbulb",
    "chunk-filled/microchip",
    "chunk-filled/vr",
    "chunk-filled/hand",
    "chunk-filled/hand-tap",
    "chunk-filled/chart-line",
    "chunk-filled/chart-bar",
    "chunk-filled/chart-pie",
    "chunk-filled/database",
    "chunk-filled/server",
    "chunk-filled/globe",
    "chunk-filled/users",
    "chunk-filled/building",
    "chunk-filled/money",
    "chunk-filled/newspaper",
    "chunk-filled/bullhorn",
    "chunk-filled/shield-check",
    "chunk-filled/star",
    "chunk-filled/robot",
]

DEFAULT_TYPOGRAPHY = {
    "font_family": '"Microsoft YaHei", "PingFang SC", Arial, sans-serif',
    "title_family": '"Microsoft YaHei", "PingFang SC", Arial, sans-serif',
    "body_family": '"Microsoft YaHei", "PingFang SC", Arial, sans-serif',
    "emphasis_family": '"Microsoft YaHei", "PingFang SC", Arial, sans-serif',
    "code_family": 'Consolas, "Courier New", monospace',
    "body": 18,
    "title": 34,
    "subtitle": 24,
    "annotation": 13,
    "cover_title": 44,
}

DEFAULT_SPACING = {"outer_margin": 56, "card_gap": 16, "section_gap": 24}
DEFAULT_SHAPE_LANGUAGE = {"radius": 10, "stroke_width": 1, "shadow": "none"}

TYPOGRAPHY_SIZE_KEYS = {"body", "title", "subtitle", "annotation", "cover_title"}
TYPOGRAPHY_FAMILY_KEYS = {"font_family", "title_family", "body_family", "emphasis_family", "code_family"}
PPT_SAFE_FONT_TAILS = {
    "microsoft yahei",
    "simhei",
    "simsun",
    "kaiti",
    "fangsong",
    "pingfang sc",
    "heiti sc",
    "songti sc",
    "stsong",
    "arial",
    "arial black",
    "calibri",
    "segoe ui",
    "verdana",
    "helvetica",
    "helvetica neue",
    "tahoma",
    "trebuchet ms",
    "times new roman",
    "times",
    "georgia",
    "cambria",
    "palatino",
    "consolas",
    "courier new",
    "menlo",
    "monaco",
    "impact",
}

FORBIDDEN = [
    "Mixing icon libraries",
    "Unspecified dark theme or dark full-slide backgrounds not defined by the active cookbook",
    "rgba()",
    "`<style>`, `class`, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<script>`, `<iframe>`, `<symbol>`",
    "`<g opacity>` (set opacity on each child element individually)",
    "`<image opacity>` (use an overlay rectangle instead)",
    "HTML named entities in text",
]

SPEC_FIELD_RESPONSIBILITY_CONTRACT = """Spec field responsibility model:
- Semantic layer: `intent` states the audience-facing claim; `why_this_layout` explains why the chosen structure fits the content. These fields should not contain visual styling.
- Structure layer: `layout_family` is for deck-level variety checks and should be cookbook-adapted when a cookbook is active; `source_recipe_anchor` names the reference recipe/motif that supplies art direction; `required_art_moves` lists visible source-native moves SVG must render; `layout` is the concrete archetype/catalog-derived structure; `layout_signature` is the one-line spatial blueprint; `composition` is the reading order and region allocation; `visual_structure` is the drawable primitive list for SVG. Do not repeat the same sentence across these fields.
- Density/fullness layer: `content_density` is the only strong density signal. Default normal content pages to `high`; use `low` only for cover/closing or explicit breathing pages.
- Theme execution layer: keep `color_role`, `visual_metaphor`, `card_anatomy`, and `visual_guidance` as short brief phrases. Do not turn any field into a detailed implementation spec.
- SVG execution layer: `icon_plan` is title-only. It may contain at most one semantic icon placeholder for the page title/header area; body cards, bullets, chips, metrics, and charts should not receive icons. Cookbook recipes teach style, not chart priority.
- Balance requirements: preserve theme consistency, avoid template sameness, keep normal content pages information-rich and visually full, and keep creativity purposeful rather than gimmicky.
"""

DIRECT_API_PROMPT_CONTRACT = f"""Current direct-API execution contract:
- Historical repository markdown (CLAUDE.md, SKILL.md, and shared references) is compatibility context, not the current art direction. The active rules are the self-contained prompt, cookbook when supplied, design_plan.json, and spec_lock.json.
- Keep old workflow safety constraints only where they protect PPT export: PPT-safe SVG, editable grouping, icon placeholders, chart markers, local image paths, and font safety. Do not inherit legacy minimal-template aesthetics from old docs.
- `design_plan.json` is the soft visual/semantic plan. `spec_lock.json` is the hard visual/token anchor for colors, fonts, icons, spacing, shape language, chart rules, and forbidden SVG features.
- Good specs are cumulative: precise fields create precise SVGs. Avoid filler values. Every non-empty field must give the SVG worker a usable drawing decision.
- Visual direction should feel designed, not cautiously templated: strong hierarchy, balanced semantic color roles, varied component interiors, expressive but controlled chart skins, and page-specific motifs that still belong to one deck.
- Theme continuity comes from a stable compact palette, typography, spacing, repeated chrome, and reusable component grammar. A single primary color does not need to dominate every slide, but the deck should not become rainbow-like: individual slides may let teal, amber, violet, or cyan lead when content semantics support it, with neutral surfaces still carrying most of the page.
{SPEC_FIELD_RESPONSIBILITY_CONTRACT}
- PPT-safe SVG rules: inline attributes only; HEX colors only; no CSS classes/styles; no rgba; no group/image opacity; no masks; no foreignObject; no script/animation; no textPath; no symbol definitions.
- Typography must be PPT-safe: font stacks should end with Microsoft YaHei, SimSun, Arial, Times New Roman, Consolas, or another known installed family. Do not use `Noto Sans SC` as a sole font-family; the Source Han export variant is produced later by post-processing.
- `clip-path` is allowed only on `<image>` elements with a matching simple `<clipPath>` in `<defs>` for photo/avatar crops. Do not use clip-path on shapes, groups, text, charts, or decorations.
- Text must be SVG XML, not HTML: escape XML-reserved characters, use raw Unicode for normal punctuation/symbols, use `<text>` and `<tspan>` only, and keep inline emphasis inside one logical `<text>` where possible.
- Group editable units with plain `<g>`: cards, process steps, icon-text pairs, chart groups, headers, and callouts. Never use `<g opacity>`.
- If a page contains a real data chart, include a `<!-- chart-plot-area: ... -->` marker inside `<g id="chartArea">` so downstream chart scanning can find it.
- Simple gradients, soft shadows, measured color bands, image treatments, and decorative motifs are allowed when they are PPT-safe and theme-consistent. Use them as deliberate design tokens, not random effects; keep saturated color controlled.
"""

LAYOUT_ARCHETYPE_LIBRARY = [
    "hero_cover",
    "executive_summary_strips",
    "policy_timeline",
    "market_growth_chart",
    "competitor_matrix",
    "research_process_flow",
    "technical_architecture",
    "sensor_mesh_detail",
    "algorithm_pipeline",
    "robustness_test_lab",
    "achievement_pillar_grid",
    "product_exploded_view",
    "certification_dashboard",
    "impact_flywheel",
    "demand_funnel",
    "positioning_map",
    "ecosystem_network",
    "go_to_market_roadmap",
    "funding_pie_allocation",
    "financial_dashboard",
    "profitability_waterfall",
    "social_impact_pillars",
    "quote_spotlight",
    "media_wall",
    "org_chart",
    "advisor_profile_split",
    "capability_matrix",
    "collaboration_ecosystem",
    "closing_centered",
]

CHARTS_INDEX_PATH = SKILL_DIR / "templates" / "charts" / "charts_index.json"


def build_chart_template_reference() -> list[dict[str, Any]]:
    """Return the chart/diagram template catalog as a compact prompt vocabulary."""

    if not CHARTS_INDEX_PATH.exists():
        return []
    try:
        index = json.loads(CHARTS_INDEX_PATH.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []

    categories = index.get("categories", {}) if isinstance(index, dict) else {}
    charts = index.get("charts", {}) if isinstance(index, dict) else {}
    if not isinstance(categories, dict) or not isinstance(charts, dict):
        return []

    category_lookup: dict[str, str] = {}
    for category_key, category_value in categories.items():
        if not isinstance(category_value, dict):
            continue
        label = str(category_value.get("label") or category_key)
        for chart_name in category_value.get("charts") or []:
            category_lookup[str(chart_name)] = label

    reference: list[dict[str, Any]] = []
    for key in sorted(charts):
        item = charts.get(key)
        if not isinstance(item, dict):
            continue
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


def default_art_direction() -> dict[str, Any]:
    return {
        "mood": "bright, precise, credible technology venture",
        "motifs": ["technical lines", "soft cards", "modular system diagrams", "measured evidence bands", "accent bars"],
        "composition_principles": [
            "one governing idea per slide",
            "repeat a recognizable chrome/palette/component grammar",
            "let individual slides rotate one leading accent color by semantic role",
            "vary layout rhythm and component interiors without changing the visual language",
        ],
        "background_style": "white or near-white canvas with soft tints, measured accent rails, and technical motifs; avoid large saturated color blocks",
        "card_style": "light panels with readable contrast, one theme-color header/rail/chip system, small radius, and optional soft depth",
        "diagram_style": "node-link, process, layered system, or dashboard diagrams using one lead accent plus one support accent",
        "chart_style": "clean axes/direct labels plus semantic color coding, one highlighted series, callout ribbons, and active legends where useful",
        "avoid": [
            "dark full-slide theme",
            "neon-on-black",
            "random color chaos",
            "paragraph-heavy pages",
            "same blue accent on every page",
            "more than two saturated accents competing on one page",
        ],
    }


def default_layout_system() -> dict[str, Any]:
    return {
        "grid": "12-column 1280x720 canvas with 52-68px outer margins",
        "density": "content-rich and visually full: normal content pages should carry enough visible evidence and component footprint to avoid large blank regions while preserving hierarchy",
        "page_occupancy": "substantive pages should use about 75-85% of the safe content area with meaningful components; cover/closing can be lighter but still should not feel empty",
        "density_scale": {
            "low": "cover, quote, breathing, and closing pages only; 1-2 text units",
            "medium": "default content density; 4-6 visible content units with short body phrases, labels, or metric chips",
            "high": "evidence/technical/finance/table/roadmap pages; 5-7 visible content units with compact labels",
            "showcase": "visual-dominant product/team/image pages with supporting specs, metric chips, or captions",
        },
        "archetypes": list(LAYOUT_ARCHETYPE_LIBRARY),
        "variation": ["hero", "evidence grid", "process/timeline", "metrics cards", "comparison", "closing"],
        "diversity_policy": "Choose specific semantic archetypes from content rather than quotas. Avoid generic two-column pages unless the right/left structure is distinctive and justified.",
        "soft_constraints": "guide composition and visual emphasis, but do not lock exact coordinates for every page",
    }


def default_component_system() -> dict[str, Any]:
    return {
        "cards": "light fills, 8-12px radius, 1px border or single color rail; keep a shared outer grammar but vary interiors with badges, chips, sidebars, and micro-visuals by content role",
        "card_internal_variations": [
            "header badge",
            "left accent rail",
            "corner number",
            "icon pocket",
            "metric chip",
            "micro chart strip",
            "nested callout band",
            "connector notch",
        ],
        "icons": "title-only chunk-filled placeholders: at most one semantic icon near the page title/header, never per-bullet or per-card icons",
        "charts": "use chart catalog as semantic vocabulary; give charts one lead series, one support series if needed, direct labels, and chart-plot-area markers for real data charts",
        "chart_template_policy": "choose real template keys from templates/charts/charts_index.json as semantic vocabulary, then redraw/restyle in the locked theme",
        "callouts": "short conclusion phrases with measured color bands, badges, metric pills, or highlight ribbons, never long paragraphs",
        "technical_motifs": "technical lines, small nodes, measured accent bars, light system diagrams",
    }


def default_style_anchor() -> dict[str, Any]:
    return {
        "theme": "light technology venture deck",
        "repeat": ["white canvas", "dark text", "compact multi-accent palette", "soft cards", "technical chrome", "optional title icon placeholders"],
        "vary": ["slide archetype", "diagram type", "card count", "leading accent color", "accent placement", "chart skin"],
    }


def default_theme_color_policy() -> dict[str, Any]:
    return {
        "primary_accent": DEFAULT_COLORS["primary"],
        "supporting_accents": [
            DEFAULT_COLORS["accent"],
            DEFAULT_COLORS["secondary_accent"],
            DEFAULT_COLORS["accent_cyan"],
            DEFAULT_COLORS["accent_violet"],
        ],
        "slide_color_roles": "each substantive slide may choose one leading accent and one supporting accent from locked colors; use additional colors only as pale tints or small metric chips",
        "color_intensity_rule": "neutral surfaces 70-85% of page; leading accent about 10-20%; support accents about 3-8%",
        "allow_extra_colors": "only if listed in spec_lock colors and used as minor semantic support, chart series, or pale tint",
        "dominance_rule": "do not force the primary accent to dominate every page, but keep saturated color disciplined and deck chrome consistent",
    }


def default_flex_rules() -> dict[str, str]:
    return {
        "allowed": "layout may adapt to page content as long as palette, typography, spacing, and shape language stay consistent",
        "not_allowed": "dark pages, one-off palettes, invented icon styles, dense paragraph dumps, exact visual clones on every page",
    }


def default_chart_rules(*, include_available_templates: bool = False) -> dict[str, Any]:
    rules: dict[str, Any] = {
        "style": "light-canvas charts with clean axes, direct labels, semantic color roles, highlighted series/callouts, and no clip-path on chart elements",
        "auto_calibration": "scan-only",
        "catalog_source": "templates/charts/charts_index.json",
        "selection_policy": "choose real catalog keys as chart_or_diagram values by content semantics first; redraw/restyle in the locked cookbook theme",
        "plot_area_marker": "required for real data charts",
    }
    if include_available_templates:
        rules["available_templates"] = [item["key"] for item in build_chart_template_reference()]
    return rules


def deck_source_markdown(deck: Deck) -> str:
    parts: list[str] = []
    if deck.front_matter:
        parts.append(deck.front_matter)
    for slide in deck.slides:
        if slide.kind == "content":
            parts.append(slide.raw_markdown)
    return "\n\n".join(parts).strip()


def compact_slide_manifest(deck: Deck) -> dict[str, Any]:
    return {
        "title": deck.title,
        "slide_count": len(deck.slides),
        "slides": [
            {
                "index": slide.index,
                "title": slide.title,
                "kind": slide.kind,
                "section_title": slide.section_title,
                "svg_filename": slide.svg_filename,
            }
            for slide in deck.slides
        ],
    }


def compact_slide_briefs(deck: Deck, *, excerpt_chars: int = 900) -> list[dict[str, Any]]:
    briefs: list[dict[str, Any]] = []
    for slide in deck.slides:
        body = re.sub(r"\s+", " ", slide.body).strip()
        briefs.append(
            {
                "index": slide.index,
                "title": slide.title,
                "kind": slide.kind,
                "section_title": slide.section_title,
                "svg_filename": slide.svg_filename,
                "content_excerpt": body[:excerpt_chars],
            }
        )
    return briefs


def design_plan_schema_example() -> dict[str, Any]:
    return {
        "project_name": "",
        "deck_title": "",
        "style": "",
        "canvas": {},
        "theme": {
            "name": "",
            "colors": dict(DEFAULT_COLORS),
            "typography": {"title_family": "", "body_family": "", "title": 34, "body": 18, "annotation": 13},
        },
        "art_direction": {
            "mood": "",
            "motifs": [],
            "source_native_art_moves": [],
            "composition_principles": [],
            "background_style": "",
            "card_style": "",
            "diagram_style": "",
            "chart_style": "",
            "avoid": [],
        },
        "layout_system": {
            "grid": "",
            "density": "",
            "page_occupancy": "",
            "density_scale": {"low": "", "medium": "", "high": "", "showcase": ""},
            "archetypes": [],
            "diversity_policy": "",
            "soft_constraints": "",
        },
        "component_system": {
            "cards": "",
            "card_internal_variations": [],
            "icons": "",
            "charts": "",
            "chart_template_policy": "",
            "callouts": "",
            "technical_motifs": "",
        },
        "assets": {"icons": {"library": "chunk-filled", "inventory": []}, "images": {}},
        "cookbook": {
            "id": "",
            "priority": "",
            "applied_to": ["design_plan", "spec_lock", "svg"],
            "recipe_policy": "reference examples, not whitelist",
            "adaptation_policy": "derive cookbook-compatible layouts when content requires other structures while preserving source-native art moves",
        },
        "slides": [slide_schema_example()],
    }


def slide_schema_example() -> dict[str, Any]:
    return {
        "index": 1,
        "title": "",
        "kind": "",
        "section_title": None,
        "svg_filename": "",
        "rhythm": "",
        "layout": "",
        "layout_family": "",
        "source_recipe_anchor": "",
        "required_art_moves": [],
        "layout_signature": "",
        "intent": "",
        "composition": "",
        "visual_structure": "",
        "why_this_layout": "",
        "visual_metaphor": "",
        "visual_guidance": "",
        "color_role": "",
        "density_plan": "",
        "card_anatomy": "",
        "icon_plan": [],
        "chart_or_diagram": "",
        "content_density": "",
    }


def spec_lock_schema_example() -> dict[str, Any]:
    return {
        "canvas": {},
        "colors": dict(DEFAULT_COLORS),
        "typography": {"title_family": "", "body_family": "", "title": 34, "body": 18, "annotation": 13},
        "icons": {"library": "chunk-filled", "inventory": list(ICON_INVENTORY), "stroke_width": 2},
        "images": {},
        "spacing": dict(DEFAULT_SPACING),
        "shape_language": dict(DEFAULT_SHAPE_LANGUAGE),
        "style_anchor": {"theme": "light technology venture deck", "repeat": [], "vary": []},
        "cookbook": {
            "id": "",
            "priority": "",
            "required_repeats": [],
            "source_native_art_moves": [],
            "layout_recipes": [],
            "adaptation_policy": "",
            "chart_catalog_precedence": "",
            "decorative_asset_policy": "",
            "under_fidelity_checks": [],
            "forbidden_drift": [],
        },
        "theme_color_policy": {
            "primary_accent": DEFAULT_COLORS["primary"],
            "supporting_accents": [
                DEFAULT_COLORS["accent"],
                DEFAULT_COLORS["secondary_accent"],
                DEFAULT_COLORS["accent_violet"],
                DEFAULT_COLORS["accent_cyan"],
            ],
            "slide_color_roles": "",
            "color_intensity_rule": "",
            "allow_extra_colors": "",
            "dominance_rule": "",
        },
        "flex_rules": {"allowed": "", "not_allowed": ""},
        "icon_rules": {"syntax": '<use data-icon="chunk-filled/name" .../>', "style": "title/header only, maximum one icon per slide, colored from locked palette by semantic role"},
        "chart_rules": {
            "style": "light-canvas charts with clean axes, semantic color roles, highlighted series/callouts, no clip-path on chart elements, no rgba",
            "catalog_source": "templates/charts/charts_index.json",
            "selected_templates": [],
            "selection_policy": "choose real catalog keys by content semantics first, then redraw/restyle in cookbook/theme grammar",
            "plot_area_marker": "required for real data charts",
        },
        "svg_rules": {
            "root_bg": "#FFFFFF",
            "max_chars": 12000,
            "forbid": ["rgba()", "<style>", "class", "<foreignObject>", "<mask>", "<g opacity>", "<image opacity>"],
            "clip_path_policy": "only allowed on <image> with matching simple <clipPath> in <defs>",
        },
        "page_rhythm": {"P01": "hero", "P02": "dense"},
        "page_art_moves": {"P01": {"source_recipe_anchor": "", "required_art_moves": []}},
        "forbidden": [],
    }


def build_deck_context_prefix(deck: Deck, canvas_format: str, style: str, cookbook: Cookbook | None = None) -> str:
    """Shared byte-stable prefix for planning, notes, and SVG requests."""
    canvas = basic_canvas_dict(canvas_format)
    manifest = compact_slide_manifest(deck)
    cookbook_context = render_cookbook_context(cookbook)
    return f"""PPT_MASTER_COMMON_PREFIX_V1

Fixed generation contract:
- Output is for an editable PPTX built from PPT-safe SVG.
- Use a light-canvas visual system by default. If the active cookbook explicitly defines dark, black, or accent full-bleed pages, those cookbook-defined reversal pages are allowed; otherwise do not invent a dark full-slide theme. Controlled color rails, soft tints, chart highlights, and small/medium accent bands are allowed when they remain PPT-safe and readable.
- If a Theme Cookbook is present, it is the visual authority for colors, typography, component geometry, decorative assets, chart skin, layout grammar, and page chrome. Generic defaults are only fallbacks.
- A Theme Cookbook is an art-directed adaptive grammar, not a chart/template whitelist or a loose mood reference: choose chart and diagram semantics from the source content and full chart catalog first, then apply the cookbook's visual grammar and source-native art moves.
- Keep theme color continuity through the locked compact palette and repeated chrome. Do not force the same primary accent to dominate every page, but limit each slide to one leading accent, one supporting accent, and neutral/pale tints so the deck does not become rainbow-like.
- Use concise, audience-facing Chinese slide text.
- Keep visible content faithful to the source Markdown; summarize dense details instead of dumping paragraphs.
- If source Markdown contains project images, reference local files with PPT-safe `<image href="../images/filename.ext" ... preserveAspectRatio="xMidYMid meet"/>` or `slice` for deliberate image fills. Use image manifest width, height, aspect_ratio, orientation, byte size, and alt text to decide whether the image fits a hero crop, side panel, portrait strip, or contained evidence image.
- Use project icon placeholders only for an optional title/header icon: `<use data-icon="chunk-filled/rocket" x="100" y="100" width="32" height="32" fill="#1D4ED8"/>`.
- Keep icon frequency extremely restrained. Do not add icons to body bullets, cards, charts, tables, metrics, or diagrams; each slide may have at most one title/header icon, and many slides should have none.
- Available icon placeholders: {", ".join(ICON_INVENTORY)}.
- Forbidden SVG features: `<style>`, `class`, `<foreignObject>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, `<mask>`, HTML named entities, `<g opacity>`, and `clip-path` outside simple image crops.
- If no task follows this prefix, return exactly `ACK`.

{DIRECT_API_PROMPT_CONTRACT}

Canvas JSON:
{json.dumps(canvas, ensure_ascii=False, sort_keys=True)}

Style mode:
{style}

Deck title:
{deck.title}

Source Markdown:
```markdown
{deck_source_markdown(deck)}
```

Slide Manifest JSON:
{json.dumps(manifest, ensure_ascii=False, indent=2)}

{cookbook_context}
"""


def resolve_api_key(api_key: str | None = None) -> str:
    resolved = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not resolved:
        raise GenerationError("DeepSeek API key is required. Use --deepseek-api-key or DEEPSEEK_API_KEY.")
    return resolved


def resolve_qwen_api_key(api_key: str | None = None) -> str:
    resolved = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
    if not resolved:
        raise GenerationError("Qwen/DashScope API key is required. Use --qwen-api-key or DASHSCOPE_API_KEY.")
    return resolved


def deterministic_plan(project_name: str, canvas_format: str, style: str, deck: Deck) -> tuple[dict[str, Any], dict[str, Any]]:
    canvas = basic_canvas_dict(canvas_format)
    slides = []
    page_rhythm: dict[str, str] = {}
    color_roles = [
        "teal lead for process/systems; blue anchors; one amber metric chip only if useful",
        "amber lead for business/evidence emphasis; blue structure; teal status marks",
        "violet lead for innovation/AI capability; cyan technical highlights; blue chrome",
        "cyan lead for data/architecture clarity; blue anchors; amber highlight for one key metric",
    ]
    for slide in deck.slides:
        if slide.kind == "cover":
            rhythm = "hero"
            layout = "hero_cover"
            intent = "open with the project name and visual identity"
            layout_family = "hero"
            visual_structure = "title-first cover with a clear glove/data motif and active palette signal"
            visual_guidance = "Create a bright title-first cover with a confident focal title, one refined technology motif, and a visible palette/chrome system that can echo through later pages."
            density_plan = "Low text density but complete hero composition: title, one subtitle line, one identity label, and one visual motif occupying the focal area."
            card_anatomy = ""
            color_role = "primary blue lead with one teal/cyan support accent; avoid rainbow cover styling"
            content_density = "low"
        elif slide.kind == "closing":
            rhythm = "closing"
            layout = "closing_centered"
            intent = "close the presentation cleanly"
            layout_family = "closing"
            visual_structure = "centered closing message with repeated accent motif"
            visual_guidance = "Use a concise closing composition with balanced whitespace and a recognizable reprise of the cover motif/palette so the deck feels intentionally closed."
            density_plan = "Low text density but complete closing composition: closing message, one supporting deck-title/contact line, and a reprise motif so the page is not empty."
            card_anatomy = ""
            color_role = "reuse cover palette with one warm accent chip to close the deck cleanly"
            content_density = "low"
        else:
            rhythm = "dense"
            archetype = LAYOUT_ARCHETYPE_LIBRARY[(slide.index - 2) % (len(LAYOUT_ARCHETYPE_LIBRARY) - 2) + 1]
            layout = archetype
            intent = "summarize the corresponding Markdown section into clear presentation points"
            layout_family = "evidence/diagram"
            visual_structure = "semantic diagram or card/chart composition selected for the slide content"
            visual_guidance = "Use a content-specific chart, card, or diagram treatment with one clear focal move."
            density_plan = "High density: preserve the main evidence as grouped short labels."
            card_anatomy = "Brief card treatment only if cards are used."
            color_role = color_roles[(slide.index - 2) % len(color_roles)]
            content_density = "high"
        page_key = f"P{slide.index:02d}"
        page_rhythm[page_key] = rhythm
        slides.append(
            {
                "index": slide.index,
                "title": slide.title,
                "kind": slide.kind,
                "section_title": slide.section_title,
                "slug": slide.slug,
                "svg_filename": slide.svg_filename,
                "rhythm": rhythm,
                "layout": layout,
                "layout_family": layout_family,
                "source_recipe_anchor": "",
                "required_art_moves": [],
                "layout_signature": layout,
                "intent": intent,
                "composition": layout,
                "visual_metaphor": "precision interaction system",
                "visual_guidance": visual_guidance,
                "color_role": color_role,
                "density_plan": density_plan,
                "card_anatomy": card_anatomy,
                "visual_structure": visual_structure,
                "why_this_layout": "Chosen to match the slide's semantic role while preserving visual variety.",
                "content_density": content_density,
            }
        )
    plan = {
        "project_name": project_name,
        "deck_title": deck.title,
        "style": style,
        "canvas": canvas,
        "theme": {
            "name": "automation-default-technology",
            "colors": dict(DEFAULT_COLORS),
            "typography": dict(DEFAULT_TYPOGRAPHY),
        },
        "art_direction": default_art_direction(),
        "layout_system": default_layout_system(),
        "component_system": default_component_system(),
        "assets": {
            "icons": {"library": "chunk-filled", "inventory": list(ICON_INVENTORY)},
            "images": {},
        },
        "slides": slides,
    }
    lock = {
        "canvas": canvas,
        "colors": dict(DEFAULT_COLORS),
        "typography": dict(DEFAULT_TYPOGRAPHY),
        "icons": {"library": "chunk-filled", "inventory": list(ICON_INVENTORY)},
        "images": {},
        "spacing": dict(DEFAULT_SPACING),
        "shape_language": dict(DEFAULT_SHAPE_LANGUAGE),
        "style_anchor": default_style_anchor(),
        "theme_color_policy": default_theme_color_policy(),
        "flex_rules": default_flex_rules(),
        "chart_rules": default_chart_rules(include_available_templates=True),
        "page_rhythm": page_rhythm,
        "page_art_moves": {page_key: {"source_recipe_anchor": "", "required_art_moves": []} for page_key in page_rhythm},
        "forbidden": list(FORBIDDEN),
    }
    return plan, lock


def build_design_plan_prompt(deck: Deck, canvas_format: str, style: str, cookbook: Cookbook | None = None) -> str:
    slide_briefs = compact_slide_briefs(deck, excerpt_chars=700)
    chart_reference = build_chart_template_reference()
    common_prefix = build_deck_context_prefix(deck, canvas_format, style, cookbook)
    cookbook_rules = ""
    if cookbook is not None:
        cookbook_rules = f"""
Theme Cookbook application rules:
- Treat cookbook `{cookbook.id}` as an art-directed adaptive grammar, not a loose inspiration paragraph and not a layout whitelist.
- Convert cookbook tokens into `theme`, `art_direction`, `layout_system`, `component_system`, `assets`, and `spec_lock`.
- Treat cookbook recipes as reference exemplars unless the cookbook explicitly says otherwise. Do not force every slide into one of the named recipes.
- Choose each slide's semantic structure from source content first. If a named cookbook recipe fits, use it. If not, create a cookbook-compatible `layout_family` such as `g08_adapted_funnel`, `g08_adapted_sankey`, or `flsg_adapted_dense_table`.
- Each normal slide must name a concrete `source_recipe_anchor` and 2+ `required_art_moves` from the cookbook. The anchor can be a source recipe, motif cluster, or adapted recipe; it must not be a generic family such as `matrix`, `dashboard`, or `process`.
- Semantic structure may adapt to content, but source-native art moves must remain visibly inherited. Density may increase, but composition logic cannot collapse into generic cards.
- If the slide needs a chart, diagram, framework, table, process, architecture visual, or infographic, choose `chart_or_diagram` from the full chart catalog before consulting cookbook recipe examples.
- If the cookbook specifies fixed chrome, spacing, card geometry, decorative assets, or chart restyling rules, materialize those values in `spec_lock` so SVG workers do not have to infer them.
- If generic defaults conflict with the cookbook, the cookbook wins, except for PPT-safe SVG forbiddens and source-content faithfulness.
- `spec_lock.cookbook` should record cookbook id, priority, required repeats, source-native art moves, recipe reference vocabulary, adaptation policy, decorative asset policy, under-fidelity checks, chart catalog precedence, and forbidden drift.
"""
    else:
        cookbook_rules = """
Default theme restoration rules:
- No cookbook is active. Use the built-in `automation-default-technology` visual system as a real theme, not a bland fallback.
- Keep the strong light technology venture look from the stable pre-split spec flow: white/near-white canvas, dark text, compact multi-accent palette, technical chrome, evidence bands, precise diagram/card/chart surfaces, and content-linked motifs.
- Normal pages should feel designed and information-rich: use chart/dashboard/table/roadmap/network/product structures when content supports them, not plain bullet cards.
- Preserve the compact fields requested by the current pipeline, but make each short phrase decisive enough for SVG: name the focal structure, one polish move, one accent role, and the visible evidence grouping.
- Use default `source_recipe_anchor` values such as `default_tech_chrome`, `default_evidence_grid`, `default_process_ribbon`, `default_metric_dashboard`, `default_architecture_cutaway`, or `default_market_chart` when no cookbook source recipe exists.
- Use `required_art_moves` from the default theme vocabulary, for example `technical top rule`, `measured evidence band`, `accent rail`, `metric chip strip`, `thin connector grid`, `soft tinted panel`, `highlighted chart series`, or `section proof slab`.
- Do not generate dark full-slide themes, empty minimalist pages, or generic rows of identical cards.
"""
    return f"""{common_prefix}

Task: design the automation plan and execution lock.

Return only two JSON documents inside the exact markers below.

Rules:
- No user confirmations.
- No layout template dependency.
- The manifest already includes generated cover and closing slides; do not add section-header slides.
- Normal level-2 Markdown headings are content slides. The `创新技术` section is split into level-3 content slides.
- Keep the schema compact and deterministic.
- Use PPT-safe fonts and HEX colors only.
- Design for a polished Chinese presentation: clear hierarchy, purposeful whitespace, cookbook-aligned art direction, balanced palette usage, diagram/card/chart-friendly layouts, and visually full pages.
- Light-canvas theme by default. Root backgrounds should be white or near-white unless the active cookbook explicitly defines dark, black, or accent full-bleed reversal pages as source-native art moves. Do not invent dark full-slide pages outside cookbook guidance; avoid GitHub-dark palette and neon-on-black styling.
- Avoid monotonous single-column bullet pages. Vary rhythm across cover-like, two-column, metric/card, timeline/process, evidence grid, and conclusion layouts where appropriate.
- `spec_lock` must be a strict visual anchor: include canvas, colors, typography, spacing, shape_language, icon_rules, chart_rules, svg_rules, page_rhythm, and forbidden.
- `icons` and `images` must be JSON objects, not strings.
- Use this icon library inventory exactly when icons are needed: {", ".join(ICON_INVENTORY)}.
- Icon usage is title-only and optional. `icon_plan` may include at most one semantic placeholder for the page title/header area. Do not put icons in body cards, bullets, chips, metrics, tables, diagrams, or charts; use labels, numbers, chips, rules, image crops, source-native motifs, or chart marks instead.
- Make art direction explicit enough for independent SVG page generation: include mood, motifs, composition principles, card style, diagram style, chart style, and slide archetypes.
- Treat the slide spec as layered design data, not a checklist of repeated instructions. Each field should own one decision surface and avoid duplicating neighboring fields.
- Keep all per-slide text fields compact: every slide-level prose field should be a short phrase or one short sentence, not a detailed implementation plan.
- `visual_guidance` must be a final SVG-facing synthesis, not a repetition of `layout_signature`, `density_plan`, and `color_role`. Name only the decisive execution moves that make the selected chart/layout beautiful, including one content-linked motif when useful.
- `color_role` should name one leading accent color and one supporting accent from `spec_lock.colors`, plus what each color is used for. Additional colors should be pale tints or small metric chips only.
- Define density explicitly. Default every non-cover, non-closing content page to `high` unless the source clearly requires a quote/breathing/showcase slide. `high` means preserve more source evidence as concise labels, tables, timelines, charts, or grouped text.
- `density_plan` should be brief, e.g. `high: grouped evidence + concise labels`; do not specify object counts or detailed card internals.
- When `chart_or_diagram` is selected, explain how to restyle that visualization in the theme: what is emphasized, how labels/legends should sit, what supporting marks are muted, and what small creative detail prevents a generic chart look.
- When a page uses cards, specify the card grammar: radius, border weight, fill relationship, header badge, icon placement, spacing, and how cards align to the page's narrative flow.
- `card_anatomy` should stay brief when cards appear; avoid enumerating detailed sub-elements.
- Creativity should be encoded as one short content-linked visual move in `visual_metaphor` or `visual_guidance`.
- If a cookbook is active, `visual_guidance` should translate cookbook style into the exact slide structure instead of producing vague inspiration language.
- Avoid generic guidance such as "make it polished" or "use a beautiful layout" unless it is followed by concrete visual choices.
- The full response must include all slides plus both marker pairs. Prefer concise slide guidance over long prose.
- Do not over-lock each page. Avoid exact coordinates or mandatory object counts unless the content truly requires them.
- Keep style consistency through repeated palette, typography, spacing, shape language, icon library, page chrome, and diagram primitives; vary layout archetype, focal visualization, leading accent color, and component internals.
- Color variety should sit between the old conservative mode and the recent over-colorful mode: define a compact locked palette and a `theme_color_policy` that lets each substantive slide choose one leading accent plus one supporting accent. The primary accent should recur across the deck, but it must not dominate every page by default; avoid more than two saturated accent families competing on the same slide.
- Do not use numeric layout quotas. Instead, choose layouts semantically from the slide content.
- Prefer specific layout archetypes over generic containers. Avoid repeating generic `two_column_left_right`; if a split layout is genuinely best, make `layout_signature` specific, e.g. `left narrative + right market growth bars`, `left product exploded view + right metric cards`, or `left quotes + right credibility badges`.
- Avoid adjacent slides with the same layout_family unless their visual_structure is materially different.
- Every slide must include `layout_family`, `source_recipe_anchor`, `required_art_moves`, `layout_signature`, `visual_structure`, and `why_this_layout` so SVG generation has concrete structure guidance.

- Use the chart template catalog below as semantic visualization vocabulary. The model does not need to read SVG template code; choose real template names from the catalog, then restyle/redraw them according to spec_lock and cookbook.
- For every slide that needs a chart, diagram, framework, table, process, architecture visual, or infographic, set `chart_or_diagram` to one catalog `key`. Leave it empty only when the recipe is purely text/image/quote/team.
- Do not invent chart/template names. If no catalog item fits, write a cookbook-compatible adapted layout in `layout_family` and leave `chart_or_diagram` empty.
- Do not over-select chart types merely because the cookbook describes them in detail; detailed cookbook recipes are examples of style execution, not priority rankings.
- Put the catalog source and selected template keys in `spec_lock.chart_rules`.

Design plan field output guide:
- `rhythm`: a page pacing tag, not a mood word. Use values such as `hero`, `showcase`, `dense`, `breathing`, `process`, `future`, `closing` when they fit. It controls macro pacing and visual weight; use `content_density` and `density_plan` for text volume.
- `layout`: the archetype or catalog-derived structure, e.g. `product_exploded_view`, `executive_summary_strips`, `roadmap_vertical`.
- `layout_family`: a concrete cookbook-adapted family when a cookbook is active, e.g. `flsg_adapted_matrix`, `g08_adapted_timeline`, or a named recipe. Use broad generic families such as `matrix`, `dashboard`, or `process` only when no cookbook is active.
- `source_recipe_anchor`: the reference recipe or motif cluster that lends the slide its source-native art direction, e.g. `flsg_status_dashboard` or `g08_papercut_side_phrase`.
- `required_art_moves`: 2+ visible cookbook-native moves that SVG must render, e.g. `top editorial chrome`, `lime proof slab`, `thin rule grid`. Use fewer only for cover/closing pages where the cookbook clearly supports it.
- `layout_signature`: a short spatial blueprint that could be sketched, e.g. `left product image + right spec cards`, `top timeline + bottom impact summary`.
- `intent`: the audience-facing message this slide must prove.
- `composition`: the major regions, reading order, and space allocation; it should make the page feel full without becoming crowded.
- `visual_structure`: visible primitives to draw, e.g. `milestone nodes + text blocks`, `hero image + metric tiles`.
- `why_this_layout`: why this structure fits the source content, not a generic justification.
- `visual_metaphor`: a motif the SVG can render as a controlled visual signal, e.g. launch trajectory, sensor mesh, precision cockpit.
- `visual_guidance`: a short SVG-facing brief. Mention only the main focal treatment or motif; do not repeat `color_role` or `density_plan`.
- `color_role`: slide-specific palette execution. Name the leading accent and supporting accent uses from locked colors; do not leave color choice implicit.
- `density_plan`: brief visible-density note. Do not include detailed counts unless the source itself provides a fixed structure.
- `card_anatomy`: if cards appear, give a brief treatment; otherwise leave empty.
- `icon_plan`: exact icon placeholder names from inventory, title/header only, maximum one per slide. Leave empty when labels or structural motifs carry the meaning better.
- `chart_or_diagram`: one real catalog key when the page needs data/diagram structure; empty only for pure quote/image/text/team pages.
- `content_density`: `low`, `medium`, `high`, or `showcase`; default normal content slides to `high`. Use `low` only for cover and closing unless the slide is intentionally a quote/breathing page.
- These fields should agree with each other. Do not set `chart_or_diagram=roadmap_vertical` while `layout_signature` describes unrelated KPI cards.

{cookbook_rules}

Layout archetype library:
{json.dumps(LAYOUT_ARCHETYPE_LIBRARY, ensure_ascii=False, indent=2)}

Available chart/diagram template catalog:
{json.dumps(chart_reference, ensure_ascii=False, indent=2)}

Slide briefs JSON:
{json.dumps(slide_briefs, ensure_ascii=False, indent=2)}

Required design_plan schema:
{json.dumps(design_plan_schema_example(), ensure_ascii=False, indent=2)}

Required spec_lock schema:
{json.dumps(spec_lock_schema_example(), ensure_ascii=False, indent=2)}

---DESIGN_PLAN_JSON_START---
{{}}
---DESIGN_PLAN_JSON_END---
---SPEC_LOCK_JSON_START---
{{}}
---SPEC_LOCK_JSON_END---
"""


def extract_json_marker(text: str, start: str, end: str) -> dict[str, Any]:
    match = re.search(re.escape(start) + r"\s*(.*?)\s*" + re.escape(end), text, re.S)
    if not match:
        fallback = extract_single_json_object(text)
        if fallback is not None:
            return fallback
        raise SpecParseError(f"Model response missing marker pair: {start} / {end}")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise SpecParseError(f"Model response contained invalid JSON for {start}") from exc


def extract_single_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort fallback for providers that ignore marker instructions."""

    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S | re.I)
    candidates: list[str] = []
    if fence:
        candidates.append(fence.group(1))
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last > first:
        candidates.append(stripped[first : last + 1])

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def hex_luminance(color: str) -> float:
    match = re.fullmatch(r"#([0-9a-fA-F]{6})", str(color).strip())
    if not match:
        return 1.0
    raw = match.group(1)
    r = int(raw[0:2], 16) / 255
    g = int(raw[2:4], 16) / 255
    b = int(raw[4:6], 16) / 255
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def merge_light_colors(colors: Any) -> dict[str, str]:
    merged = {**DEFAULT_COLORS}
    if isinstance(colors, dict):
        for key, value in colors.items():
            if isinstance(value, str) and value.startswith("#"):
                merged[key] = value
    for background_key in ("bg", "background", "canvas", "slide_bg"):
        value = merged.get(background_key)
        if value and hex_luminance(value) < 0.72:
            merged[background_key] = "#FFFFFF" if background_key in {"bg", "background", "canvas", "slide_bg"} else "#F8FAFC"
    for panel_key in ("panel", "muted_panel", "soft_panel"):
        value = merged.get(panel_key)
        if value and hex_luminance(value) < 0.68:
            merged[panel_key] = DEFAULT_COLORS.get(panel_key, "#F8FAFC")
    return merged


def font_stack_has_safe_tail(value: str) -> bool:
    parts = [
        part.strip().strip('"').strip("'").lower()
        for part in str(value).split(",")
    ]
    concrete = [
        part
        for part in parts
        if part and part not in {"sans-serif", "serif", "monospace", "cursive", "fantasy", "system-ui"}
    ]
    return bool(concrete and concrete[-1] in PPT_SAFE_FONT_TAILS)


def merge_typography(typography: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {**DEFAULT_TYPOGRAPHY}
    if not isinstance(typography, dict):
        return merged

    for key, value in typography.items():
        if key in TYPOGRAPHY_SIZE_KEYS:
            try:
                size = int(value)
            except (TypeError, ValueError):
                continue
            if 8 <= size <= 72:
                merged[key] = size
        elif key in TYPOGRAPHY_FAMILY_KEYS and isinstance(value, str) and font_stack_has_safe_tail(value):
            merged[key] = value
    return merged


def enforce_light_theme(plan: dict[str, Any], lock: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    theme = plan.setdefault("theme", {})
    if not isinstance(theme, dict):
        theme = {}
        plan["theme"] = theme
    theme["colors"] = merge_light_colors(theme.get("colors", {}))
    theme["typography"] = merge_typography(theme.get("typography", {}))
    plan.setdefault("art_direction", default_art_direction())
    if isinstance(plan.get("art_direction"), dict):
        plan["art_direction"].setdefault("source_native_art_moves", [])
    plan.setdefault("layout_system", default_layout_system())
    plan.setdefault("component_system", default_component_system())
    plan.setdefault("assets", {})
    if isinstance(plan["assets"], dict):
        plan["assets"]["icons"] = {"library": "chunk-filled", "inventory": list(ICON_INVENTORY)}

    lock["colors"] = merge_light_colors(lock.get("colors", {}))
    lock["typography"] = merge_typography(lock.get("typography", {}))
    lock["icons"] = {"library": "chunk-filled", "inventory": list(ICON_INVENTORY), "stroke_width": 2}
    lock.setdefault("spacing", dict(DEFAULT_SPACING))
    lock.setdefault("shape_language", dict(DEFAULT_SHAPE_LANGUAGE))
    lock.setdefault("style_anchor", default_style_anchor())
    cookbook_lock = lock.setdefault("cookbook", {})
    if isinstance(cookbook_lock, dict):
        cookbook_lock.setdefault("source_native_art_moves", [])
        cookbook_lock.setdefault(
            "under_fidelity_checks",
            [
                "Every normal slide carries 2+ source-native art moves when a cookbook is active",
                "Density adaptation preserves composition logic, not just palette and fonts",
            ],
        )
    lock.setdefault("theme_color_policy", default_theme_color_policy())
    lock.setdefault("flex_rules", default_flex_rules())
    lock.setdefault("icon_rules", {"syntax": '<use data-icon="chunk-filled/name" .../>', "style": "title/header only, maximum one icon per slide, colored from locked palette by semantic role"})
    chart_rules = lock.setdefault("chart_rules", default_chart_rules())
    if isinstance(chart_rules, dict):
        chart_rules.setdefault("catalog_source", "templates/charts/charts_index.json")
        chart_rules.setdefault(
            "selection_policy",
            "choose real catalog keys as chart_or_diagram values by content semantics first; redraw/restyle in the locked cookbook theme",
        )
        chart_rules.setdefault("available_templates", [item["key"] for item in build_chart_template_reference()])
        chart_rules.setdefault("plot_area_marker", "required for real data charts")
    lock.setdefault(
        "svg_rules",
        {
            "root_bg": "#FFFFFF",
            "max_chars": 12000,
            "forbid": ["rgba()", "<style>", "class", "<foreignObject>", "<mask>", "<g opacity>", "<image opacity>"],
            "clip_path_policy": "only allowed on <image> with matching simple <clipPath> in <defs>",
        },
    )
    forbidden = lock.get("forbidden", [])
    if not isinstance(forbidden, list):
        forbidden = []
    for item in FORBIDDEN:
        if item not in forbidden:
            forbidden.append(item)
    lock["forbidden"] = forbidden
    return plan, lock


def call_deepseek_anthropic(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    system: str,
    max_tokens: int,
    timeout: int = 180,
) -> tuple[str, dict[str, Any]]:
    endpoint = base_url.rstrip("/") + "/v1/messages"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GenerationError(f"DeepSeek Anthropic API failed: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GenerationError(f"DeepSeek Anthropic API request failed: {exc}") from exc
    except (TimeoutError, http.client.IncompleteRead) as exc:
        raise GenerationError(f"DeepSeek Anthropic API transport failed: {exc}") from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"DeepSeek Anthropic API returned invalid JSON: {raw[:500]}") from exc
    blocks = result.get("content", [])
    if isinstance(blocks, str):
        text_parts = [blocks]
    elif isinstance(blocks, list):
        text_parts = [
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
    else:
        text_parts = []
    return "\n".join(text_parts).strip(), result.get("usage", {})


def call_qwen_openai(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    system: str,
    max_tokens: int,
    timeout: int = QWEN_TIMEOUT,
) -> tuple[str, dict[str, Any]]:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(60, int(timeout))) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GenerationError(f"Qwen OpenAI-compatible API failed: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GenerationError(f"Qwen OpenAI-compatible API request failed: {exc}") from exc

    result = json.loads(raw)
    choices = result.get("choices", [])
    text = ""
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        if isinstance(message, dict):
            text = str(message.get("content") or "")
    return text.strip(), result.get("usage", {}) if isinstance(result.get("usage"), dict) else {}


def call_planner_provider(
    *,
    provider: str,
    prompt: str,
    api_key: str | None,
    base_url: str,
    model: str,
    qwen_api_key: str | None,
    qwen_base_url: str,
    qwen_model: str,
    qwen_max_tokens: int,
    qwen_timeout: int,
    max_tokens: int = 24000,
) -> tuple[str, dict[str, Any], str]:
    if provider == "qwen":
        text, usage = call_qwen_openai(
            api_key=resolve_qwen_api_key(qwen_api_key),
            base_url=qwen_base_url,
            model=qwen_model,
            prompt=prompt,
            system=DEEPSEEK_SYSTEM,
            max_tokens=qwen_max_tokens,
            timeout=qwen_timeout,
        )
        return text, usage, qwen_model

    text, usage = call_deepseek_anthropic(
        api_key=resolve_api_key(api_key),
        base_url=base_url,
        model=model,
        prompt=prompt,
        system=DEEPSEEK_SYSTEM,
        max_tokens=max_tokens,
    )
    return text, usage, model


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def resolve_spec_retries() -> int:
    return max(0, env_int("PPT_MASTER_SPEC_RETRIES", env_int("PPT_API_SPEC_RETRIES", DEFAULT_SPEC_RETRIES)))


def resolve_spec_retry_backoff_seconds() -> float:
    return max(0.0, env_float("PPT_MASTER_SPEC_RETRY_BACKOFF_SECONDS", DEFAULT_SPEC_RETRY_BACKOFF_SECONDS))


def spec_retry_prompt(prompt: str, attempt: int, previous_error: Exception) -> str:
    if attempt <= 1:
        return prompt
    return f"""{prompt}

Retry correction:
- The previous spec response could not be parsed as valid JSON: {previous_error}
- Regenerate the entire design_plan/spec_lock response from scratch.
- Return complete, strict JSON only inside the exact marker pairs.
- Do not reuse corrupted partial JSON, raw control characters, comments, Markdown prose, or trailing explanations.
"""


def normalize_required_art_moves(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
    return []


def normalize_slide_spec(slide_spec: dict[str, Any], source_slide: Any) -> dict[str, Any]:
    normalized = dict(slide_spec) if isinstance(slide_spec, dict) else {}
    normalized["index"] = source_slide.index
    normalized["title"] = str(normalized.get("title") or source_slide.title)
    normalized["kind"] = str(normalized.get("kind") or source_slide.kind)
    normalized["section_title"] = normalized.get("section_title", source_slide.section_title)
    normalized["svg_filename"] = str(normalized.get("svg_filename") or source_slide.svg_filename)

    defaults = slide_schema_example()
    for key, default_value in defaults.items():
        normalized.setdefault(key, default_value)
    normalized["required_art_moves"] = normalize_required_art_moves(normalized.get("required_art_moves"))
    if not isinstance(normalized.get("icon_plan"), list):
        normalized["icon_plan"] = []
    normalized["icon_plan"] = [str(item).strip() for item in normalized["icon_plan"] if str(item).strip()][:1]
    normalized["content_density"] = "low" if source_slide.kind in {"cover", "closing"} else "high"
    if not str(normalized.get("layout_family") or "").strip():
        normalized["layout_family"] = str(normalized.get("layout") or "theme_adapted_content")
    if not str(normalized.get("layout_signature") or "").strip():
        normalized["layout_signature"] = str(normalized.get("layout") or normalized["layout_family"])
    return normalized


def normalize_design_plan(
    plan: dict[str, Any],
    *,
    project_name: str,
    deck: Deck,
    canvas_format: str,
    style: str,
    slide_specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = dict(plan) if isinstance(plan, dict) else {}
    normalized.setdefault("project_name", project_name)
    normalized.setdefault("deck_title", deck.title)
    normalized.setdefault("style", style)
    normalized.setdefault("canvas", basic_canvas_dict(canvas_format))
    normalized.setdefault("theme", {"name": "", "colors": dict(DEFAULT_COLORS), "typography": dict(DEFAULT_TYPOGRAPHY)})
    normalized.setdefault("art_direction", default_art_direction())
    normalized.setdefault("layout_system", default_layout_system())
    normalized.setdefault("component_system", default_component_system())
    normalized.setdefault("assets", {"icons": {"library": "chunk-filled", "inventory": list(ICON_INVENTORY)}, "images": {}})
    normalized.setdefault("cookbook", {})

    by_index: dict[int, dict[str, Any]] = {}
    raw_slides = normalized.get("slides")
    if isinstance(raw_slides, list):
        for item in raw_slides:
            if isinstance(item, dict):
                try:
                    by_index[int(item.get("index", 0))] = item
                except (TypeError, ValueError):
                    continue
    if slide_specs:
        for item in slide_specs:
            if isinstance(item, dict):
                try:
                    by_index.setdefault(int(item.get("index", 0)), item)
                except (TypeError, ValueError):
                    continue

    normalized["slides"] = [normalize_slide_spec(by_index.get(slide.index, {}), slide) for slide in deck.slides]
    return normalized


def normalize_spec_lock(lock: dict[str, Any], *, deck: Deck, canvas_format: str, design_plan: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(lock) if isinstance(lock, dict) else {}
    normalized.setdefault("canvas", basic_canvas_dict(canvas_format))
    normalized.setdefault("colors", dict(DEFAULT_COLORS))
    normalized.setdefault("typography", dict(DEFAULT_TYPOGRAPHY))
    normalized.setdefault("icons", {"library": "chunk-filled", "inventory": list(ICON_INVENTORY), "stroke_width": 2})
    normalized.setdefault("images", {})
    normalized.setdefault("spacing", dict(DEFAULT_SPACING))
    normalized.setdefault("shape_language", dict(DEFAULT_SHAPE_LANGUAGE))
    normalized.setdefault("style_anchor", default_style_anchor())
    normalized.setdefault("cookbook", {})
    normalized.setdefault("theme_color_policy", default_theme_color_policy())
    normalized.setdefault("flex_rules", default_flex_rules())
    normalized.setdefault("icon_rules", {"syntax": '<use data-icon="chunk-filled/name" .../>', "style": "title/header only, maximum one icon per slide, colored from locked palette by semantic role"})
    normalized.setdefault("chart_rules", default_chart_rules(include_available_templates=True))
    normalized.setdefault("svg_rules", spec_lock_schema_example()["svg_rules"])
    normalized.setdefault("forbidden", [])

    page_rhythm: dict[str, str] = {}
    page_art_moves: dict[str, dict[str, Any]] = {}
    slides = design_plan.get("slides", []) if isinstance(design_plan, dict) else []
    if isinstance(slides, list):
        for item in slides:
            if not isinstance(item, dict):
                continue
            try:
                page_key = f"P{int(item.get('index', 0)):02d}"
            except (TypeError, ValueError):
                continue
            page_rhythm[page_key] = str(item.get("rhythm") or "dense")
            page_art_moves[page_key] = {
                "source_recipe_anchor": item.get("source_recipe_anchor", ""),
                "required_art_moves": normalize_required_art_moves(item.get("required_art_moves")),
            }
    for slide in deck.slides:
        page_key = f"P{slide.index:02d}"
        page_rhythm.setdefault(page_key, "hero" if slide.kind == "cover" else "closing" if slide.kind == "closing" else "dense")
        page_art_moves.setdefault(page_key, {"source_recipe_anchor": "", "required_art_moves": []})
    normalized["page_rhythm"] = page_rhythm
    normalized["page_art_moves"] = page_art_moves
    return normalized


def generate_plan(
    *,
    project_path,
    project_name: str,
    canvas_format: str,
    style: str,
    deck: Deck,
    renderer: str,
    api_key: str | None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    provider: str = "deepseek",
    qwen_api_key: str | None = None,
    qwen_base_url: str = QWEN_BASE_URL,
    qwen_model: str = QWEN_MODEL,
    qwen_max_tokens: int = QWEN_MAX_TOKENS,
    qwen_timeout: int = QWEN_TIMEOUT,
    cookbook: Cookbook | None = None,
    logger: UsageLogger | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if renderer == "local":
        plan, lock = deterministic_plan(project_name, canvas_format, style, deck)
        write_plan_artifacts(project_path, plan, lock)
        return plan, lock

    prompt = build_design_plan_prompt(deck, canvas_format, style, cookbook)
    retries = resolve_spec_retries()
    attempts = max(1, retries + 1)
    retry_backoff = resolve_spec_retry_backoff_seconds()
    last_parse_error: Exception | None = None
    plan: dict[str, Any] | None = None
    lock: dict[str, Any] | None = None
    usage: dict[str, Any] = {}
    actual_model = model
    text = ""
    for attempt in range(1, attempts + 1):
        attempt_prompt = spec_retry_prompt(prompt, attempt, last_parse_error) if last_parse_error is not None else prompt
        text, usage, actual_model = call_planner_provider(
            provider=provider,
            prompt=attempt_prompt,
            api_key=api_key,
            base_url=base_url,
            model=model,
            qwen_api_key=qwen_api_key,
            qwen_base_url=qwen_base_url,
            qwen_model=qwen_model,
            qwen_max_tokens=qwen_max_tokens,
            qwen_timeout=qwen_timeout,
            max_tokens=max(24000, env_int("PPT_MASTER_DEEPSEEK_PLAN_MAX_TOKENS", DEFAULT_DEEPSEEK_PLAN_MAX_TOKENS)),
        )
        try:
            plan = extract_json_marker(text, "---DESIGN_PLAN_JSON_START---", "---DESIGN_PLAN_JSON_END---")
            lock = extract_json_marker(text, "---SPEC_LOCK_JSON_START---", "---SPEC_LOCK_JSON_END---")
        except SpecParseError as exc:
            last_parse_error = exc
            retrying = attempt < attempts
            if logger:
                logger.log_transcript(
                    f"{provider}_plan",
                    system=DEEPSEEK_SYSTEM,
                    prompt=attempt_prompt,
                    response=text,
                    metadata={
                        "model": actual_model,
                        "usage": usage,
                        "attempt": attempt,
                        "attempts": attempts,
                        "ok": False,
                        "retrying": retrying,
                        "error": str(exc),
                    },
                )
                logger.log(
                    f"{provider}_plan",
                    ok=False,
                    retrying=retrying,
                    attempt=attempt,
                    attempts=attempts,
                    error=str(exc),
                    usage=usage,
                    input_chars=len(attempt_prompt),
                    output_chars=len(text),
                )
            if retrying:
                time.sleep(retry_backoff * attempt)
                continue
            raise GenerationError(f"Spec planning failed after {attempts} attempt(s): {exc}") from exc
        if logger:
            logger.log_transcript(
                f"{provider}_plan",
                system=DEEPSEEK_SYSTEM,
                prompt=attempt_prompt,
                response=text,
                metadata={
                    "model": actual_model,
                    "usage": usage,
                    "attempt": attempt,
                    "attempts": attempts,
                    "ok": True,
                },
            )
        break

    if plan is None or lock is None:
        raise GenerationError("Spec planning failed without a parseable plan/spec response.")
    plan = normalize_design_plan(plan, project_name=project_name, deck=deck, canvas_format=canvas_format, style=style)
    lock = normalize_spec_lock(lock, deck=deck, canvas_format=canvas_format, design_plan=plan)
    plan, lock = enforce_light_theme(plan, lock)
    lock = normalize_spec_lock(lock, deck=deck, canvas_format=canvas_format, design_plan=plan)
    if logger:
        logger.log(
            f"{provider}_plan",
            ok=True,
            usage=usage,
            input_chars=len(attempt_prompt),
            output_chars=len(text),
            model=actual_model,
            attempt=attempt,
            attempts=attempts,
        )
    write_plan_artifacts(project_path, plan, lock)
    return plan, lock


def prime_deepseek_cache(
    *,
    deck: Deck,
    canvas_format: str,
    style: str,
    api_key: str | None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    cookbook: Cookbook | None = None,
    logger: UsageLogger | None = None,
) -> None:
    prompt = build_deck_context_prefix(deck, canvas_format, style, cookbook)
    text, usage = call_deepseek_anthropic(
        api_key=resolve_api_key(api_key),
        base_url=base_url,
        model=model,
        prompt=prompt,
        system=DEEPSEEK_SYSTEM,
        max_tokens=8,
    )
    if logger:
        logger.log_transcript(
            "deepseek_cache_prime",
            system=DEEPSEEK_SYSTEM,
            prompt=prompt,
            response=text,
            metadata={"model": model, "usage": usage, "scope": "deck_context_prefix"},
        )
        logger.log(
            "deepseek_cache_prime",
            usage=usage,
            input_chars=len(prompt),
            output_chars=len(text),
            model=model,
            scope="deck_context_prefix",
        )


def build_notes_prompt(deck: Deck, canvas_format: str, style: str, cookbook: Cookbook | None = None) -> str:
    return f"""{build_deck_context_prefix(deck, canvas_format, style, cookbook)}

Task: generate `notes/total.md` for this PPT Master project.

Rules:
- Use one level-1 heading per slide.
- Heading must exactly equal the SVG stem from the manifest, e.g. `# 01_title`.
- Each slide note must include a transition sentence, key points, and duration.
- Use Chinese labels naturally when source text is Chinese.
- Output only the complete `total.md` content.
"""
