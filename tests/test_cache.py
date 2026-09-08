"""Tests for the Redis cache layer.

Runs against a real Redis, not a mock: the whole point of these tests is that
TTL, SCAN and serialisation behave the way Redis actually behaves. Start one
with `docker compose up -d redis` before running locally; in CI the service
container covers it.
"""

from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio

from app import cache

# Use a throwaway database so a failing test can never wipe dev data.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


@pytest_asyncio.fixture(autouse=True)
async def clean_redis():
    cache._client = None  # force a fresh client bound to the test DB
    client = cache.get_client()
    await client.flushdb()
    yield
    await client.flushdb()
    await cache.close_client()


@pytest.mark.asyncio
async def test_second_call_does_not_reach_the_source():
    calls = {"n": 0}

    @cache.cached("jobs:list", ttl=60)
    async def list_jobs(status: str) -> list[dict]:
        calls["n"] += 1
        return [{"id": 1, "status": status}]

    first = await list_jobs("open")
    second = await list_jobs("open")

    assert first == second
    assert calls["n"] == 1, "second call should have been served from Redis"


@pytest.mark.asyncio
async def test_different_arguments_are_cached_separately():
    calls = {"n": 0}

    @cache.cached("jobs:list", ttl=60)
    async def list_jobs(status: str) -> list[dict]:
        calls["n"] += 1
        return [{"status": status}]

    await list_jobs("open")
    await list_jobs("closed")

    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_entry_expires_after_ttl():
    calls = {"n": 0}

    @cache.cached("jobs:short", ttl=1)
    async def list_jobs() -> list[dict]:
        calls["n"] += 1
        return [{"id": 1}]

    await list_jobs()
    await asyncio.sleep(1.2)
    await list_jobs()

    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_invalidate_clears_only_its_own_prefix():
    @cache.cached("jobs:list", ttl=60)
    async def list_jobs() -> list[dict]:
        return [{"id": 1}]

    @cache.cached("companies:list", ttl=60)
    async def list_companies() -> list[dict]:
        return [{"id": 2}]

    await list_jobs()
    await list_companies()

    removed = await cache.invalidate("jobs:list")
    client = cache.get_client()

    assert removed == 1
    assert await client.dbsize() == 1, "companies cache must survive"


@pytest.mark.asyncio
async def test_redis_outage_does_not_break_the_endpoint(monkeypatch):
    """Fail-open: a dead cache degrades latency, not availability."""
    calls = {"n": 0}

    @cache.cached("jobs:list", ttl=60)
    async def list_jobs() -> list[dict]:
        calls["n"] += 1
        return [{"id": 1}]

    cache._client = None
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6399/0")  # nothing listening

    result = await list_jobs()

    assert result == [{"id": 1}]
    assert calls["n"] == 1
