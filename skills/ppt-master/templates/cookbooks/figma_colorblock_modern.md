# Cookbook: figma_colorblock_modern

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
- Requested frames: 35 frames under `145:*`.
- Local evidence:
  - `figma/65CMrCi7opIqi80NPrKFxu/contact_sheet_145_designs.png`
  - `figma/65CMrCi7opIqi80NPrKFxu/capture_manifest_145_designs.json`
  - `figma/65CMrCi7opIqi80NPrKFxu/mcp/145_designs/design_context_samples.md`
  - `figma/65CMrCi7opIqi80NPrKFxu/notes/145_designs/capture_process_and_limitations.md`
- Visual DNA: modern colorblock editorial deck with full-bleed mustard, burnt orange, sage green, and powder blue fields; very light Plus Jakarta Sans titles; high-tracking uppercase labels; hard rectangular slabs; thin monoline outline glyphs; large device/photo placeholders; sparse poster rhythm; and direct numeric list or metric systems.
- Key source frames: `145:1024`, `145:1053`, `145:1114`, `145:1174`, `145:1215`, `145:1238`, `145:1246`, `145:1255`, `145:1314`.

Coordinate note:
- Figma references are `1920 x 1080`.
- PPT Master SVG uses `viewBox="0 0 1280 720"`.
- Geometry below is already scaled by `2/3` unless explicitly labeled as Figma-native.

## 1. Pipeline Role

### 1.1 Design/spec stage

When generating `design_plan.json` and `spec_lock.json`:

- Set `design_plan.cookbook.id` and `spec_lock.cookbook.id` to `figma_colorblock_modern`.
- Treat this cookbook as the hard art-direction system for color fields, typography, page rhythm, device/photo slots, outline glyphs, chart restyling, density, and forbidden drift.
- First decide each slide's semantic job from source content: cover, chapter poster, agenda, TOC, quote, editorial narrative, image evidence, device showcase, metric proof, budget/chart, milestone, team/contact, closing, table, architecture, process, comparison, or dense evidence.
- If a chart, diagram, framework, table, process, architecture visual, or infographic is needed, set `chart_or_diagram` to a real key from `templates/charts/charts_index.json`.
- Put either a matching `cbm_*` reference recipe or a derived `cbm_adapted_*` layout in `layout_family`, `layout_signature`, and `visual_structure`.
- Put a concrete source recipe or motif in `source_recipe_anchor`, such as `cbm_cover_split_image_slab`, `cbm_quote_poster`, `cbm_metrics_colorblock_columns`, or `cbm_adapted_table`.
- Put at least 2 visible art moves from the inventory into `required_art_moves` for every normal slide. Cover, quote, and closing pages may use 1 dominant art move only when the composition is intentionally poster-like.
- Convert tokens into `spec_lock`: palette, typography, grid, colorblock rules, image/device policy, outline glyph policy, chart skin, density modes, adaptation policy, and forbidden drift.
- Do not infer slide semantics from recipe names. Recipes are examples of how this theme renders structures; source content and chart catalog still choose the structure.

### 1.2 SVG stage

When generating SVG:

- Follow `spec_lock` first. If `spec_lock` is incomplete, fall back to this cookbook.
- Build the selected `layout_family` visibly. If it is a named `cbm_*` recipe, use the corresponding geometry. If it is `cbm_adapted_*`, keep this theme's flat color fields, Plus Jakarta typography, hard rectangles, monoline glyphs, large media/device slots, and high-tracking labels.
- If `chart_or_diagram` names a catalog key, preserve that chart's semantic geometry and restyle it in this theme.
- Use project-local images when supplied. If no image exists for an image/device slot, draw a flat placeholder or checker screen region and label it briefly.
- Use flat solid fills. Do not introduce gradients, shadows, glass panels, rounded card systems, bokeh, or decorative blobs.

## 2. Global Tokens

Canvas:
- SVG root: `width="1280" height="720" viewBox="0 0 1280 720"`.
- Figma reference: `1920 x 1080`.
- Scale factor: `0.6667`.

Color tokens:
- `black`: `#000000`
- `white`: `#FFFFFF`
- `green`: `#465E3A`
- `yellow`: `#EAB855`
- `blue`: `#8BA7BF`
- `orange`: `#D96B2C`
- `device_gray`: `#D8D8D8`
- `placeholder_light`: `#F5F5F5`
- `placeholder_mid`: `#CFCFCF`

Semantic color roles:
- `green`: serious base, cover/closing/quote root, high-contrast field.
- `yellow`: warm keynote base, agenda, chart base, device poster, highlight rail.
- `blue`: calm information field, TOC, device inset, team band, evidence background.
- `orange`: energetic chapter, quote root, contact/team root, strong contrast block.
- `black`: primary text and monoline glyphs on yellow, blue, and orange.
- `white`: primary text on green and selected dark image/photo areas.

Color use rules:
- Every normal page should be dominated by 1 large color field and usually show 1 or 2 secondary color fields.
- Use the four brand fields in large slabs, not as tiny accents.
- Avoid extra hues. For charts with many categories, use tints of the four fields plus direct labels.
- Do not soften the palette into pastel beige, slate, purple, or default blue tech styling.

