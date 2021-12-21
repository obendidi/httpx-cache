from pathlib import Path

import anyio
import httpx
import mock
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio

testcases = [
    httpx_cache.DictSerializer(),
    httpx_cache.StringJsonSerializer(),
    httpx_cache.BytesJsonSerializer(),
    httpx_cache.MsgPackSerializer(),
]
testids = [
    "DictSerializer",
    "StringJsonSerializer",
    "BytesJsonSerializer",
    "MsgPackSerializer",
]


def test_file_cache_init_bad_serializer():
    with pytest.raises(TypeError):
        httpx_cache.FileCache(serializer="Serial")


@mock.patch.object(Path, "mkdir")
def test_file_cache_init_bad_default_cache_dir(mock_mkdir: mock.MagicMock):
    cache = httpx_cache.FileCache()
    default_cache_dir = Path.home() / ".cache/httpx-cache"
    assert cache.cache_dir == default_cache_dir
    mock_mkdir.assert_called_once_with(exist_ok=True)


@mock.patch.object(Path, "mkdir")
def test_file_cache_init_bad_custom_path_cache_dir(mock_mkdir: mock.MagicMock):
    cache_dir = Path("./some-path")
    cache = httpx_cache.FileCache(cache_dir=cache_dir)
    assert cache.cache_dir == cache_dir
    mock_mkdir.assert_called_once_with(exist_ok=True)


@mock.patch.object(Path, "mkdir")
def test_file_cache_init_bad_custom_str_cache_dir(mock_mkdir: mock.MagicMock):
    cache_dir = "./some-path"
    cache = httpx_cache.FileCache(cache_dir=cache_dir)
    assert isinstance(cache.cache_dir, Path)
    assert cache.cache_dir == Path(cache_dir)
    mock_mkdir.assert_called_once_with(exist_ok=True)


@pytest.mark.parametrize("serializer", testcases, ids=testids)
@mock.patch.object(Path, "mkdir")
@mock.patch.object(Path, "is_file", return_value=False)
def test_file_cache_get_not_found(
    mock_is_file: mock.MagicMock,
    mock_mkdir: mock.MagicMock,
    serializer: httpx_cache.BaseSerializer,
    httpx_request: httpx.Request,
):
    cache = httpx_cache.FileCache(serializer=serializer)
    cached = cache.get(httpx_request)
    assert cached is None
    mock_mkdir.assert_called_once_with(exist_ok=True)
    mock_is_file.assert_called_once_with()


@pytest.mark.parametrize("serializer", testcases, ids=testids)
@mock.patch.object(Path, "mkdir")
@mock.patch.object(anyio.Path, "is_file", return_value=False)
async def test_file_cache_aget_not_found(
    mock_is_file: mock.AsyncMock,
    mock_mkdir: mock.MagicMock,
    serializer: httpx_cache.BaseSerializer,
    httpx_request: httpx.Request,
):
    cache = httpx_cache.FileCache(serializer=serializer)
    cached = await cache.aget(httpx_request)
    assert cached is None
    mock_mkdir.assert_called_once_with(exist_ok=True)
    mock_is_file.assert_awaited_once_with()
