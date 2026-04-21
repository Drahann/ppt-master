# PPT Master API Redis Job Mode

This API supports two response modes:

- `responseMode=sync`: legacy behavior. The HTTP request waits for PPT generation, upload, and optional callback.
- `responseMode=async`: Redis-backed job mode. The API creates a job, returns `job_id`, and background workers execute the generation.

## Required Redis Configuration

```env
REDIS_URL=redis://redis:6379/0
PPT_REDIS_KEY_PREFIX=ppt
PPT_API_ASYNC_WORKERS=15
```

`docker-compose.yml` includes a Redis service and wires `REDIS_URL` into `ppt-master-api`.

## Async Request Example

```json
{
  "report_id": "demo-001",
  "title": "Demo PPT",
  "content": "# Demo\n\nPPT source markdown.",
  "responseMode": "async",
  "callbackMode": "none",
  "batchMode": "parallel",
  "parallelBatchWorkers": 3,
  "batchPartition": "anchor_even"
}
```

`anchor_even` means: use the first 2 pages as the anchor batch, then split the remaining pages into near-even follow-up groups with a target size around 6 pages.

Response:

```json
{
  "success": true,
  "report_id": "demo-001",
  "pptUrl": null,
  "slideCount": 0,
  "title": "Demo PPT",
  "callback": null,
  "status": "queued",
  "job_id": "job_...",
  "pollingUrl": "/api/jobs/job_..."
}
```

## Job APIs

```text
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/artifacts
POST /api/jobs/{job_id}/cancel
```

Job states:

```text
accepted
queued
running
succeeded
failed
cancelled
```

## Callback Modes

- `callbackMode=auto`: call the configured report callback after PPT upload.
- `callbackMode=defer`: generate and upload PPT, but do not callback. The caller should aggregate PDF/Word/PPT links and callback once.
- `callbackMode=none`: same no-callback behavior, intended for tests or polling-only clients.

Use `callbackMode=defer` for rag-agent when PPT starts in parallel with PDF and Word generation.

## Redis LLM Slots

When `REDIS_URL` is configured, `qwen_ppt_runner.py` uses Redis slot leases for LLM stages instead of local files. Without Redis, it falls back to the existing file-slot backend.

Slot keys:

```text
ppt:llm:slot:{stage}:{index}
ppt:llm:slotmeta:{stage}:{index}
ppt:llm:waiting:{stage}
```

## Dynamic SVG Budget

Static SVG slots remain the default. To enable TPM-derived dynamic SVG concurrency, set:

```env
PPT_API_LLM_BUDGET_TPM=15000000
PPT_API_LLM_TARGET_UTILIZATION=0.75
PPT_API_LLM_MIN_SVG_CONCURRENCY=1
PPT_API_LLM_HARD_MAX_SVG_CONCURRENCY=32
PPT_API_LLM_EWMA_ALPHA=0.2
PPT_API_LLM_TPM_PACING_ENABLED=1
PPT_API_LLM_PACING_WINDOW_SECONDS=60
PPT_API_LLM_PACING_SAFETY_FACTOR=1.15
PPT_API_LLM_DEFAULT_SVG_RESERVE_TOKENS=700000
```

The runner records observed token-per-minute EWMA in Redis:

```text
ppt:llm:ewma:svg:tpm
ppt:llm:ewma:{stage}:{model}
```

Formula:

```text
global_svg_concurrency = floor(PPT_API_LLM_BUDGET_TPM * PPT_API_LLM_TARGET_UTILIZATION / observed_svg_worker_tpm)
```

The result is clamped by `PPT_API_LLM_MIN_SVG_CONCURRENCY` and `PPT_API_LLM_HARD_MAX_SVG_CONCURRENCY`.

TPM pacing is separate from slot concurrency. Before a new SVG turn starts, the runner reserves an estimated token budget in a rolling Redis window. If the current window is full, the turn waits instead of creating a new provider-side TPM spike.
