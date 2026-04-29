# API Service

FastAPI production shell for the current PPT Master Claude pipeline.

The service intentionally keeps the existing production API paths so callers can switch from the old service by changing only the host port from `3001` to `3003`.

## Concurrency Model

Redis is used for:

- async job queue and job status
- DeepSeek/Claude account leases
- metrics snapshots

The DeepSeek/Claude account pool is job-level, not SVG-turn-level:

- default account capacity: 2 concurrent jobs
- default account capacity: 24 SVG slots
- default job request: 12 SVG workers

With those defaults, one account carries two jobs and a 10-account pool carries twenty jobs.

## Runner

The runner calls:

```bash
python skills/ppt-master/scripts/api_ppt.py generate <source.md> \
  --renderer claude \
  --planner-provider qwen \
  --notes-provider qwen \
  --qwen-model qwen3.6-plus \
  --qwen-max-tokens 65536 \
  --qwen-timeout 900 \
  --cache-prime \
  --svg-workers 12 \
  --svg-batch-size 3 \
  --claude-effort max \
  --claude-timeout 1200 \
  --claude-retries 1
```

DeepSeek keys are injected from the account lease into child process environment variables, not passed on the command line.
