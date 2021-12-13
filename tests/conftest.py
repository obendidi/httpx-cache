import typing as tp

import httpx
import pytest
from pytest_cases import case, fixture, parametrize_with_cases

from httpx_cache.serializer import BaseSerializer


class StreamingBody:
    def __iter__(self):
        yield b"Hello, "
        yield b"world!"


def streaming_body():
    yield b"Hello, "
    yield b"world!"


async def async_streaming_body():
    yield b"Hello, "
    yield b"world!"


class HeadersCases:
    def case_cache_control_no_cache(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers([("Cache-Control", "no-cache")])
        cache_control = {"no-cache": None}
        return headers, cache_control, False

    def case_cache_control_no_store(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [("Cache-Control", "no-store"), ("Content-Type", "text/plain")]
        )
        cache_control = {"no-store": None}
        return headers, cache_control, False

    def case_cache_control_max_age_666(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [("Cache-Control", "max-age=666"), ("Content-Type", "text/plain")]
        )
        cache_control = {"max-age": 666}
        return headers, cache_control, True

    def case_cache_control_max_age_0(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [("Cache-Control", "max-age=0"), ("Content-Type", "text/plain")]
        )
        cache_control = {"max-age": 0}
        return headers, cache_control, False

    def case_content_type_text_plain(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        return httpx.Headers([("Content-Type", "text/plain")]), {}, True

    def case_content_type_application_json(
        self,
    ) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        return httpx.Headers([("Content-Type", "application/json")]), {}, True

    def case_cache_controle_max_age_invalid(
        self,
    ) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [
                ("Cache-Control", "max-stale=aaa"),
                ("Cache-Control", "max-age=aaa"),
                ("Cache-Control", "max-age"),
            ]
        )
        return headers, {"max-stale": None}, True

    def case_cache_controle_no_transform(
        self,
    ) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [("Cache-Control", "no-transform"), ("Content-Type", "text/plain")]
        )
        return headers, {"no-transform": None}, True

    def case_cache_controle_max_stale(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [
                ("Cache-Control", "no-cache"),
                ("Cache-Control", "max-age=666"),
                ("Cache-Control", "max-stale=44"),
            ]
        )
        return headers, {"max-age": 666, "max-stale": None, "no-cache": None}, False

    def case_cache_controle_unknown(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [
                ("Cache-Control", "no-transform"),
                ("Cache-Control", "max-age=666"),
                ("Cache-Control", "unknown"),
            ]
        )
        return headers, {"max-age": 666, "no-transform": None}, True

    def case_cache_controle_with_comma(self) -> tp.Tuple[httpx.Headers, tp.Dict, bool]:
        headers = httpx.Headers(
            [
                ("Cache-Control", "max-age=666,proxy-revalidate,min-fresh=09"),
                ("Content-Type", "text/plain"),
            ]
        )
        return headers, {"max-age": 666, "min-fresh": 9, "proxy-revalidate": None}, True


@fixture
@parametrize_with_cases("headers,cache_control,cacheable", cases=HeadersCases)
def httpx_headers_cache_control(
    headers: httpx.Headers, cache_control: tp.Dict, cacheable: bool
) -> tp.Tuple[httpx.Headers, tp.Dict]:
    return headers, cache_control


@fixture
@parametrize_with_cases("headers,cache_control,cacheable", cases=HeadersCases)
def httpx_headers_cacheable(
    headers: httpx.Headers, cache_control: tp.Dict, cacheable: bool
) -> tp.Tuple[httpx.Headers, bool]:
    return headers, cacheable


@fixture
@parametrize_with_cases("headers,cache_control,cacheable", cases=HeadersCases)
def httpx_headers(
    headers: httpx.Headers, cache_control: tp.Dict, cacheable: bool
) -> httpx.Headers:
    return headers


