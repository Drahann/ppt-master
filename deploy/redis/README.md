# Claude PPT Redis

This Redis instance is dedicated to the DeepSeek/Claude PPT API service. It is intentionally separate from the existing production PPT service so both services can run on the same server.

Default host port: `6380`

```bash
cd deploy/redis
cp redis.env.example redis.env
docker compose --env-file redis.env -f docker-compose.redis.yml up -d
```

Use this URL from the API container when Redis runs on the Docker host:

```env
PPT_REDIS_URL=redis://:change-me@host.docker.internal:6380/0
```

Use this URL when Redis runs inside the same Compose network:

```env
PPT_REDIS_URL=redis://ppt-master-claude-redis:6379/0
```
