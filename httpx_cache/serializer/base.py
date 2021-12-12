import typing as tp
from abc import ABC, abstractmethod

import httpx


class BaseSerializer(ABC):
    @abstractmethod
    def dumps(self, *, response: httpx.Response, content: bytes) -> tp.Any:
        pass

    @abstractmethod
    def loads(self, *, request: httpx.Request, data: tp.Any) -> httpx.Response:
        pass
