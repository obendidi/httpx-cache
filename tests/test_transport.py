import uuid

import httpx
import mock
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio


def random_response_handler(request: httpx.Request) -> httpx.Response:
    content = f"{request.url}-{uuid.uuid4()}"
    return httpx.Response(200, content=content.encode())


def stream_response_handler(request: httpx.Request) -> httpx.Response:
    content = f"{request.url}-{uuid.uuid4()}"
    stream = httpx.ByteStream(content.encode())
    return httpx.Response(200, stream=stream)


def test_cache_control_transport_init_defaults():
    transport = httpx_cache.CacheControlTransport()
    async_transport = httpx_cache.AsyncCacheControlTransport()

    assert isinstance(async_transport.transport, httpx.AsyncHTTPTransport)
    assert isinstance(async_transport.cache, httpx_cache.DictCache)
    assert isinstance(transport.transport, httpx.HTTPTransport)
    assert isinstance(transport.cache, httpx_cache.DictCache)
    assert (
        transport.controller.cacheable_methods
        == async_transport.controller.cacheable_methods
        == ("GET",)
    )
    assert (
        transport.controller.cacheable_status_codes
        == async_transport.controller.cacheable_status_codes
        == (200, 203, 300, 301, 308)
    )
    assert transport.controller.always_cache is False
    assert async_transport.controller.always_cache is False


def test_cache_control_transport_handle_request(cache: httpx_cache.BaseCache):
    transport = httpx_cache.CacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # create a random request
    request = httpx.Request("GET", "http://test-request-1")

    # we start with an empty cache
    response = transport.handle_request(request)

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = transport.handle_request(request)
    # second response is from cache
    assert getattr(response2, "from_cache") is True
    assert response.content == response2.content
    transport.close()