Typography:
- Display/title stack: `Plus Jakarta Sans, Microsoft YaHei, PingFang SC, Arial, sans-serif`.
- Body stack: `Plus Jakarta Sans, Microsoft YaHei, PingFang SC, Arial, sans-serif`.
- Dense fallback: `Microsoft YaHei, PingFang SC, Arial, sans-serif` for CJK-heavy pages.

Scaled type ramp:
- Closing title: `160`, Light, line-height `1.0`, letter spacing `0`.
- Cover/title/subtitle poster: `64`, Light, line-height `1.0`, letter spacing `0`.
- Headline: `48`, Regular, line-height `1.0`, uppercase when source uses uppercase.
- Subheadline large: `53`, Light, line-height `1.0`, letter spacing about `0.7`.
- Uppercase label/name: `32`, Medium, line-height `1.0`, letter spacing about `3.2`.
- Body: `23`, Regular, line-height `1.1`, letter spacing about `0.23`.
- Dense body: `15`, Regular, line-height `1.05..1.15`.
- Small label/caption: `11..13`, Medium or Regular, uppercase, letter spacing `1.0..2.0`.
- Chart/table body: `12..16`, Regular, line-height `1.1..1.2`.

Typography rules:
- Titles are intentionally light, not bold.
- Large titles often sit close to the top-left or bottom-left edge at `x=33..38`, `y=33..57`.
- Labels and names are uppercase with wide tracking. Do not apply wide tracking to long CJK text; use normal tracking for readability.
- Do not use serif type in this theme.
- Do not replace the light display titles with bold sans-serif unless the content is a compact table heading.

Shape language:
- Hard, flat rectangles with `rx=0` for color fields and information blocks.
- Device frames may use rounded rectangles because the device silhouette requires them.
- Contact cards and app mockups may use small radii if inherited from the device/app screenshot, but page-level blocks stay sharp.
- Monoline outline glyphs use `stroke-width=1.5..2`, no fill, and large simple geometry.
- No shadows, gradients, bevels, or glass effects.

Spacing and grid:
- Outer field margin from Figma: `50..56` -> PPT `33..38`.
- Large inset panel: `x=38`, `y=33`, `w=1206`, `h=653`.
- Standard title origin: `x=33..38`, `y=33..57`.
- Wide title width: `w=1180..1213`.
- Dominant media/device zone usually starts at `x=302..606` and may crop to the right.
- Wide team/evidence band: `x=33`, `y=271`, `w=1223`, `h=416`.
- Agenda/list right column begins around `x=620` for numbers and `x=754` for labels.
- Prefer large areas and edge alignment over many small cards.

## 3. Decorative / Asset System

This theme is decorative through color fields, media slabs, and monoline glyphs. It does not use ornamental backgrounds.

Source-native art moves:
- `full_bleed_colorblock`: one of the four brand colors fills the entire canvas.
- `inset_poster_slab`: a second large color panel inset about `33..38` from the canvas edge.
- `oversized_light_type`: huge Plus Jakarta Sans Light title, quote, metric, or closing phrase.
- `tracked_uppercase_label`: Medium uppercase labels/names with wide tracking.
- `hard_media_slab`: rectangular image or device frame used as the main visual object, often cropped or offset.
- `monoline_outline_glyph`: thin outlined quote mark, chair-like mark, arrow, or abstract line icon, no fill.
- `colorblock_metric_mosaic`: large numeric/statistical blocks in orange, green, blue, and yellow.
- `device_screen_placeholder`: laptop/phone frame with checker or inserted screen area.
- `edge_anchored_image`: small image placed near a corner or edge as a compositional counterweight.

Design-plan usage:
- Put concrete anchors like `cbm_quote_poster`, `cbm_phone_showcase`, or `cbm_colorblock_metric_mosaic` in `source_recipe_anchor`.
- Put 2+ items from the art-move inventory in `required_art_moves` for normal slides.
- Use `cbm_adapted_*` names when the semantic structure is not one of the reference recipes.
- Do not use generic anchors like `dashboard`, `matrix`, or `timeline` without a `cbm_*` adapted prefix and explicit art moves.

Reusable SVG motifs:

```xml
<!-- full bleed color field -->
<rect x="0" y="0" width="1280" height="720" fill="#465E3A"/>

<!-- inset poster slab -->
<rect x="38" y="33" width="1206" height="653" fill="#8BA7BF"/>

<!-- cover yellow rail -->
<rect x="988" y="33" width="255" height="653" fill="#EAB855"/>

<!-- monoline outline glyph placeholder -->
<path d="M1030 86 L1138 86 L1174 242 L1085 242 L1056 164 L1030 164 Z" fill="none" stroke="#000000" stroke-width="2"/>

<!-- colorblock metric column -->
<rect x="431" y="241" width="420" height="446" fill="#465E3A"/>
<text x="460" y="344" font-family="Plus Jakarta Sans, Microsoft YaHei, sans-serif" font-size="64" font-weight="300" fill="#FFFFFF">231K</text>

<!-- checker placeholder for inserted device screen -->
<rect x="462" y="160" width="356" height="395" fill="#F5F5F5" stroke="#000000" stroke-width="2" rx="24"/>
<path d="M462 200 H818 M462 240 H818 M462 280 H818" stroke="#E5E5E5" stroke-width="1"/>
```

