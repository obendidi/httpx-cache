from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
import zlib
from pathlib import Path
from typing import Any

from httpx_cache.cache._codec import entry_from_json_dict, entry_to_json_dict
from httpx_cache.cache.base import BaseCache
from httpx_cache.types import CacheEntry, CacheStats

DEFAULT_SQLITE_PATH = Path.home() / ".cache" / "httpx-cache" / "cache.sqlite3"
_COMPRESS_THRESHOLD_BYTES = 1024
SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    key TEXT PRIMARY KEY,
    status_code INTEGER NOT NULL,
    headers_json TEXT NOT NULL,
    body BLOB NOT NULL,
    compressed INTEGER NOT NULL DEFAULT 0,
    http_version TEXT NOT NULL DEFAULT 'HTTP/1.1',
    encoding TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    expires_at REAL,
    last_accessed REAL NOT NULL,
    size_bytes INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_expires_at
    ON entries(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entries_last_accessed
    ON entries(last_accessed);
"""


def _like_prefix_pattern(prefix: str) -> str:
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


class SqliteCache(BaseCache):
    """WAL-mode SQLite response cache with indexed TTL expiry and LRU size capping.

    Thread-safe via a per-instance lock and async-safe via ``asyncio.to_thread``.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_size_bytes: int | None = None,
        compress: bool = True,
        busy_timeout_ms: int = 5000,
    ) -> None:
        if max_size_bytes is not None and max_size_bytes <= 0:
            raise ValueError(f"max_size_bytes must be positive, got {max_size_bytes}")
        if busy_timeout_ms < 0:
            raise ValueError(f"busy_timeout_ms must be non-negative, got {busy_timeout_ms}")

        if path is None:
            resolved_path: str | Path = DEFAULT_SQLITE_PATH
        elif str(path) == ":memory:":
            resolved_path = ":memory:"
        else:
            resolved_path = Path(path).expanduser()

        self.path: str | Path = resolved_path
        self.max_size_bytes = max_size_bytes
        self.compress = compress

        if isinstance(resolved_path, Path):
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._closed = False
        self._hits = 0
        self._misses = 0
        self._expired = 0

        self._conn = sqlite3.connect(
            str(resolved_path),
            timeout=busy_timeout_ms / 1000.0,
            check_same_thread=False,
        )
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)};")
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
            self._conn.commit()

    def get(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        now = time.time()
        with self._lock:
            self._ensure_open()
            row = self._conn.execute(
                """
                SELECT status_code, headers_json, body, compressed, http_version,
                       encoding, metadata_json, created_at, expires_at
                FROM entries
                WHERE key = ?
                """,
                (key,),
            ).fetchone()
            if row is None:
                self._misses += 1
                return None

            (
                status_code,
                headers_json,
                raw_body,
                compressed,
                http_version,
                encoding,
                metadata_json,
                created_at,
                expires_at,
            ) = row

            if not ignore_expiry and expires_at is not None and now >= expires_at:
                self._conn.execute("DELETE FROM entries WHERE key = ?", (key,))
                self._conn.commit()
                self._expired += 1
                self._misses += 1
                return None

            self._conn.execute(
                "UPDATE entries SET last_accessed = ? WHERE key = ?",
                (now, key),
            )
            self._conn.commit()
            self._hits += 1

        return self._row_to_entry(
            status_code=status_code,
            headers_json=headers_json,
            raw_body=raw_body,
            compressed=compressed,
            http_version=http_version,
            encoding=encoding,
            metadata_json=metadata_json,
            created_at=created_at,
            expires_at=expires_at,
        )

    async def aget(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        return await asyncio.to_thread(self.get, key, ignore_expiry=ignore_expiry)

    def set(self, key: str, entry: CacheEntry) -> None:
        headers_json = json.dumps(entry.headers)
        metadata_json = json.dumps(entry.metadata)
        stored_body = entry.body
        compressed = 0
        if self.compress and len(entry.body) >= _COMPRESS_THRESHOLD_BYTES:
            candidate = zlib.compress(entry.body, level=6)
            if len(candidate) < len(entry.body):
                stored_body = candidate
                compressed = 1

        stored_size = len(stored_body) + len(headers_json.encode("utf-8"))
        if self.max_size_bytes is not None and stored_size > self.max_size_bytes:
            return

        now = time.time()
        with self._lock:
            self._ensure_open()
            self._conn.execute(
                """
                INSERT INTO entries (
                    key, status_code, headers_json, body, compressed, http_version,
                    encoding, metadata_json, created_at, expires_at, last_accessed, size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    status_code = excluded.status_code,
                    headers_json = excluded.headers_json,
                    body = excluded.body,
                    compressed = excluded.compressed,
                    http_version = excluded.http_version,
                    encoding = excluded.encoding,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    last_accessed = excluded.last_accessed,
                    size_bytes = excluded.size_bytes
                """,
                (
                    key,
                    entry.status_code,
                    headers_json,
                    sqlite3.Binary(stored_body),
                    compressed,
                    entry.http_version,
                    entry.encoding,
                    metadata_json,
                    entry.created_at,
                    entry.expires_at,
                    now,
                    stored_size,
                ),
            )
            if self.max_size_bytes is not None:
                self._enforce_size_cap_locked(now)
            self._conn.commit()

    async def aset(self, key: str, entry: CacheEntry) -> None:
        await asyncio.to_thread(self.set, key, entry)

    def delete(self, key: str) -> bool:
        with self._lock:
            self._ensure_open()
            cursor = self._conn.execute("DELETE FROM entries WHERE key = ?", (key,))
            self._conn.commit()
            return cursor.rowcount > 0

    async def adelete(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)

    def keys(self, prefix: str = "") -> list[str]:
        with self._lock:
            self._ensure_open()
            if prefix:
                rows = self._conn.execute(
                    "SELECT key FROM entries WHERE key LIKE ? ESCAPE '\\' ORDER BY key ASC",
                    (_like_prefix_pattern(prefix),),
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT key FROM entries ORDER BY key ASC").fetchall()
            return [str(r[0]) for r in rows]

    async def akeys(self, prefix: str = "") -> list[str]:
        return await asyncio.to_thread(self.keys, prefix)

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            self._ensure_open()
            if prefix:
                cursor = self._conn.execute(
                    "DELETE FROM entries WHERE key LIKE ? ESCAPE '\\'",
                    (_like_prefix_pattern(prefix),),
                )
            else:
                cursor = self._conn.execute("DELETE FROM entries")
            self._conn.commit()
            return max(0, cursor.rowcount)

    async def adelete_prefix(self, prefix: str) -> int:
        return await asyncio.to_thread(self.delete_prefix, prefix)

    def clear(self) -> None:
        with self._lock:
            self._ensure_open()
            self._conn.execute("DELETE FROM entries")
            self._conn.commit()

    async def aclear(self) -> None:
        await asyncio.to_thread(self.clear)

    def purge_expired(self) -> int:
        """Delete all expired rows using the expires_at index and return row count."""
        now = time.time()
        with self._lock:
            self._ensure_open()
            removed = self._purge_expired_locked(now)
            self._conn.commit()
            return removed

    async def apurge_expired(self) -> int:
        return await asyncio.to_thread(self.purge_expired)

    def export_json(self, output_path: str | Path) -> int:
        """Export all cached entries to a sorted, diff-friendly JSON file."""
        target = Path(output_path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        exported: dict[str, Any] = {}
        with self._lock:
            self._ensure_open()
            rows = self._conn.execute(
                """
                SELECT key, status_code, headers_json, body, compressed, http_version,
                       encoding, metadata_json, created_at, expires_at
                FROM entries
                ORDER BY key ASC
                """
            ).fetchall()
        for row in rows:
            entry = self._row_to_entry(
                status_code=row[1],
                headers_json=row[2],
                raw_body=row[3],
                compressed=row[4],
                http_version=row[5],
                encoding=row[6],
                metadata_json=row[7],
                created_at=row[8],
                expires_at=row[9],
            )
            exported[str(row[0])] = entry_to_json_dict(entry)
        target.write_text(
            json.dumps({"version": 1, "entries": exported}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return len(exported)

    def import_json(self, input_path: str | Path) -> int:
        """Import entries from a JSON file produced by :meth:`export_json` or ``JsonCache``."""
        source = Path(input_path).expanduser()
        payload: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
        entries: dict[str, Any] = payload.get("entries", payload)
        count = 0
        for key, item in entries.items():
            self.set(str(key), entry_from_json_dict(item))
            count += 1
        return count

    def stats(self) -> CacheStats:
        with self._lock:
            self._ensure_open()
            row = self._conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM entries"
            ).fetchone()
            entries = int(row[0]) if row else 0
            size_bytes = int(row[1]) if row else 0
            return CacheStats(
                entries=entries,
                size_bytes=size_bytes,
                hits=self._hits,
                misses=self._misses,
                expired=self._expired,
            )

    async def astats(self) -> CacheStats:
        return await asyncio.to_thread(self.stats)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._conn.close()

    async def aclose(self) -> None:
        await asyncio.to_thread(self.close)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SqliteCache is closed.")

    @staticmethod
    def _row_to_entry(
        *,
        status_code: int,
        headers_json: str,
        raw_body: bytes,
        compressed: int,
        http_version: str,
        encoding: str | None,
        metadata_json: str,
        created_at: float,
        expires_at: float | None,
    ) -> CacheEntry:
        body = zlib.decompress(raw_body) if compressed else bytes(raw_body)
        headers_list: list[list[str]] = json.loads(headers_json)
        headers = tuple((k, v) for k, v in headers_list)
        metadata: dict[str, Any] = json.loads(metadata_json) if metadata_json else {}
        return CacheEntry(
            status_code=status_code,
            headers=headers,
            body=body,
            http_version=http_version,
            encoding=encoding,
            created_at=created_at,
            expires_at=expires_at,
            metadata=metadata,
        )

    def _purge_expired_locked(self, now: float) -> int:
        cursor = self._conn.execute(
            "DELETE FROM entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        removed = max(0, cursor.rowcount)
        self._expired += removed
        return removed

    def _enforce_size_cap_locked(self, now: float) -> None:
        assert self.max_size_bytes is not None
        total_row = self._conn.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM entries"
        ).fetchone()
        total = int(total_row[0]) if total_row else 0
        if total <= self.max_size_bytes:
            return

        self._purge_expired_locked(now)
        total_row = self._conn.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM entries"
        ).fetchone()
        total = int(total_row[0]) if total_row else 0
        if total <= self.max_size_bytes:
            return

        rows = self._conn.execute(
            "SELECT key, size_bytes FROM entries ORDER BY last_accessed ASC"
        ).fetchall()
        to_delete: list[tuple[str]] = []
        for k, sz in rows:
            if total <= self.max_size_bytes:
                break
            to_delete.append((k,))
            total -= int(sz)
        if to_delete:
            self._conn.executemany("DELETE FROM entries WHERE key = ?", to_delete)
