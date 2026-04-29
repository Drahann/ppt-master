#!/bin/sh
set -eu

if [ -n "${PPT_CLAUDE_REDIS_PASSWORD:-}" ]; then
  exec redis-server /usr/local/etc/redis/redis.conf --requirepass "$PPT_CLAUDE_REDIS_PASSWORD"
fi

exec redis-server /usr/local/etc/redis/redis.conf
