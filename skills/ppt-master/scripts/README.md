# PPT Master Scripts

This directory now centers on the automation-first Markdown/JSON to PPTX pipeline.

## Primary Entry Point

```bash
python3 scripts/api_ppt.py generate input.md --project-name demo
python3 scripts/api_ppt.py generate postppt.json --project-name demo --json-field content
python3 scripts/api_ppt.py generate postppt.json --project-name demo --renderer local
python3 scripts/api_ppt.py generate input.md --project-name demo --dry-run
```

`api_ppt.py` is a thin CLI. The implementation lives in `scripts/ppt_automation/`.

## Automation Package

| Module | Responsibility |
| --- | --- |
| `ppt_automation/parser.py` | Markdown/JSON input parsing; `#` title and `##` slide boundaries |
| `ppt_automation/project.py` | Project directories, manifests, plan/lock mirrors, `result.json` |
| `ppt_automation/planner.py` | DeepSeek direct API and deterministic local design plan |
| `ppt_automation/svg_generator.py` | Local SVG smoke renderer and Claude Code per-slide SVG generation |
| `ppt_automation/pipeline.py` | End-to-end orchestration, quality report, chart scan, notes, export |
| `ppt_automation/usage.py` | `logs/usage.jsonl` and compatibility `logs/api_ppt.log` |

## Core Outputs

```text
project/
├── sources/input.md
├── slide_manifest.json
├── slide_manifest.md
├── design_plan.json
├── design_plan.md
├── spec_lock.json
├── spec_lock.md
├── svg_output/
├── notes/total.md
├── svg_quality_report.txt
├── logs/usage.jsonl
├── result.json
├── svg_final/
└── exports/*.pptx
```

## DeepSeek / Claude Code Environment

Live mode uses DeepSeek's Anthropic-compatible endpoint and Claude Code CLI for per-slide SVG generation.

```bash
set DEEPSEEK_API_KEY=sk-...
set ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
set ANTHROPIC_AUTH_TOKEN=<DeepSeek key>
set ANTHROPIC_MODEL=deepseek-v4-pro[1m]
set ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]
set ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]
set ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
set CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash
set CLAUDE_CODE_EFFORT_LEVEL=high
```

The automation package sets the Anthropic variables for child Claude Code processes. Do not write API keys into project files.

## Reused Asset/Export Scripts

| Area | Scripts |
| --- | --- |
| Quality | `svg_quality_checker.py` |
| Notes | `total_md_split.py` |
| SVG post-processing | `finalize_svg.py`, `svg_finalize/*` |
| PPTX export | `svg_to_pptx.py`, `svg_to_pptx/*` |
| Source conversion | `source_to_md/pdf_to_md.py`, `doc_to_md.py`, `excel_to_md.py`, `ppt_to_md.py`, `web_to_md.py` |
| Image tools | `image_gen.py`, `analyze_images.py` |
| Template import | `pptx_template_import.py`, `template_import/*` |

## Manual Export Pipeline

If SVGs and notes already exist:

```bash
python3 scripts/total_md_split.py <project_path>
python3 scripts/finalize_svg.py <project_path>
python3 scripts/svg_to_pptx.py <project_path> -s final
```

Always export from `svg_final/` using `-s final`.

## v1 Limits

- HTTP service remains a placeholder until protocol details are provided.
- Quality errors are reported, not auto-retried.
- Chart pages are scanned, not auto-calibrated.
- Local renderer is a smoke-test path, not final design-quality rendering.
