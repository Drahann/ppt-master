# Cookbook Authoring Method

Use this method to create an art-directed adaptive PPT theme cookbook from reference slides.

## 1. Source Audit

Collect evidence before writing.

For a local Figma export folder:
- Count slide files and asset types.
- Read slide markdown files for titles and intended layouts.
- Inspect SVG files for colors, fonts, paths, sizes, repeated components, and chrome.
- Open representative PNG/JPG previews when available.
- Sample at least cover, chapter/TOC, text, image, metric, chart/table, team/contact, and closing pages.

For a PPTX or existing deck:
- Render thumbnails/contact sheet if possible.
- Inspect master/theme if available.
- Identify repeated slide families and where the deck intentionally breaks rhythm.

Record:
- Theme posture: editorial, technical, premium, playful, institutional, etc.
- Visual DNA: palette, typography, shapes, imagery, layout rhythm, density.
- Repeated components: cards, chips, numbers, rules, labels, charts, tables, footers.
- What must not happen: dark fallback, generic dashboard, random stock photos, wrong font family, repeated 3-card pages.

## 2. Extract Theme Grammar And Art Moves

Convert observations into executable rules.

Palette:
- Name core colors and semantic roles.
- Include exact HEX values.
- Say which color dominates and which colors are support only.

Typography:
- Define display, body, caption, metric, table, and fallback stacks.
- Give font-size ranges and max line counts.
- State whether typography is serif, sans, condensed, mono, handwritten, etc.

Layout:
- Define canvas, margins, columns, title positions, footer/page-mark positions.
- Define layout rhythm, not only static templates.
- Explain how to vary pages while keeping theme continuity.

Decorative assets:
- Provide concrete paths, shape recipes, texture rules, crop rules, or icon rules.
- Say when decoration is required, optional, or forbidden.

Art moves:
- Name the source-native visual actions that make the reference recognizable, not just the colors and fonts.
- Examples: irregular paper shards, rotated photo slabs, side italic phrases, giant serif numerals, lime proof panels, black/green reversal pages, top editorial chrome, thin rule grids, status capsules, progress bars.
- Record which moves are global repeats and which moves belong to specific recipes.
- Require adapted layouts to inherit at least two relevant art moves unless the page is a purely functional appendix.

Components:
- Define cards, labels, metric rows, quote blocks, tables, image slabs, diagrams, and charts.
- Include geometry and spacing, not just aesthetic adjectives.

Density:
- Define `content_density=low|medium|high`.
- Low: poster or live keynote page.
- Medium: normal business/technical presentation page.
- High: leave-behind, evidence, table, or technical page.
- Make high density possible inside the theme instead of forcing every page into sparse poster mode.
- Density is not a permission to delete the template's composition logic. Low density preserves original whitespace; medium compresses whitespace while keeping proportions; high uses tables/columns/annotation layers while retaining one strong source-native art move.

## 3. Keep Chart Catalog Precedence

The cookbook must not replace the chart catalog.

Required rule:
1. Read source content and decide the relationship semantics.
2. Choose the best real `chart_or_diagram` key from the full catalog.
3. Restyle/redraw that chart in the cookbook theme.
4. Use a cookbook chart recipe only when it is semantically correct.

Bad:
- "Use only these chart recipes."
- "Prefer these cookbook charts."
- Describing only Venn/matrix/timeline so the model overuses them.

Good:
- "Any catalog key may be used. Preserve its semantic geometry, then apply this theme's fills, lines, labels, spacing, and typography."
- "Funnel, sankey, radar, treemap, waterfall, scatter, heatmap, table, org chart, and architecture diagrams are all allowed if the content calls for them."

## 4. Use Recipes As Teaching Examples

Recipes should teach the style deeply enough that the AI can extrapolate.

Each recipe should include:
- When to use it.
- Composition.
- Geometry.
- Art moves to preserve.
- Adaptation rules for different semantic structures.
- Text rules.
- Decorative rules.
- Variants.
- Failure modes.

But recipes must be framed as examples:
- "Reference recipes"
- "Named shortcuts"
- "Use when content naturally matches"
- "Derive `theme_adapted_*` when content needs another structure"

