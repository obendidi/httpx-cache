"""
We run a suite of tests on the DictSerializer to make sure we are able to
reconstruct exactly the same response from the serialized dict, and that bot original
and cached response behave similiary.

Test are taken from:
    https://github.com/encode/httpx/blob/master/tests/models/test_responses.py
"""
import json

import httpx
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
testcases_encoding = [
    "utf-8",
    "utf-8-sig",
    "utf-16",
    "utf-16-be",
    "utf-16-le",
    "utf-32",
    "utf-32-be",
    "utf-32-le",
]


class StreamingBody:
    def __iter__(self):
        yield b"Hello, "
        yield b"world!"


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_content(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, content=b"Hello, world!")
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.status_code == cached.status_code
    assert response.reason_phrase == cached.reason_phrase
    assert response.content == cached.content == b"Hello, world!"
    assert response.text == cached.text == "Hello, world!"
    assert response.headers == cached.headers == {"Content-Length": "13"}
    assert response.is_closed and cached.is_closed


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_content_with_request(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, content=b"Hello, world!")
    request = httpx.Request("GET", "http://testurl")
    cached = serializer.loads(
        cached=serializer.dumps(response=response), request=request
    )
    assert cached.request is request


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_text(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, text="Hello, world!")
    cached = serializer.loads(cached=serializer.dumps(response=response))
    expected_headers = {
        "Content-Length": "13",
        "Content-Type": "text/plain; charset=utf-8",
    }

    assert response.status_code == cached.status_code
    assert response.reason_phrase == cached.reason_phrase
    assert response.text == cached.text
    assert response.headers == cached.headers == expected_headers


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_html(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, html="<html><body>Hello, world!</html></body>")
    cached = serializer.loads(cached=serializer.dumps(response=response))
    expected_headers = {
        "Content-Length": "39",
        "Content-Type": "text/html; charset=utf-8",
    }
    assert response.status_code == cached.status_code
    assert response.reason_phrase == cached.reason_phrase
    assert response.text == cached.text
    assert response.headers == cached.headers == expected_headers


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_json(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, json={"hello": "world"})
    cached = serializer.loads(cached=serializer.dumps(response=response))
    expected_headers = {
        "Content-Length": "18",
        "Content-Type": "application/json",
    }
    assert response.status_code == cached.status_code
    assert response.reason_phrase == cached.reason_phrase
    assert response.json() == cached.json()
    assert response.headers == cached.headers == expected_headers


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_content_type_encoding(serializer: httpx_cache.BaseSerializer):
    headers = {"Content-Type": "text-plain; charset=latin-1"}
    content = "Latin 1: ÿ".encode("latin-1")
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text
    assert response.encoding == cached.encoding


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_autodetect_encoding(serializer: httpx_cache.BaseSerializer):
    content = "おはようございます。".encode("utf-8")
    response = httpx.Response(
        200,
        content=content,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text
    assert response.encoding is cached.encoding is None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_fallback_to_autodetect(serializer: httpx_cache.BaseSerializer):
    headers = {"Content-Type": "text-plain; charset=invalid-codec-name"}
    content = "おはようございます。".encode("utf-8")
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text
    assert response.encoding is cached.encoding is None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_no_charset_with_ascii_content(
    serializer: httpx_cache.BaseSerializer,
):
    content = b"Hello, world!"
    headers = {"Content-Type": "text/plain"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text
    assert response.encoding is cached.encoding is None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_no_charset_with_utf8_content(
    serializer: httpx_cache.BaseSerializer,
):
    content = "Unicode Snowman: ☃".encode("utf-8")
    headers = {"Content-Type": "text/plain"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text
    assert response.encoding is cached.encoding is None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_no_charset_with_iso_8859_1_content(
    serializer: httpx_cache.BaseSerializer,
):
    content = "Accented: Österreich abcdefghijklmnopqrstuzwxyz".encode("iso-8859-1")
    headers = {"Content-Type": "text/plain"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text
    assert response.charset_encoding is cached.charset_encoding is None
    assert response.apparent_encoding is cached.apparent_encoding is not None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_no_charset_with_cp_1252_content(
    serializer: httpx_cache.BaseSerializer,
):
    content = "Euro Currency: € abcdefghijklmnopqrstuzwxyz".encode("cp1252")
    headers = {"Content-Type": "text/plain"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text
    assert response.charset_encoding is cached.charset_encoding is None
    assert response.apparent_encoding is cached.apparent_encoding is not None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_non_text_encoding(serializer: httpx_cache.BaseSerializer):
    headers = {"Content-Type": "image/png"}
    response = httpx.Response(
        200,
        content=b"xyz",
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text == "xyz"
    assert response.encoding is cached.encoding is None


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_set_explicit_encoding(serializer: httpx_cache.BaseSerializer):
    headers = {
        "Content-Type": "text-plain; charset=utf-8"
    }  # Deliberately incorrect charset
    response = httpx.Response(
        200,
        content="Latin 1: ÿ".encode("latin-1"),
        headers=headers,
    )
    response.encoding = "latin-1"
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text == "Latin 1: ÿ"
    assert response.encoding == cached.encoding == "latin-1"


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_response_force_encoding(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(
        200,
        content="Snowman: ☃".encode("utf-8"),
    )
    response.encoding = "iso-8859-1"
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text == "Snowman: â\x98\x83"
    assert response.encoding == cached.encoding == "iso-8859-1"


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_json_with_specified_encoding(serializer: httpx_cache.BaseSerializer):
    data = {"greeting": "hello", "recipient": "world"}
    content = json.dumps(data).encode("utf-16")
    headers = {"Content-Type": "application/json, charset=utf-16"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert cached.json() == data


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_json_with_options(serializer: httpx_cache.BaseSerializer):
    data = {"greeting": "hello", "recipient": "world", "amount": 1}
    content = json.dumps(data).encode("utf-16")
    headers = {"Content-Type": "application/json, charset=utf-16"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert cached.json(parse_int=str)["amount"] == "1"


@pytest.mark.parametrize("encoding", testcases_encoding, ids=testcases_encoding)
@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_json_without_specified_charset(
    encoding: str, serializer: httpx_cache.BaseSerializer
):
    data = {"greeting": "hello", "recipient": "world"}
    content = json.dumps(data).encode(encoding)
    headers = {"Content-Type": "application/json"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert cached.json() == data


@pytest.mark.parametrize("encoding", testcases_encoding, ids=testcases_encoding)
@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_json_with_specified_charset(
    encoding: str, serializer: httpx_cache.BaseSerializer
):
    data = {"greeting": "hello", "recipient": "world"}
    content = json.dumps(data).encode(encoding)
    headers = {"Content-Type": f"application/json; charset={encoding}"}
    response = httpx.Response(
        200,
        content=content,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert cached.json() == data


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_read(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(
        200,
        content=b"Hello, world!",
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    content = response.read()
    cached_content = cached.read()
    assert content == cached_content


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_empty_read(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200)
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text == ""
    content = response.read()
    cached_content = cached.read()
    assert content == cached_content == cached.content == b""


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_aread(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(
        200,
        content=b"Hello, world!",
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text == "Hello, world!"
    content = await response.aread()
    cached_content = await cached.aread()
    assert content == cached_content == cached.content == b"Hello, world!"


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_empty_aread(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200)
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert response.text == cached.text == ""
    content = await response.aread()
    cached_content = await cached.aread()
    assert content == cached_content == cached.content == b""


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_iter_raw_request_not_read_error(
    serializer: httpx_cache.BaseSerializer, streaming_body
):
    response = httpx.Response(200, content=streaming_body)
    with pytest.raises(httpx.ResponseNotRead):
        serializer.loads(cached=serializer.dumps(response=response))


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_iter_raw(serializer: httpx_cache.BaseSerializer, streaming_body):
    # We create a response with a streamig body response
    response = httpx.Response(200, content=streaming_body)
    # as long as we don't run the .read() method, we will have no content
    # in the response above
    with pytest.raises(httpx.ResponseNotRead):
        response.content

    # The response doesn't have a content, so technically there is nothing to cache
    # we create a wrapper around the reponse stream then, that will use a callback
    # to cache the response when the stream has been fully loaded

    store = {}  # where we will store the cached response using the callbak

    def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # since we didn't read the response, they are set to False
    assert response.is_stream_consumed is False
    assert response.is_closed is False

    # before reading the response, make sure the store is empty
    assert len(store) == 0

    # we iter on the original response
    # at the end of the iter, the callback should be automatically called
    original_content = b""
    for part in response.iter_raw():
        original_content += part

    # we should have a cached element in store now
    assert "cached" in store

    # we load the cached response
    cached = serializer.loads(cached=store["cached"])

    # same as original response, cached should not have content before read()
    with pytest.raises(httpx.ResponseNotRead):
        cached.content

    # last step is to iter over cached response and get content
    cached_content = b""
    for part in cached.iter_raw():
        cached_content += part

    # make sure the content is the same
    assert cached_content == original_content


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_iter_raw_with_chunksize(
    serializer: httpx_cache.BaseSerializer, streaming_body
):
    # same as test above but we skip most of the checks since already done
    response = httpx.Response(200, content=streaming_body)
    store = {}

    def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # we iter on original the response
    # at the end of the iter, the callback should be automatically called
    original_parts = [part for part in response.iter_raw(chunk_size=5)]

    # we load the cached response
    cached = serializer.loads(cached=store["cached"])

    # last step is to iter over cached response and get content
    cached_parts = [part for part in cached.iter_raw(chunk_size=5)]

    # make sure the content is the same
    assert original_parts == cached_parts == [b"Hello", b", wor", b"ld!"]


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_iter_raw_on_iterable(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, content=StreamingBody())
    store = {}

    def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # we iter on the original response
    # at the end of the iter, the callback should be automatically called
    original_content = b""
    for part in response.iter_raw():
        original_content += part

    cached = serializer.loads(cached=store["cached"])

    cached_content = b""
    for part in cached.iter_raw():
        cached_content += part

    # make sure the content is the same
    assert cached_content == original_content


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_aiter_raw(serializer: httpx_cache.BaseSerializer, async_streaming_body):
    response = httpx.Response(200, content=async_streaming_body)
    store = {}

    async def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # we iter on the original response
    # at the end of the iter, the callback should be automatically called
    original_content = b""
    async for part in response.aiter_raw():
        original_content += part

    cached = serializer.loads(cached=store["cached"])

    cached_content = b""
    async for part in cached.aiter_raw():
        cached_content += part

    # make sure the content is the same
    assert cached_content == original_content


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_aiter_raw_with_chunksize(
    serializer: httpx_cache.BaseSerializer, async_streaming_body
):
    # same as test above but we skip most of the checks since already done
    response = httpx.Response(200, content=async_streaming_body)
    store = {}

    async def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # we iter on original the response
    # at the end of the iter, the callback should be automatically called
    original_parts = [part async for part in response.aiter_raw(chunk_size=5)]

    # we load the cached response
    cached = serializer.loads(cached=store["cached"])

    # last step is to iter over cached response and get content
    cached_parts = [part async for part in cached.aiter_raw(chunk_size=5)]

    # make sure the content is the same
    assert original_parts == cached_parts == [b"Hello", b", wor", b"ld!"]


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_iter_bytes(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, content=b"Hello, world!")
    cached = serializer.loads(cached=serializer.dumps(response=response))

    content = b""
    for part in cached.iter_bytes():
        content += part
    assert content == b"Hello, world!"


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_iter_bytes_with_chunk_size(
    serializer: httpx_cache.BaseSerializer, streaming_body
):
    response = httpx.Response(200, content=streaming_body)
    store = {}

    def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # we iter on original the response
    # at the end of the iter, the callback should be automatically called
    original_parts = [part for part in response.iter_bytes(chunk_size=5)]

    # we load the cached response
    cached = serializer.loads(cached=store["cached"])

    # last step is to iter over cached response and get content
    cached_parts = [part for part in cached.iter_bytes(chunk_size=5)]

    # make sure the content is the same
    assert original_parts == cached_parts == [b"Hello", b", wor", b"ld!"]


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_iter_bytes_with_empty_response(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, content=b"")
    cached = serializer.loads(cached=serializer.dumps(response=response))
    parts = [part for part in cached.iter_bytes()]
    assert parts == []


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_aiter_bytes(serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(200, content=b"Hello, world!")
    cached = serializer.loads(cached=serializer.dumps(response=response))

    content = b""
    async for part in cached.aiter_bytes():
        content += part
    assert content == b"Hello, world!"


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_aiter_bytes_with_chunk_size(
    serializer: httpx_cache.BaseSerializer, async_streaming_body
):
    response = httpx.Response(200, content=async_streaming_body)
    store = {}

    async def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    # we iter on original the response
    # at the end of the iter, the callback should be automatically called
    original_parts = [part async for part in response.aiter_bytes(chunk_size=5)]

    # we load the cached response
    cached = serializer.loads(cached=store["cached"])

    # last step is to iter over cached response and get content
    cached_parts = [part async for part in cached.aiter_bytes(chunk_size=5)]

    # make sure the content is the same
    assert original_parts == cached_parts == [b"Hello", b", wor", b"ld!"]


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_sync_streaming_response(
    serializer: httpx_cache.BaseSerializer, streaming_body
):
    response = httpx.Response(200, content=streaming_body)
    store = {}

    def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    assert not response.is_closed

    content = response.read()
    assert response.is_closed
    cached = serializer.loads(cached=store["cached"])
    assert not cached.is_closed
    assert cached.read() == content
    assert cached.is_closed


@pytest.mark.parametrize("serializer", testcases, ids=testids)
async def test_async_streaming_response(
    serializer: httpx_cache.BaseSerializer, async_streaming_body
):
    response = httpx.Response(200, content=async_streaming_body)
    store = {}

    async def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    assert not response.is_closed

    content = await response.aread()
    assert response.is_closed
    cached = serializer.loads(cached=store["cached"])
    assert not cached.is_closed
    assert await cached.aread() == content
    assert cached.is_closed


@pytest.mark.parametrize(
    "headers, expected",
    [
        (
            {"Link": "<https://example.com>; rel='preload'"},
            {"preload": {"rel": "preload", "url": "https://example.com"}},
        ),
        (
            {"Link": '</hub>; rel="hub", </resource>; rel="self"'},
            {
                "hub": {"url": "/hub", "rel": "hub"},
                "self": {"url": "/resource", "rel": "self"},
            },
        ),
    ],
)
@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_link_headers(headers, expected, serializer: httpx_cache.BaseSerializer):
    response = httpx.Response(
        200,
        content=None,
        headers=headers,
    )
    cached = serializer.loads(cached=serializer.dumps(response=response))
    assert cached.links == expected


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_generator_with_transfer_encoding_header(
    serializer: httpx_cache.BaseSerializer,
):
    def content():
        yield b"test 123"

    response = httpx.Response(200, content=content())
    store = {}

    def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )

    response.read()
    cached = serializer.loads(cached=store["cached"])

    assert cached.headers == {"Transfer-Encoding": "chunked"}


@pytest.mark.parametrize("serializer", testcases, ids=testids)
def test_generator_with_content_length_header(
    serializer: httpx_cache.BaseSerializer,
):
    def content():
        yield b"test 123"

    headers = {"Content-Length": "8"}
    response = httpx.Response(200, content=content(), headers=headers)
    store = {}

    def callback(content: bytes) -> None:
        store["cached"] = serializer.dumps(response=response, content=content)

    # wrap the response stream
    response.stream = httpx_cache.ByteStreamWrapper(
        stream=response.stream, callback=callback  # type: ignore
    )
    response.read()
    cached = serializer.loads(cached=store["cached"])
    assert cached.headers == {"Content-Length": "8"}
