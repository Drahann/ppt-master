# PPT Master Theme Cookbooks

Cookbooks are hard theme systems for the automation pipeline. They are loaded before planning and injected into the stable prompt prefix used by:

- `design_plan.json` / `spec_lock.json` generation
- cache-prime prompts
- per-slide SVG generation prompts
- generated project prompt archives

Usage:

```bash
python skills/ppt-master/scripts/api_ppt.py generate input.md
python skills/ppt-master/scripts/api_ppt.py generate input.md --cookbook figma_65cm_default
```

You can pass a root-level cookbook markdown file, a cookbook folder containing
`<folder-name>.md` or `cookbook.md`, an absolute path, or set
`PPT_MASTER_COOKBOOK`.

When no cookbook is specified, each generation currently uses the built-in
default no-cookbook theme. The random theme pool is intentionally restricted to
`default`; pass `--cookbook <name>` to force a cookbook such as
`figma_65cm_default`, `figma_colorblock_modern`, or `figma_lime_serif_grid`.

Current cookbooks:

- `figma_65cm_default/figma_65cm_default.md` - Figma 65CM dark pharmaceutical finance analysis system with Metropolis typography, night gradients, Pfizer/Merck dual-brand chroming, BBS top mark, translucent oversized brand letters/numerals, blue/green/orange accent logic, glassy data panels, 3D medical assets, financial-document stacks, team portrait strips, and dense chart/table layouts.
- `figma_colorblock_modern.md` - Figma colorblock editorial system with mustard/orange/sage/powder-blue fields, light sans display type, thin outline glyphs, device/photo slabs, and sparse numeric systems.
- `figma_lime_serif_grid.md` - Figma lime serif grid system with Neuton display type, Open Sans body text, lime/dark-green/black/white pages, top chrome, thin editorial rules, hard metric fields, status pills, timelines, budget stacks, and dark risk rows.
