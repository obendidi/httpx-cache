from __future__ import annotations

import gzip
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from httpx_cache import (
    AsyncCacheTransport,
    CacheMissError,
    MemoryCache,
    SqliteCache,
    SyncCacheTransport,
    wrap,
)


def test_sync_force_caching_extensions_and_post_body_hash(
    http_mod: ModuleType,
    cache: SqliteCache | MemoryCache,
) -> None:
    calls = 0

    def handler(request: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(
            200,
            headers={"cache-control": "no-store"},
            json={"call": calls, "body": request.content.decode()},
        )

    transport = SyncCacheTransport(
        http_mod.MockTransport(handler),
        cache=cache,
        policy="force",
        cache_post=True,
    )
    with http_mod.Client(transport=transport) as client:
        r1 = client.post("https://api.example.com/chat", json={"q": "alpha"})
        r2 = client.post("https://api.example.com/chat", json={"q": "alpha"})
        r3 = client.post("https://api.example.com/chat", json={"q": "beta"})

    assert calls == 2
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
    assert r3.extensions["from_cache"] is False
    assert r1.extensions["cache_key"] == r2.extensions["cache_key"]
    assert r1.extensions["cache_key"] != r3.extensions["cache_key"]
    assert r1.json() == r2.json()
    assert r3.json()["call"] == 2

    # Deleting by response.extensions["cache_key"] invalidates that exact entry
    assert cache.delete(r1.extensions["cache_key"]) is True


async def test_async_force_caching_and_custom_key_fn(
    http_mod: ModuleType,
    cache: SqliteCache | MemoryCache,
) -> None:
    calls = 0

    async def handler(request: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, text=f"resp-{calls}")

    transport = AsyncCacheTransport(
        http_mod.MockTransport(handler),
        cache=cache,
        policy="force",
        key_fn=lambda req: f"path:{req.url.path}",
    )
    async with http_mod.AsyncClient(transport=transport) as client:
        r1 = await client.get("https://api.example.com/items?ts=1")
        r2 = await client.get("https://api.example.com/items?ts=2")

    assert calls == 1
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
    assert r2.extensions["cache_key"] == "path:/items"
    assert r2.text == "resp-1"


def test_sync_streaming_caches_only_on_complete_read_and_preserves_gzip(
    http_mod: ModuleType,
    sqlite_cache: SqliteCache,
) -> None:
    calls = 0
    raw_gzipped = gzip.compress(b"hello streaming world")

    def handler(request: Any) -> Any:
        nonlocal calls
        calls += 1

        def chunks() -> Iterator[bytes]:
            mid = len(raw_gzipped) // 2
            yield raw_gzipped[:mid]
            yield raw_gzipped[mid:]

        return http_mod.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=chunks(),
        )

    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=sqlite_cache,
        policy="force",
    )

    with client:
        # Aborted partial stream must NOT populate the cache
        with client.stream("GET", "https://example.com/stream") as partial:
            first_chunk = next(partial.iter_raw())
            assert first_chunk
        assert sqlite_cache.stats().entries == 0

        # Full stream read populates the cache
        with client.stream("GET", "https://example.com/stream") as r1:
            assert r1.extensions["from_cache"] is False
            collected = b"".join(r1.iter_bytes())
        assert collected == b"hello streaming world"
        assert sqlite_cache.stats().entries == 1

        # Subsequent stream hit AND regular get() hit decode gzip cleanly
        with client.stream("GET", "https://example.com/stream") as r2:
            assert r2.extensions["from_cache"] is True
            assert b"".join(r2.iter_bytes()) == b"hello streaming world"

        r3 = client.get("https://example.com/stream")
        assert r3.extensions["from_cache"] is True
        assert r3.content == b"hello streaming world"

    assert calls == 2


