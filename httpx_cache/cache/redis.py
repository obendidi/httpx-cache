from __future__ import annotations

import math
import threading
import time
from datetime import timedelta
from typing import Any

from httpx_cache.cache._codec import decode_entry, encode_entry
from httpx_cache.cache.base import BaseCache
from httpx_cache.types import CacheEntry, CacheStats


def _import_redis() -> tuple[type[Any], type[Any]]:
    try:
        from redis import Redis
        from redis.asyncio import Redis as AsyncRedis
    except ImportError as exc:
        raise ImportError(
            "RedisCache requires the optional 'redis' dependency. "
            "Install it with: pip install 'httpx-cache[redis]'"
        ) from exc
    return Redis, AsyncRedis


class RedisCache(BaseCache):
    """Redis-backed response cache supporting sync and async ``redis>=5`` clients."""

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        redis: Any | None = None,
        aredis: Any | None = None,
        namespace: str = "httpx_cache",
        default_ttl: float | timedelta | None = None,
        compress: bool = True,
    ) -> None:
        if redis is None and aredis is None and not redis_url:
            redis_url = "redis://localhost:6379/0"

        if isinstance(default_ttl, timedelta):
            ttl_seconds: float | None = default_ttl.total_seconds()
        elif default_ttl is not None:
            ttl_seconds = float(default_ttl)
        else:
            ttl_seconds = None
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError(f"default_ttl must be positive, got {ttl_seconds}")

        self.redis_url = redis_url
        self.namespace = namespace
        self.default_ttl = ttl_seconds
        self.compress = compress

        self._redis: Any | None = redis
        self._aredis: Any | None = aredis
        self._owns_redis = redis is None
        self._owns_aredis = aredis is None

        self._counter_lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._expired = 0

    @property
    def redis(self) -> Any:
        if self._redis is None:
            if not self.redis_url:
                raise RuntimeError("No sync Redis client or redis_url configured.")
            redis_cls, _ = _import_redis()
            self._redis = redis_cls.from_url(self.redis_url)
        return self._redis

    @property
    def aredis(self) -> Any:
        if self._aredis is None:
            if not self.redis_url:
                raise RuntimeError("No async Redis client or redis_url configured.")
            _, async_redis_cls = _import_redis()
            self._aredis = async_redis_cls.from_url(self.redis_url)
        return self._aredis

    def _namespaced_key(self, key: str) -> str:
        return f"{self.namespace}:{key}" if self.namespace else key

    def _strip_namespace(self, raw_key: Any) -> str:
        text = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
        ns_prefix = f"{self.namespace}:"
        if self.namespace and text.startswith(ns_prefix):
            return text[len(ns_prefix) :]
        return text

    def _scan_pattern(self, prefix: str = "") -> str:
        escaped = (
            prefix.replace("\\", "\\\\")
            .replace("*", "\\*")
            .replace("?", "\\?")
            .replace("[", "\\[")
        )
        if self.namespace:
            return f"{self.namespace}:{escaped}*"
        return f"{escaped}*"

    def _ttl_ms(self, entry: CacheEntry) -> int | None:
        if entry.expires_at is not None:
            remaining = entry.expires_at - time.time()
            return max(1, math.ceil(remaining * 1000))
        if self.default_ttl is not None:
            return max(1, math.ceil(self.default_ttl * 1000))
        return None

    def get(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        raw = self.redis.get(self._namespaced_key(key))
        if raw is None:
            with self._counter_lock:
                self._misses += 1
            return None
        entry = decode_entry(bytes(raw))
        if not ignore_expiry and entry.is_expired():
            self.redis.delete(self._namespaced_key(key))
            with self._counter_lock:
                self._expired += 1
                self._misses += 1
            return None
        with self._counter_lock:
            self._hits += 1
        return entry

    async def aget(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        raw = await self.aredis.get(self._namespaced_key(key))
        if raw is None:
            with self._counter_lock:
                self._misses += 1
            return None
        entry = decode_entry(bytes(raw))
        if not ignore_expiry and entry.is_expired():
            await self.aredis.delete(self._namespaced_key(key))
            with self._counter_lock:
                self._expired += 1
                self._misses += 1
            return None
        with self._counter_lock:
            self._hits += 1
        return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        rkey = self._namespaced_key(key)
        payload = encode_entry(entry, compress=self.compress)
        ttl_ms = self._ttl_ms(entry)
        if ttl_ms is not None:
            self.redis.set(rkey, payload, px=ttl_ms)
        else:
            self.redis.set(rkey, payload)

    async def aset(self, key: str, entry: CacheEntry) -> None:
        rkey = self._namespaced_key(key)
        payload = encode_entry(entry, compress=self.compress)
        ttl_ms = self._ttl_ms(entry)
        if ttl_ms is not None:
            await self.aredis.set(rkey, payload, px=ttl_ms)
        else:
            await self.aredis.set(rkey, payload)

    def delete(self, key: str) -> bool:
        removed = int(self.redis.delete(self._namespaced_key(key)))
        return removed > 0

    async def adelete(self, key: str) -> bool:
        removed = int(await self.aredis.delete(self._namespaced_key(key)))
        return removed > 0

    def keys(self, prefix: str = "") -> list[str]:
        found = [
            self._strip_namespace(rkey)
            for rkey in self.redis.scan_iter(match=self._scan_pattern(prefix), count=200)
        ]
        return sorted(k for k in found if not prefix or k.startswith(prefix))

    async def akeys(self, prefix: str = "") -> list[str]:
        found = [
            self._strip_namespace(rkey)
            async for rkey in self.aredis.scan_iter(match=self._scan_pattern(prefix), count=200)
        ]
        return sorted(k for k in found if not prefix or k.startswith(prefix))

    def delete_prefix(self, prefix: str) -> int:
        batch: list[Any] = []
        removed = 0
        for rkey in self.redis.scan_iter(match=self._scan_pattern(prefix), count=200):
            if prefix and not self._strip_namespace(rkey).startswith(prefix):
                continue
            batch.append(rkey)
            if len(batch) >= 200:
                removed += int(self.redis.delete(*batch))
                batch.clear()
        if batch:
            removed += int(self.redis.delete(*batch))
        return removed

    async def adelete_prefix(self, prefix: str) -> int:
        batch: list[Any] = []
        removed = 0
        async for rkey in self.aredis.scan_iter(match=self._scan_pattern(prefix), count=200):
            if prefix and not self._strip_namespace(rkey).startswith(prefix):
                continue
            batch.append(rkey)
            if len(batch) >= 200:
                removed += int(await self.aredis.delete(*batch))
                batch.clear()
        if batch:
            removed += int(await self.aredis.delete(*batch))
        return removed

    def clear(self) -> None:
        batch: list[Any] = []
        for rkey in self.redis.scan_iter(match=self._scan_pattern(), count=200):
            batch.append(rkey)
            if len(batch) >= 200:
                self.redis.delete(*batch)
                batch.clear()
        if batch:
            self.redis.delete(*batch)

    async def aclear(self) -> None:
        batch: list[Any] = []
        async for rkey in self.aredis.scan_iter(match=self._scan_pattern(), count=200):
            batch.append(rkey)
            if len(batch) >= 200:
                await self.aredis.delete(*batch)
                batch.clear()
        if batch:
            await self.aredis.delete(*batch)

    def stats(self) -> CacheStats:
        entries = 0
        size_bytes = 0
        for rkey in self.redis.scan_iter(match=self._scan_pattern(), count=200):
            entries += 1
            raw = self.redis.get(rkey)
            if raw is not None:
                size_bytes += len(raw)
        with self._counter_lock:
            return CacheStats(
                entries=entries,
                size_bytes=size_bytes,
                hits=self._hits,
                misses=self._misses,
                expired=self._expired,
            )

    async def astats(self) -> CacheStats:
        entries = 0
        size_bytes = 0
        async for rkey in self.aredis.scan_iter(match=self._scan_pattern(), count=200):
            entries += 1
            raw = await self.aredis.get(rkey)
            if raw is not None:
                size_bytes += len(raw)
        with self._counter_lock:
            return CacheStats(
                entries=entries,
                size_bytes=size_bytes,
                hits=self._hits,
                misses=self._misses,
                expired=self._expired,
            )

    def close(self) -> None:
        if self._owns_redis and self._redis is not None:
            self._redis.close()
            self._redis = None

    async def aclose(self) -> None:
        if self._owns_aredis and self._aredis is not None:
            if hasattr(self._aredis, "aclose"):
                await self._aredis.aclose()
            else:
                await self._aredis.close()
            self._aredis = None
        self.close()
