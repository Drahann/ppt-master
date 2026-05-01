# API Service

FastAPI production shell for the current PPT Master Claude pipeline.

The service intentionally keeps the existing production API paths so callers can switch from the old service by changing only the host port from `3001` to `3003`.

## Concurrency Model

Redis is used for:

- async job queue and job status
- DeepSeek/Claude account leases
- runner start stagger
- metrics snapshots

The DeepSeek/Claude account pool is job-level, not SVG-turn-level:

- default account capacity: 2 concurrent jobs
- default account capacity: 24 SVG slots
- current production job request: 12 SVG workers

With the current two-server deployment, each node normally carries 5 accounts
and 10 concurrent jobs. The external load balancer spreads work across two
nodes for 20 total jobs.

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
  --svg-batch-size 4 \
  --claude-effort max \
  --claude-timeout 1200 \
  --claude-retries 1
```

DeepSeek keys are injected from the account lease into child process environment variables, not passed on the command line.

SVG generation is scheduled per slide. `--svg-workers` is the actual concurrent
Claude process limit; `--svg-batch-size` only keeps logical batch metadata in
logs and does not bind a worker slot to a whole batch.
