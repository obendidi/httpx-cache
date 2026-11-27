from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from httpx_cache import (
    CacheEntry,
    CacheMissError,
    FileCache,
    JsonCache,
    MemoryCache,
    RedisCache,
    SqliteCache,
    wrap,
)
from httpx_cache.cli import main as cli_main
from httpx_cache.pytest_plugin import Cassette

# ---------------------------------------------------------------------------
# 1. In-flight request coalescing (singleflight)
# ---------------------------------------------------------------------------


async def test_async_coalescing_deduplicates_concurrent_requests(http_mod: ModuleType) -> None:
    calls = 0

    async def slow_handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return http_mod.Response(200, json={"call": calls})

    cache = MemoryCache()
    client = wrap(
        http_mod.AsyncClient(transport=http_mod.MockTransport(slow_handler)),
        cache=cache,
        policy="force",
        coalesce=True,
    )
    async with client:
        responses = await asyncio.gather(
            *(client.get("https://api.example.com/hot") for _ in range(15))
        )

    assert calls == 1
    assert all(r.json() == {"call": 1} for r in responses)
    assert sum(1 for r in responses if r.extensions["from_cache"]) == 14


def test_sync_coalescing_deduplicates_threads_and_releases_on_error(
    http_mod: ModuleType,
) -> None:
    calls = 0
    lock = threading.Lock()

    def slow_handler(req: Any) -> Any:
        nonlocal calls
        time.sleep(0.05)
        with lock:
            calls += 1
            n = calls
        return http_mod.Response(200, json={"call": n})

    cache = MemoryCache()
    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(slow_handler)),
        cache=cache,
        policy="force",
        coalesce=True,
    )
    with client, ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: client.get("https://api.example.com/shared"), range(8))
        )

    assert calls == 1
    assert all(r.json() == {"call": 1} for r in results)

    # Error in leader must release waiters cleanly without deadlocking
    def failing_handler(req: Any) -> Any:
        raise http_mod.ConnectError("boom")

    err_client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(failing_handler)),
        cache=MemoryCache(),
        coalesce=True,
    )
    with err_client, pytest.raises(http_mod.ConnectError):
        err_client.get("https://api.example.com/fail")


# ---------------------------------------------------------------------------
# 2. Stale-if-error resilience
# ---------------------------------------------------------------------------


def test_stale_if_error_serves_stale_on_5xx_and_network_error(
    http_mod: ModuleType,
    tmp_path: Path,
) -> None:
    mode = "ok"

    def handler(req: Any) -> Any:
        if mode == "ok":
            return http_mod.Response(200, json={"v": 1})
        if mode == "503":
            return http_mod.Response(503, text="service unavailable")
        raise http_mod.ConnectError("upstream down")

    cache = SqliteCache(tmp_path / "stale.sqlite3")
    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=cache,
        policy="force",
        ttl=0.01,
        stale_if_error=True,
    )
    with client:
        r1 = client.get("https://api.example.com/data")
        assert r1.json() == {"v": 1}
        assert r1.extensions["from_cache"] is False

        time.sleep(0.02)  # entry is now expired

        mode = "503"
        r2 = client.get("https://api.example.com/data")
        assert r2.status_code == 200
        assert r2.json() == {"v": 1}
        assert r2.extensions["from_cache"] is True
        assert r2.extensions["stale"] is True

        mode = "err"
        r3 = client.get("https://api.example.com/data")
        assert r3.status_code == 200
        assert r3.json() == {"v": 1}
        assert r3.extensions["stale"] is True
    cache.close()


async def test_async_stale_if_error_respects_window(http_mod: ModuleType) -> None:
    fail = False

    async def handler(req: Any) -> Any:
        if fail:
            return http_mod.Response(502, text="bad gateway")
        return http_mod.Response(200, text="good")

    cache = MemoryCache()
    client = wrap(
        http_mod.AsyncClient(transport=http_mod.MockTransport(handler)),
        cache=cache,
        policy="force",
        ttl=0.01,
        stale_if_error=0.02,
    )
    async with client:
        await client.get("https://api.example.com/x")
        fail = True
        await asyncio.sleep(0.05)  # past ttl (0.01) + stale window (0.02)
        r = await client.get("https://api.example.com/x")
        assert r.status_code == 502
        assert r.extensions["from_cache"] is False


