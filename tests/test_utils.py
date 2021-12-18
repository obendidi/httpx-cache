import json
import uuid

import httpx
import pytest

import httpx_cache
from httpx_cache.utils import CustomJSONEncoder, parse_cache_control_headers

pytestmark = pytest.mark.anyio


def test_custom_json_encoder():
    data = {"key1": "str", "key2": 42, "key3": b"bytes"}
    dumped = json.dumps(data, cls=CustomJSONEncoder)
    assert dumped == '{"key1": "str", "key2": 42, "key3": "bytes"}'


def test_parse_cache_control_headers_no_cache():
    headers = httpx.Headers([("Cache-Control", "no-cache")])
    assert parse_cache_control_headers(headers) == {"no-cache": None}


def test_parse_cache_control_headers_no_store():
    headers = httpx.Headers(
        [("Cache-Control", "no-store"), ("Content-Type", "text/plain")]
    )
    assert parse_cache_control_headers(headers) == {"no-store": None}


def test_parse_cache_control_headers_max_age_666():
    headers = httpx.Headers(
        [("Cache-Control", "max-age=666"), ("Content-Type", "text/plain")]
    )
    assert parse_cache_control_headers(headers) == {"max-age": 666}


def test_parse_cache_control_headers_max_age_0():
    headers = httpx.Headers(
        [("Cache-Control", "max-age=0"), ("Content-Type", "text/plain")]
    )
    assert parse_cache_control_headers(headers) == {"max-age": 0}


def test_parse_cache_control_headers_content_type_text_plain():
    headers = httpx.Headers([("Content-Type", "text/plain")])
    assert parse_cache_control_headers(headers) == {}


def test_parse_cache_control_headers_content_type_application_json():
    headers = httpx.Headers([("Content-Type", "application/json")])
    assert parse_cache_control_headers(headers) == {}


def test_parse_cache_control_headerse_max_age_invalid():
    headers = httpx.Headers(
        [
            ("Cache-Control", "max-stale=aaa"),
            ("Cache-Control", "max-age=aaa"),
            ("Cache-Control", "max-age"),
        ]
    )
    assert parse_cache_control_headers(headers) == {"max-stale": None}


def test_parse_cache_control_headerse_no_transform():
    headers = httpx.Headers(
        [("Cache-Control", "no-transform"), ("Content-Type", "text/plain")]
    )
    assert parse_cache_control_headers(headers) == {"no-transform": None}


def test_parse_cache_control_headerse_max_stale():
    headers = httpx.Headers(
        [
            ("Cache-Control", "no-cache"),
            ("Cache-Control", "max-age=666"),
            ("Cache-Control", "max-stale=44"),
        ]
    )
    assert parse_cache_control_headers(headers) == {
        "max-age": 666,
        "max-stale": None,
        "no-cache": None,
    }


def test_parse_cache_control_headerse_unknown():
    headers = httpx.Headers(
        [
            ("Cache-Control", "no-transform"),
            ("Cache-Control", "max-age=666"),
            ("Cache-Control", "unknown"),
        ]
    )
    assert parse_cache_control_headers(headers) == {
        "max-age": 666,
        "no-transform": None,
    }


def test_parse_cache_control_headerse_with_comma():
    headers = httpx.Headers(
        [
            ("Cache-Control", "max-age=666,proxy-revalidate,min-fresh=09"),
            ("Content-Type", "text/plain"),
        ]
    )
    assert parse_cache_control_headers(headers) == {
        "max-age": 666,
        "min-fresh": 9,
        "proxy-revalidate": None,
    }


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
