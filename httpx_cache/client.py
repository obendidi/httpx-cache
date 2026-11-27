from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any, TypeVar

from httpx_cache._backend import Backend, detect_backend_from_obj, get_backend
from httpx_cache.cache.base import BaseCache
from httpx_cache.cache.sqlite import SqliteCache
from httpx_cache.transport import AsyncCacheTransport, SyncCacheTransport
from httpx_cache.types import BackendName, KeyFn, PolicyName

TClient = TypeVar("TClient")


def wrap(
    client: TClient,
    *,
    cache: BaseCache | None = None,
    policy: PolicyName = "force",
    ttl: float | timedelta | None = None,
    cache_post: bool = False,
    cacheable_methods: Sequence[str] | None = None,
    cacheable_status_codes: Sequence[int] | None = None,
    key_fn: KeyFn | None = None,
    shared: bool = False,
) -> TClient:
    """Wrap an existing ``httpx`` or ``httpx2`` Client/AsyncClient with caching in place.

    Automatically detects sync vs async and ``httpx`` vs ``httpx2`` from ``client``.
    Wraps both the default transport and any configured mounted transports.
    """
    backend = detect_backend_from_obj(client)
    if backend is None:
        raise TypeError(
            f"Expected an httpx or httpx2 Client/AsyncClient, got {type(client).__name__}."
        )

    is_async = isinstance(client, backend.AsyncClient)
    is_sync = isinstance(client, backend.Client)
    if not is_async and not is_sync:
        raise TypeError(
            f"Expected an httpx or httpx2 Client/AsyncClient, got {type(client).__name__}."
        )

    owns_cache = cache is None
    resolved_cache: BaseCache = cache if cache is not None else SqliteCache()
    transport_cls: type[Any] = AsyncCacheTransport if is_async else SyncCacheTransport

    common_kwargs: dict[str, Any] = {
        "cache": resolved_cache,
        "policy": policy,
        "ttl": ttl,
        "cache_post": cache_post,
        "cacheable_methods": cacheable_methods,
        "cacheable_status_codes": cacheable_status_codes,
        "key_fn": key_fn,
        "shared": shared,
        "backend": backend.name,
    }

    current_transport = getattr(client, "_transport", None)
    if current_transport is not None and not isinstance(current_transport, transport_cls):
        client._transport = transport_cls(  # type: ignore[attr-defined]
            current_transport,
            _owns_cache=owns_cache,
            **common_kwargs,
        )
        owns_cache = False

    mounts: dict[Any, Any] | None = getattr(client, "_mounts", None)
    if mounts:
        for pattern, mounted in list(mounts.items()):
            if mounted is not None and not isinstance(mounted, transport_cls):
                mounts[pattern] = transport_cls(
                    mounted,
                    _owns_cache=owns_cache,
                    **common_kwargs,
                )
                owns_cache = False

    return client


_CLIENT_CLASS_CACHE: dict[BackendName, tuple[type[Any], type[Any]]] = {}


def build_client_classes(backend_name: BackendName | None = None) -> tuple[type[Any], type[Any]]:
    """Build (Client, AsyncClient) subclasses for the chosen or detected backend."""
    backend: Backend = get_backend(backend_name)
    cached = _CLIENT_CLASS_CACHE.get(backend.name)
    if cached is not None:
        return cached

    base_sync = backend.Client
    base_async = backend.AsyncClient

    class CachedClient(base_sync):  # type: ignore[valid-type, misc]
        """Caching drop-in replacement for Client."""

        def __init__(
            self,
            *args: Any,
            cache: BaseCache | None = None,
            policy: PolicyName = "force",
            ttl: float | timedelta | None = None,
            cache_post: bool = False,
            cacheable_methods: Sequence[str] | None = None,
            cacheable_status_codes: Sequence[int] | None = None,
            key_fn: KeyFn | None = None,
            shared: bool = False,
            **kwargs: Any,
        ) -> None:
            super().__init__(*args, **kwargs)
            existing = getattr(self, "_transport", None)
            if isinstance(existing, SyncCacheTransport):
                self.cache: BaseCache = existing.cache
            else:
                resolved = cache if cache is not None else SqliteCache()
                self.cache = resolved
                wrap(
                    self,
                    cache=resolved,
                    policy=policy,
                    ttl=ttl,
                    cache_post=cache_post,
                    cacheable_methods=cacheable_methods,
                    cacheable_status_codes=cacheable_status_codes,
                    key_fn=key_fn,
                    shared=shared,
                )
                if cache is None and isinstance(self._transport, SyncCacheTransport):
                    self._transport._owns_cache = True

    class CachedAsyncClient(base_async):  # type: ignore[valid-type, misc]
        """Caching drop-in replacement for AsyncClient."""

        def __init__(
            self,
            *args: Any,
            cache: BaseCache | None = None,
            policy: PolicyName = "force",
            ttl: float | timedelta | None = None,
            cache_post: bool = False,
            cacheable_methods: Sequence[str] | None = None,
            cacheable_status_codes: Sequence[int] | None = None,
            key_fn: KeyFn | None = None,
            shared: bool = False,
            **kwargs: Any,
        ) -> None:
            super().__init__(*args, **kwargs)
            existing = getattr(self, "_transport", None)
            if isinstance(existing, AsyncCacheTransport):
                self.cache: BaseCache = existing.cache
            else:
                resolved = cache if cache is not None else SqliteCache()
                self.cache = resolved
                wrap(
                    self,
                    cache=resolved,
                    policy=policy,
                    ttl=ttl,
                    cache_post=cache_post,
                    cacheable_methods=cacheable_methods,
                    cacheable_status_codes=cacheable_status_codes,
                    key_fn=key_fn,
                    shared=shared,
                )
                if cache is None and isinstance(self._transport, AsyncCacheTransport):
                    self._transport._owns_cache = True

    CachedClient.__name__ = "Client"
    CachedClient.__qualname__ = "Client"
    CachedAsyncClient.__name__ = "AsyncClient"
    CachedAsyncClient.__qualname__ = "AsyncClient"

    pair = (CachedClient, CachedAsyncClient)
    _CLIENT_CLASS_CACHE[backend.name] = pair
    return pair
