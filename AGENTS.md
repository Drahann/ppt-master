# AGENTS.md

This file is the project entry point for general AI agents.

For a complete current-state onboarding brief, read [`AGENT_CONTEXT.md`](AGENT_CONTEXT.md). If this file's legacy summaries conflict with `AGENT_CONTEXT.md` or `skills/ppt-master/SKILL.md`, prefer `SKILL.md` first, then `AGENT_CONTEXT.md`.

Before any PPT generation task, **you MUST first read [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md)** — the authoritative workflow for project creation, role switching, serial execution, quality gates, post-processing, and export.

## Project Overview

Current default: automation-first generation. Use `Markdown/JSON input -> slide_manifest -> design_plan/spec_lock -> per-slide SVG -> quality report -> notes -> finalize_svg -> export PPTX`. The older multi-role / Eight Confirmations pipeline below is legacy context only unless the user explicitly asks for it.

PPT Master is an AI-driven presentation generation system. Multi-role collaboration (Strategist → Image_Generator → Executor) converts source documents (PDF/DOCX/URL/Markdown) into natively editable PPTX with real PowerPoint shapes (DrawingML).

**Core Pipeline**: `Source Document → Create Project → Template Option → Strategist Eight Confirmations → [Image_Generator] → Executor → Quality Check → Chart Calibration → Post-processing → Export PPTX`

## Execution Requirements

- Read [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md) before starting a PPT task.
- For standalone template creation, read [`skills/ppt-master/workflows/create-template.md`](skills/ppt-master/workflows/create-template.md).
- Role-specific rules live in [`skills/ppt-master/references/`](skills/ppt-master/references/).
- Technical SVG/PPT constraints live in [`skills/ppt-master/references/shared-standards.md`](skills/ppt-master/references/shared-standards.md).
- Canvas choices live in [`skills/ppt-master/references/canvas-formats.md`](skills/ppt-master/references/canvas-formats.md).
- Icon library details live in [`skills/ppt-master/templates/icons/README.md`](skills/ppt-master/templates/icons/README.md).

## Compatibility Boundary

- This repository is a workflow/skill package, not an app or service scaffold.
- Do NOT assume conventions like `.worktrees/`, `tests/`, or mandatory branch setup unless the user explicitly requests them.
- On conflict with a generic coding skill, prioritize [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md) and this file inside this repository.

## Command Quick Reference

Current automation entry point: `python skills/ppt-master/scripts/api_ppt.py generate <input.md|postppt.json> --project-name <name>`. Use the manual commands below only for source conversion, standalone project management, or post-processing an existing generated project.

Convenience summary only — full workflow in [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md).

```bash
# Source content conversion
python3 skills/ppt-master/scripts/source_to_md/pdf_to_md.py <PDF_file>
python3 skills/ppt-master/scripts/source_to_md/doc_to_md.py <DOCX_or_other_file>
python3 skills/ppt-master/scripts/source_to_md/excel_to_md.py <XLSX_or_XLSM_file>
python3 skills/ppt-master/scripts/source_to_md/ppt_to_md.py <PPTX_file>
python3 skills/ppt-master/scripts/source_to_md/web_to_md.py <URL>

# Project management
python3 skills/ppt-master/scripts/project_manager.py init <project_name> --format ppt169
python3 skills/ppt-master/scripts/project_manager.py import-sources <project_path> <source_files_or_URLs...> --move
python3 skills/ppt-master/scripts/project_manager.py validate <project_path>

# Image tools and SVG quality check
python3 skills/ppt-master/scripts/analyze_images.py <project_path>/images
python3 skills/ppt-master/scripts/image_gen.py "prompt" --aspect_ratio 16:9 --image_size 1K -o <project_path>/images
python3 skills/ppt-master/scripts/svg_quality_checker.py <project_path>

# Chart coordinate calibration (MANDATORY after quality check, before notes)
# Step 1: find pages with charts
grep -l "chart-plot-area" <project_path>/svg_output/*.svg
# Step 2: run calculator per chart type and update SVG coordinates
python3 skills/ppt-master/scripts/svg_position_calculator.py calc bar --data "L1:V1,L2:V2" --area "x_min,y_min,x_max,y_max" --bar-width 120
python3 skills/ppt-master/scripts/svg_position_calculator.py calc pie --data "A:35,B:25" --center "cx,cy" --radius 200
python3 skills/ppt-master/scripts/svg_position_calculator.py calc line --data "x1:y1,x2:y2" --area "x_min,y_min,x_max,y_max" --y-range "0,max"

# Post-processing pipeline: run sequentially, one command at a time
python3 skills/ppt-master/scripts/total_md_split.py <project_path>
python3 skills/ppt-master/scripts/finalize_svg.py <project_path>
python3 skills/ppt-master/scripts/svg_to_pptx.py <project_path> -s final
```

## Core Directories

- `skills/ppt-master/SKILL.md` — main workflow authority.
- `skills/ppt-master/references/` — role definitions and technical specifications.
- `skills/ppt-master/scripts/` — runnable tool scripts.
- `skills/ppt-master/scripts/docs/` — topic-focused script docs.
- `skills/ppt-master/templates/` — layout templates, chart templates, icon library.
- `examples/` — example projects.
- `projects/` — user project workspace.
