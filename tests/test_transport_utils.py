import uuid

import pytest

from httpx_cache.transport.utils import ResponseStreamWrapper

# This is the same as using the @pytest.mark.anyio on all test functions in the module
pytestmark = pytest.mark.anyio


def test_response_stream_wrapper(httpx_stream_response):

    store = {}
    key = str(uuid.uuid4())

    def _callback(buffer: bytes) -> None:
        assert isinstance(buffer, bytes)
        store[key] = buffer

    httpx_stream_response.stream = ResponseStreamWrapper(
        stream=httpx_stream_response.stream, callback=_callback
    )
    content = httpx_stream_response.read()
    assert content == store[key]


async def test_response_async_stream_wrapper(httpx_async_stream_response):

    store = {}
    key = str(uuid.uuid4())

    async def _callback(buffer: bytes) -> None:
        assert isinstance(buffer, bytes)
        store[key] = buffer

    httpx_async_stream_response.stream = ResponseStreamWrapper(
        stream=httpx_async_stream_response.stream, callback=_callback
    )
    content = await httpx_async_stream_response.aread()
    assert content == store[key]
