import typing as tp
from abc import ABC, abstractmethod

import attr
import httpx

from httpx_cache.serializer import Serializer
from httpx_cache.serializer.base import BaseSerializer


@attr.s
class BaseCacheMixin:
    serializer: BaseSerializer = attr.ib(kw_only=True, factory=Serializer, repr=False)

    def _gen_key(self, request: httpx.Request) -> str:
        return str(request.url)


@attr.s
class BaseCache(ABC, BaseCacheMixin):
    @abstractmethod
    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        pass

    @abstractmethod
    def set(
        self, *, request: httpx.Request, response: httpx.Response, content: bytes
    ) -> None:
        pass

    @abstractmethod
    def delete(self, request: httpx.Request) -> None:
        pass

    def close(self) -> None:
        pass


@attr.s
class AsyncBaseCache(ABC, BaseCacheMixin):
    @abstractmethod
    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        pass

    @abstractmethod
    async def aset(
        self, *, request: httpx.Request, response: httpx.Response, content: bytes
    ) -> None:
        pass

    @abstractmethod
    async def adelete(self, request: httpx.Request) -> None:
        pass

    async def aclose(self) -> None:
        pass
