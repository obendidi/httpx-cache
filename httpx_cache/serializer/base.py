import typing as tp
from abc import ABC, abstractmethod

import httpx


class BaseSerializer(ABC):
    def dumps(
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> tp.Any:
        """Dumps amd httpx Response and serialize it to be stored in cache.

        The content is provided separatly because in most cases, the response contains
        a stream that completly read before caching.

        When used with an httpx.BaseTransport the content is generally provided via a
        callback, when the user as completly read the stream (we wrapp the response
        stream so that a callback is called when the stream is fully loaded).

        Usage:
            >>> # simplest usage.
            >>> resp = httpx.Response(200, ...)
            >>> data = Serializer().dumps(response=resp, content=resp.read())

        Args:
            response: httpx.Response
            content: optional content in bytes of the httpx.Response

        Returns:
            dumped and serialized response.
        """
        state = response.__getstate__()
        if "_content" not in state:
            if content is None:
                raise httpx.ResponseNotRead()
            state["stream_content"] = content
            # remove info related to content if present
            # will be populated automatically by httpx
            state.pop("is_stream_consumed", None)
            state.pop("_num_bytes_downloaded", None)

        # remove request if in state
        state.pop("_request", None)

        # get state of headers
        headers = state.get("headers")
        assert isinstance(headers, httpx.Headers)
        state["headers"] = state["headers"].raw
        return self.serialize(state)

    def loads(
        self, *, data: tp.Any, request: tp.Optional[httpx.Request] = None
    ) -> httpx.Response:
        """Deserialize and loads an httpx.Response from serialized data.

        Data will first be deserialized before creating a new httpx.Response object.

        The bytes content will be wrapped in an httpx.ByteStream.

        Args:
            data: dumped data to load

        Returns:
            httpx.Response
        """
        state = self.deserialize(data)
        status_code = state.pop("status_code")
        headers = state.pop("headers", None)
        stream_content = state.pop("stream_content", None)
        if isinstance(stream_content, str):
            stream_content = stream_content.encode("utf-8")
        stream = None if stream_content is None else httpx.ByteStream(stream_content)
        if isinstance(state.get("_content"), str):
            state["_content"] = state["_content"].encode("utf-8")

        response = httpx.Response(status_code, stream=stream, headers=headers)
        for name, value in state.items():
            setattr(response, name, value)

        if request is not None:
            response.request = request
        return response

    @abstractmethod
    def serialize(self, data: tp.Dict[str, tp.Any]) -> tp.Any:
        """Serialize a data dict to another (usually more compact) format.

        Args:
            data: Data to serialize as a dict of 'str: Any' items.

        Returns:
            Serialized data dict.
        """

    @abstractmethod
    def deserialize(self, data: tp.Any) -> tp.Dict[str, tp.Any]:
        """Deserialize the input data.

        The data can be anything, but it should always be the direct output of
        self.serialize function

        Args:
            data: data to deserialize

        Returns:
            Deserialized dict data
        """


class NullSerializer(BaseSerializer):
    def dumps(
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> httpx.Response:
        return response

    def loads(
        self, *, data: httpx.Response, request: tp.Optional[httpx.Request] = None
    ) -> httpx.Response:
        return data

    def serialize(self, data: tp.Dict[str, tp.Any]) -> tp.Dict[str, tp.Any]:
        """Do Nothing."""

    def deserialize(self, data: tp.Dict[str, tp.Any]) -> tp.Dict[str, tp.Any]:
        """Do Nothing."""
