import typing as tp

import msgpack

from httpx_cache.serializer.base import BaseSerializer


class MsgPackSerializer(BaseSerializer):
    """Simple serializer to bytes using msgpack."""

    def serialize(self, data: tp.Dict[str, tp.Any]) -> str:
        return msgpack.dumps(data, use_bin_type=True)

    def deserialize(self, data: str) -> tp.Dict[str, tp.Any]:
        return msgpack.loads(data, raw=False)
