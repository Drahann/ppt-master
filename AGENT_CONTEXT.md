# PPT Master Agent Context

This file is the fast onboarding brief for future agent sessions in this
workspace. It is intentionally written in ASCII-friendly English so it remains
readable from Windows PowerShell even when UTF-8 files without BOM are displayed
incorrectly.

Authoritative rule: for PPT generation or repair work, read
`skills/ppt-master/SKILL.md` first. If any older README, role reference, or
legacy AGENTS summary conflicts with `SKILL.md`, follow `SKILL.md`.

## 0. Current Operating State

Last updated: 2026-05-01.

Active production branch:

```text
codex/automation-stress-20260429
```

Remote normally used for this branch:

```text
https://github.com/Drahann/ppt-master.git
```

Recent high-value commits on this branch:

| Commit | Meaning |
| --- | --- |
| `020b1fc3` | Added the FastAPI production shell around Claude PPT generation. |
| `6233a905` | Added Redis-backed runner start stagger and jitter. |
| `01f76c21` | Made the Qwen planning/spec timeout configurable. |
| `bd988487` | Restored Claude prompt-cache locality by sharing job-level Claude config. |
| `59a376db` | Changed default SVG concurrency to `8 workers x batch size 4`. |
| `ba2144d0` | Fixed API job image asset copying from `source_files/` into project `images/`. |
| `b11d7ae4` | Changed one production node to a five-account pool and ten job workers. |
| `ca7740bc` | Ignored split real account-pool JSON files. |

Current production shape:

- The old production PPT service and this Claude/DeepSeek service coexist.
- Existing service keeps its own port, usually host `3001`.
- This service maps container port `3000` to host `3003`.
- `docker-compose.yml` starts both the API container and its own Redis container.
- Redis default host port is `6380` unless overridden.
- Two physical servers sit behind external load balancing.
- Each server should use five DeepSeek/Claude accounts.
- Each account allows two concurrent PPT jobs and has 24 SVG slots.
- Per server capacity is therefore `5 accounts x 2 jobs = 10 jobs`.
- Across two servers the intended total is 20 concurrent jobs.
- Do not put the same five accounts on both servers.

Current default generation policy for production:

- Planner: Qwen via DashScope, model `qwen3.6-plus`.
- Notes: Qwen via DashScope.
- SVG renderer: Claude Code using DeepSeek Anthropic-compatible endpoint.
- Claude model: `deepseek-v4-pro[1m]`.
- Claude flash model: `deepseek-v4-flash`.
- SVG concurrency: `PPT_API_SVG_WORKERS=8`.
- SVG batch size: `PPT_API_SVG_BATCH_SIZE=4`.
- Cache priming: enabled.
- Claude effort: `max`.
- Claude timeout: 1200 seconds.
- Qwen timeout: 900 seconds.
- Notes generation runs in parallel with SVG generation, so after SVG completes
  the pipeline can proceed directly into post-processing once notes have also
  finished.

Important ignored local files:

| Path | Meaning |
| --- | --- |
| `.env.api` | Real local/server API env. Ignored by git. |
| `deploy/production/server-claude.env.api` | Real production env copy. Ignored by git. |
| `deploy/production/deepseek_claude_account_pool.json` | Real first-server account pool, accounts 01-05. Ignored by git. |
| `deploy/production/deepseek_claude_account_pool_06_10.json` | Real second-server account pool, accounts 06-10. Ignored by git. |
| `secrets/deepseek_claude_account_pool.json` | Runtime account-pool file mounted into the container. Ignored by git. |

Tracked examples should stay sanitized:

- `deploy/production/server-claude.env.api.example`
- `deploy/production/deepseek_claude_account_pool.example.json`

## 1. What This Repository Is

PPT Master is a local-first AI presentation generation workflow package. It is
not a normal web app or service scaffold.

The goal is to turn Markdown, JSON-contained Markdown, or converted source
documents into a real editable PowerPoint file. The output should contain native
PowerPoint objects via DrawingML: shapes, text boxes, pictures, charts, and
groups. It should not be a deck made from full-slide screenshots.

Current default workflow:

```text
Markdown/JSON input
-> slide_manifest
-> design_plan.json + spec_lock.json
-> per-slide SVG
-> svg_quality_report
-> notes/total.md
-> svg_final
-> exports/*.pptx
```

Implementation note: in current production code, notes are generated in parallel
with the per-slide SVG stage, then post-processing waits for both.