Image treatment:
- Use source or project-local images only when provided.
- Images are rectangular slabs, often grayscale or low-saturation.
- Large device mockups may intentionally crop off-canvas.
- If no image exists, use a neutral checker screen, pale placeholder, or solid brand-color block with a short label.
- Do not invent unrelated stock imagery.

Outline glyph treatment:
- Recreate Figma vector glyphs as simple `<path>`, `<polyline>`, or `<line>` primitives.
- Use stroke only, usually black on yellow/blue/orange and white on green.
- Keep glyphs large and sparse. Do not replace them with emoji or filled icons.

## 4. Reference Layout Recipes

These recipe IDs are teaching examples and named shortcuts, not an exhaustive layout list.

Use a listed ID when content naturally matches it. If content needs another structure, derive `cbm_adapted_<semantic_structure>` while preserving this theme's visual grammar.

Reference recipes:
- `cbm_cover_split_image_slab`
- `cbm_chapter_image_poster`
- `cbm_agenda_numeric_index`
- `cbm_toc_blue_index`
- `cbm_quote_poster`
- `cbm_editorial_text_glyph`
- `cbm_icon_text_grid`
- `cbm_laptop_showcase`
- `cbm_phone_showcase`
- `cbm_image_evidence_strip`
- `cbm_metrics_colorblock_columns`
- `cbm_budget_bar_columns`
- `cbm_milestone_timeline`
- `cbm_team_colorblock_roster`
- `cbm_contact_cta`
- `cbm_closing_dark_green`
- `cbm_adapted_table`
- `cbm_adapted_chart`
- `cbm_adapted_architecture`
- `cbm_adapted_comparison`

Recipe art-move map:
- `cbm_cover_split_image_slab`: `full_bleed_colorblock`, `oversized_light_type`, `hard_media_slab`, `inset_poster_slab`.
- `cbm_chapter_image_poster`: `full_bleed_colorblock`, `hard_media_slab`, `tracked_uppercase_label`, `edge_anchored_image`.
- `cbm_agenda_numeric_index`: `full_bleed_colorblock`, `oversized_light_type`, `tracked_uppercase_label`, `hard_media_slab`.
- `cbm_toc_blue_index`: `full_bleed_colorblock`, `monoline_outline_glyph`, `oversized_light_type`, numeric right column.
- `cbm_quote_poster`: `inset_poster_slab`, `oversized_light_type`, `monoline_outline_glyph`, `tracked_uppercase_label`.
- `cbm_editorial_text_glyph`: `full_bleed_colorblock`, `oversized_light_type`, `monoline_outline_glyph`, compact body block.
- `cbm_icon_text_grid`: `full_bleed_colorblock`, `monoline_outline_glyph`, compact body grid, `oversized_light_type`.
- `cbm_laptop_showcase`: `full_bleed_colorblock`, `inset_poster_slab`, `device_screen_placeholder`, `hard_media_slab`.
- `cbm_phone_showcase`: `full_bleed_colorblock`, `inset_poster_slab`, `device_screen_placeholder`, side labels.
- `cbm_image_evidence_strip`: `full_bleed_colorblock`, `hard_media_slab`, `tracked_uppercase_label`, row captions.
- `cbm_metrics_colorblock_columns`: `full_bleed_colorblock`, `colorblock_metric_mosaic`, `oversized_light_type`, body-at-bottom text.
- `cbm_budget_bar_columns`: `full_bleed_colorblock`, staggered `colorblock_metric_mosaic`, `tracked_uppercase_label`, bottom year labels.
- `cbm_milestone_timeline`: `full_bleed_colorblock`, horizontal color strip, year labels, compact body blocks.
- `cbm_team_colorblock_roster`: `full_bleed_colorblock`, `inset_poster_slab`, `hard_media_slab`, `tracked_uppercase_label`.
- `cbm_contact_cta`: `full_bleed_colorblock`, large closing phrase, small contact card, `hard_media_slab`.
- `cbm_closing_dark_green`: `full_bleed_colorblock`, `oversized_light_type`, `edge_anchored_image`.

Forbidden drift:
- Do not use blue or purple gradients.
- Do not use shadowed cards, glassmorphism, neon glows, 3D objects, bokeh, decorative orbs, or generic abstract blobs.
- Do not turn the theme into beige, coffee, slate-blue, or monochrome gray.
- Do not use rounded card grids as the main visual system.
- Do not add icons as filled pictograms; use large monoline outline glyphs or no glyph.
- Do not replace the colorblock palette with a rainbow chart palette.
- Do not make all pages white dashboards. White is support only, not the base identity of this set.

## 5. Recipe Details

### 5.1 `cbm_cover_split_image_slab`

Use for cover, title, product introduction, or theme opener.

Composition:
- Full green background.
- Large white light title top-left.
- Small tracked uppercase subheadline bottom-left.
- Tall image slab near right center.
- Yellow rail on far right, aligned to the image height.

Geometry:
- Background: `rect 0 0 1280 720 fill="#465E3A"`.
- Title: `x=33`, `y=33`, width `537`, size `64`, Light, white, max 4 short lines.
- Subheadline: `x=33`, `y=657`, width `255`, size `32`, Medium, uppercase, tracking `3.2`.
- Image: `x=606`, `y=34`, `w=472`, `h=653`, `preserveAspectRatio="xMidYMid slice"`.
- Yellow rail: `x=988`, `y=33`, `w=255`, `h=653`.