# ---------------------------------------------------------------------------
# 3. Per-request extensions, should_cache (GraphQL), urls_expire_after
# ---------------------------------------------------------------------------


def test_per_request_extensions_disabled_force_refresh_ttl_and_key(
    http_mod: ModuleType,
) -> None:
    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, json={"call": calls})

    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=MemoryCache(),
        policy="force",
        ttl=3600,
    )
    with client:
        r1 = client.get("https://api.example.com/item")
        r2 = client.get("https://api.example.com/item")
        assert calls == 1
        assert r1.extensions["from_cache"] is False
        assert r2.extensions["from_cache"] is True

        # Per-request disabled bypasses cache completely
        r_dis = client.get("https://api.example.com/item", extensions={"cache": {"disabled": True}})
        assert calls == 2
        assert r_dis.extensions["from_cache"] is False

        # Per-request force_refresh fetches fresh and overwrites cache
        r_ref = client.get(
            "https://api.example.com/item",
            extensions={"cache": {"force_refresh": True}},
        )
        assert calls == 3
        assert r_ref.json() == {"call": 3}

        r_after = client.get("https://api.example.com/item")
        assert calls == 3
        assert r_after.extensions["from_cache"] is True
        assert r_after.json() == {"call": 3}

        # Per-request custom key + short ttl
        r_k = client.get(
            "https://api.example.com/other",
            extensions={"cache": {"key": "custom-slot", "ttl": 0.01}},
        )
        assert r_k.extensions["cache_key"] == "custom-slot"
        time.sleep(0.02)
        r_k2 = client.get(
            "https://api.example.com/other",
            extensions={"cache": {"key": "custom-slot"}},
        )
        assert r_k2.extensions["from_cache"] is False


def test_should_cache_skips_graphql_errors_even_when_streaming(http_mod: ModuleType) -> None:
    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        payload = b'{"errors":[{"message":"rate limited"}]}' if calls == 1 else b'{"data":{"ok":1}}'

        def chunks() -> Iterator[bytes]:
            yield payload

        return http_mod.Response(200, headers={"content-type": "application/json"}, stream=chunks())

    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=MemoryCache(),
        policy="force",
        cache_post=True,
        should_cache=lambda req, resp: "errors" not in resp.json(),
    )
    with client:
        r1 = client.post("https://api.example.com/graphql", json={"query": "{ ok }"})
        assert "errors" in r1.json()
        # Error response was NOT cached -> 2nd call hits upstream and caches healthy payload
        r2 = client.post("https://api.example.com/graphql", json={"query": "{ ok }"})
        assert r2.json() == {"data": {"ok": 1}}
        assert r2.extensions["from_cache"] is False
        # 3rd call hits cache
        r3 = client.post("https://api.example.com/graphql", json={"query": "{ ok }"})
        assert r3.extensions["from_cache"] is True
        assert calls == 2


def test_urls_expire_after_patterns(http_mod: ModuleType) -> None:
    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, text=f"c-{calls}")

    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=MemoryCache(),
        policy="force",
        ttl=3600,
        urls_expire_after={
            "*/auth/*": 0,  # never cache
            "*/prices": 0.01,  # short TTL
            "*/static/*": None,  # forever
        },
    )
    with client:
        # /auth/* never cached
        a1 = client.get("https://api.example.com/auth/token")
        a2 = client.get("https://api.example.com/auth/token")
        assert a1.extensions["from_cache"] is False
        assert a2.extensions["from_cache"] is False

        # /prices expires quickly
        p1 = client.get("https://api.example.com/prices")
        p2 = client.get("https://api.example.com/prices")
        assert p1.extensions["from_cache"] is False
        assert p2.extensions["from_cache"] is True
        time.sleep(0.02)
        p3 = client.get("https://api.example.com/prices")
        assert p3.extensions["from_cache"] is False


# ---------------------------------------------------------------------------
# 4. Actionable CacheMissError diffs, scrub_headers, JsonCache & export/import
# ---------------------------------------------------------------------------


