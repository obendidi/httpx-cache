import typing as tp

import attr
import httpx


@attr.s
class ResponseStreamWrapper(httpx.ByteStream):
    """Wrapper around the stream object of an httpx.Response."""

    stream: httpx.ByteStream = attr.ib(kw_only=True)
    callback: tp.Callable[[bytes], tp.Any] = attr.ib(kw_only=True)
    content: bytearray = attr.ib(factory=bytearray, init=False)

    def close(self) -> None:
        """Close stream."""
        self.stream.close()

    async def aclose(self) -> None:
        """Close async stream."""
        await self.stream.aclose()

    def __iter__(self) -> tp.Iterator[bytes]:
        """Iterate over the stream object and store it's chunks in a content.

        After the stream is completed call the callback with content as argument.
        """
        for chunk in self.stream:
            self.content.extend(chunk)
            yield chunk
        self.callback(bytes(self.content))

    async def __aiter__(self) -> tp.AsyncIterator[bytes]:
        """Iterate over the async stream object and store it's chunks in a content.

        After the stream is completed call the async callback with content as argument.
        """
        async for chunk in self.stream:
            self.content.extend(chunk)
            yield chunk
        await self.callback(bytes(self.content))
