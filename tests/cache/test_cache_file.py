from pathlib import Path

import anyio
import httpx
import mock
import pytest

import httpx_cache

pytestmark = pytest.mark.anyio

testcases = [
    httpx_cache.BytesJsonSerializer(),
    httpx_cache.MsgPackSerializer(),
]
testids = [
    "BytesJsonSerializer",
    "MsgPackSerializer",
]


def test_file_cache_init_bad_serializer():
    with pytest.raises(TypeError):
        httpx_cache.FileCache(serializer="Serial")


@mock.patch.object(Path, "mkdir")
def test_file_cache_init_default_cache_dir(mock_mkdir: mock.MagicMock):
    cache = httpx_cache.FileCache()
    default_cache_dir = Path.home() / ".cache/httpx-cache"
    assert cache.cache_dir == default_cache_dir
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


@mock.patch.object(Path, "mkdir")
def test_file_cache_init_bad_custom_path_cache_dir(mock_mkdir: mock.MagicMock):
    cache_dir = Path("./some-path")
    cache = httpx_cache.FileCache(cache_dir=cache_dir)
    assert cache.cache_dir == cache_dir
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


@mock.patch.object(Path, "mkdir")
def test_file_cache_init_bad_custom_str_cache_dir(mock_mkdir: mock.MagicMock):
    cache_dir = "./some-path"
    cache = httpx_cache.FileCache(cache_dir=cache_dir)
    assert isinstance(cache.cache_dir, Path)
    assert cache.cache_dir == Path(cache_dir)
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


@mock.patch.object(Path, "mkdir", new=lambda *args, **kwargs: None)
@mock.patch.object(Path, "is_file", return_value=False)
def test_file_cache_get_not_found(
    mock_is_file: mock.MagicMock,
    file_cache: httpx_cache.FileCache,
    httpx_request: httpx.Request,
):
    cached = file_cache.get(httpx_request)
    mock_is_file.assert_called_once_with()
    assert cached is None


@mock.patch.object(Path, "mkdir", new=lambda *args, **kwargs: None)
@mock.patch.object(anyio.Path, "is_file", return_value=False)
async def test_file_cache_aget_not_found(
    mock_is_file: mock.AsyncMock,
    file_cache: httpx_cache.FileCache,
    httpx_request: httpx.Request,
):
    cached = await file_cache.aget(httpx_request)
    mock_is_file.assert_awaited_once_with()
    assert cached is None


def test_file_cache_set_get_delete(
    file_cache: httpx_cache.FileCache,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    # make sure cache_dir is new and empty
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    # check again that cache is empty
    cached_response = file_cache.get(httpx_request)
    assert cached_response is None

    # cache a request
    file_cache.set(request=httpx_request, response=httpx_response, content=None)
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 1

    # get the cached response
    cached_response = file_cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    file_cache.delete(httpx_request)
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    # delete with cached file not found
    # should do nothing (not raise an error)
    file_cache.delete(httpx_request)

    file_cache.close()


async def test_file_cache_aset_aget_adelete(
    file_cache: httpx_cache.FileCache,
    httpx_request: httpx.Request,
    httpx_response: httpx.Response,
):
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    # cache a request
    await file_cache.aset(request=httpx_request, response=httpx_response, content=None)

    # make sure we have one request inside
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 1

    # get the cached response
    cached_response = await file_cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.content == httpx_response.content
    assert cached_response.headers == httpx_response.headers

    # delete the cached response
    await file_cache.adelete(httpx_request)
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    await file_cache.aclose()


def test_file_cache_set_get_delete_with_streaming_body(
    file_cache: httpx_cache.FileCache,
    httpx_request: httpx.Request,
    streaming_body,
):
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    httpx_response = httpx.Response(200, content=streaming_body)

    def callback(content: bytes) -> None:
        # set it in cache
        file_cache.set(request=httpx_request, response=httpx_response, content=content)

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    httpx_response.read()

    # make sure we have one request inside
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 1

    # get the cached response
    cached_response = file_cache.get(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert cached_response.read() == httpx_response.content

    # delete the cached response
    file_cache.delete(httpx_request)
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    file_cache.close()


async def test_file_cache_aset_aget_adelete_with_async_streaming_body(
    file_cache: httpx_cache.FileCache,
    httpx_request: httpx.Request,
    async_streaming_body,
):
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    httpx_response = httpx.Response(200, content=async_streaming_body)

    async def callback(content: bytes) -> None:
        # set it in cache
        await file_cache.aset(
            request=httpx_request, response=httpx_response, content=content
        )

    # wrap the response stream
    httpx_response.stream = httpx_cache.ByteStreamWrapper(
        stream=httpx_response.stream, callback=callback  # type: ignore
    )

    # when read the response, it will be cached using the callback
    await httpx_response.aread()

    # make sure we have one request inside
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 1

    # get the cached response
    cached_response = await file_cache.aget(httpx_request)
    assert cached_response is not None
    assert cached_response.status_code == httpx_response.status_code
    assert cached_response.headers == httpx_response.headers
    with pytest.raises(httpx.ResponseNotRead):
        cached_response.content
    assert await cached_response.aread() == httpx_response.content

    # delete the cached response
    await file_cache.adelete(httpx_request)
    assert len(list(file_cache.cache_dir.glob("**/*"))) == 0

    await file_cache.aclose()
