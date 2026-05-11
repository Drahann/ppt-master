# Cookbook: figma_65cm_default

Priority: hard default-candidate theme system.

Important philosophy:
- This cookbook is an art-directed adaptive grammar, not a layout/chart whitelist or a loose style reference.
- Source content and the full chart catalog decide semantic structure.
- This cookbook decides how that structure is rendered in the theme.
- Named recipes are reference exemplars. Use them when they fit; derive `f65_adapted_*` layouts when content needs another structure.
- Semantic structure may adapt to content; source-native art moves must remain visibly inherited.
- Density may increase, but composition logic cannot collapse into generic cards.

Theme evidence summary:
- Extracted from 29 reference presentation frames.
- Visual DNA: dark pharmaceutical finance analysis deck, Metropolis typography, night radial gradients, Pfizer-blue/Merck-green dual accent grammar, orange emphasis, BBS top mark, giant translucent brand words/numerals, white data-document slabs, dense financial charts/tables, 3D medical objects, team portrait strips, and rounded page-number badges.

## 1. Pipeline Role

### 1.1 Design/spec stage

When generating `design_plan.json` and `spec_lock.json`:

- Set `design_plan.cookbook.id` and `spec_lock.cookbook.id` to `figma_65cm_default`.
- First decide each slide's semantic job from source content.
- If a chart, diagram, framework, table, process, architecture visual, or infographic is needed, set `chart_or_diagram` to a real key from the full chart catalog.
- Use either a matching reference recipe or a derived `f65_adapted_*` layout in `layout_family`, `layout_signature`, and `visual_structure`.
- For every normal slide, write a concrete `source_recipe_anchor` such as `f65_dark_chart_pair`, `f65_glass_card_strategy`, or `f65_financial_document_stack`.
- For every normal slide, put at least two visible art moves in `required_art_moves`.
- Convert tokens into `spec_lock`: typography, colors, spacing, chrome, background gradients, brand/label policy, image policy, chart restyling, density modes, adaptation policy, and forbidden drift.

### 1.2 SVG stage

When generating SVG:

- Use `viewBox="0 0 1280 720"`. Figma is `1920 x 1080`; scale coordinates by `2/3`.
- Follow `spec_lock` first, then this cookbook.
- Build the selected recipe visibly. Do not only copy palette and fonts.
- If `chart_or_diagram` names a catalog key, preserve that chart/diagram's semantic geometry and restyle it in this theme.
- Use source images only when provided or when a local reusable asset is semantically compatible.
- For unrelated source decks, replace literal Pfizer/Merck brand words with source-relevant large ghost words, but preserve the ghost-word behavior.
- Do not drift into generic SaaS dashboard cards, flat corporate blue, or pastel/paper styles.

## 2. Global Tokens

Canvas:
- `viewBox="0 0 1280 720"`.
- Reference scale: Figma `1920 x 1080` to PPT Master `1280 x 720`, multiply Figma coordinates by `0.6667`.

Color tokens:
- `bg_night`: `#0B091E` dominant background.
- `bg_panel`: `#11102E` dark glass panel fill.
- `white`: `#FFFFFF`.
- `off_white`: `#F2F2F2`.
- `pfizer_blue`: `#1E74FB`.
- `pfizer_cyan`: `#0190FF`.
- `deep_brand_blue`: `#2B01BE`.
- `merck_green`: `#007A73`.
- `merck_teal`: `#03AAA1`.
- `orange`: `#FF6400`.
- `yellow_note`: `#FAFF00` only for tiny emphasis.
- `gray_line`: `#898989`, `#BDBDBD`, `#C4C4C4` for financial/document pages.
- `black`: `#000000`.

Color behavior:
- Most pages are dark: `bg_night` plus large radial glow in `pfizer_blue` or `merck_green`.
- Use `orange` for task number, parenthetical marker, emphasized financial/risk keywords, and small numbered bubbles.
- Use blue and green as competing brand/accent systems: left/top Pfizer-like sections lean blue; right/bottom Merck-like sections lean green.
- White tables/charts are allowed and common, but should sit as embedded evidence objects on a dark stage.
- Light financial-document pages may use white/very pale blue backgrounds, but must keep purple/green timeline or numbered bubbles.

