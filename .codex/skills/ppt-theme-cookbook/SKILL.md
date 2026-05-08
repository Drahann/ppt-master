---
name: ppt-theme-cookbook
description: Create or revise strong PPT theme cookbooks from Figma exports, existing slide decks, PPT templates, screenshots, or generated slide samples. Use when Codex needs to extract a presentation theme's visual grammar, write a reusable cookbook for AI PPT/SVG generation, avoid chart-template overbias, define density modes, or integrate cookbook guidance into design/spec/SVG generation prompts.
---

# PPT Theme Cookbook

Use this skill to turn a reference slide theme into a reusable AI-generation cookbook. The output should teach another AI how to reproduce the theme from scratch without prior conversation context.

## Core Principle

Write a **strong visual grammar**, not a template whitelist.

- Strong: provide exact colors, type scales, geometry, spacing, chrome, image treatment, chart skin, text-density rules, and forbidden drift.
- Flexible: let slide content and the full chart catalog decide semantic structure.
- Recipes are exemplars: use named layout recipes as teaching examples and shortcuts, but allow `theme_adapted_*` layouts when content requires different structures.

## Workflow

1. Inspect the reference source.
   - For Figma export folders, inventory slide markdown/SVG/PNG/JPG files, then sample representative slides from each layout family.
   - For PPTX/decks/screenshots, render or inspect enough pages to see cover, dividers, text pages, image pages, metrics, charts, tables, team/contact, and dense evidence pages.
   - Extract repeated visual DNA: canvas, palette, fonts, title scale, body scale, margins, shape language, cards, diagrams, chart treatment, decorative assets, image crops, page numbers, footers, and density.

2. Separate semantics from style.
   - Semantic structure belongs to source content and chart catalog: bar, line, funnel, sankey, radar, matrix, timeline, org chart, table, architecture, etc.
   - Cookbook style belongs to theme execution: how each semantic structure looks in this theme.
   - Never let a detailed cookbook example suppress a better catalog chart key.

3. Write the cookbook using the method reference.
   - Load [references/cookbook-method.md](references/cookbook-method.md) before drafting.
   - Use [references/cookbook-template.md](references/cookbook-template.md) as the output skeleton when a complete cookbook is requested.

4. Include hard guidance in these areas.
   - Pipeline role: how design/spec/SVG stages must use the cookbook.
   - Theme tokens: colors, fonts, type ramp, spacing, rules, shape language.
   - Decorative system: reusable paths/shapes/assets and placement rules.
   - Reference layout recipes: named exemplars with geometry and use cases.
   - Chart catalog policy: catalog first, cookbook restyling second.
   - Density modes: low, medium, high, with text fitting rules.
   - SVG/PPT safety: allowed/forbidden SVG features, image path rules, font fallback.
   - Spec lock snippet: fields downstream prompts should carry.
   - QA rubric: bias, density, consistency, text fit, chart diversity.

5. Validate against overbias.
   - Check that `chart_or_diagram` can use the full chart catalog.
   - Check that recipe names are framed as reference examples, not `use only`.
   - Check that high-density technical/table pages are possible without breaking the theme.
   - Check that the cookbook is strong enough to prevent vague, mixed, generic output.

## Output Contract

When asked to create a cookbook, produce a single Markdown cookbook that can be saved directly into a PPT generation project.

The cookbook must state:
- `This cookbook is a strong visual grammar, not a layout or chart whitelist.`
- `Source content and the full chart catalog decide semantic structure.`
- `The cookbook decides how that structure is rendered in the theme.`
- `Named recipes are reference exemplars; derive adapted layouts when needed.`

Avoid vague wording like "make it elegant" unless paired with executable geometry, typography, and component rules.
