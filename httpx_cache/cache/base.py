import typing as tp
from abc import ABC, abstractmethod

import httpx


class BaseCache(ABC):
    @abstractmethod
    def get(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        """Get cached response from Cache.

        We use the httpx.Request.url as key.

        Args:
            request: httpx.Request

        Returns:
            tp.Optional[httpx.Response]
        """

    @abstractmethod
    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        """(Async) Get cached response from Cache.

        We use the httpx.Request.url as key.

        Args:
            request: httpx.Request

        Returns:
            tp.Optional[httpx.Response]
        """

    @abstractmethod
    def set(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        """Set new response entry in cache.

        In case the response does not yet have a '_content' property, content should
        be provided in the optional 'content' kwarg (usually using a callback)

        Args:
            request: httpx.Request
            response: httpx.Response, to cache
            content (bytes, optional): Defaults to None, should be provided in case
                response that not have yet content.
        """

    @abstractmethod
    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        """(Async) Set new response entry in cache.

        In case the response does not yet have a '_content' property, content should
        be provided in the optional 'content' kwarg (usually using a callback)

        Args:
            request: httpx.Request
            response: httpx.Response, to cache
            content (bytes, optional): Defaults to None, should be provided in case
                response that not have yet content.
        """

    @abstractmethod
    def delete(self, request: httpx.Request) -> None:
        """Delete an entry from cache.

        Args:
            request: httpx.Request
        """

    @abstractmethod
    async def adelete(self, request: httpx.Request) -> None:
        """(Async) Delete an entry from cache.

        Args:
            request: httpx.Request
        """

    def close(self) -> None:
        """Close cache."""

    async def aclose(self) -> None:
        """(Async) Close cache."""
