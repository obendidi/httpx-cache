import threading
import typing as tp
from abc import ABC

import anyio
import httpx
from httpx_cache.cache.base import BaseCache
from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer
from httpx_cache.utils import get_cache_key
from redis import Redis
from redis.asyncio import Redis as AsyncRedis


class RedisCache(BaseCache, ABC):
    lock = threading.Lock()

    def __init__(
        self, serializer: tp.Optional[BaseSerializer] = None, **configs
    ) -> None:
        self.cache = Redis(**configs)
        self.serializer = serializer or MsgPackSerializer()

        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Expected serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )

    def _get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = get_cache_key(request)
        cached = self.cache.get(key)
        if cached is not None:
            return self.serializer.loads(cached=cached, request=request)
        return None

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        return self._get(request)

    def set(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        key = get_cache_key(request)
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock:
            self.cache.set(key, to_cache)

    def delete(self, request: httpx.Request) -> None:
        key = get_cache_key(request)
        with self.lock:
            self.cache.delete(key)


class AsyncRedisCache(BaseCache, ABC):
    async_lock = anyio.Lock()

    def __init__(
        self, serializer: tp.Optional[BaseSerializer] = None, **configs
    ) -> None:
        self.cache = AsyncRedis(**configs)
        self.serializer = serializer or MsgPackSerializer()

        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Expected serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )

    async def _get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = get_cache_key(request)
        cached_data = await self.cache.get(key)

        if cached_data is not None:
            return self.serializer.loads(cached=cached_data, request=request)
        return None

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        return await self._get(request)

    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        to_cache = self.serializer.dumps(response=response, content=content)
        key = get_cache_key(request)
        async with self.async_lock:
            await self.cache.set(key, to_cache)

    async def adelete(self, request: httpx.Request) -> None:
        key = get_cache_key(request)
        async with self.async_lock:
            await self.cache.delete(key)

    async def aclose(self):
        await self.cache.close()