async def test_async_streaming_caches_only_on_complete_read(
    http_mod: ModuleType,
    sqlite_cache: SqliteCache,
) -> None:
    calls = 0

    async def handler(request: Any) -> Any:
        nonlocal calls
        calls += 1

        async def chunks() -> AsyncIterator[bytes]:
            yield b"chunk-1-"
            yield b"chunk-2"

        return http_mod.Response(200, stream=chunks())

    client = wrap(
        http_mod.AsyncClient(transport=http_mod.MockTransport(handler)),
        cache=sqlite_cache,
        policy="force",
    )
    async with client:
        # Aborted async stream does not cache
        async with client.stream("GET", "https://example.com/astream") as partial:
            async for _ in partial.aiter_bytes():
                break
        assert (await sqlite_cache.astats()).entries == 0

        # Full async stream caches
        async with client.stream("GET", "https://example.com/astream") as r1:
            data = b"".join([c async for c in r1.aiter_bytes()])
        assert data == b"chunk-1-chunk-2"
        assert (await sqlite_cache.astats()).entries == 1

        # Cached hit works for both stream and normal get
        r2 = await client.get("https://example.com/astream")
        assert r2.extensions["from_cache"] is True
        assert r2.content == b"chunk-1-chunk-2"

    assert calls == 2


def test_rfc9111_etag_304_end_to_end_sync(http_mod: ModuleType, tmp_path: Path) -> None:
    calls = 0

    def handler(request: Any) -> Any:
        nonlocal calls
        calls += 1
        if request.headers.get("if-none-match") == '"abc"':
            return http_mod.Response(
                304,
                headers={"etag": '"abc"', "cache-control": "max-age=60"},
            )
        return http_mod.Response(
            200,
            headers={"etag": '"abc"', "cache-control": "no-cache"},
            content=b"fresh-body",
        )

    cache = SqliteCache(tmp_path / "etag.sqlite3")
    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=cache,
        policy="rfc9111",
    )
    with client:
        r1 = client.get("https://example.com/resource")
        assert r1.extensions["from_cache"] is False
        assert r1.content == b"fresh-body"

        # Because initial response had no-cache + ETag, 2nd call sends If-None-Match -> 304
        r2 = client.get("https://example.com/resource")
        assert r2.extensions["from_cache"] is True
        assert r2.extensions["revalidated"] is True
        assert r2.content == b"fresh-body"

        # 304 updated cache-control to max-age=60 -> 3rd call hits cache without upstream call
        r3 = client.get("https://example.com/resource")
        assert r3.extensions["from_cache"] is True
        assert r3.content == b"fresh-body"

    assert calls == 2
    cache.close()


async def test_rfc9111_etag_304_end_to_end_async(http_mod: ModuleType, tmp_path: Path) -> None:
    calls = 0

    async def handler(request: Any) -> Any:
        nonlocal calls
        calls += 1
        if request.headers.get("if-none-match") == '"v1"':
            return http_mod.Response(304, headers={"etag": '"v1"', "cache-control": "max-age=60"})
        return http_mod.Response(
            200,
            headers={"etag": '"v1"', "cache-control": "no-cache"},
            content=b"async-body",
        )

    cache = SqliteCache(tmp_path / "aetag.sqlite3")
    client = wrap(
        http_mod.AsyncClient(transport=http_mod.MockTransport(handler)),
        cache=cache,
        policy="rfc9111",
    )
    async with client:
        r1 = await client.get("https://example.com/r")
        r2 = await client.get("https://example.com/r")
        r3 = await client.get("https://example.com/r")

    assert calls == 2
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
    assert r2.extensions["revalidated"] is True
    assert r3.extensions["from_cache"] is True
    assert r3.content == b"async-body"
    cache.close()


