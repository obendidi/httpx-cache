import os
import shutil
import typing as tp
import uuid

import httpx
import pytest
import respx

import httpx_cache

pytestmark = pytest.mark.anyio

TEST_CACHE_DIR = os.path.join(os.path.dirname(__file__), "__cache__")


@pytest.fixture(scope="module")
def cache_dir() -> tp.Generator[str, None, None]:
    yield TEST_CACHE_DIR
    if os.path.isdir(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


@pytest.fixture(scope="module")
def respx_router():
    return respx.Router(base_url="http://testurl")


@pytest.mark.parametrize(
    "cache",
    [
        httpx_cache.DictCache(serializer=httpx_cache.DictSerializer()),
        httpx_cache.DictCache(serializer=httpx_cache.NullSerializer()),
        httpx_cache.DictCache(serializer=httpx_cache.MsgPackSerializer()),
        httpx_cache.DictCache(serializer=httpx_cache.StringSerializer()),
        httpx_cache.DictCache(serializer=httpx_cache.BytesSerializer()),
        httpx_cache.FileCache(
            serializer=httpx_cache.BytesSerializer(), cache_dir=TEST_CACHE_DIR
        ),
        httpx_cache.FileCache(
            serializer=httpx_cache.MsgPackSerializer(), cache_dir=TEST_CACHE_DIR
        ),
    ],
    ids=[
        "DictCache-DictSerializer",
        "DictCache-NullSerializer",
        "DictCache-MsgPackSerializer",
        "DictCache-StringSerializer",
        "DictCache-BytesSerializer",
        "FileCache-BytesSerializer",
        "FileCache-MsgPackSerializer",
    ],
)
def test_cache_control_transport(
    cache: httpx_cache.BaseCache, respx_router: respx.Router, cache_dir: str
):
    route = str(uuid.uuid4())
    # First response used in mock
    first_original_resp = httpx.Response(200, content=b"This is the first response.")

    # we first create a mock for the route /get
    respx_router.get(f"/{route}", name="get").mock(return_value=first_original_resp)
    mock_transport = httpx.MockTransport(respx_router.handler)

    # Create httpx Client with cacheControl transport
    client = httpx.Client(
        transport=httpx_cache.CacheControlTransport(
            transport=mock_transport, cache=cache
        ),
        base_url="http://testurl",
    )

    # get result for a query, it should be put in cache in this step
    client.get(f"/{route}")

    # overide route teh mocked route with a new response.
    # The idea is that if the cache is working as it should
    # it will return the first respinse instead of te new mocked second response
    second_original_resp = httpx.Response(200, content=b"This is the second response.")
    respx_router.get(f"/{route}", name="get").mock(return_value=second_original_resp)

    # run the same GET operation again, = first response
    cached_resp = client.get(f"/{route}")
    assert cached_resp.read() == b"This is the first response."

    # let's delete the cache and try again
    client._transport.cache.delete(httpx.Request("GET", f"http://testurl/{route}"))  # type: ignore # noqa
    new_resp = client.get(f"/{route}")
    assert new_resp.read() == b"This is the second response."
    client.close()


@pytest.mark.parametrize(
    "cache",
    [
        httpx_cache.AsyncDictCache(serializer=httpx_cache.DictSerializer()),
        httpx_cache.AsyncDictCache(serializer=httpx_cache.NullSerializer()),
        httpx_cache.AsyncDictCache(serializer=httpx_cache.MsgPackSerializer()),
        httpx_cache.AsyncDictCache(serializer=httpx_cache.StringSerializer()),
        httpx_cache.AsyncDictCache(serializer=httpx_cache.BytesSerializer()),
        httpx_cache.AsyncFileCache(
            serializer=httpx_cache.BytesSerializer(), cache_dir=TEST_CACHE_DIR
        ),
        httpx_cache.AsyncFileCache(
            serializer=httpx_cache.MsgPackSerializer(), cache_dir=TEST_CACHE_DIR
        ),
    ],
    ids=[
        "AsyncDictCache-DictSerializer",
        "AsyncDictCache-NullSerializer",
        "AsyncDictCache-MsgPackSerializer",
        "AsyncDictCache-StringSerializer",
        "AsyncDictCache-BytesSerializer",
        "AsyncFileCache-BytesSerializer",
        "AsyncFileCache-MsgPackSerializer",
    ],
)
async def test_async_cache_control_transport(
    cache: httpx_cache.AsyncBaseCache, respx_router: respx.Router, cache_dir: str
):
    route = str(uuid.uuid4())
    # First response used in mock
    first_original_resp = httpx.Response(200, content=b"This is the first response.")

    # we first create a mock for the route /get
    respx_router.get(f"/{route}", name="get").mock(return_value=first_original_resp)
    mock_transport = httpx.MockTransport(respx_router.handler)

    # Create httpx Client with cacheControl transport
    client = httpx.AsyncClient(
        transport=httpx_cache.AsyncCacheControlTransport(
            transport=mock_transport, cache=cache
        ),
        base_url="http://testurl",
    )

    # get result for a query, it should be put in cache in this step
    await client.get(f"/{route}")

    # overide route teh mocked route with a new response.
    # The idea is that if the cache is working as it should
    # it will return the first respinse instead of te new mocked second response
    second_original_resp = httpx.Response(200, content=b"This is the second response.")
    respx_router.get(f"/{route}", name="get").mock(return_value=second_original_resp)

    # run the same GET operation again, = first response
    cached_resp = await client.get(f"/{route}")
    assert await cached_resp.aread() == b"This is the first response."

    # let's delete the cache and try again
    await client._transport.cache.adelete(httpx.Request("GET", f"http://testurl/{route}"))  # type: ignore # noqa
    new_resp = await client.get(f"/{route}")

    assert await new_resp.aread() == b"This is the second response."
    await client.aclose()
