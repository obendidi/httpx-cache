import typing as tp
from pathlib import Path

import anyio
import fasteners
from aiorwlock import RWLock
import httpx

from httpx_cache.cache.base import BaseCache
from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer
from httpx_cache.utils import get_cache_filepath


class FileCache(BaseCache):
    """File cache that stores cached responses in files on disk.

    Uses a lock/async_lock to make sure each get/set/delete operation is safe.

    Args:
        cache_dir: Optional custom cache_dir where to store cache files, defaults to
            ~/.cache/httpx-cache
        serializer: Optional serializer for the data to cache, defaults to:
            httpx_cache.MsgPackSerializer
    """

    lock = fasteners.ReaderWriterLock()

    def __init__(
        self,
        cache_dir: tp.Union[None, str, Path] = None,
        serializer: tp.Optional[BaseSerializer] = None,
    ) -> None:
        self.serializer = serializer or MsgPackSerializer()
        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Excpected sel.serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )
        self._extra = str(type(self.serializer).__name__)

        if cache_dir is None:
            cache_dir = Path.home() / ".cache/httpx-cache"
        elif not isinstance(cache_dir, Path):
            assert isinstance(cache_dir, str)
            cache_dir = Path(cache_dir)

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)

    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        filepath = get_cache_filepath(self.cache_dir, request, extra=self._extra)
        if filepath.is_file():
            with self.lock.read_lock():
                cached = filepath.read_bytes()
            return self.serializer.loads(request=request, cached=cached)
        return None

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        filepath = anyio.Path(
            get_cache_filepath(self.cache_dir, request, extra=self._extra)
        )
        if await filepath.is_file():
            async with RWLock().reader:
                cached = await filepath.read_bytes()
            return self.serializer.loads(request=request, cached=cached)
        return None

    def set(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        filepath = get_cache_filepath(self.cache_dir, request, extra=self._extra)
        to_cache = self.serializer.dumps(response=response, content=content)
        with self.lock.write_lock():
            filepath.write_bytes(to_cache)

    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        filepath = anyio.Path(
            get_cache_filepath(self.cache_dir, request, extra=self._extra)
        )
        to_cache = self.serializer.dumps(response=response, content=content)
        async with RWLock().writer:
            await filepath.write_bytes(to_cache)

    def delete(self, request: httpx.Request) -> None:
        filepath = get_cache_filepath(self.cache_dir, request, extra=self._extra)
        if filepath.is_file():
            with self.lock.write_lock():
                filepath.unlink()

    async def adelete(self, request: httpx.Request) -> None:
        filepath = anyio.Path(
            get_cache_filepath(self.cache_dir, request, extra=self._extra)
        )
        async with RWLock().writer:
            await filepath.unlink(missing_ok=True)
