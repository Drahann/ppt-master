# Capture Process and Limitations: 145 Designs

Capture date: 2026-05-09

## Completed

- Verified Figma MCP access with `whoami`.
- Captured all 35 requested frames with `get_screenshot` at `1920 x 1080`.
- Downloaded each short-lived MCP screenshot URL immediately to local PNG files under `screenshots/145_designs/`.
- Generated a local contact sheet: `figma/65CMrCi7opIqi80NPrKFxu/contact_sheet_145_designs.png`.
- Captured variable definitions for representative cover, agenda, metric, chart, team, and closing pages.
- Captured metadata for representative cover, agenda, metrics, chart, team, closing, quote, laptop, phone, and icon-grid pages.
- Captured design context for representative cover, agenda, metrics, chart, team, closing, quote, laptop, phone, and icon-grid pages.

## Limitations

- MCP asset URLs in design context are temporary and were not preserved as runtime dependencies.
- Full raw generated React code was summarized rather than stored verbatim for every sampled page because final PPT Master output must be SVG/PPT-safe, not React/Tailwind.
- The cookbook treats metadata geometry as exact for sampled recipes and screenshot/contact-sheet evidence as visual truth for unsampled recipe variants.
- Device and photo images in the Figma source should be treated as placeholders unless equivalent project-local images are supplied during PPT generation.
- Figma layer names are generic in many nodes (`Frame`, `Image`, `Decorative`, `Body`), so semantic roles in the manifest are inferred from screenshots plus geometry.

## Evidence Boundaries

- Exact tokens: colors and typography are from `get_variable_defs`.
- Exact geometry: representative recipes use `get_metadata` and `get_design_context`, scaled from `1920 x 1080` to `1280 x 720`.
- Visual-family coverage: all 35 pages are covered by the contact sheet and manifest.
- Inferred design grammar: art moves, recipe grouping, density rules, and chart restyling are synthesized from the full contact sheet plus sampled MCP evidence.