def test_replay_mode_record_then_offline_playback_and_miss(
    http_mod: ModuleType,
    tmp_path: Path,
) -> None:
    db = tmp_path / "cassette.sqlite3"
    record_calls = 0

    def record_handler(request: Any) -> Any:
        nonlocal record_calls
        record_calls += 1
        return http_mod.Response(200, json={"echo": request.content.decode()})

    # Step 1: Record GET + POST into SQLite cassette
    with SqliteCache(db) as rec_cache:
        recorder = wrap(
            http_mod.Client(transport=http_mod.MockTransport(record_handler)),
            cache=rec_cache,
            policy="force",
            ttl=0.001,  # expires immediately, yet replay must still serve it
            cache_post=True,
        )
        with recorder:
            recorder.get("https://api.example.com/ping")
            recorder.post("https://api.example.com/llm", json={"prompt": "hello"})

    assert record_calls == 2

    # Step 2: Replay offline — transport fails loudly if ever called
    def forbidden_handler(request: Any) -> Any:
        raise AssertionError("Replay mode must never call upstream transport")

    with SqliteCache(db) as play_cache:
        replayer = wrap(
            http_mod.Client(transport=http_mod.MockTransport(forbidden_handler)),
            cache=play_cache,
            policy="replay",
        )
        with replayer:
            r_get = replayer.get("https://api.example.com/ping")
            r_post = replayer.post("https://api.example.com/llm", json={"prompt": "hello"})
            assert r_get.extensions["from_cache"] is True
            assert r_post.extensions["from_cache"] is True
            assert r_post.json() == {"echo": '{"prompt":"hello"}'}

            with pytest.raises(CacheMissError) as exc_info:
                replayer.post("https://api.example.com/llm", json={"prompt": "unseen"})
            assert "https://api.example.com/llm" in str(exc_info.value)
            assert exc_info.value.key
            assert exc_info.value.request.method == "POST"


async def test_async_replay_mode_miss_and_hit(http_mod: ModuleType) -> None:
    cache = MemoryCache()
    recorder = wrap(
        http_mod.AsyncClient(
            transport=http_mod.MockTransport(lambda req: http_mod.Response(200, text="saved"))
        ),
        cache=cache,
        policy="force",
    )
    async with recorder:
        await recorder.get("https://example.com/a")

    transport = AsyncCacheTransport(cache=cache, policy="replay", backend=http_mod.__name__)
    async with http_mod.AsyncClient(transport=transport) as replayer:
        hit = await replayer.get("https://example.com/a")
        assert hit.extensions["from_cache"] is True
        assert hit.text == "saved"

        with pytest.raises(CacheMissError):
            await replayer.get("https://example.com/missing")


def test_streaming_post_request_body_and_vary_key_fn(http_mod: ModuleType) -> None:
    from httpx_cache import default_key_fn

    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, content=req.read())

    cache = MemoryCache()

    def gen(payload: bytes) -> Iterator[bytes]:
        yield payload[:3]
        yield payload[3:]

    with (
        SyncCacheTransport(
            http_mod.MockTransport(handler),
            cache=cache,
            policy="force",
            cache_post=True,
            key_fn=lambda req: default_key_fn(req, vary_headers=("x-tenant",)),
        ) as transport,
        http_mod.Client(transport=transport) as client,
    ):
        r1 = client.post(
            "https://api.example.com/rpc",
            headers={"x-tenant": "a"},
            content=gen(b"abcdef"),
        )
        r2 = client.post(
            "https://api.example.com/rpc",
            headers={"x-tenant": "a"},
            content=gen(b"abcdef"),
        )
        r3 = client.post(
            "https://api.example.com/rpc",
            headers={"x-tenant": "b"},
            content=gen(b"abcdef"),
        )

    assert calls == 2
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
    assert r3.extensions["from_cache"] is False
    assert r2.content == b"abcdef"


async def test_async_streaming_post_request_body_and_stale_eviction(
    http_mod: ModuleType,
) -> None:
    calls = 0

    async def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        body = await req.aread()
        return http_mod.Response(
            200,
            headers={"cache-control": "max-age=0"},
            content=body + f"-{calls}".encode(),
        )

    async def agen(payload: bytes) -> AsyncIterator[bytes]:
        yield payload[:2]
        yield payload[2:]

    cache = MemoryCache()
    async with (
        AsyncCacheTransport(
            http_mod.MockTransport(handler),
            cache=cache,
            policy="rfc9111",
            cache_post=True,
        ) as transport,
        http_mod.AsyncClient(transport=transport) as client,
    ):
        r1 = await client.post("https://api.example.com/a", content=agen(b"hello"))
        r2 = await client.post("https://api.example.com/a", content=agen(b"hello"))

    assert calls == 2
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is False
    assert r2.content == b"hello-2"
