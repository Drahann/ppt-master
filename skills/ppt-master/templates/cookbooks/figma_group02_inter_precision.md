# Cookbook: figma_group02_inter_precision

Priority: hard theme system. This cookbook is not inspiration. It is a reusable design system that must be converted into `design_plan.json`, `spec_lock.json`, and per-slide SVG decisions.

Reference set:
- Source folder: `W:\3spring\figma-slides\group-02`
- Visual DNA: Inter Bold/Regular, white canvas, black typography, neutral gray panels, large quiet spacing, exact editorial grid, minimal decoration, device/photo/avatar media slots.
- Key source slides: `2:288`, `2:298`, `2:306`, `2:359`, `2:419`, `2:433`, `2:444`, `2:460`, `2:496`, `2:525`, `2:539`, `2:556`, `2:630`, `2:641`, `2:646`, `2:693`.

## 1. Pipeline Role

### 1.1 Design/spec stage

When generating `design_plan.json` and `spec_lock.json`, do all of the following:

- Set the deck theme to `figma_group02_inter_precision`.
- Put this cookbook id in `design_plan.cookbook.id` and `spec_lock.cookbook.id`.
- Use the layout recipe IDs in this cookbook as the allowed `layout_family` vocabulary.
- For every slide, choose exactly one primary recipe ID and write it into:
  - `layout_family`
  - `layout_signature`
  - `visual_structure`
  - `visual_guidance`
- Do not leave layout descriptions generic. Bad: `two column layout`. Good: `g02_metric_2x2_left_explainer`.
- Materialize fixed tokens in `spec_lock`: colors, typography, spacing, chrome, shape language, card recipes, media policy, chart template mapping, forbidden drift.
- The SVG stage should not have to infer the theme from prose. Spec lock must carry the executable theme.

### 1.2 SVG stage

When generating an SVG page:

- Follow the current slide recipe from `design_plan.json`.
- If the recipe gives dimensions, use them unless the slide would overflow.
- Do not invent new card styles, shadows, gradients, colored header bars, or decorative blobs.
- If text is long, compress it into the recipe's allowed text slots.
- Every content page must include the micro-chrome defined below.

## 2. Global Tokens

Canvas:
- `viewBox="0 0 1280 720"`
- The Figma reference is `1920 x 1080`; all coordinates below are already scaled to `1280 x 720`.

Color tokens:
- `bg`: `#FFFFFF`
- `text`: `#000000`
- `text_secondary`: `#4D4D4D`
- `text_muted`: `#7A7A7A`
- `panel`: `#CFCFCF`
- `panel_light`: `#E7E7E7`
- `border`: `#CFCFCF`
- `rule`: `#BDBDBD`
- `inverse_text`: `#FFFFFF`
- `primary`: `#000000`
- `accent`: `#CFCFCF`
- Optional data highlight only when needed: `#2569ED`

Important color rule:
- This is a monochrome editorial system, not a blue technology deck.
- Do not force the old default blue system unless the slide is explicitly a data highlight.
- Most slides should use only white, black, and gray.

Typography:
- Use this exact SVG stack:
  - `font-family="Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif"`
- PPT-safe note:
  - `Inter` can lead the stack for SVG preview. PPT export may map to installed/fallback fonts.
  - Chinese text must remain readable with `Microsoft YaHei` or `PingFang SC`.

Scaled type ramp:
- Cover title: `64`, weight `700`, line-height `1.2`
- Cover body: `24`, weight `400`, line-height `1.4`
- Section title: `64`, weight `700`, line-height `1.2`
- Page title H2: `32`, weight `700`, line-height `1.2`
- Block title H3: `24`, weight `700`, line-height `1.32`
- Body large: `20`, weight `400`, line-height `1.36`
- Body regular: `16`, weight `400`, line-height `1.34`
- Timeline subtitle: `19`, weight `500`, line-height `27`
- Funnel label: `16`, weight `600`
- Metric number: `40` or `64`, weight `700`
- Footer/header chrome: `10` or `11`, weight `400`

Letter spacing:
- Keep `letter-spacing="0"`. The Figma export uses slight negative tracking, but this pipeline should avoid negative spacing for CJK/PPT stability.

