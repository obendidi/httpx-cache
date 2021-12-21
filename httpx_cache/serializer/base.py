import typing as tp
from abc import ABC, abstractmethod

import httpx


class BaseSerializer(ABC):
    @abstractmethod
    def dumps(
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> tp.Any:
        """Abstract method for dumping an httpx.Response."""

    @abstractmethod
    def loads(
        self, *, cached: tp.Any, request: tp.Optional[httpx.Request] = None
    ) -> httpx.Response:
        """Abstract method for loading an httpx.Response."""
