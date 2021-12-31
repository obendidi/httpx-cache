import hashlib
import logging
import typing as tp
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import attr
import httpx

logger = logging.getLogger(__name__)


def get_cache_key(request: httpx.Request) -> str:
    """Get the cache key from a request.

    The cache key is the str request url.

    Args:
        request: httpx.Request

    Returns:
        str: httpx.Request.url
    """
    return str(request.url)


def get_cache_filepath(
    cache_dir: Path, request: httpx.Request, extra: str = ""
) -> Path:
    """Get the cache filepath from a request.

    Args:
        cache_dir: pathlib.Path, path to the cache_dir
        request: httpx.Request
        extra: an extra string to add to filename before encoding it.

    Returns:
        pathlib.Path of the cache filepath
    """
    buffer = (get_cache_key(request) + extra).encode()
    filename = hashlib.sha224(buffer).hexdigest()
    return cache_dir / filename


def parse_headers_date(headers_date: tp.Optional[str]) -> tp.Optional[datetime]:
    """Parse a 'Date' header and return it as an optional datetime object.

    If the 'Date' doe not exist return None
    IF there is an error usirng parsing return None

    Args:
        headers: httpx.Headers

    Returns:
        Optional[datetime]
    """
    if not isinstance(headers_date, str):
        return None

    try:
        return parsedate_to_datetime(headers_date)
    except (ValueError, TypeError) as error:
        logger.error(error)
        return None


def parse_cache_control_headers(
    headers: httpx.Headers,
) -> tp.Dict[str, tp.Optional[int]]:
    """Parse cache-control headers.

    Args:
        headers: An instance of httpx headers.

    Returns:
        parsed cache-control headers as dict.
    """

    cache_control: tp.Dict[str, tp.Optional[int]] = {}
    directives = headers.get_list("cache-control", split_commas=True)
    for directive in directives:
        if "=" in directive:
            name, value = directive.split("=", maxsplit=1)
            if value.isdigit():
                cache_control[name] = int(value)
            else:
                cache_control[name] = None
        else:
            cache_control[directive] = None
    return cache_control


@attr.s
class ByteStreamWrapper(httpx.ByteStream):
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