Shape language:
- Cards: `rx="11"` for the large gray-card recipe, `rx="8"` for small utility cards.
- Shadow: none.
- Stroke: only when needed, `stroke="#CFCFCF"`, `stroke-width="1"`.
- Dividers and timeline rules: `stroke="#BDBDBD"`, `stroke-width="1.5"` or `2`.

Spacing:
- Outer margin: `85`
- Content top for title-led pages: `85`
- Content top after title: `180` to `205`
- Column gutter: `32` or `43`
- Text block internal gap: `11` or `16`
- Card internal padding: `32`

## 3. Fixed Micro-Chrome

The Figma reference is nearly chrome-free, but this project needs stable page identity. Use micro-chrome so the slide still looks like the reference theme.

Apply to every non-cover, non-closing content page:

```xml
<g id="deck-chrome">
  <text x="85" y="38" font-family="Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="10" font-weight="600" fill="#7A7A7A">SECTION_LABEL</text>
  <text x="1195" y="38" text-anchor="end" font-family="Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="10" font-weight="400" fill="#7A7A7A">P02 / 18</text>
</g>
```

Rules:
- No footer bar.
- No colored top strip.
- No large logo unless the source explicitly provides one.
- Chrome must never compete with the main page title.
- If the slide is a full image/device slide, keep only the top-right page number.

Cover and closing:
- No mandatory chrome.
- Put date/organization/project metadata at bottom-left if needed, `x=85`, `y=645..672`, `font-size=12`, fill `#7A7A7A`.

## 4. Allowed Layout Recipe Vocabulary

Design plan must choose from these IDs:

- `g02_cover_left_title`
- `g02_section_center`
- `g02_section_left_description`
- `g02_section_bottom_title`
- `g02_highlight_left_right`
- `g02_simple_list_left_title_three_blocks`
- `g02_text_grid_three_columns`
- `g02_text_grid_four_columns`
- `g02_principles_three_gray_cards`
- `g02_image_left_text_right`
- `g02_image_three_with_captions`
- `g02_metric_single_big_number`
- `g02_metric_three_rows`
- `g02_metric_three_columns`
- `g02_metric_2x2_left_explainer`
- `g02_timeline_five_milestones`
- `g02_overlap_circles`
- `g02_matrix_2x2_left_explainer`
- `g02_venn_left_explainer`
- `g02_funnel_left_explainer`
- `g02_device_phone_left_explainer`
- `g02_device_phone_gallery`
- `g02_device_desktop_left_explainer`
- `g02_quote_single_avatar`
- `g02_quote_three_cards`
- `g02_quote_two_column_text`
- `g02_team_roster`
- `g02_closing_centered`

Forbidden layout drift:
- Do not use generic dashboard cards when a recipe exists.
- Do not turn the theme into McKinsey/consulting blue.
- Do not add gradient blobs or decorative abstract shapes.
- Do not use colored card header bars. This theme's card identity is gray block + black typography, not header bars.
- Do not use heavy shadows.
- Do not place all pages into the same two-column layout.

## 5. Recipe Details

### 5.1 `g02_cover_left_title`

Use for the cover.

Geometry:
- Text group: `x=85`, `y≈300`, `width=800`
- Title: `font-size=64`, `font-weight=700`, max 2 lines
- Body/subtitle: `font-size=24`, max 2 lines, starts `32` below title
- Optional metadata: bottom-left `x=85`, `y=650`

SVG skeleton:

```xml
<rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
<text x="85" y="310" font-family="Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="64" font-weight="700" fill="#000000">
  <tspan x="85" dy="0">主标题第一行</tspan>
  <tspan x="85" dy="77">主标题第二行</tspan>
</text>
<text x="85" y="500" font-family="Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" fill="#4D4D4D">
  <tspan x="85" dy="0">副标题或一句价值说明</tspan>
</text>
```

Do:
- Make the title the main visual object.
- Keep empty space. Do not fill the right side with random illustrations.

### 5.2 `g02_section_center`

Use for chapter dividers or section openers.

Geometry:
- Center text block width `800`, centered at `x=640`, `y≈360`.
- Title `64`, weight `700`.
- Optional subtitle `24`, y gap `24`.

