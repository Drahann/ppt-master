"""Design planning and direct DeepSeek calls."""

from __future__ import annotations

import json
import os
import re
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


DEFAULT_COLORS = {
    "bg": "#FFFFFF",
    "panel": "#F8FAFC",
    "muted_panel": "#E0F2FE",
    "soft_panel": "#EEF2FF",
    "primary": "#1D4ED8",
    "accent": "#0F766E",
    "secondary_accent": "#F59E0B",
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

FORBIDDEN = [
    "Mixing icon libraries",
    "Dark theme or dark full-slide backgrounds",
    "rgba()",
    "`<style>`, `class`, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<script>`, `<iframe>`, `<symbol>`",
    "`<g opacity>` (set opacity on each child element individually)",
    "`<image opacity>` (use an overlay rectangle instead)",
    "HTML named entities in text",
]

REPOSITORY_REFERENCE_CONTRACT = """Repository reference contract distilled from CLAUDE.md, SKILL.md, shared-standards.md, and executor references:
- Direct API calls do not auto-load repository markdown. This prompt is the self-contained execution contract.
- `design_plan.json` is the soft visual/semantic plan. `spec_lock.json` is the hard visual/token anchor for colors, fonts, icons, spacing, shape language, chart rules, and forbidden SVG features.
- Each slide spec field has a role: `rhythm` controls density and whitespace; `layout` names the semantic archetype; `layout_signature` is the spatial blueprint; `intent` is the message; `composition` maps regions; `visual_structure` lists visible primitives; `why_this_layout` explains the content fit; `visual_metaphor` names the motif; `visual_guidance` gives concrete aesthetic execution; `icon_plan` lists exact placeholder icons; `chart_or_diagram` names the visualization grammar; `content_density` controls text compression.
- Good specs are cumulative: precise fields create precise SVGs. Avoid filler values. Every non-empty field must give the SVG worker a usable drawing decision.
- PPT-safe SVG rules: inline attributes only; HEX colors only; no CSS classes/styles; no rgba; no group/image opacity; no masks; no foreignObject; no script/animation; no textPath; no symbol definitions.
- `clip-path` is allowed only on `<image>` elements with a matching simple `<clipPath>` in `<defs>` for photo/avatar crops. Do not use clip-path on shapes, groups, text, charts, or decorations.
- Text must be SVG XML, not HTML: escape XML-reserved characters, use raw Unicode for normal punctuation/symbols, use `<text>` and `<tspan>` only, and keep inline emphasis inside one logical `<text>` where possible.
- Group editable units with plain `<g>`: cards, process steps, icon-text pairs, chart groups, headers, and callouts. Never use `<g opacity>`.
- If a page contains a real data chart, include a `<!-- chart-plot-area: ... -->` marker inside `<g id="chartArea">` so downstream chart scanning can find it.
- Use shadows and gradients sparingly. Prefer spacing, typography, borders, subtle tints, and accent bars before decorative effects.
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


def build_deck_context_prefix(deck: Deck, canvas_format: str, style: str, cookbook: Cookbook | None = None) -> str:
    """Shared byte-stable prefix for planning, notes, and SVG requests."""
    canvas = basic_canvas_dict(canvas_format)
    manifest = compact_slide_manifest(deck)
    cookbook_context = render_cookbook_context(cookbook)
    return f"""PPT_MASTER_COMMON_PREFIX_V1

Fixed generation contract:
- Output is for an editable PPTX built from PPT-safe SVG.
- Use a light visual system only; never use a dark full-slide theme.
- If a Theme Cookbook is present, it is the visual authority for colors, typography, component geometry, decorative assets, chart skin, layout grammar, and page chrome. Generic defaults are only fallbacks.
- A Theme Cookbook is not a chart/template whitelist: choose chart and diagram semantics from the source content and full chart catalog first, then apply the cookbook's visual grammar.
- Keep theme color continuity: the locked primary accent must remain dominant on every slide. Without a Theme Cookbook, use `#1D4ED8` as the default primary accent; with a Theme Cookbook, use the cookbook/spec_lock primary instead.
- Use concise, audience-facing Chinese slide text.
- Keep visible content faithful to the source Markdown; summarize dense details instead of dumping paragraphs.
- If source Markdown contains project images, reference local files with PPT-safe `<image href="../images/filename.ext" ... preserveAspectRatio="xMidYMid meet"/>` or `slice` for deliberate image fills.
- Use project icon placeholders when icons are needed: `<use data-icon="chunk-filled/rocket" x="100" y="100" width="32" height="32" fill="#1D4ED8"/>`.
- Available icon placeholders: {", ".join(ICON_INVENTORY)}.
- Forbidden SVG features: `<style>`, `class`, `<foreignObject>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, `<mask>`, HTML named entities, `<g opacity>`, and `clip-path` outside simple image crops.
- If no task follows this prefix, return exactly `ACK`.

{REPOSITORY_REFERENCE_CONTRACT}

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
    for slide in deck.slides:
        if slide.kind == "cover":
            rhythm = "hero"
            layout = "hero_cover"
            intent = "open with the project name and visual identity"
            layout_family = "hero"
            visual_structure = "title-first cover with a subtle glove/data motif"
            visual_guidance = "Create a bright title-first cover with a confident focal title, one refined technology motif, generous negative space, and a small repeated accent system that can echo through later pages."
        elif slide.kind == "closing":
            rhythm = "closing"
            layout = "closing_centered"
            intent = "close the presentation cleanly"
            layout_family = "closing"
            visual_structure = "centered closing message with repeated accent motif"
            visual_guidance = "Use a quiet closing composition with a concise thank-you message, balanced whitespace, and a restrained reprise of the cover motif so the deck feels intentionally closed."
        else:
            rhythm = "breathing" if slide.index % 5 == 0 else "dense"
            archetype = LAYOUT_ARCHETYPE_LIBRARY[(slide.index - 2) % (len(LAYOUT_ARCHETYPE_LIBRARY) - 2) + 1]
            layout = archetype
            intent = "summarize the corresponding Markdown section into clear presentation points"
            layout_family = "evidence/diagram"
            visual_structure = "semantic diagram or card/chart composition selected for the slide content"
            visual_guidance = "Use the shared light technology style, then choose a content-specific diagram/card/chart treatment with clear focal hierarchy, elegant spacing, and one tasteful detail that makes the page feel designed rather than templated."
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
                "layout_signature": layout,
                "intent": intent,
                "composition": layout,
                "visual_metaphor": "precision interaction system",
                "visual_guidance": visual_guidance,
                "visual_structure": visual_structure,
                "why_this_layout": "Chosen to match the slide's semantic role while preserving visual variety.",
                "content_density": "medium",
            }
        )
    plan = {
        "project_name": project_name,
        "deck_title": deck.title,
        "style": style,
        "canvas": canvas,
        "theme": {
            "name": "automation-default-technology",
            "colors": DEFAULT_COLORS,
            "typography": DEFAULT_TYPOGRAPHY,
        },
        "art_direction": {
            "mood": "bright, precise, credible technology venture",
            "motifs": ["thin technical lines", "soft cards", "modular system diagrams", "measured accent bars"],
            "composition_principles": [
                "one governing idea per slide",
                "repeat a small set of accents, cards, and diagram primitives",
                "vary layout rhythm without changing the visual language",
            ],
            "background_style": "white or near-white canvas with sparse technical line accents",
            "card_style": "near-white panels, thin borders, small radius, no heavy shadow",
            "diagram_style": "simple node-link, process, or layered system diagrams using the locked palette",
            "chart_style": "minimal axes, direct labels, restrained accent fills, no decorative chart effects",
            "avoid": ["dark dashboard aesthetic", "neon-on-black", "decorative noise", "paragraph-heavy pages"],
        },
        "layout_system": {
            "grid": "12-column 1280x720 canvas with 60-80px outer margins",
            "density": "one governing idea per slide; use cards and diagrams for support",
            "archetypes": LAYOUT_ARCHETYPE_LIBRARY,
            "variation": ["hero", "evidence grid", "process/timeline", "metrics cards", "comparison", "closing"],
            "diversity_policy": "Choose specific semantic archetypes from content rather than quotas. Avoid generic two-column pages unless the right/left structure is distinctive and justified.",
            "soft_constraints": "guide composition and visual emphasis, but do not lock exact coordinates for every page",
        },
        "component_system": {
            "cards": "near-white fills, 8-12px radius, 1px border, no heavy shadows",
            "icons": "chunk-filled placeholders, 20-40px, one accent color per group",
            "charts": "prefer simplified SVG chart motifs; reserve chart templates for explicit data-heavy pages; include chart-plot-area markers for real data charts",
            "chart_template_policy": "choose real template keys from templates/charts/charts_index.json as semantic vocabulary, then redraw/restyle in the locked theme",
            "callouts": "short conclusion phrases with accent bars or small badges, never long paragraphs",
        },
        "assets": {
            "icons": {"library": "chunk-filled", "inventory": ICON_INVENTORY},
            "images": {},
        },
        "slides": slides,
    }
    lock = {
        "canvas": canvas,
        "colors": DEFAULT_COLORS,
        "typography": DEFAULT_TYPOGRAPHY,
        "icons": {"library": "chunk-filled", "inventory": ICON_INVENTORY},
        "images": {},
        "spacing": {"outer_margin": 64, "card_gap": 20, "section_gap": 28},
        "shape_language": {"radius": 10, "stroke_width": 1, "shadow": "none"},
        "style_anchor": {
            "theme": "light technology venture deck",
            "repeat": ["white canvas", "thin slate borders", "blue/teal/amber accents", "soft cards", "simple technical diagrams"],
            "vary": ["slide archetype", "diagram type", "card count", "accent placement"],
        },
        "theme_color_policy": {
            "primary_accent": DEFAULT_COLORS["primary"],
            "supporting_accents": [DEFAULT_COLORS["accent"], DEFAULT_COLORS["secondary_accent"]],
            "allow_extra_colors": "yes, as subtle tints, semantic highlights, or chart support",
            "dominance_rule": "primary_accent must remain the dominant non-neutral accent on every slide; supporting colors must not turn an individual slide into a green/orange/other theme",
        },
        "flex_rules": {
            "allowed": "layout may adapt to page content as long as palette, typography, spacing, and shape language stay consistent",
            "not_allowed": "dark pages, one-off palettes, invented icon styles, dense paragraph dumps, exact visual clones on every page",
        },
        "chart_rules": {
            "style": "light, minimal axes, restrained labels, no clip-path on chart elements",
            "auto_calibration": "scan-only",
            "catalog_source": "templates/charts/charts_index.json",
            "available_templates": [item["key"] for item in build_chart_template_reference()],
            "selection_policy": "choose real catalog keys as chart_or_diagram values; redraw/restyle in the locked theme",
            "plot_area_marker": "required for real data charts",
        },
        "page_rhythm": page_rhythm,
        "forbidden": FORBIDDEN,
    }
    return plan, lock


def build_design_plan_prompt(deck: Deck, canvas_format: str, style: str, cookbook: Cookbook | None = None) -> str:
    slide_briefs = []
    for slide in deck.slides:
        body = re.sub(r"\s+", " ", slide.body).strip()
        slide_briefs.append(
            {
                "index": slide.index,
                "title": slide.title,
                "kind": slide.kind,
                "section_title": slide.section_title,
                "svg_filename": slide.svg_filename,
                "content_excerpt": body[:700],
            }
        )
    chart_reference = build_chart_template_reference()
    common_prefix = build_deck_context_prefix(deck, canvas_format, style, cookbook)
    cookbook_rules = ""
    if cookbook is not None:
        cookbook_rules = f"""
Theme Cookbook application rules:
- Treat cookbook `{cookbook.id}` as a hard art-direction system, not a loose inspiration paragraph.
- Convert cookbook tokens into `theme`, `art_direction`, `layout_system`, `component_system`, `assets`, and `spec_lock`.
- Treat cookbook recipes as reference exemplars unless the cookbook explicitly says otherwise. Do not force every slide into one of the named recipes.
- Choose each slide's semantic structure from source content first. If a named cookbook recipe fits, use it. If not, create a cookbook-compatible `layout_family` such as `g08_adapted_funnel`, `g08_adapted_sankey`, or `g08_adapted_dense_table`.
- If the slide needs a chart, diagram, framework, table, process, architecture visual, or infographic, choose `chart_or_diagram` from the full chart catalog before consulting cookbook recipe examples.
- If the cookbook specifies fixed chrome, spacing, card geometry, decorative assets, or chart restyling rules, materialize those values in `spec_lock` so SVG workers do not have to infer them.
- If generic defaults conflict with the cookbook, the cookbook wins, except for PPT-safe SVG forbiddens and source-content faithfulness.
- `spec_lock.cookbook` should record cookbook id, priority, required repeats, recipe reference vocabulary, adaptation policy, decorative asset policy, chart catalog precedence, and forbidden drift.
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
- Design for a polished Chinese presentation: clear hierarchy, generous whitespace, cookbook-aligned art direction, restrained accent color, diagram/card/chart-friendly layouts.
- Light theme only. Backgrounds must be white or near-white (`#FFFFFF`, `#F8FAFC`, `#F1F5F9`, `#EEF2FF`, `#E0F2FE`). Do not use dark theme, dark canvas, black hero background, GitHub-dark palette, neon-on-black, or large dark panels.
- Avoid monotonous single-column bullet pages. Vary rhythm across cover-like, two-column, metric/card, timeline/process, evidence grid, and conclusion layouts where appropriate.
- `spec_lock` must be a strict visual anchor: include canvas, colors, typography, spacing, shape_language, icon_rules, chart_rules, svg_rules, page_rhythm, and forbidden.
- `icons` and `images` must be JSON objects, not strings.
- Use this icon library inventory exactly when icons are needed: {", ".join(ICON_INVENTORY)}.
- Make art direction explicit enough for independent SVG page generation: include mood, motifs, composition principles, card style, diagram style, chart style, and slide archetypes.
- Add useful visual guidance for every slide: one concise but concrete sentence describing composition intent, focal visual, component/card/chart treatment, decorative motif, whitespace rhythm, and accent usage where relevant.
- Keep all per-slide text fields compact: `intent`, `composition`, `visual_structure`, `why_this_layout`, `visual_metaphor`, and `visual_guidance` should be short phrases or one short sentence, not paragraphs.
- `visual_guidance` must improve aesthetic execution, not merely repeat the chosen layout. Name the design moves that make the selected chart/layout beautiful: card silhouette, title scale, label placement, highlight path, axis treatment, decorative image/motif, rhythm of empty space, and micro-contrast.
- When `chart_or_diagram` is selected, explain how to restyle that visualization in the theme: what is emphasized, how labels/legends should sit, what supporting marks are muted, and what small creative detail prevents a generic chart look.
- When a page uses cards, specify the card grammar: radius, border weight, fill relationship, header badge, icon placement, spacing, and how cards align to the page's narrative flow.
- If a cookbook is active, `visual_guidance` should translate cookbook style into the exact slide structure instead of producing vague inspiration language.
- Avoid generic guidance such as "make it polished" or "use a beautiful layout" unless it is followed by concrete visual choices.
- The full response must include all slides plus both marker pairs. Prefer concise slide guidance over long prose.
- Do not over-lock each page. Avoid exact coordinates or mandatory object counts unless the content truly requires them.
- Keep style consistency through repeated palette, typography, spacing, shape language, icon library, and diagram primitives; vary only the layout archetype and focal visualization.
- Color variety is allowed, but theme continuity is not optional: the primary accent must remain dominant on every page; secondary accents and extra colors are supporting details only.
- Do not use numeric layout quotas. Instead, choose layouts semantically from the slide content.
- Prefer specific layout archetypes over generic containers. Avoid repeating generic `two_column_left_right`; if a split layout is genuinely best, make `layout_signature` specific, e.g. `left narrative + right market growth bars`, `left product exploded view + right metric cards`, or `left quotes + right credibility badges`.
- Avoid adjacent slides with the same layout_family unless their visual_structure is materially different.
- Every slide must include `layout_family`, `layout_signature`, `visual_structure`, and `why_this_layout` so SVG generation has concrete structure guidance.
- Use the chart template catalog below as semantic visualization vocabulary. The model does not need to read SVG template code; choose real template names from the catalog, then restyle/redraw them according to spec_lock and cookbook.
- For every slide that needs a chart, diagram, framework, table, process, architecture visual, or infographic, set `chart_or_diagram` to one catalog `key`. Leave it empty only when the recipe is purely text/image/quote/team.
- Do not invent chart/template names. If no catalog item fits, write a cookbook-compatible adapted layout in `layout_family` and leave `chart_or_diagram` empty.
- Do not over-select chart types merely because the cookbook describes them in detail; detailed cookbook recipes are examples of style execution, not priority rankings.
- Put the catalog source and selected template keys in `spec_lock.chart_rules`.

Design plan field contract:
- `rhythm`: a page pacing tag, not a mood word. Use values such as `hero`, `showcase`, `dense`, `breathing`, `process`, `future`, `closing` when they fit. It controls whitespace, text amount, and visual weight.
- `layout`: the archetype or catalog-derived structure, e.g. `product_exploded_view`, `executive_summary_strips`, `roadmap_vertical`.
- `layout_family`: broader family for continuity checks, e.g. `product`, `timeline`, `dashboard`, `matrix`, `network`, `quote`, `closing`.
- `layout_signature`: a short spatial blueprint that could be sketched, e.g. `left product image + right spec cards`, `top timeline + bottom impact summary`.
- `intent`: the audience-facing message this slide must prove.
- `composition`: the major regions and reading order.
- `visual_structure`: visible primitives to draw, e.g. `milestone nodes + text blocks`, `hero image + metric tiles`.
- `why_this_layout`: why this structure fits the source content, not a generic justification.
- `visual_metaphor`: a motif the SVG can render subtly, e.g. launch trajectory, sensor mesh, precision cockpit.
- `visual_guidance`: the execution brief. Mention card grammar, chart label/legend placement, decorative motif, highlight path, image framing, whitespace rhythm, and accent hierarchy where relevant.
- `icon_plan`: exact icon placeholder names from inventory, only when icons have semantic value.
- `chart_or_diagram`: one real catalog key when the page needs data/diagram structure; empty only for pure quote/image/text/team pages.
- `content_density`: `low`, `medium`, `high`, or `showcase`; use it to tell SVG generation how aggressively to compress visible text.
- These fields should agree with each other. Do not set `chart_or_diagram=roadmap_vertical` while `layout_signature` describes unrelated KPI cards.

{cookbook_rules}

Layout archetype library:
{json.dumps(LAYOUT_ARCHETYPE_LIBRARY, ensure_ascii=False, indent=2)}

Available chart/diagram template catalog:
{json.dumps(chart_reference, ensure_ascii=False, indent=2)}

Slide briefs JSON:
{json.dumps(slide_briefs, ensure_ascii=False, indent=2)}

Required design_plan schema:
{{
  "project_name": "",
  "deck_title": "",
  "style": "",
  "canvas": {{}},
  "theme": {{
    "name": "",
    "colors": {{"bg": "#FFFFFF", "panel": "#F8FAFC", "primary": "#1D4ED8", "accent": "#0F766E", "text": "#0F172A", "text_secondary": "#475569", "border": "#CBD5E1"}},
    "typography": {{"title_family": "", "body_family": "", "title": 34, "body": 18, "annotation": 13}}
  }},
  "art_direction": {{"mood": "", "motifs": [], "composition_principles": [], "background_style": "", "card_style": "", "diagram_style": "", "chart_style": "", "avoid": []}},
  "layout_system": {{"grid": "", "density": "", "archetypes": [], "diversity_policy": "", "soft_constraints": ""}},
  "component_system": {{"cards": "", "icons": "", "charts": "", "chart_template_policy": "", "callouts": "", "technical_motifs": ""}},
  "assets": {{"icons": {{"library": "chunk-filled", "inventory": []}}, "images": {{}}}},
  "cookbook": {{"id": "", "priority": "", "applied_to": ["design_plan", "spec_lock", "svg"], "recipe_policy": "reference examples, not whitelist", "adaptation_policy": "derive cookbook-compatible layouts when content requires other structures"}},
  "slides": [
    {{"index": 1, "title": "", "kind": "", "section_title": null, "svg_filename": "", "rhythm": "", "layout": "", "layout_family": "", "layout_signature": "", "intent": "", "composition": "", "visual_structure": "", "why_this_layout": "", "visual_metaphor": "", "visual_guidance": "", "icon_plan": [], "chart_or_diagram": "", "content_density": ""}}
  ]
}}

Required spec_lock schema:
{{
  "canvas": {{}},
  "colors": {{"bg": "#FFFFFF", "panel": "#F8FAFC", "primary": "#1D4ED8", "accent": "#0F766E", "text": "#0F172A", "text_secondary": "#475569", "border": "#CBD5E1"}},
  "typography": {{"title_family": "", "body_family": "", "title": 34, "body": 18, "annotation": 13}},
  "icons": {{"library": "chunk-filled", "inventory": {json.dumps(ICON_INVENTORY, ensure_ascii=False)}, "stroke_width": 2}},
  "images": {{}},
  "spacing": {{"outer_margin": 64, "card_gap": 20, "section_gap": 28}},
  "shape_language": {{"radius": 10, "stroke_width": 1, "shadow": "none"}},
  "style_anchor": {{"theme": "light technology venture deck", "repeat": [], "vary": []}},
  "cookbook": {{"id": "", "priority": "", "required_repeats": [], "layout_recipes": [], "adaptation_policy": "", "chart_catalog_precedence": "", "decorative_asset_policy": "", "forbidden_drift": []}},
  "theme_color_policy": {{"primary_accent": "#1D4ED8", "supporting_accents": ["#0F766E", "#F59E0B"], "allow_extra_colors": "", "dominance_rule": ""}},
  "flex_rules": {{"allowed": "", "not_allowed": ""}},
  "icon_rules": {{"syntax": "<use data-icon=\\"chunk-filled/name\\" .../>", "style": "filled, simple, one accent color"}},
  "chart_rules": {{"style": "light, minimal axes, no clip-path on chart elements, no rgba", "catalog_source": "templates/charts/charts_index.json", "selected_templates": [], "selection_policy": "choose real catalog keys by content semantics first, then redraw/restyle in cookbook theme", "plot_area_marker": "required for real data charts"}},
  "svg_rules": {{"root_bg": "#FFFFFF", "max_chars": 12000, "forbid": ["rgba()", "<style>", "class", "<foreignObject>", "<mask>", "<g opacity>", "<image opacity>"], "clip_path_policy": "only allowed on <image> with matching simple <clipPath> in <defs>"}},
  "page_rhythm": {{"P01": "hero", "P02": "dense"}},
  "forbidden": []
}}

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
        raise GenerationError(f"Model response missing marker pair: {start} / {end}")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise GenerationError(f"Model response contained invalid JSON for {start}") from exc


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


def enforce_light_theme(plan: dict[str, Any], lock: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    theme = plan.setdefault("theme", {})
    if not isinstance(theme, dict):
        theme = {}
        plan["theme"] = theme
    theme["colors"] = merge_light_colors(theme.get("colors", {}))
    theme.setdefault("typography", DEFAULT_TYPOGRAPHY)
    plan.setdefault(
        "art_direction",
        {
            "mood": "bright, precise, credible technology venture",
            "motifs": ["thin technical lines", "soft cards", "modular system diagrams", "measured accent bars"],
            "composition_principles": ["one clear governing idea per slide", "prefer diagrams/cards over bullet dumps"],
            "background_style": "white or near-white canvas with sparse technical line accents",
            "card_style": "near-white panels, thin borders, small radius, no heavy shadow",
            "diagram_style": "simple node-link, process, or layered system diagrams using the locked palette",
            "chart_style": "minimal axes, direct labels, restrained accent fills, no decorative chart effects",
            "avoid": ["dark dashboard aesthetic", "neon-on-black", "decorative noise", "paragraph-heavy pages"],
        },
    )
    plan.setdefault(
        "layout_system",
        {
            "grid": "12-column 1280x720 canvas with 60-80px outer margins",
            "density": "one governing idea per slide",
            "archetypes": ["cover", "evidence grid", "process/timeline", "metrics cards", "comparison", "closing"],
            "diversity_policy": "choose specific semantic archetypes from content rather than quotas; avoid generic repeat layouts",
            "soft_constraints": "guide composition and visual emphasis, but do not lock exact coordinates for every page",
        },
    )
    plan.setdefault(
        "component_system",
        {
            "cards": "near-white fills, 8-12px radius, 1px border, no heavy shadows",
            "icons": "chunk-filled placeholders, 20-40px, one accent color per group",
            "charts": "light, minimal axes, restrained labels, chart-plot-area markers for real data charts",
            "callouts": "short highlighted phrases, never full paragraphs",
            "technical_motifs": "thin lines, small nodes, measured accent bars, light system diagrams",
        },
    )
    plan.setdefault("assets", {})
    if isinstance(plan["assets"], dict):
        plan["assets"]["icons"] = {"library": "chunk-filled", "inventory": ICON_INVENTORY}

    lock["colors"] = merge_light_colors(lock.get("colors", {}))
    lock.setdefault("typography", DEFAULT_TYPOGRAPHY)
    lock["icons"] = {"library": "chunk-filled", "inventory": ICON_INVENTORY, "stroke_width": 2}
    lock.setdefault("spacing", {"outer_margin": 64, "card_gap": 20, "section_gap": 28})
    lock.setdefault("shape_language", {"radius": 10, "stroke_width": 1, "shadow": "none"})
    lock.setdefault(
        "style_anchor",
        {
            "theme": "light technology venture deck",
            "repeat": ["white canvas", "thin slate borders", "blue/teal/amber accents", "soft cards", "simple technical diagrams"],
            "vary": ["slide archetype", "diagram type", "card count", "accent placement"],
        },
    )
    lock.setdefault(
        "theme_color_policy",
        {
            "primary_accent": DEFAULT_COLORS["primary"],
            "supporting_accents": [DEFAULT_COLORS["accent"], DEFAULT_COLORS["secondary_accent"]],
            "allow_extra_colors": "yes, as subtle tints, semantic highlights, or chart support",
            "dominance_rule": "primary_accent must remain the dominant non-neutral accent on every slide; supporting colors must not turn an individual slide into a green/orange/other theme",
        },
    )
    lock.setdefault(
        "flex_rules",
        {
            "allowed": "layout may adapt to page content as long as palette, typography, spacing, and shape language stay consistent",
            "not_allowed": "dark pages, one-off palettes, invented icon styles, dense paragraph dumps, exact visual clones on every page",
        },
    )
    lock.setdefault("icon_rules", {"syntax": '<use data-icon="chunk-filled/name" .../>', "style": "filled, simple, one accent color"})
    chart_rules = lock.setdefault("chart_rules", {"style": "light, minimal axes, no clip-path on chart elements, no rgba"})
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
    if provider == "qwen":
        actual_model = qwen_model
        text, usage = call_qwen_openai(
            api_key=resolve_qwen_api_key(qwen_api_key),
            base_url=qwen_base_url,
            model=qwen_model,
            prompt=prompt,
            system=DEEPSEEK_SYSTEM,
            max_tokens=qwen_max_tokens,
            timeout=qwen_timeout,
        )
    else:
        actual_model = model
        text, usage = call_deepseek_anthropic(
            api_key=resolve_api_key(api_key),
            base_url=base_url,
            model=model,
            prompt=prompt,
            system=DEEPSEEK_SYSTEM,
            max_tokens=24000,
        )
    if logger:
        logger.log_transcript(
            f"{provider}_plan",
            system=DEEPSEEK_SYSTEM,
            prompt=prompt,
            response=text,
            metadata={"model": actual_model, "usage": usage},
        )
    plan = extract_json_marker(text, "---DESIGN_PLAN_JSON_START---", "---DESIGN_PLAN_JSON_END---")
    lock = extract_json_marker(text, "---SPEC_LOCK_JSON_START---", "---SPEC_LOCK_JSON_END---")
    plan, lock = enforce_light_theme(plan, lock)
    if logger:
        logger.log(f"{provider}_plan", usage=usage, input_chars=len(prompt), output_chars=len(text))
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
            metadata={"model": model, "usage": usage, "scope": "common_prefix"},
        )
        logger.log("deepseek_cache_prime", usage=usage, input_chars=len(prompt), output_chars=len(text))


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
