import typing as tp

import httpx
import pytest
from pytest_cases import fixture, parametrize_with_cases


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


class DummySerializer:
    def dumps(
        self, *, response: httpx.Response, content: tp.Optional[bytes] = None
    ) -> httpx.Response:
        return response

    def loads(
        self, *, data: httpx.Response, request: tp.Optional[httpx.Request] = None
    ) -> httpx.Response:
        return data


@pytest.fixture(scope="session")
def dummy_serializer():
    return DummySerializer()


@pytest.fixture
def streaming_body():
    def _streaming_body():
        yield b"Hello, "
        yield b"world!"

    return _streaming_body()


@pytest.fixture
async def async_streaming_body():
    async def _async_streaming_body():
        yield b"Hello, "
        yield b"world!"

    return _async_streaming_body()
