---
name: ppt-theme-cookbook
description: Create or revise strong PPT theme cookbooks from Figma exports, existing slide decks, PPT templates, screenshots, or generated slide samples. Use when Codex needs to extract a presentation theme's visual grammar, write a reusable cookbook for AI PPT/SVG generation, avoid chart-template overbias, define density modes, or integrate cookbook guidance into design/spec/SVG generation prompts.
---

# PPT Theme Cookbook

Use this skill to turn a reference slide theme into a reusable AI-generation cookbook. The output should teach another AI how to reproduce the theme from scratch without prior conversation context.

## Core Principle

Write an **art-directed adaptive grammar**, not a template whitelist or a loose mood reference.

- Art-directed: every recipe must carry visible source-native art moves, not only a layout skeleton.
- Adaptive: let slide content and the full chart catalog decide semantic structure.
- Grammar: provide exact colors, type scales, geometry, spacing, chrome, image treatment, chart skin, text-density rules, and forbidden drift.
- Recipes are exemplars: use named layout recipes as teaching examples and shortcuts, but allow `theme_adapted_*` layouts when content requires different structures.
- The target is template translation: semantic structure may change, but source-native art moves must remain visible.

## Workflow

1. Inspect the reference source.
   - For Figma MCP sources, do a full reference capture before drafting:
     - Create `figma/<fileKey>/` with `screenshots/`, `mcp/`, and `notes/`.
     - Call `whoami` once to verify Figma MCP access.
     - For every requested frame, call `get_screenshot` at native slide scale and immediately download the PNG locally because MCP asset URLs are short-lived.
     - For every requested frame, capture `node_id`, URL, screenshot filename, and intended layout role in a machine-readable manifest.
     - When the cookbook may become a default or reusable production theme, treat the task as a heavy design-system extraction, not a light visual summary:
       - Download every requested frame screenshot.
       - Generate a contact sheet before interpretation.
       - Extract aggregate colors, fonts, node types, image counts, text samples, and reusable layer names across all frames.
       - Download representative decorative/image assets exposed by Figma design-context constants into a stable local asset folder.
       - Write an asset index explaining what each downloaded asset is, when it may be reused, and when literal brand assets must be replaced.
       - Preserve capture notes with tool limitations, timeouts, truncation, and evidence-vs-inference boundaries.
     - Call `get_variable_defs` on representative light, dark, accent, image, dashboard, and dense pages to collect color/font variable names and exact values.
     - Call `get_metadata` for representative pages to preserve frame hierarchy, geometry, and layer names.
     - Call `get_design_context` for at least one representative page per layout family to capture generated React/Tailwind-style code, asset constants, typography summary, node IDs, and exact geometry clues. Store excerpts locally; do not rely on chat history.
     - If using `use_figma` for custom extraction, keep outputs compact enough to avoid truncation. Do not assume Figma plugin runtime can `fetch` to localhost.
     - Generate a contact sheet so the full reference set can be visually audited in one pass.
     - Record MCP/tool limitations and any missing or truncated captures in `notes/`.
   - For Figma export folders, inventory slide markdown/SVG/PNG/JPG files, then sample representative slides from each layout family.
   - For PPTX/decks/screenshots, render or inspect enough pages to see cover, dividers, text pages, image pages, metrics, charts, tables, team/contact, and dense evidence pages.
   - For reference PPT/PPTX templates, use the reserved template-capture interface when that workflow is requested:
     - Create `ppt_templates/<template_id>/` with `source/`, `renders/`, `extracted/`, and `notes/`.
     - Preserve the original `.pptx` or template file in `source/` without modifying it.
     - Render slide thumbnails/contact sheets before interpreting the visual system.
     - Extract theme/master evidence when available: slide size, theme fonts, theme colors, master layouts, placeholders, background fills, recurring footer/header/page-number elements, table/chart styling, and image treatment.
     - Capture representative editable-object geometry from the deck when tooling supports it: shape positions, text boxes, table bounds, chart bounds, line weights, fills, gradients, shadows, and placeholder roles.
     - Record missing extraction capabilities explicitly. If only screenshots are available, mark geometry and master/theme details as inference.
     - Do not draft a PPT-template cookbook from screenshots alone when the template file is available but not inspected.
     - This interface is intentionally a placeholder for a future PPT-template workflow; prefer the Figma MCP workflow for Figma sources.
   - Extract repeated visual DNA: canvas, palette, fonts, title scale, body scale, margins, shape language, cards, diagrams, chart treatment, decorative assets, image crops, page numbers, footers, and density.

2. Separate semantics, style, and art moves.
   - Semantic structure belongs to source content and chart catalog: bar, line, funnel, sankey, radar, matrix, timeline, org chart, table, architecture, etc.
   - Cookbook style belongs to theme execution: how each semantic structure looks in this theme.
   - Art moves are the non-generic, source-native visual actions that make the reference recognizable: unusual paper shards, rotated image slabs, side italic phrases, giant serif numerals, lime proof slabs, editorial chrome, thin rule grids, status capsules, black/green reversal pages, etc.
   - Never let a detailed cookbook example suppress a better catalog chart key.
   - Never let adaptation erase the art moves. A slide may become a comparison table, matrix, or architecture view, but it must visibly inherit at least two relevant source-native art moves unless it is a purely functional appendix page.

