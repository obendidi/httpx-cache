from __future__ import annotations

from typing import TYPE_CHECKING, Any

from httpx_cache.cache import BaseCache, FileCache, MemoryCache, RedisCache, SqliteCache
from httpx_cache.client import build_client_classes, wrap
from httpx_cache.keys import default_key_fn
from httpx_cache.policy import PolicyController
from httpx_cache.transport import AsyncCacheTransport, SyncCacheTransport
from httpx_cache.types import BackendName, CacheEntry, CacheMissError, CacheStats, KeyFn, PolicyName

if TYPE_CHECKING:
    Client: type[Any]
    AsyncClient: type[Any]

__all__ = [
    "AsyncCacheTransport",
    "AsyncClient",
    "BackendName",
    "BaseCache",
    "CacheEntry",
    "CacheMissError",
    "CacheStats",
    "Client",
    "FileCache",
    "KeyFn",
    "MemoryCache",
    "PolicyController",
    "PolicyName",
    "RedisCache",
    "SqliteCache",
    "SyncCacheTransport",
    "default_key_fn",
    "wrap",
]


def __getattr__(name: str) -> Any:
    if name in ("Client", "AsyncClient"):
        sync_cls, async_cls = build_client_classes()
        globals()["Client"] = sync_cls
        globals()["AsyncClient"] = async_cls
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
