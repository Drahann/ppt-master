# Automation Runner

This document covers the local Qwen-based automation runner for PPT Master.

## `qwen_ppt_runner.py`

Generate a PPT Master project from a JSON request by combining deterministic repo scripts with staged Qwen Code CLI sessions.

```bash
python3 skills/ppt-master/scripts/qwen_ppt_runner.py path/to/request.json
```

Stop active local runner jobs and their `qwen.CMD` / `node` subprocess chain:

```bash
python3 skills/ppt-master/scripts/stop_qwen_runner.py --dry-run
python3 skills/ppt-master/scripts/stop_qwen_runner.py --include-orphans
python3 skills/ppt-master/scripts/stop_qwen_runner.py --match debugtxt
```

Request shape:

```json
{
  "job_id": "local-test-001",
  "source_md_path": "C:/replace/with/your/source.md",
  "project_name": "my_deck",
  "canvas_format": "ppt169",
  "project_base_dir": "projects",
  "model": "qwen3.6-plus",
  "review_model": "qwen3-max",
  "batch_mode": "auto",
  "batch_size": 8,
  "rules": {
    "template_mode": "free",
    "include_cover": true,
    "include_ending": true,
    "include_toc": false,
    "include_section_headers": false,
    "content_density": "moderately_high",
    "faithful_to_source": true,
    "highlight_key_points": true,
    "pagination": {
      "default": "each_h2_one_slide",
      "expand_h2_titles": ["创新技术", "产业验证"],
      "expand_rule": "each_h3_one_slide_no_parent_h2_slide"
    }
  }
}
```

Behavior:
- Creates a project under `project_base_dir`
- Imports the markdown into `sources/` with copy semantics
- Builds a deterministic slide plan from markdown headings
- Treats resource-only H2 sections such as `相关图片信息` as image resources instead of slide pages
- Precomputes real chart-template references from `templates/charts/charts_index.json`
- Precomputes per-slide `chunk` icon candidates from the real icon library
- Precomputes a slide content digest so the model starts from structured source notes instead of raw markdown only
- Runs five isolated Qwen stages:
  - `spec_generation`: writes `design_spec.md`
  - `spec_review`: re-reads the generated spec in a separate session and repairs icon/template issues
  - `svg_generation`: generates `svg_output/`
  - `notes_generation`: writes `notes/total.md` after SVG generation has finished
  - `svg_review`: repairs SVG naming, XML, and local layout/render issues in a separate session
- Uses batched serial SVG generation automatically for long decks by default
  - `batch_mode=auto`: enable batching when page count exceeds the threshold
  - `batch_mode=always`: always use batched serial SVG generation
  - `batch_mode=never`: force legacy single-session SVG generation
  - `batch_size`: slides per batch
- During `svg_generation`, explicitly loads:
  - `executor-base.md`
  - the selected style file (`executor-consultant.md` or `executor-general.md`)
  - `shared-standards.md`
  - `image-layout-spec.md`
  - `svg_design_cookbook.md`
  - `svg_anchor_context.json`
- Sends prompts over stdin instead of packing the full task into the command line
- Explicitly allows the Qwen tools needed for file creation and shell execution
- Auto-resumes the active session when template selection or Eight Confirmations block the workflow
- Forces the Strategist stage to read `strategist.md`, `design_spec_reference.md`, `charts_index.json`, and `executor-base.md` up front
- Writes deterministic review input with invalid-icon candidates and unknown chart-template findings before the review stage
- Rejects invalid `design_spec.md` outputs when required sections are missing, chart template names are fake, icon planning is too thin, or icon names do not exist in the locked library
- Rejects invalid SVG outputs when XML parsing fails, icon coverage is too low, `data-icon` names do not exist in the locked icon library, or emoji are used instead of proper icons
- Runs `svg_quality_checker.py`, `total_md_split.py`, `finalize_svg.py`, and `svg_to_pptx.py -s final`

Output:

```json
{
  "job_id": "local-test-001",
  "status": "succeeded",
  "project_path": "W:/.../projects/my_deck_ppt169_20260417",
  "qwen_session_id": "svg-review-session-uuid",
  "native_pptx_path": "W:/.../exports/my_deck.pptx",
  "svg_pptx_path": "W:/.../exports/my_deck_svg.pptx",
  "log_path": "W:/.../runner/runner.log",
  "error": null
}
```

Runner artifacts are written to `<project_path>/runner/`:
- `request.json`
- `slide_plan.json`
- `slide_content_digest.json`
- `available_chart_templates.json`
- `available_icon_candidates.json`
- `available_icon_inventory.json`
- `svg_executor_context.json`
- `svg_anchor_context.json`
- `spec_prompt.txt`
- `review_prompt.txt`
- `bootstrap_prompt.txt`
- `notes_prompt.txt`
- `svg_review_prompt.txt`
- `spec_review_input.json`
- `spec_review_report.json`
- `svg_review_input.json`
- `svg_review_report.json`
- `svg_quality_report.txt`
- `stage_sessions.json`
- `spec_turn_*.stdout.txt`
- `spec_turn_*.stderr.txt`
- `spec_turn_*.assistant.txt`
- `review_turn_*.stdout.txt`
- `review_turn_*.stderr.txt`
- `review_turn_*.assistant.txt`
- `svg_batch_*.stdout.txt` / `svg_batch_*.stderr.txt` / `svg_batch_*.assistant.txt` when batched SVG mode is active
- `notes_turn_*.stdout.txt`
- `notes_turn_*.stderr.txt`
- `notes_turn_*.assistant.txt`
- `svg_review_turn_*.stdout.txt`
- `svg_review_turn_*.stderr.txt`
- `svg_review_turn_*.assistant.txt`
- `qwen_turn_*.stdout.txt`
- `qwen_turn_*.stderr.txt`
- `qwen_turn_*.assistant.txt`
- `result.json`
- `runner.log`

Notes:
- `model` drives the Strategist, SVG, and Notes stages
- `review_model` drives both isolated review stages; if omitted, it defaults to `qwen3-max`
- The returned `qwen_session_id` is the final SVG review session id; all stage session ids are written to `stage_sessions.json`
- Completion is accepted only when the stage sentinel appears and the generated files pass deterministic validation
- To stop a stuck local run cleanly on Windows, prefer `stop_qwen_runner.py` instead of killing only the outer `python` process
- The current local test prompt locks the deck to a light theme; adjust the prompt later if you want dark-theme experiments
- The runner still does not score final visual polish automatically; visual review remains manual

See the example request at `skills/ppt-master/scripts/assets/qwen_runner_request.example.json`.
