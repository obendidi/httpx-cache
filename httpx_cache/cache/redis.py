import threading
import typing as tp

import anyio
import httpx
from httpx_cache.cache.base import BaseCache
from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer
from httpx_cache.utils import get_cache_key
from redis import Redis
from redis.asyncio import Redis as AsyncRedis


class RedisCache(BaseCache):
    lock = threading.Lock()
    async_lock = anyio.Lock()

    def __init__(
        self, redis_url, serializer: tp.Optional[BaseSerializer] = None
    ) -> None:
        self._redis_url = redis_url
        self._redis: tp.Optional[Redis] = None
        self._aredis: tp.Optional[AsyncRedis] = None
        self.serializer = serializer or MsgPackSerializer()
        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Expected serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self._redis_url)
        return self._redis

    @property
    def aredis(self) -> AsyncRedis:
        if self._aredis is None:
            self._aredis = AsyncRedis.from_url(self._redis_url)
        return self._aredis

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = get_cache_key(request)
        cached = self._redis.get(key)
        if cached is not None:
            return self.serializer.loads(cached=cached, request=request)
        return None

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = get_cache_key(request)
        cached_data = await self._aredis.get(key)
        if cached_data is not None:
            return self.serializer.loads(cached=cached_data, request=request)
        return None

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
            self._redis.set(key, to_cache)

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
            await self._aredis.set(key, to_cache)

    def delete(self, request: httpx.Request) -> None:
        key = get_cache_key(request)
        with self.lock:
            self._redis.delete(key)

    async def adelete(self, request: httpx.Request) -> None:
        key = get_cache_key(request)
        async with self.async_lock:
            await self._aredis.delete(key)

    async def aclose(self):
        await self._aredis.close()
