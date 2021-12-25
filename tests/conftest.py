import re
from pathlib import Path

import httpx
import pytest
from pytest_cases import case, fixture, fixture_union, parametrize_with_cases

import httpx_cache


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory):
    name = re.sub(r"[\W]", "_", request.node.name)
    return tmp_path_factory.mktemp(name)


@pytest.fixture(scope="session")
def httpx_request():
    return httpx.Request("GET", "http://httpx-cache")


@pytest.fixture(scope="session")
def httpx_response():
    return httpx.Response(200, content=b"httpx-cache-is-awesome")


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


class SerializerCases:
    @case(tags=["dict"])
    def case_dict_serializer(self) -> httpx_cache.BaseSerializer:
        return httpx_cache.DictSerializer()

    @case(tags=["str"])
    def case_string_json_serializer(self) -> httpx_cache.BaseSerializer:
        return httpx_cache.StringJsonSerializer()

    @case(tags=["bytes"])
    def case_bytes_json_serializer(self) -> httpx_cache.BaseSerializer:
        return httpx_cache.BytesJsonSerializer()

    @case(tags=["bytes"])
    def case_msgpack_serializer(self) -> httpx_cache.BaseSerializer:
        return httpx_cache.MsgPackSerializer()


@fixture(scope="function")
@parametrize_with_cases("serializer", cases=SerializerCases)
def serializer(serializer: httpx_cache.BaseSerializer) -> httpx_cache.BaseSerializer:
    return serializer


@fixture(scope="function")
@parametrize_with_cases("serializer", cases=SerializerCases)
def dict_cache(serializer: httpx_cache.BaseSerializer) -> httpx_cache.DictCache:
    return httpx_cache.DictCache(serializer=serializer)


@fixture(scope="function")
@parametrize_with_cases("serializer", cases=SerializerCases, has_tag="bytes")
def file_cache(
    serializer: httpx_cache.BaseSerializer, tmp_path: Path
) -> httpx_cache.FileCache:
    return httpx_cache.FileCache(serializer=serializer, cache_dir=tmp_path)


cache = fixture_union("cache", [dict_cache, file_cache], scope="function")
