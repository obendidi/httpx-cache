import threading
import typing as tp

import anyio
import attr
import httpx

from httpx_cache.cache.base import AsyncBaseCache, BaseCache, gen_cache_key
from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer


@attr.s
class DictCache(BaseCache):
    lock = threading.Lock()
    data: tp.Dict[str, tp.Any] = attr.ib(
        kw_only=True, factory=dict, validator=attr.validators.instance_of(dict)
    )
    serializer: BaseSerializer = attr.ib(
        kw_only=True, factory=MsgPackSerializer, repr=False
    )

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = gen_cache_key(request)
        cached = self.data.get(key)
        if cached is not None:
            return self.serializer.loads(data=cached, request=request)
        return None

    def set(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None
    ) -> None:
        key = gen_cache_key(request)
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock:
            self.data.update({key: to_cache})

    def delete(self, request: httpx.Request) -> None:
        key = gen_cache_key(request)
        with self.lock:
            self.data.pop(key, None)


@attr.s
class AsyncDictCache(AsyncBaseCache):
    lock = anyio.Lock()
    data: tp.Dict[str, tp.Any] = attr.ib(
        kw_only=True, factory=dict, validator=attr.validators.instance_of(dict)
    )
    serializer: BaseSerializer = attr.ib(
        kw_only=True, factory=MsgPackSerializer, repr=False
    )

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = gen_cache_key(request)
        cached = self.data.get(key)
        if cached is not None:
            return self.serializer.loads(data=cached)
        return None

    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None
    ) -> None:
        key = gen_cache_key(request)
        to_cache = self.serializer.dumps(response=response, content=content)
        async with self.lock:
            self.data.update({key: to_cache})

    async def adelete(self, request: httpx.Request) -> None:
        key = gen_cache_key(request)
        async with self.lock:
            self.data.pop(key, None)
