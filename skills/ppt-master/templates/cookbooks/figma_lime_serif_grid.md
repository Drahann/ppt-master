# Cookbook: figma_lime_serif_grid

Priority: hard theme system. This cookbook must shape `design_plan.json`, `spec_lock.json`, and per-slide SVG output.

Important philosophy:
- This cookbook is an art-directed adaptive grammar, not a layout/chart whitelist or a loose style reference.
- Source content and the full chart catalog decide semantic structure.
- The cookbook decides how that structure is rendered in the theme.
- Named recipes are reference exemplars; derive adapted layouts when needed.
- Semantic structure may adapt to content; source-native art moves must remain visibly inherited.
- Density may increase, but composition logic cannot collapse into generic cards.

Reference set:
- Source folder: `figma/65CMrCi7opIqi80NPrKFxu`
- Figma file: `https://www.figma.com/design/65CMrCi7opIqi80NPrKFxu/Untitled`
- Local evidence:
  - `figma/65CMrCi7opIqi80NPrKFxu/contact_sheet.png`
  - `figma/65CMrCi7opIqi80NPrKFxu/capture_manifest.json`
  - `figma/65CMrCi7opIqi80NPrKFxu/mcp/design_context_samples.md`
- Visual DNA: sharp editorial business deck with lime full-bleed pages, white analytical pages, black/dark-green sparse pages, Neuton serif display type, Open Sans body type, thin rules, hard rectangles, status pills, large metrics, and a restrained grid.
- Key source frames: `131:305`, `131:352`, `131:509`, `131:381`, `131:322`, `131:295`, `131:538`, `131:401`, `131:435`, `131:457`, `131:474`.

Coordinate note:
- Figma references are `1920 x 1080`.
- PPT Master SVG uses `viewBox="0 0 1280 720"`.
- Geometry below is already scaled by `2/3` unless explicitly labeled as Figma-native.

## 1. Pipeline Role

### 1.1 Design/spec stage

When generating `design_plan.json` and `spec_lock.json`:

- Set `design_plan.cookbook.id` and `spec_lock.cookbook.id` to `figma_lime_serif_grid`.
- Treat this cookbook as the hard art-direction system for typography, page chrome, color roles, grid rhythm, line weight, component geometry, chart restyling, and density handling.
- First decide each slide's semantic job from source content: section divider, agenda, narrative overview, objective/proof, milestone, status, timeline, budget, risk, team/contact, chart, table, architecture, or dense evidence.
- If a chart, diagram, framework, table, process, architecture visual, or infographic is needed, set `chart_or_diagram` to a real key from `templates/charts/charts_index.json`.
- Put either a matching `flsg_*` reference recipe or a derived `flsg_adapted_*` layout in `layout_family`, `layout_signature`, and `visual_structure`.
- Convert theme tokens into `spec_lock`: palette, typography, chrome, coordinate system, rule weights, status pill geometry, metric treatment, image placeholder policy, chart skin, density modes, and forbidden drift.
- Do not infer semantics from these recipe names. Recipes are examples of how the theme renders structures; source content and chart catalog still choose the structure.

### 1.2 SVG stage

When generating SVG:

- Follow `spec_lock` first. If `spec_lock` is incomplete, fall back to this cookbook.
- Build the selected `layout_family` visibly. If it is a named `flsg_*` recipe, use the corresponding geometry. If it is `flsg_adapted_*`, keep this theme's typography, chrome, thin-rule system, flat color fields, and editorial spacing.
- If `chart_or_diagram` names a catalog key, preserve that chart's semantic geometry and restyle it in this theme.
- Use source images when available. If no image exists for an image slot, render a light neutral checker or pale placeholder area with a short label; do not invent stock imagery.
- Use flat solid fills. Do not drift into gradients, shadows, glass panels, decorative blobs, or generic SaaS dashboard cards.

## 2. Global Tokens

Canvas:
- SVG root: `width="1280" height="720" viewBox="0 0 1280 720"`.
- Figma reference: `1920 x 1080`.
- Scale factor: `0.6667`.

Color tokens:
- `lime`: `#C7EF4E`
- `dark_green`: `#003310`
- `metric_green`: `#085420`
- `black`: `#000000`
- `white`: `#FFFFFF`
- `secondary_gray`: `#7A7A7A`
- `placeholder_light`: `#F3F3F0`
- `placeholder_mid`: `#DCDDD4`
- `rule_light_on_dark`: `#7A7A7A`

