import hashlib
import os
import typing as tp

import anyio
import attr
import fasteners
import httpx

from httpx_cache.cache.base import AsyncBaseCache, BaseCache, gen_cache_key
from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer


def create_cache_dir(cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.abspath(cache_dir)


def cache_dir_factory() -> str:
    return os.path.join(os.path.expanduser("~"), ".cache/httpx-cache")


def gen_cache_filepath(cache_dir: str, request: httpx.Request) -> str:
    filename = gen_cache_key(request)
    return os.path.join(cache_dir, hashlib.sha224(filename.encode()).hexdigest())


@attr.s
class FileCache(BaseCache):
    lock = fasteners.ReaderWriterLock()
    serializer: BaseSerializer = attr.ib(
        kw_only=True,
        factory=MsgPackSerializer,
        repr=False,
        eq=False,
        order=False,
    )
    cache_dir: str = attr.ib(
        factory=cache_dir_factory, kw_only=True, converter=create_cache_dir
    )

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        filepath = gen_cache_filepath(self.cache_dir, request)
        if not os.path.isfile(filepath):
            return None
        with self.lock.read_lock():
            with open(filepath, "rb") as fh:
                cached = fh.read()
        return self.serializer.loads(request=request, data=cached)

    def set(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None
    ) -> None:
        filepath = gen_cache_filepath(self.cache_dir, request)
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock.write_lock():
            with open(filepath, "wb") as fh:
                fh.write(to_cache)

    def delete(self, request: httpx.Request) -> None:
        filepath = gen_cache_filepath(self.cache_dir, request)
        if os.path.isfile(filepath):
            with self.lock.write_lock():
                os.remove(filepath)


@attr.s
class AsyncFileCache(AsyncBaseCache):
    lock = anyio.Lock()
    serializer: BaseSerializer = attr.ib(
        kw_only=True,
        factory=MsgPackSerializer,
        repr=False,
        eq=False,
        order=False,
    )
    cache_dir: str = attr.ib(
        factory=cache_dir_factory, kw_only=True, converter=create_cache_dir
    )

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        filepath = anyio.Path(gen_cache_filepath(self.cache_dir, request))
        if not await filepath.is_file():
            return None
        async with self.lock:
            cached = await filepath.read_bytes()

        return self.serializer.loads(request=request, data=cached)

    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None
    ) -> None:
        filepath = anyio.Path(gen_cache_filepath(self.cache_dir, request))
        to_cache = self.serializer.dumps(response=response, content=content)
        async with self.lock:
            await filepath.write_bytes(to_cache)

    async def adelete(self, request: httpx.Request) -> None:
        filepath = anyio.Path(gen_cache_filepath(self.cache_dir, request))
        async with self.lock:
            await filepath.unlink(missing_ok=True)
