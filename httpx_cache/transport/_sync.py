import attr
import httpx
from httpx._utils import get_logger

from httpx_cache.cache import BaseCache, DictCache
from httpx_cache.transport.base import CacheControlTransportMixin
from httpx_cache.utils import ByteStreamWrapper

logger = get_logger(__name__)


@attr.s
class CacheControlTransport(httpx.BaseTransport, CacheControlTransportMixin):

    transport: httpx.BaseTransport = attr.ib(kw_only=True, factory=httpx.HTTPTransport)
    cache: BaseCache = attr.ib(kw_only=True, factory=DictCache)

    def close(self) -> None:
        self.cache.close()
        self.transport.close()

    def handle_request(self, request: httpx.Request) -> httpx.Response:

        # try to get response from cache
        if self.is_request_cacheable(request):
            logger.trace(f"Checking cache for request: {request}")
            cached_response = self.cache.get(request=request)
            if cached_response is not None:
                logger.trace(f"Found an entry in cache for: {request}")
                setattr(cached_response, "from_cache", True)
                return cached_response
            logger.trace(f"No entry found in cache for: {request}")

        # Request is not in cache, call original transport
        response = self.transport.handle_request(request)

        # if response is cacheable
        if self.is_response_cacheable(response) and self.is_request_cacheable(request):
            # if content already exists, save it
            if hasattr(response, "_content"):
                logger.trace(f"Saving response in cache for: {request}")
                self.cache.set(request=request, response=response)
            else:
                # Wrap the response with cache callback:
                def _callback(content: bytes) -> None:
                    logger.trace(f"Saving response in cache for: {request}")
                    self.cache.set(request=request, response=response, content=content)

                response.stream = ByteStreamWrapper(
                    stream=response.stream, callback=_callback  # type: ignore
                )
        setattr(response, "from_cache", False)
        return response
