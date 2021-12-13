import httpx
import pytest

from httpx_cache.cache import AsyncDictCache, DictCache

# This is the same as using the @pytest.mark.anyio on all test functions in the module
pytestmark = pytest.mark.anyio


def test_dict_cache(dummy_serializer):
    cache = DictCache(serializer=dummy_serializer)

    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(200, content=b"Hello, World", request=request)

    # set inside the dict cache
    cache.set(request=request, response=response, content=b"Hello, World")

    # get the object
    cached_response = cache.get(request=request)

    assert cached_response is response  # same id since it should be exactly the same

    # delete the cached response
    cache.delete(request)

    # try to get the same request again
    cached_response = cache.get(request=request)
    assert cached_response is None

    # check that the cache is empty
    assert len(cache.data) == 0


async def test_async_dict_cache(dummy_serializer):
    cache = AsyncDictCache(serializer=dummy_serializer)

    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(200, content=b"Hello, World", request=request)

    # set inside the dict cache
    await cache.aset(request=request, response=response, content=b"Hello, World")

    # get the object
    cached_response = await cache.aget(request=request)

    assert cached_response is response  # same id since it should be exactly the same

    # delete the cached response
    await cache.adelete(request)

    # try to get the same request again
    cached_response = await cache.aget(request=request)
    assert cached_response is None

    # check that the cache is empty
    assert len(cache.data) == 0
