import os
import shutil
import uuid
from unittest import mock

import anyio
import httpx
import pytest

import httpx_cache
from httpx_cache.cache.file import cache_dir_factory, create_cache_dir

pytestmark = pytest.mark.anyio

TEST_REQUEST = httpx.Request("GET", "http://testurl")
ENCODED_REQ_URL = "e60261b34e117e33a1e985ac506a7a9076f92e7033082750ce20c80a"
TEST_RESPONSE = httpx.Response(status_code=200, content=str(uuid.uuid4()).encode())


@pytest.fixture(scope="session")
def file_cache_dir() -> str:
    cache_dir = os.path.join(os.path.dirname(__file__), "__cache__")
    yield cache_dir
    if os.path.isdir(cache_dir):
        shutil.rmtree(cache_dir)


@pytest.fixture
def mock_os_makedirs():
    with mock.patch("os.makedirs") as _fixture:
        yield _fixture


@pytest.fixture
def file_cache(
    file_cache_dir: str,
    mock_os_makedirs: mock.MagicMock,
    serializer: httpx_cache.IdentitySerializer,
) -> httpx_cache.FileCache:
    cache = httpx_cache.FileCache(cache_dir=file_cache_dir, serializer=serializer)  # type: ignore # noqa
    assert cache.cache_dir == file_cache_dir
    mock_os_makedirs.assert_called_with(file_cache_dir, exist_ok=True)
    return cache


@pytest.fixture
def async_file_cache(
    file_cache_dir: str,
    mock_os_makedirs: mock.MagicMock,
    serializer: httpx_cache.IdentitySerializer,
) -> httpx_cache.AsyncFileCache:
    cache = httpx_cache.AsyncFileCache(cache_dir=file_cache_dir, serializer=serializer)  # type: ignore # noqa
    assert cache.cache_dir == file_cache_dir
    mock_os_makedirs.assert_called_with(file_cache_dir, exist_ok=True)
    return cache


def test_cache_dir_factory(mock_os_makedirs: mock.MagicMock):
    cache_dir = "my-custom-dir"
    abs_cache_dir = create_cache_dir(cache_dir)
    assert os.path.isabs(abs_cache_dir)
    mock_os_makedirs.assert_called_with(cache_dir, exist_ok=True)


def test_create_cache_dir(mock_os_makedirs: mock.MagicMock):
    cache = httpx_cache.FileCache()
    async_cache = httpx_cache.AsyncFileCache()

    default = cache_dir_factory()

    assert cache.cache_dir == async_cache.cache_dir == default
    mock_os_makedirs.assert_called_with(default, exist_ok=True)


def test_file_cache_get_cache_filepath(mock_os_makedirs: mock.MagicMock):
    cache = httpx_cache.FileCache(cache_dir="sync-cache")
    async_cache = httpx_cache.AsyncFileCache(cache_dir="async-cache")
    filepath = cache.get_cache_filepath(TEST_REQUEST)
    async_filepath = async_cache.get_cache_filepath(TEST_REQUEST)
    assert os.path.join(cache.cache_dir, ENCODED_REQ_URL) == filepath
    assert os.path.join(async_cache.cache_dir, ENCODED_REQ_URL) == async_filepath


def test_file_cache_get_not_found(
    file_cache: httpx_cache.FileCache, mock_os_is_not_file: mock.MagicMock
):
    cached = file_cache.get(TEST_REQUEST)
    assert cached is None
    filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
    mock_os_is_not_file.assert_called_once_with(filepath)


def test_file_cache_get(
    file_cache: httpx_cache.FileCache, mock_os_is_file: mock.MagicMock
):

    read_data = {
        "status_code": 200,
        "headers": [(b"Content-Length", b"36")],
        "_request": None,
        "next_request": None,
        "history": [],
        "is_stream_consumed": True,
        "_num_bytes_downloaded": 0,
        "_content": TEST_RESPONSE.content,
    }
    with mock.patch(
        "httpx_cache.cache.file.open", mock.mock_open(read_data=read_data)
    ) as mocked_open:
        cached = file_cache.get(TEST_REQUEST)

    assert cached == b"some-data"
    filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
    mocked_open.assert_called_once_with(filepath, "rb")
    mock_os_is_file.assert_called_once_with(filepath)


# def test_file_cache_set(file_cache: FileCache):
#     response = httpx.Response(200, content=b"some-random-response")
#     with mock.patch("httpx_cache.cache.file.open", mock.mock_open()) as mocked_open:
#         file_cache.set(
#             request=TEST_REQUEST, response=response, content=response.content
#         )

#     filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
#     mocked_open.assert_called_once_with(filepath, "wb")
#     handle = mocked_open()
#     handle.write.assert_called_once_with(b"some-random-response")


# @mock.patch("os.remove")
# def test_file_cache_delete(
#     mock_os_remove: mock.MagicMock,
#     file_cache: FileCache,
#     mock_os_is_file: mock.MagicMock,
# ):
#     file_cache.delete(TEST_REQUEST)
#     filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
#     mock_os_remove.assert_called_once_with(filepath)
#     mock_os_is_file.assert_called_once_with(filepath)


# @mock.patch("os.remove")
# def test_file_cache_not_found(
#     mock_os_remove: mock.MagicMock,
#     file_cache: FileCache,
#     mock_os_is_not_file: mock.MagicMock,
# ):
#     file_cache.delete(TEST_REQUEST)
#     filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
#     mock_os_is_not_file.assert_called_once_with(filepath)
#     mock_os_remove.assert_not_called()


# async def test_async_file_cache_get_not_found(
#     async_file_cache: AsyncFileCache, mock_anyio_path_is_not_file: mock.AsyncMock
# ):
#     cached = await async_file_cache.aget(TEST_REQUEST)
#     assert cached is None
#     mock_anyio_path_is_not_file.assert_awaited_once_with()


# @mock.patch.object(anyio.Path, "read_bytes", return_value=b"some-data")
# async def test_async_file_cache_get(
#     mock_anyio_path_read_bytes: mock.AsyncMock,
#     async_file_cache: AsyncFileCache,
#     mock_anyio_path_is_file: mock.AsyncMock,
# ):
#     cached = await async_file_cache.aget(TEST_REQUEST)
#     assert cached == b"some-data"
#     mock_anyio_path_read_bytes.assert_awaited_once_with()
#     mock_anyio_path_is_file.assert_awaited_once_with()


# @mock.patch.object(anyio.Path, "write_bytes")
# async def test_sync_file_cache_set(
#     mock_anyio_path_write_bytes: mock.AsyncMock,
#     async_file_cache: AsyncFileCache,
# ):
#     response = httpx.Response(200, content=b"some-random-response")

#     await async_file_cache.aset(
#         request=TEST_REQUEST, response=response, content=response.content
#     )
#     mock_anyio_path_write_bytes.assert_awaited_once_with(response.content)


# @mock.patch.object(anyio.Path, "unlink")
# async def test_async_file_cache_delete(
#     mock_anyio_path_unlink: mock.AsyncMock,
#     async_file_cache: AsyncFileCache,
# ):
#     await async_file_cache.adelete(TEST_REQUEST)
#     mock_anyio_path_unlink.assert_awaited_once_with(missing_ok=True)
