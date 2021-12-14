import httpx
import pytest
import respx

from httpx_cache.transport.default import (
    AsyncCacheControlTransport,
    CacheControlTransport,
)

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
def respx_router():
    return respx.Router(base_url="http://testurl")


def test_cache_control_transport(
    respx_router: respx.Router, httpx_sync_response: httpx.Response
):

    # we create a first mock for a route
    respx_router.get("/simple-get", name="simple-get").mock(
        return_value=httpx_sync_response,
    )
    mock_transport = httpx.MockTransport(respx_router.handler)
    cache_transport = CacheControlTransport(transport=mock_transport)
    client = httpx.Client(transport=cache_transport, base_url="http://testurl")

    # get result for a query, it should be put in cache in this step
    client.get("/simple-get")

    # overide route, but since it's cached it should return same as before
    respx_router.get("/simple-get", name="simple-get").mock(
        return_value=httpx.Response(200, json={"name": "error"}),
    )
    response = client.get("/simple-get")

    assert response.read() == httpx_sync_response.read()
    client.close()

    # lets check the cache
    assert (
        len(cache_transport.cache.data) == 1  # type: ignore
    )  # only 1 element in cache
    assert isinstance(cache_transport.cache.data["http://testurl/simple-get"], bytes)  # type: ignore # noqa


async def test_async_cache_control_transport(
    respx_router: respx.Router, httpx_async_response: httpx.Response
):

    # we create a first mock for a route
    respx_router.get("/simple-get", name="simple-get").mock(
        return_value=httpx_async_response,
    )
    mock_transport = httpx.MockTransport(respx_router.async_handler)
    cache_transport = AsyncCacheControlTransport(transport=mock_transport)
    client = httpx.AsyncClient(transport=cache_transport, base_url="http://testurl")

    # get result for a query, it should be put in cache in this step
    await client.get("/simple-get")

    # overide route, but since it's cached it should return same as before
    respx_router.get("/simple-get", name="simple-get").mock(
        return_value=httpx.Response(200, json={"name": "error"}),
    )
    response = await client.get("/simple-get")

    assert await response.aread() == await httpx_async_response.aread()
    await client.aclose()

    # lets check the cache
    assert (
        len(cache_transport.cache.data) == 1  # type: ignore
    )  # only 1 element in cache
    assert isinstance(cache_transport.cache.data["http://testurl/simple-get"], bytes)  # type: ignore # noqa
