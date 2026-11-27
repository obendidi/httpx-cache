from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import timedelta
from types import TracebackType
from typing import Any

from httpx_cache._backend import Backend, detect_backend_from_obj, get_backend
from httpx_cache.cache.base import BaseCache
from httpx_cache.cache.sqlite import SqliteCache
from httpx_cache.keys import (
    default_key_fn,
    read_request_body_async,
    read_request_body_sync,
)
from httpx_cache.policy import PolicyController
from httpx_cache.types import BackendName, CacheMissError, KeyFn, PolicyName

logger = logging.getLogger(__name__)


class SyncCacheTransport:
    """Synchronous caching transport compatible with both ``httpx`` and ``httpx2``."""

    def __init__(
        self,
        transport: Any | None = None,
        *,
        cache: BaseCache | None = None,
        policy: PolicyName = "force",
        ttl: float | timedelta | None = None,
        cache_post: bool = False,
        cacheable_methods: Sequence[str] | None = None,
        cacheable_status_codes: Sequence[int] | None = None,
        key_fn: KeyFn | None = None,
        shared: bool = False,
        backend: BackendName | None = None,
        _owns_cache: bool | None = None,
    ) -> None:
        self.controller = PolicyController(
            policy=policy,
            ttl=ttl,
            cache_post=cache_post,
            cacheable_methods=cacheable_methods,
            cacheable_status_codes=cacheable_status_codes,
            shared=shared,
        )
        self.key_fn: KeyFn = key_fn or default_key_fn
        self._owns_cache = (cache is None) if _owns_cache is None else _owns_cache
        self.cache: BaseCache = cache if cache is not None else SqliteCache()

        detected = detect_backend_from_obj(transport)
        if backend is not None:
            self._backend: Backend | None = get_backend(backend)
        elif detected is not None:
            self._backend = detected
        else:
            self._backend = None

        if transport is not None:
            self.transport: Any = transport
        elif policy == "replay":
            self.transport = None
        else:
            active_backend = self._backend or get_backend()
            self._backend = active_backend
            self.transport = active_backend.HTTPTransport()

    def _resolve_backend(self, request: Any) -> Backend:
        if self._backend is not None:
            return self._backend
        detected = detect_backend_from_obj(request)
        if detected is not None:
            return detected
        return get_backend()

    def handle_request(self, request: Any) -> Any:
        backend = self._resolve_backend(request)

        if self.controller.needs_request_body(request):
            read_request_body_sync(request)

        key = self.key_fn(request)

        # Replay mode: strictly offline, never touches upstream transport.
        if self.controller.policy == "replay":
            entry = self.cache.get(key, ignore_expiry=True)
            if entry is None:
                raise CacheMissError(key=key, request=request)
            return backend.build_response(
                entry,
                request=request,
                extensions={"from_cache": True, "cache_key": key},
            )

        cached_entry = None
        revalidate = False
        if self.controller.should_lookup(request):
            cached_entry = self.cache.get(key)
            if cached_entry is not None:
                decision = self.controller.evaluate_cached(request, cached_entry)
                if decision == "fresh":
                    return backend.build_response(
                        cached_entry,
                        request=request,
                        extensions={"from_cache": True, "cache_key": key},
                    )
                if decision == "revalidate":
                    revalidate = True
                else:
                    self.cache.delete(key)
                    cached_entry = None

        if self.transport is None:
            raise RuntimeError("No upstream transport configured for cache miss.")

        upstream_request = request
        if revalidate and cached_entry is not None:
            cond_headers = self.controller.conditional_headers(cached_entry)
            if cond_headers:
                upstream_request = backend.clone_request_with_headers(request, cond_headers)

        response = self.transport.handle_request(upstream_request)

        if revalidate and cached_entry is not None and int(response.status_code) == 304:
            try:
                response.read()
            finally:
                response.close()
            merged = self.controller.merge_revalidated_entry(request, cached_entry, response)
            self.cache.set(key, merged)
            return backend.build_response(
                merged,
                request=request,
                extensions={"from_cache": True, "revalidated": True, "cache_key": key},
            )

        response.extensions["from_cache"] = False
        response.extensions["cache_key"] = key

        if self.controller.should_store(request, response):
            if hasattr(response, "_content"):
                entry = self.controller.build_entry(
                    request,
                    response,
                    body=bytes(response.content),
                    raw_stream=False,
                )
                self.cache.set(key, entry)
            else:
                def _on_complete(content: bytes) -> None:
                    entry = self.controller.build_entry(
                        request,
                        response,
                        body=content,
                        raw_stream=True,
                    )
                    self.cache.set(key, entry)

                response.stream = backend.wrap_sync_stream(response.stream, _on_complete)

        return response

    def close(self) -> None:
        if self.transport is not None and hasattr(self.transport, "close"):
            self.transport.close()
        if self._owns_cache:
            self.cache.close()

    def __enter__(self) -> SyncCacheTransport:
        if self.transport is not None and hasattr(self.transport, "__enter__"):
            self.transport.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.transport is not None and hasattr(self.transport, "__exit__"):
            self.transport.__exit__(exc_type, exc_val, exc_tb)
        if self._owns_cache:
            self.cache.close()