Typography:
- Primary SVG stack: `font-family="Metropolis, Montserrat, Inter, Microsoft YaHei, PingFang SC, Arial, sans-serif"`.
- Use `Metropolis` for most title/body/chrome.
- Use `Inter Bold` only for the small BBS/PERFORMANCE MEASUREMENT SYSTEM mark.
- Use `Montserrat` for business-model-canvas boxes.
- Use `Merriweather Black` only for oversized quote marks.

Scaled type ramp for `1280 x 720`:
- Cover title: `72`, weight `700`, uppercase, line-height `0.83`, letter-spacing `0`.
- Cover subtitle/kicker: `16`, weight `700`, accent color.
- Page title: `42`, weight `400`, centered, max 1 line when possible.
- Section/page label: `16`, weight `400`, top-left.
- Body large: `19`, weight `400`.
- Caption under charts: `16`, weight `400`.
- Glass-card title: `13-14`, weight `500`.
- Glass-card body: `9-10`, weight `300`, line-height `1.0`.
- Business canvas title: `12`, Montserrat ExtraBold.
- Business canvas body: `10-11`, Montserrat Regular.
- Giant ghost numerals/words: `180-267`, weight `700`, opacity `0.10-0.18`.
- Page number in corner badge: `18-19`, weight `400`.

Shape language:
- Backgrounds: radial gradients and large flat dark rectangles, not decorative orbs.
- Glass cards: `rx=11`, fill `#11102E` or `#0B0B22`, stroke `#024BDA` or `#007A73`, stroke width `2`, slight vertical fade simulated with a darker top rectangle when needed.
- Data image slabs: white rectangles with `rx=7`, thin green/blue border, optional `filter`-free shadow simulated by a translucent dark rectangle behind the slab.
- Timeline bubbles: circles `r=23` in blue/green/orange/magenta with white two-digit labels.
- Page number badge: circle or shield-like vector at bottom-right, about `61 x 60`, fill `#2B01BE` or gradient-compatible flat blue, white page number.
- Quote mark: huge Merriweather curly quote in green or white at `0.15` to `1.0` opacity.

Spacing:
- Top-left task label: `x=49`, `y=32`.
- Top-right BBS mark: approximately `x=1043`, `y=21`, `w=208`, `h=37`.
- Center title: `x=350..930`, `y=24..64`, depending width.
- Dark chart page content: `x=49`, `y=113`, `w=1240`, `h=560`.
- Footer caption band: `y=632..680`, font `16`.
- Bottom-right page badge: `x=1194`, `y=640`, `w=61`, `h=60`.

## 3. Art Move Inventory

Every normal slide must visibly preserve at least two of these source-native moves:

- `f65_night_radial_stage`: deep navy/purple canvas with large radial blue or green glows.
- `f65_ghost_brand_word`: oversized translucent word, logo shape, numeral, or section glyph behind content.
- `f65_bbs_top_mark`: compact top-right institutional mark plus tiny uppercase label.
- `f65_task_label`: small top-left task/section label.
- `f65_bottom_right_page_badge`: circular or shield-like page number at bottom-right.
- `f65_dual_brand_accent`: blue/green split language used to compare two entities, streams, or alternatives.
- `f65_orange_keyword`: orange highlights for parenthetical section IDs, key words, numeric bubbles, or risk labels.
- `f65_glass_card`: dark rounded panels with blue/green stroke and compact text.
- `f65_white_evidence_slab`: white table/chart/document slab embedded into dark background.
- `f65_3d_medical_object`: floating shield, capsule, molecule, logo, or medical image object.
- `f65_rotated_or_cropped_evidence`: rotated/cropped image slabs and overhanging evidence images.
- `f65_financial_document_stack`: layered financial statement screenshots connected by arrows and year rail.
- `f65_giant_quote_mark`: Merriweather quote punctuation as structural decoration.
- `f65_team_portrait_strip`: black/white portrait crops with giant translucent numbers.

Forbidden drift:
- No beige, pastel, paper-cut, or warm editorial theme.
- No generic gradient blobs/orbs disconnected from the brand stage.
- No light SaaS dashboards unless the recipe is the financial-document page.
- No random stock photos where source or local assets do not justify them.
- No thick decorative shadows. Use subtle dark offset rectangles for depth.
- Do not reuse Pfizer/Merck literal logos for unrelated content.

