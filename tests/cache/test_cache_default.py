import httpx
import pytest

from httpx_cache.cache import AsyncDictCache, DictCache

pytestmark = pytest.mark.anyio


def test_dict_cache_invalid_data_init():
    with pytest.raises(TypeError):
        DictCache(data=[])


def test_async_dict_cache_invalid_data_init():
    with pytest.raises(TypeError):
        AsyncDictCache(data=())


def test_dict_cache_get_not_found(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = DictCache(serializer=dummy_serializer)

    cached = cache.get(request)
    assert cached is None


def test_dict_cache_get(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = DictCache(
        serializer=dummy_serializer,
        data={DictCache.gen_key(request): b"some-random-response"},
    )

    cached = cache.get(request)
    assert cached == b"some-random-response"


def test_dict_cache_set(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = DictCache(serializer=dummy_serializer)
    response = httpx.Response(200, content=b"some-random-response")

    cache.set(request=request, response=response, content=response.content)
    assert cache.data[DictCache.gen_key(request)] == b"some-random-response"


def test_dict_cache_update_existing(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = DictCache(
        serializer=dummy_serializer,
        data={DictCache.gen_key(request): b"some-random-response"},
    )
    response = httpx.Response(200, content=b"the-updated-response")

    cache.set(request=request, response=response, content=response.content)
    assert cache.data[DictCache.gen_key(request)] == b"the-updated-response"


def test_dict_cache_delete(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = DictCache(
        serializer=dummy_serializer,
        data={DictCache.gen_key(request): b"some-random-response"},
    )

    cache.delete(request)
    assert len(cache.data) == 0


def test_dict_cache_delete_not_found(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = DictCache(serializer=dummy_serializer)

    cache.delete(request)
    assert len(cache.data) == 0


async def test_async_dict_cache_get_not_found(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = AsyncDictCache(serializer=dummy_serializer)

    cached = await cache.aget(request)
    assert cached is None


async def test_async_dict_cache_get(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = AsyncDictCache(
        serializer=dummy_serializer,
        data={AsyncDictCache.gen_key(request): b"some-random-response"},
    )

    cached = await cache.aget(request)
    assert cached == b"some-random-response"


async def test_async_dict_cache_set(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = AsyncDictCache(serializer=dummy_serializer)
    response = httpx.Response(200, content=b"some-random-response")

    await cache.aset(request=request, response=response, content=response.content)
    assert cache.data[AsyncDictCache.gen_key(request)] == b"some-random-response"


async def test_async_dict_cache_update_existing(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = AsyncDictCache(
        serializer=dummy_serializer,
        data={DictCache.gen_key(request): b"some-random-response"},
    )
    response = httpx.Response(200, content=b"the-updated-response")

    await cache.aset(request=request, response=response, content=response.content)
    assert cache.data[DictCache.gen_key(request)] == b"the-updated-response"


async def test_async_dict_cache_delete(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = AsyncDictCache(
        serializer=dummy_serializer,
        data={AsyncDictCache.gen_key(request): b"some-random-response"},
    )

    await cache.adelete(request)
    assert len(cache.data) == 0


async def test_async_dict_cache_delete_not_found(dummy_serializer):
    request = httpx.Request("GET", "http://testurl")
    cache = AsyncDictCache(serializer=dummy_serializer)

    await cache.adelete(request)
    assert len(cache.data) == 0
