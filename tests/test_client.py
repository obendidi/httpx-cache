import httpx
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio


def test_httpx_cache_client_with_existing_cache_control_transport():
    transport = httpx_cache.CacheControlTransport()
    with httpx_cache.Client(transport=transport) as client:
        assert isinstance(client, httpx.Client)
        assert isinstance(client._transport, httpx_cache.CacheControlTransport)
        assert not isinstance(
            client._transport.transport, httpx_cache.CacheControlTransport
        )


def test_httpx_cache_client(respx_mock):
    my_route = respx_mock.get("https://example.org/").mock(
        return_value=httpx.Response(200, json={"foo": "bar"})
    )
    with httpx_cache.Client() as client:
        assert isinstance(client, httpx.Client)
        assert isinstance(client._transport, httpx_cache.CacheControlTransport)
        response = client.get("https://example.org/")
        cached = client.get("https://example.org/")
        assert my_route.called
        assert getattr(response, "from_cache") is False
        assert getattr(cached, "from_cache") is True
        assert cached.status_code == response.status_code == 200
        assert cached.json() == response.json() == {"foo": "bar"}


async def test_httpx_cache_async_client_with_existing_cache_control_transport():
    transport = httpx_cache.AsyncCacheControlTransport()
    async with httpx_cache.AsyncClient(transport=transport) as client:
        assert isinstance(client, httpx.AsyncClient)
        assert isinstance(client._transport, httpx_cache.AsyncCacheControlTransport)
        assert not isinstance(
            client._transport.transport, httpx_cache.AsyncCacheControlTransport
        )


async def test_httpx_cache_async_client(respx_mock):
    my_route = respx_mock.get("https://example.org/").mock(
        return_value=httpx.Response(200, json={"foo": "bar"})
    )
    async with httpx_cache.AsyncClient() as client:
        assert isinstance(client, httpx.AsyncClient)
        assert isinstance(client._transport, httpx_cache.AsyncCacheControlTransport)
        response = await client.get("https://example.org/")
        cached = await client.get("https://example.org/")
        assert my_route.called
        assert getattr(response, "from_cache") is False
        assert getattr(cached, "from_cache") is True
        assert cached.status_code == response.status_code == 200
        assert cached.json() == response.json() == {"foo": "bar"}
