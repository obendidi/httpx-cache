import os
import uuid
from unittest import mock

import anyio
import httpx
import pytest

import httpx_cache
from httpx_cache.cache.file import (
    cache_dir_factory,
    create_cache_dir,
    gen_cache_filepath,
)

pytestmark = pytest.mark.anyio

TEST_REQUEST = httpx.Request("GET", "http://testurl")
ENCODED_REQ_URL = "e60261b34e117e33a1e985ac506a7a9076f92e7033082750ce20c80a"
TEST_RESPONSE = httpx.Response(status_code=200, content=str(uuid.uuid4()).encode())


@pytest.fixture(scope="module")
def null_serializer():
    return httpx_cache.NullSerializer()


@pytest.fixture(scope="module")
def file_cache(
    cache_dir: str, null_serializer: httpx_cache.BaseSerializer
) -> httpx_cache.FileCache:
    return httpx_cache.FileCache(cache_dir=cache_dir, serializer=null_serializer)


@pytest.fixture(scope="module")
def async_file_cache(
    cache_dir: str, null_serializer: httpx_cache.BaseSerializer
) -> httpx_cache.AsyncFileCache:
    return httpx_cache.AsyncFileCache(cache_dir=cache_dir, serializer=null_serializer)


@mock.patch("os.makedirs")
def test_cache_dir_factory(mock_os_makedirs: mock.MagicMock):
    cache_dir = "my-custom-dir"
    abs_cache_dir = create_cache_dir(cache_dir)
    assert os.path.isabs(abs_cache_dir)
    mock_os_makedirs.assert_called_with(cache_dir, exist_ok=True)


@mock.patch("os.makedirs")
def test_create_cache_dir(mock_os_makedirs: mock.MagicMock):
    cache = httpx_cache.FileCache()
    async_cache = httpx_cache.AsyncFileCache()

    default = cache_dir_factory()

    assert cache.cache_dir == async_cache.cache_dir == default
    mock_os_makedirs.assert_called_with(default, exist_ok=True)


def test_gen_cache_filepath():
    cache_dir = "some_dir"
    filepath = gen_cache_filepath(cache_dir, TEST_REQUEST)
    assert os.path.join(cache_dir, ENCODED_REQ_URL) == filepath


@mock.patch("os.path.isfile", return_value=False)
def test_file_cache_get_not_found(
    mock_os_isfile: mock.MagicMock, file_cache: httpx_cache.FileCache
):
    cached = file_cache.get(TEST_REQUEST)
    assert cached is None
    filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
    mock_os_isfile.assert_called_once_with(filepath)


@mock.patch("os.path.isfile", return_value=True)
def test_file_cache_get(
    mock_os_isfile: mock.MagicMock, file_cache: httpx_cache.FileCache
):

    read_data = "some-data-cached"
    with mock.patch(
        "httpx_cache.cache.file.open", mock.mock_open(read_data=read_data)
    ) as mocked_open:
        cached = file_cache.get(TEST_REQUEST)

    assert cached == read_data
    filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
    mocked_open.assert_called_once_with(filepath, "rb")
    mock_os_isfile.assert_called_once_with(filepath)


def test_file_cache_set(file_cache: httpx_cache.FileCache):
    with mock.patch("httpx_cache.cache.file.open", mock.mock_open()) as mocked_open:
        file_cache.set(request=TEST_REQUEST, response=b"some-random-response")  # type: ignore # noqa

    filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
    mocked_open.assert_called_once_with(filepath, "wb")
    handle = mocked_open()
    handle.write.assert_called_once_with(b"some-random-response")


@mock.patch("os.remove")
@mock.patch("os.path.isfile", return_value=True)
def test_file_cache_delete(
    mock_os_isfile: mock.MagicMock,
    mock_os_remove: mock.MagicMock,
    file_cache: httpx_cache.FileCache,
):
    file_cache.delete(TEST_REQUEST)
    filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
    mock_os_remove.assert_called_once_with(filepath)
    mock_os_isfile.assert_called_once_with(filepath)


@mock.patch("os.remove")
@mock.patch("os.path.isfile", return_value=False)
def test_file_cache_not_found(
    mock_os_isfile: mock.MagicMock,
    mock_os_remove: mock.MagicMock,
    file_cache: httpx_cache.FileCache,
):
    file_cache.delete(TEST_REQUEST)
    filepath = os.path.join(file_cache.cache_dir, ENCODED_REQ_URL)
    mock_os_isfile.assert_called_once_with(filepath)
    mock_os_remove.assert_not_called()


@mock.patch.object(anyio.Path, "is_file", return_value=False)
async def test_async_file_cache_get_not_found(
    mock_anyio_path_isfile: mock.MagicMock, async_file_cache: httpx_cache.AsyncFileCache
):
    cached = await async_file_cache.aget(TEST_REQUEST)
    assert cached is None
    mock_anyio_path_isfile.assert_awaited_once_with()


