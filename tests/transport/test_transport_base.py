import httpx
import pytest

from httpx_cache.transport.base import CacheControlTransportMixin


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


def test_cache_control_transport_mixin_is_request_cacheable_with_no_cache_headers():
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "no-cache"}
    )
    mixin = CacheControlTransportMixin()
    assert mixin.is_request_cacheable(request) is False


def test_cache_control_transport_mixin_is_request_cacheable_with_no_store_headers():
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "no-store"}
    )
    mixin = CacheControlTransportMixin()
    assert mixin.is_request_cacheable(request) is False


def test_cache_control_transport_mixin_is_request_cacheable_with_max_age_0_headers():
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "max-age=0"}
    )
    mixin = CacheControlTransportMixin()
    assert mixin.is_request_cacheable(request) is False


@pytest.mark.parametrize(
    "status_code,cacheable_status_codes,expected",
    [(200, (), False), (200, (200,), True)],
)
def test_cache_control_transport_mixin_is_response_cacheable_with_status_code(
    status_code, cacheable_status_codes, expected
):
    response = httpx.Response(status_code)
    mixin = CacheControlTransportMixin(cacheable_status_codes=cacheable_status_codes)
    assert mixin.is_response_cacheable(response) is expected


def test_cache_control_transport_mixin_is_response_cacheable_with_no_store_headers():
    response = httpx.Response(200, headers={"cache-control": "no-store"})
    mixin = CacheControlTransportMixin()
    assert mixin.is_response_cacheable(response) is False
