"""Explicit ``httpx2`` client classes for environments where both ``httpx`` and ``httpx2`` exist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from httpx_cache.client import build_client_classes, wrap
from httpx_cache.transport import AsyncCacheTransport, SyncCacheTransport

if TYPE_CHECKING:
    Client: type[Any]
    AsyncClient: type[Any]

__all__ = [
    "AsyncCacheTransport",
    "AsyncClient",
    "Client",
    "SyncCacheTransport",
    "wrap",
]


def __getattr__(name: str) -> Any:
    if name in ("Client", "AsyncClient"):
        sync_cls, async_cls = build_client_classes("httpx2")
        globals()["Client"] = sync_cls
        globals()["AsyncClient"] = async_cls
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
