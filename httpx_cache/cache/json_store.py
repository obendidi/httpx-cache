from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from httpx_cache.cache._codec import entry_from_json_dict, entry_to_json_dict
from httpx_cache.cache.base import BaseCache
from httpx_cache.types import CacheEntry, CacheStats


class JsonCache(BaseCache):
    """Human-readable, git-diffable single-file JSON cache store for cassettes and fixtures."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.Lock()
        self._entries: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._expired = 0

        if self.path.is_file():
            self._load_locked()

    def _load_locked(self) -> None:
        payload: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        raw_entries: dict[str, Any] = payload.get("entries", {})
        self._entries = {
            str(key): entry_from_json_dict(item) for key, item in raw_entries.items()
        }

    def _flush_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {
            "version": 1,
            "entries": {
                key: entry_to_json_dict(self._entries[key]) for key in sorted(self._entries)
            },
        }
        content = (json.dumps(serialized, indent=2, sort_keys=True) + "\n").encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            os.replace(tmp_name, self.path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def get(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        now = time.time()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if not ignore_expiry and entry.is_expired(now):
                del self._entries[key]
                self._flush_locked()
                self._expired += 1
                self._misses += 1
                return None
            self._hits += 1
            return entry

    async def aget(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        return await asyncio.to_thread(self.get, key, ignore_expiry=ignore_expiry)

    def set(self, key: str, entry: CacheEntry) -> None:
        with self._lock:
            self._entries[key] = entry
            self._flush_locked()

    async def aset(self, key: str, entry: CacheEntry) -> None:
        await asyncio.to_thread(self.set, key, entry)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._entries:
                return False
            del self._entries[key]
            self._flush_locked()
            return True

    async def adelete(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    def keys(self, prefix: str = "") -> list[str]:
        with self._lock:
            return sorted(k for k in self._entries if not prefix or k.startswith(prefix))

    async def akeys(self, prefix: str = "") -> list[str]:
        return await asyncio.to_thread(self.keys, prefix)

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            targets = [k for k in self._entries if not prefix or k.startswith(prefix)]
            if not targets:
                return 0
            for k in targets:
                del self._entries[k]
            self._flush_locked()
            return len(targets)

    async def adelete_prefix(self, prefix: str) -> int:
        return await asyncio.to_thread(self.delete_prefix, prefix)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            if self.path.exists():
                self._flush_locked()

    async def aclear(self) -> None:
        await asyncio.to_thread(self.clear)

    def stats(self) -> CacheStats:
        with self._lock:
            size_bytes = self.path.stat().st_size if self.path.is_file() else 0
            return CacheStats(
                entries=len(self._entries),
                size_bytes=size_bytes,
                hits=self._hits,
                misses=self._misses,
                expired=self._expired,
            )

    async def astats(self) -> CacheStats:
        return await asyncio.to_thread(self.stats)
