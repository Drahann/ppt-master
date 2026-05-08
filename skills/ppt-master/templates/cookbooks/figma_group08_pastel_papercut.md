# Cookbook: figma_group08_pastel_papercut

Priority: hard theme system. This cookbook must shape `design_plan.json`, `spec_lock.json`, and per-slide SVG output. It is intentionally different from `figma_group02_inter_precision`.

Important philosophy:
- This cookbook is a strong visual grammar, not a layout or chart whitelist.
- It teaches how this theme thinks: typography, paper geometry, rhythm, chrome, image treatment, spacing, and chart skin.
- The slide's source content and the full chart catalog still decide the semantic structure. This cookbook decides how that structure should look in the group-08 theme.
- Named `g08_*` recipes are reference exemplars. Use them when they fit; derive new cookbook-compatible layouts when the content needs another structure.

Reference set:
- Source folder: `W:\3spring\figma-slides\group-08`
- Visual DNA: Pastel Papercut editorial deck, oversized serif title, italic side phrases, white canvas, huge irregular paper cutout shapes, soft pastel blue/green/purple/yellow, rotated image slabs, minimal black rules.
- Key source slides: `4:2072`, `4:2086`, `4:2167`, `4:2256`, `4:2294`, `4:2343`, `4:2366`, `4:2441`, `4:2469`, `4:2500`.

## 1. Pipeline Role

### 1.1 Design/spec stage

When generating `design_plan.json` and `spec_lock.json`:

- Set `design_plan.cookbook.id` and `spec_lock.cookbook.id` to `figma_group08_pastel_papercut`.
- Treat this cookbook as a theme, layout grammar, and decorative asset system.
- First decide the slide's semantic job from the source content: narrative, comparison, proof, process, architecture, timeline, table, chart, team, quote, closing, or image evidence.
- If the slide needs a chart, diagram, framework, table, process, architecture visual, or infographic, set `chart_or_diagram` to a real key from `templates/charts/charts_index.json` before choosing a cookbook recipe.
- Do not invent chart template names. The full chart catalog is the vocabulary; this cookbook is the visual restyling and composition layer.
- Put either a matching `g08_*` reference recipe or a derived `g08_adapted_*` layout in `layout_family`, `layout_signature`, and `visual_structure`.
- Convert theme tokens into `spec_lock`: typography, colors, chrome, paper shape recipes, image policy, chart restyling rules, reference recipe vocabulary, adaptation policy, forbidden drift.

### 1.2 SVG stage

When generating an SVG:

- Build the selected `layout_family` visibly. If it is a named `g08_*` recipe, follow the recipe. If it is a derived `g08_adapted_*` layout, apply the same typography, paper geometry, black rule, image, and chrome language to the semantic structure.
- If `chart_or_diagram` names a catalog key, draw that catalog concept in this theme even when no exact recipe below describes it.
- Use the paper-cutout motifs on most pages. At least one large pastel shape should appear on every content slide unless the page is a pure image/device page.
- Use real project images only when provided by source markdown. If no image exists, draw paper shapes, not stock-like placeholders.
- Keep text editorial, but do not discard essential evidence. Use the requested `content_density`: low = sparse poster; medium = readable live presentation; high = leave-behind with tighter columns, smaller display type, and stronger text fitting.
- Do not switch back to modern sans-serif card/dashboard styling.

## 2. Global Tokens

Canvas:
- `viewBox="0 0 1280 720"`
- Figma reference is `1920 x 1080`; values here are already scaled.

Color tokens:
- `bg`: `#FFFFFF`
- `text`: `#111111`
- `text_secondary`: `#2F2F2F`
- `caption`: `#444444`
- `paper_blue`: `#BED0E8`
- `paper_green`: `#ACD6BC`
- `paper_yellow`: `#F3DB9B`
- `paper_purple`: `#F2CCFF`
- `paper_lavender`: `#D8C4F2`
- `paper_shadow`: `#EFE7D6`
- `rule`: `#111111`
- `primary`: `#111111`
- `accent`: `#F2CCFF`

