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
PPT_API_LIVE_USAGE_ENABLED=1
PPT_API_LIVE_USAGE_POLL_SECONDS=10
PPT_API_LIVE_USAGE_LOG_INTERVAL_SECONDS=60
PPT_API_LIVE_TPM_WINDOW_SECONDS=60
PPT_API_LIVE_TPM_ADMISSION_ENABLED=1
PPT_API_SVG_LIVE_TPM_BYPASS_COMPLETION_GUARD=1
PPT_API_SVG_LIVE_TPM_STARTUP_RESERVE_SECONDS=15
PPT_API_SVG_QWEN_START_STAGGER_SECONDS=12
PPT_API_QWEN_START_STAGGER_PER_STAGE=1
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

When live usage observation is enabled, running CLI turns also stream actual usage events into Redis from chat-recording telemetry. Metrics expose the current rolling SVG TPM, and SVG admission can prefer that live rolling window plus a bounded startup reserve over the older completion-bucket-only estimate.

Local start staggering is an additional per-runner guard. It spaces out qwen CLI process starts inside one PPT job, so one runner cannot launch several SVG qwen turns in the same few seconds even if global slots are available.

## Global Qwen Account Pool

The centralized SVG scheduler can lease Qwen credentials from a Redis-backed global pool. Use this when multiple API servers share one Redis and should draw from the same accounts dynamically instead of pinning accounts per server.

If no account pool is configured, behavior is unchanged: SVG/spec/notes stages use `PPT_API_QWEN_API_KEY` and `PPT_API_QWEN_BASE_URL`.

Recommended 3-server shape:

```env
PPT_API_MAX_CONCURRENT_JOBS=20
PPT_API_ASYNC_WORKERS=20
PPT_API_SVG_SCHEDULER_ENABLED=1
PPT_SERVER_ID=server-1
REDIS_URL=redis://shared-redis:6379/0
PPT_API_QWEN_ACCOUNT_POOL_FILE=/app/secrets/qwen_account_pool.json
```

Account pool file format:

```json
{
  "accounts": [
    {
      "account_id": "qwen-01",
      "api_key": "sk-...",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "model": "qwen3.6-plus",
      "tpm_limit": 5000000,
      "target_utilization": 0.9,
      "max_parallel_turns": 10,
      "enabled": true
    }
  ]
}
```

The scheduler writes only `account_id` and non-secret state to metrics/logs. Full API keys are copied into per-worker request files only for the worker process that owns the lease.

Metrics expose:

```text
/metrics.apiKeyPool.accounts[*].live_tpm_60s
/metrics.apiKeyPool.accounts[*].active_leases
/metrics.apiKeyPool.accounts[*].cooldown_until
/metrics.apiKeyPool.accounts[*].enabled
/metrics.apiKeyPool.accounts[*].granted
/metrics.apiKeyPool.accounts[*].denied
/metrics.apiKeyPool.accounts[*].last_error
/metrics.svgScheduler.account_id_counts
```
