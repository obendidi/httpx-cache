import json

import httpx
import pytest

from httpx_cache.serializer import BaseSerializer, Serializer

# This is the same as using the @pytest.mark.anyio on all test functions in the module
pytestmark = pytest.mark.anyio


def test_serializer_is_base_serializer():
    serializer = Serializer()
    assert isinstance(serializer, BaseSerializer)


async def test_serializer_dumps_and_loads(httpx_response: httpx.Response):
    # create instance of serializer
    serializer = Serializer()
    # create dummy request
    request = httpx.Request("GET", "http://testurl")
    # dump data
    if isinstance(httpx_response.stream, httpx.AsyncByteStream):
        httpx_content = await httpx_response.aread()
    else:
        httpx_content = httpx_response.read()
    data = serializer.dumps(response=httpx_response, content=httpx_content)
    # make sure it's in bytes
    assert isinstance(data, bytes)

    # load cached response -> new httpx.Response object
    cached_response = serializer.loads(data=data, request=request)
    assert isinstance(cached_response, httpx.Response)

    # make sure they have the same status code
    assert cached_response.status_code == httpx_response.status_code

    # Next we compare content of both original and cached response
    # we can get content usng the `read` or `aread` methods
    if isinstance(httpx_response.stream, httpx.AsyncByteStream):
        cached_content = await cached_response.aread()
    else:
        cached_content = cached_response.read()

    # comparse both contents
    assert cached_content == httpx_content

    # make sure teh rest is the same
    # TODO: check if there are other things that need to be compared ?
    assert cached_response.headers == httpx_response.headers
    assert cached_response.content == httpx_response.content
    assert cached_response.text == httpx_response.text
    assert cached_response.history == httpx_response.history
    assert cached_response.extensions == httpx_response.extensions
    assert cached_response.reason_phrase == httpx_response.reason_phrase
    assert cached_response.encoding == httpx_response.encoding
    assert cached_response.charset_encoding == httpx_response.charset_encoding
    assert cached_response.apparent_encoding == httpx_response.apparent_encoding
    assert cached_response.request is request

    try:
        httpx_response_json = httpx_response.json()
    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
        httpx_response_json = None

    if httpx_response_json is not None:
        assert httpx_response_json == cached_response.json()