Important:
- This is not a technology-blue deck.
- Use `#111111` as the main accent. Pastel paper shapes are the decorative color layer.
- Do not use dark backgrounds or large dark panels.

Typography:
- Title / display stack:
  - `font-family="Shippori Mincho, SimSun, Songti SC, Georgia, Times New Roman, serif"`
- Body / editorial stack:
  - `font-family="Playfair Display, Georgia, SimSun, Times New Roman, serif"`
- CJK dense fallback:
  - `font-family="SimSun, Microsoft YaHei, PingFang SC, serif"`
- Use serif stacks for the whole theme. Do not use Inter/Arial as the primary look.

Scaled type ramp:
- Cover title: `60..80`, weight `400`, line-height `1.05`
- Large page title: `60..80`, weight `400`, line-height `1.1`
- Section title: `60`, weight `400`
- Headline: `27`, weight `400`, line-height `1.1`
- Body editorial: `18..22`, weight `400`, line-height `1.25`
- Italic note / side phrase: `18`, italic, line-height `1.25`
- Caption / page mark: `13`, weight `400`
- Metric number: `72..82`, weight `400`
- Matrix / Venn label: `18`, italic

Shape language:
- Irregular large paper shapes made with SVG `<path>` or `<polygon>`.
- No heavy shadows.
- No card shadows.
- No colored card header bars.
- Rectangular image slabs may rotate `-3..4` degrees.
- Thin rules are black, `stroke-width="1.5"` or `2`.

Spacing:
- Outer margin: `60`
- Primary title x: `60`
- Primary title y: `60..100`
- Bottom captions: `x=60`, `y=660`
- Right page mark: `x=1180`, `y=660`, `text-anchor="end"`
- Side phrase column: `x=1170`, `y=160`, rotated 90 degrees or stacked vertically.

## 3. Fixed Decorative System

This theme needs decoration. Decoration is not optional.

### 3.1 Base paper wash

Use 1 to 3 oversized low-opacity pastel paths behind content. Preferred fills: `#F2CCFF`, `#BED0E8`, `#ACD6BC`, `#F3DB9B`.

Use these path recipes. Scale/translate them as needed.

Blue paper blob:

```xml
<path d="M1168 555 L1280 226 L1105 0 L510 156 C30 37 -43 378 19 580 L431 720 L570 268 L724 631 L1168 555 Z" fill="#BED0E8"/>
```

Green organic cutout:

```xml
<path d="M408 18 C502 16 568 15 582 15 L604 21 C654 56 687 86 713 126 C755 77 835 -26 916 4 C1016 42 1070 74 1088 134 C1074 207 1071 239 1071 239 L1104 292 C1220 308 1278 333 1269 395 C1241 482 1208 573 1138 584 C1047 598 927 615 927 615 C1019 702 1037 791 1004 855 C983 895 932 894 882 879 C779 846 668 770 625 674 C612 786 541 879 433 923 C346 958 214 969 137 934 C87 911 31 851 36 756 C41 674 163 646 163 646 C106 621 34 583 12 530 C-17 459 60 383 191 340 C304 303 365 289 365 289 C315 248 245 179 230 115 C215 49 292 21 408 18 Z" fill="#ACD6BC"/>
```

Simple purple ribbon:

```xml
<path d="M0 430 C180 360 310 430 470 390 C680 338 800 255 980 320 C1120 370 1210 325 1280 285 L1280 520 C1120 585 990 555 825 610 C650 668 500 594 310 635 C180 662 75 640 0 692 Z" fill="#F2CCFF"/>
```

Yellow quote splash:

```xml
<path d="M760 80 C890 30 1040 78 1130 176 C1212 265 1198 394 1115 477 C1015 578 858 560 743 485 C625 408 617 241 760 80 Z" fill="#F3DB9B"/>
```

Rules:
- Paper paths may go off-canvas.
- Use solid fills. Do not use gradients.
- Do not use masks or clip-paths.
- If paper shapes compete with text, lower visual weight by moving them behind or using a lighter color, not opacity on a group.