Art moves to preserve:
- `full_bleed_colorblock`
- `oversized_light_type`
- `hard_media_slab`
- `inset_poster_slab`

Text rules:
- Title should be the literal subject or deck title.
- Avoid more than 4 lines. If too long, reduce to `52..56`.

Failure modes:
- Do not center the title.
- Do not add logos or decorative blobs.
- Do not make the image a small thumbnail.

### 5.2 `cbm_chapter_image_poster`

Use for chapter dividers, transition slides, and section title posters.

Composition:
- Orange, yellow, or blue full background.
- One large inner color slab or band.
- Small image centered or edge-aligned.
- Minimal chapter/title text.

Geometry:
- Orange root: `#D96B2C`; optional yellow slab `x=67`, `y=40`, `w=1146`, `h=600`.
- Center image: about `x=460`, `y=170`, `w=360`, `h=260`.
- Chapter label: `x=33..640`, `y=24..680`, size `16..48`, depending whether label is primary or metadata.

Art moves to preserve:
- `full_bleed_colorblock`
- `hard_media_slab`
- `tracked_uppercase_label`

Adaptation rules:
- For section slides without images, replace image with a large monoline glyph and keep the same color field relationship.
- For CJK titles, use a shorter two-line label and avoid wide tracking.

Failure modes:
- Do not overfill with body text.
- Do not add multiple content cards.

### 5.3 `cbm_agenda_numeric_index`

Use for agenda, contents, line-up, or sequence pages.

Composition:
- Yellow full background.
- `AGENDA` or topic label at top-left.
- Right side has large numeric column and large item label column.
- Small image counterweight bottom-left.

Geometry:
- Background `#EAB855`.
- Title: `x=38`, `y=22`, width `498`, size `48`, Regular, uppercase.
- Image: `x=38`, `y=485`, `w=269`, `h=202`.
- Number column: `x=620`, `w=113`, right-aligned, size `53`, Light.
- Item column: `x=754`, `w=464`, size `53`, Light.
- Row y positions: `22`, `108`, `193`, `278`, `364`, `449`, `534`.

Art moves to preserve:
- `full_bleed_colorblock`
- `oversized_light_type`
- numeric right-column rhythm
- `hard_media_slab`

Adaptation rules:
- For 4 or fewer items, increase row spacing and keep large type.
- For 8 to 10 items, reduce row type to `40..44` and keep two-column number/name structure.
- For process content, choose a real process/timeline chart key only if the content requires process semantics; otherwise keep agenda structure.

Failure modes:
- Do not add bullet dots.
- Do not make list rows into cards.

### 5.4 `cbm_toc_blue_index`

Use for table of contents, compact navigation, or two-column index pages.

Composition:
- Blue full background.
- Left title near top-left.
- Large monoline outline glyph near top-right or upper middle.
- Numeric list in two columns on the right half.

Geometry:
- Background `#8BA7BF`.
- Title: `x=38`, `y=32`, width `430`, size `48` or `53`, Light.
- Outline glyph: `x=1018`, `y=30`, `w=180`, `h=220`, stroke white or black.
- List left column x about `860`; list right column x about `1120`; row size `24..32`.

Art moves to preserve:
- `full_bleed_colorblock`
- `monoline_outline_glyph`
- numeric index rhythm

Failure modes:
- Do not create a generic white TOC card.
- Do not use icons for every item.

### 5.5 `cbm_quote_poster`

Use for quotes, principles, thesis statements, and editorial openers.

Composition:
- Orange root with blue inset poster slab, or green root with direct white quote.
- Large light quote text at upper-left.
- Large outline quote glyph near top-right.
- Small tracked author/source line bottom-right.

Geometry:
- Root fill `#D96B2C`.
- Inset slab: `x=38`, `y=33`, `w=1206`, `h=653`, fill `#8BA7BF`.
- Quote: `x=61`, `y=46`, width `771`, size `64`, Light, black.
- Quote glyph: `x=1001`, `y=66`, `w=209`, `h=156`, stroke black.
- Author: right-aligned, `x=1209`, `y=631`, width `502`, size `32`, Medium, uppercase, tracking `3.2`.

Art moves to preserve:
- `inset_poster_slab`
- `oversized_light_type`
- `monoline_outline_glyph`
- `tracked_uppercase_label`

Text rules:
- Quote max 3 lines at `64`; use `52..56` for longer quotes.
- Use body-size attribution only when source is long.

Failure modes:
- Do not add quotation marks as oversized serif punctuation.
- Do not use a card container for the quote.

### 5.6 `cbm_editorial_text_glyph`

Use for narrative explanation, a single claim, or thesis/body pages.

Composition:
- One full-bleed color field.
- Headline or body block in upper-left.
- Optional small image or large outline glyph in a corner.
- Body copy is paragraph-like, not bullet-driven.

Geometry:
- Headline: `x=37`, `y=33`, width `1200`, size `48`, Regular uppercase.
- Story paragraph: `x=37`, `y=216`, width `427`, size `23`, line-height `1.1`.
- Supporting small body blocks: width `320`, size `15`.
- Glyph: `w=110..140`, `h=80..120`, stroke black/white.