Semantic color roles:
- White analytical pages: background `white`, primary text `black`, secondary text `secondary_gray`, accent fields `lime`, metric text `metric_green`.
- Lime section/action pages: background `lime`, primary text `black`, display text `dark_green`, dividers `black` or darkened lime-green.
- Dark pages: background `black` or `dark_green`, primary text `white`, display/section accent `lime`, dividers `secondary_gray` or low-contrast green.
- Do not rely on Figma variable names alone. In this source, a variable named `White` can resolve to `#000000`; use resolved colors and semantic roles.

Typography:
- Display/title stack: `Neuton, Georgia, Times New Roman, SimSun, Songti SC, serif`.
- Body stack: `Open Sans, Arial, Microsoft YaHei, PingFang SC, sans-serif`.
- Label stack: `Open Sans, Arial, Microsoft YaHei, PingFang SC, sans-serif`.
- CJK fallback: use `Microsoft YaHei` or `PingFang SC` for body; use `SimSun`/`Songti SC` for display if Neuton is unavailable.

Scaled type ramp:
- Hero display: `font-size=133`, Neuton Light, line-height `1.0`, letter spacing about `-1.5`.
- Page title: `font-size=53`, Neuton Light, line-height `1.1`, letter spacing about `-1.1`.
- Body large/headline: `font-size=24`, Open Sans Regular, line-height `1.2`, letter spacing about `-0.5`.
- Body medium: `font-size=16`, Open Sans Regular, line-height `1.3`.
- Body small/status text: `font-size=13`, Open Sans Regular, line-height `1.3`.
- Label/chrome: `font-size=13`, Open Sans SemiBold, uppercase, letter spacing about `0.3`.
- Metric number: `font-size=133` for huge 3-column metrics; `font-size=53..72` for budget/status metrics.

Shape language:
- Flat, sharp, editorial, grid-based.
- Most rectangles have `rx=0`.
- Status pills may use rounded capsules with `rx=27`.
- No card-shadow system.
- No generic rounded white cards.
- Use thin `1px` rules in Figma, scaled to `0.7..1` SVG stroke; use `1` for PPT robustness.
- Use hard lime rectangles, thin separators, timeline rules, progress bars, and direct text labels.

Spacing and chrome:
- Primary outer margin: `67`.
- Top project label: `x=67`, `y=47`, label size `13`.
- Top page number: `x=1195`, `y=47`, `text-anchor="end"`, label size `13`.
- Top rule: `x1=67`, `x2=1211`, `y=67`, `stroke-width=1`.
- Standard title: `x=67`, `y=143`, width about `1145`, size `53`.
- Dark risk title: `x=67`, `y=128`, width about `758`, size `53`.
- Use the top chrome on most content pages. Full title/closing pages may use footer-style metadata instead.

Reusable SVG chrome:

```xml
<text x="67" y="47" font-family="Open Sans, Arial, Microsoft YaHei, sans-serif" font-size="13" font-weight="600" letter-spacing="0.3" text-transform="uppercase" fill="#7A7A7A">PROJECT NAME</text>
<text x="1195" y="47" text-anchor="end" font-family="Open Sans, Arial, Microsoft YaHei, sans-serif" font-size="13" font-weight="600" letter-spacing="0.3" fill="#7A7A7A">03</text>
<line x1="67" y1="67" x2="1211" y2="67" stroke="#7A7A7A" stroke-width="1"/>
```

On lime backgrounds, chrome text and rules may be `#000000`. On black/dark-green backgrounds, chrome should be `#7A7A7A` or `#FFFFFF` depending on contrast.

## 3. Decorative / Asset System

This theme is not decorative in the papercut sense. Its identity comes from disciplined editorial typography, lime fields, dark fields, and thin structural rules.

Required motifs:
- Top chrome line with project label and page number.
- Large Neuton serif title or display word.
- Lime accent fields or dark-green/black full-bleed fields.
- Thin rule separators.
- Direct labels instead of icons.

Source-native art moves:
- `top_editorial_chrome`: small project label, page number, and full-width thin rule at the top of normal content pages.
- `hard_lime_slab`: flat `#C7EF4E` rectangular proof/status/action field with sharp corners.
- `black_green_reversal`: black or dark-green full-bleed page with lime display type or lime connectors.
- `giant_neuton_metric`: oversized Neuton numeral or display word used as the visual mass.
- `thin_rule_grid`: 1px dividers, table rules, timeline rails, and vertical separators as structure.
- `status_capsule`: compact rounded dark-green pill with lime/white status text.
- `narrow_editorial_chrome`: small uppercase labels, direct captions, and page metadata instead of icons.