Do not add cards, charts, or icons.

### 5.3 `g02_section_left_description`

Use when the section needs one sentence of explanation.

Geometry:
- Block: `x=85`, `y≈280`, `width=800`
- Title `64`
- Description `24`, starts `32` below title.

### 5.4 `g02_highlight_left_right`

Use for one contrast or one key idea with explanation.

Geometry:
- Left headline: `x=85`, `y≈330`, `width=440`, `font-size=40`
- Right body: `x=645`, `y≈310`, `width=453`, `font-size=24`

Rule:
- The left side is a short claim.
- The right side is one explanation paragraph, max 5 lines.

### 5.5 `g02_simple_list_left_title_three_blocks`

Use for 3-part explanations.

Geometry:
- Left title: `x=85`, `y≈345`, `width=373`, `font-size=32`
- Right blocks: `x=645`, `width=453`
- Block y positions: `182`, `317`, `452`
- Each block:
  - Title `24`, weight `700`
  - Body `16`, y gap `11`, max 3 lines

No card backgrounds in this recipe.

### 5.6 `g02_text_grid_three_columns`

Use for three benefits, three modules, or three observations.

Geometry:
- Page title: `x=85`, `y=116`, `width=1056`, `font-size=32`
- Columns:
  - `x=85`, `x=469`, `x=853`
  - `y=297`
  - `width=341`
- Column title `24`, body `20`

Rule:
- Body text should be large and sparse.
- No bullets inside these blocks unless the source is inherently list-like.

### 5.7 `g02_text_grid_four_columns`

Use for four compact items.

Geometry:
- Page title: `x=85`, `y=116`, `font-size=32`
- Columns:
  - `x=85`, `x=373`, `x=661`, `x=949`
  - `y=306`
  - `width=245`
- Column title `24`, body `16`

Rule:
- Four-column body copy must be short. If any item needs more than 3 lines, use a 2x2 or 3-column recipe instead.

### 5.8 `g02_principles_three_gray_cards`

This is the main card recipe. Use it for principles, innovations, advantages, or three large modules.

Geometry:
- Page title: `x=85`, `y=116`, `font-size=32`
- Cards:
  - Card 1: `x=85`, `y=183`, `w=341`, `h=452`
  - Card 2: `x=469`, `y=183`, `w=341`, `h=452`
  - Card 3: `x=853`, `y=183`, `w=341`, `h=452`
- Card fill `#CFCFCF`, no stroke, no shadow, `rx=11`.
- Card title: `x=card_x+32`, `y=228`, `font-size=24`, weight `700`, max 2 lines.
- Large bottom statement/body:
  - `x=card_x+32`
  - baseline around `y=560`
  - `font-size=32`
  - weight `700`
  - max 3 lines.

SVG skeleton:

```xml
<rect x="85" y="183" width="341" height="452" rx="11" fill="#CFCFCF"/>
<text x="117" y="228" font-family="Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" font-weight="700" fill="#000000">
  <tspan x="117" dy="0">卡片标题</tspan>
</text>
<text x="117" y="520" font-family="Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="32" font-weight="700" fill="#000000">
  <tspan x="117" dy="0">底部主结论</tspan>
  <tspan x="117" dy="42">第二行</tspan>
</text>
```

Important:
- This card is not a white floating card.
- Do not add colored title strips.
- Do not add icons unless the source explicitly needs them. If icons are used, place small black icons near the card title, not as decorative hero objects.
- Cards should feel heavy, editorial, and block-like.

### 5.9 `g02_metric_single_big_number`

Use when the page has one dominant statistic.

Geometry:
- Title: `x=85`, `y=116`, `font-size=32`
- Metric number: center or left, `font-size=64`, weight `700`
- Description: `font-size=24`, max 3 lines

Rule:
- One number only. Do not add small cards around it.

### 5.10 `g02_metric_three_rows`

Use for three metrics with labels.

Geometry:
- Left title: `x=85`, `y≈350`, `width=386`, `font-size=32`
- Metric number x: `645`, y: `242`, `355`, `469`, `font-size=40`
- Text block x: `776`, y matches number, `width=419`
- Text block title `24`, body `16`

