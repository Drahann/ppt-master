# API Service

FastAPI production shell for the current PPT Master DeepSeek direct API pipeline.

The service intentionally keeps the existing production API paths so callers can switch from the old service by changing only the host port from `3001` to `3003`.

## Concurrency Model

Redis is used for:

- async job queue and job status
- DeepSeek account leases
- runner start stagger
- metrics snapshots

The DeepSeek account pool is job-level, not SVG-turn-level:

- default account capacity: 2 concurrent jobs
- default account capacity: 40 SVG slots
- current production job request: 18 SVG workers

With the current two-server deployment, each node normally carries 5 accounts
and 10 concurrent jobs. The external load balancer spreads work across two
nodes for 20 total jobs.

## Runner

The runner calls:

```bash
python skills/ppt-master/scripts/api_ppt.py generate <source.md> \
  --renderer deepseek \
  --planner-provider qwen \
  --notes-provider qwen \
  --qwen-model qwen3.6-plus \
  --qwen-max-tokens 65536 \
  --qwen-timeout 900 \
  --cache-prime \
  --svg-workers 18 \
  --svg-batch-size 4 \
  --svg-model deepseek-v4-pro[1m] \
  --svg-repair-model deepseek-v4-flash \
  --svg-timeout 1200 \
  --svg-retries 1
```

DeepSeek keys are injected from the account lease into child process environment variables, not passed on the command line.

Cache prime is enabled through the API environment:

```bash
PPT_API_CACHE_PRIME=1
```

Spec planning retries are enabled through the child process environment:

```bash
PPT_MASTER_SPEC_RETRIES=2
PPT_MASTER_SPEC_RETRY_BACKOFF_SECONDS=8
```

These retries regenerate the entire `design_plan/spec_lock` response when the
model returns missing marker pairs or invalid JSON. They do not try to salvage a
corrupted spec payload.

When the planner provider is DeepSeek, this primes the shared deck context before
the single-stage design plan/spec lock call, including spec-only jobs. SVG
generation performs a separate prime for the shared SVG prompt prefix and waits
briefly before scheduling the first slide batch so batch one can reuse the
provider cache when it is available.

SVG generation is scheduled per slide. `--svg-workers` is the actual concurrent
direct API request limit; `--svg-batch-size` only keeps logical batch metadata in
logs and does not bind a worker slot to a whole batch.