@mock.patch.object(anyio.Path, "is_file", return_value=True)
@mock.patch.object(anyio.Path, "read_bytes", return_value=b"some-data")
async def test_async_file_cache_get(
    mock_anyio_path_read_bytes: mock.AsyncMock,
    mock_anyio_path_isfile: mock.MagicMock,
    async_file_cache: httpx_cache.AsyncFileCache,
):
    cached = await async_file_cache.aget(TEST_REQUEST)
    assert cached == b"some-data"
    mock_anyio_path_read_bytes.assert_awaited_once_with()
    mock_anyio_path_isfile.assert_awaited_once_with()


@mock.patch.object(anyio.Path, "write_bytes")
async def test_sync_file_cache_set(
    mock_anyio_path_write_bytes: mock.AsyncMock,
    async_file_cache: httpx_cache.AsyncFileCache,
):
    response = httpx.Response(200, content=b"some-random-response")
    await async_file_cache.aset(
        request=TEST_REQUEST, response=response, content=response.content
    )
    mock_anyio_path_write_bytes.assert_awaited_once()


@mock.patch.object(anyio.Path, "unlink")
async def test_async_file_cache_delete(
    mock_anyio_path_unlink: mock.AsyncMock,
    async_file_cache: httpx_cache.AsyncFileCache,
):
    await async_file_cache.adelete(TEST_REQUEST)
    mock_anyio_path_unlink.assert_awaited_once_with(missing_ok=True)


@pytest.mark.parametrize(
    "serializer",
    [httpx_cache.BytesSerializer(), httpx_cache.MsgPackSerializer()],
    ids=["BytesSerializer", "MsgPackSerializer"],
)
def test_file_cache_with_serializer(
    cache_dir: str, serializer: httpx_cache.BaseSerializer
):

    # create an empty cache
    cache = httpx_cache.FileCache(serializer=serializer, cache_dir=cache_dir)

    # make sure we start with an empty cache
    assert len(os.listdir(cache_dir)) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=str(uuid.uuid4()).encode())

    # set it in cache
    cache.set(request=request, response=response)

    # the cache should have exactly one element
    assert len(os.listdir(cache_dir)) == 1

    # lets get the cached response
    cached_response = cache.get(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == cached_response.content

    # delete the cached response
    cache.delete(request)
    assert len(os.listdir(cache_dir)) == 0


@pytest.mark.parametrize(
    "serializer",
    [httpx_cache.BytesSerializer(), httpx_cache.MsgPackSerializer()],
    ids=["BytesSerializer", "MsgPackSerializer"],
)
async def test_async_file_cache_with_serializer(
    cache_dir: str, serializer: httpx_cache.BaseSerializer
):

    # create an empty cache
    cache = httpx_cache.AsyncFileCache(serializer=serializer, cache_dir=cache_dir)

    # make sure we start with an empty cache
    assert len(os.listdir(cache_dir)) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=str(uuid.uuid4()).encode())

    # set it in cache
    await cache.aset(request=request, response=response)

    # the cache should have exactly one element
    assert len(os.listdir(cache_dir)) == 1

    # lets get the cached response
    cached_response = await cache.aget(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == cached_response.content

    # delete the cached response
    await cache.adelete(request)
    assert len(os.listdir(cache_dir)) == 0


@pytest.mark.parametrize(
    "serializer",
    [httpx_cache.BytesSerializer(), httpx_cache.MsgPackSerializer()],
    ids=["BytesSerializer", "MsgPackSerializer"],
)
def test_file_cache_streaming_response_with_serializer(
    cache_dir: str, serializer: httpx_cache.BaseSerializer, streaming_body
):

    # create an empty cache
    cache = httpx_cache.FileCache(serializer=serializer, cache_dir=cache_dir)

    # make sure we start with an empty cache
    assert len(os.listdir(cache_dir)) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=streaming_body)

    def callback(content: bytes) -> None:
        # set it in cache
        cache.set(request=request, response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    response.read()

    # the cache should have exactly one element
    assert len(os.listdir(cache_dir)) == 1

    # lets get the cached response
    cached_response = cache.get(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == cached_response.read()

    # delete the cached response
    cache.delete(request)
    assert len(os.listdir(cache_dir)) == 0


@pytest.mark.parametrize(
    "serializer",
    [httpx_cache.BytesSerializer(), httpx_cache.MsgPackSerializer()],
    ids=["BytesSerializer", "MsgPackSerializer"],
)
async def test_async_file_cache_streaming_response_with_serializer(
    cache_dir: str, serializer: httpx_cache.BaseSerializer, async_streaming_body
):

    # create an empty cache
    cache = httpx_cache.AsyncFileCache(serializer=serializer, cache_dir=cache_dir)

    # make sure we start with an empty cache
    assert len(os.listdir(cache_dir)) == 0

    # create a request-response pair
    request = httpx.Request("GET", f"http://{uuid.uuid4()}")
    response = httpx.Response(200, content=async_streaming_body)

    async def callback(content: bytes) -> None:
        # set it in cache
        await cache.aset(request=request, response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    await response.aread()

    # the cache should have exactly one element
    assert len(os.listdir(cache_dir)) == 1

    # lets get the cached response
    cached_response = await cache.aget(request)
    assert cached_response is not None
    assert response.status_code == cached_response.status_code
    assert response.content == await cached_response.aread()

    # delete the cached response
    await cache.adelete(request)
    assert len(os.listdir(cache_dir)) == 0
