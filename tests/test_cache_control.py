from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

import httpx_cache
from httpx_cache.cache_control import _PERMANENT_REDIRECT_STATUSES, CacheControl


def test_is_request_cacheable(httpx_request):
    controller = httpx_cache.CacheControl()
    assert controller.is_request_cacheable(httpx_request) is True


def test_is_request_cacheable_with_relative_url():
    request = httpx.Request("GET", "/path")
    controller = httpx_cache.CacheControl()
    assert controller.is_request_cacheable(request) is False


@pytest.mark.parametrize(
    "cacheable_methods,method,expected",
    [
        (("GET",), "POST", False),
        (("GET", "POST"), "POST", True),
    ],
)
def test_is_request_cacheable_with_method(cacheable_methods, method, expected):
    request = httpx.Request(method, "http://testurl/path")
    controller = httpx_cache.CacheControl(cacheable_methods=cacheable_methods)
    assert controller.is_request_cacheable(request) is expected


def test_is_request_cacheable_with_no_cache_headers():
    request = httpx.Request(
        "GET", "http://testurl/path", headers={"cache-control": "no-cache"}
    )
    controller = httpx_cache.CacheControl()
    assert controller.is_request_cacheable(request) is False


def test_is_request_cacheable_with_max_age_0_headers():
    request = httpx.Request(
        "GET", "http://testurl/path", headers={"cache-control": "max-age=0"}
    )
    controller = httpx_cache.CacheControl()
    assert controller.is_request_cacheable(request) is False


def test_is_response_cacheable(httpx_request, httpx_response):
    controller = httpx_cache.CacheControl()
    assert (
        controller.is_response_cacheable(request=httpx_request, response=httpx_response)
        is True
    )


@pytest.mark.parametrize(
    "cacheable_status_codes,code,expected",
    [
        ((200, 203, 300, 301, 308), 200, True),
        ((500, 404), 400, False),
    ],
)
def test_is_response_cacheable_with_status_code(
    cacheable_status_codes, code, expected, httpx_request
):
    response = httpx.Response(code)
    controller = httpx_cache.CacheControl(cacheable_status_codes=cacheable_status_codes)
    assert (
        controller.is_response_cacheable(request=httpx_request, response=response)
        is expected
    )


def test_is_response_cacheable_with_response_no_store_header(
    httpx_request,
):
    response = httpx.Response(200, headers={"cache-control": "no-store"})
    controller = httpx_cache.CacheControl()
    assert (
        controller.is_response_cacheable(request=httpx_request, response=response)
        is False
    )


def test_is_response_cacheable_with_request_no_store_header():
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "no-store"}
    )
    response = httpx.Response(200)
    controller = httpx_cache.CacheControl()
    assert controller.is_response_cacheable(request=request, response=response) is False


def test_is_response_cacheable_with_request_no_store_header_and_always_cache_is_True():
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "no-store"}
    )
    response = httpx.Response(200)
    controller = httpx_cache.CacheControl(always_cache=True)
    assert controller.is_response_cacheable(request=request, response=response) is True


def test_is_response_fresh(httpx_request, httpx_response):
    controller = httpx_cache.CacheControl()
    assert (
        controller.is_response_fresh(request=httpx_request, response=httpx_response)
        is True
    )


@pytest.mark.parametrize("code", _PERMANENT_REDIRECT_STATUSES)
def test_is_response_fresh_with_permanent_redirect(httpx_request, code):
    controller = httpx_cache.CacheControl()
    response = httpx.Response(code)
    assert (
        controller.is_response_fresh(request=httpx_request, response=response) is True
    )


def test_is_response_fresh_with_expires_header_no_date():
    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(200, headers={"expires": "Tue, 15 Nov 1994 12:45:26 GMT"})
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is False


def test_is_response_fresh_with_invalid_expires_header():
    date = datetime.now(tz=timezone.utc)
    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
            "expires": "lala",
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is False


def test_is_response_fresh_with_expires_header_fresh():
    date = datetime.now(tz=timezone.utc)
    expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
            "expires": format_datetime(expires, usegmt=True),
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is True


def test_is_response_fresh_with_expires_header_not_fresh():
    expires = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    date = expires - timedelta(minutes=5)
    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
            "expires": format_datetime(expires, usegmt=True),
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is False


def test_is_response_fresh_with_max_age_response_header_fresh():
    expires = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    date = expires - timedelta(minutes=5)
    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
            "expires": format_datetime(expires, usegmt=True),
            "cache-control": "max-age=900",
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is True


def test_is_response_fresh_with_max_age_response_header_not_fresh():
    date = datetime.now(tz=timezone.utc) - timedelta(days=1)
    expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
            "expires": format_datetime(expires, usegmt=True),
            "cache-control": "max-age=900",
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is False


def test_is_response_fresh_with_max_age_response_header_no_date():
    request = httpx.Request("GET", "http://testurl")
    response = httpx.Response(
        200,
        headers={"cache-control": "max-age=900"},
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is False


def test_is_response_fresh_with_max_age_request_header_fresh():
    date = datetime.now(tz=timezone.utc) - timedelta(days=1)
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "max-age=100000"}
    )
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
            "cache-control": "max-age=900",
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is True


def test_is_response_fresh_with_max_age_request_header_not_fresh():
    date = datetime.now(tz=timezone.utc) - timedelta(days=1)
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "max-age=900"}
    )
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
            "cache-control": "max-age=100000",
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is False


def test_is_response_fresh_with_max_age_request_header_fresh_with_min_fresh_header():
    date = datetime.now(tz=timezone.utc) - timedelta(minutes=51)
    request = httpx.Request(
        "GET", "http://testurl", headers={"cache-control": "max-age=3600,min-fresh=600"}
    )
    response = httpx.Response(
        200,
        headers={
            "date": format_datetime(date, usegmt=True),
        },
    )
    controller = CacheControl()
    assert controller.is_response_fresh(request=request, response=response) is False
