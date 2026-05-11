---
name: ppt-master
description: >
  Automation-first PPT generation system. Converts Markdown/JSON input into
  planned SVG slides and exports editable PPTX while reusing PPT Master chart,
  icon, canvas, quality-check, post-processing, and export assets.
---

# PPT Master Skill

> PPT Master now defaults to an automation-first pipeline: Markdown/JSON input → design plan → parallel per-slide SVG → quality report → PPTX export.

## Default Pipeline

Use this path for normal work:

```bash
python3 ${SKILL_DIR}/scripts/api_ppt.py generate input.md --project-name demo
```

For JSON payloads where Markdown is in `content`:

```bash
python3 ${SKILL_DIR}/scripts/api_ppt.py generate postppt.json --project-name demo
```

When no `--cookbook` is provided, the runner randomly selects one of four theme
modes for each generation: default no-cookbook, `figma_65cm_default`,
`figma_colorblock_modern`, or `figma_lime_serif_grid`. Use
`--cookbook default` to force the built-in no-cookbook theme.

For local smoke tests without DeepSeek:

```bash
python3 ${SKILL_DIR}/scripts/api_ppt.py generate postppt.json --project-name demo --renderer local
```

For dry runs:

```bash
python3 ${SKILL_DIR}/scripts/api_ppt.py generate input.md --project-name demo --dry-run
```

For live runs that should prime provider context cache before planning and SVG generation:

```bash
python3 ${SKILL_DIR}/scripts/api_ppt.py generate postppt.json --project-name demo --cache-prime --svg-workers 6 --svg-batch-size 5
```

For named cookbook folders that include reusable assets:

```bash
python3 ${SKILL_DIR}/scripts/api_ppt.py generate postppt.json --project-name demo --cookbook figma_65cm_default
```

## Automation Contract

- First `#` heading is the deck title.
- The parser automatically adds a cover slide and a closing slide.
- Normal `##` headings become content slides.
- No section-header slides are generated.
- Content before the first `##` is preserved as source front matter and is not merged into the cover slide.
- Under the `创新技术` `##` section, each `###` heading becomes an independent content slide.
- Other `###` and deeper headings remain inside the current content slide body.
- No Eight Confirmations.
- No role-switch blocking.
- No default layout-template flow.
- HTTP service is intentionally deferred until the caller provides the API protocol.
- v1 quality policy is report-only: SVG quality errors are recorded but do not block export unless the exporter fails.
- v1 chart policy is scan-only: chart pages are reported but not automatically coordinate-calibrated.

## Core Artifacts

Each generated project writes:

```text
project/
├── sources/input.md
├── slide_manifest.json
├── slide_manifest.md
├── design_plan.json
├── design_plan.md
├── spec_lock.json
├── spec_lock.md
├── svg_output/*.svg
├── notes/total.md
├── svg_quality_report.txt
├── logs/usage.jsonl
├── logs/llm_transcript.jsonl
├── logs/transcripts/
├── result.json
├── svg_final/
└── exports/*.pptx
```

`design_plan.json` and `spec_lock.json` are the automation source of truth. `design_spec.md` and `spec_lock.md` remain as compatibility/readability files for existing tools and humans.

## Asset Layer To Preserve

The old interactive workflow is no longer the main execution path, but these repository assets remain core:

| Asset | Path | Purpose |
| --- | --- | --- |
| Canvas formats | `scripts/config.py`, `references/canvas-formats.md` | Dimensions and viewBox contracts |
| Chart templates | `templates/charts/` | Visualization references and chart patterns |
| Icon library | `templates/icons/` | Built-in SVG icon inventory |
| SVG constraints | `references/shared-standards.md` | PPT-safe SVG rules |
| Quality checker | `scripts/svg_quality_checker.py` | Report SVG compatibility issues |
| Post-processing | `scripts/finalize_svg.py` | Embed icons/images and normalize SVG |
| Exporter | `scripts/svg_to_pptx.py` | Export native editable PPTX plus SVG reference PPTX |

## Main Scripts