### 3.2 Micro-chrome

All non-cover and non-closing pages:

```xml
<g id="deck-chrome">
  <text x="60" y="662" font-family="Playfair Display, Georgia, SimSun, Times New Roman, serif" font-size="13" fill="#111111">PROJECT_LABEL</text>
  <text x="1180" y="662" text-anchor="end" font-family="Playfair Display, Georgia, SimSun, Times New Roman, serif" font-size="13" fill="#111111">P02 / 18</text>
</g>
```

Side phrase:
- Many pages should include an italic side phrase.
- Use short English or Chinese poetic phrasing, not functional instructions.
- SVG implementation can rotate the text:

```xml
<text x="1188" y="160" transform="rotate(90 1188 160)" font-family="Playfair Display, Georgia, SimSun, Times New Roman, serif" font-size="18" font-style="italic" fill="#111111">
  <tspan>Quiet structure, vivid evidence.</tspan>
</text>
```

Rules:
- No footer bars.
- No colored top strip.
- No dashboard header.

## 4. Reference Layout Recipe Vocabulary

These recipe IDs are teaching examples and named shortcuts, not an exhaustive whitelist.

Use a listed ID when the slide content naturally matches it. If the content needs a different structure, derive a new cookbook-compatible layout and name it `g08_adapted_<semantic_structure>` while preserving this theme's visual grammar.

Reference recipes:

- `g08_cover_papercut_title`
- `g08_chapter_papercut_title`
- `g08_toc_big_numbers`
- `g08_two_column_line_items`
- `g08_editorial_paragraph`
- `g08_numbered_list_with_side_note`
- `g08_three_column_editorial`
- `g08_left_text_rotated_image`
- `g08_image_with_numbered_list`
- `g08_metric_four_rows`
- `g08_metric_three_columns`
- `g08_metric_single_hero`
- `g08_milestone_big_numbers`
- `g08_vertical_timeline`
- `g08_matrix_paper_labels`
- `g08_venn_pastel_circles`
- `g08_phone_device_showcase`
- `g08_desktop_device_showcase`
- `g08_quote_yellow_splash`
- `g08_team_editorial_gallery`
- `g08_contact_closing`

Forbidden drift:
- Do not use group-02 gray block cards.
- Do not use blue tech cards, dashboard cards, or modern SaaS UI panels.
- Do not use icons as decoration. Use paper shapes, lines, image slabs, and typography.
- Do not put text inside rounded cards unless the semantic structure genuinely needs a label chip or compact table cell.
- Do not make every page into a three-column layout.
- Do not use random photos when source images are absent.

## 5. Recipe Details

### 5.1 `g08_cover_papercut_title`

Use for cover.

Composition:
- White background.
- One huge blue or green paper shape behind/right of title.
- Title top-left, large serif.
- Small caption bottom-left and page/year bottom-right.
- Optional italic side phrase rotated on right.

Geometry:
- Title: `x=60`, `y=105`, width `960`, size `68..76`, max 3 lines.
- Caption: `x=60`, `y=660`, size `13`.
- Right mark: `x=1180`, `y=660`, size `13`, anchor end.
- Side phrase: `x=1188`, `y=160`, rotated 90, size `18`, italic.

### 5.2 `g08_chapter_papercut_title`

Use for chapter/section divider.

Geometry:
- Large title: `x=60`, `y=110`, size `72`, max 2 lines.
- Paper ribbon behind lower third.
- Optional chapter number huge `x=760`, `y=430`, size `110`, fill `#111111`.

### 5.3 `g08_toc_big_numbers`

Use for agenda/table of contents.

Geometry:
- Left title: `x=60`, `y=90`, size `60`.
- Two columns of contents.
- Number size `96`, title size `27`.
- Left column x: number `390`, text `540`.
- Right column x: number `760`, text `910`.
- Row y positions: `105`, `235`, `365`, `495`.
- Underline each number with a black rule width `75`.

### 5.4 `g08_two_column_line_items`