Design-plan usage:
- Put a concrete recipe or motif in `source_recipe_anchor`, such as `flsg_status_dashboard`, `flsg_white_metric_columns`, or `flsg_black_green_reversal`.
- Put 2+ items from `Source-native art moves` in `required_art_moves` for every normal slide.
- Do not use generic anchors like `matrix`, `dashboard`, or `process` without a `flsg_*` adapted prefix and concrete art moves.

Reusable structural shapes:

```xml
<!-- hard lime proof panel -->
<rect x="54" y="442" width="377" height="201" fill="#C7EF4E"/>

<!-- thin top rule -->
<line x1="67" y1="67" x2="1211" y2="67" stroke="#7A7A7A" stroke-width="1"/>

<!-- status pill -->
<rect x="467" y="185" width="97" height="29" rx="14.5" fill="#003310"/>
<text x="515" y="203" text-anchor="middle" font-family="Open Sans, Arial, sans-serif" font-size="12" fill="#C7EF4E">Complete</text>

<!-- progress bar -->
<rect x="67" y="649" width="1147" height="21" fill="#C7EF4E"/>
<rect x="67" y="649" width="855" height="21" fill="#003310"/>

<!-- risk arrow connector -->
<line x1="605" y1="285" x2="706" y2="285" stroke="#C7EF4E" stroke-width="1"/>
<path d="M699 280 L706 285 L699 290" fill="none" stroke="#C7EF4E" stroke-width="1"/>
```

Image treatment:
- Use source images only when provided.
- Image/evidence pages use rectangular slabs or placeholder rectangles, no heavy border radius.
- If an image is missing, use a pale checker-like placeholder region with a short caption, not a generated photo.
- Keep image labels small, uppercase, and aligned to the grid.

## 4. Reference Layout Recipes

These recipe IDs are teaching examples and named shortcuts, not an exhaustive layout list.

Use a listed ID when content naturally matches it. If content needs another structure, derive `flsg_adapted_<semantic_structure>` while preserving this theme's visual grammar.

Reference recipes:
- `flsg_lime_agenda`
- `flsg_white_metric_columns`
- `flsg_lime_action_columns`
- `flsg_lime_image_milestones`
- `flsg_dark_overview_people`
- `flsg_dark_title_footer`
- `flsg_dark_contact`
- `flsg_status_dashboard`
- `flsg_quarterly_timeline`
- `flsg_budget_metric_stack`
- `flsg_dark_risk_mitigation`
- `flsg_adapted_table`
- `flsg_adapted_chart`
- `flsg_adapted_architecture`
- `flsg_adapted_comparison`

Recipe art-move map:
- `flsg_lime_agenda`: `hard_lime_slab`, `giant_neuton_metric`, `thin_rule_grid`, `top_editorial_chrome`.
- `flsg_white_metric_columns`: `top_editorial_chrome`, `hard_lime_slab`, `giant_neuton_metric`, `thin_rule_grid`.
- `flsg_lime_action_columns`: `hard_lime_slab`, `top_editorial_chrome`, `thin_rule_grid`, `narrow_editorial_chrome`.
- `flsg_lime_image_milestones`: `hard_lime_slab`, `thin_rule_grid`, `narrow_editorial_chrome`, rectangular image slab.
- `flsg_dark_overview_people`: `black_green_reversal`, `top_editorial_chrome`, `thin_rule_grid`, direct labels.
- `flsg_dark_title_footer`: `black_green_reversal`, `giant_neuton_metric`, footer metadata chrome.
- `flsg_dark_contact`: `black_green_reversal`, `giant_neuton_metric`, `thin_rule_grid`, footer metadata chrome.
- `flsg_status_dashboard`: `top_editorial_chrome`, `status_capsule`, `thin_rule_grid`, hard rectangular evidence panels.
- `flsg_quarterly_timeline`: `top_editorial_chrome`, `thin_rule_grid`, `hard_lime_slab`, progress/timeline rail.
- `flsg_budget_metric_stack`: `top_editorial_chrome`, `giant_neuton_metric`, `thin_rule_grid`, metric-green proof numbers.
- `flsg_dark_risk_mitigation`: `black_green_reversal`, `thin_rule_grid`, lime arrow connectors, `status_capsule`.
- `flsg_adapted_table`: `top_editorial_chrome`, `thin_rule_grid`, `status_capsule`, narrow editorial labels.
- `flsg_adapted_chart`: `top_editorial_chrome`, `thin_rule_grid`, `hard_lime_slab`, direct chart labels.
- `flsg_adapted_architecture`: `top_editorial_chrome`, `thin_rule_grid`, hard rectangular nodes, lime connector rails.
- `flsg_adapted_comparison`: `top_editorial_chrome`, `hard_lime_slab`, `thin_rule_grid`, direct labels.

