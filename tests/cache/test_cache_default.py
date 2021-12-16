import typing as tp
import uuid

import httpx
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio

TEST_REQUEST = httpx.Request("GET", "http://testurl")
TEST_RESPONSE = httpx.Response(status_code=200, content=str(uuid.uuid4()).encode())


@pytest.fixture
def serializer():
    return httpx_cache.IdentitySerializer()


@pytest.fixture
def init_data(serializer: httpx_cache.IdentitySerializer):
    key = httpx_cache.BaseCache.gen_key(TEST_REQUEST)
    value = serializer.dumps(response=TEST_RESPONSE)
    return {key: value}


@pytest.fixture
def cache(serializer: httpx_cache.IdentitySerializer, init_data: tp.Dict[str, tp.Any]):
    return httpx_cache.DictCache(serializer=serializer, data=init_data)


@pytest.fixture
def async_cache(
    serializer: httpx_cache.BaseSerializer, init_data: tp.Dict[str, tp.Any]
):
    return httpx_cache.AsyncDictCache(serializer=serializer, data=init_data)


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
    assert isinstance(cached, httpx.Response)
    assert cached.status_code == 200
    assert cached.content == TEST_RESPONSE.content


def test_dict_cache_set(cache: httpx_cache.DictCache):

    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)

    cache.set(request=request, response=response)
    key = httpx_cache.DictCache.gen_key(request)
    assert len(cache.data) == 2
    assert cache.data[key] == {
        "status_code": 200,
        "headers": [(b"Content-Length", b"36")],
        "_request": None,
        "next_request": None,
        "history": [],
        "is_stream_consumed": True,
        "_num_bytes_downloaded": 0,
        "_content": content,
    }


def test_dict_cache_update_existing(cache: httpx_cache.DictCache):
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)

    cache.set(request=TEST_REQUEST, response=response)
    key = httpx_cache.DictCache.gen_key(TEST_REQUEST)
    assert len(cache.data) == 1
    assert cache.data[key] == {
        "status_code": 200,
        "headers": [(b"Content-Length", b"36")],
        "_request": None,
        "next_request": None,
        "history": [],
        "is_stream_consumed": True,
        "_num_bytes_downloaded": 0,
        "_content": content,
    }


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
    assert isinstance(cached, httpx.Response)
    assert cached.status_code == 200
    assert cached.content == TEST_RESPONSE.content


async def test_async_dict_cache_set(async_cache: httpx_cache.AsyncDictCache):
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)

    await async_cache.aset(request=request, response=response, content=response.content)
    key = httpx_cache.AsyncDictCache.gen_key(request)
    assert len(async_cache.data) == 2
    assert async_cache.data[key] == {
        "status_code": 200,
        "headers": [(b"Content-Length", b"36")],
        "_request": None,
        "next_request": None,
        "history": [],
        "is_stream_consumed": True,
        "_num_bytes_downloaded": 0,
        "_content": content,
    }


async def test_async_dict_cache_update_existing(
    async_cache: httpx_cache.AsyncDictCache,
):
    content = str(uuid.uuid4()).encode()
    response = httpx.Response(200, content=content)

    await async_cache.aset(request=TEST_REQUEST, response=response)
    key = httpx_cache.AsyncDictCache.gen_key(TEST_REQUEST)
    assert len(async_cache.data) == 1
    assert async_cache.data[key] == {
        "status_code": 200,
        "headers": [(b"Content-Length", b"36")],
        "_request": None,
        "next_request": None,
        "history": [],
        "is_stream_consumed": True,
        "_num_bytes_downloaded": 0,
        "_content": content,
    }


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
    "serializer", [httpx_cache.IdentitySerializer(), httpx_cache.MsgPackSerializer()]
)
def test_dict_cache_with_serializer(serializer: httpx_cache.BaseSerializer):

    cache = httpx_cache.DictCache(serializer=serializer, data={})
