import os
import shutil
import typing as tp

import pytest

TEST_CACHE_DIR = os.path.join(os.path.dirname(__file__), "__cache__")


@pytest.fixture(scope="session")
def cache_dir() -> tp.Generator[str, None, None]:
    yield TEST_CACHE_DIR
    if os.path.isdir(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


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
