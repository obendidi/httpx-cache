from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import httpx_cache
from httpx_cache import AsyncCacheTransport, MemoryCache, SqliteCache, SyncCacheTransport, wrap


def test_wrap_client_and_mounts_and_no_double_wrap(http_mod: ModuleType) -> None:
    calls = 0

    def handler(request: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, text=f"{request.url}-{calls}")

    cache = MemoryCache()
    raw = http_mod.Client(
        transport=http_mod.MockTransport(handler),
        mounts={"https://mounted.example/": http_mod.MockTransport(handler)},
    )
    wrapped = wrap(raw, cache=cache)
    assert wrapped is raw
    assert isinstance(wrapped._transport, SyncCacheTransport)

    # Calling wrap() a second time is a safe no-op (no double wrapping)
    wrap(wrapped, cache=cache)
    assert not isinstance(wrapped._transport.transport, SyncCacheTransport)

    with wrapped:
        r1 = wrapped.get("https://default.example/a")
        r2 = wrapped.get("https://default.example/a")
        m1 = wrapped.get("https://mounted.example/b")
        m2 = wrapped.get("https://mounted.example/b")

    assert calls == 2
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
    assert m1.extensions["from_cache"] is False
    assert m2.extensions["from_cache"] is True


def test_wrap_third_party_client_subclass(http_mod: ModuleType) -> None:
    class CustomSdkClient(http_mod.Client):  # type: ignore[name-defined, misc]
        pass

    cache = MemoryCache()
    sdk_client = wrap(
        CustomSdkClient(
            transport=http_mod.MockTransport(lambda req: http_mod.Response(200, text="sdk"))
        ),
        cache=cache,
    )
    with sdk_client:
        r1 = sdk_client.get("https://api.openai.com/v1/models")
        r2 = sdk_client.get("https://api.openai.com/v1/models")
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
    assert r2.text == "sdk"


def test_wrap_rejects_non_client() -> None:
    with pytest.raises(TypeError, match="httpx or httpx2"):
        wrap(object())


def test_client_and_async_client_subclasses(tmp_path: Path) -> None:
    httpx = pytest.importorskip("httpx")

    cache = SqliteCache(tmp_path / "client.sqlite3")
    with httpx_cache.Client(
        cache=cache,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"ok": True})),
    ) as client:
        assert isinstance(client, httpx.Client)
        r1 = client.get("https://example.org/test")
        r2 = client.get("https://example.org/test")
        assert r1.extensions["from_cache"] is False
        assert r2.extensions["from_cache"] is True
        assert r2.json() == {"ok": True}

    # Caller-provided cache stays open after client closes
    assert cache.stats().entries == 1
    cache.close()


async def test_async_client_subclass(tmp_path: Path) -> None:
    httpx = pytest.importorskip("httpx")

    cache = SqliteCache(tmp_path / "aclient.sqlite3")
    async with httpx_cache.AsyncClient(
        cache=cache,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, text="async-ok")),
    ) as client:
        assert isinstance(client, httpx.AsyncClient)
        r1 = await client.get("https://example.org/async")
        r2 = await client.get("https://example.org/async")
        assert r1.extensions["from_cache"] is False
        assert r2.extensions["from_cache"] is True
        assert r2.text == "async-ok"
    assert cache.stats().entries == 1
    cache.close()


def test_default_client_works_on_any_installed_backend(tmp_path: Path) -> None:
    from httpx_cache._backend import get_backend

    backend = get_backend()
    cache = SqliteCache(tmp_path / "any_backend.sqlite3")
    with httpx_cache.Client(
        cache=cache,
        transport=backend.module.MockTransport(
            lambda req: backend.Response(200, text="ok")
        ),
    ) as client:
        assert isinstance(client, backend.Client)
        r1 = client.get("https://example.org/any")
        r2 = client.get("https://example.org/any")
        assert r1.extensions["from_cache"] is False
        assert r2.extensions["from_cache"] is True
    cache.close()


def test_httpx_and_httpx2_share_same_sqlite_cache_in_one_process(tmp_path: Path) -> None:
    httpx = pytest.importorskip("httpx")
    httpx2 = pytest.importorskip("httpx2")
    import httpx_cache.httpx2 as hc2

    with SqliteCache(tmp_path / "shared.sqlite3") as shared_cache:
        # Write via httpx client
        with httpx_cache.Client(
            cache=shared_cache,
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"src": "httpx"})),
        ) as c1:
            r1 = c1.get("https://shared.example/data")
            assert isinstance(r1, httpx.Response)
            assert r1.extensions["from_cache"] is False

        # Read the exact same cached entry via httpx2 client!
        def must_not_call(req: Any) -> Any:
            raise AssertionError("Should hit shared cache populated by httpx")

        with hc2.Client(
            cache=shared_cache,
            transport=httpx2.MockTransport(must_not_call),
        ) as c2:
            assert isinstance(c2, httpx2.Client)
            r2 = c2.get("https://shared.example/data")
            assert isinstance(r2, httpx2.Response)
            assert r2.extensions["from_cache"] is True
            assert r2.json() == {"src": "httpx"}


async def test_httpx2_async_client_subclass() -> None:
    httpx2 = pytest.importorskip("httpx2")
    import httpx_cache.httpx2 as hc2

    cache = MemoryCache()
    async with hc2.AsyncClient(
        cache=cache,
        transport=httpx2.MockTransport(lambda req: httpx2.Response(200, text="h2-async")),
    ) as client:
        assert isinstance(client, httpx2.AsyncClient)
        assert isinstance(client._transport, AsyncCacheTransport)
        r1 = await client.get("https://example.org/h2")
        r2 = await client.get("https://example.org/h2")
        assert isinstance(r2, httpx2.Response)
        assert r1.extensions["from_cache"] is False
        assert r2.extensions["from_cache"] is True
        assert r2.text == "h2-async"