Use for 4 to 6 line items.

Geometry:
- Background paper shape behind middle.
- Two columns:
  - Left x `90`, right x `665`
  - Row y `180`, `305`, `430`
- Item number: `font-size=56`, title `font-size=27`, body `font-size=17`.
- Thin black separator line below each item.

### 5.5 `g08_editorial_paragraph`

Use for a conceptual page, problem statement, or methodology explanation.

Geometry:
- Title: `x=60`, `y=105`, size `60..68`.
- Body block: `x=80`, `y=310`, width `760`, size `22`, line-height `30`, max 6 lines.
- Paper shape: right/lower area, does not cover text.
- Side phrase: right rotated.

Rule:
- No bullets. Write as a short editorial paragraph.

### 5.6 `g08_numbered_list_with_side_note`

Use for 3 to 4 steps/requirements.

Geometry:
- Title/subtitle: `x=60`, `y=90`, size `54`.
- Numbered list starts `x=90`, `y=230`.
- Numbers `56`, item title `27`, note `17`.
- Right note block: `x=840`, `y=260`, width `280`, italic size `20`.
- Purple/yellow paper block behind right note.

### 5.7 `g08_three_column_editorial`

Use for three themes, modules, innovation points, or advantages.

Geometry:
- Main title: `x=50`, `y=95`, size `72`, max 2 lines.
- Columns:
  - x `55`, `455`, `855`
  - headline y `400`, size `27`
  - italic body y `480`, size `18`, line-height `24`
  - width `330`
- One large paper shape behind top/right.

Rule:
- Do not wrap columns in cards.
- The whitespace between columns is the structure.

### 5.8 `g08_left_text_rotated_image`

Use when source has a meaningful image or product photo.

Geometry:
- Title: `x=60`, `y=95`, size `60`.
- Body: `x=60`, `y=260`, width `440`, size `20`.
- Image slab: `x=610`, `y=130`, `w=440`, `h=390`, rotated `-4` degrees around center.
- Add a paper shape behind image.

SVG image:
- `<image href="../images/file.png" x="610" y="130" width="440" height="390" preserveAspectRatio="xMidYMid slice" transform="rotate(-4 830 325)"/>`

If no image exists:
- Use `g08_editorial_paragraph` or `g08_three_column_editorial` instead.

### 5.9 `g08_image_with_numbered_list`

Use for image evidence plus 3 to 4 annotations.

Geometry:
- Image slab left: `x=60`, `y=170`, `w=470`, `h=390`, rotated `3`.
- Numbered list right: `x=660`, `y=180`, width `440`.
- Number `48`, title `25`, body `16`.

### 5.10 `g08_metric_four_rows`

Use for four numeric proof points.

Geometry:
- Left title: `x=60`, `y=75`, width `330`, size `60`.
- Rows:
  - Number x `430`, text x `820`
  - y `105`, `245`, `385`, `525`
- Number size `76`, title/explanation size `27`.
- A vertical paper strip behind the title column.

Rule:
- Use actual numbers. If no numbers exist, use a list recipe instead.

### 5.11 `g08_metric_three_columns`

Use for three large KPIs.

Geometry:
- Title: `x=60`, `y=85`, size `60`.
- Columns x `100`, `480`, `860`, y `290`.
- Metric number size `76`, label `24`, body `17`.
- Paper shape should cross behind the metric row.

### 5.12 `g08_metric_single_hero`

Use for one central result.

Geometry:
- Hero number: `x=80`, `y=350`, size `110`.
- Explanation headline: `x=560`, `y=260`, size `32`.
- Body: `x=560`, `y=330`, width `500`, size `20`.
- Paper splash behind number.

### 5.13 `g08_milestone_big_numbers`

Use for 4 to 5 milestones or optimization phases.

Geometry:
- Title: `x=60`, `y=95`, size `72`.
- Milestone numbers across middle:
  - x `150`, `380`, `610`, `840`, `1070`
  - y `445`, size `60`
