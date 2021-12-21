import uuid

import httpx
import mock
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio


def _handler(request: httpx.Request) -> httpx.Response:
    key = str(request.url).lstrip("http://")
    return httpx.Response(200, content=key.encode("utf-8"))


async def test_async_cache_control_transport_handle_request_with_cache():

    key = str(uuid.uuid4())
    url = f"http://{key}"
    request = httpx.Request("GET", url)

    transport = httpx_cache.AsyncCacheControlTransport(
        cache=httpx_cache.AsyncDictCache(serializer=httpx_cache.NullSerializer()),
        transport=httpx.MockTransport(_handler),
    )

    # first request is not from cache
    first_response = await transport.handle_async_request(request)
    assert getattr(first_response, "from_cache") is False

    # second same request should be from cache
    second_response = await transport.handle_async_request(request)
    assert getattr(second_response, "from_cache") is True
    assert first_response.content == second_response.content == key.encode("utf-8")
    await transport.aclose()


@mock.patch.object(
    httpx_cache.AsyncCacheControlTransport, "is_request_cacheable", return_value=False
)
async def test_async_cache_control_transport_handle_request_with_request_not_cacheable(
    mock_is_request_cacheable: mock.MagicMock,
):

    key = str(uuid.uuid4())
    url = f"http://{key}"
    request = httpx.Request("GET", url)

    transport = httpx_cache.AsyncCacheControlTransport(
        transport=httpx.MockTransport(_handler), cache=httpx_cache.AsyncDictCache()
    )

    # first request is not from cache
    first_response = await transport.handle_async_request(request)
    assert getattr(first_response, "from_cache") is False

    # second same request is still not from cache
    second_response = await transport.handle_async_request(request)
    assert getattr(second_response, "from_cache") is False
    await transport.aclose()


@mock.patch.object(
    httpx_cache.AsyncCacheControlTransport, "is_response_cacheable", return_value=False
)
async def test_async_cache_control_transport_handle_request_with_response_not_cacheable(
    mock_is_response_cacheable: mock.MagicMock,
):

    key = str(uuid.uuid4())
    url = f"http://{key}"
    request = httpx.Request("GET", url)

    transport = httpx_cache.AsyncCacheControlTransport(
        transport=httpx.MockTransport(_handler), cache=httpx_cache.AsyncDictCache()
    )

    # first request is not from cache
    first_response = await transport.handle_async_request(request)
    assert getattr(first_response, "from_cache") is False

    # second same request is still not from cache
    second_response = await transport.handle_async_request(request)
    assert getattr(second_response, "from_cache") is False
    await transport.aclose()
