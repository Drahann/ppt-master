# QWEN.md

This repository is optimized for PPT generation workflows in Qwen Code.

Before doing any PPT generation work, read these files in order:

1. `AGENTS.md`
2. `.qwen/skills/ppt-master/SKILL.md`
3. `skills/ppt-master/SKILL.md`

## Project Intent

PPT Master converts source documents into SVG slide pages and exports them to editable PPTX.

Core pipeline:

`Source Document -> Create Project -> Template Option -> Strategist -> [Image_Generator] -> Executor -> Post-processing -> Export PPTX`

## Important Execution Rules

- This is a strict serial workflow. Do not skip or reorder phases.
- `skills/ppt-master/SKILL.md` remains the source of truth for the workflow.
- SVG generation must stay in the main agent and proceed sequentially page by page.
- Do not treat this repository like a generic app scaffold.

## Qwen-native Entry Points

- Project skill wrapper: `.qwen/skills/ppt-master/SKILL.md`
- Spec review skill: `.qwen/skills/ppt-spec-review/SKILL.md`
- SVG review skill: `.qwen/skills/ppt-svg-review/SKILL.md`
- SVG review workflow: `.qwen/skills/ppt-svg-review/workflows/svg-review.md`
- Mirrored workflow references: `.qwen/skills/ppt-master/references/`
- Mirrored template references: `.qwen/skills/ppt-master/templates/`

## When Generating SVG

Always read:

- `.qwen/skills/ppt-master/references/svg_design_cookbook.md`
- `.qwen/skills/ppt-master/references/executor-base.md`
- the matching style file under `.qwen/skills/ppt-master/references/`
- `.qwen/skills/ppt-master/references/shared-standards.md`
- `runner/svg_anchor_context.json` when it exists

Read `.qwen/skills/ppt-master/references/image-layout-spec.md` when the page uses images or mixed media blocks.

The `.qwen/skills/...` cookbook copy is the Qwen-native primary path. Keep it in sync with the repo reference copy when the cookbook is updated.
During long SVG runs, re-anchor periodically to both the cookbook and `runner/svg_anchor_context.json` so header/footer/defs/naming rules do not drift mid-run.