- Thin connector lines black, no colored nodes.
- Alternating descriptions above/below line, size `17`.
- Paper ribbon diagonally behind the timeline.

Chart template mapping:
- `chart_or_diagram`: `timeline`

### 5.14 `g08_vertical_timeline`

Use for year-by-year or commit history.

Geometry:
- Left paper strip.
- Years/steps on left `x=170`, text on right `x=360`.
- Use black vertical rule `x=300`.
- Serif year size `42`, body size `18`.

Chart template mapping:
- `chart_or_diagram`: `roadmap_vertical` or `timeline`.

### 5.15 `g08_matrix_paper_labels`

Use for 2x2 positioning/tradeoff.

Geometry:
- Title: `x=60`, `y=95`, size `60`.
- Matrix center:
  - horizontal line `x1=170`, `x2=1120`, `y=405`
  - vertical line `x=640`, `y1=185`, `y2=615`
- Axis labels size `27`.
- Quadrant labels sit inside irregular paper shapes, not normal cards.
- Each label shape can be an ellipse-like path, size around `160 x 110`.

Chart template mapping:
- `chart_or_diagram`: `matrix_2x2`.

### 5.16 `g08_venn_pastel_circles`

Use for overlaps and capability combinations.

Geometry:
- Title: `x=60`, `y=95`, size `72`.
- Venn circles:
  - left circle `cx=650`, `cy=420`, `r=170`, fill `#F2CCFF`
  - right circle `cx=825`, `cy=420`, `r=170`, fill `#BED0E8`
  - optional top circle `cx=737`, `cy=290`, `r=150`, fill `#ACD6BC`
- Use `fill-opacity` on each circle individually, not on a group.
- Legend on left with small paper icons.

Chart template mapping:
- `chart_or_diagram`: `venn_diagram`.

### 5.17 `g08_phone_device_showcase`

Use for product/app/interface pages.

Geometry:
- Left title/body: `x=60`, title `y=100`, body `y=260`.
- Phone frame right: `x=760`, `y=90`, `w=260`, `h=540`, rounded `36`.
- Paper blob behind phone.
- Side phrase on far right.

If no real screenshot:
- Draw simplified phone UI with white screen and 4 pastel blocks.

### 5.18 `g08_desktop_device_showcase`

Use for software/PPT/platform preview.

Geometry:
- Title: `x=60`, `y=90`, size `60`.
- Laptop: `x=500`, `y=150`, `w=650`, `h=420`.
- Paper green/yellow behind laptop.
- Left/right labels may use italic text and thin connector lines.

### 5.19 `g08_quote_yellow_splash`

Use for quotes, expert comments, or key thesis.

Geometry:
- Yellow splash on right or center.
- Quote text: `x=60`, `y=120`, width `950`, size `60..68`, max 3 lines.
- Author/title: `x=60`, `y=500`, size `27` and caption `13`.
- Side phrase right rotated.

Rule:
- Do not use quotation mark icons.

### 5.20 `g08_team_editorial_gallery`

Use for team/advisors/partners.

Geometry:
- Title: `x=60`, `y=95`, size `60`.
- Three image slabs:
  - `x=60`, `450`, `840`
  - `y=210`
  - size around `290 x 250`
  - slight rotations `-3`, `2`, `-2`.
- Name below, size `27`.
- Role below, size `18`.

If no images exist:
- Draw pastel portrait placeholders with initials, not stock icons.

### 5.21 `g08_contact_closing`

Use for thank-you/closing.

Geometry:
- Huge closing title: `x=60`, `y=135`, size `80`.
- Secondary line: `x=470`, `y=135`, size `60`.
- Green or purple ribbon across lower third.
- Contact/details bottom-left.
- Side phrase right rotated.

## 6. Chart Catalog and Theme Restyling

The chart catalog comes from `templates/charts/charts_index.json`. Use it as the full visualization vocabulary.

Selection order:
1. Read the source content and decide the data/relationship semantics.
2. Pick the most accurate `chart_or_diagram` key from the full catalog.
3. Use this cookbook to restyle/redraw that chart in the group-08 visual language.
4. Only use a cookbook recipe as the chart type when it is semantically correct. Do not choose `venn`, `matrix`, `metric`, or `timeline` merely because this cookbook describes them in detail.

