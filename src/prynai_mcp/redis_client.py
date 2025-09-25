from __future__ import annotations
from typing import Optional
from redis.asyncio import Redis
from .config import settings
import anyio

_redis: Optional[Redis] = None
_lock = anyio.Lock()

async def ensure_redis() -> Redis:
    global _redis
    if _redis is None:
        async with _lock:
            if _redis is None:
                _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
                await _redis.ping()
    return _redis

async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
