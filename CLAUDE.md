# CLAUDE.md

This file is project memory for Claude Code in this repository.

## Primary Mode

PPT Master now defaults to automation mode:

`Markdown/JSON input -> slide manifest -> design_plan/spec_lock -> parallel per-slide SVG -> quality report -> PPTX export`

Follow `skills/ppt-master/SKILL.md` for the current workflow. The old Strategist / Executor / Eight Confirmations workflow is legacy reference only and must not be used unless the caller explicitly asks for it.

## Claude Code Invocation Rules

When invoked by `skills/ppt-master/scripts/api_ppt.py`:

- Follow the stdin prompt exactly.
- For SVG generation, return exactly one complete SVG document for the requested slide and no prose.
- SVG/spec font choices are preserved for the primary editable PPTX export. Post-processing also builds a temporary `svg_final_sourcehan/` variant and exports a Source Han version (`思源宋体` titles, `思源黑体` body text) without changing `svg_final/`.
- Do not output summaries, plans, explanations, markdown fences, or progress narration.
- Do not inspect unrelated repository files or run tools unless the prompt explicitly asks for it.
- Treat `design_plan.json` as soft visual guidance and `spec_lock.json` as the hard visual/token anchor.
- Keep the deck style light, polished, and consistent across pages.
- Keep the locked primary accent dominant on every slide. Supporting colors may enrich the page, but they must not turn individual pages into a different theme.
- Never use dark full-slide themes, black hero backgrounds, neon-on-black styling, `rgba()`, `clip-path`, `<style>`, `class`, `<foreignObject>`, `<script>`, `<animate*>`, `<textPath>`, `<mask>`, or HTML named entities in generated SVG.
- Prefer project icon placeholders such as `<use data-icon="chunk-filled/rocket" .../>`; `finalize_svg.py` embeds the actual icons.

## Cache Discipline

The automation runner builds a byte-stable `PPT_MASTER_COMMON_PREFIX_V1` shared prompt prefix.

- Do not depend on project paths, timestamps, logs, random values, or current page numbers inside shared prompt context.
- Page-specific information must remain after the shared prefix.
- If a prompt asks for cache priming and no task follows the common prefix, return exactly `ACK`.

## Useful Commands

```bash
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --renderer local
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --cache-prime --svg-workers 12 --svg-batch-size 4
python skills/ppt-master/scripts/total_md_split.py <project_path>
python skills/ppt-master/scripts/finalize_svg.py <project_path>
python skills/ppt-master/scripts/svg_to_pptx.py <project_path> -s final
```

## Repository Boundaries

- This repository is a PPT workflow and automation engine, not a generic app scaffold.
- Do not create `.worktrees/`, generic app test folders, or branch-management workflows unless explicitly requested.
- Keep API keys out of files and logs.