Art moves to preserve:
- `full_bleed_colorblock`
- `oversized_light_type`
- `monoline_outline_glyph`

Adaptation rules:
- For dense text, split into 2 to 4 text blocks while keeping one dominant color field and one large glyph.
- For technical evidence, use `cbm_adapted_table` instead of shrinking paragraphs below `11`.

Failure modes:
- Do not paste raw long paragraphs.
- Do not add small decorative icons.

### 5.7 `cbm_icon_text_grid`

Use for four concepts, feature explanations, capabilities, or benefit grids.

Composition:
- Blue full background.
- Large headline across top.
- Left column has one larger narrative paragraph.
- Right two columns hold four glyph-plus-copy clusters.

Geometry:
- Title: `x=37`, `y=33`, width `1209`, size `48`.
- Left paragraph: `x=37`, `y=216`, `w=427`, size `23`.
- Right cluster x positions: `511`, `927`; y positions `224`, `470`.
- Glyph size: `110..135`, stroke `1.5..2`.
- Copy under glyph: `w=320`, size `15`, line-height `1.0..1.1`.

Art moves to preserve:
- `full_bleed_colorblock`
- `monoline_outline_glyph`
- compact body grid
- `oversized_light_type`

Failure modes:
- Do not use filled icon sets.
- Do not put each cluster in a card.

### 5.8 `cbm_laptop_showcase`

Use for software, dashboard, platform, website, generated PPT, or product screen examples.

Composition:
- Green root with blue inset slab, or yellow full page with centered laptop.
- Laptop or screen dominates the right or center.
- Short text block on the left or small labels at the sides.

Geometry:
- Green root plus blue inset: `x=38`, `y=33`, `w=1206`, `h=653`.
- Left title: `x=66`, `y=56`, width `696`, size `53`.
- Left body: `x=66`, `y=381`, width `403`, size `23`, line-height `1.1`.
- Oversized laptop stage: `x=37`, `y=33`, `w=1206`, `h=653`; laptop may crop right.
- Alternative yellow full page laptop: centered device `x=120`, `y=110`, `w=920`, `h=430`.

Image/device rules:
- If project image exists, place it in the screen.
- If not, draw simplified laptop with gray frame and checker screen.
- Keep device large enough to define the page.

Art moves to preserve:
- `full_bleed_colorblock`
- `inset_poster_slab`
- `device_screen_placeholder`
- `hard_media_slab`

Failure modes:
- Do not add a web-app dashboard card around the device.
- Do not shrink the laptop to a small illustration.

### 5.9 `cbm_phone_showcase`

Use for mobile app, interface state, product journey, or screen-by-screen evidence.

Composition:
- Green or blue base.
- Blue or orange inset/device field.
- Large phone frame, sometimes portrait and cropped, sometimes landscape.
- One or two side labels.

Geometry:
- Inset slab: `x=38`, `y=33`, `w=1206`, `h=653`.
- Portrait phone stage: `x=302`, `y=33`, `w=677`, `h=653`.
- Left label: `x=35`, `y=275`, width `321`, size `32`, Medium, uppercase, tracking `3.2`.
- Left body: `x=35`, `y=334`, width `321`, size `23`.
- Right label: `x=925`, `y=520`, width `319`, size `32`.
- Landscape phone variant: centered at `x=463`, `y=210`, `w=356`, `h=180`, with title/label below.

Art moves to preserve:
- `full_bleed_colorblock`
- `inset_poster_slab`
- `device_screen_placeholder`
- `tracked_uppercase_label`

Failure modes:
- Do not surround phone annotations with cards.
- Do not use generic phone icons instead of a device frame.

### 5.10 `cbm_image_evidence_strip`

Use for three comparable images, case studies, proofs, screenshots, or examples.

Composition:
- Blue full background.
- Title top-left.
- Three equal image slabs in a horizontal strip.
- Caption label and one short body below each image.

Geometry:
- Title: `x=33`, `y=33`, size `48..64`.
- Image row: `x=38`, `y=274`, `w=1180`, `h=198`.
- Three image slots: `x=38`, `x=348`, `x=658` or use equal 3-column slots with `w=300..360`.
- Label: size `32`, Medium, uppercase, tracking `3.2`.
- Body: size `13..16`, width `240..320`.

Art moves to preserve:
- `full_bleed_colorblock`
- `hard_media_slab`
- `tracked_uppercase_label`

Failure modes:
- Do not add drop shadows.
- Do not use rounded photo cards.

### 5.11 `cbm_metrics_colorblock_columns`

Use for three KPIs, proof points, quantified outcomes, or pillar metrics.

Composition:
- Yellow root.
- Large title at top-left.
- Three tall bottom color columns: orange, green, blue.
- Metric numbers sit near top of each column; body copy sits near bottom.

Geometry:
- Background `#EAB855`.
- Title: `x=34`, `y=34`, width `1213`, size `64`.
- Column 1: `x=69`, `y=241`, `w=395`, `h=446`, fill orange.
- Column 2: `x=431`, `y=241`, `w=420`, `h=446`, fill green.
- Column 3: `x=851`, `y=241`, `w=394`, `h=446`, fill blue.
- Metric baseline: `y=344`, size `64`, Light.
- Body: `y=489..645`, width `280`, size `23`, line-height `1.1`.