Rule:
- Align all three metric baselines.
- Keep numbers black unless one metric requires a blue highlight.

### 5.11 `g02_metric_three_columns`

Use for three comparable KPIs.

Geometry:
- Page title: `x=85`, `y=116`, `font-size=32`
- Metric blocks:
  - x: `85`, `468`, `853`
  - y: `283`
  - width: `342`
- Number: `font-size=40`, weight `700`
- Description: `font-size=20`, line-height `27`

### 5.12 `g02_metric_2x2_left_explainer`

Use for four supporting numbers plus one explanation.

Geometry:
- Left text block: `x=85`, `y≈288`, `width=386`
- Left title `32`, left body `20`
- Metric grid:
  - column x: `627`, `937`
  - row y: `213`, `389`
  - block width `257`
- Number: `64`, label `24`

### 5.13 `g02_timeline_five_milestones`

Use for history, commits, project stages, optimization process.

Geometry:
- Page title: `x=85`, `y=116`, `font-size=24`
- Horizontal rule: `x1=86`, `x2=1195`, `y=369`, `stroke=#BDBDBD`, `stroke-width=2`
- Milestone x positions: `85`, `307`, `528`, `749`, `971`
- Upper text boxes: y around `228`, with connector down to line.
- Lower text boxes: y around `391`, with connector up to line.
- Text box width: `224`
- Milestone title: `19`, weight `500`
- Milestone body: `16`, max 3 lines

Rule:
- Alternate upper/lower only if 4 or 5 milestones.
- If there are 3 milestones, put all below the line.
- Do not use colored circles; use tiny black/gray nodes or short connector lines.

### 5.14 `g02_matrix_2x2_left_explainer`

Use for two-axis decisions, positioning, risk-value tradeoffs.

Geometry:
- Left text block: `x=85`, `y≈300`, `width=400`
- Matrix area: `x=590`, `y=110`, `w=560`, `h=500`
- Vertical axis line at `x=870`, horizontal line at `y=360`
- Axis labels `font-size=16`
- Quadrant labels `font-size=18`, weight `700`

Rule:
- Do not fill each quadrant with colored cards.
- Use sparse text, labels, and 1px lines.

Chart template mapping:
- If the project chart layer is used, map to `templates/charts/matrix_2x2.svg` and restyle to cookbook colors.

### 5.15 `g02_venn_left_explainer`

Use for two/three capability overlaps.

Geometry:
- Left text block: `x=85`, `y≈300`, `width=373`
- Venn area: `x=506`, `y=131`, `w=689`, `h=459`
- Three-circle version:
  - Circle r `150..170`
  - Centers around `(660,360)`, `(820,360)`, `(740,250)`
- Fill:
  - `#CFCFCF` with opacity `0.65`
  - one circle may be black with opacity `0.82` only if white label is needed.
- Labels `font-size=18..20`, centered.

Rule:
- Intersections should be readable.
- No gradient fills.

Chart template mapping:
- `templates/charts/venn_diagram.svg`

### 5.16 `g02_funnel_left_explainer`

Use for pipelines, filtering, staged conversion, sales/market funnel.

Geometry:
- Left text block: `x=85`, `y≈300`, `width=400`
- Funnel area: `x=608`, `y=127`, `w=587`, `h=467`
- Five layers, gap `3`.
- Layer heights around `90`.
- Use SVG `polygon`, not `mask` or `clip-path`.
- Layer fills alternate `#CFCFCF` and `#D8D8D8`.
- Label centered, `font-size=16`, weight `600`.

Example layer widths:
- Top: `587`
- Second: `500`
- Third: `410`
- Fourth: `315`
- Bottom: `220`

Chart template mapping:
- `templates/charts/funnel_chart.svg`, but the final SVG must remain mask-free.

### 5.17 `g02_image_left_text_right`

Use when source Markdown contains a useful project image or product/photo evidence.

Geometry:
- Left text block: `x=85`, `y≈265`, `width=430`
- Image rectangle: `x=640`, `y=150`, `w=480`, `h=360`
- Image may bleed taller if it is the focal point.
- Add no frame unless contrast is poor.

