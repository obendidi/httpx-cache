import threading
import typing as tp

import anyio
import attr
import httpx

from httpx_cache.cache.base import AsyncBaseCache, BaseCache


@attr.s
class DictCache(BaseCache):
    lock: threading.Lock = attr.ib(
        init=False, factory=threading.Lock, repr=False, eq=False, order=False
    )
    data: tp.Dict[str, bytes] = attr.ib(
        kw_only=True, factory=dict, validator=attr.validators.instance_of(dict)
    )

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = self._gen_key(request)
        cached = self.data.get(key)
        if cached is not None:
            return self.serializer.loads(request=request, data=cached)
        return None

    def set(
        self, *, request: httpx.Request, response: httpx.Response, content: bytes
    ) -> None:
        key = self._gen_key(request)
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock:
            self.data.update({key: to_cache})

    def delete(self, request: httpx.Request) -> None:
        key = self._gen_key(request)
        with self.lock:
            self.data.pop(key, None)


@attr.s
class AsyncDictCache(AsyncBaseCache):
    lock: anyio.Lock = attr.ib(
        init=False, factory=anyio.Lock, repr=False, eq=False, order=False
    )
    data: tp.Dict[str, bytes] = attr.ib(
        kw_only=True, factory=dict, validator=attr.validators.instance_of(dict)
    )

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = self._gen_key(request)
        cached = self.data.get(key)
        if cached is not None:
            return self.serializer.loads(request=request, data=cached)
        return None

    async def aset(
        self, *, request: httpx.Request, response: httpx.Response, content: bytes
    ) -> None:
        key = self._gen_key(request)
        to_cache = self.serializer.dumps(response=response, content=content)
        async with self.lock:
            self.data.update({key: to_cache})

    async def adelete(self, request: httpx.Request) -> None:
        key = self._gen_key(request)
        async with self.lock:
            self.data.pop(key, None)
