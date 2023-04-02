import json
import typing as tp

import httpx
import msgpack

from httpx_cache.serializer.base import BaseSerializer


class DictSerializer(BaseSerializer):
    """Dumps and loads and httpx.Response into/from a python dict.

    The dict contains the state of the response, with all necessary info to recreate it.
    """

    def dumps(
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> tp.Dict[str, tp.Any]:
        """Converts and httpx.Response into a dict with it's state.

        The goal is that this state we are able later to reconstruct the same
        response later on.

        In case the response does not yet have a '_content' property, content should
        be provided in the optional 'content' kwarg (usually using a callback)

        Args:
            response: httpx.Response
            content (bytes, optional): Defaults to None, should be provided in case
                response that not have yet content.

        Raises:
            httpx.ResponseNotRead: if response does not have content and no content
                is provided

        Returns:
            Dict[str, Any]
        """
        state: tp.Dict[str, tp.Any] = {}

        # set status_code
        state["status_code"] = response.status_code

        # get content or stream_content
        if hasattr(response, "_content"):
            state["_content"] = response.content
        elif content is None:
            raise httpx.ResponseNotRead()
        else:
            state["stream_content"] = content

        # get headers
        state["headers"] = response.headers.multi_items()

        # get encoding
        if response.encoding:
            state["encoding"] = response.encoding
        return state

    def loads(
        self,
        *,
        cached: tp.Dict[str, tp.Any],
        request: tp.Optional[httpx.Request] = None,
    ) -> httpx.Response:
        """Convert a dict (contains response state) to an httpx.Response instance.

        Args:
            state: Dict of the state of teh response to create
            request (httpx.Request, optional): Defaults to None, request to optionally
                attach to the response

        Returns:
            httpx.Response
        """
        status_code = cached["status_code"]
        headers = cached["headers"]
        content = cached.get("_content")
        stream_content = cached.get("stream_content")
        encoding = cached.get("encoding")

        stream = None if stream_content is None else httpx.ByteStream(stream_content)
        response = httpx.Response(
            status_code, stream=stream, headers=headers, content=content
        )
        if encoding is not None:
            response.encoding = encoding

        if request is not None:
            response.request = request
        return response


class StringJsonSerializer(DictSerializer):
    """Serialize an httpx.Response using python Json Encoder.

    Serialized data is returned as a JSON string.

    The serialized data contains the state of the response, with all necessary
    info to recreate it.

    NB: bytes are automatically parsed as strings when using this serializer, when
    recreating response the loader is smart enough to know which key/value need to
    be bytes and not strings (like: _content/stream)
    """

    def dumps(  # type: ignore
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> str:
        """Dump an httpx.Response to json string."""
        state = super().dumps(response=response, content=content)
        encoding = state.get("encoding", "utf-8")
        if isinstance(state.get("_content"), bytes):
            state["_content"] = state["_content"].decode(encoding)
        if isinstance(state.get("stream_content"), bytes):
            state["stream_content"] = state["stream_content"].decode(encoding)

        return json.dumps(state)

    def loads(  # type: ignore
        self, *, cached: str, request: tp.Optional[httpx.Request] = None
    ) -> httpx.Response:
        """Load an httpx.Response from a json string"""
        state = json.loads(cached)
        encoding = state.get("encoding", "utf-8")
        if isinstance(state.get("_content"), str):
            state["_content"] = state["_content"].encode(encoding)
        if isinstance(state.get("stream_content"), str):
            state["stream_content"] = state["stream_content"].encode(encoding)
        return super().loads(cached=state, request=request)


class BytesJsonSerializer(StringJsonSerializer):
    """Same as httpx_cache.StringJsonSerializer, but converts the dumped strings
    into bytes (encoded/decode with utf-8).
    """

    def dumps(  # type: ignore
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> bytes:
        """Dump an httpx.Response to an utf-8 encoded bytes string."""
        return super().dumps(response=response, content=content).encode("utf-8")

    def loads(  # type: ignore
        self, *, cached: bytes, request: tp.Optional[httpx.Request] = None
    ) -> httpx.Response:
        """Load an httpx.Response to an utf-8 encoded bytes string."""
        return super().loads(cached=cached.decode("utf-8"), request=request)


class MsgPackSerializer(DictSerializer):
    """Serialize an httpx.Response using msgpack.

    Serialized data is returned as a bytes.

    The serialized data contains the state of the response, with all necessary
    info to recreate it.
    """

    def dumps(  # type: ignore
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> bytes:
        """Dump an httpx.Response to msgapck bytes."""
        return msgpack.dumps(
            super().dumps(response=response, content=content), use_bin_type=True
        )

    def loads(  # type: ignore
        self, *, cached: bytes, request: tp.Optional[httpx.Request] = None
    ) -> httpx.Response:
        """Load an httpx.Response from a msgapck bytes."""
        return super().loads(cached=msgpack.loads(cached, raw=False), request=request)
