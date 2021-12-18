import uuid

import httpx
import pytest

import httpx_cache
from httpx_cache.cache.base import gen_cache_key

pytestmark = pytest.mark.anyio

TEST_REQUEST = httpx.Request("GET", "http://testurl")
TEST_REQUEST_KEY = gen_cache_key(TEST_REQUEST)
TEST_RESPONSE = httpx.Response(status_code=200, content=str(uuid.uuid4()).encode())


@pytest.fixture(scope="module")
def null_serializer():
    return httpx_cache.NullSerializer()


@pytest.fixture
def cache(null_serializer: httpx_cache.BaseSerializer):
    return httpx_cache.DictCache(
        serializer=null_serializer, data={TEST_REQUEST_KEY: TEST_RESPONSE}
    )


@pytest.fixture
def async_cache(null_serializer: httpx_cache.BaseSerializer):
    return httpx_cache.AsyncDictCache(
        serializer=null_serializer, data={TEST_REQUEST_KEY: TEST_RESPONSE}
    )


def test_dict_cache_invalid_data_init():
    with pytest.raises(TypeError):
        httpx_cache.DictCache(data=[])


def test_async_dict_cache_invalid_data_init():
    with pytest.raises(TypeError):
        httpx_cache.AsyncDictCache(data=())


def test_dict_cache_get_not_found(cache: httpx_cache.DictCache):
    cached = cache.get(httpx.Request("GET", f"http://{uuid.uuid4()}"))
    assert cached is None


def test_dict_cache_get(cache: httpx_cache.DictCache):
    cached = cache.get(TEST_REQUEST)
    assert cached is TEST_RESPONSE


def test_dict_cache_set(cache: httpx_cache.DictCache):
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)
    cache.set(request=request, response=response)
    key = gen_cache_key(request)
    assert len(cache.data) == 2
    assert cache.data[key] is response


def test_dict_cache_update_existing(cache: httpx_cache.DictCache):
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)
    cache.set(request=TEST_REQUEST, response=response)
    assert len(cache.data) == 1
    assert cache.data[TEST_REQUEST_KEY] is response


def test_dict_cache_delete(cache: httpx_cache.DictCache):
    cache.delete(TEST_REQUEST)
    assert len(cache.data) == 0


def test_dict_cache_delete_not_found(cache: httpx_cache.DictCache):
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    cache.delete(request)
    assert len(cache.data) == 1


async def test_async_dict_cache_get_not_found(async_cache: httpx_cache.AsyncDictCache):
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    cached = await async_cache.aget(request)
    assert cached is None


async def test_async_dict_cache_get(async_cache: httpx_cache.AsyncDictCache):
    cached = await async_cache.aget(TEST_REQUEST)
    assert cached is TEST_RESPONSE


async def test_async_dict_cache_set(async_cache: httpx_cache.AsyncDictCache):
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)
    await async_cache.aset(request=request, response=response)
    key = gen_cache_key(request)
    assert len(async_cache.data) == 2
    assert async_cache.data[key] is response


async def test_async_dict_cache_update_existing(
    async_cache: httpx_cache.AsyncDictCache,
):
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)

    await async_cache.aset(request=TEST_REQUEST, response=response)
    assert len(async_cache.data) == 1
    assert async_cache.data[TEST_REQUEST_KEY] is response


async def test_async_dict_cache_delete(async_cache: httpx_cache.AsyncDictCache):
    await async_cache.adelete(TEST_REQUEST)
    assert len(async_cache.data) == 0


async def test_async_dict_cache_delete_not_found(
    async_cache: httpx_cache.AsyncDictCache,
):
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    await async_cache.adelete(request)
    assert len(async_cache.data) == 1


