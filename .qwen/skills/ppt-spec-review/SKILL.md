---
name: ppt-spec-review
description: >
  Review and repair PPT Master design specs after strategist generation. Use
  this when `design_spec.md` exists and needs a separate review pass focused on
  icon validity, chart-template validity, weak layout choices, and report
  generation without touching SVG or notes.
---

# PPT Spec Review

This skill reviews an existing `design_spec.md` as a narrow repair task.

Read these files first:

1. `../ppt-master/SKILL.md`
2. `../ppt-master/references/repo_skill.md`
3. `../ppt-master/references/strategist.md`
4. `../ppt-master/templates/design_spec_reference.md`
5. `../ppt-master/references/svg_design_cookbook.md`

Scope:

- Allowed edits:
  - `design_spec.md`
  - `spec_review_report.json`
- Forbidden edits:
  - `svg_output/`
  - `notes/`
  - `slide_plan.json`

Checklist:

- All icon names must exist in the locked icon library
- All visualization templates must exist in `templates/charts/`
- No emoji
- Reassess weak page-task decisions, especially commercial and team slides
- Preserve downstream SVG anchorability: reviewed layouts should still support a stable title/icon/header/footer system across long sequential SVG generation
- Keep page count and slide order unchanged

Output:

- Repair the existing design spec in place
- Write a JSON review report with `status`, `summary`, `issues_found`, `issues_fixed`, and `remaining_risks`