class AsyncCacheTransport:
    """Asynchronous caching transport compatible with both ``httpx`` and ``httpx2``."""

    def __init__(
        self,
        transport: Any | None = None,
        *,
        cache: BaseCache | None = None,
        policy: PolicyName = "force",
        ttl: float | timedelta | None = None,
        cache_post: bool = False,
        cacheable_methods: Sequence[str] | None = None,
        cacheable_status_codes: Sequence[int] | None = None,
        key_fn: KeyFn | None = None,
        shared: bool = False,
        backend: BackendName | None = None,
        _owns_cache: bool | None = None,
    ) -> None:
        self.controller = PolicyController(
            policy=policy,
            ttl=ttl,
            cache_post=cache_post,
            cacheable_methods=cacheable_methods,
            cacheable_status_codes=cacheable_status_codes,
            shared=shared,
        )
        self.key_fn: KeyFn = key_fn or default_key_fn
        self._owns_cache = (cache is None) if _owns_cache is None else _owns_cache
        self.cache: BaseCache = cache if cache is not None else SqliteCache()

        detected = detect_backend_from_obj(transport)
        if backend is not None:
            self._backend: Backend | None = get_backend(backend)
        elif detected is not None:
            self._backend = detected
        else:
            self._backend = None

        if transport is not None:
            self.transport: Any = transport
        elif policy == "replay":
            self.transport = None
        else:
            active_backend = self._backend or get_backend()
            self._backend = active_backend
            self.transport = active_backend.AsyncHTTPTransport()

    def _resolve_backend(self, request: Any) -> Backend:
        if self._backend is not None:
            return self._backend
        detected = detect_backend_from_obj(request)
        if detected is not None:
            return detected
        return get_backend()

    async def handle_async_request(self, request: Any) -> Any:
        backend = self._resolve_backend(request)

        if self.controller.needs_request_body(request):
            await read_request_body_async(request)

        key = self.key_fn(request)

        if self.controller.policy == "replay":
            entry = await self.cache.aget(key, ignore_expiry=True)
            if entry is None:
                raise CacheMissError(key=key, request=request)
            return backend.build_response(
                entry,
                request=request,
                extensions={"from_cache": True, "cache_key": key},
            )

        cached_entry = None
        revalidate = False
        if self.controller.should_lookup(request):
            cached_entry = await self.cache.aget(key)
            if cached_entry is not None:
                decision = self.controller.evaluate_cached(request, cached_entry)
                if decision == "fresh":
                    return backend.build_response(
                        cached_entry,
                        request=request,
                        extensions={"from_cache": True, "cache_key": key},
                    )
                if decision == "revalidate":
                    revalidate = True
                else:
                    await self.cache.adelete(key)
                    cached_entry = None

        if self.transport is None:
            raise RuntimeError("No upstream transport configured for cache miss.")

        upstream_request = request
        if revalidate and cached_entry is not None:
            cond_headers = self.controller.conditional_headers(cached_entry)
            if cond_headers:
                upstream_request = backend.clone_request_with_headers(request, cond_headers)

        response = await self.transport.handle_async_request(upstream_request)

        if revalidate and cached_entry is not None and int(response.status_code) == 304:
            try:
                await response.aread()
            finally:
                await response.aclose()
            merged = self.controller.merge_revalidated_entry(request, cached_entry, response)
            await self.cache.aset(key, merged)
            return backend.build_response(
                merged,
                request=request,
                extensions={"from_cache": True, "revalidated": True, "cache_key": key},
            )

        response.extensions["from_cache"] = False
        response.extensions["cache_key"] = key

        if self.controller.should_store(request, response):
            if hasattr(response, "_content"):
                entry = self.controller.build_entry(
                    request,
                    response,
                    body=bytes(response.content),
                    raw_stream=False,
                )
                await self.cache.aset(key, entry)
            else:
                async def _on_complete(content: bytes) -> None:
                    entry = self.controller.build_entry(
                        request,
                        response,
                        body=content,
                        raw_stream=True,
                    )
                    await self.cache.aset(key, entry)

                response.stream = backend.wrap_async_stream(response.stream, _on_complete)

        return response

    async def aclose(self) -> None:
        if self.transport is not None and hasattr(self.transport, "aclose"):
            await self.transport.aclose()
        if self._owns_cache:
            await self.cache.aclose()

    async def __aenter__(self) -> AsyncCacheTransport:
        if self.transport is not None and hasattr(self.transport, "__aenter__"):
            await self.transport.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.transport is not None and hasattr(self.transport, "__aexit__"):
            await self.transport.__aexit__(exc_type, exc_val, exc_tb)
        if self._owns_cache:
            await self.cache.aclose()