Art moves to preserve:
- `full_bleed_colorblock`
- `colorblock_metric_mosaic`
- `oversized_light_type`

Adaptation rules:
- For 2 metrics, use two wide columns and keep the title large.
- For 4 metrics, use a 2x2 mosaic like `cbm_adapted_chart` or `cbm_adapted_comparison`.
- If there are no numbers, use editorial or comparison layout instead.

Failure modes:
- Do not create small KPI cards.
- Do not put metrics on white cards.

### 5.12 `cbm_budget_bar_columns`

Use for budget, financial allocation, market sizing, sequential values, or simple categorical bars.

Composition:
- Yellow root.
- Large subtitle at top-left.
- Five wide vertical bars aligned near bottom with staggered heights.
- Value labels sit at bar tops; category/year labels sit at bottom.

Geometry:
- Title: `x=34`, `y=34`, size `64`.
- Bar width: `243`; use x positions `269`, `511`, `753`, `995`, and optionally `1237` if an off-canvas crop is desired.
- Bar y and h must be data-driven. Reference heights range `125..448`.
- Value label: centered, size `32`, Medium, tracking `3.2`.
- Category label: centered below bars, size `15..23`.

Art moves to preserve:
- `full_bleed_colorblock`
- staggered `colorblock_metric_mosaic`
- `tracked_uppercase_label`

Chart template mapping:
- Use `bar_chart`, `column_chart`, `stacked_bar_chart`, `waterfall_chart`, or `comparison_table` from the catalog based on data semantics.
- Restyle using wide flat bars, no card container, no heavy axes.

Failure modes:
- Do not use default chart colors.
- Do not add grid-heavy Excel axes unless the data requires precision.

### 5.13 `cbm_milestone_timeline`

Use for roadmap, years, phases, development plan, or major milestones.

Composition:
- Blue or yellow background.
- Large title top-left.
- Horizontal segmented color strip across the middle.
- Years or phase labels arranged around the strip.
- Compact descriptions below or beside each milestone.

Geometry:
- Title: `x=33`, `y=33`, size `48..64`.
- Main strip: `x=432`, `y=342`, `w=634`, `h=12..30` for sparse page; or `x=140`, `y=330`, `w=960`, `h=60` for dense milestone cards.
- Four milestone anchors: `x=432`, `x=613`, `x=793`, `x=974`.
- Year labels: size `32..48`, Light or Regular.
- Body: size `12..16`, width `190..230`.

Art moves to preserve:
- `full_bleed_colorblock`
- horizontal color strip
- large year labels

Chart template mapping:
- Use `timeline`, `roadmap_horizontal`, `gantt_chart`, or related catalog keys when the content is truly temporal.

Failure modes:
- Do not use small circular nodes as the main motif.
- Do not create a generic timeline with arrows and icons.

### 5.14 `cbm_team_colorblock_roster`

Use for team, advisors, partners, contributors, or stakeholder groups.

Composition:
- Orange root.
- Large title top-left.
- Wide blue band across lower two-thirds.
- Four image slabs across the band.
- Uppercase names and compact roles below.

Geometry:
- Title: `x=33`, `y=33`, width `1223`, size `64`.
- Blue band: `x=33`, `y=271`, `w=1223`, `h=416`.
- Image slots:
  - `x=33`, `w=301`
  - `x=335`, `w=305`
  - `x=639`, `w=307`
  - `x=947`, `w=309`
  - all `y=271`, `h=198`
- Names: y around `482`, size `32`, Medium, uppercase, tracking `3.2`.
- Role/title: y around `645`, size `15..23`.

Art moves to preserve:
- `full_bleed_colorblock`
- `inset_poster_slab`
- `hard_media_slab`
- `tracked_uppercase_label`

Adaptation rules:
- For 1 person, use `cbm_contact_cta` or a single large portrait variant.
- For 2 people, use two wide image columns inside the blue band.
- For more than 4 people, use two rows but keep the blue band and large title.

Failure modes:
- Do not use circular avatars.
- Do not use profile cards with shadows.

### 5.15 `cbm_contact_cta`

Use for contact, keep-in-touch, feedback, or Q&A lead-in.

Composition:
- Blue or green root.
- Large orange/yellow contact slab.
- One small white contact card or form preview.
- Oversized call-to-action phrase anchored at bottom or side.

Geometry:
- Orange slab: `x=33..860`, `y=33..560`, `w=500..620`, `h=500..650`.
- Contact card: `w=260..360`, `h=90..140`, small radius allowed inside app/form card only.
- CTA phrase: size `53..64`, Light, bottom-right or bottom-left.

Art moves to preserve:
- `full_bleed_colorblock`
- `inset_poster_slab`
- `oversized_light_type`
- small UI/contact card

Failure modes:
- Do not turn the page into a generic form UI.
- Do not use social media icon rows unless source content supplies them.

### 5.16 `cbm_closing_dark_green`

Use for thank-you, Q&A, final discussion, and closing title pages.

Composition:
- Full green background.
- Large white closing phrase at bottom-left.
- Image slab at upper-right.

Geometry:
- Background `#465E3A`.
- Closing title: `x=33`, `y=527`, width `1213`, size `160`, Light, white.
- Image: `x=696`, `y=34`, `w=547`, `h=411`.

