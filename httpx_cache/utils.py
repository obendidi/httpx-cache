import hashlib
import typing as tp
from pathlib import Path

import attr
import httpx
from httpx._utils import get_logger

logger = get_logger(__name__)

# https://tools.ietf.org/html/rfc7234#section-5.2
KNOWN_DIRECTIVES = {
    "max-age": (int, True),
    "max-stale": (int, False),
    "min-fresh": (int, True),
    "no-cache": (None, False),
    "no-store": (None, False),
    "no-transform": (None, False),
    "only-if-cached": (None, False),
    "must-revalidate": (None, False),
    "public": (None, False),
    "private": (None, False),
    "proxy-revalidate": (None, False),
    "s-maxage": (int, True),
}


def get_cache_key(request: httpx.Request) -> str:
    """Get the cache key from a request.

    The cache key is the str request url.

    Args:
        request: httpx.Request

    Returns:
        str: httpx.Request.url
    """
    return str(request.url)


def get_cache_filepath(cache_dir: Path, request: httpx.Request) -> Path:
    """Get the cache filepath from a request.

    Args:
        cache_dir: pathlib.Path, path to the cache_dir
        request: httpx.Request

    Returns:
        pathlib.Path of the cache filepath
    """
    filename = hashlib.sha224(get_cache_key(request).encode()).hexdigest()
    return cache_dir / filename


def parse_cache_control_headers(
    headers: httpx.Headers,
) -> tp.Dict[str, tp.Optional[int]]:
    """Parse cache-control headers.

    Args:
        headers: An instance of httpx headers.

    Returns:
        parsed cache-control headers as dict.
    """

    parsed_cc: tp.Dict[str, tp.Any] = {}
    directives = headers.get_list("cache-control", split_commas=True)
    for directive in directives:
        name, value = directive.split("=", 1) if "=" in directive else (directive, None)
        if name not in KNOWN_DIRECTIVES:
            logger.debug(f"Unknown cache-control directive: {name}")
            continue
        value_type, required = KNOWN_DIRECTIVES[name]
        if value_type is None or not required:
            parsed_cc[name] = None
        elif value_type is not None:
            if value is not None:
                try:
                    parsed_cc[name] = value_type(value)
                except ValueError:
                    logger.debug(
                        f"Invalid value for cache-control directive: {name}."
                        f"Expected {value_type}, got {value} ({type(value)})"
                    )
            elif value is None and required:
                logger.debug(f"Missing value for cache-control directive: {name}")
    return parsed_cc


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