## 4. Decorative / Asset System

Reusable local assets live in `assets/figma_assets/`.

Asset classes:
- Institutional mark: `bbs_logo_rect_151534.png`, `bbs_logo_round_151534.png`, `orange_bbs_mark.png`.
- Medical/3D objects: `shield_material_1.png`, `shield_material_2.png`, `medical_circle_icon.png`.
- Evidence imagery: `strategic_building_crop_a.png`, `strategic_building_crop_b.png`, `merck_rotated_company_visual.png`.
- Financial evidence: `financial_*` and `financial_approach_*` document stacks.
- Team portrait references: `team_*_portrait.png`.

SVG-safe generated alternatives:
- Prefer primitive reconstructions for large ghost words, cards, circles, rails, tables, and charts.
- Use `<image href="...">` only for downloaded assets or source-provided images. Keep opacity on an enclosing tinted rectangle, not on image nodes.
- Avoid masks, clip-paths, CSS classes, style blocks, rgba, filters, and foreignObject.

Core decorative snippets:

```xml
<rect x="0" y="0" width="1280" height="720" fill="#0B091E"/>
<circle cx="-80" cy="40" r="430" fill="#1E74FB" opacity="0.38"/>
<circle cx="1180" cy="620" r="500" fill="#007A73" opacity="0.25"/>
<text x="52" y="78" font-size="210" font-weight="700" fill="#2B01BE" opacity="0.18">SOURCE</text>
<text x="49" y="48" font-size="16" fill="#FFFFFF">Task 1</text>
<circle cx="1224" cy="674" r="30" fill="#2B01BE"/>
<text x="1224" y="681" text-anchor="middle" font-size="18" fill="#F2F2F2">08</text>
```

Glass card:

```xml
<rect x="64" y="170" width="177" height="287" rx="11" fill="#11102E" stroke="#024BDA" stroke-width="2"/>
<text x="77" y="206" font-size="14" font-weight="500" fill="#FFFFFF">Card title</text>
<text x="77" y="246" font-size="10" fill="#FFFFFF">Compact evidence text</text>
```

White evidence slab:

```xml
<rect x="50" y="116" width="622" height="568" rx="7" fill="#FFFFFF" stroke="#007A73" stroke-width="1"/>
<rect x="56" y="122" width="610" height="28" fill="#007A73"/>
```

## 5. Reference Layout Recipes

These recipe IDs are teaching examples and named shortcuts, not an exhaustive whitelist.

Use a listed ID when content naturally matches it. If content needs another structure, derive `f65_adapted_<semantic_structure>`.

### 5.1 `f65_cover_dual_brand_stage`

Use for: title/cover, major branded opening, project title.

Composition:
- Full dark stage.
- Left/center title block with stacked uppercase title.
- Background split between blue and green radial glows.
- Huge translucent group number or source glyph.
- Right or side area may contain large vertical brand/source word.

Geometry:
- Background fills full canvas.
- Main title around `x=390`, `y=255`, `w=500`, `h=180`, font `72`.
- Kicker at `x=502`, `y=256`, font `16`, accent green/blue.
- Date/organization at bottom center or bottom-left, font `14-18`.
- Ghost numeral around `x=580`, `y=490`, font `200`.

Art moves to preserve:
- `f65_night_radial_stage`
- `f65_ghost_brand_word`
- `f65_dual_brand_accent`

Failure modes:
- Flat black background without glows.
- Centered title with no ghost typography.
- Literal Pfizer/Merck logo on unrelated decks.

### 5.2 `f65_agenda_big_year_steps`

Use for: agenda, process outline, section roadmap.

Composition:
- Large ghost year/range or keyword on lower-left.
- Right-side vertical numbered agenda list in circular badges.
- Optional source logo/glyph near top-left.

Geometry:
- Big year: `x=380`, `y=340`, font `155`, fill `#007A73`.
- Step circles: `cx=860`, `y=135/275/430/580`, radius `33`, fill `#0B0B22` with blue stroke.
- Step copy: `x=955`, width `280`.

Art moves to preserve:
- `f65_ghost_brand_word`
- `f65_orange_keyword`
- `f65_bottom_right_page_badge`

### 5.3 `f65_glass_card_strategy`

Use for: strategy cards, risks, priorities, dense qualitative evidence.

