from __future__ import annotations

import os
import time
import uuid
from typing import Any

import pytest

from httpx_cache import CacheEntry, RedisCache, wrap

REDIS_URL = os.environ.get("HTTPX_CACHE_REDIS_URL")

pytestmark = pytest.mark.skipif(
    not REDIS_URL,
    reason="Set HTTPX_CACHE_REDIS_URL to run live Redis integration tests.",
)


def _entry(body: bytes, *, expires_at: float | None = None) -> CacheEntry:
    return CacheEntry(
        status_code=200,
        headers=(("content-type", "application/json"),),
        body=body,
        expires_at=expires_at,
    )


def test_live_redis_sync_crud_ttl_and_namespace_isolation() -> None:
    assert REDIS_URL is not None
    ns1 = f"httpx_cache_test_{uuid.uuid4().hex}"
    ns2 = f"httpx_cache_test_{uuid.uuid4().hex}"

    c1 = RedisCache(redis_url=REDIS_URL, namespace=ns1)
    c2 = RedisCache(redis_url=REDIS_URL, namespace=ns2)
    try:
        c1.set("k1", _entry(b'{"a":1}'))
        c2.set("k1", _entry(b'{"a":2}'))

        g1 = c1.get("k1")
        g2 = c2.get("k1")
        assert g1 is not None and g1.body == b'{"a":1}'
        assert g2 is not None and g2.body == b'{"a":2}'
        assert c1.stats().entries == 1

        # Short TTL expiry on Redis server
        c1.set("short", _entry(b"bye", expires_at=time.time() + 0.15))
        assert c1.get("short") is not None
        time.sleep(0.25)
        assert c1.get("short") is None

        c1.clear()
        assert c1.stats().entries == 0
        # Other namespace untouched
        assert c2.get("k1") is not None
    finally:
        c1.clear()
        c2.clear()
        c1.close()
        c2.close()


async def test_live_redis_async_and_client_wrap(http_mod: Any) -> None:
    assert REDIS_URL is not None
    ns = f"httpx_cache_async_{uuid.uuid4().hex}"
    calls = 0

    async def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, json={"calls": calls})

    cache = RedisCache(redis_url=REDIS_URL, namespace=ns, default_ttl=30)
    try:
        client = wrap(
            http_mod.AsyncClient(transport=http_mod.MockTransport(handler)),
            cache=cache,
            policy="force",
        )
        async with client:
            r1 = await client.get("https://example.com/redis")
            r2 = await client.get("https://example.com/redis")

        assert calls == 1
        assert r1.extensions["from_cache"] is False
        assert r2.extensions["from_cache"] is True
        assert r2.json() == {"calls": 1}
        assert (await cache.astats()).entries == 1
    finally:
        await cache.aclear()
        await cache.aclose()
