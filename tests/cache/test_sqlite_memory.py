from __future__ import annotations

import asyncio
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from httpx_cache import CacheEntry, MemoryCache, SqliteCache


def _make_entry(
    body: bytes = b"hello",
    *,
    status_code: int = 200,
    expires_at: float | None = None,
    headers: tuple[tuple[str, str], ...] = (("content-type", "text/plain"),),
) -> CacheEntry:
    return CacheEntry(
        status_code=status_code,
        headers=headers,
        body=body,
        expires_at=expires_at,
    )


def test_sqlite_wal_mode_and_persistence(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "cache.sqlite3"
    with SqliteCache(db_path) as cache:
        with sqlite3.connect(db_path) as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert mode.lower() == "wal"

        payload = b"x" * 4096  # triggers zlib compression (>1024 bytes)
        cache.set("k1", _make_entry(payload))
        got = cache.get("k1")
        assert got is not None
        assert got.body == payload
        assert got.status_code == 200

    # Reopen from disk and verify persistence + stats
    with SqliteCache(db_path) as reopened:
        got = reopened.get("k1")
        assert got is not None
        assert got.body == payload
        st = reopened.stats()
        assert st.entries == 1
        assert st.hits == 1
        assert st.misses == 0
        assert st.size_bytes < len(payload)  # compressed on disk


def test_sqlite_binary_payload_lossless(sqlite_cache: SqliteCache) -> None:
    raw_binary = bytes(range(256)) * 8
    sqlite_cache.set("bin", _make_entry(raw_binary))
    got = sqlite_cache.get("bin")
    assert got is not None
    assert got.body == raw_binary


def test_cache_crud_and_stats(cache: SqliteCache | MemoryCache) -> None:
    assert cache.get("missing") is None
    assert cache.delete("missing") is False

    entry = _make_entry(b"payload")
    cache.set("k1", entry)
    assert cache.get("k1") is not None
    assert cache.stats().entries == 1
    assert cache.stats().hits == 1
    assert cache.stats().misses == 1

    assert cache.delete("k1") is True
    assert cache.delete("k1") is False
    assert cache.stats().entries == 0

    cache.set("a", entry)
    cache.set("b", entry)
    cache.clear()
    assert cache.stats().entries == 0


def test_cache_ttl_expiry_and_ignore_expiry(cache: SqliteCache | MemoryCache) -> None:
    past = time.time() - 10.0
    future = time.time() + 3600.0
    cache.set("expired", _make_entry(b"old", expires_at=past))
    cache.set("valid", _make_entry(b"new", expires_at=future))

    # Replay uses ignore_expiry=True before normal lookup deletes it
    replayed = cache.get("expired", ignore_expiry=True)
    assert replayed is not None
    assert replayed.body == b"old"

    # Normal get expires and purges the entry
    assert cache.get("expired") is None
    assert cache.stats().expired == 1
    assert cache.get("valid") is not None


def test_sqlite_purge_expired(sqlite_cache: SqliteCache) -> None:
    past = time.time() - 5.0
    sqlite_cache.set("e1", _make_entry(b"1", expires_at=past))
    sqlite_cache.set("e2", _make_entry(b"2", expires_at=past))
    sqlite_cache.set("live", _make_entry(b"3", expires_at=time.time() + 60.0))

    removed = sqlite_cache.purge_expired()
    assert removed == 2
    assert sqlite_cache.stats().entries == 1
    assert sqlite_cache.stats().expired == 2


def test_sqlite_max_size_bytes_lru_eviction(tmp_path: Path) -> None:
    cache = SqliteCache(tmp_path / "cap.sqlite3", max_size_bytes=250, compress=False)
    try:
        cache.set("k1", _make_entry(b"a" * 80))
        time.sleep(0.01)
        cache.set("k2", _make_entry(b"b" * 80))
        time.sleep(0.01)
        # Touch k1 so k2 becomes least-recently-used
        assert cache.get("k1") is not None
        time.sleep(0.01)
        cache.set("k3", _make_entry(b"c" * 80))

        assert cache.get("k2") is None
        assert cache.get("k1") is not None
        assert cache.get("k3") is not None

        # Oversized single entry is skipped rather than wiping cache
        cache.set("huge", _make_entry(b"z" * 1000))
        assert cache.get("huge") is None
        assert cache.stats().entries == 2
    finally:
        cache.close()


def test_memory_cache_lru_eviction() -> None:
    cache = MemoryCache(max_entries=2)
    cache.set("k1", _make_entry(b"1"))
    cache.set("k2", _make_entry(b"2"))
    assert cache.get("k1") is not None  # k2 is now oldest
    cache.set("k3", _make_entry(b"3"))

    assert cache.get("k2") is None
    assert cache.get("k1") is not None
    assert cache.get("k3") is not None

    # max_size_bytes cap and purge_expired
    sized = MemoryCache(max_size_bytes=100)
    sized.set("huge", _make_entry(b"x" * 200))
    assert sized.get("huge") is None
    sized.set("exp", _make_entry(b"a", expires_at=time.time() - 5))
    assert sized.purge_expired() == 1


async def test_memory_cache_async_operations() -> None:
    async with MemoryCache() as cache:
        await cache.aset("k1", _make_entry(b"m1"))
        got = await cache.aget("k1")
        assert got is not None and got.body == b"m1"
        assert (await cache.astats()).entries == 1
        assert await cache.adelete("k1") is True
        await cache.aset("k2", _make_entry(b"m2"))
        await cache.aclear()
        assert (await cache.astats()).entries == 0


def test_sqlite_thread_safety(tmp_path: Path) -> None:
    with SqliteCache(tmp_path / "threads.sqlite3") as cache:
        def worker(i: int) -> bytes:
            key = f"k-{i}"
            cache.set(key, _make_entry(f"val-{i}".encode()))
            got = cache.get(key)
            assert got is not None
            return got.body

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(worker, range(40)))

        assert results == [f"val-{i}".encode() for i in range(40)]
        assert cache.stats().entries == 40


async def test_sqlite_async_concurrency(tmp_path: Path) -> None:
    async with SqliteCache(tmp_path / "async.sqlite3") as cache:
        async def task(i: int) -> bytes:
            key = f"a-{i}"
            await cache.aset(key, _make_entry(f"aval-{i}".encode()))
            got = await cache.aget(key)
            assert got is not None
            return got.body

        results = await asyncio.gather(*(task(i) for i in range(30)))
        assert results == [f"aval-{i}".encode() for i in range(30)]
        st = await cache.astats()
        assert st.entries == 30
        assert await cache.adelete("a-0") is True
        await cache.aclear()
        assert (await cache.astats()).entries == 0


def test_sqlite_closed_raises(tmp_path: Path) -> None:
    cache = SqliteCache(tmp_path / "closed.sqlite3")
    cache.close()
    cache.close()  # idempotent
    with pytest.raises(RuntimeError, match="closed"):
        cache.get("k1")
