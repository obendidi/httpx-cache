import re
import shutil
from pathlib import Path

import httpx
import pytest
from pytest_cases import case, fixture, fixture_union, parametrize_with_cases

import httpx_cache
from httpx_cache.cache.redis import RedisCache


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory):
    name = re.sub(r"[\W]", "_", request.node.name)
    new_tmp_path = tmp_path_factory.mktemp(name)
    yield new_tmp_path
    shutil.rmtree(str(new_tmp_path))


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


class _MockRedis:
    def __init__(self):
        self._data = {}

    def get(self, key: str) -> bytes:
        return self._data.get(key)

    def set(self, key: str, value: bytes):
        self._data[key] = value

    def setex(self, key: str, time_: int, value: bytes):
        # TODO: time_ is ignored
        self.set(key, value)

    def delete(self, key: str):
        self._data.pop(key, None)

    def close(self):
        pass


class _MockAsyncRedis:
    def __init__(self):
        self._data = {}

    async def get(self, key: str) -> bytes:
        return self._data.get(key)

    async def set(self, key: str, value: bytes):
        self._data[key] = value

    async def setex(self, key: str, time_: int, value: bytes):
        # TODO: time_ is ignored
        self.set(key, value)

    async def delete(self, key: str):
        self._data.pop(key, None)

    async def close(self):
        pass


@fixture(scope="function")
@parametrize_with_cases("serializer", cases=SerializerCases, has_tag="bytes")
def redis_cache(serializer: httpx_cache.BaseSerializer) -> RedisCache:
    redis = _MockRedis()
    aredis = _MockAsyncRedis()
    return RedisCache(serializer=serializer, redis=redis, aredis=aredis)


cache = fixture_union("cache", [dict_cache, file_cache, redis_cache], scope="function")