3. Synthesize rich evidence into executable cookbook rules.
   - Treat screenshots as visual truth, `get_metadata` as geometry truth, `get_variable_defs` as token evidence, and `get_design_context` as implementation evidence.
   - Convert Figma/React/Tailwind coordinates into PPT Master SVG coordinates. For `1920 x 1080` Figma slides, scale geometry by `2/3` to `1280 x 720`.
   - Use `get_design_context` examples to identify reusable motifs: chrome, line assets, status pills, image slabs, metric blocks, timelines, arrows, table rows, and placeholders. Rewrite these as SVG/PPT-safe primitives; do not preserve generated React/Tailwind code as cookbook implementation.
   - Use `get_metadata` to define recipe geometry with concrete x/y/w/h values, not vague layout descriptions.
   - Cross-check variable names against resolved colors. If names are misleading, document semantic color roles instead of trusting variable names.
   - For each recipe, write both a semantic use case and an `Art moves to preserve` list. A recipe without art moves is incomplete.
   - For adapted layouts, define how art moves transfer: e.g. `source_recipe_anchor`, `required_art_moves`, and the composition logic that must survive after content-density changes.
   - Write from the full evidence pack: reference images, manifest, metadata, variable defs, design-context excerpts, and contact sheet.
   - Store any tool limitations, missing captures, or inference boundaries near the source folder so future cookbook revisions do not over-trust incomplete evidence.
   - The final cookbook injected into API prompts must not include local path lists, `Reference set:` sections, MCP URLs, Figma node URLs, or source-folder breadcrumbs. Summarize provenance as `Theme evidence summary` with reference type, frame count, visual DNA, motifs, and limitations only.
   - For production/default-candidate cookbooks, the output should be a folder, not only a single markdown file:
     - `<theme_id>/<theme_id>.md`
     - `<theme_id>/assets/screenshots/`
     - `<theme_id>/assets/figma_assets/`
     - `<theme_id>/assets/notes/`
     - `<theme_id>/assets/contact_sheet.png`
     - Optionally add a root README or index if the repo supports named cookbook folders.

4. Write the cookbook using the method reference.
   - Load [references/cookbook-method.md](references/cookbook-method.md) before drafting.
   - Use [references/cookbook-template.md](references/cookbook-template.md) as the output skeleton when a complete cookbook is requested.
   - It is acceptable to adapt the skeleton when richer Figma evidence supports a stronger structure, but the cookbook must still include pipeline role, tokens, layout recipes, chart policy, density/text fitting, SVG safety, spec lock snippet, and QA.

5. Include hard guidance in these areas.
   - Pipeline role: how design/spec/SVG stages must use the cookbook.
   - Theme tokens: colors, fonts, type ramp, spacing, rules, shape language.
   - Art move inventory: the source-native visual actions that must remain recognizable after adaptation.
   - Decorative system: reusable paths/shapes/assets and placement rules.
   - Reference layout recipes: named exemplars with geometry, use cases, art moves, adaptation rules, and failure modes.
   - Chart catalog policy: catalog first, cookbook restyling second.
   - Density modes: low, medium, high, with text fitting rules and composition-preservation rules.
   - SVG/PPT safety: allowed/forbidden SVG features, image path rules, font fallback.
   - Spec lock snippet: fields downstream prompts should carry.
   - QA rubric: bias, under-fidelity, density, composition logic, consistency, text fit, chart diversity.

6. Validate against overbias and under-fidelity.
   - Check that `chart_or_diagram` can use the full chart catalog.
   - Check that recipe names are framed as reference examples, not `use only`.
   - Check that high-density technical/table pages are possible without breaking the theme.
   - Check that the cookbook is strong enough to prevent vague, mixed, generic output.
   - Check that every recipe visibly carries 2+ source-native art moves.
   - Check that density adaptation preserves the reference composition logic instead of just filling the canvas with cards.
   - Check that a viewer could recognize the reference template without seeing the cookbook name.
   - Check that at least one recipe came from actual metadata/design-context geometry instead of screenshot-only impressions.
   - Check that short-lived Figma MCP asset URLs are not required by the final cookbook or generated SVG.
   - Check that downloaded assets are local and indexed.
   - Check that brand-specific source assets are not mandated for unrelated decks; preserve the art move while allowing semantic replacement.

## Output Contract

When asked to create a cookbook, produce a single Markdown cookbook that can be saved directly into a PPT generation project.

The cookbook must state:
- `This cookbook is an art-directed adaptive grammar, not a layout/chart whitelist or a loose style reference.`
- `Source content and the full chart catalog decide semantic structure.`
- `The cookbook decides how that structure is rendered in the theme.`
- `Named recipes are reference exemplars; derive adapted layouts when needed.`
- `Semantic structure may adapt to content; source-native art moves must remain visibly inherited.`
- `Density may increase, but composition logic cannot collapse into generic cards.`

Avoid vague wording like "make it elegant" unless paired with executable geometry, typography, and component rules.
