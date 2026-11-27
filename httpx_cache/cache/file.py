from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
import zlib
from pathlib import Path

from httpx_cache.cache._codec import decode_entry, encode_entry
from httpx_cache.cache.base import BaseCache
from httpx_cache.types import CacheEntry, CacheStats

logger = logging.getLogger(__name__)

DEFAULT_FILE_CACHE_DIR = Path.home() / ".cache" / "httpx-cache" / "files"
_FILE_SUFFIX = ".cache"


class FileCache(BaseCache):
    """Filesystem response cache storing one atomically written file per key."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        compress: bool = True,
    ) -> None:
        self.cache_dir = (
            DEFAULT_FILE_CACHE_DIR if cache_dir is None else Path(cache_dir).expanduser()
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.compress = compress

        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._expired = 0

    def _path_for_key(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}{_FILE_SUFFIX}"

    def get(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        path = self._path_for_key(key)
        now = time.time()
        with self._lock:
            if not path.is_file():
                self._misses += 1
                return None
            try:
                raw = path.read_bytes()
                entry = decode_entry(raw)
            except (OSError, ValueError, KeyError, zlib.error, json.JSONDecodeError) as exc:
                logger.debug("Removing unreadable cache file %s: %s", path, exc)
                path.unlink(missing_ok=True)
                self._misses += 1
                return None

            if not ignore_expiry and entry.is_expired(now):
                path.unlink(missing_ok=True)
                self._expired += 1
                self._misses += 1
                return None

            self._hits += 1
            return entry

    async def aget(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        return await asyncio.to_thread(self.get, key, ignore_expiry=ignore_expiry)

    def set(self, key: str, entry: CacheEntry) -> None:
        path = self._path_for_key(key)
        payload = encode_entry(entry, compress=self.compress)
        with self._lock:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                os.replace(tmp_name, path)
            except BaseException:
                Path(tmp_name).unlink(missing_ok=True)
                raise

    async def aset(self, key: str, entry: CacheEntry) -> None:
        await asyncio.to_thread(self.set, key, entry)

    def delete(self, key: str) -> bool:
        path = self._path_for_key(key)
        with self._lock:
            if not path.is_file():
                return False
            path.unlink(missing_ok=True)
            return True

    async def adelete(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    def clear(self) -> None:
        with self._lock:
            for item in self.cache_dir.glob(f"*{_FILE_SUFFIX}"):
                item.unlink(missing_ok=True)

    async def aclear(self) -> None:
        await asyncio.to_thread(self.clear)

    def purge_expired(self) -> int:
        """Scan cache files and delete any whose entry has expired."""
        now = time.time()
        removed = 0
        with self._lock:
            for item in self.cache_dir.glob(f"*{_FILE_SUFFIX}"):
                try:
                    entry = decode_entry(item.read_bytes())
                except (OSError, ValueError, KeyError, zlib.error, json.JSONDecodeError):
                    item.unlink(missing_ok=True)
                    removed += 1
                    continue
                if entry.is_expired(now):
                    item.unlink(missing_ok=True)
                    removed += 1
                    self._expired += 1
        return removed

    async def apurge_expired(self) -> int:
        return await asyncio.to_thread(self.purge_expired)

    def stats(self) -> CacheStats:
        with self._lock:
            files = list(self.cache_dir.glob(f"*{_FILE_SUFFIX}"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            return CacheStats(
                entries=len(files),
                size_bytes=total_size,
                hits=self._hits,
                misses=self._misses,
                expired=self._expired,
            )

    async def astats(self) -> CacheStats:
        return await asyncio.to_thread(self.stats)
