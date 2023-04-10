import httpx
import mock
import pytest

import httpx_cache
from httpx_cache.cache.redis import RedisCache, Redis, AsyncRedis

pytestmark = pytest.mark.anyio

testcases = [
    httpx_cache.BytesJsonSerializer(),
    httpx_cache.MsgPackSerializer(),
]
testids = [
    "BytesJsonSerializer",
    "MsgPackSerializer",
]


@mock.patch.object(Redis, "from_url")
@mock.patch.object(AsyncRedis, "from_url")
def test_redis_cache_init_default_values(
    mock_async_redis_from_url: mock.Mock,
    mock_redis_from_url: mock.Mock,
) -> None:
    redis_mock = mock.Mock()
    aredis_mock = mock.Mock()

    mock_redis_from_url.return_value = redis_mock
    mock_async_redis_from_url.return_value = aredis_mock
    cache = RedisCache()

    assert cache.namespace == "httpx_cache"
    assert cache.redis == redis_mock
    assert cache.aredis == aredis_mock
    assert isinstance(cache.serializer, httpx_cache.MsgPackSerializer)
    assert cache.default_ttl is None


def test_redis_cache_get_not_found(
    httpx_request: httpx.Request,
    redis_cache: RedisCache,
):
    cached = redis_cache.get(httpx_request)
    assert cached is None


async def test_redis_cache_aget_not_found(
    redis_cache: RedisCache,
    httpx_request: httpx.Request,
):
    cached = await redis_cache.aget(httpx_request)
    assert cached is None


def test_redis_cache_set_get_delete(
    redis_cache: RedisCache,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    # make sure mock cache is new and empty
    assert len(redis_cache.redis._data) == 0

    # check again that cache is empty
    cached_response = redis_cache.get(httpx_request)
    assert cached_response is None

    # cache a request
    redis_cache.set(request=httpx_request, response=httpx_response, content=None)
    assert len(redis_cache.redis._data) == 1

    # get the cached response
    cached_response = redis_cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    redis_cache.delete(httpx_request)
    assert len(redis_cache.redis._data) == 0

    # delete with cached file not found
    # should do nothing (not raise an error)
    redis_cache.delete(httpx_request)

    redis_cache.close()


async def test_redis_cache_aset_aget_adelete(
    redis_cache: RedisCache,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    assert len(redis_cache.aredis._data) == 0

    # cache a request
    await redis_cache.aset(request=httpx_request, response=httpx_response, content=None)

    # make sure we have one request inside
    assert len(redis_cache.aredis._data) == 1

    # get the cached response
    cached_response = await redis_cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    await redis_cache.adelete(httpx_request)
    assert len(redis_cache.aredis._data) == 0

    await redis_cache.aclose()


def test_redis_cache_set_get_delete_with_streaming_body(
    redis_cache: RedisCache,
    httpx_request: httpx.Request,
    streaming_body,
):
    assert len(redis_cache.redis._data) == 0

    httpx_response = httpx.Response(200, content=streaming_body)

    def callback(content: bytes) -> None:
        # set it in cache
        redis_cache.set(request=httpx_request, response=httpx_response, content=content)

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    httpx_response.read()

    # make sure we have one request inside
    assert len(redis_cache.redis._data) == 1

    # get the cached response
    cached_response = redis_cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert cached_response.read() == httpx_response.content

    # delete the cached response
    redis_cache.delete(httpx_request)
    assert len(redis_cache.redis._data) == 0

    redis_cache.close()


async def test_redis_cache_aset_aget_adelete_with_async_streaming_body(
    redis_cache: RedisCache,
    httpx_request: httpx.Request,
    async_streaming_body,
):
    assert len(redis_cache.aredis._data) == 0

    httpx_response = httpx.Response(200, content=async_streaming_body)

    async def callback(content: bytes) -> None:
        # set it in cache
        await redis_cache.aset(
            request=httpx_request, response=httpx_response, content=content
        )

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    await httpx_response.aread()

    # make sure we have one request inside
    assert len(redis_cache.aredis._data) == 1

    # get the cached response
    cached_response = await redis_cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert await cached_response.aread() == httpx_response.content

    # delete the cached response
    await redis_cache.adelete(httpx_request)
    assert len(redis_cache.aredis._data) == 0

    await redis_cache.aclose()