The old Strategist -> Image_Generator -> Executor -> Eight Confirmations flow is
legacy reference material only. Those files still contain useful design and SVG
knowledge, but they are not the default execution path unless the user asks for
that older workflow.

## 2. New Session Read Order

1. `AGENTS.md` - repo entry rules.
2. `AGENT_CONTEXT.md` - this current-state overview.
3. `skills/ppt-master/SKILL.md` - current workflow authority.
4. `skills/ppt-master/workflows/api-automation.md` - automation details.
5. Read these only when needed:
   - `api_service/README.md`
   - `deploy/production/README.md`
   - `skills/ppt-master/references/shared-standards.md`
   - `skills/ppt-master/references/canvas-formats.md`
   - `skills/ppt-master/templates/icons/README.md`
   - `skills/ppt-master/scripts/README.md`

Do not bulk-open the icon tree. It contains thousands of SVG files.

## 3. Core Commands

This workspace is on Windows. In PowerShell, use `python` if `python3` is not
available.

```bash
# Default generation from Markdown
python skills/ppt-master/scripts/api_ppt.py generate input.md --project-name demo

# JSON input, default JSON field is "content"
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --json-field content

# Deterministic local smoke test, no DeepSeek/Qwen/Claude Code calls
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --renderer local

# Dry run: project, source, manifest, plan/lock, and prompts only
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --dry-run

# Live run with cache priming and current production SVG concurrency
python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --cache-prime --svg-workers 8 --svg-batch-size 4
```

Manual export pipeline for an existing generated project:

```bash
python skills/ppt-master/scripts/total_md_split.py <project_path>
python skills/ppt-master/scripts/finalize_svg.py <project_path>
python skills/ppt-master/scripts/svg_to_pptx.py <project_path> -s final
```

Rules:

- If `svg_output/` changes, rerun `finalize_svg.py` and `svg_to_pptx.py -s final`.
- If `notes/total.md` changes, rerun all three manual export steps.
- Never use a file copy as a substitute for `finalize_svg.py`.
- Never export directly from `svg_output/`; exports must use `svg_final/` with `-s final`.

## 4. Input Parsing Rules

Primary entry point: `skills/ppt-master/scripts/api_ppt.py`.

Implementation package: `skills/ppt-master/scripts/ppt_automation/`.

Parser behavior:

- Input may be `.md`, or `.json` with a Markdown string field.
- The first level-1 heading (`#`) becomes the deck title.
- If no level-1 heading is found, the title becomes `Untitled Deck`.
- At least one level-2 heading (`##`) is required.
- A cover slide and closing slide are added automatically.
- Normal level-2 headings become content slides.
- The special level-2 section intended to mean "Innovation Technology" expands
  each level-3 heading (`###`) into its own slide. Inspect `parser.py` before
  changing this because some files display mojibake in PowerShell.
- Content before the first level-2 heading is preserved as front matter and is
  not merged into the cover slide.
- `--max-slides` limits content slides only; cover and closing still exist.

## 5. Automation Code Map

`api_ppt.py` is a thin CLI. It builds `GenerationOptions` and calls
`ppt_automation.pipeline.generate()`.

Important modules:

| Path | Responsibility |
| --- | --- |
| `ppt_automation/parser.py` | Reads Markdown/JSON and builds `Deck` / `Slide`. |
| `ppt_automation/assets.py` | Materializes Markdown images into project `images/`; handles HTTP(S), local relative images, and API job `source_files/`. |
| `ppt_automation/project.py` | Creates timestamped projects and writes source, manifest, plan/lock mirrors, and `result.json`. |
| `ppt_automation/planner.py` | Builds `design_plan` and `spec_lock`; supports DeepSeek, Qwen, and deterministic local mode. |
| `ppt_automation/svg_generator.py` | Writes prompt files; local SVG smoke renderer; Claude Code per-slide SVG generation. |
| `ppt_automation/pipeline.py` | End-to-end orchestration: assets, parsing, cache prime, plan, SVG, entity cleanup, quality check, chart scan, notes, export. |
| `ppt_automation/usage.py` | Writes `logs/usage.jsonl`, `logs/api_ppt.log`, and full prompt/response transcripts. |
| `ppt_automation/config.py` | Shared paths, canvas formats, default models, and provider endpoints. |

Production API modules:

| Path | Responsibility |
| --- | --- |
| `api_service/app.py` | FastAPI routes, sync/async request handling, Redis queue/status, account lease, callback trigger. |
| `api_service/runner.py` | Converts API settings into the `api_ppt.py generate` child process command and environment. |
| `api_service/account_pool.py` | Redis-backed DeepSeek/Claude account pool and per-job account leases. |
| `api_service/job_store.py` | Redis-backed job records for queued/running/succeeded/failed/cancelled status. |
| `api_service/markdown_assets.py` | API request preprocessor that downloads/copies incoming Markdown images to the job `source_files/` directory. |
| `api_service/storage.py` | COS upload and report callback. |
| `api_service/models.py` | API request/response schemas. |

Provider behavior:

- DeepSeek Anthropic-compatible API can be used for plan, notes, and the Claude
  Code backend.
- Qwen/DashScope OpenAI-compatible API can be used with
  `--planner-provider qwen` and `--notes-provider qwen`.
- Claude Code CLI is used only for per-slide SVG generation in live mode.
- Claude SVG calls must return exactly one complete SVG document and no prose.
- Shared prompt prefix: `PPT_MASTER_COMMON_PREFIX_V1`.
- The shared prefix must be byte-stable: no project paths, timestamps, logs,
  random values, or current page numbers.
- `--cache-prime` sends low-output ACK-style requests before live work.
- In production, `PPT_MASTER_CLAUDE_CONFIG_SCOPE=job` is intentional. Cache
  prime and all SVG batches for the same PPT job share the same job-level Claude
  config directory. This avoids the poor cache hit rate seen when config was
  isolated per batch.
- Do not switch back to per-batch Claude config unless the user explicitly
  chooses file-lock isolation over prompt-cache locality.
- The old `C:\Users\...\ .claude.json` lock problem came from multiple jobs
  sharing one global Claude config file. The current fix is job-scoped config:
  each PPT job has its own Claude config directory, while batches inside that
  same job share it.
- API keys must come from CLI args or environment variables. Do not write them
  into docs, logs, project artifacts, or transcripts.

## 6. Production API Shell

The production API shell intentionally mirrors the existing production service
interface closely.

Routes:

| Route | Meaning |
| --- | --- |
| `POST /api/report-to-ppt` | Existing production-compatible report request shape. |
| `POST /api/generate-ppt` | Direct PPT generation request shape. |
| `GET /api/jobs/{job_id}` | Redis job status. |
| `GET /api/jobs/{job_id}/artifacts` | Completed artifact/result pointer. |
| `POST /api/jobs/{job_id}/cancel` | Mark queued/running job as cancelled. |
| `GET /healthz` | Health, Redis, and account pool status. |
| `GET /metrics` | In-memory API metrics plus Redis job/account snapshots. |
| `GET /dashboard` | Simple dashboard page. |

Important runtime env:

```env
PPT_API_HOST_PORT=3003
PPT_API_MAX_CONCURRENT_JOBS=10
PPT_API_ASYNC_WORKERS=10
PPT_REDIS_URL=redis://ppt-master-claude-redis:6379/0
PPT_REDIS_KEY_PREFIX=ppt-claude
PPT_API_DEEPSEEK_ACCOUNT_POOL_FILE=/app/secrets/deepseek_claude_account_pool.json
PPT_API_REQUIRE_ACCOUNT_POOL=1
PPT_API_SVG_WORKERS=8
PPT_API_SVG_BATCH_SIZE=4
PPT_MASTER_CLAUDE_CONFIG_ROOT=/app/tmp/claude-code-config
PPT_MASTER_CLAUDE_CONFIG_SCOPE=job
```

Redis is used for:

- API job queue/status.
- Account-pool leases.
- Runner start stagger.
- Metrics snapshots.

Account pool behavior:

- The account lease is job-level, not SVG-batch-level.
- A PPT job acquires one DeepSeek/Claude account before launching `api_ppt.py`.
- The account's key and model settings are injected into the child process
  environment by `api_service/runner.py`.
- Each job requests `svg_workers` slots from the selected account.
- With current defaults, each job requests 8 slots; each account has 24 slots,
  but `max_concurrent_jobs=2` caps the account at two jobs.
- Selection prefers the emptiest available account.

Deployment shape:

```bash
docker compose --env-file .env.api build
docker compose --env-file .env.api up -d
curl http://127.0.0.1:3003/healthz
curl http://127.0.0.1:3003/metrics
```