Forbidden drift:
- Do not use blue technology gradients.
- Do not use shadowed cards, glassmorphism, neon glows, 3D objects, bokeh, decorative orbs, or random abstract blobs.
- Do not make pages beige, coffee, slate-blue, or purple-gradient.
- Do not use icons as the main visual system.
- Do not wrap every content unit in rounded cards. Pills are reserved for status labels.
- Do not remove the top chrome on normal content pages.
- Do not replace Neuton display type with a generic sans-serif title.

## 5. Recipe Details

### 5.1 `flsg_lime_agenda`

Use for agenda, TOC, and section-entry pages.

Composition:
- Full-bleed lime background.
- Giant Neuton display word on the left.
- Agenda list on the right with thin dividers.
- Top chrome in black.

Geometry:
- Background: `rect 0 0 1280 720 fill="#C7EF4E"`.
- Display word: `x=67`, `y=423`, size `133`, fill `#003310`, max 1 line.
- Agenda group: `x=747`, `y=238`, width `466`.
- Agenda line text: Open Sans Regular `24`, black, line-height `1.2`.
- Row gap: about `17`.
- Divider: `x1=747`, `x2=1213`, `stroke="#000000"`, `stroke-width=1`, positioned after each item.

Failure modes:
- Do not center the title.
- Do not create bullet dots.
- Do not turn the agenda into cards.

### 5.2 `flsg_white_metric_columns`

Use for objectives, goals, KPI proof, three strategy pillars with numbers.

Composition:
- White background.
- Standard top chrome.
- Large Neuton title at upper left.
- Three evenly spaced content columns.
- Lime proof panels across the lower part of each column.
- Huge metric numbers in metric green.

Geometry:
- Title: `x=67`, `y=143`, width `1145`, size `53`.
- Column x positions: `67`, `456`, `845`.
- Column width: `365..370`.
- Column text group starts around `y=283`.
- Body headline: Open Sans Regular `24`, black.
- Body paragraph: Open Sans Regular `16`, gray, width `365`, line-height `1.3`.
- Lime panels:
  - `x=54`, `446`, `835`
  - `y=442`
  - `w=377`, `h=201`
- Metric label: Open Sans SemiBold `13`, uppercase, black, inside panel near `x+13`, `y+24`.
- Metric number: Neuton Light `133`, fill `#085420`, baseline around `y+160`.

Variants:
- For two metrics, use two wider panels.
- For four metrics, reduce number size to `96` and use a 2x2 grid.
- If no numeric values exist, use `flsg_lime_action_columns` or `flsg_adapted_comparison`.

### 5.3 `flsg_lime_action_columns`

Use for next steps, action plan, workstreams, recommendations, and 4-column task lists.

Composition:
- Full-bleed lime background.
- Standard top chrome in black.
- Title at upper left.
- Four text columns separated by vertical rules.

Geometry:
- Title: `x=67`, `y=239`, size `53`, black.
- Column x positions: `67`, `284`, `501`, `718`.
- Column width: about `170`.
- Start y: `276`.
- Vertical separator lines: `x=67`, `284`, `501`, `718`; `y1=276`, `y2=347` or taller depending content.
- Column heading: Open Sans Regular `16`, black, max 3 lines.
- Body: Open Sans Regular `10..11`, black, line-height `1.3`, max 5 short lines.

Failure modes:
- Do not overuse tiny body text. If a column needs more than 5 lines, switch to a 2-column adapted layout.
- Do not add icons or numbered circles.

### 5.4 `flsg_lime_image_milestones`

Use for milestones with screenshots, evidence images, product snapshots, or achieved deliverables.

Composition:
- Full-bleed lime background.
- Title on left, split across lines if needed.
- Three image slabs across the upper-right/middle.
- Caption labels and descriptions below each image.

Geometry:
- Title: `x=67`, `y=242`, width `240`, size `53`, black.
- Image slabs:
  - x `410`, `554`, `698` in compact form if three equal cards are needed; or use wider slots `410`, `684`, `958`.
  - y around `238`.
  - height around `180..230`.
