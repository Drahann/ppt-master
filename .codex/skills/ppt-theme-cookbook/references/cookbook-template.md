# Cookbook: THEME_ID

Priority: hard theme system.

Important philosophy:
- This cookbook is a strong visual grammar, not a layout or chart whitelist.
- Source content and the full chart catalog decide semantic structure.
- This cookbook decides how that structure is rendered in the theme.
- Named recipes are reference exemplars. Use them when they fit; derive `THEME_adapted_*` layouts when content needs another structure.

Reference set:
- Source folder/deck:
- Visual DNA:
- Key source slides/pages:

## 1. Pipeline Role

### 1.1 Design/spec stage

When generating `design_plan.json` and `spec_lock.json`:

- Set `design_plan.cookbook.id` and `spec_lock.cookbook.id` to `THEME_ID`.
- First decide each slide's semantic job from source content.
- If a chart, diagram, framework, table, process, architecture visual, or infographic is needed, set `chart_or_diagram` to a real key from the full chart catalog.
- Use either a matching reference recipe or a derived `THEME_adapted_*` layout in `layout_family`, `layout_signature`, and `visual_structure`.
- Convert tokens into `spec_lock`: typography, colors, spacing, chrome, image policy, chart restyling rules, density modes, adaptation policy, and forbidden drift.

### 1.2 SVG stage

When generating SVG:

- Build the selected `layout_family` visibly.
- If `chart_or_diagram` names a catalog key, preserve that chart/diagram's semantic geometry and restyle it in this theme.
- Use source images only when provided.
- Follow density mode and text fitting rules.
- Do not drift into generic dashboard/card styles.

## 2. Global Tokens

Canvas:
- `viewBox="0 0 1280 720"`

Color tokens:
- `bg`:
- `text`:
- `text_secondary`:
- `primary`:
- `accent`:
- Supporting colors:

Typography:
- Display/title stack:
- Body stack:
- Dense fallback:

Type ramp:
- Cover title:
- Page title:
- Headline:
- Body:
- Caption:
- Metric:
- Table:

Shape language:
- 

Spacing:
- Outer margin:
- Title position:
- Body grid:
- Footer/page mark:

## 3. Decorative / Asset System

Define required motifs and reusable geometry.

Rules:
- 

Reusable shapes/assets:

```xml
<!-- paste concrete SVG path/polygon/image treatment examples here -->
```

## 4. Reference Layout Recipes

These recipe IDs are teaching examples and named shortcuts, not an exhaustive whitelist.

Use a listed ID when content naturally matches it. If content needs another structure, derive `THEME_adapted_<semantic_structure>`.

### 4.1 `THEME_cover`

Use for:

Composition:

Geometry:

Text rules:

Failure modes:

### 4.2 `THEME_text_or_editorial`

Use for:

Composition:

Geometry:

Text rules:

Failure modes:

### 4.3 `THEME_image_evidence`

Use for:

Composition:

Geometry:

Image rules:

Failure modes:

### 4.4 `THEME_metric_or_proof`

Use for:

Composition:

Geometry:

Number rules:

Failure modes:

### 4.5 `THEME_chart_table_diagram_example`

Use for:

Composition:

Geometry:

Chart/table restyling:

Failure modes:

## 5. Chart Catalog and Theme Restyling

The chart catalog is the full visualization vocabulary.

Selection order:
1. Read source content and decide data/relationship semantics.
2. Pick the most accurate `chart_or_diagram` key from the full catalog.
3. Restyle/redraw that chart in this theme.
4. Do not choose a cookbook chart recipe merely because it is documented here.

Theme restyling rules:
- Bar/line/area:
- Funnel/sankey/radar/treemap/waterfall/scatter/heatmap:
- Matrix/Venn/timeline:
- Tables:
- Strategy frameworks:
- Architecture/process diagrams:
- Team/org charts:

## 6. Density and Text Fitting

- `content_density=low`:
- `content_density=medium`:
- `content_density=high`:

Rules:
- Do not discard essential evidence just to preserve sparse style.
- Do not paste raw long paragraphs.
- Use theme-compatible tables/columns for high-density pages.
- Minimum font size:
- Max title lines:
- Body line-height:
- Fallback when text clips:

## 7. SVG / PPT Safety Contract

Allowed:
- 

Forbidden:
- `<style>`, `class`, `<foreignObject>`, `clip-path`, `<mask>`, `rgba()`, `<script>`, `<animate*>`, `<textPath>`, external URLs.

Root skeleton:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="..."/>
  ...
</svg>
```

## 8. Spec Lock Snippet

```json
"cookbook": {
  "id": "THEME_ID",
  "priority": "hard",
  "required_repeats": [],
  "layout_recipes": ["reference examples only; may derive THEME_adapted_* layouts when content requires other structures"],
  "adaptation_policy": "derive theme-compatible layouts from content semantics",
  "chart_catalog_precedence": "choose chart_or_diagram from full catalog first, then restyle in this theme",
  "decorative_asset_policy": "",
  "forbidden_drift": []
},
"chart_rules": {
  "catalog_source": "templates/charts/charts_index.json",
  "selected_templates": [],
  "selection_policy": "choose real catalog keys by content semantics first, then redraw/restyle in cookbook theme"
}
```

## 9. QA Checklist

- Cookbook is strong enough to avoid generic output.
- Recipes are examples, not a whitelist.
- Chart catalog precedence is explicit.
- Low/medium/high density modes exist.
- Dense evidence pages can still be generated.
- SVG safety rules are explicit.
- Forbidden drift is concrete.
- Text fitting rules prevent clipping.