When cloning from GitHub is unavailable on a server, a safe fallback is to
archive the branch locally and copy the tarball to the server. If GitHub access
works, prefer normal `git pull` on `codex/automation-stress-20260429`.

Two-server account split:

- Server A: use accounts 01-05.
- Server B: use accounts 06-10.
- The second local file is
  `deploy/production/deepseek_claude_account_pool_06_10.json`; copy it to the
  server as `secrets/deepseek_claude_account_pool.json` or equivalent runtime
  secret path.
- Keep split real JSON files ignored. Do not commit real keys.

## 7. Generated Project Anatomy

Generated projects usually live under:

```text
projects/<project_name>_ppt169_YYYYMMDD_HHMMSS/
```

Core artifacts:

| Path | Meaning |
| --- | --- |
| `sources/input.md` | Actual Markdown used for generation; image URLs may be rewritten to local files. |
| `slide_manifest.json/.md` | Deck structure, slide titles, kinds, slugs, and SVG filenames. |
| `design_plan.json` | Soft visual plan; machine source of truth for design guidance. |
| `design_plan.md` / `design_spec.md` | Human-readable mirror and compatibility file. |
| `spec_lock.json` | Hard visual lock: canvas, colors, typography, icons, SVG rules. |
| `spec_lock.md` | Human-readable lock mirror. |
| `prompts/design_plan_prompt.md` | Prompt used for plan/lock generation. |
| `prompts/svg_prefix.md` | Shared SVG prompt prefix. |
| `prompts/svg_pages/*.md` | Final per-slide SVG prompts. |
| `svg_output/*.svg` | Raw SVG generated by model or local renderer. |
| `svg_quality_report.txt` | SVG/PPT compatibility report; v1 is report-only. |
| `logs/chart_scan.txt` | Chart scan; v1 does not auto-calibrate coordinates. |
| `notes/total.md` | Full speaker notes document. |
| `notes/*.md` | Per-slide notes split from `total.md`. |
| `svg_final/*.svg` | Post-processed SVG used for export. |
| `exports/*.pptx` | Native editable PPTX and `_svg.pptx` visual reference deck. |
| `result.json` | Run status, paths, quality summary, warnings, and error if failed. |

## 8. SVG And PPT Hard Rules

Before writing or fixing SVG, use `shared-standards.md`.

Key rules:

- For `ppt169`, use `width="1280" height="720" viewBox="0 0 1280 720"`.
- Draw the page background explicitly with a full-canvas `<rect>`.
- Use inline attributes only.
- Forbidden: `rgba()`, `<style>`, `class`, `<foreignObject>`, `<script>`,
  `<animate*>`, `<textPath>`, `<mask>`, `@font-face`, HTML named entities,
  and `<g opacity>`.
- Use `fill-opacity` or `stroke-opacity` instead of `rgba()`.
- Escape XML reserved characters in text and attributes.
- Keep one logical text line in one `<text>` element with inline `<tspan>`
  children. Do not split adjacent fragments into separate `<text>` elements.
- Group logical units with plain `<g>` so PowerPoint users can move/edit them.
- Prefer icon placeholders like
  `<use data-icon="chunk-filled/rocket" x="100" y="100" width="32" height="32" fill="#1D4ED8"/>`.
- One deck should use one stylistic icon library. `simple-icons` is only for
  real brand logos.
- Use local images via `href="../images/file.ext"` with `preserveAspectRatio`.
- Do not reference external HTTP URLs or absolute local paths in SVG.
- Shadows are not default decoration. Use them only for real elevated elements.
- For chart arcs, arrows, and coordinates, calculate precisely. Use
  `svg_position_calculator.py` when needed.

## 9. Assets And Libraries

- `skills/ppt-master/templates/layouts/`: legacy/optional template resources.
  Automation mode does not depend on them by default.
- `skills/ppt-master/templates/charts/`: 57 SVG visualization templates.
  `charts_index.json` is the lookup source of truth.
- `skills/ppt-master/templates/icons/`: 11,600+ icons across
  `chunk-filled`, `tabler-filled`, `tabler-outline`, `phosphor-duotone`, and
  `simple-icons`.
- `skills/ppt-master/scripts/source_to_md/`: source conversion helpers for PDF,
  DOCX, Excel, PPT, and web pages.