Art moves to preserve:
- `full_bleed_colorblock`
- `oversized_light_type`
- `edge_anchored_image`

Failure modes:
- Do not center the closing text.
- Do not add footer chrome.

### 5.17 `cbm_adapted_table`

Use for high-density evidence, comparisons, feature matrices, requirements, or financial line items.

Composition:
- Choose one brand field as the page root.
- Use large table rows as color fields, not a white spreadsheet card.
- Header may be a full-width color strip.
- Maintain one oversized title or large label.

Geometry:
- Title: `x=33`, `y=33`, size `48..64`.
- Table area: `x=33`, `y=150`, `w=1214`, `h=500`.
- Header height: `42..58`.
- Row height: `42..72`.
- Use thin rules only when color boundaries are not enough.
- Cell text: `12..16`, line-height `1.15`.

Art moves to preserve:
- `full_bleed_colorblock`
- colorblock rows or columns
- `tracked_uppercase_label`

Chart template mapping:
- Use `comparison_table`, `feature_matrix_table`, `consulting_table`, or a related catalog table key.

Failure modes:
- Do not create small rounded table cards.
- Do not use default gray table theme.

### 5.18 `cbm_adapted_chart`

Use for any real data chart selected from the catalog.

Composition:
- Plot directly on the colored canvas or inside one large color field.
- Use flat brand-color marks.
- Use direct labels instead of legends when possible.
- Do not put charts inside white dashboard cards.

Restyling rules:
- Bar/column: broad flat bars in orange, green, blue, and yellow; minimal axis; value labels in Plus Jakarta Medium.
- Line/area: green or black line, yellow or blue area, direct point labels.
- Scatter/bubble: black or green points with orange/yellow highlights.
- Heatmap/treemap: four-color tonal grid with black/white contrast labels.
- Waterfall: orange/yellow positive moves, blue/green totals, black labels.
- Funnel/sankey: flat blocks or bands in the four brand colors, no gradients.
- Radar: green/black stroke, pale blue/yellow fill if needed.

Required chart policy:
- Choose chart semantics from the full chart catalog first.
- Then restyle to this theme.
- Do not choose a metric/bar/timeline layout merely because this cookbook documents it.

### 5.19 `cbm_adapted_architecture`

Use for systems, process flows, technical architecture, and module diagrams.

Composition:
- Use large color fields as system layers.
- Nodes are sharp rectangles or text-only labels.
- Use monoline connectors and outline glyph grammar.

Geometry:
- Layer fields: height `90..170`, full width or half width.
- Node rectangles: `rx=0`, fill brand color, stroke black/white as needed.
- Connector lines: `stroke-width=1.5..2`, arrowheads as simple paths.
- Node title: uppercase label size `16..24`, tracking `1..2`.
- Node body: `12..16`.

Failure modes:
- Do not use cloud/server pictograms or glossy blocks.
- Do not use gradient connector ribbons.

## 6. Chart Catalog and Theme Restyling

The chart catalog comes from `templates/charts/charts_index.json`. Use it as the complete visualization vocabulary.

Selection order:
1. Read source content and decide data/relationship semantics.
2. Pick the most accurate `chart_or_diagram` key from the full catalog.
3. Preserve that chart/diagram's semantic geometry.
4. Restyle/redraw it in `figma_colorblock_modern`.

Any real catalog key may be used. Suggested mappings below are examples, not limits.

Suggested mappings:
- Agenda/TOC: no chart key unless content is a process.
- Metrics: `kpi_cards`, `metric_tiles`, `bar_chart`, `bullet_chart`, selected by semantics.
- Budget/finance: `column_chart`, `bar_chart`, `stacked_bar_chart`, `waterfall_chart`, `comparison_table`.
- Timeline: `timeline`, `roadmap_horizontal`, `gantt_chart`.
- Comparison/matrix: `comparison_columns`, `feature_matrix_table`, `matrix_2x2`.
- Team/org: `team_roster`, `org_chart`.
- Architecture/process: `process_flow`, `layered_architecture`, `client_server_flow`, `swimlane_process`.
- Funnel/sankey/radar/treemap/scatter/heatmap: allowed when the source content calls for those semantics.

Theme restyling rules:
- Use Plus Jakarta Sans for all labels and values.
- Use the four brand colors as large marks, not tiny accents.
- Keep axes and gridlines sparse. Favor direct labels.
- Use black text on yellow/blue/orange and white text on green when contrast requires.
- Avoid legends when labels can sit directly on marks.
- Do not add chart cards, shadows, or default multicolor palettes.

## 7. Density and Text Fitting

This theme supports low, medium, and high density, but its identity relies on large color fields.

`content_density=low`:
- Use for cover, chapter posters, quotes, closing, single CTA, or one dominant metric.
- One large title/quote/image/device object.
- Body maximum: one short paragraph or 2 labels.
- Preserve large fields and edge alignment.

`content_density=medium`:
- Use for normal presentation pages.
- 2 to 5 content groups.
- Body size `18..23`, line-height `1.1`.
- Use color columns, image strips, device showcases, or icon text grids.