Any real catalog key may be used. The suggested mappings below are examples, not limits.

Theme restyling rules:
- Bar/line/area charts: black labels, pastel fills, no grid-heavy dashboard look.
- Matrix/Venn/funnel/timeline: make them editorial and paper-like.
- Tables: avoid dense spreadsheet look; use large serif row labels and thin black rules.
- Strategy frameworks: use irregular pastel regions or large typography, not corporate boxes.
- Architecture/process diagrams: reduce nodes; use pastel paper blocks connected by thin black lines.
- Funnel/Sankey/radar/treemap/waterfall/scatter/heatmap and other catalog visuals: preserve their semantic geometry, then apply pastel paper fills, thin black rules, direct labels, and generous white space.

Suggested mappings:
- Ranking/comparison: `bar_chart`, `horizontal_bar_chart`, `comparison_columns`
- Progress/KPI: `kpi_cards`, `progress_bar_chart`, `bullet_chart`
- Timeline/roadmap: `timeline`, `roadmap_vertical`, `gantt_chart`
- Process/pipeline: `process_flow`, `pipeline_with_stages`, `chevron_process`
- Tradeoff: `matrix_2x2`, `bcg_matrix`
- Overlap: `venn_diagram`, `concentric_circles`
- Strategy: `swot_analysis`, `pest_analysis`, `value_chain`, `porter_five_forces`
- Architecture: `layered_architecture`, `module_composition`, `client_server_flow`
- Team: `team_roster`, `org_chart`
- Tables: `comparison_table`, `feature_matrix_table`, `consulting_table`

## 7. Text Fitting Rules

- This theme prefers fewer, larger words in low-density mode, but it can support medium and high-density pages when the source content needs evidence.
- Do not default every slide to low density solely because the theme is editorial.
- `content_density=low`: poster-like, one claim, max 1 short paragraph or 3 short labels.
- `content_density=medium`: live presentation, 2 to 4 evidence blocks or 4 to 7 short lines of body text.
- `content_density=high`: leave-behind / technical evidence, tighter columns, smaller title, 8 to 12 short lines, thin dividers, no cramped overlap.
- Convert dense content into headings, short editorial paragraphs, numbered moments, or theme-styled tables; do not paste raw long paragraphs.
- Three-column pages: each column may use one headline plus one or two short evidence lines, not only an italic note when details matter.
- Metric pages: show real numbers plus concise context labels.
- Do not go below `13px`.
- Do not cram long Chinese paragraphs into a serif display page.

## 8. SVG Safety Contract

Allowed:
- `path`, `polygon`, `rect`, `circle`, `line`, `polyline`, `text`, `tspan`, `image`.
- `transform="rotate(...)"` on individual shapes/images/text.
- `fill-opacity` on individual circles/paths.

Forbidden:
- `<style>`, `class`, `<foreignObject>`, `clip-path`, `<mask>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, external URLs.
- Gradients and heavy filters.
- Group-level opacity.
- Absolute local image paths.

Root skeleton:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
  ...
</svg>
```

## 9. Spec Lock Snippet

Spec lock should include a cookbook record like:

```json
"cookbook": {
  "id": "figma_group08_pastel_papercut",
  "priority": "hard",
  "required_repeats": ["white canvas", "large serif title", "pastel papercut decoration", "bottom captions", "right-side italic phrase on many pages"],
  "layout_recipes": ["reference examples only; may derive g08_adapted_* layouts when content requires other structures"],
  "chart_policy": "choose chart_or_diagram from the full chart catalog first, then restyle in the group-08 theme",
  "decorative_asset_policy": "draw paper-cutout SVG paths, use project-local images only when source provides them",
  "forbidden_drift": ["modern blue tech cards", "Inter dashboard", "gray block cards", "heavy shadows", "gradient blobs", "random stock photos"]
}
```
