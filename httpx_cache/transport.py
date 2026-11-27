from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
from collections.abc import Mapping, Sequence
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
from httpx_cache.policy import _UNSET, PolicyController, vary_variant_key
from httpx_cache.types import (
    BackendName,
    CacheEntry,
    CacheHitHook,
    CacheMissError,
    CacheMissHook,
    CacheStoreHook,
    KeyFn,
    PolicyName,
    ShouldCacheFn,
    _suggest_closest_keys,
)

logger = logging.getLogger(__name__)

_VARY_INDEX_PREFIX = "__vary__:"


def _request_cache_options(request: Any) -> dict[str, Any]:
    extensions = getattr(request, "extensions", None)
    if not isinstance(extensions, Mapping):
        return {}
    opts = extensions.get("cache")
    return dict(opts) if isinstance(opts, Mapping) else {}


def _parse_vary_index(entry: CacheEntry | None) -> tuple[str, ...]:
    if entry is None:
        return ()
    try:
        items = json.loads(entry.body.decode("utf-8"))
        if isinstance(items, list):
            return tuple(str(x).lower() for x in items)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ()
    return ()


def _make_vary_index_entry(vary_headers: Sequence[str]) -> CacheEntry:
    return CacheEntry(
        status_code=200,
        headers=(),
        body=json.dumps(list(vary_headers)).encode("utf-8"),
        metadata={"vary_index": True},
    )