- Caption label: Open Sans SemiBold `13`, uppercase, black.
- Description: Open Sans Regular `11..13`, black, line-height `1.25`.

Image rules:
- Use rectangular clips via `<image preserveAspectRatio="xMidYMid slice">`.
- If missing, use `placeholder_light` checker area and a brief label.
- Do not add drop shadows.

### 5.5 `flsg_dark_overview_people`

Use for project overview, team overview, scope, dates, and project metadata.

Composition:
- Black background.
- Top chrome and rule in dark gray.
- Left narrative block.
- Right date/team columns.

Geometry:
- Title: `x=67`, `y=239`, size `32..36`, Neuton Light, white.
- Body narrative: `x=67`, `y=350`, width `370`, Open Sans Regular `16`, white, line-height `1.3`.
- Date or right label: `x=747`, `y=239`, Open Sans SemiBold `13`, uppercase, white or gray.
- People list columns: right side, Open Sans body `13..14`, names white, roles gray.

Failure modes:
- Do not use lime panels on this page. Keep it sparse and documentary.
- Do not use profile avatar placeholders unless source provides photos.

### 5.6 `flsg_dark_title_footer`

Use for major status/title transition pages and closing title pages.

Composition:
- Dark green full-bleed background.
- Huge lime Neuton display title.
- Thin footer rule and compact metadata at bottom.

Geometry:
- Title: `x=333`, `y=96`, size `80..96`, fill `#C7EF4E`, max 1 line.
- Footer rule: `x1=333`, `x2=1211`, `y=550`, stroke muted green/gray.
- Footer metadata columns: y `575`, label size `13`, lime for project/title, white/gray for secondary.
- Optional logo placeholder at bottom-right as text, not as a graphic if no source logo exists.

Failure modes:
- Do not center everything vertically; keep the title high and left-biased.
- Do not add background patterns.

### 5.7 `flsg_dark_contact`

Use for Q&A, thank-you, contact, and final discussion.

Composition:
- Dark green background.
- Large lime `Q&A`, `Questions`, or closing phrase on left.
- Contact blocks on right/middle.

Geometry:
- Main display: `x=80`, `y=505`, size `80..100`, Neuton Light, lime.
- Contact blocks: `x=520` and `x=780`, y around `520`, width `220`.
- Name: Open Sans SemiBold `13`, lime or white.
- Email/role: Open Sans Regular `10..12`, white.

Failure modes:
- Do not use a contact card container.
- Do not add social icons.

### 5.8 `flsg_status_dashboard`

Use for project status, workstream tracker, launch readiness, milestone health, or a compact roadmap state.

Composition:
- White background.
- Standard top chrome.
- Title on left.
- Workstream labels and status pills in the middle.
- Body descriptions on the right.
- Progress bar across bottom.

Geometry:
- Title: `x=67`, `y=143`, width `380`, size `53`, black.
- Pill column: `x=467`, `y=185/226/338/375/491/531`, `w=97`, `h=29`, `rx=14.5`.
- Workstream label x: `467`, y about `149`, `303`, `451`; label size `13`, uppercase, black.
- Body x: `585`, width `626`, body size `16`, gray, line-height `1.3`.
- Progress bar:
  - base `x=67`, `y=649`, `w=1147`, `h=21`, fill lime
  - progress overlay `x=67`, `w=855` for about 75%, fill dark green
- Date labels: y about `629`, size `13`, uppercase.

Status pill colors:
- Complete: fill `#003310`, text `#C7EF4E`.
- In progress: fill `#C7EF4E`, text `#000000`.
- Not started: fill `#000000`, text `#FFFFFF`.
- At risk: fill `#000000`, text `#C7EF4E` plus adjacent label if needed.

Failure modes:
- Do not surround this dashboard with cards.
- Do not add dashboard sidebars or icon sets.
- Keep it editorial and thin-lined.

### 5.9 `flsg_quarterly_timeline`

Use for roadmap, quarters, phases, research plan, launch plan, or delivery schedule.

Composition:
- White background.
- Standard top chrome.
- Title upper left.
- Horizontal rule timeline across the middle.
- Lime pill labels above milestone dots.
- Short bullets below each phase.