Media rule:
- Use only project-local images from `Available Project Images JSON`.
- For SVG: `<image href="../images/file.png" x="640" y="150" width="480" height="360" preserveAspectRatio="xMidYMid slice"/>`
- Do not use external URLs or Figma source paths at runtime.

### 5.18 `g02_image_three_with_captions`

Use for three comparable visuals or evidence photos.

Geometry:
- Title: `x=85`, `y=116`
- Image slots:
  - x: `85`, `469`, `853`
  - y: `183`
  - w: `341`
  - h: `301`
- Caption/title below: `y=530`, `font-size=24`
- Caption/body: `y=565`, `font-size=16`

If no real images exist:
- Do not invent photos.
- Use gray image placeholders with short labels only if the slide concept needs visual slots.

### 5.19 `g02_device_phone_left_explainer`

Use for app/product/interface/process examples.

Geometry:
- Left text block: `x=85`, `y≈300`, `width=453`
- Phone mockup area: `x=776`, `y=65`, `w=287`, `h=590`

If device image assets are available in project images:
- Use them as images.

If not available:
- Draw a simplified phone:
  - Outer rect `x=850`, `y=88`, `w=210`, `h=520`, `rx=36`, fill `#F8F8F8`, stroke `#CFCFCF`
  - Screen rect `x=865`, `y=122`, `w=180`, `h=440`, `rx=18`, fill `#FFFFFF`, stroke `#E0E0E0`
  - Notch small rounded rect at top.
  - Inside screen, use 3 to 5 gray/black UI blocks.

Rule:
- Device frame is the decorative object. Do not add extra floating icons.

### 5.20 `g02_device_desktop_left_explainer`

Use for software, web app, platform, dashboard, or generated PPT output preview.

Geometry:
- Left text block: `x=85`, `y≈300`, `width=453`
- Laptop mockup area: `x=596`, `y=85`, `w=720`, `h=500`, may crop off the right edge.

If no laptop asset exists:
- Draw simplified laptop:
  - Screen outer rect `x=610`, `y=120`, `w=620`, `h=390`, `rx=18`, fill `#D9D9D9`
  - Screen inner rect `x=635`, `y=145`, `w=570`, `h=320`, `rx=6`, fill `#FFFFFF`
  - Base trapezoid or rect at `y=510`, fill `#CFCFCF`

### 5.21 `g02_quote_single_avatar`

Use for one testimonial, expert quote, or user voice.

Geometry:
- Avatar circle: `cx=150`, `cy=165`, `r=36`, fill `#CFCFCF` if no image
- Quote text: `x=85`, `y=300`, `width=920`, `font-size=40`, weight `700`, max 3 lines
- Attribution: `x=85`, `y=575`, `font-size=16`, fill `#4D4D4D`

Rule:
- No quotation mark decoration unless subtle.

### 5.22 `g02_quote_three_cards`

Use for three quotes, reviews, or expert comments.

Geometry:
- Title: `x=85`, `y=116`
- Three columns x: `85`, `469`, `853`
- Avatar circle y: `250`
- Quote y: `330`, `font-size=20`
- Attribution y: `565`, `font-size=16`

No gray card background. The white space is the container.

### 5.23 `g02_team_roster`

Use for team/advisors/partners.

Geometry:
- Title: `x=85`, `y=116`, `font-size=32`
- Grid: 5 columns x `85`, `309`, `533`, `757`, `981`; 2 rows y `230`, `455`
- Avatar circle: r `45`, fill `#CFCFCF` or use source avatar image.
- Name `font-size=18`, weight `700`
- Role `font-size=14`, fill `#4D4D4D`

Rule:
- Keep team entries compact and consistent.

## 6. Chart and Diagram Template Mapping

This cookbook gives theme-specific chart preferences, but the full chart vocabulary comes from `templates/charts/charts_index.json`.

Spec stage rule:
- First choose from the full chart catalog when a slide needs a visualization.
- Then apply this cookbook's monochrome Figma group-02 styling.
- `chart_or_diagram` should use the real catalog key, not a cookbook-only nickname.
- Cookbook recipes such as `g02_funnel_left_explainer` define composition and style; chart catalog keys such as `funnel_chart` define the underlying visualization type.

