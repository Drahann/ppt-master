# API Automation Mode

API Automation Mode is the primary PPT Master workflow. It turns Markdown or JSON-contained Markdown into a timestamped project and exported PPTX without the old interactive Strategist/Executor confirmation gates.

## Scope

- Input is Markdown, or JSON containing a Markdown string.
- First `#` heading is the deck title.
- The parser automatically adds a cover slide and a closing slide.
- Normal `##` headings become content slides.
- No section-header slides are generated.
- Content before the first `##` is preserved as front matter and is not merged into the cover slide.
- Under the `创新技术` `##` section, each `###` heading becomes an independent content slide.
- Other `###` and deeper headings stay inside the current slide body.
- No Eight Confirmations.
- No layout-template dependency.
- No AI images by default.
- HTTP service is deferred until the external protocol is provided.

## Commands

Dry run:

```bash
python skills/ppt-master/scripts/api_ppt.py generate input.md --project-name demo --dry-run
```

JSON input using `content`:

```bash
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo
```

Local deterministic smoke mode:

```bash
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --renderer local
```

DeepSeek-backed mode:

```bash
set DEEPSEEK_API_KEY=sk-...
python skills/ppt-master/scripts/api_ppt.py generate input.md --project-name demo
```

Parallel SVG generation plus cache priming:

```bash
set DEEPSEEK_API_KEY=sk-...
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --cache-prime --svg-workers 6 --svg-batch-size 5
```

## Core Artifacts

```text
project/
├── sources/input.md
├── slide_manifest.json
├── slide_manifest.md
├── design_plan.json
├── design_plan.md
├── design_spec.md
├── spec_lock.json
├── spec_lock.md
├── prompts/
├── svg_output/
├── notes/total.md
├── svg_quality_report.txt
├── logs/usage.jsonl
├── logs/api_ppt.log
├── logs/llm_transcript.jsonl
├── logs/transcripts/
├── result.json
├── svg_final/
└── exports/*.pptx
```

`design_plan.json` and `spec_lock.json` are the primary automation artifacts. Markdown mirrors remain for existing tooling and human review.

## Runtime Behavior

- DeepSeek direct API generates `design_plan/spec_lock` and one SVG per slide in live mode; speaker notes default to Qwen.
- Direct live prompts for plan/lock, notes, and SVG start with a byte-stable `PPT_MASTER_COMMON_PREFIX_V1` containing fixed rules, canvas, style, source Markdown, and a compact slide manifest.
- SVG prompts then append SVG rules, `design_plan.json`, `spec_lock.json`, and current page Markdown last.
- The common prefix must not include project paths, timestamps, random paths, logs, current page numbers, or other run-specific values.
- `--cache-prime` sends a low-output ACK request for the common prefix before live work. This adds one small request but improves cache locality for decks with many pages.
- Color quality checks allow additional HEX colors as palette richness. They warn only when the dominant non-neutral accent drifts away from the locked primary theme color.
- Layout diversity is semantic, not quota-based: `design_plan` should prefer specific archetypes and include `layout_family`, `layout_signature`, `visual_structure`, and `why_this_layout` per slide.
- Quality checking is report-only in v1.
- Chart calibration is scan-only in v1.
- Export still uses the proven three-step pipeline: `total_md_split.py`, `finalize_svg.py`, `svg_to_pptx.py -s final`.

## Usage Logging

All model calls append JSONL records to `logs/usage.jsonl`.

DeepSeek records include available token/cache fields from the API response.

SVG records include slide filename, prompt size, output size, duration, success/failure, and DeepSeek usage fields. If a direct API call times out or fails, the failure is logged and a failure `result.json` is written.

Full live LLM prompts and responses are also written to `logs/llm_transcript.jsonl` with body files under `logs/transcripts/`. This is intended for prompt audit: checking whether the agent produced unnecessary summaries, performed avoidable work, or ignored output-only constraints. API keys are redacted before writing transcript files.

## v1 Limits

- No HTTP service implementation.
- SVG generation retries failed pages by default; use `--svg-retries` to override the retry count.
- No automatic chart coordinate calibration.
- No automatic template selection.
- No AI image generation.
- Local renderer is only for pipeline smoke testing, not final design quality.