| Script | Purpose |
| --- | --- |
| `${SKILL_DIR}/scripts/api_ppt.py` | Thin CLI for automation generation |
| `${SKILL_DIR}/scripts/ppt_automation/` | Automation core package |
| `${SKILL_DIR}/scripts/svg_quality_checker.py` | Report SVG issues |
| `${SKILL_DIR}/scripts/total_md_split.py` | Split `notes/total.md` |
| `${SKILL_DIR}/scripts/finalize_svg.py` | Post-process SVGs |
| `${SKILL_DIR}/scripts/svg_to_pptx.py` | Export PPTX |
| `${SKILL_DIR}/scripts/source_to_md/*.py` | Optional source conversion helpers |

## Model Usage

- Qwen is the default provider for `design_plan/spec_lock` and speaker notes. DeepSeek direct Anthropic-compatible API is used for per-slide SVG generation in live mode, and can still be used as a planner fallback with a larger `PPT_MASTER_DEEPSEEK_PLAN_MAX_TOKENS` budget.
- SVG generation produces one independent direct API request per slide; no Claude Code CLI process is used in this branch.
- `--svg-workers` is the true SVG concurrency limit. `--svg-batch-size` only groups pages for log/reporting batch metadata; it does not reserve a worker slot for a whole batch.
- SVG/spec font choices are preserved for the primary editable PPTX export. Post-processing also builds a temporary `svg_final_sourcehan/` variant and exports a Source Han version (`思源宋体` titles, `思源黑体` body text) without changing `svg_final/`.
- All live prompt families start with a byte-stable `PPT_MASTER_COMMON_PREFIX_V1` deck prefix: fixed rules, canvas, style, source Markdown, and compact slide manifest.
- The common prefix must not include project paths, timestamps, logs, current page numbers, or random values.
- Cache prime is enabled by default in API-style live runs. It sends low-output ACK requests for stable shared prefixes before live model work; SVG generation waits briefly after the shared-prefix prime before scheduling the first slide batch so the first batch can hit provider cache when the provider has materialized it.
- Spec planning retries are enabled by default: `PPT_MASTER_SPEC_RETRIES=2` retries the whole `design_plan/spec_lock` provider request when marker pairs are missing or JSON is invalid. Do not salvage corrupted spec content; regenerate it.
- Cookbooks may be single markdown files or named folders under `templates/cookbooks/`. Folder cookbooks should keep the markdown at `<theme_id>/<theme_id>.md` or `<theme_id>/cookbook.md` and store screenshots/assets/notes alongside it.
- Default-candidate Figma cookbooks must preserve an evidence pack: native screenshots for all requested frames, a contact sheet, representative Figma metadata/design-context evidence, local reusable assets, and notes about missing/truncated captures.
- Cookbook markdown injected into prompts must not include local path lists, `Reference set:` sections, Figma URLs, or MCP asset URLs. Keep those in asset notes only; the prompt-facing cookbook should summarize provenance as visual DNA, motifs, frame count, and limitations.
- Downloaded/copied input images must be described in `images/image_manifest.json` with filename, alt text, width, height, aspect ratio, orientation, byte size, and MIME type so SVG generation can choose correct image frame ratios and `meet`/`slice` behavior.
- Theme color policy: extra HEX colors are allowed for richness, but the locked primary accent must remain the dominant non-neutral accent on every slide.
- Layout diversity is semantic, not quota-based: `design_plan` should prefer specific archetypes and include `layout_family`, `layout_signature`, `visual_structure`, and `why_this_layout` per slide.
- Usage is appended to `logs/usage.jsonl`; legacy `logs/api_ppt.log` is also written for compatibility.
- Full live LLM prompts and responses are written to `logs/llm_transcript.jsonl` plus `logs/transcripts/` for audit. Secrets are redacted before writing.
- API keys must come from CLI args or environment variables and must not be written to tracked docs or project artifacts.

## Legacy References

The old Strategist / Executor / Image_Generator references are retained as design knowledge and technical examples only. They are not mandatory execution gates for automation mode.

## Related Workflow

Read `workflows/api-automation.md` for detailed local/API automation behavior.
