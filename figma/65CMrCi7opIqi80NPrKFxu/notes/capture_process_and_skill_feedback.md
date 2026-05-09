# Capture Process And Skill Feedback

This note records what should change in the cookbook workflow after the first full Figma MCP capture.

## What Was Missing From The First Pass

The initial capture preserved screenshots, a contact sheet, and basic tokens. That is enough for a lightweight visual reference, but it is not enough for a strong cookbook.

A stronger Figma capture also needs:
- `get_design_context` examples for representative pages.
- `get_metadata` geometry for representative pages.
- `get_variable_defs` across light, lime, dark, dashboard, image, and dense pages.
- A manifest that maps every requested node to local evidence.
- Notes about Figma variable naming quirks and MCP limitations.

## Figma MCP Practical Findings

- `get_screenshot` works well for native 1920 x 1080 PNG capture.
- Screenshot URLs are short-lived, so local download must happen immediately.
- `get_design_context` is valuable because it returns exact React/Tailwind-like geometry, style summaries, asset constants, and node IDs.
- `get_metadata` is compact and useful for cookbook geometry recipes.
- `get_variable_defs` can reveal exact token values, but variable names may be misleading. In this file, `White` can resolve to `#000000`.
- `use_figma` can extract richer custom summaries, but large outputs are truncated in MCP responses.
- The Figma plugin runtime available here did not expose `fetch`, so a local POST receiver is not a reliable capture strategy.

## Skill Update Applied

Updated `.codex/skills/ppt-theme-cookbook/SKILL.md` to add a Figma MCP reference-capture checklist:
- create `figma/<fileKey>/`
- capture screenshots for every frame
- create manifest
- collect variable defs
- collect metadata
- collect representative design_context examples
- generate contact sheet
- record tool limitations

## Recommended Future Workflow

1. Create `figma/<fileKey>/screenshots`, `figma/<fileKey>/mcp`, and `figma/<fileKey>/notes`.
2. Capture screenshots for every requested node.
3. Download screenshots immediately.
4. Generate `contact_sheet.png`.
5. Build `capture_manifest.json`.
6. Run `get_variable_defs` on representative nodes.
7. Run `get_metadata` on each layout family.
8. Run `get_design_context` on each major layout family, at minimum:
   - agenda/divider
   - objective/metric grid
   - image/evidence
   - dark overview/title
   - dashboard/status
   - timeline
   - budget/metric stack
   - dense risk/table-equivalent
9. Save implementation-relevant excerpts into `mcp/design_context_samples.md`.
10. Only then write the cookbook.

## Remaining Gap

The current local evidence set stores screenshots, manifest, contact sheet, representative metadata and design_context excerpts. It does not store full raw Figma node JSON for every layer because MCP output truncation and plugin-network constraints made that unreliable in this environment.

For future automation, consider adding a small dedicated extractor command that calls Figma through an authenticated API/token if available, or enhances the MCP server with a file-output mode for large captures.
