import httpx
import msgpack

from httpx_cache.serializer.base import BaseSerializer


class Serializer(BaseSerializer):
    def dumps(self, *, response: httpx.Response, content: bytes) -> bytes:
        """Dump an httpx.Response and it's content into bytes using msgpack.

        The content is the bytes content of httpx.Response.
        They are given as 2 separate arguments because most of the time the
        httpx.Response contains a stream that is not read/loaded.

        When used with an httpx.BaseTransport the content is generally provided via a
        callback, when the user as completly read the stream (we wrapp the response
        stream so that a callback is called when the stream is fully loaded).

        Usage:
            >>> # simplest usage.
            >>> respone = httpx.Response(200, ...)
            >>> data = Serializer().dumps(response=response, content=response.read())

        Args:
            response: instance of httpx.Response
            content: butes content of the httpx.Response

        Returns:
            Dumped representation of the httpx.Response
        """
        data = {
            "headers": response.headers.raw,
            "status_code": response.status_code,
            "encoding": response.encoding,
            "content": content,
        }
        return msgpack.dumps(data, use_bin_type=True)

    def loads(self, *, request: httpx.Request, data: bytes) -> httpx.Response:
        """Load an httpx.Response from provided data.

        Args:
            data (bytes): data previously dumped using this serializer
            request (httpx.Request): request to add to the generated
            response

        Returns:
            httpx.Response
        """
        resp_data = msgpack.loads(data, raw=False)
        status_code = resp_data.pop("status_code")
        encoding = resp_data.pop("encoding")
        content = resp_data.pop("content")
        stream = httpx.ByteStream(content)
        response = httpx.Response(
            status_code, stream=stream, request=request, **resp_data
        )
        if encoding is not None:
            response.encoding = encoding
        return response
