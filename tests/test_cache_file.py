import os
from unittest import mock

from httpx_cache.cache.file import AsyncFileCache, FileCache
from httpx_cache.serializer.base import BaseSerializer


@mock.patch("os.makedirs")
def test_file_cache_init_default(
    makedirs_mock: mock.MagicMock, dummy_serializer: BaseSerializer
):

    default_cache_dir = os.path.join(os.path.expanduser("~"), ".cache/httpx-cache")
    cache = FileCache(serializer=dummy_serializer)
    assert cache.cache_dir == default_cache_dir
    makedirs_mock.assert_called_once_with(default_cache_dir, exist_ok=True)


@mock.patch("os.makedirs")
def test_async_file_cache_init_default(
    makedirs_mock: mock.MagicMock, dummy_serializer: BaseSerializer
):

    default_cache_dir = os.path.join(os.path.expanduser("~"), ".cache/httpx-cache")
    cache = AsyncFileCache(serializer=dummy_serializer)
    assert cache.cache_dir == default_cache_dir
    makedirs_mock.assert_called_once_with(default_cache_dir, exist_ok=True)


@mock.patch("os.makedirs")
def test_file_cache_init_custom_cache_dir(
    makedirs_mock: mock.MagicMock, dummy_serializer: BaseSerializer
):

    cache_dir = "my_custom_cache_dir"
    cache = FileCache(serializer=dummy_serializer, cache_dir=cache_dir)
    assert cache.cache_dir == os.path.abspath(cache_dir)
    makedirs_mock.assert_called_once_with(cache_dir, exist_ok=True)


@mock.patch("os.makedirs")
def test_async_file_cache_init_custom_cache_dir(
    makedirs_mock: mock.MagicMock, dummy_serializer: BaseSerializer
):

    cache_dir = "my_custom_cache_dir"
    cache = AsyncFileCache(serializer=dummy_serializer, cache_dir=cache_dir)
    assert cache.cache_dir == os.path.abspath(cache_dir)
    makedirs_mock.assert_called_once_with(cache_dir, exist_ok=True)