Geometry:
- Title: `x=67`, `y=143`, size `53`.
- Timeline line: `x1=67`, `x2=1211`, `y=365`, stroke dark green, width `1`.
- Milestone x positions for 4 points: `160`, `398`, `686`, `1015`.
- Dot radius: `2.5..3`, fill dark green.
- Lime quarter pill: `w=70..90`, `h=20`, `rx=10`, y around `330`.
- Bullets: x near each milestone, y `405`, width `220`, body size `12..13`, gray/black.

Chart template mapping:
- Use `timeline`, `roadmap_horizontal`, or related catalog key when content calls for timeline semantics.
- Restyle catalog geometry with lime pills, dark-green rule, and Open Sans labels.

### 5.10 `flsg_budget_metric_stack`

Use for budget, cost allocation, market size, financial snapshot, or three numeric callouts.

Composition:
- White background.
- Standard top chrome.
- Title on left.
- Main visual area/image placeholder center-left.
- Vertical stack of large serif metrics on right.

Geometry:
- Title: `x=67`, `y=143`, size `53`.
- Visual area: `x=337`, `y=200`, `w=430..520`, `h=300..360`.
- Metric stack x: `1110`, y values around `235`, `375`, `515`.
- Metric number: Neuton Light `48..56`, fill metric green.
- Metric label: Open Sans SemiBold `10..13`, uppercase, black.

Failure modes:
- Do not use a donut chart merely because this is financial. Choose chart type from data semantics.
- Do not add currency icons.

### 5.11 `flsg_dark_risk_mitigation`

Use for risks, objections, issue/response, mitigation plan, decision log, and dense two-column evidence.

Composition:
- Black background.
- Top chrome/rule in gray.
- Title upper left.
- Four issue rows.
- Left issue block and right mitigation block separated by lime arrow connectors.

Geometry:
- Title: `x=67`, `y=128`, width `758`, size `53`, white.
- Row group: `x=67`, `y=229`, width `1145`, height `424`.
- Row y positions: `229`, `345`, `461`, `577`.
- Left block width: `483`.
- Right block x: `697`, width `445`.
- Gap between blocks: about `214`.
- Issue heading: Open Sans Regular `24`, lime, line-height `1.2`.
- Issue body: Open Sans Regular `16`, white, line-height `1.3`.
- Mitigation body: Open Sans Regular `16`, white, line-height `1.3`.
- Arrow connector: `x1=605`, `x2=706`, y aligned to row center, stroke lime.

Variants:
- For 3 rows, increase row height and body size slightly.
- For 5 rows, reduce body to `13..14` and keep heading `20`.
- For risk matrices or severity scoring, use a real chart/table catalog key and apply this dark row styling.

Failure modes:
- Do not use red/yellow risk colors.
- Do not introduce warning icons.
- Do not make the rows into cards.

### 5.12 `flsg_adapted_table`

Use for high-density evidence, comparisons, feature matrices, financial line items, and requirements.

Composition:
- Pick white, lime, or dark background based on surrounding deck rhythm and content gravity.
- Use thin rules and direct labels, not boxed spreadsheet cells.
- Header row may use lime fill on white pages or black/dark-green fill on lime pages.

Geometry:
- Outer table x `67`, y `190..230`, width `1145`.
- Header height `34`.
- Row height `38..55` depending density.
- Column rules stroke `#7A7A7A` or dark green at width `1`.
- Header label: Open Sans SemiBold `12..13`, uppercase.
- Cell text: Open Sans Regular `12..15`, line-height `1.25`.

Chart template mapping:
- `comparison_table`, `feature_matrix_table`, `consulting_table`, or another real catalog table key.

### 5.13 `flsg_adapted_chart`

Use for any real data chart selected from the catalog.

Composition:
- Chart title follows standard Neuton page title.
- Plot area uses thin dark-green/gray axes, minimal gridlines, direct labels, and lime/dark-green highlights.
- Use white chart backgrounds on white pages; do not create a separate card container.

Restyling rules:
- Bar charts: lime bars with one dark-green highlight; labels in Open Sans.
- Line charts: dark-green primary line, lime highlight point/area, minimal gridlines.
- Area charts: pale lime area with dark-green stroke.
- Scatter/bubble: dark-green points plus lime highlight cluster.
- Heatmap/treemap: use lime-to-dark-green tonal scale, with black/white text based on contrast.
- Waterfall: lime positive, black/dark-green totals, gray negative if needed.
- Funnel/sankey: flat lime/dark-green bands, direct labels, no gradients.
- Radar: dark-green stroke, pale lime fill.