def _resolve_max_cacheable_bytes(cache: BaseCache, explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    cap = getattr(cache, "max_size_bytes", None)
    return int(cap) if isinstance(cap, int) else None


def _passes_should_cache(
    should_cache: ShouldCacheFn | None,
    backend: Backend,
    request: Any,
    response: Any,
    entry: CacheEntry,
) -> bool:
    if should_cache is None:
        return True
    if hasattr(response, "_content"):
        return bool(should_cache(request, response))
    # For unread streams, give the predicate a readable copy without mutating the caller's stream.
    readable = backend.build_response(entry, request=request)
    if not hasattr(readable, "_content"):
        readable.read()
    return bool(should_cache(request, readable))


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
        urls_expire_after: Mapping[str, float | timedelta | None] | None = None,
        stale_if_error: bool | float | timedelta = False,
        scrub_headers: Sequence[str] = (),
        should_cache: ShouldCacheFn | None = None,
        coalesce: bool = False,
        max_cacheable_bytes: int | None = None,
        on_hit: CacheHitHook | None = None,
        on_miss: CacheMissHook | None = None,
        on_store: CacheStoreHook | None = None,
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
            urls_expire_after=urls_expire_after,
            stale_if_error=stale_if_error,
            scrub_headers=scrub_headers,
        )
        self.key_fn: KeyFn = key_fn or default_key_fn
        self.should_cache = should_cache
        self.coalesce = coalesce
        self.on_hit = on_hit
        self.on_miss = on_miss
        self.on_store = on_store
        self._owns_cache = (cache is None) if _owns_cache is None else _owns_cache
        self.cache: BaseCache = cache if cache is not None else SqliteCache()
        self.max_cacheable_bytes = _resolve_max_cacheable_bytes(self.cache, max_cacheable_bytes)

        self._inflight_lock = threading.Lock()
        self._inflight: dict[str, threading.Event] = {}

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

    def _lookup_entry(self, base_key: str, request: Any) -> tuple[str, CacheEntry | None]:
        ignore_expiry = self.controller.stale_if_error_enabled
        if self.controller.policy == "rfc9111":
            idx_entry = self.cache.get(f"{_VARY_INDEX_PREFIX}{base_key}", ignore_expiry=True)
            vary_hdrs = _parse_vary_index(idx_entry)
            if vary_hdrs:
                vkey = vary_variant_key(base_key, request, vary_hdrs)
                return vkey, self.cache.get(vkey, ignore_expiry=ignore_expiry)
        return base_key, self.cache.get(base_key, ignore_expiry=ignore_expiry)

    def _store_entry(
        self,
        base_key: str,
        request: Any,
        response: Any,
        entry: CacheEntry,
    ) -> str:
        vary_hdrs = self.controller.vary_headers_for_response(response)
        if vary_hdrs:
            self.cache.set(
                f"{_VARY_INDEX_PREFIX}{base_key}",
                _make_vary_index_entry(vary_hdrs),
            )
            storage_key = vary_variant_key(base_key, request, vary_hdrs)
        else:
            storage_key = base_key
        self.cache.set(storage_key, entry)
        if self.on_store is not None:
            self.on_store(storage_key, request, entry)
        return storage_key

    def _release_inflight(self, key: str, event: threading.Event | None) -> None:
        if event is None:
            return
        with self._inflight_lock:
            if self._inflight.get(key) is event:
                del self._inflight[key]
        event.set()

    def handle_request(self, request: Any) -> Any:
        backend = self._resolve_backend(request)
        req_opts = _request_cache_options(request)

        if req_opts.get("disabled"):
            if self.transport is None:
                raise RuntimeError("No upstream transport configured.")
            response = self.transport.handle_request(request)
            response.extensions["from_cache"] = False
            return response

        force_refresh = bool(req_opts.get("force_refresh", False))
        override_ttl = req_opts.get("ttl", _UNSET)

        if self.controller.needs_request_body(request):
            read_request_body_sync(request)

        base_key = str(req_opts["key"]) if "key" in req_opts else self.key_fn(request)

        # Replay mode: strictly offline, never touches upstream transport.
        if self.controller.policy == "replay":
            entry = self.cache.get(base_key, ignore_expiry=True)
            if entry is None:
                if self.on_miss is not None:
                    self.on_miss(base_key, request)
                recorded = [
                    k for k in self.cache.keys("") if not k.startswith(_VARY_INDEX_PREFIX)
                ]
                closest = _suggest_closest_keys(base_key, recorded)
                raise CacheMissError(key=base_key, request=request, closest_keys=closest)
            if self.on_hit is not None:
                self.on_hit(base_key, request)
            return backend.build_response(
                entry,
                request=request,
                extensions={"from_cache": True, "cache_key": base_key},
            )

        lookup_allowed = self.controller.should_lookup(request, override_ttl=override_ttl)
        leader_event: threading.Event | None = None

        while True:
            cached_entry: CacheEntry | None = None
            storage_key = base_key
            revalidate = False

            if lookup_allowed and not force_refresh:
                storage_key, cached_entry = self._lookup_entry(base_key, request)
                if cached_entry is not None:
                    decision = self.controller.evaluate_cached(request, cached_entry)
                    if decision == "fresh":
                        if self.on_hit is not None:
                            self.on_hit(storage_key, request)
                        return backend.build_response(
                            cached_entry,
                            request=request,
                            extensions={"from_cache": True, "cache_key": storage_key},
                        )
                    if decision == "revalidate":
                        revalidate = True
                    elif not self.controller.can_serve_stale_on_error(cached_entry):
                        self.cache.delete(storage_key)
                        cached_entry = None

            if not (self.coalesce and lookup_allowed and not force_refresh):
                break

            with self._inflight_lock:
                existing_event = self._inflight.get(base_key)
                if existing_event is None:
                    leader_event = threading.Event()
                    self._inflight[base_key] = leader_event
                    break
            existing_event.wait()
            # Re-check cache once the leader finishes; if still a miss, avoid infinite wait.
            storage_key, cached_entry = self._lookup_entry(base_key, request)
            if cached_entry is not None and (
                self.controller.evaluate_cached(request, cached_entry) == "fresh"
            ):
                if self.on_hit is not None:
                    self.on_hit(storage_key, request)
                return backend.build_response(
                    cached_entry,
                    request=request,
                    extensions={"from_cache": True, "cache_key": storage_key},
                )
            break

        if self.on_miss is not None:
            self.on_miss(base_key, request)

        stale_fallback = (
            cached_entry
            if cached_entry is not None and self.controller.can_serve_stale_on_error(cached_entry)
            else None
        )

        released_by_stream = False
        try:
            if self.transport is None:
                raise RuntimeError("No upstream transport configured for cache miss.")

            upstream_request = request
            if revalidate and cached_entry is not None:
                cond_headers = self.controller.conditional_headers(cached_entry)
                if cond_headers:
                    upstream_request = backend.clone_request_with_headers(request, cond_headers)

            try:
                response = self.transport.handle_request(upstream_request)
            except (backend.HTTPError, OSError):
                if stale_fallback is not None:
                    if self.on_hit is not None:
                        self.on_hit(storage_key, request)
                    return backend.build_response(
                        stale_fallback,
                        request=request,
                        extensions={
                            "from_cache": True,
                            "stale": True,
                            "cache_key": storage_key,
                        },
                    )
                raise

            if stale_fallback is not None and 500 <= int(response.status_code) < 600:
                with contextlib.suppress(Exception):
                    response.close()
                if self.on_hit is not None:
                    self.on_hit(storage_key, request)
                return backend.build_response(
                    stale_fallback,
                    request=request,
                    extensions={
                        "from_cache": True,
                        "stale": True,
                        "cache_key": storage_key,
                    },
                )

            if revalidate and cached_entry is not None and int(response.status_code) == 304:
                try:
                    response.read()
                finally:
                    response.close()
                merged = self.controller.merge_revalidated_entry(
                    request, cached_entry, response, override_ttl=override_ttl
                )
                self.cache.set(storage_key, merged)
                if self.on_store is not None:
                    self.on_store(storage_key, request, merged)
                if self.on_hit is not None:
                    self.on_hit(storage_key, request)
                return backend.build_response(
                    merged,
                    request=request,
                    extensions={
                        "from_cache": True,
                        "revalidated": True,
                        "cache_key": storage_key,
                    },
                )

            response.extensions["from_cache"] = False
            response.extensions["cache_key"] = base_key

            if self.controller.should_store(request, response, override_ttl=override_ttl):
                if hasattr(response, "_content"):
                    body = bytes(response.content)
                    within_cap = (
                        self.max_cacheable_bytes is None
                        or len(body) <= self.max_cacheable_bytes
                    )
                    if within_cap:
                        entry = self.controller.build_entry(
                            request,
                            response,
                            body=body,
                            raw_stream=False,
                            override_ttl=override_ttl,
                        )
                        if _passes_should_cache(
                            self.should_cache, backend, request, response, entry
                        ):
                            saved_key = self._store_entry(base_key, request, response, entry)
                            response.extensions["cache_key"] = saved_key
                else:
                    def _on_complete(content: bytes) -> None:
                        entry = self.controller.build_entry(
                            request,
                            response,
                            body=content,
                            raw_stream=True,
                            override_ttl=override_ttl,
                        )
                        if _passes_should_cache(
                            self.should_cache, backend, request, response, entry
                        ):
                            saved_key = self._store_entry(base_key, request, response, entry)
                            response.extensions["cache_key"] = saved_key

                    def _on_finish() -> None:
                        self._release_inflight(base_key, leader_event)

                    response.stream = backend.wrap_sync_stream(
                        response.stream,
                        _on_complete,
                        max_bytes=self.max_cacheable_bytes,
                        on_finish=_on_finish if leader_event is not None else None,
                    )
                    released_by_stream = leader_event is not None

            return response
        finally:
            if not released_by_stream:
                self._release_inflight(base_key, leader_event)

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
        urls_expire_after: Mapping[str, float | timedelta | None] | None = None,
        stale_if_error: bool | float | timedelta = False,
        scrub_headers: Sequence[str] = (),
        should_cache: ShouldCacheFn | None = None,
        coalesce: bool = False,
        max_cacheable_bytes: int | None = None,
        on_hit: CacheHitHook | None = None,
        on_miss: CacheMissHook | None = None,
        on_store: CacheStoreHook | None = None,
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
            urls_expire_after=urls_expire_after,
            stale_if_error=stale_if_error,
            scrub_headers=scrub_headers,
        )
        self.key_fn: KeyFn = key_fn or default_key_fn
        self.should_cache = should_cache
        self.coalesce = coalesce
        self.on_hit = on_hit
        self.on_miss = on_miss
        self.on_store = on_store
        self._owns_cache = (cache is None) if _owns_cache is None else _owns_cache
        self.cache: BaseCache = cache if cache is not None else SqliteCache()
        self.max_cacheable_bytes = _resolve_max_cacheable_bytes(self.cache, max_cacheable_bytes)

        self._inflight: dict[str, asyncio.Event] = {}

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

    async def _alookup_entry(self, base_key: str, request: Any) -> tuple[str, CacheEntry | None]:
        ignore_expiry = self.controller.stale_if_error_enabled
        if self.controller.policy == "rfc9111":
            idx_entry = await self.cache.aget(f"{_VARY_INDEX_PREFIX}{base_key}", ignore_expiry=True)
            vary_hdrs = _parse_vary_index(idx_entry)
            if vary_hdrs:
                vkey = vary_variant_key(base_key, request, vary_hdrs)
                return vkey, await self.cache.aget(vkey, ignore_expiry=ignore_expiry)
        return base_key, await self.cache.aget(base_key, ignore_expiry=ignore_expiry)

    async def _astore_entry(
        self,
        base_key: str,
        request: Any,
        response: Any,
        entry: CacheEntry,
    ) -> str:
        vary_hdrs = self.controller.vary_headers_for_response(response)
        if vary_hdrs:
            await self.cache.aset(
                f"{_VARY_INDEX_PREFIX}{base_key}",
                _make_vary_index_entry(vary_hdrs),
            )
            storage_key = vary_variant_key(base_key, request, vary_hdrs)
        else:
            storage_key = base_key
        await self.cache.aset(storage_key, entry)
        if self.on_store is not None:
            self.on_store(storage_key, request, entry)
        return storage_key

    def _release_inflight(self, key: str, event: asyncio.Event | None) -> None:
        if event is None:
            return
        if self._inflight.get(key) is event:
            del self._inflight[key]
        event.set()

    async def handle_async_request(self, request: Any) -> Any:
        backend = self._resolve_backend(request)
        req_opts = _request_cache_options(request)

        if req_opts.get("disabled"):
            if self.transport is None:
                raise RuntimeError("No upstream transport configured.")
            response = await self.transport.handle_async_request(request)
            response.extensions["from_cache"] = False
            return response

        force_refresh = bool(req_opts.get("force_refresh", False))
        override_ttl = req_opts.get("ttl", _UNSET)

        if self.controller.needs_request_body(request):
            await read_request_body_async(request)

        base_key = str(req_opts["key"]) if "key" in req_opts else self.key_fn(request)

        if self.controller.policy == "replay":
            entry = await self.cache.aget(base_key, ignore_expiry=True)
            if entry is None:
                if self.on_miss is not None:
                    self.on_miss(base_key, request)
                recorded = [
                    k for k in await self.cache.akeys() if not k.startswith(_VARY_INDEX_PREFIX)
                ]
                closest = _suggest_closest_keys(base_key, recorded)
                raise CacheMissError(key=base_key, request=request, closest_keys=closest)
            if self.on_hit is not None:
                self.on_hit(base_key, request)
            return backend.build_response(
                entry,
                request=request,
                extensions={"from_cache": True, "cache_key": base_key},
            )

        lookup_allowed = self.controller.should_lookup(request, override_ttl=override_ttl)
        leader_event: asyncio.Event | None = None

        while True:
            cached_entry: CacheEntry | None = None
            storage_key = base_key
            revalidate = False

            if lookup_allowed and not force_refresh:
                storage_key, cached_entry = await self._alookup_entry(base_key, request)
                if cached_entry is not None:
                    decision = self.controller.evaluate_cached(request, cached_entry)
                    if decision == "fresh":
                        if self.on_hit is not None:
                            self.on_hit(storage_key, request)
                        return backend.build_response(
                            cached_entry,
                            request=request,
                            extensions={"from_cache": True, "cache_key": storage_key},
                        )
                    if decision == "revalidate":
                        revalidate = True
                    elif not self.controller.can_serve_stale_on_error(cached_entry):
                        await self.cache.adelete(storage_key)
                        cached_entry = None

            if not (self.coalesce and lookup_allowed and not force_refresh):
                break

            existing_event = self._inflight.get(base_key)
            if existing_event is None:
                leader_event = asyncio.Event()
                self._inflight[base_key] = leader_event
                break

            await existing_event.wait()
            storage_key, cached_entry = await self._alookup_entry(base_key, request)
            if cached_entry is not None and (
                self.controller.evaluate_cached(request, cached_entry) == "fresh"
            ):
                if self.on_hit is not None:
                    self.on_hit(storage_key, request)
                return backend.build_response(
                    cached_entry,
                    request=request,
                    extensions={"from_cache": True, "cache_key": storage_key},
                )
            break

        if self.on_miss is not None:
            self.on_miss(base_key, request)

        stale_fallback = (
            cached_entry
            if cached_entry is not None and self.controller.can_serve_stale_on_error(cached_entry)
            else None
        )

        released_by_stream = False
        try:
            if self.transport is None:
                raise RuntimeError("No upstream transport configured for cache miss.")

            upstream_request = request
            if revalidate and cached_entry is not None:
                cond_headers = self.controller.conditional_headers(cached_entry)
                if cond_headers:
                    upstream_request = backend.clone_request_with_headers(request, cond_headers)

            try:
                response = await self.transport.handle_async_request(upstream_request)
            except (backend.HTTPError, OSError):
                if stale_fallback is not None:
                    if self.on_hit is not None:
                        self.on_hit(storage_key, request)
                    return backend.build_response(
                        stale_fallback,
                        request=request,
                        extensions={
                            "from_cache": True,
                            "stale": True,
                            "cache_key": storage_key,
                        },
                    )
                raise

            if stale_fallback is not None and 500 <= int(response.status_code) < 600:
                with contextlib.suppress(Exception):
                    await response.aclose()
                if self.on_hit is not None:
                    self.on_hit(storage_key, request)
                return backend.build_response(
                    stale_fallback,
                    request=request,
                    extensions={
                        "from_cache": True,
                        "stale": True,
                        "cache_key": storage_key,
                    },
                )

            if revalidate and cached_entry is not None and int(response.status_code) == 304:
                try:
                    await response.aread()
                finally:
                    await response.aclose()
                merged = self.controller.merge_revalidated_entry(
                    request, cached_entry, response, override_ttl=override_ttl
                )
                await self.cache.aset(storage_key, merged)
                if self.on_store is not None:
                    self.on_store(storage_key, request, merged)
                if self.on_hit is not None:
                    self.on_hit(storage_key, request)
                return backend.build_response(
                    merged,
                    request=request,
                    extensions={
                        "from_cache": True,
                        "revalidated": True,
                        "cache_key": storage_key,
                    },
                )

            response.extensions["from_cache"] = False
            response.extensions["cache_key"] = base_key

            if self.controller.should_store(request, response, override_ttl=override_ttl):
                if hasattr(response, "_content"):
                    body = bytes(response.content)
                    within_cap = (
                        self.max_cacheable_bytes is None
                        or len(body) <= self.max_cacheable_bytes
                    )
                    if within_cap:
                        entry = self.controller.build_entry(
                            request,
                            response,
                            body=body,
                            raw_stream=False,
                            override_ttl=override_ttl,
                        )
                        if _passes_should_cache(
                            self.should_cache, backend, request, response, entry
                        ):
                            saved_key = await self._astore_entry(base_key, request, response, entry)
                            response.extensions["cache_key"] = saved_key
                else:
                    async def _on_complete(content: bytes) -> None:
                        entry = self.controller.build_entry(
                            request,
                            response,
                            body=content,
                            raw_stream=True,
                            override_ttl=override_ttl,
                        )
                        if _passes_should_cache(
                            self.should_cache, backend, request, response, entry
                        ):
                            saved_key = await self._astore_entry(base_key, request, response, entry)
                            response.extensions["cache_key"] = saved_key

                    def _on_finish() -> None:
                        self._release_inflight(base_key, leader_event)

                    response.stream = backend.wrap_async_stream(
                        response.stream,
                        _on_complete,
                        max_bytes=self.max_cacheable_bytes,
                        on_finish=_on_finish if leader_event is not None else None,
                    )
                    released_by_stream = leader_event is not None

            return response
        finally:
            if not released_by_stream:
                self._release_inflight(base_key, leader_event)

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