- `skills/ppt-master/scripts/image_backends/`: AI image backend adapters.
- `skills/ppt-master/scripts/template_import/`: PPTX template import tooling.
- `examples/`: shareable example projects.
- `projects/`: user workspace, usually ignored by git, can contain large
  intermediate outputs and logs.

## 10. Current Workspace Snapshot

Last inspected: 2026-05-01.

Most complete current run:

```text
projects/postppt_qwen36plus_12w_b3_max_ppt169_20260429_103503
```

From `result.json`:

- `ok: true`
- `renderer: claude`
- `slides: 32`
- Native PPTX:
  `exports/postppt_qwen36plus_12w_b3_max_ppt169_20260429_103503_20260429_110608.pptx`
- SVG reference PPTX:
  `exports/postppt_qwen36plus_12w_b3_max_ppt169_20260429_103503_20260429_110608_svg.pptx`
- `svg_output/*.svg`: 32 files
- `svg_final/*.svg`: 32 files
- `notes/*.md`: 33 files, including `total.md`
- Images: 10 real image assets plus `image_manifest.json/.md`
- Quality: 0 errors, 2 files with warnings. The warnings are oversized source
  images displayed at smaller dimensions; they do not block export.
- Chart scan: no marked chart pages and no chart-like pages.
- `logs/usage.jsonl` labels: `input_images`, `deepseek_cache_prime`,
  `qwen_plan`, `claude_cache_prime`, `claude_parallel`, `claude_batch`,
  `claude_svg`, `qwen_notes`.
- `logs/transcripts/`: 141 transcript files.

Current project caveats:

- `slide_manifest.json` title is `Untitled Deck`. The source likely did not
  contain a parseable level-1 heading. Confirm the intended title before formal
  delivery.
- Many Chinese titles and bodies in the manifest, filenames, and logs appear as
  mojibake. Before editing content, inspect `postppt.json` and
  `sources/input.md` encoding.
- The IDE-open files mentioned in the user context belong to this run's
  prompt/spec/transcript debugging surface.

Recent production/stress observations:

- `projects/postppt_qwen36plus_12w_b3_max_stress01_ppt169_20260429_141135`
  is a useful local/stress comparison run. Its `sources/input.md` references
  `../images/...`, and its `images/` directory contains the expected 10
  business image assets.
- `projects/longying..._ppt169_20260429_110326` and
  `projects/longying..._ppt169_20260429_123630` were server/API runs before
  the image-copy fix. Their `sources/input.md` kept `source_files/...`
  references and their project `images/` directories were empty. The root cause
  was container/job path resolution: API preprocessing put images under
  `/app/tmp/api-jobs/<job>/source_files`, but the generation pipeline did not
  resolve image paths relative to the input `source.md` directory.
- The fix in `ba2144d0` changed `ppt_automation/assets.py` and
  `ppt_automation/pipeline.py` so local relative images are copied from the
  input file directory into project `images/` and rewritten to `../images/...`.
  A dry-run against real job
  `.tmp/api-jobs/job_1777466160982_50622fb60c/source.md` copied 10 images and
  logged `copied=10, missing=0`.
- The server run
  `projects/longying..._ppt169_20260429_123630` showed the prompt-cache
  locality fix working: observed cache ratio was about 89.83%, up from the
  earlier poor server cache behavior around 40.20%.
- That same run still had two SVG retries where Claude returned no complete
  `<svg>` document. These were not script-washable incomplete SVGs; there was
  no usable SVG tree to repair. Treat those as model/retry events.

## 11. How To Continue Work On The Current Project

If the user wants specific slides changed:

1. Read `slide_manifest.md` to map slide numbers to SVG filenames.
2. Read the relevant `prompts/svg_pages/<stem>.md` to understand the original
   generation prompt.
3. Edit `svg_output/<file>.svg` or regenerate that slide.
4. Run cleanup and QA:

```bash
python skills/ppt-master/scripts/clean_svg_entities.py <project_path>/svg_output --validate
python skills/ppt-master/scripts/svg_quality_checker.py <project_path> --format ppt169 --export --output <project_path>/svg_quality_report.txt
```

5. Rerun post-processing and export:

```bash
python skills/ppt-master/scripts/finalize_svg.py <project_path>
python skills/ppt-master/scripts/svg_to_pptx.py <project_path> -s final
```

If the user wants speaker notes changed:

1. Edit `notes/total.md`.
2. Run `total_md_split.py`.
3. Run `finalize_svg.py`.
4. Run `svg_to_pptx.py <project_path> -s final`.

