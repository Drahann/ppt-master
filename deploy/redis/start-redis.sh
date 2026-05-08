#!/bin/sh
set -eu

if [ -n "${PPT_DEEPSEEK_REDIS_PASSWORD:-}" ]; then
  exec redis-server /usr/local/etc/redis/redis.conf --requirepass "$PPT_DEEPSEEK_REDIS_PASSWORD"
fi

exec redis-server /usr/local/etc/redis/redis.conf