Composition:
- Dark background with ghost brand word.
- Multiple glass cards arranged by semantic relationship.
- Cards use blue stroke for one stream, green stroke for another.
- Floating medical/industry asset may anchor a corner.

Geometry:
- Small card: `w=177`, `h=240..287`, `rx=11`, padding `13`.
- 4-card risk grid: two columns across `x=520..1220`, two rows.
- Text: title `13-15`, body `9-11`, line-height `1.0`.
- Number nodes or circular bullets on left rail when sequence matters.

Art moves to preserve:
- `f65_glass_card`
- `f65_dual_brand_accent`
- `f65_3d_medical_object`
- `f65_orange_keyword`

Adaptation:
- For technical content, use cards for subsystems, risks, modules, or constraints.
- For high density, shrink body text and use two rows of cards rather than adding paragraphs.

### 5.4 `f65_dark_chart_pair`

Use for: ratio analysis, horizontal/vertical analysis, chart comparisons.

Composition:
- Header centered.
- Two large white chart/table slabs, often side-by-side.
- Bottom caption under each slab or single bottom explanation.
- Company/source mark at bottom-left of each slab region.

Geometry:
- Two chart slabs: `x=45`, `y=135`, `w=560`, `h=340`; `x=675`, `y=135`, `w=560`, `h=340`.
- Top mini tables: `x=50`, `y=95`, `w=520`, `h=80`; second at `x=690`.
- Caption: `x=210`, `y=632`, `w=430`, font `16`.
- Header: `x=385`, `y=35`, `w=510`, font `42`.

Art moves to preserve:
- `f65_white_evidence_slab`
- `f65_bbs_top_mark`
- `f65_bottom_right_page_badge`
- `f65_dual_brand_accent`

Chart restyling:
- Keep plot area white.
- Use thin gray grid lines, colored series in blue/green/orange/pink.
- Legends should be tiny and inside top-right or bottom-right of plot.
- If source data is textual rather than numeric, use table or matrix but keep white evidence slab treatment.

### 5.5 `f65_single_large_table_chart`

Use for: one company table plus chart, dense financial statements, detailed evidence page.

Composition:
- One large table/image slab on left or right.
- One chart slab next to it.
- Decorative rotated company visual or medical image below.

Geometry:
- Large table: `x=49`, `y=113`, `w=622`, `h=568`.
- Chart: `x=694`, `y=113`, `w=549`, `h=340`.
- Supporting image: `x=694`, `y=480`, `w=293`, `h=175`, rotated if needed.

Art moves to preserve:
- `f65_white_evidence_slab`
- `f65_rotated_or_cropped_evidence`
- `f65_task_label`

### 5.6 `f65_business_canvas_white_cards`

Use for: business model canvas, capability map, ecosystem map.

Composition:
- Dark background.
- White rectangular canvas modules with Montserrat labels.
- Thin black dividers, small image accents, source label rotated or side-aligned.

Geometry:
- Outer margin `50`.
- Card grid starts `x=75`, `y=110`, with `w≈220`, `h≈160`, gutters `16`.
- Card title font `12`, Montserrat ExtraBold.
- Card body font `10-11`, Montserrat Regular.

Art moves to preserve:
- `f65_white_evidence_slab`
- `f65_task_label`
- `f65_3d_medical_object`

### 5.7 `f65_financial_document_stack`

Use for: methodology, annual report analysis, document workflow, timeline over evidence.

Composition:
- Light or pale background.
- Multiple overlapping financial statements/document screenshots.
- Curved connector lines and numbered bubbles.
- Bottom year rail with purple bar and green label capsule.

Geometry:
- Header image: `x=0`, `y=0`, `w=605`, `h=251`, rounded bottom-right.
- Main document: `x=510`, `y=88`, `w=587`, `h=614`.
- Left document stack: `x=60`, `y=162`, `w=603`, `h=549`.
- Right stack: `x=700`, `y=225`, `w=556`, `h=494`.
- Bottom rail: `x=35`, `y=555`, `w=1192`, `h=55`, `rx=38`, fill `#2B01BE`.
- Center green label: `x=535`, `y=636`, `w=262`, `h=57`, fill `#007A73`.

Art moves to preserve:
- `f65_financial_document_stack`
- `f65_orange_keyword`
- `f65_white_evidence_slab`