Required chart policy:
- Choose chart semantics from the full chart catalog first.
- Then restyle to this theme.
- Do not choose a timeline/matrix/metric layout merely because this cookbook documents it.

### 5.14 `flsg_adapted_architecture`

Use for systems, process, architecture, and module diagrams.

Composition:
- Use open grid layout with thin connectors.
- Nodes are text-first rectangles, sharp or slightly pill-like only for state labels.
- Use lime panels sparingly to highlight current/future or core modules.

Geometry:
- Node rectangles: sharp `rx=0`, stroke `#003310`, fill white or lime.
- Connector lines: stroke dark green, width `1`, arrowheads as simple paths.
- Labels: Open Sans SemiBold `13` uppercase for node group; Open Sans Regular `14..16` for node body.

Failure modes:
- Do not use cloud icons, server icons, or glossy architecture blocks.

## 6. Chart Catalog and Theme Restyling

The chart catalog comes from `templates/charts/charts_index.json`. Use it as the complete visualization vocabulary.

Selection order:
1. Read source content and decide data/relationship semantics.
2. Pick the most accurate `chart_or_diagram` key from the full catalog.
3. Preserve that chart/diagram's semantic geometry.
4. Restyle/redraw it in `figma_lime_serif_grid`.

Any real catalog key may be used. The suggested mappings below are examples, not limits.

Suggested mappings:
- Agenda/section navigation: no chart key unless the content is a process.
- Progress/status: `progress_bar_chart`, `bullet_chart`, `gantt_chart`, `roadmap_horizontal`.
- Timeline/roadmap: `timeline`, `roadmap_horizontal`, `gantt_chart`.
- Budget/finance: `waterfall_chart`, `stacked_bar_chart`, `donut_chart`, `comparison_table`, chosen by data semantics.
- Risk: `risk_matrix`, `matrix_2x2`, `comparison_table`, or `process_flow` when appropriate.
- Objectives/KPIs: `kpi_cards`, `metric_tiles`, `bar_chart`, `bullet_chart`.
- Architecture/process: `process_flow`, `layered_architecture`, `client_server_flow`, `swimlane_process`.
- Comparison: `comparison_columns`, `feature_matrix_table`, `matrix_2x2`.
- Team/org: `team_roster`, `org_chart`.

Theme restyling rules:
- Use Neuton for major titles and metric numbers.
- Use Open Sans for all chart labels, axes, tables, and annotations.
- Use lime as the primary highlight field; dark green as the serious/status/progress color; black/gray for supporting rules and text.
- Keep gridlines minimal. Prefer direct labels and thin dividers.
- Do not add chart cards. Put the chart directly on the page canvas.
- Avoid multicolor rainbow palettes. When more categories are required, use lime/dark-green/gray tonal variations plus direct labels.

## 7. Density and Text Fitting

This theme has real density range. It is not a sparse-only poster deck.

`content_density=low`:
- Use for agenda, divider, Q&A, dark title pages, and single-metric proof.
- One dominant title or metric.
- Body text maximum: 1 short paragraph or 3 labels.
- Preserve large whitespace.

`content_density=medium`:
- Use for normal presentation pages.
- 3 to 5 content groups.
- Body medium `15..16`, line-height `1.3`.
- Standard title size `48..53`.
- Use columns, status rows, timelines, or metric panels.

`content_density=high`:
- Use for risk pages, tables, technical detail, financial evidence, dense action plans.
- Title size may reduce to `40..48`.
- Body size may reduce to `12..14`, but never below `11` in SVG.
- Use thin rules, clear row grouping, and 2-column structures.
- Keep text concise by summarizing raw paragraphs into labels plus one or two evidence lines.

Text fitting rules:
- Neuton display titles: max 2 lines at `53`; if longer, reduce to `44..48` before wrapping.
- Hero display words: max 1 short line at `133`; if longer, use page-title scale.
- Body paragraphs: max 4 lines in metric/action columns; switch layout if more is needed.
- Status/risk rows: max 2 body lines per cell at medium density, 3 at high density.
- For CJK source text, use body sizes `13..18` and avoid excessive negative letter spacing.
- Never overlap top chrome, page title, or bottom progress bars.

## 8. SVG / PPT Safety Contract

Allowed:
- `<rect>`, `<line>`, `<path>`, `<circle>`, `<polyline>`, `<text>`, `<tspan>`, `<image>`.
- `rx` on status pills only or when a chart semantic requires a pill label.
- Individual `transform` for arrowheads and rotated labels if needed.
- Solid fills and direct strokes.

