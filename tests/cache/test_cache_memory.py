import httpx
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio


def test_dict_cache_invalid_data_init():
    with pytest.raises(TypeError):
        httpx_cache.DictCache(data=["data"])


def test_dict_cache_invalid_serializer():
    with pytest.raises(TypeError):
        httpx_cache.DictCache(serializer="Serial")


def test_dict_cache_get_not_found(
    dict_cache: httpx_cache.DictCache, httpx_request: httpx.Request
):
    cached = dict_cache.get(httpx_request)
    assert cached is None


async def test_dict_cache_aget_not_found(
    dict_cache: httpx_cache.DictCache, httpx_request: httpx.Request
):
    cached = await dict_cache.aget(httpx_request)
    assert cached is None


def test_dict_cache_set_get_delete(
    dict_cache: httpx_cache.DictCache,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    assert len(dict_cache.data) == 0

    # cache a request
    dict_cache.set(request=httpx_request, response=httpx_response, content=None)

    # make sure we have one request inside
    assert len(dict_cache.data) == 1

    # get the cached response
    cached_response = dict_cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    dict_cache.delete(httpx_request)
    assert len(dict_cache.data) == 0

    dict_cache.close()


async def test_dict_cache_aset_aget_adelete(
    dict_cache: httpx_cache.DictCache,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    assert len(dict_cache.data) == 0

    # cache a request
    await dict_cache.aset(request=httpx_request, response=httpx_response, content=None)

    # make sure we have one request inside
    assert len(dict_cache.data) == 1

    # get the cached response
    cached_response = await dict_cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    await dict_cache.adelete(httpx_request)
    assert len(dict_cache.data) == 0

    await dict_cache.aclose()


def test_dict_cache_set_get_delete_with_streaming_body(
    dict_cache: httpx_cache.DictCache,
    httpx_request: httpx.Request,
    streaming_body,
):
    assert len(dict_cache.data) == 0

    httpx_response = httpx.Response(200, content=streaming_body)

    def callback(content: bytes) -> None:
        # set it in cache
        dict_cache.set(request=httpx_request, response=httpx_response, content=content)

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    httpx_response.read()

    # make sure we have one request inside
    assert len(dict_cache.data) == 1

    # get the cached response
    cached_response = dict_cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert cached_response.read() == httpx_response.content

    # delete the cached response
    dict_cache.delete(httpx_request)
    assert len(dict_cache.data) == 0

    dict_cache.close()


async def test_dict_cache_aset_aget_adelete_with_async_streaming_body(
    dict_cache: httpx_cache.DictCache,
    httpx_request: httpx.Request,
    async_streaming_body,
):
    assert len(dict_cache.data) == 0

    httpx_response = httpx.Response(200, content=async_streaming_body)

    async def callback(content: bytes) -> None:
        # set it in cache
        await dict_cache.aset(
            request=httpx_request, response=httpx_response, content=content
        )

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    await httpx_response.aread()

    # make sure we have one request inside
    assert len(dict_cache.data) == 1

    # get the cached response
    cached_response = await dict_cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert await cached_response.aread() == httpx_response.content

    # delete the cached response
    await dict_cache.adelete(httpx_request)
    assert len(dict_cache.data) == 0

    await dict_cache.aclose()