If the user wants a full regeneration:

1. Confirm input encoding, level-1 deck title, and level-2 slide boundaries.
2. Run `--dry-run` or `--renderer local` for a structure smoke test.
3. Run the live renderer only after the structure is correct.
4. Verify `result.json`, `svg_quality_report.txt`, `logs/chart_scan.txt`, and
   the exported PPTX files.

## 12. Verification Checklist

Before claiming a PPT task is complete, collect evidence:

- `result.json` is `ok: true`.
- `svg_quality_report.txt` reports `With errors: 0`.
- Count of `svg_output/*.svg` equals `slide_manifest.json.slide_count`.
- Count of `svg_final/*.svg` equals `slide_manifest.json.slide_count`.
- `exports/` contains both a new native `.pptx` and a new `_svg.pptx`.
- If the request entered through the API and has images, `sources/input.md`
  should reference `../images/...`, `images/` should contain the copied files,
  and `logs/usage.jsonl` should include `input_images` with expected `copied`
  or `downloaded` counts and `missing: 0`.
- Image warnings are only size recommendations, not structural SVG failures.
- If chart pages changed, check `logs/chart_scan.txt`; calibrate coordinates
  when needed.
- If text or notes changed, spot-check the PPTX for editable text, correct
  grouping, and readable Chinese.

For production/API work, also verify:

- `GET /healthz` shows Redis available.
- `apiKeyPool.configured` is true.
- On a single production node, `apiKeyPool.accounts` should normally have five
  entries.
- `GET /metrics` reflects queue/running/completed jobs and account-pool
  snapshots.

## 13. Explicit Limits

- Quality errors are reported, not automatically retried.
- Chart pages are scanned, not automatically calibrated.
- AI image generation is not part of the default automation path.
- Layout template selection/copying is not part of the default automation path.
- `--renderer local` is a pipeline smoke test, not final design quality.
- The API service exists and is production-shaped, but it is a shell around the
  existing CLI pipeline. Do not bypass the CLI pipeline unless the user asks for
  a deeper service refactor.
- Do not add dependencies unless explicitly requested.
- Do not write API keys, model tokens, or private URLs into tracked files,
  generated docs, or transcripts.

## 14. Common Failure Entry Points

- Missing DeepSeek/Qwen key: inspect CLI args and env vars; failures usually
  land in `result.json.error`.
- Missing Claude Code CLI: install/update `@anthropic-ai/claude-code`; the
  script preflight reports this clearly.
- Poor Claude cache hit rate in API runs: confirm
  `PPT_MASTER_CLAUDE_CONFIG_SCOPE=job`. Per-batch config isolation improves
  lock isolation but destroys useful cache locality.
- `.claude.json` lock/file contention: should not recur with job-scoped Claude
  config. If it does, inspect `PPT_MASTER_CLAUDE_CONFIG_ROOT`,
  `PPT_MASTER_CLAUDE_CONFIG_SCOPE`, and runner logs before changing account
  scheduling.
- Empty image placeholders in API-generated PPTs: inspect
  `sources/input.md`, project `images/`, and `logs/usage.jsonl`. If input still
  references `source_files/...`, the image-copy fix is not present or the wrong
  branch/container image is running.
- `/root/rag-agent/media/mermaid/...` references are not the business images.
  Those absolute local mermaid paths are intentionally ignored.
- Qwen spec/planner timeout: production uses `PPT_API_QWEN_TIMEOUT=900`; older
  300-second timeouts can fail on long spec generation.
- SVG XML failure: run `clean_svg_entities.py --validate`; look for HTML named
  entities, bare `&`, or unescaped `<`.
- Claude response without a complete `<svg>`: not script-washable unless there
  is a complete SVG tree. Usually let the existing retry path handle it.
- PPTX export failure: confirm export is from `svg_final/` and all SVG files
  parse as XML.
- Chinese mojibake: inspect input file encoding and JSON field content first;
  generated filenames may already have inherited mojibake.
- GitHub clone/fetch failure on a server: first distinguish protocol vs network.
  HTTP/2 framing errors can be worked around with
  `git -c http.version=HTTP/1.1 ...`; port 443 timeouts are network/proxy
  problems, not git branch problems.
- Too many files: use `rg`, `rg --files`, or targeted directory listings. Do
  not open the full icon library.