When design_plan sets `chart_or_diagram`, choose from existing project chart templates conceptually:

- Timeline/process: `templates/charts/timeline.svg`, `process_flow.svg`, `pipeline_with_stages.svg`
- Funnel/filter: `templates/charts/funnel_chart.svg`
- Venn/overlap: `templates/charts/venn_diagram.svg`, `concentric_circles.svg`
- Matrix/tradeoff: `templates/charts/matrix_2x2.svg`, `bcg_matrix.svg`
- KPI cards: `templates/charts/kpi_cards.svg`
- Comparison: `templates/charts/comparison_columns.svg`, `comparison_table.svg`
- Team/advisors: `templates/charts/team_roster.svg`, `org_chart.svg`

But:
- Do not import template colors directly.
- Re-render chart visuals in this cookbook's monochrome system.
- Template name guides structure, not palette.
- Project SVG forbiddens still apply: no `clip-path`, no `mask`, no `rgba`, no `<style>`.

## 7. Decorative Asset Policy

This theme's decorative layer is not ornamental. It uses real or plausible media objects:

- Large cropped project images.
- Product/interface screenshots.
- Device mockups.
- Avatar circles.
- Thin timeline/matrix lines.
- Gray image placeholders only when actual images are missing and the layout requires a visual slot.

Allowed decorative assets:
- Project-local image files listed in `Available Project Images JSON`.
- Drawn phone/laptop frames if no device PNG exists.
- Simple avatar circles if no portrait exists.
- Line SVG primitives for annotation, timeline, and matrix.

Forbidden decorative assets:
- Gradient blobs or floating orbs.
- Random abstract illustrations.
- Colored icon confetti.
- Background patterns.
- Heavy photographic overlays behind text.
- Unrelated stock-like images.

Spec lock should record:

```json
"cookbook": {
  "id": "figma_group02_inter_precision",
  "priority": "hard",
  "required_repeats": ["micro-chrome on content pages", "white background", "Inter/YaHei stack", "black/gray palette", "recipe-specific geometry"],
  "layout_recipes": ["g02_cover_left_title", "g02_principles_three_gray_cards", "g02_timeline_five_milestones", "g02_funnel_left_explainer", "g02_venn_left_explainer"],
  "decorative_asset_policy": "real project images, device mockups, avatar circles, and thin lines only",
  "forbidden_drift": ["blue tech default", "colored header card bars", "heavy shadows", "gradient blobs", "generic dashboard cards"]
}
```

## 8. Text Fitting Rules

The recipe is stronger than source prose. If the source text is too long:

- Convert paragraphs into 1 sentence plus 2 to 4 key phrases.
- In card recipes, the bottom statement should be a conclusion, not raw paragraph text.
- In metric recipes, numbers must be real values from source. If no numeric value exists, choose a text-grid or principle-card recipe instead.
- Do not reduce text below `13px`.
- Do not place more than 5 visible text blocks on one slide unless using team roster.

## 9. SVG Construction Rules

Root:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
  ...
</svg>
```

Text:
- Use `<text>` with `<tspan>` for manual line wrapping.
- Escape XML reserved characters.
- Do not use HTML `<span>`.

Groups:
- Use semantic `<g id="...">`.
- Do not use `<g opacity>`.

Images:
- Use project relative image hrefs only.
- Preferred `preserveAspectRatio`:
  - `xMidYMid slice` for photo fills.
  - `xMidYMid meet` for logos/screenshots when cropping would harm meaning.

## 10. Common Failure Corrections

If the model is about to do this:

- "Add blue gradient tech background" -> stop; use white background and black/gray type.
- "Create many small white cards with shadows" -> stop; use the exact gray-card recipe or no cards.
- "Use a generic two-column slide" -> stop; select a named `g02_*` recipe.
- "Put all text in bullets" -> stop; convert into title/body text blocks.
- "Use a chart template color palette" -> stop; keep chart geometry but restyle monochrome.
- "Decorate with abstract shapes" -> stop; use media/device/avatar/line primitives only.
