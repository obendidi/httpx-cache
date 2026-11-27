from __future__ import annotations

import threading
import time
from collections import OrderedDict

from httpx_cache.cache.base import BaseCache
from httpx_cache.types import CacheEntry, CacheStats


class MemoryCache(BaseCache):
    """Thread-safe and async-safe in-memory LRU cache."""

    def __init__(
        self,
        *,
        max_entries: int | None = None,
        max_size_bytes: int | None = None,
    ) -> None:
        if max_entries is not None and max_entries <= 0:
            raise ValueError(f"max_entries must be positive, got {max_entries}")
        if max_size_bytes is not None and max_size_bytes <= 0:
            raise ValueError(f"max_size_bytes must be positive, got {max_size_bytes}")
        self.max_entries = max_entries
        self.max_size_bytes = max_size_bytes

        self._lock = threading.Lock()
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._size_bytes = 0
        self._hits = 0
        self._misses = 0
        self._expired = 0

    def get(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        now = time.time()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if not ignore_expiry and entry.is_expired(now):
                self._remove_locked(key)
                self._expired += 1
                self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._hits += 1
            return entry

    async def aget(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        return self.get(key, ignore_expiry=ignore_expiry)

    def set(self, key: str, entry: CacheEntry) -> None:
        entry_size = entry.size_bytes
        if self.max_size_bytes is not None and entry_size > self.max_size_bytes:
            return
        now = time.time()
        with self._lock:
            if key in self._entries:
                self._remove_locked(key)
            self._entries[key] = entry
            self._size_bytes += entry_size
            self._evict_locked(now)

    async def aset(self, key: str, entry: CacheEntry) -> None:
        self.set(key, entry)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._remove_locked(key)

    async def adelete(self, key: str) -> bool:
        return self.delete(key)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._size_bytes = 0

    async def aclear(self) -> None:
        self.clear()

    def keys(self, prefix: str = "") -> list[str]:
        with self._lock:
            return sorted(k for k in self._entries if not prefix or k.startswith(prefix))

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            targets = [k for k in self._entries if not prefix or k.startswith(prefix)]
            for k in targets:
                self._remove_locked(k)
            return len(targets)

    def purge_expired(self) -> int:
        """Remove all expired entries and return how many were removed."""
        now = time.time()
        with self._lock:
            return self._purge_expired_locked(now)

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                entries=len(self._entries),
                size_bytes=self._size_bytes,
                hits=self._hits,
                misses=self._misses,
                expired=self._expired,
            )

    async def astats(self) -> CacheStats:
        return self.stats()

    def _remove_locked(self, key: str) -> bool:
        existing = self._entries.pop(key, None)
        if existing is None:
            return False
        self._size_bytes -= existing.size_bytes
        return True

    def _purge_expired_locked(self, now: float) -> int:
        expired_keys = [k for k, v in self._entries.items() if v.is_expired(now)]
        for k in expired_keys:
            self._remove_locked(k)
        self._expired += len(expired_keys)
        return len(expired_keys)

    def _evict_locked(self, now: float) -> None:
        needs_eviction = (
            self.max_entries is not None and len(self._entries) > self.max_entries
        ) or (self.max_size_bytes is not None and self._size_bytes > self.max_size_bytes)
        if not needs_eviction:
            return

        self._purge_expired_locked(now)

        while self._entries and (
            (self.max_entries is not None and len(self._entries) > self.max_entries)
            or (self.max_size_bytes is not None and self._size_bytes > self.max_size_bytes)
        ):
            _, oldest = self._entries.popitem(last=False)
            self._size_bytes -= oldest.size_bytes