Failure modes:
- Turning the page into a generic process diagram with no document stack.
- Removing the year rail.

### 5.8 `f65_insight_text_image_split`

Use for: insights, conclusion evidence, textual interpretation with one large image.

Composition:
- Dark background.
- Left text sections with colored entity labels.
- Right large image/photo crop or evidence image.
- Optional bottom/side logo.

Geometry:
- Main title: `x=49`, `y=140`, font `42`.
- Text blocks: `x=50`, `y=260/460`, width `775`, font `19`.
- Image: `x=820`, `y=90`, `w=450`, `h=600` or right half.

Art moves to preserve:
- `f65_night_radial_stage`
- `f65_dual_brand_accent`
- `f65_rotated_or_cropped_evidence`

### 5.9 `f65_quote_or_declaration`

Use for: plagiarism/declaration, key quote, manifesto, references divider.

Composition:
- Large title in upper center.
- Giant quote mark or ghost numeral.
- Long text block can sit low across width.
- Portrait/image tiles may create depth.

Geometry:
- Title: `x=445`, `y=48`, font `64`.
- Quote mark: `x=60`, `y=360`, font `228`, Merriweather Black.
- Long body: `x=136`, `y=512`, `w=1008`, font `13-18`.

Art moves to preserve:
- `f65_giant_quote_mark`
- `f65_ghost_brand_word`
- `f65_night_radial_stage`

### 5.10 `f65_team_portrait_strip`

Use for: team members, advisors, roles, credits.

Composition:
- Black/dark background.
- Large portrait strips in thirds or quarters.
- Each member gets huge translucent numeral behind portrait.
- First name in orange, surname in white.
- School/company seal may sit between portraits.

Geometry:
- Portrait columns: 3 or 4 equal vertical bands.
- Ghost numeral: font `267`, opacity `0.15`.
- Name: `x` aligned to portrait, `y≈430`, font `26`, two lines.

Art moves to preserve:
- `f65_team_portrait_strip`
- `f65_ghost_brand_word`
- `f65_orange_keyword`

### 5.11 `f65_closing_question_stage`

Use for: closing / thank you / Q&A.

Composition:
- Dark dual-brand stage.
- Large centered uppercase thank-you.
- Huge translucent question mark.
- Bottom special thanks line.
- Optional portrait or logo strip.

Geometry:
- Main title: `x=315`, `y=260`, `w=650`, font `72`, line-height `0.83`.
- Question mark: `x=830`, `y=300`, font `233`, opacity `0.25`.
- Subtitle: `x=415`, `y=390`, font `42`, accent cyan/green.

Art moves to preserve:
- `f65_night_radial_stage`
- `f65_ghost_brand_word`
- `f65_dual_brand_accent`

## 6. Chart Catalog and Theme Restyling

The chart catalog is the full visualization vocabulary.

Selection order:
1. Read source content and decide data/relationship semantics.
2. Pick the most accurate `chart_or_diagram` key from the full catalog.
3. Restyle/redraw that chart in this theme.
4. Do not choose a cookbook chart recipe merely because it is documented here.

Theme restyling:
- Bar/line/area: white plot slab, light gray grid, thin colored lines/bars, tiny legend, bottom caption. Use blue/green/orange/pink series.
- Tables: white background, dark green header row for Merck-like data, blue header row for Pfizer/source A, orange header for source B; compact fonts; thin gray row rules.
- Matrix: dark background with glass cells or white evidence cells depending density; retain ghost brand word behind.
- Timeline: use colored bubbles and rail, with years in white or purple bar.
- Risk/process diagrams: dark glass cards connected by thin blue/green lines; use icon chips or local 3D assets sparingly.
- Architecture diagrams: preserve semantic topology, but render nodes as dark glass modules with blue/green strokes and orange callouts.
- Team/org charts: portrait strip if photos exist; otherwise use dark bands with ghost numerals and orange names.

## 7. Density and Text Fitting

- `content_density=low`: cover, closing, quote, single insight. Large title/ghost typography; 1-3 short text blocks.
- `content_density=medium`: normal narrative pages. 3-5 cards or 2 large evidence slabs plus captions.
- `content_density=high`: default for substantive content pages. Dense tables/charts, 6-10 compact labels, or 6+ glass cards with microcopy.
- `content_density=showcase`: visual-dominant image/document/team page with supporting labels.