async def test_cache_control_transport_handle_async_request(
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.AsyncCacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # create a random request
    request = httpx.Request("GET", "http://test-request-1")

    # we start with an empty cache
    response = await transport.handle_async_request(request)

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = await transport.handle_async_request(request)
    # second response is from cache
    assert getattr(response2, "from_cache") is True
    assert response.content == response2.content
    await transport.aclose()


def test_cache_control_transport_handle_request_no_cache(cache: httpx_cache.BaseCache):
    transport = httpx_cache.CacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # we start with an empty cache
    response = transport.handle_request(httpx.Request("GET", "http://test-request-1"))

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = transport.handle_request(
        httpx.Request(
            "GET", "http://test-request-1", headers={"cache-control": "no-cache"}
        )
    )
    # second response is not from cache
    assert getattr(response2, "from_cache") is False
    assert response.content != response2.content

    # run a 3rd request to get from cache
    response3 = transport.handle_request(httpx.Request("GET", "http://test-request-1"))
    # second response is not from cache
    assert getattr(response3, "from_cache") is True
    assert response2.content == response3.content

    transport.close()


async def test_cache_control_transport_handle_async_request_no_cache(
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.AsyncCacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # we start with an empty cache
    response = await transport.handle_async_request(
        httpx.Request("GET", "http://test-request-1")
    )

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = await transport.handle_async_request(
        httpx.Request(
            "GET", "http://test-request-1", headers={"cache-control": "no-cache"}
        )
    )
    # second response is not from cache
    assert getattr(response2, "from_cache") is False
    assert response.content != response2.content

    # run a 3rd request to get from cache
    response3 = await transport.handle_async_request(
        httpx.Request("GET", "http://test-request-1")
    )
    # second response is not from cache
    assert getattr(response3, "from_cache") is True
    assert response2.content == response3.content

    await transport.aclose()


def test_cache_control_transport_handle_request_no_store(cache: httpx_cache.BaseCache):
    transport = httpx_cache.CacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # we start with an empty cache
    response = transport.handle_request(
        httpx.Request(
            "GET", "http://test-request-1", headers={"cache-control": "no-store"}
        )
    )

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = transport.handle_request(httpx.Request("GET", "http://test-request-1"))
    # second response is not from cache
    assert getattr(response2, "from_cache") is False
    assert response.content != response2.content

    # run a 3rd request to get from cache
    response3 = transport.handle_request(httpx.Request("GET", "http://test-request-1"))

    # 3rd response is from cache
    assert getattr(response3, "from_cache") is True
    assert response2.content == response3.content

    transport.close()


async def test_cache_control_transport_handle_async_request_no_store(
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.AsyncCacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # we start with an empty cache
    response = await transport.handle_async_request(
        httpx.Request(
            "GET", "http://test-request-1", headers={"cache-control": "no-store"}
        )
    )

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = await transport.handle_async_request(
        httpx.Request("GET", "http://test-request-1")
    )
    # second response is not from cache
    assert getattr(response2, "from_cache") is False
    assert response.content != response2.content

    # run a 3rd request to get from cache
    response3 = await transport.handle_async_request(
        httpx.Request("GET", "http://test-request-1")
    )
    # second response is not from cache
    assert getattr(response3, "from_cache") is True
    assert response2.content == response3.content

    await transport.aclose()


def test_cache_control_transport_handle_request_no_store_always_cache(
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.CacheControlTransport(
        cache=cache,
        transport=httpx.MockTransport(random_response_handler),
        always_cache=True,
    )

    # we start with an empty cache
    response1 = transport.handle_request(
        httpx.Request(
            "GET", "http://test-request-1", headers={"cache-control": "no-store"}
        )
    )

    # first response is not from cache (since it's the first request)
    assert getattr(response1, "from_cache") is False

    # run the same request again, it should be from cache, since we always cache
    response2 = transport.handle_request(httpx.Request("GET", "http://test-request-1"))
    assert getattr(response2, "from_cache") is True
    assert response2.content == response1.content

    transport.close()


async def test_cache_control_transport_handle_async_request_no_store_always_cache(
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.AsyncCacheControlTransport(
        cache=cache,
        transport=httpx.MockTransport(random_response_handler),
        always_cache=True,
    )

    # we start with an empty cache
    response1 = await transport.handle_async_request(
        httpx.Request(
            "GET", "http://test-request-1", headers={"cache-control": "no-store"}
        )
    )

    # first response is not from cache (since it's the first request)
    assert getattr(response1, "from_cache") is False

    # run the same request again, it should be from cache, since we always cache
    response2 = await transport.handle_async_request(
        httpx.Request("GET", "http://test-request-1")
    )
    assert getattr(response2, "from_cache") is True
    assert response2.content == response1.content

    await transport.aclose()


@mock.patch.object(httpx_cache.CacheControl, "is_response_fresh", return_value=False)
def test_cache_control_transport_handle_request_stale_response(
    mock_is_response_fresh: mock.MagicMock,
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.CacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # create a random request
    request = httpx.Request("GET", "http://test-request-1")

    # we start with an empty cache
    response = transport.handle_request(request)

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = transport.handle_request(request)
    # second response is from cache
    assert getattr(response2, "from_cache") is False
    assert response.content != response2.content
    mock_is_response_fresh.assert_called_once()
    transport.close()


@mock.patch.object(httpx_cache.CacheControl, "is_response_fresh", return_value=False)
async def test_cache_control_transport_handle_async_request_stale_response(
    mock_is_response_fresh: mock.MagicMock,
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.AsyncCacheControlTransport(
        cache=cache, transport=httpx.MockTransport(random_response_handler)
    )

    # create a random request
    request = httpx.Request("GET", "http://test-request-1")

    # we start with an empty cache
    response = await transport.handle_async_request(request)

    # first response is not from cache
    assert getattr(response, "from_cache") is False

    # run the same request again
    response2 = await transport.handle_async_request(request)
    # second response is from cache
    assert getattr(response2, "from_cache") is False
    assert response.content != response2.content
    mock_is_response_fresh.assert_called_once()
    await transport.aclose()


def test_cache_control_transport_handle_request_with_response_stream(
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.CacheControlTransport(
        cache=cache, transport=httpx.MockTransport(stream_response_handler)
    )

    # create a random request
    request = httpx.Request("GET", "http://test-request-1")

    # we start with an empty cache
    response = transport.handle_request(request)

    # check that the response has no content
    assert not hasattr(response, "_content")

    # we can hijack the cach and try to GET the response
    # (to get null, since callback not called)
    cached = transport.cache.get(request)
    assert cached is None

    # we still need to make sure first response is not from cache
    assert getattr(response, "from_cache") is False

    # we read the response
    response.read()

    # if we check the cached again it should not be empty
    cached = transport.cache.get(request)
    assert isinstance(cached, httpx.Response)

    # cached should also be a stream since first response was also a stream
    # in other words it has no _content yet
    assert not hasattr(cached, "_content")
    # we read the cached response
    cached.read()
    assert cached.content == response.content

    # run the same request again
    response2 = transport.handle_request(request)
    # second response is from cache
    assert getattr(response2, "from_cache") is True
    assert not hasattr(response2, "_content")
    assert response2.read() == response.content
    transport.close()


async def test_cache_control_transport_handle_async_request_with_response_stream(
    cache: httpx_cache.BaseCache,
):
    transport = httpx_cache.AsyncCacheControlTransport(
        cache=cache, transport=httpx.MockTransport(stream_response_handler)
    )

    # create a random request
    request = httpx.Request("GET", "http://test-request-1")

    # we start with an empty cache
    response = await transport.handle_async_request(request)

    # check that the response has no content
    assert not hasattr(response, "_content")

    # we can hijack the cach and try to GET the response
    # (to get null, since callback not called)
    cached = await transport.cache.aget(request)
    assert cached is None

    # we still need to make sure first response is not from cache
    assert getattr(response, "from_cache") is False

    # we read the response
    await response.aread()

    # if we check the cached again it should not be empty
    cached = await transport.cache.aget(request)
    assert isinstance(cached, httpx.Response)

    # cached should also be a stream since first response was also a stream
    # in other words it has no _content yet
    assert not hasattr(cached, "_content")
    # we read the cached response
    await cached.aread()
    assert cached.content == response.content

    # run the same request again
    response2 = await transport.handle_async_request(request)
    # second response is from cache
    assert getattr(response2, "from_cache") is True
    assert not hasattr(response2, "_content")
    assert await response2.aread() == response.content
    await transport.aclose()