`content_density=high`:
- Use for evidence, tables, technical notes, feature comparisons, dense milestones, or long agendas.
- Title size may reduce to `40..48`.
- Body size may reduce to `11..15`, but never below `10`.
- Use wide colorblock rows/columns, not many tiny cards.
- Retain at least one strong source-native art move: a full field, large title, large glyph, or colorblock mosaic.

Text fitting rules:
- Light title at `64`: max 4 short lines; if longer, reduce to `52..56`.
- Closing title at `160`: max 1 line; if longer, reduce to `110..130` or split intentionally.
- Agenda numbers/items at `53`: max 7 rows; for more rows reduce to `40..44`.
- Uppercase labels at `32`: max 2 short lines; for long CJK labels use `22..26` with normal tracking.
- Body at `23`: max 5 lines in a block; if longer, split into columns or use high-density table.
- Do not overlap edge images, device frames, or bottom titles.
- Summarize raw paragraphs into short claims plus evidence lines.

## 8. SVG / PPT Safety Contract

Allowed:
- `<rect>`, `<line>`, `<path>`, `<circle>`, `<polyline>`, `<polygon>`, `<text>`, `<tspan>`, `<image>`.
- Solid fills and direct strokes.
- `rx` for device frames, phone/laptop screens, and small app/contact cards only.
- Simple transforms on glyphs or device parts when needed.

Forbidden:
- `<style>`, `class`, `<foreignObject>`, `clip-path`, `<mask>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, external URLs.
- Gradients, blurred shadows, filters, glass effects, image masks, group-level opacity.
- Remote Figma MCP asset URLs in final SVG. Use local project images or redraw simple glyphs as SVG primitives.

Root skeleton:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="#465E3A"/>
  <text x="33" y="33" font-family="Plus Jakarta Sans, Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="64" font-weight="300" fill="#FFFFFF">
    <tspan x="33" dy="64">Colorblock</tspan>
  </text>
  ...
</svg>
```

## 9. Spec Lock Snippet

```json
"cookbook": {
  "id": "figma_colorblock_modern",
  "priority": "hard",
  "required_repeats": [
    "1920-to-1280 scaled geometry",
    "Plus Jakarta Sans light titles and regular body",
    "flat four-color colorblock palette",
    "large full-bleed or inset rectangular fields",
    "hard media/device slabs",
    "tracked uppercase labels where appropriate",
    "monoline outline glyphs instead of filled icons"
  ],
  "source_native_art_moves": [
    "full_bleed_colorblock",
    "inset_poster_slab",
    "oversized_light_type",
    "tracked_uppercase_label",
    "hard_media_slab",
    "monoline_outline_glyph",
    "colorblock_metric_mosaic",
    "device_screen_placeholder",
    "edge_anchored_image"
  ],
  "layout_recipes": [
    "reference examples only; may derive cbm_adapted_* layouts when content requires other structures"
  ],
  "adaptation_policy": "derive colorblock-modern compatible layouts from source semantics while keeping flat fields, light typography, large media/device or glyph structure, and 2+ source-native art moves per normal slide",
  "under_fidelity_checks": [
    "Every normal slide carries 2+ Colorblock Modern art moves",
    "A viewer can recognize the four-color colorblock Figma source without seeing this cookbook name",
    "Density adaptation preserves field geometry and typography, not only palette"
  ],
  "chart_catalog_precedence": "choose chart_or_diagram from the full catalog first, then redraw/restyle in figma_colorblock_modern",
  "decorative_asset_policy": "redraw outline glyphs as SVG primitives; use project-local media for images/devices; draw checker placeholders for missing screens",
  "forbidden_drift": [
    "blue or purple gradients",
    "shadowed cards",
    "glassmorphism",
    "decorative blobs/orbs",
    "filled icon sets",
    "generic SaaS dashboards",
    "white card grid layouts",
    "remote Figma asset URLs"
  ]
},
"chart_rules": {
  "catalog_source": "templates/charts/charts_index.json",
  "selected_templates": [],
  "selection_policy": "choose real catalog keys by content semantics first, then redraw/restyle in cookbook theme",
  "style": "flat colorblock chart skin with broad orange/green/blue/yellow marks, Plus Jakarta labels, sparse axes, direct annotations, and no chart card container"
}
```

## 10. QA Checklist

- Cookbook id appears in `design_plan.cookbook.id` and `spec_lock.cookbook.id`.
- Normal content pages use the four-color colorblock system, not generic white slides.
- Titles use Plus Jakarta Sans Light or configured sans fallback.
- Body, labels, chart labels, tables, and annotations use Plus Jakarta Sans or configured CJK-safe fallback.
- Large titles, images, devices, or glyphs dominate the page; small cards do not.
- `design_plan.slides[*].source_recipe_anchor` uses concrete `cbm_*` recipes or motif anchors.
- Normal slides carry 2+ `required_art_moves` from this cookbook.
- Density adaptation preserves color field geometry, edge alignment, and light typography.
- A viewer can recognize the Colorblock Modern reference without seeing the cookbook name.
- Dense table/evidence pages remain possible without text overlap.
- Charts use real catalog semantics before cookbook restyling.
- SVG contains no external Figma URLs, `<style>`, `class`, `clip-path`, `mask`, `rgba()`, or unsupported effects.
- Adjacent pages vary between green, yellow, blue, and orange fields without becoming random.