def test_cache_miss_error_suggests_closest_key_and_scrub_headers(
    http_mod: ModuleType,
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "cassette.json"
    cache = JsonCache(json_path)

    def handler(req: Any) -> Any:
        return http_mod.Response(
            200,
            headers={"set-cookie": "session=secret", "x-ok": "1"},
            json={"answer": 42},
        )

    recorder = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=cache,
        policy="force",
        cache_post=True,
        scrub_headers=("Set-Cookie",),
    )
    with recorder:
        recorder.post("https://api.example.com/v1/chat", json={"prompt": "hello"})

    # Verify JSON cassette is human-readable and Set-Cookie was scrubbed
    disk = json.loads(json_path.read_text(encoding="utf-8"))
    stored_entry = next(iter(disk["entries"].values()))
    header_names = {k.lower() for k, _ in stored_entry["headers"]}
    assert "set-cookie" not in header_names
    assert "x-ok" in header_names
    assert stored_entry["body_encoding"] == "utf-8"

    # Replay with slightly different POST body -> actionable closest-key diff
    replayer = wrap(
        http_mod.Client(),
        cache=JsonCache(json_path),
        policy="replay",
    )
    with replayer, pytest.raises(CacheMissError) as exc_info:
        replayer.post("https://api.example.com/v1/chat", json={"prompt": "different"})

    assert exc_info.value.closest_keys
    assert "same method/URL" in str(exc_info.value)


def test_cassette_json_format_and_sqlite_export_import(
    http_mod: ModuleType,
    tmp_path: Path,
) -> None:
    cassette = Cassette(tmp_path / "test.json", mode="once", format="json")
    try:
        with cassette.wrap(
            http_mod.Client(
                transport=http_mod.MockTransport(lambda req: http_mod.Response(200, text="hi"))
            )
        ) as client:
            client.get("https://example.com/one")
        assert (tmp_path / "test.json").is_file()
    finally:
        cassette.close()

    # Import that JSON into SqliteCache and export back
    db = SqliteCache(tmp_path / "imported.sqlite3")
    try:
        assert db.import_json(tmp_path / "test.json") == 1
        got = db.get("GET:https://example.com/one")
        assert got is not None and got.body == b"hi"
        out_json = tmp_path / "exported.json"
        assert db.export_json(out_json) == 1
        assert "GET:https://example.com/one" in out_json.read_text(encoding="utf-8")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. Streaming memory guard (max_cacheable_bytes) + SSE (text/event-stream)
# ---------------------------------------------------------------------------


def test_streaming_max_cacheable_bytes_skips_oversized_without_failing(
    http_mod: ModuleType,
) -> None:
    def handler(req: Any) -> Any:
        def chunks() -> Iterator[bytes]:
            for _ in range(10):
                yield b"0123456789"

        return http_mod.Response(200, stream=chunks())

    cache = MemoryCache()
    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=cache,
        policy="force",
        max_cacheable_bytes=25,
    )
    with client:
        with client.stream("GET", "https://example.com/big") as r:
            body = b"".join(r.iter_bytes())
        assert len(body) == 100
        assert cache.stats().entries == 0


async def test_sse_llm_stream_record_and_replay(http_mod: ModuleType, tmp_path: Path) -> None:
    sse_events = [
        b'data: {"delta":"Hello"}\n\n',
        b'data: {"delta":" world"}\n\n',
        b"data: [DONE]\n\n",
    ]

    async def sse_handler(req: Any) -> Any:
        async def chunks() -> AsyncIterator[bytes]:
            for ev in sse_events:
                yield ev

        return http_mod.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=chunks(),
        )

    db = tmp_path / "sse.sqlite3"
    with SqliteCache(db) as cache:
        rec = wrap(
            http_mod.AsyncClient(transport=http_mod.MockTransport(sse_handler)),
            cache=cache,
            policy="force",
            cache_post=True,
        )
        async with rec, rec.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            json={"stream": True, "messages": [{"role": "user", "content": "hi"}]},
        ) as r1:
            lines1 = [line async for line in r1.aiter_lines() if line]

        # Replay SSE offline
        play = wrap(http_mod.AsyncClient(), cache=cache, policy="replay")
        async with play, play.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            json={"stream": True, "messages": [{"role": "user", "content": "hi"}]},
        ) as r2:
            assert r2.extensions["from_cache"] is True
            lines2 = [line async for line in r2.aiter_lines() if line]

    assert lines1 == lines2 == [
        'data: {"delta":"Hello"}',
        'data: {"delta":" world"}',
        "data: [DONE]",
    ]


