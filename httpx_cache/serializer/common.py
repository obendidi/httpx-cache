import json
import typing as tp

import msgpack

from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.utils import CustomJSONEncoder


class MsgPackSerializer(BaseSerializer):
    """Simple serializer to bytes using msgpack."""

    def serialize(self, data: tp.Dict[str, tp.Any]) -> str:
        return msgpack.dumps(data, use_bin_type=True)

    def deserialize(self, data: str) -> tp.Dict[str, tp.Any]:
        return msgpack.loads(data, raw=False)


class DictSerializer(BaseSerializer):
    def serialize(self, data: tp.Dict[str, tp.Any]) -> tp.Dict[str, tp.Any]:
        return data

    def deserialize(self, data: tp.Dict[str, tp.Any]) -> tp.Dict[str, tp.Any]:
        return data


class StringSerializer(BaseSerializer):
    def serialize(self, data: tp.Dict[str, tp.Any]) -> str:
        return json.dumps(data, cls=CustomJSONEncoder)

    def deserialize(self, data: str) -> tp.Dict[str, tp.Any]:
        return json.loads(data)


class BytesSerializer(StringSerializer):
    def serialize(self, data: tp.Dict[str, tp.Any]) -> bytes:  # type: ignore[override]
        return super().serialize(data).encode("utf-8")

    def deserialize(self, data: bytes) -> tp.Dict[str, tp.Any]:  # type: ignore[override] # noqa
        return super().deserialize(data.decode("utf-8"))
