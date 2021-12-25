import logging
import typing as tp

import httpx

from httpx_cache.cache import BaseCache, DictCache
from httpx_cache.cache_control import CacheControl
from httpx_cache.utils import ByteStreamWrapper

logger = logging.getLogger(__name__)


class CacheControlTransport(httpx.BaseTransport, httpx.AsyncBaseTransport):
    def __init__(
        self,
        *,
        transport: tp.Union[None, httpx.BaseTransport, httpx.AsyncBaseTransport] = None,
        cache: tp.Optional[BaseCache] = None,
        cacheable_methods: tp.Tuple[str, ...] = ("GET",),
        cacheable_status_codes: tp.Tuple[int, ...] = (200, 203, 300, 301, 308),
    ):
        self.controller = CacheControl(
            cacheable_methods=cacheable_methods,
            cacheable_status_codes=cacheable_status_codes,
        )
        self.transport = transport or httpx.HTTPTransport()
        self.cache = cache or DictCache()

    def close(self):
        self.cache.close()
        self.transport.close()

    async def aclose(self):
        await self.cache.aclose()
        await self.transport.aclose()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        # check if request is cacheable
        if self.controller.is_request_cacheable(request):
            logger.debug(f"Checking cache for: {request}")
            cached_response = self.cache.get(request)
            if cached_response is not None:
                logger.debug(f"Found cached response for: {request}")
                if self.controller.is_response_fresh(
                    request=request, response=cached_response
                ):
                    setattr(cached_response, "from_cache", True)
                    return cached_response
                else:
                    logger.debug(f"Cached response is stale, deleting: {request}")
                    self.cache.delete(request)
            logger.debug("No valid cached response found in cache...")

        # Request is not in cache, call original transport
        assert isinstance(self.transport, httpx.BaseTransport)
        response = self.transport.handle_request(request)

        if self.controller.is_response_cacheable(request=request, response=response):
            if hasattr(response, "_content"):
                logger.debug(f"Caching response for: {request}")
                self.cache.set(request=request, response=response)
            else:
                # Wrap the response with cache callback:
                def _callback(content: bytes) -> None:
                    logger.debug(f"Caching response for: {request}")
                    self.cache.set(request=request, response=response, content=content)

                response.stream = ByteStreamWrapper(
                    stream=response.stream, callback=_callback  # type: ignore
                )
        setattr(response, "from_cache", False)
        return response

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # check if request is cacheable
        if self.controller.is_request_cacheable(request):
            logger.debug(f"Checking cache for: {request}")
            cached_response = await self.cache.aget(request)
            if cached_response is not None:
                logger.debug(f"Found cached response for: {request}")
                if self.controller.is_response_fresh(
                    request=request, response=cached_response
                ):
                    setattr(cached_response, "from_cache", True)
                    return cached_response
                else:
                    logger.debug(f"Cached response is stale, deleting: {request}")
                    await self.cache.adelete(request)

        # Request is not in cache, call original transport
        assert isinstance(self.transport, httpx.AsyncBaseTransport)
        response = await self.transport.handle_async_request(request)

        if self.controller.is_response_cacheable(request=request, response=response):
            if hasattr(response, "_content"):
                logger.debug(f"Caching response for: {request}")
                await self.cache.aset(request=request, response=response)
            else:
                # Wrap the response with cache callback:
                async def _callback(content: bytes) -> None:
                    logger.debug(f"Caching response for: {request}")
                    await self.cache.aset(
                        request=request, response=response, content=content
                    )

                response.stream = ByteStreamWrapper(
                    stream=response.stream, callback=_callback  # type: ignore
                )
        setattr(response, "from_cache", False)
        return response


class AsyncCacheControlTransport(CacheControlTransport):
    def __init__(
        self,
        *,
        transport: tp.Optional[httpx.AsyncBaseTransport] = None,
        cache: tp.Optional[BaseCache] = None,
        cacheable_methods: tp.Tuple[str, ...] = ("GET",),
        cacheable_status_codes: tp.Tuple[int, ...] = (200, 203, 300, 301, 308),
    ):
        transport = transport or httpx.AsyncHTTPTransport()
        super().__init__(
            transport=transport,
            cache=cache,
            cacheable_methods=cacheable_methods,
            cacheable_status_codes=cacheable_status_codes,
        )