# ---------------------------------------------------------------------------
# 6. keys(prefix), delete_prefix(prefix), PRAGMA user_version
# ---------------------------------------------------------------------------


def test_keys_and_delete_prefix_across_all_stores(tmp_path: Path) -> None:
    import fnmatch

    class _FakeRedis:
        def __init__(self) -> None:
            self.data: dict[str, bytes] = {}

        def get(self, k: str) -> bytes | None:
            return self.data.get(k)

        def set(self, k: str, v: bytes, *, px: int | None = None) -> None:
            self.data[k] = v

        def delete(self, *keys: str) -> int:
            return sum(1 for k in keys if self.data.pop(k, None) is not None)

        def scan_iter(self, *, match: str = "*", count: int = 100) -> Iterator[str]:
            for k in list(self.data):
                if fnmatch.fnmatch(k, match):
                    yield k

    sqlite_db = tmp_path / "prefix.sqlite3"
    stores = [
        SqliteCache(sqlite_db),
        MemoryCache(),
        FileCache(tmp_path / "files"),
        JsonCache(tmp_path / "store.json"),
        RedisCache(redis=_FakeRedis(), namespace="ns"),
    ]
    entry = CacheEntry(status_code=200, headers=(), body=b"ok")

    try:
        for store in stores:
            store.set("GET:https://a.com/users/1", entry)
            store.set("GET:https://a.com/users/2", entry)
            store.set("GET:https://a.com/posts/1", entry)

            assert store.keys("GET:https://a.com/users/") == [
                "GET:https://a.com/users/1",
                "GET:https://a.com/users/2",
            ]
            assert store.delete_prefix("GET:https://a.com/users/") == 2
            assert store.keys() == ["GET:https://a.com/posts/1"]

        with sqlite3.connect(sqlite_db) as conn:
            assert conn.execute("PRAGMA user_version;").fetchone()[0] == 1
    finally:
        for store in stores:
            store.close()


# ---------------------------------------------------------------------------
# 7. RFC 9111 multi-variant Vary storage
# ---------------------------------------------------------------------------


def test_rfc9111_multi_variant_vary_coexists(http_mod: ModuleType) -> None:
    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        lang = req.headers.get("accept-language", "en")
        return http_mod.Response(
            200,
            headers={"cache-control": "max-age=60", "vary": "Accept-Language"},
            text=f"hello-{lang}-{calls}",
        )

    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=MemoryCache(),
        policy="rfc9111",
    )
    with client:
        en1 = client.get("https://example.com/doc", headers={"Accept-Language": "en"})
        fr1 = client.get("https://example.com/doc", headers={"Accept-Language": "fr"})
        en2 = client.get("https://example.com/doc", headers={"Accept-Language": "en"})
        fr2 = client.get("https://example.com/doc", headers={"Accept-Language": "fr"})

    assert calls == 2
    assert en1.extensions["from_cache"] is False
    assert fr1.extensions["from_cache"] is False
    assert en2.extensions["from_cache"] is True
    assert fr2.extensions["from_cache"] is True
    assert en2.text == en1.text
    assert fr2.text == fr1.text


# ---------------------------------------------------------------------------
# 8. Observability hooks (on_hit, on_miss, on_store)
# ---------------------------------------------------------------------------


def test_observability_hooks_fire_accurately(http_mod: ModuleType) -> None:
    events: list[tuple[str, str]] = []

    client = wrap(
        http_mod.Client(
            transport=http_mod.MockTransport(lambda req: http_mod.Response(200, text="ok"))
        ),
        cache=MemoryCache(),
        policy="force",
        on_hit=lambda key, req: events.append(("hit", key)),
        on_miss=lambda key, req: events.append(("miss", key)),
        on_store=lambda key, req, entry: events.append(("store", key)),
    )
    with client:
        client.get("https://example.com/obs")
        client.get("https://example.com/obs")

    assert [ev[0] for ev in events] == ["miss", "store", "hit"]


