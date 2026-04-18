---
name: ppt-master
description: >
  Qwen Code wrapper skill for the PPT Master repository. Use this when working
  inside this repo on PPT generation tasks so Qwen follows the repo-native
  workflow, role references, and SVG execution rules.
---

# PPT Master for Qwen Code

This is a thin Qwen-native wrapper around the repository's original workflow skill.

Source of truth:

- `.qwen/skills/ppt-master/references/repo_skill.md`

Read these files in order before executing PPT tasks:

1. `AGENTS.md`
2. `QWEN.md`
3. `.qwen/skills/ppt-master/references/repo_skill.md`

Then load only the role-specific references needed for the current phase:

- Strategist phase:
  - `.qwen/skills/ppt-master/references/strategist.md`
  - `.qwen/skills/ppt-master/templates/design_spec_reference.md`
  - `.qwen/skills/ppt-master/templates/charts/charts_index.json`
- Executor phase:
  - `.qwen/skills/ppt-master/references/svg_design_cookbook.md`
  - `.qwen/skills/ppt-master/references/executor-base.md`
  - one of:
    - `.qwen/skills/ppt-master/references/executor-consultant.md`
    - `.qwen/skills/ppt-master/references/executor-general.md`
  - `.qwen/skills/ppt-master/references/shared-standards.md`
  - `.qwen/skills/ppt-master/references/image-layout-spec.md` when images are involved
  - runtime anchor file `runner/svg_anchor_context.json` when present
- Review phases:
  - `.qwen/skills/ppt-spec-review/SKILL.md`

## Qwen-specific Guidance

- Use this wrapper to discover the repo workflow natively from `.qwen/skills/`.
- Prefer the cookbook under `.qwen/skills/ppt-master/references/` so Qwen reads it as part of the native skill context.
- Do not duplicate or rewrite the original rules into a parallel workflow.
- Treat `.qwen/skills/ppt-master/references/repo_skill.md` as authoritative when this wrapper is shorter than the original.
- During Executor work, SVG generation must remain in the main agent and proceed sequentially page by page.
- During long SVG runs, periodically re-anchor to both the cookbook and `runner/svg_anchor_context.json` so geometry, defs, naming, and footer/header rules do not drift.
- When the local runner enables batched execution, treat each batch as one continuous Executor segment governed by the same deck-level anchor contract.
