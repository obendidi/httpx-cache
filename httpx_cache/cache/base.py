from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import TypeVar

from httpx_cache.types import CacheEntry, CacheStats

_TCache = TypeVar("_TCache", bound="BaseCache")


class BaseCache(ABC):
    """Abstract base class for string-keyed response cache stores."""

    @abstractmethod
    def get(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        """Fetch a cached entry by key, returning None on miss or expiry."""

    @abstractmethod
    async def aget(self, key: str, *, ignore_expiry: bool = False) -> CacheEntry | None:
        """Async equivalent of :meth:`get`."""

    @abstractmethod
    def set(self, key: str, entry: CacheEntry) -> None:
        """Store or overwrite an entry under ``key``."""

    @abstractmethod
    async def aset(self, key: str, entry: CacheEntry) -> None:
        """Async equivalent of :meth:`set`."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove ``key`` from the cache. Returns True if an entry was removed."""

    @abstractmethod
    async def adelete(self, key: str) -> bool:
        """Async equivalent of :meth:`delete`."""

    @abstractmethod
    def clear(self) -> None:
        """Delete all entries from the cache."""

    @abstractmethod
    async def aclear(self) -> None:
        """Async equivalent of :meth:`clear`."""

    @abstractmethod
    def stats(self) -> CacheStats:
        """Return current cache entry/size/hit/miss/expired counters."""

    @abstractmethod
    async def astats(self) -> CacheStats:
        """Async equivalent of :meth:`stats`."""

    def close(self) -> None:  # noqa: B027
        """Release any underlying resources."""

    async def aclose(self) -> None:
        """Async equivalent of :meth:`close`."""
        self.close()

    def __enter__(self: _TCache) -> _TCache:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    async def __aenter__(self: _TCache) -> _TCache:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()