Rules:
- Default normal slides to `high` unless they are cover, closing, quote, or deliberate showcase.
- Do not discard essential evidence just to preserve spacious style.
- Do not paste raw long paragraphs. Convert to compact labels, captions, table rows, cards, or annotations.
- High density must still retain at least one strong source-native art move and one chrome element.
- Minimum body font: `9` for glass-card microcopy, `12` for normal body, `8` for chart labels.
- Max page title lines: 1 preferred, 2 maximum at reduced size.
- If text clips, first reduce body copy, then switch to table/card labels, then reduce font within limits.

## 8. SVG / PPT Safety Contract

Allowed:
- Inline SVG primitives: `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `path`, `text`, `tspan`, `image`, `g`.
- Simple linear/radial gradients in `<defs>` only when needed for the main background.
- Local image hrefs for source images or cookbook assets.

Forbidden:
- `<style>`, `class`, `<foreignObject>`, `clip-path`, `<mask>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, CSS filters, external nonlocal URLs.
- Image opacity. Use a transparent overlay rectangle instead.
- Group opacity on large content groups; apply opacity to individual primitive fills when necessary.

Root skeleton:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <radialGradient id="bgBlue" cx="0" cy="0" r="1">
      <stop offset="0" stop-color="#1E74FB"/>
      <stop offset="1" stop-color="#0B091E"/>
    </radialGradient>
  </defs>
  <rect x="0" y="0" width="1280" height="720" fill="#0B091E"/>
</svg>
```

## 9. Spec Lock Snippet

```json
"cookbook": {
  "id": "figma_65cm_default",
  "priority": "hard default-candidate theme",
  "required_repeats": [
    "top-left task label on content pages",
    "top-right compact institutional mark",
    "bottom-right page badge",
    "night radial stage or explicit financial-document light stage"
  ],
  "source_native_art_moves": [
    "f65_night_radial_stage",
    "f65_ghost_brand_word",
    "f65_dual_brand_accent",
    "f65_glass_card",
    "f65_white_evidence_slab",
    "f65_orange_keyword",
    "f65_bottom_right_page_badge"
  ],
  "layout_recipes": ["reference examples only; may derive f65_adapted_* layouts when content requires other structures"],
  "adaptation_policy": "derive theme-compatible layouts from content semantics while preserving at least two source-native art moves on normal slides",
  "under_fidelity_checks": [
    "Every normal slide carries 2+ source-native art moves",
    "A viewer can recognize the dark finance/pharma reference without seeing the cookbook name",
    "Density adaptation preserves composition logic, not just palette/fonts",
    "Charts/tables remain white evidence slabs or theme-styled dark glass visuals"
  ],
  "chart_catalog_precedence": "choose chart_or_diagram from full catalog first, then restyle in this theme",
  "decorative_asset_policy": "reuse local assets only when semantically compatible; otherwise reconstruct motifs as safe SVG primitives",
  "forbidden_drift": [
    "generic SaaS dashboard",
    "pastel or beige editorial theme",
    "flat black slides with no radial/ghost/chrome art moves",
    "literal Pfizer/Merck marks on unrelated decks",
    "low-density-only poster pages for evidence-heavy content"
  ]
},
"chart_rules": {
  "catalog_source": "templates/charts/charts_index.json",
  "selected_templates": [],
  "selection_policy": "choose real catalog keys by content semantics first, then redraw/restyle in cookbook theme"
}
```

## 10. QA Checklist

- Cookbook is strong enough to avoid generic output.
- Recipes are examples, not a whitelist.
- Chart catalog precedence is explicit.
- Every recipe has `Art moves to preserve`.
- Design plans use `source_recipe_anchor` and `required_art_moves`, not only generic layout families.
- Each normal slide visibly carries at least two source-native art moves.
- A viewer can recognize the reference template without seeing the cookbook name.
- Density changes preserve composition logic, not only palette and fonts.
- Low/medium/high/showcase density modes exist.
- Dense evidence pages can still be generated.
- SVG safety rules are explicit.
- Forbidden drift is concrete.
- Text fitting rules prevent clipping.
- Local asset references do not depend on short-lived Figma URLs.
