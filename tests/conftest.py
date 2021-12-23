import httpx
import pytest


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory):
    return tmp_path_factory.mktemp(request.node.name)


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
