import httpx
import pytest

from httpx_cache.transport.base import CacheControlTransportMixin


def test_cache_control_transport_mixin_is_request_cacheable_with_headers(
    httpx_headers_cacheable,
):
    headers, expected = httpx_headers_cacheable
    request = httpx.Request("GET", "http://testurl", headers=headers)
    mixin = CacheControlTransportMixin()
    assert mixin.is_request_cacheable(request) is expected


def test_cache_control_transport_mixin_is_request_cacheable_with_relative_url():
    request = httpx.Request("GET", "/items")
    mixin = CacheControlTransportMixin()
    assert mixin.is_request_cacheable(request) is False


@pytest.mark.parametrize(
    "method,cacheable_methods,expected", [("GET", (), False), ("GET", ("GET",), True)]
)
def test_cache_control_transport_mixin_is_request_cacheable_with_method(
    method, cacheable_methods, expected
):
    request = httpx.Request(method, "http://testurl")
    mixin = CacheControlTransportMixin(cacheable_methods=cacheable_methods)
    assert mixin.is_request_cacheable(request) is expected


def test_cache_control_transport_mixin_is_response_cacheable_with_headers(
    httpx_headers: httpx.Headers,
):
    expected = False if any(v == "no-store" for _, v in httpx_headers.items()) else True
    request = httpx.Response(200, headers=httpx_headers)
    mixin = CacheControlTransportMixin()
    assert mixin.is_response_cacheable(request) is expected


@pytest.mark.parametrize(
    "status_code,cacheable_status_codes,expected",
    [(200, (), False), (200, (200,), True)],
)
def test_cache_control_transport_mixin_is_response_cacheable_with_status_code(
    status_code, cacheable_status_codes, expected
):
    request = httpx.Response(status_code)
    mixin = CacheControlTransportMixin(cacheable_status_codes=cacheable_status_codes)
    assert mixin.is_response_cacheable(request) is expected
