import httpx

import httpx_cache


def test_msgpack_serializer_serialize():
    serializer = httpx_cache.MsgPackSerializer()
    data = {"some": "data", "is": "stored", "here": "."}
    expected = b"\x83\xa4some\xa4data\xa2is\xa6stored\xa4here\xa1."
    assert serializer.serialize(data) == expected


def test_msgpack_serializer_deserialize():
    serializer = httpx_cache.MsgPackSerializer()
    data = b"\x83\xa4some\xa4data\xa2is\xa6stored\xa4here\xa1."
    assert serializer.deserialize(data) == {"some": "data", "is": "stored", "here": "."}


def test_msgpack_serializer_e2e():
    serializer = httpx_cache.MsgPackSerializer()
    response = httpx.Response(
        200, content=b"Hello, world!", headers={"Content-Type": "application/json"}
    )
    new_response = serializer.loads(data=serializer.dumps(response=response))
    assert response.__getstate__() == new_response.__getstate__()