# ---------------------------------------------------------------------------
# 9. CLI (stats, inspect, purge, clear, export, import)
# ---------------------------------------------------------------------------


def test_cli_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "cli.sqlite3"
    assert cli_main(["--db", str(db), "stats"]) == 1

    with SqliteCache(db) as cache:
        cache.set("GET:https://a.com/1", CacheEntry(200, (), b"hello"))
        cache.set("GET:https://a.com/2", CacheEntry(200, (), b"world"))
        cache.set("GET:https://b.com/old", CacheEntry(200, (), b"old", expires_at=time.time() - 5))

    assert cli_main(["--db", str(db), "stats"]) == 0
    assert "entries:    3" in capsys.readouterr().out

    assert cli_main(["--db", str(db), "inspect", "--prefix", "GET:https://a.com/"]) == 0
    out = capsys.readouterr().out
    assert "GET:https://a.com/1" in out
    assert "GET:https://b.com/old" not in out

    assert cli_main(["--db", str(db), "purge"]) == 0
    assert "Purged 1 expired entry." in capsys.readouterr().out

    exported = tmp_path / "dump.json"
    assert cli_main(["--db", str(db), "export", str(exported)]) == 0
    assert "Exported 2 entries" in capsys.readouterr().out

    assert cli_main(["--db", str(db), "clear", "--prefix", "GET:https://a.com/1"]) == 0
    assert "Deleted 1 entry" in capsys.readouterr().out

    assert cli_main(["--db", str(db), "clear"]) == 0
    assert "Cleared all entries" in capsys.readouterr().out

    db2 = tmp_path / "restored.sqlite3"
    assert cli_main(["--db", str(db2), "import", str(exported)]) == 0
    assert "Imported 2 entries" in capsys.readouterr().out


async def test_json_cache_async_expiry_binary_and_clear(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "full.json")
    raw_bin = bytes(range(256))
    await cache.aset("bin", CacheEntry(200, (("x-b", "1"),), raw_bin))
    await cache.aset("exp", CacheEntry(200, (), b"old", expires_at=time.time() - 5))

    got = await cache.aget("bin")
    assert got is not None and got.body == raw_bin
    assert await cache.aget("exp") is None
    assert (await cache.astats()).expired == 1
    assert await cache.akeys() == ["bin"]
    assert await cache.adelete("bin") is True
    assert await cache.adelete("missing") is False
    await cache.aset("a", CacheEntry(200, (), b"1"))
    await cache.aset("b", CacheEntry(200, (), b"2"))
    assert await cache.adelete_prefix("a") == 1
    await cache.aclear()
    assert (await cache.astats()).entries == 0


async def test_async_rfc9111_vary_and_hooks(http_mod: ModuleType) -> None:
    calls = 0
    events: list[str] = []

    async def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        lang = req.headers.get("accept-language", "en")
        return http_mod.Response(
            200,
            headers={"cache-control": "max-age=60", "vary": "Accept-Language"},
            text=f"async-{lang}-{calls}",
        )

    client = wrap(
        http_mod.AsyncClient(transport=http_mod.MockTransport(handler)),
        cache=MemoryCache(),
        policy="rfc9111",
        on_hit=lambda k, r: events.append("hit"),
        on_miss=lambda k, r: events.append("miss"),
        on_store=lambda k, r, e: events.append("store"),
    )
    async with client:
        en1 = await client.get("https://example.com/v", headers={"Accept-Language": "en"})
        fr1 = await client.get("https://example.com/v", headers={"Accept-Language": "fr"})
        en2 = await client.get("https://example.com/v", headers={"Accept-Language": "en"})
        fr2 = await client.get("https://example.com/v", headers={"Accept-Language": "fr"})

    assert calls == 2
    assert en2.text == en1.text and fr2.text == fr1.text
    assert events == ["miss", "store", "miss", "store", "hit", "hit"]
