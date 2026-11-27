from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

PolicyName = Literal["force", "rfc9111", "replay"]
BackendName = Literal["httpx", "httpx2"]
KeyFn = Callable[[Any], str]


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Serialized HTTP response stored in a cache backend."""

    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    http_version: str = "HTTP/1.1"
    encoding: str | None = None
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: float | None = None) -> bool:
        """Return True if this entry has a finite store-level expiry in the past."""
        if self.expires_at is None:
            return False
        current = time.time() if now is None else now
        return current >= self.expires_at

    @property
    def size_bytes(self) -> int:
        """Approximate stored byte size for eviction budgeting."""
        header_bytes = sum(len(k) + len(v) for k, v in self.headers)
        return len(self.body) + header_bytes


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Point-in-time metrics reported by a cache store."""

    entries: int
    size_bytes: int
    hits: int
    misses: int
    expired: int


class CacheMissError(LookupError):
    """Raised in ``policy="replay"`` mode when a request is not found in the cache."""

    def __init__(self, key: str, request: Any) -> None:
        self.key = key
        self.request = request
        method = getattr(request, "method", "?")
        url = getattr(request, "url", "?")
        super().__init__(f"Cache miss in replay mode for {method} {url} (key={key!r})")
