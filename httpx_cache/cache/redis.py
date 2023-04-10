import typing as tp
from datetime import timedelta

import httpx
from aiorwlock import RWLock as AsyncRWLock
from fasteners import ReaderWriterLock as RWLock
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from httpx_cache.cache.base import BaseCache
from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer
from httpx_cache.utils import get_cache_key

__all__ = ["RedisCache"]


class RedisCache(BaseCache):
    """Redis cache that stores cached responses in Redis.

    Uses a lock/async_lock to make sure each get/set/delete operation is safe.

    You can either provide an instance of 'Redis'/'AsyncRedis' or a redis url to
    have RedisCache create the connection for you.

    Args:
        serializer: Optional serializer for the data to cache, defaults to:
            httpx_cache.MsgPackSerializer
        namespace: Optional namespace for the cache keys, defaults to "httpx_cache"
        redis_url: Optional redis url, defaults to empty string
        redis: Optional redis instance, defaults to None
        aredis: Optional async redis instance, defaults to None
        default_ttl: Optional default ttl for cached responses, defaults to None
    """

    lock = RWLock()

    def __init__(
        self,
        serializer: tp.Optional[BaseSerializer] = None,
        namespace: str = "httpx_cache",
        redis_url: str = "",
        redis: tp.Optional["Redis[bytes]"] = None,
        aredis: tp.Optional["AsyncRedis[bytes]"] = None,
        default_ttl: tp.Optional[timedelta] = None,
    ) -> None:
        self.namespace = namespace
        # redis connection is lazy loaded
        self.redis = redis or Redis.from_url(redis_url)
        self.aredis = aredis or AsyncRedis.from_url(redis_url)
        self.serializer = serializer or MsgPackSerializer()
        self.default_ttl = default_ttl
        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Expected serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )

        self._async_lock: tp.Optional[AsyncRWLock] = None

    @property
    def async_lock(self) -> AsyncRWLock:
        if self._async_lock is None:
            self._async_lock = AsyncRWLock()
        return self._async_lock

    def _get_namespaced_cache_key(self, request: httpx.Request) -> str:
        key = get_cache_key(request)
        if self.namespace:
            key = f"{self.namespace}:{key}"
        return key

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = self._get_namespaced_cache_key(request)
        with self.lock.read_lock():
            cached = self.redis.get(key)
        if cached is not None:
            return self.serializer.loads(cached=cached, request=request)
        return None

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = self._get_namespaced_cache_key(request)
        async with self.async_lock.reader:
            cached_data = await self.aredis.get(key)
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
        key = self._get_namespaced_cache_key(request)
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock.write_lock():
            if self.default_ttl:
                self.redis.setex(key, self.default_ttl, to_cache)
            else:
                self.redis.set(key, to_cache)

    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        to_cache = self.serializer.dumps(response=response, content=content)
        key = self._get_namespaced_cache_key(request)
        async with self.async_lock.writer:
            if self.default_ttl:
                await self.aredis.setex(key, self.default_ttl, to_cache)
            else:
                await self.aredis.set(key, to_cache)

    def delete(self, request: httpx.Request) -> None:
        key = self._get_namespaced_cache_key(request)
        with self.lock.write_lock():
            self.redis.delete(key)

    async def adelete(self, request: httpx.Request) -> None:
        key = self._get_namespaced_cache_key(request)
        async with self.async_lock.writer:
            await self.aredis.delete(key)

    def close(self) -> None:
        self.redis.close()

    async def aclose(self) -> None:
        await self.aredis.close()
