import uuid
from unittest import mock

import httpx
import pytest

import httpx_cache
from tests.conftest import TEST_CACHE_DIR


def _handler(request: httpx.Request) -> httpx.Response:
    key = str(request.url).lstrip("http://")
    return httpx.Response(200, content=key.encode("utf-8"))


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
def test_cache_control_transport_handle_request_with_cache(
    cache: httpx_cache.BaseCache, cache_dir: str
):

    key = str(uuid.uuid4())
    url = f"http://{key}"
    request = httpx.Request("GET", url)

    transport = httpx_cache.CacheControlTransport(
        cache=cache, transport=httpx.MockTransport(_handler)
    )

    # first request is not from cache
    first_response = transport.handle_request(request)
    assert getattr(first_response, "from_cache") is False

    # second same request should be from cache
    second_response = transport.handle_request(request)
    assert getattr(second_response, "from_cache") is True
    assert first_response.content == second_response.content == key.encode("utf-8")
    transport.close()


@mock.patch.object(
    httpx_cache.CacheControlTransport, "is_request_cacheable", return_value=False
)
def test_cache_control_transport_handle_request_with_request_not_cacheable(
    mock_is_request_cacheable: mock.MagicMock,
):
    def _handler(request: httpx.Request) -> httpx.Response:
        key = str(request.url).lstrip("http://")
        return httpx.Response(200, content=key.encode("utf-8"))

    key = str(uuid.uuid4())
    url = f"http://{key}"
    request = httpx.Request("GET", url)

    transport = httpx_cache.CacheControlTransport(
        transport=httpx.MockTransport(_handler), cache=httpx_cache.DictCache()
    )

    # first request is not from cache
    first_response = transport.handle_request(request)
    assert getattr(first_response, "from_cache") is False

    # second same request is still not from cache
    second_response = transport.handle_request(request)
    assert getattr(second_response, "from_cache") is False
    transport.close()


@mock.patch.object(
    httpx_cache.CacheControlTransport, "is_response_cacheable", return_value=False
)
def test_cache_control_transport_handle_request_with_response_not_cacheable(
    mock_is_response_cacheable: mock.MagicMock,
):

    key = str(uuid.uuid4())
    url = f"http://{key}"
    request = httpx.Request("GET", url)

    transport = httpx_cache.CacheControlTransport(
        transport=httpx.MockTransport(_handler), cache=httpx_cache.DictCache()
    )

    # first request is not from cache
    first_response = transport.handle_request(request)
    assert getattr(first_response, "from_cache") is False

    # second same request is still not from cache
    second_response = transport.handle_request(request)
    assert getattr(second_response, "from_cache") is False
    transport.close()
