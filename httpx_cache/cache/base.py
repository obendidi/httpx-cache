import typing as tp
from abc import ABC, abstractmethod

import httpx


def gen_cache_key(request: httpx.Request) -> str:
    return str(request.url)


class BaseCache(ABC):
    @abstractmethod
    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        """Get response from cache if available else None."""

    @abstractmethod
    def set(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None
    ) -> None:
        """Set a response in cache."""

    @abstractmethod
    def delete(self, request: httpx.Request) -> None:
        """Delete a Respnse form cache."""

    def close(self) -> None:
        """Close cache."""


class AsyncBaseCache(ABC):
    @abstractmethod
    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        """Get response from cache if available else None."""

    @abstractmethod
    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None
    ) -> None:
        """Set a response in cache."""

    @abstractmethod
    async def adelete(self, request: httpx.Request) -> None:
        """Delete a Respnse form cache."""

    async def aclose(self) -> None:
        """Close cache."""
