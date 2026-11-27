from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Protocol, runtime_checkable

from httpx_cache.types import BackendName, CacheEntry


@runtime_checkable
class HeadersLike(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def get_list(self, key: str, split_commas: bool = False) -> list[str]: ...
    def multi_items(self) -> list[tuple[str, str]]: ...
    def __contains__(self, key: Any) -> bool: ...


@runtime_checkable
class RequestLike(Protocol):
    method: str
    url: Any
    headers: HeadersLike
    stream: Any

    @property
    def content(self) -> bytes: ...
    def read(self) -> bytes: ...
    async def aread(self) -> bytes: ...


@runtime_checkable
class ResponseLike(Protocol):
    status_code: int
    headers: HeadersLike
    extensions: dict[str, Any]
    stream: Any
    request: Any
    http_version: str
    encoding: str | None

    @property
    def content(self) -> bytes: ...
    def read(self) -> bytes: ...
    async def aread(self) -> bytes: ...


@dataclass(frozen=True, slots=True)
class Backend:
    """Thin adapter around either ``httpx`` or ``httpx2``."""

    name: BackendName
    module: ModuleType
    _sync_wrapper_cls: type[Any] = field(init=False, repr=False, compare=False)
    _async_wrapper_cls: type[Any] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        sync_base = self.module.SyncByteStream
        async_base = self.module.AsyncByteStream

        class _SyncByteStreamWrapper(sync_base):  # type: ignore[valid-type, misc]
            def __init__(
                self,
                stream: Any,
                on_complete: Callable[[bytes], None],
                *,
                max_bytes: int | None = None,
                on_finish: Callable[[], None] | None = None,
            ) -> None:
                self._stream = stream
                self._on_complete = on_complete
                self._max_bytes = max_bytes
                self._on_finish = on_finish
                self._chunks = bytearray()
                self._exceeded = False
                self._completed = False
                self._finished = False

            def _notify_finish(self) -> None:
                if not self._finished:
                    self._finished = True
                    if self._on_finish is not None:
                        self._on_finish()

            def __iter__(self) -> Iterator[bytes]:
                try:
                    for chunk in self._stream:
                        if not self._exceeded:
                            if (
                                self._max_bytes is not None
                                and len(self._chunks) + len(chunk) > self._max_bytes
                            ):
                                self._exceeded = True
                                self._chunks.clear()
                            else:
                                self._chunks.extend(chunk)
                        yield chunk
                    if not self._completed and not self._exceeded:
                        self._completed = True
                        self._on_complete(bytes(self._chunks))
                finally:
                    self._notify_finish()

            def close(self) -> None:
                try:
                    if hasattr(self._stream, "close"):
                        self._stream.close()
                finally:
                    self._notify_finish()

        class _AsyncByteStreamWrapper(async_base):  # type: ignore[valid-type, misc]
            def __init__(
                self,
                stream: Any,
                on_complete: Callable[[bytes], Awaitable[None]],
                *,
                max_bytes: int | None = None,
                on_finish: Callable[[], None] | None = None,
            ) -> None:
                self._stream = stream
                self._on_complete = on_complete
                self._max_bytes = max_bytes
                self._on_finish = on_finish
                self._chunks = bytearray()
                self._exceeded = False
                self._completed = False
                self._finished = False

            def _notify_finish(self) -> None:
                if not self._finished:
                    self._finished = True
                    if self._on_finish is not None:
                        self._on_finish()

            async def __aiter__(self) -> AsyncIterator[bytes]:
                try:
                    async for chunk in self._stream:
                        if not self._exceeded:
                            if (
                                self._max_bytes is not None
                                and len(self._chunks) + len(chunk) > self._max_bytes
                            ):
                                self._exceeded = True
                                self._chunks.clear()
                            else:
                                self._chunks.extend(chunk)
                        yield chunk
                    if not self._completed and not self._exceeded:
                        self._completed = True
                        await self._on_complete(bytes(self._chunks))
                finally:
                    self._notify_finish()

            async def aclose(self) -> None:
                try:
                    if hasattr(self._stream, "aclose"):
                        await self._stream.aclose()
                finally:
                    self._notify_finish()

        object.__setattr__(self, "_sync_wrapper_cls", _SyncByteStreamWrapper)
        object.__setattr__(self, "_async_wrapper_cls", _AsyncByteStreamWrapper)

    def wrap_sync_stream(
        self,
        stream: Any,
        on_complete: Callable[[bytes], None],
        *,
        max_bytes: int | None = None,
        on_finish: Callable[[], None] | None = None,
    ) -> Any:
        """Wrap a backend SyncByteStream so ``on_complete`` runs only on full consumption."""
        return self._sync_wrapper_cls(
            stream,
            on_complete,
            max_bytes=max_bytes,
            on_finish=on_finish,
        )

    def wrap_async_stream(
        self,
        stream: Any,
        on_complete: Callable[[bytes], Awaitable[None]],
        *,
        max_bytes: int | None = None,
        on_finish: Callable[[], None] | None = None,
    ) -> Any:
        """Wrap a backend AsyncByteStream so ``on_complete`` runs only on full consumption."""
        return self._async_wrapper_cls(
            stream,
            on_complete,
            max_bytes=max_bytes,
            on_finish=on_finish,
        )

    @property
    def Client(self) -> type[Any]:
        return self.module.Client  # type: ignore[no-any-return]

    @property
    def AsyncClient(self) -> type[Any]:
        return self.module.AsyncClient  # type: ignore[no-any-return]

    @property
    def HTTPTransport(self) -> type[Any]:
        return self.module.HTTPTransport  # type: ignore[no-any-return]

    @property
    def AsyncHTTPTransport(self) -> type[Any]:
        return self.module.AsyncHTTPTransport  # type: ignore[no-any-return]

    @property
    def Request(self) -> type[Any]:
        return self.module.Request  # type: ignore[no-any-return]

    @property
    def Response(self) -> type[Any]:
        return self.module.Response  # type: ignore[no-any-return]

    @property
    def ByteStream(self) -> type[Any]:
        return self.module.ByteStream  # type: ignore[no-any-return]

    @property
    def Headers(self) -> type[Any]:
        return self.module.Headers  # type: ignore[no-any-return]

    @property
    def HTTPError(self) -> type[Exception]:
        return self.module.HTTPError  # type: ignore[no-any-return]

    def build_response(
        self,
        entry: CacheEntry,
        *,
        request: Any | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> Any:
        """Reconstruct a backend-native Response from a cached CacheEntry."""
        ext: dict[str, Any] = {"http_version": entry.http_version.encode("ascii")}
        if extensions:
            ext.update(extensions)

        is_raw_stream = bool(entry.metadata.get("raw_stream", False))
        if is_raw_stream:
            response = self.Response(
                status_code=entry.status_code,
                headers=list(entry.headers),
                stream=self.ByteStream(entry.body),
                extensions=ext,
            )
        else:
            response = self.Response(
                status_code=entry.status_code,
                headers=list(entry.headers),
                content=entry.body,
                extensions=ext,
            )

        if entry.encoding is not None:
            response.encoding = entry.encoding
        if request is not None:
            response.request = request
        return response

    def clone_request_with_headers(
        self,
        request: Any,
        extra_headers: dict[str, str],
    ) -> Any:
        """Return a shallow copy of request with additional headers merged in."""
        headers = self.Headers(request.headers.multi_items())
        for name, value in extra_headers.items():
            if name not in headers:
                headers[name] = value

        kwargs: dict[str, Any] = {
            "headers": headers,
            "extensions": dict(getattr(request, "extensions", {}) or {}),
        }
        if hasattr(request, "_content"):
            kwargs["content"] = request.content
        elif hasattr(request, "stream"):
            kwargs["stream"] = request.stream
        return self.Request(request.method, request.url, **kwargs)


_BACKEND_CACHE: dict[BackendName, Backend] = {}


def load_backend(name: BackendName) -> Backend:
    """Import and cache a specific HTTP client backend (``httpx`` or ``httpx2``)."""
    cached = _BACKEND_CACHE.get(name)
    if cached is not None:
        return cached
    try:
        mod = importlib.import_module(name)
    except ImportError as exc:
        raise ImportError(
            f"Backend {name!r} is not installed. "
            f"Install it with: pip install 'httpx-cache[{name}]'"
        ) from exc
    backend = Backend(name=name, module=mod)
    _BACKEND_CACHE[name] = backend
    return backend


def detect_backend_from_obj(obj: Any) -> Backend | None:
    """Detect whether an object (or any of its base classes) belongs to ``httpx`` or ``httpx2``."""
    if obj is None:
        return None
    for cls in type(obj).__mro__:
        root = cls.__module__.split(".", 1)[0]
        if root == "httpx2":
            return load_backend("httpx2")
        if root == "httpx":
            return load_backend("httpx")
    return None


def get_backend(name: BackendName | None = None) -> Backend:
    """Return the requested backend, or auto-select whichever of httpx / httpx2 is installed."""
    if name is not None:
        return load_backend(name)
    for candidate in ("httpx", "httpx2"):
        try:
            return load_backend(candidate)
        except ImportError:
            continue
    raise ImportError(
        "httpx-cache requires either 'httpx' or 'httpx2' to be installed. "
        "Install one with: pip install 'httpx-cache[httpx]' or pip install 'httpx-cache[httpx2]'"
    )
