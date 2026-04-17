---
name: ppt-svg-review
description: >
  Review and repair PPT Master SVG outputs after executor generation. Use this
  when `svg_output/*.svg` already exist and need a separate repair pass focused
  on XML validity, filename drift, notes-heading mismatches, local chart
  geometry mistakes, overflow, misalignment, and other small SVG defects
  without redesigning whole slides.
---

# PPT SVG Review

This skill is for local SVG repair and polish after the main SVG generation session.

Primary workflow source:

- `workflows/svg-review.md`

Read these files first:

1. `../ppt-master/SKILL.md`
2. `../ppt-master/references/repo_skill.md`
3. `../ppt-master/references/executor-base.md`
4. `../ppt-master/references/svg_design_cookbook.md`
5. `../ppt-master/references/shared-standards.md`
6. `../ppt-master/references/image-layout-spec.md`
7. `runner/svg_anchor_context.json` if it exists
8. `workflows/svg-review.md`

Scope:

- Allowed edits:
  - `svg_output/*.svg`
  - `notes/total.md`
  - `svg_review_report.json`
- Forbidden edits:
  - `design_spec.md`
  - `slide_plan.json`
  - full-page redesigns

Repair priorities:

1. Invalid XML, broken tags, unescaped `<` / `>` / `&`
2. SVG filenames that do not match the slide plan
3. Notes headings that do not match SVG stems
4. Invalid icon refs
5. Local layout defects: misalignment, clipping, overflow, border spill, overlap
6. Obvious chart-geometry mistakes when a local redraw is enough to fix the intended chart

Review order:

- C1 skeleton consistency against the baseline content page
- C2 title-icon alignment
- C3 text overflow and clipping
- C4 XML and escaping validity
- C5 big-number / badge completeness
- C6 layout monotony and local polish

Rules:

- Preserve the slide’s intended design and content
- Prefer small local edits over full rewrites
- If a chart is semantically wrong, repair the chart region rather than the whole page
- Use the runtime anchor context to restore fixed header/footer/defs/icon-spacing/naming consistency after long-run drift or interrupted resumes

Output:

- Repair the existing SVG and notes files in place
- Write a JSON review report with `status`, `summary`, `issues_found`, `issues_fixed`, and `remaining_risks`
