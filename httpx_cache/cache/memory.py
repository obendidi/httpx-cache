import threading
import typing as tp

import anyio
import httpx

from httpx_cache.cache.base import BaseCache
from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer
from httpx_cache.utils import get_cache_key


class DictCache(BaseCache):
    """Simple in-memory dict cache.

    Uses a lock/async_lock to make sure each get/set/delete operation is safe.

    Args:
        data: Optional initial data for the cache {str: Any}, default to {}
        serializer: Optional serializer for the data to cache, defaults to:
            httpx_cache.MsgPackSerializer
    """

    lock = threading.Lock()
    async_lock = anyio.Lock()

    def __init__(
        self,
        data: tp.Optional[tp.Dict[str, tp.Any]] = None,
        serializer: tp.Optional[BaseSerializer] = None,
    ) -> None:
        self.data: tp.Dict[str, tp.Any] = data or {}
        self.serializer = serializer or MsgPackSerializer()

        if not isinstance(self.data, dict):
            raise TypeError(f"Excpected data of type 'dict', got {type(self.data)}")
        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Excpected serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )

    def _get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = get_cache_key(request)
        cached = self.data.get(key)
        if cached is not None:
            return self.serializer.loads(cached=cached, request=request)
        return None

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        return self._get(request)

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        return self._get(request)

    def set(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock:
            self.data.update({get_cache_key(request): to_cache})

    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        to_cache = self.serializer.dumps(response=response, content=content)
        async with self.async_lock:
            self.data.update({get_cache_key(request): to_cache})

    def delete(self, request: httpx.Request) -> None:
        key = get_cache_key(request)
        with self.lock:
            self.data.pop(key, None)

    async def adelete(self, request: httpx.Request) -> None:
        key = get_cache_key(request)
        async with self.async_lock:
            self.data.pop(key, None)
