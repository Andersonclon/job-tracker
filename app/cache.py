"""Redis cache layer.

Fail-open by design: if Redis is down the app keeps serving, it just stops
caching. A cache outage must never become an API outage.

Cache the data-access function, not the route handler. Route handlers take
Request/Session objects that cannot be hashed into a stable cache key.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_TTL = int(os.getenv("CACHE_TTL_SECONDS", "60"))

# Arguments that must never take part in the cache key: they are per-request
# objects whose repr() changes every call, which would make every lookup a miss.
_SKIP_ARGS = {"request", "response", "db", "session", "conn"}

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    """Lazily build one connection pool for the whole process."""
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


async def close_client() -> None:
    """Call from the FastAPI lifespan shutdown hook."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _is_key_material(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool, type(None)))


def _make_key(prefix: str, args: tuple, kwargs: dict) -> str:
    payload = json.dumps([list(args), sorted(kwargs.items())], sort_keys=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


def cached(prefix: str, ttl: int = DEFAULT_TTL) -> Callable:
    """Cache the JSON-serialisable return value of an async function.

    Usage:

        @cached("jobs:list", ttl=30)
        async def list_jobs(status: str, limit: int) -> list[dict]:
            ...

    The decorated function must return something json.dumps can handle.
    For Pydantic models return [m.model_dump() for m in rows] instead.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            key_args = tuple(a for a in args if _is_key_material(a))
            key_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in _SKIP_ARGS and _is_key_material(v)
            }
            key = _make_key(prefix, key_args, key_kwargs)
            client = get_client()

            try:
                hit = await client.get(key)
                if hit is not None:
                    log.debug("cache hit %s", key)
                    return json.loads(hit)
            except redis.RedisError:
                log.warning("cache read failed, falling back to source", exc_info=True)

            result = await fn(*args, **kwargs)

            try:
                await client.set(key, json.dumps(result), ex=ttl)
            except (redis.RedisError, TypeError):
                # TypeError = the return value is not JSON-serialisable.
                # Still return it; only the caching is lost.
                log.warning("cache write failed for %s", key, exc_info=True)

            return result

        return wrapper

    return decorator


async def invalidate(prefix: str) -> int:
    """Drop every key under a prefix. Call this after any write.

    Uses SCAN, not KEYS: KEYS walks the entire keyspace in one blocking pass
    and will stall a busy Redis. SCAN is cursor-based and yields between batches.
    """
    client = get_client()
    removed = 0
    try:
        async for key in client.scan_iter(match=f"{prefix}:*", count=100):
            await client.delete(key)
            removed += 1
    except redis.RedisError:
        log.warning("cache invalidation failed for %s", prefix, exc_info=True)
    return removed
