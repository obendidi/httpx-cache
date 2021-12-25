import uuid
from pathlib import Path

import httpx
import pytest

import httpx_cache
from httpx_cache.utils import (
    get_cache_filepath,
    get_cache_key,
    parse_cache_control_headers,
    parse_headers_date,
)

pytestmark = pytest.mark.anyio


def test_parse_headers_date_none():
    parsed = parse_headers_date(None)
    assert parsed is None


def test_parse_headers_date():
    parsed = parse_headers_date("Tue, 15 Nov 1994 12:45:26 GMT")
    assert parsed.isoformat() == "1994-11-15T12:45:26+00:00"


@pytest.mark.parametrize("invalid_date", ["some-str-invalid-date", "Tue", 15])
def test_parse_headers_date_value_error(invalid_date):
    parsed = parse_headers_date(invalid_date)
    assert parsed is None


def test_get_cache_key(httpx_request):
    assert get_cache_key(httpx_request) == "http://httpx-cache"


def test_get_cache_filepath(httpx_request):
    cache_dir = Path("./some-relative-dir")
    assert get_cache_filepath(cache_dir, httpx_request) == Path(
        "some-relative-dir/5092db9fa0e037de33b24831c064396e00d79173978beef0153a0027"
    )


def test_parse_cache_control_headers_no_cc():
    headers = httpx.Headers([("content-type", "application/json")])
    cc = parse_cache_control_headers(headers)
    assert cc == {}


def test_parse_cache_control_headers_simple_cc():
    headers = httpx.Headers([("cache-control", "no-store")])
    cc = parse_cache_control_headers(headers)
    assert cc == {"no-store": None}


def test_parse_cache_control_headers_simple_cc_with_comma():
    headers = httpx.Headers([("cache-control", "no-store,no-transform")])
    cc = parse_cache_control_headers(headers)
    assert cc == {"no-store": None, "no-transform": None}


def test_parse_cache_control_headers_simple_cc_with_digit_value():
    headers = httpx.Headers([("cache-control", "no-store,max-age=679900")])
    cc = parse_cache_control_headers(headers)
    assert cc == {"no-store": None, "max-age": 679900}


def test_parse_cache_control_headers_simple_cc_with_non_digit_value():
    headers = httpx.Headers([("cache-control", "no-store,max-age=lol")])
    cc = parse_cache_control_headers(headers)
    assert cc == {"no-store": None, "max-age": None}


def test_response_stream_wrapper(streaming_body):
    response = httpx.Response(200, content=streaming_body)
    store = {}
    key = str(uuid.uuid4())

    def _callback(buffer: bytes) -> None:
        store[key] = buffer

    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=_callback
    )
    content = response.read()
    assert content == store[key]


async def test_response_async_stream_wrapper(async_streaming_body):
    response = httpx.Response(200, content=async_streaming_body)
    store = {}
    key = str(uuid.uuid4())

    async def _callback(buffer: bytes) -> None:
        store[key] = buffer

    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=_callback
    )
    content = await response.aread()
    assert content == store[key]
