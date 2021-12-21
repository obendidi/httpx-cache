import httpx
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio


testcases = [
    httpx_cache.DictSerializer(),
    httpx_cache.StringJsonSerializer(),
    httpx_cache.BytesJsonSerializer(),
    httpx_cache.MsgPackSerializer(),
]
testids = [
    "DictSerializer",
    "StringJsonSerializer",
    "BytesJsonSerializer",
    "MsgPackSerializer",
]


def test_dict_cache_invalid_data_init():
    with pytest.raises(TypeError):
        httpx_cache.DictCache(data=["data"])


def test_dict_cache_invalid_serializer():
    with pytest.raises(TypeError):
        httpx_cache.DictCache(serializer="Serial")


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_dict_cache_get_not_found(
    serializer: httpx_cache.BaseSerializer, httpx_request: httpx.Request
):
    cache = httpx_cache.DictCache(serializer=serializer)
    cached = cache.get(httpx_request)
    assert cached is None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_dict_cache_aget_not_found(
    serializer: httpx_cache.BaseSerializer, httpx_request: httpx.Request
):
    cache = httpx_cache.DictCache(serializer=serializer)
    cached = await cache.aget(httpx_request)
    assert cached is None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_dict_cache_set_get_delete(
    serializer: httpx_cache.BaseSerializer,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    cache = httpx_cache.DictCache(serializer=serializer)

    assert len(cache.data) == 0

    # cache a request
    cache.set(request=httpx_request, response=httpx_response, content=None)

    # make sure we have one request inside
    assert len(cache.data) == 1

    # get the cached response
    cached_response = cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    cache.delete(httpx_request)
    assert len(cache.data) == 0

    cache.close()


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_dict_cache_aset_aget_adelete(
    serializer: httpx_cache.BaseSerializer,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    cache = httpx_cache.DictCache(serializer=serializer)

    assert len(cache.data) == 0

    # cache a request
    await cache.aset(request=httpx_request, response=httpx_response, content=None)

    # make sure we have one request inside
    assert len(cache.data) == 1

    # get the cached response
    cached_response = await cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    await cache.adelete(httpx_request)
    assert len(cache.data) == 0

    await cache.aclose()


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_dict_cache_set_get_delete_with_streaming_body(
    serializer: httpx_cache.BaseSerializer,
    httpx_request: httpx.Request,
    streaming_body,
):
    cache = httpx_cache.DictCache(serializer=serializer)

    assert len(cache.data) == 0

    httpx_response = httpx.Response(200, content=streaming_body)

    def callback(content: bytes) -> None:
        # set it in cache
        cache.set(request=httpx_request, response=httpx_response, content=content)

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    httpx_response.read()

    # make sure we have one request inside
    assert len(cache.data) == 1

    # get the cached response
    cached_response = cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert cached_response.read() == httpx_response.content

    # delete the cached response
    cache.delete(httpx_request)
    assert len(cache.data) == 0

    cache.close()


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_dict_cache_aset_aget_adelete_with_async_streaming_body(
    serializer: httpx_cache.BaseSerializer,
    httpx_request: httpx.Request,
    async_streaming_body,
):
    cache = httpx_cache.DictCache(serializer=serializer)

    assert len(cache.data) == 0

    httpx_response = httpx.Response(200, content=async_streaming_body)

    async def callback(content: bytes) -> None:
        # set it in cache
        await cache.aset(
            request=httpx_request, response=httpx_response, content=content
        )

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    await httpx_response.aread()

    # make sure we have one request inside
    assert len(cache.data) == 1

    # get the cached response
    cached_response = await cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert await cached_response.aread() == httpx_response.content

    # delete the cached response
    await cache.adelete(httpx_request)
    assert len(cache.data) == 0

    await cache.aclose()