@pytest.mark.parametrize(
    "serializer",
    [
        httpx_cache.DictSerializer(),
        httpx_cache.MsgPackSerializer(),
        httpx_cache.StringSerializer(),
        httpx_cache.BytesSerializer(),
        httpx_cache.NullSerializer(),
    ],
    ids=[
        "DictSerializer",
        "MsgPackSerializer",
        "StringSerializer",
        "BytesSerializer",
        "NullSerializer",
    ],
)
def test_dict_cache_with_serializer(serializer: httpx_cache.BaseSerializer):

    # create an empty cache
    cache = httpx_cache.DictCache(serializer=serializer, data={})

    # make sure we start with an empty cache
    assert len(cache.data) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=str(uuid.uuid4()).encode())

    # set it in cache
    cache.set(request=request, response=response)

    # the cache should have exactly one element
    assert len(cache.data) == 1

    # lets get the cached response
    cached_response = cache.get(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == cached_response.content

    # delete the cached response
    cache.delete(request)
    assert len(cache.data) == 0


@pytest.mark.parametrize(
    "serializer",
    [
        httpx_cache.DictSerializer(),
        httpx_cache.MsgPackSerializer(),
        httpx_cache.StringSerializer(),
        httpx_cache.BytesSerializer(),
        httpx_cache.NullSerializer(),
    ],
    ids=[
        "DictSerializer",
        "MsgPackSerializer",
        "StringSerializer",
        "BytesSerializer",
        "NullSerializer",
    ],
)
async def test_async_dict_cache_with_serializer(serializer: httpx_cache.BaseSerializer):

    # create an empty cache
    cache = httpx_cache.AsyncDictCache(serializer=serializer, data={})

    # make sure we start with an empty cache
    assert len(cache.data) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=str(uuid.uuid4()).encode())

    # set it in cache
    await cache.aset(request=request, response=response)

    # the cache should have exactly one element
    assert len(cache.data) == 1

    # lets get the cached response
    cached_response = await cache.aget(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == cached_response.content

    # delete the cached response
    await cache.adelete(request)
    assert len(cache.data) == 0


@pytest.mark.parametrize(
    "serializer",
    [
        httpx_cache.DictSerializer(),
        httpx_cache.MsgPackSerializer(),
        httpx_cache.StringSerializer(),
        httpx_cache.BytesSerializer(),
        httpx_cache.NullSerializer(),
    ],
    ids=[
        "DictSerializer",
        "MsgPackSerializer",
        "StringSerializer",
        "BytesSerializer",
        "NullSerializer",
    ],
)
def test_dict_cache_streaming_response_with_serializer(
    serializer: httpx_cache.BaseSerializer, streaming_body
):

    # create an empty cache
    cache = httpx_cache.DictCache(serializer=serializer, data={})

    # make sure we start with an empty cache
    assert len(cache.data) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=streaming_body)

    def callback(content: bytes) -> None:
        # set it in cache
        cache.set(request=request, response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    response.read()

    # the cache should have exactly one element
    assert len(cache.data) == 1

    # lets get the cached response
    cached_response = cache.get(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == cached_response.read()

    # delete the cached response
    cache.delete(request)
    assert len(cache.data) == 0


@pytest.mark.parametrize(
    "serializer",
    [
        httpx_cache.DictSerializer(),
        httpx_cache.MsgPackSerializer(),
        httpx_cache.StringSerializer(),
        httpx_cache.BytesSerializer(),
        httpx_cache.NullSerializer(),
    ],
    ids=[
        "DictSerializer",
        "MsgPackSerializer",
        "StringSerializer",
        "BytesSerializer",
        "NullSerializer",
    ],
)
async def test_async_dict_cache_streaming_response_with_serializer(
    serializer: httpx_cache.BaseSerializer, async_streaming_body
):

    # create an empty cache
    cache = httpx_cache.AsyncDictCache(serializer=serializer, data={})

    # make sure we start with an empty cache
    assert len(cache.data) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=async_streaming_body)

    async def callback(content: bytes) -> None:
        # set it in cache
        await cache.aset(request=request, response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    await response.aread()

    # the cache should have exactly one element
    assert len(cache.data) == 1

    # lets get the cached response
    cached_response = await cache.aget(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == await cached_response.aread()

    # delete the cached response
    await cache.adelete(request)
    assert len(cache.data) == 0
