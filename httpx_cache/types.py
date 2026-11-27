from __future__ import annotations

import difflib
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

PolicyName = Literal["force", "rfc9111", "replay"]
BackendName = Literal["httpx", "httpx2"]
KeyFn = Callable[[Any], str]
ShouldCacheFn = Callable[[Any, Any], bool]
CacheHitHook = Callable[[str, Any], None]
CacheMissHook = Callable[[str, Any], None]
CacheStoreHook = Callable[[str, Any, "CacheEntry"], None]


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


def _suggest_closest_keys(
    key: str,
    candidates: Sequence[str],
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    if not candidates:
        return ()
    base = key.split("|", 1)[0]
    same_base = [c for c in candidates if c != key and c.split("|", 1)[0] == base]
    if same_base:
        return tuple(same_base[:limit])
    return tuple(difflib.get_close_matches(key, candidates, n=limit, cutoff=0.4))


class CacheMissError(LookupError):
    """Raised in ``policy="replay"`` mode when a request is not found in the cache."""

    def __init__(
        self,
        key: str,
        request: Any,
        *,
        closest_keys: Sequence[str] = (),
    ) -> None:
        self.key = key
        self.request = request
        self.closest_keys: tuple[str, ...] = tuple(closest_keys)
        method = getattr(request, "method", "?")
        url = getattr(request, "url", "?")
        msg = f"Cache miss in replay mode for {method} {url} (key={key!r})"
        if self.closest_keys:
            base = key.split("|", 1)[0]
            if any(c.split("|", 1)[0] == base for c in self.closest_keys):
                msg += (
                    ". Closest recorded key(s) share the same method/URL "
                    f"(different body or headers): {', '.join(repr(c) for c in self.closest_keys)}"
                )
            else:
                msg += f". Closest recorded key(s): {', '.join(repr(c) for c in self.closest_keys)}"
        super().__init__(msg)
