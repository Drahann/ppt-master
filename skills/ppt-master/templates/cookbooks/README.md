# PPT Master Theme Cookbooks

Cookbooks are hard theme systems for the automation pipeline. They are loaded before planning and injected into the stable prompt prefix used by:

- `design_plan.json` / `spec_lock.json` generation
- cache-prime prompts
- per-slide SVG generation prompts
- generated project prompt archives

Usage:

```bash
python skills/ppt-master/scripts/api_ppt.py generate input.md --cookbook figma_group02_inter_precision
```

You can also pass an absolute path or set `PPT_MASTER_COOKBOOK`.

Current cookbooks:

- `figma_group02_inter_precision.md` - Figma group-02 monochrome editorial system with fixed recipe geometry, micro-chrome, gray cards, metrics, timeline, matrix, Venn, funnel, device, quote, and team layouts.
- `figma_group08_pastel_papercut.md` - Figma group-08 pastel papercut editorial system with oversized serif titles, Playfair/Georgia italic notes, irregular pastel paper paths, rotated image slabs, big metrics, milestones, matrix, Venn, device, quote, and team gallery layouts.
- `figma_lime_serif_grid.md` - Figma lime serif grid system with Neuton display type, Open Sans body text, lime/dark-green/black/white pages, top chrome, thin editorial rules, hard metric fields, status pills, timelines, budget stacks, and dark risk rows.
