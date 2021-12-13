import hashlib
import os
import typing as tp

import anyio
import attr
import fasteners
import httpx

from httpx_cache.cache.base import AsyncBaseCache, BaseCache, BaseCacheMixin


def _create_cache_dir(cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.abspath(cache_dir)


def _cache_dir_factory() -> str:
    return os.path.join(os.path.expanduser("~"), ".cache/httpx-cache")


@attr.s
class FileCacheMixin(BaseCacheMixin):
    cache_dir: str = attr.ib(
        factory=_cache_dir_factory, kw_only=True, converter=_create_cache_dir
    )

    def get_cache_filepath(self, request: httpx.Request) -> str:
        filename = self._gen_key(request)
        return os.path.join(
            self.cache_dir, hashlib.sha224(filename.encode()).hexdigest()
        )


@attr.s
class FileCache(BaseCache, FileCacheMixin):
    lock: fasteners.ReaderWriterLock = attr.ib(
        init=False,
        factory=fasteners.ReaderWriterLock,
        repr=False,
        eq=False,
        order=False,
    )

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        filepath = self.get_cache_filepath(request)
        if not os.path.isfile(filepath):
            return None
        with self.lock.read_lock():
            with open(filepath, "rb") as fh:
                cached = fh.read()

        if not cached:
            return None

        return self.serializer.loads(request=request, data=cached)

    def set(
        self, *, request: httpx.Request, response: httpx.Response, content: bytes
    ) -> None:
        filepath = self.get_cache_filepath(request)
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock.write_lock():
            with open(filepath, "wb") as fh:
                fh.write(to_cache)

    def delete(self, request: httpx.Request) -> None:
        filepath = self.get_cache_filepath(request)
        if os.path.isfile(filepath):
            with self.lock.write_lock():
                os.remove(filepath)


@attr.s
class AsyncFileCache(AsyncBaseCache, FileCacheMixin):
    lock: anyio.Lock = attr.ib(
        init=False,
        factory=anyio.Lock,
        repr=False,
        eq=False,
        order=False,
    )

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        filepath = anyio.Path(self.get_cache_filepath(request))
        if not await filepath.is_file():
            return None
        async with self.lock:
            cached = await filepath.read_bytes()

        if not cached:
            return None

        return self.serializer.loads(request=request, data=cached)

    async def aset(
        self, *, request: httpx.Request, response: httpx.Response, content: bytes
    ) -> None:
        filepath = anyio.Path(self.get_cache_filepath(request))
        to_cache = self.serializer.dumps(response=response, content=content)
        async with self.lock:
            await filepath.write_bytes(to_cache)

    async def adelete(self, request: httpx.Request) -> None:
        filepath = anyio.Path(self.get_cache_filepath(request))
        async with self.lock:
            await filepath.unlink(missing_ok=True)
