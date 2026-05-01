# Claude PPT Production Shell

This directory mirrors the current production PPT API shape, but targets the DeepSeek-backed Claude Code PPT generator in this repository.

## Ports

- Existing production PPT service: keep using host port `3001`.
- New DeepSeek/Claude PPT service: host port `3003`, container port `3000`.
- Dedicated Redis for this service: host port `6380`.

The business API paths stay the same:

- `POST /api/report-to-ppt`
- `POST /api/generate-ppt`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/artifacts`
- `POST /api/jobs/{job_id}/cancel`
- `GET /healthz`
- `GET /metrics`
- `GET /dashboard`

## Account Pool

Copy the example and replace the five keys for this server:

```bash
mkdir -p secrets
cp deploy/production/deepseek_claude_account_pool.example.json secrets/deepseek_claude_account_pool.json
```

This working tree also contains ignored ready-to-copy files when generated locally:

- `.env.api`
- `secrets/deepseek_claude_account_pool.json`
- `deploy/production/server-claude.env.api`
- `deploy/production/deepseek_claude_account_pool.json`
- `deploy/production/deepseek_claude_account_pool_06_10.json`

Default policy:

- 5 DeepSeek/Claude accounts per server.
- Each account allows 2 concurrent PPT jobs.
- Each account has 24 SVG slots.
- Each PPT job requests 8 SVG slots by default.

That makes one server admit ten concurrent jobs. The two-server production
deployment uses external load balancing and admits twenty concurrent jobs total.

Use accounts 01-05 on the first server and accounts 06-10 on the second server.
Do not deploy the same five-account pool to both servers.

## Runner Start Stagger

The API applies a Redis-backed process-start gate before launching `api_ppt.py`. With the production env below, runner processes start at least `4s` apart globally, then add `0-12s` random jitter per job:

```env
PPT_API_RUNNER_START_STAGGER_ENABLED=1
PPT_API_RUNNER_START_STAGGER_SECONDS=4
PPT_API_RUNNER_START_JITTER_SECONDS=12
PPT_API_RUNNER_START_STAGGER_SCOPE=global
```

For `qwen3.6-plus` spec generation, the Qwen request timeout is intentionally longer than the old 5-minute default:

```env
PPT_API_QWEN_TIMEOUT=900
```

## Start API And Redis

The root `docker-compose.yml` starts both the API container and the dedicated
Redis container for this service.

```bash
cp deploy/production/server-claude.env.api.example .env.api
docker compose --env-file .env.api up -d --build
```

If you run Redis outside the root compose stack, make sure `.env.api` points to
that external Redis URL instead of `ppt-master-claude-redis`.

## Start API Only

```bash
docker compose --env-file .env.api up -d --build ppt-master-claude-api
```

Then verify:

```bash
curl http://127.0.0.1:3003/healthz
curl http://127.0.0.1:3003/metrics
```

Expected checks:

- `redis.available` is `true`.
- `apiKeyPool.configured` is `true`.
- `apiKeyPool.required` is `true`.
- `apiKeyPool.accounts` has 5 entries on a normal production node.

## Callback

When generation finishes, the service uploads the result zip to COS and posts the same callback payload shape as the existing service:

```json
{
  "success": "success",
  "msg": "报告上传成功",
  "data": {
    "reportId": "...",
    "fileUrl": "...",
    "pptUrl": "...",
    "wordUrl": "..."
  }
}
```

Set `REPORT_CALLBACK_URL` in `.env.api`.