class ResponseCases:
    """httpx Response test cases:

    Mostly copied from:
    https://github.com/encode/httpx/blob/1.0.0.beta0/tests/models/test_responses.py

    """

    @case(tags=["sync", "async"])
    def case_response_content(self) -> httpx.Response:
        return httpx.Response(200, content=b"Hello, world!")

    @case(tags=["sync", "async"])
    def case_response_text(self) -> httpx.Response:
        return httpx.Response(200, text="Hello, world!")

    @case(tags=["sync", "async"])
    def case_response_html(self) -> httpx.Response:
        return httpx.Response(200, html="<html><body>Hello, world!</html></body>")

    @case(tags=["sync", "async"])
    def case_response_json(self) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    @case(tags=["sync", "async"])
    def case_response_content_type_encoding(self) -> httpx.Response:
        headers = {"Content-Type": "text-plain; charset=latin-1"}
        content = "Latin 1: ÿ".encode("latin-1")
        return httpx.Response(200, content=content, headers=headers)

    @case(tags=["sync", "async"])
    def case_response_autodetect_encoding(self) -> httpx.Response:
        content = "おはようございます。".encode("utf-8")
        return httpx.Response(200, content=content)

    @case(tags=["sync", "async"])
    def case_response_fallback_to_autodetect(self) -> httpx.Response:
        headers = {"Content-Type": "text-plain; charset=invalid-codec-name"}
        content = "おはようございます。".encode("utf-8")
        return httpx.Response(200, content=content, headers=headers)

    @case(tags=["sync", "async"])
    def case_response_no_charset_with_ascii_content(self) -> httpx.Response:
        content = b"Hello, world!"
        headers = {"Content-Type": "text/plain"}
        return httpx.Response(200, content=content, headers=headers)

    @case(tags=["sync", "async"])
    def case_response_no_charset_with_utf8_content(self) -> httpx.Response:
        content = "Unicode Snowman: ☃".encode("utf-8")
        headers = {"Content-Type": "text/plain"}
        return httpx.Response(200, content=content, headers=headers)

    @case(tags=["sync", "async"])
    def case_response_no_charset_with_iso_8859_1_content(self) -> httpx.Response:
        content = "Accented: Österreich abcdefghijklmnopqrstuzwxyz".encode("iso-8859-1")
        headers = {"Content-Type": "text/plain"}
        return httpx.Response(200, content=content, headers=headers)

    @case(tags=["sync", "async"])
    def case_response_no_charset_with_cp_1252_content(self) -> httpx.Response:
        content = "Euro Currency: € abcdefghijklmnopqrstuzwxyz".encode("cp1252")
        headers = {"Content-Type": "text/plain"}
        return httpx.Response(200, content=content, headers=headers)

    @case(tags=["sync", "async"])
    def case_response_non_text_encoding(self) -> httpx.Response:
        headers = {"Content-Type": "image/png"}
        return httpx.Response(200, content=b"xyz", headers=headers)

    @case(tags=["sync", "async"])
    def case_response_set_explicit_encoding(self) -> httpx.Response:
        # Deliberately incorrect charset
        headers = {"Content-Type": "text-plain; charset=utf-8"}
        response = httpx.Response(
            200, content="Latin 1: ÿ".encode("latin-1"), headers=headers
        )
        response.encoding = "latin-1"
        return response

    @case(tags=["sync", "async"])
    def case_response_force_encoding(self) -> httpx.Response:
        response = httpx.Response(200, content="Snowman: ☃".encode("utf-8"))
        response.encoding = "iso-8859-1"
        return response

    @case(tags=["sync", "async"])
    def case_empty_read(self) -> httpx.Response:
        return httpx.Response(200)

    # TODO: check why it does not work with `test_cache_control_transport`
    @case(tags=["stream_sync"])
    def case_iter_raw(self) -> httpx.Response:
        return httpx.Response(200, content=streaming_body())

    @case(tags=["stream_sync", "sync"])
    def case_iter_raw_on_iterable(self) -> httpx.Response:
        return httpx.Response(200, content=StreamingBody())

    # TODO: check why it does not work with `test_async_cache_control_transport`
    @case(tags=["async_stream"])
    def case_aiter_raw(self) -> httpx.Response:
        return httpx.Response(200, content=async_streaming_body())


@fixture
@parametrize_with_cases("response", cases=ResponseCases)
def httpx_response(response: httpx.Response) -> httpx.Response:
    return response


@fixture
@parametrize_with_cases("response", cases=ResponseCases, has_tag="sync")
def httpx_sync_response(response: httpx.Response) -> httpx.Response:
    return response


@fixture
@parametrize_with_cases("response", cases=ResponseCases, has_tag="async")
def httpx_async_response(response: httpx.Response) -> httpx.Response:
    return response


@fixture
@parametrize_with_cases("response", cases=ResponseCases, has_tag="stream_sync")
def httpx_stream_response(response: httpx.Response) -> httpx.Response:
    return response


@fixture
@parametrize_with_cases("response", cases=ResponseCases, has_tag="async_stream")
def httpx_async_stream_response(response: httpx.Response) -> httpx.Response:
    return response


class DummySerializer(BaseSerializer):
    def dumps(self, *, response: httpx.Response, content: bytes) -> httpx.Response:
        return response

    def loads(self, *, data: httpx.Response, request: httpx.Request) -> httpx.Response:
        return data


@pytest.fixture
def dummy_serializer():
    return DummySerializer()
