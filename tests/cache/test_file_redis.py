from __future__ import annotations

import fnmatch
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest

from httpx_cache import CacheEntry, FileCache, RedisCache
from httpx_cache.cache._codec import decode_entry, encode_entry


def _make_entry(body: bytes = b"payload", *, expires_at: float | None = None) -> CacheEntry:
    return CacheEntry(
        status_code=200,
        headers=(("content-type", "application/octet-stream"),),
        body=body,
        expires_at=expires_at,
    )


class _FakeSyncRedis:
    def __init__(self) -> None:
        self.data: dict[str, tuple[bytes, float | None]] = {}
        self.closed = False

    def get(self, key: str) -> bytes | None:
        item = self.data.get(key)
        if item is None:
            return None
        val, exp = item
        if exp is not None and time.time() >= exp:
            del self.data[key]
            return None
        return val

    def set(self, key: str, value: bytes, *, px: int | None = None) -> None:
        exp = None if px is None else time.time() + px / 1000.0
        self.data[key] = (value, exp)

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                removed += 1
        return removed

    def scan_iter(self, *, match: str = "*", count: int = 100) -> Iterator[str]:
        for key in list(self.data):
            if fnmatch.fnmatch(key, match):
                yield key

    def close(self) -> None:
        self.closed = True


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self._inner = _FakeSyncRedis()

    async def get(self, key: str) -> bytes | None:
        return self._inner.get(key)

    async def set(self, key: str, value: bytes, *, px: int | None = None) -> None:
        self._inner.set(key, value, px=px)

    async def delete(self, *keys: str) -> int:
        return self._inner.delete(*keys)

    async def scan_iter(self, *, match: str = "*", count: int = 100) -> AsyncIterator[str]:
        for key in self._inner.scan_iter(match=match, count=count):
            yield key

    async def aclose(self) -> None:
        self._inner.close()


def test_codec_roundtrip_and_corruption_errors() -> None:
    small = _make_entry(b"tiny")
    assert decode_entry(encode_entry(small)).body == b"tiny"

    large = _make_entry(b"A" * 4096)
    encoded_large = encode_entry(large, compress=True)
    assert len(encoded_large) < 4096
    assert decode_entry(encoded_large).body == large.body

    with pytest.raises(ValueError, match="Truncated"):
        decode_entry(b"short")
    with pytest.raises(ValueError, match="Invalid cache entry magic"):
        decode_entry(b"NOPE" + b"\x00" * 16)


def test_file_cache_crud_expiry_corrupt_recovery_and_stats(tmp_path: Path) -> None:
    cache = FileCache(tmp_path / "files")
    assert cache.get("missing") is None
    assert cache.delete("missing") is False

    binary = bytes(range(256)) * 10
    cache.set("k1", _make_entry(binary))
    got = cache.get("k1")
    assert got is not None
    assert got.body == binary

    # Expired entry: replay works via ignore_expiry, normal get removes it
    cache.set("exp", _make_entry(b"old", expires_at=time.time() - 5.0))
    assert cache.get("exp", ignore_expiry=True) is not None
    assert cache.get("exp") is None
    assert cache.stats().expired == 1

    # Corrupt file is gracefully evicted as a miss
    corrupt_path = cache._path_for_key("corrupt")
    corrupt_path.write_bytes(b"corrupted-garbage")
    assert cache.get("corrupt") is None
    assert not corrupt_path.exists()

    # purge_expired + delete + clear
    cache.set("exp2", _make_entry(b"old2", expires_at=time.time() - 1.0))
    assert cache.purge_expired() == 1
    assert cache.delete("k1") is True
    assert cache.stats().entries == 0

    cache.set("a", _make_entry(b"1"))
    cache.set("b", _make_entry(b"2"))
    assert cache.stats().entries == 2
    cache.clear()
    assert cache.stats().entries == 0


async def test_file_cache_async_operations(tmp_path: Path) -> None:
    async with FileCache(tmp_path / "afiles") as cache:
        await cache.aset("k1", _make_entry(b"async-data"))
        got = await cache.aget("k1")
        assert got is not None
        assert got.body == b"async-data"
        assert (await cache.astats()).entries == 1
        assert await cache.adelete("k1") is True
        await cache.aclear()
        assert (await cache.astats()).entries == 0


def test_redis_cache_sync_crud_ttl_namespace_and_clear() -> None:
    fake = _FakeSyncRedis()
    fake.set("other_ns:keep", b"untouched")

    cache = RedisCache(redis=fake, namespace="mycache", default_ttl=30)
    assert cache.get("k1") is None

    cache.set("k1", _make_entry(b"v1"))
    assert "mycache:k1" in fake.data
    got = cache.get("k1")
    assert got is not None
    assert got.body == b"v1"
    assert cache.stats().entries == 1
    assert cache.stats().hits == 1
    assert cache.stats().misses == 1

    # Expired entry in Redis still handled if not yet evicted by server
    cache.set("exp", _make_entry(b"old", expires_at=time.time() - 5.0))
    assert cache.get("exp") is None

    assert cache.delete("k1") is True
    assert cache.delete("k1") is False

    cache.set("a", _make_entry(b"1"))
    cache.set("b", _make_entry(b"2"))
    cache.clear()
    assert cache.stats().entries == 0
    assert fake.get("other_ns:keep") == b"untouched"


async def test_redis_cache_async_crud_and_clear() -> None:
    fake_async = _FakeAsyncRedis()
    cache = RedisCache(aredis=fake_async, namespace="async_ns")

    assert await cache.aget("missing") is None
    await cache.aset("k1", _make_entry(b"hello-redis"))
    got = await cache.aget("k1")
    assert got is not None
    assert got.body == b"hello-redis"
    assert (await cache.astats()).entries == 1

    assert await cache.adelete("k1") is True
    await cache.aset("exp", _make_entry(b"old", expires_at=time.time() - 5.0))
    assert await cache.aget("exp") is None
    await cache.aset("x", _make_entry(b"1"))
    await cache.aclear()
    assert (await cache.astats()).entries == 0
    await cache.aclose()


def test_redis_cache_invalid_ttl() -> None:
    with pytest.raises(ValueError, match="positive"):
        RedisCache(redis=_FakeSyncRedis(), default_ttl=0)
    from datetime import timedelta

    cache = RedisCache(redis=_FakeSyncRedis(), default_ttl=timedelta(seconds=10))
    assert cache.default_ttl == 10.0


def test_file_cache_end_to_end_with_clients(http_mod: Any, tmp_path: Path) -> None:
    from httpx_cache import wrap

    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, text=f"file-{calls}")

    cache = FileCache(tmp_path / "e2e")
    with wrap(http_mod.Client(transport=http_mod.MockTransport(handler)), cache=cache) as client:
        r1 = client.get("https://example.com/file")
        r2 = client.get("https://example.com/file")
    assert calls == 1
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
    assert r2.text == "file-1"