Avoid:
- "Allowed layout vocabulary"
- "Use only these recipe IDs"
- "Every slide must choose exactly one listed recipe"

## 5. Write Pipeline Integration Rules

Design/spec stage:
- Set cookbook id in `design_plan` and `spec_lock`.
- Convert tokens into executable `spec_lock` fields.
- Put recipe or adapted layout in `layout_family`.
- Put the concrete recipe/motif anchor in `source_recipe_anchor`.
- Put 2+ visible source-native moves in `required_art_moves`.
- Put a real chart catalog key in `chart_or_diagram` when needed.
- Record `chart_catalog_precedence` and `adaptation_policy`.

SVG stage:
- Follow `spec_lock` first.
- Use cookbook text when `spec_lock` misses details.
- Build named recipes or adapted layouts visibly.
- If `chart_or_diagram` exists, preserve the chart's semantic geometry and restyle it in the theme.
- Do not downgrade to generic cards/two-column pages.

## 6. Cookbook Strength Checklist

A strong cookbook has:
- Exact color tokens.
- Exact font stacks and type ramp.
- Canvas and spacing numbers.
- Source-native art move inventory.
- Reusable decorative geometry or asset rules.
- Page chrome rules.
- Concrete component geometry.
- Multiple density modes.
- Per-recipe art moves and adaptation rules.
- Chart catalog precedence.
- SVG/PPT safety contract.
- Forbidden drift list.
- Spec lock snippet.
- QA checklist.

A weak cookbook has:
- Only inspiration words.
- Only colors/fonts, with no source-native art moves.
- No geometry.
- No text fitting rules.
- No density modes.
- No chart policy.
- No failure modes.

An over-restrictive cookbook has:
- Hard layout whitelist.
- Hard chart whitelist.
- Repeated same layout across pages.
- Low-density-only rule.
- No adapted layout mechanism.

## 7. Validation Procedure

After writing:
- Search for restrictive phrases: `use only`, `exactly one`, `must choose`, `allowed vocabulary`.
- If present, make sure they apply only to safety rules, not chart/layout semantics.
- Confirm chart catalog precedence is explicit.
- Confirm `theme_adapted_*` or equivalent adapted layout mechanism exists.
- Confirm every recipe names art moves to preserve.
- Confirm `source_recipe_anchor` and `required_art_moves` are described for design_plan/spec usage.
- Confirm the QA checklist includes under-fidelity, not only overbias.
- Confirm low/medium/high density modes exist.
- Confirm at least one recipe teaches each major surface: cover, text, image, metric, chart/table/diagram, team/contact/closing.
- If a generated deck exists, inspect `design_plan` recipe distribution and `chart_or_diagram` diversity.
- Render a contact sheet and look for text clipping, over-sparse slides, monotony, and theme drift.

## 8. Common Fixes

If AI overuses cookbook charts:
- Strengthen chart catalog precedence.
- Rename cookbook chart sections as "theme restyling examples".
- Add "do not choose this chart merely because it is documented here."

If output is visually mushy:
- Add exact geometry, font sizes, coordinates, and forbidden drift.
- Add stronger decorative asset recipes.
- Add negative examples.
- Add recipe-level art moves and require 2+ moves in `required_art_moves`.

If output is too sparse:
- Add `content_density=medium/high`.
- Provide high-density table/evidence layout rules.
- Reduce title size ranges for dense pages.
- Define how medium/high density preserves composition proportions instead of merely filling blank areas.

If output is too template-like:
- Add adapted layout mechanism.
- Require semantic layout choice from content.
- Forbid repeated adjacent layout unless structure differs.

If output is too generic:
- Add an under-fidelity QA gate: would a viewer recognize the source template without seeing the cookbook name?
- Require concrete `source_recipe_anchor` values, not generic families such as `matrix`, `dashboard`, or `process`.
- Require the reducer/spec stage to preserve source-native art moves through adaptation.

If output clips text:
- Add max title width, max line count, fallback title sizes, and body line-height rules.
- Require dynamic compression before clipping.