Forbidden:
- `<style>`, `class`, `<foreignObject>`, `clip-path`, `<mask>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, external URLs.
- Gradients, blurred shadows, filters, glass effects, image masks, group-level opacity.
- Remote Figma MCP asset URLs in final SVG. Use local project images or redraw simple lines/arrows as SVG primitives.

Root skeleton:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
  <text x="67" y="47" font-family="Open Sans, Arial, Microsoft YaHei, sans-serif" font-size="13" font-weight="600" letter-spacing="0.3" fill="#7A7A7A">PROJECT NAME</text>
  <text x="1195" y="47" text-anchor="end" font-family="Open Sans, Arial, Microsoft YaHei, sans-serif" font-size="13" font-weight="600" letter-spacing="0.3" fill="#7A7A7A">03</text>
  <line x1="67" y1="67" x2="1211" y2="67" stroke="#7A7A7A" stroke-width="1"/>
  ...
</svg>
```

## 9. Spec Lock Snippet

```json
"cookbook": {
  "id": "figma_lime_serif_grid",
  "priority": "hard",
  "required_repeats": [
    "1920-to-1280 scaled geometry",
    "Neuton serif display/title",
    "Open Sans body and uppercase labels",
    "top project-name/page-number/rule chrome on content pages",
    "flat lime/dark-green/black/white palette",
    "thin editorial rules and sharp rectangles"
  ],
  "source_native_art_moves": [
    "top_editorial_chrome",
    "hard_lime_slab",
    "black_green_reversal",
    "giant_neuton_metric",
    "thin_rule_grid",
    "status_capsule",
    "narrow_editorial_chrome"
  ],
  "layout_recipes": [
    "reference examples only; may derive flsg_adapted_* layouts when content requires other structures"
  ],
  "adaptation_policy": "derive theme-compatible layouts from source semantics while keeping typography, chrome, hard color fields, line rules, density rules, and 2+ source-native art moves per normal slide",
  "under_fidelity_checks": [
    "Every normal slide carries 2+ source-native FLSG art moves",
    "A viewer can recognize the lime serif grid template without seeing this cookbook name",
    "Density adaptation preserves editorial composition logic instead of collapsing into generic cards"
  ],
  "chart_catalog_precedence": "choose chart_or_diagram from the full catalog first, then redraw/restyle in figma_lime_serif_grid",
  "decorative_asset_policy": "redraw line and arrow assets as SVG primitives; use source images only when provided; use flat placeholders for missing image evidence",
  "forbidden_drift": [
    "blue tech gradients",
    "shadowed cards",
    "glassmorphism",
    "decorative blobs/orbs",
    "icon-driven layouts",
    "generic SaaS dashboards",
    "rounded cards except status pills",
    "remote Figma asset URLs"
  ]
},
"chart_rules": {
  "catalog_source": "templates/charts/charts_index.json",
  "selected_templates": [],
  "selection_policy": "choose real catalog keys by content semantics first, then redraw/restyle in cookbook theme",
  "style": "flat editorial chart skin with lime highlights, dark-green serious/progress marks, thin axes/rules, Open Sans labels, direct annotations, and no chart card container"
}
```

## 10. QA Checklist

- Cookbook id appears in `design_plan.cookbook.id` and `spec_lock.cookbook.id`.
- Normal content pages keep project label, page number, and top rule.
- Titles and big numbers use Neuton or configured serif fallback.
- Body, labels, chart labels, tables, and annotations use Open Sans or configured sans fallback.
- The deck alternates correctly among white, lime, black, and dark-green pages.
- Lime is crisp and dominant when used; it should not become a pale pastel theme.
- White pages do not become generic card dashboards.
- Dark pages stay sparse and high contrast.
- `design_plan.slides[*].source_recipe_anchor` uses concrete `flsg_*` recipes or motif anchors, not generic families.
- Normal slides carry 2+ `required_art_moves` from this cookbook.
- Density adaptation preserves FLSG composition logic: editorial chrome, rules, hard slabs, Neuton mass, and direct labels remain visible.
- A viewer can recognize the lime serif grid reference without seeing the cookbook name.
- Dense risk/table pages remain possible without text overlap.
- Charts use real catalog semantics before cookbook restyling.
- SVG contains no external Figma URLs, `<style>`, `class`, `clip-path`, `mask`, `rgba()`, or unsupported effects.
- Adjacent pages do not repeat the same column layout unless the source structure truly repeats.
