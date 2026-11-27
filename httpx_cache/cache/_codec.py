from __future__ import annotations

import json
import struct
import zlib
from typing import Any

from httpx_cache.types import CacheEntry

_MAGIC = b"HXC1"
_HEADER_STRUCT = struct.Struct(">4sBI")
_FLAG_COMPRESSED = 1
_COMPRESS_THRESHOLD_BYTES = 1024


def encode_entry(entry: CacheEntry, *, compress: bool = True) -> bytes:
    """Encode a CacheEntry into a compact binary envelope (JSON metadata + raw/zlib body)."""
    meta = {
        "status_code": entry.status_code,
        "headers": [list(pair) for pair in entry.headers],
        "http_version": entry.http_version,
        "encoding": entry.encoding,
        "created_at": entry.created_at,
        "expires_at": entry.expires_at,
        "metadata": entry.metadata,
    }
    meta_bytes = json.dumps(meta, separators=(",", ":")).encode("utf-8")

    body = entry.body
    flags = 0
    if compress and len(body) >= _COMPRESS_THRESHOLD_BYTES:
        compressed = zlib.compress(body, level=6)
        if len(compressed) < len(body):
            body = compressed
            flags |= _FLAG_COMPRESSED

    header = _HEADER_STRUCT.pack(_MAGIC, flags, len(meta_bytes))
    return header + meta_bytes + body


def decode_entry(raw: bytes) -> CacheEntry:
    """Decode a binary envelope produced by :func:`encode_entry`."""
    if len(raw) < _HEADER_STRUCT.size:
        raise ValueError("Truncated cache entry payload.")

    magic, flags, meta_len = _HEADER_STRUCT.unpack_from(raw, 0)
    if magic != _MAGIC:
        raise ValueError(f"Invalid cache entry magic header: {magic!r}")

    meta_start = _HEADER_STRUCT.size
    meta_end = meta_start + meta_len
    if meta_end > len(raw):
        raise ValueError("Corrupted cache entry metadata length.")

    meta: dict[str, Any] = json.loads(raw[meta_start:meta_end].decode("utf-8"))
    raw_body = raw[meta_end:]
    body = zlib.decompress(raw_body) if (flags & _FLAG_COMPRESSED) else raw_body

    headers = tuple((str(k), str(v)) for k, v in meta["headers"])
    return CacheEntry(
        status_code=int(meta["status_code"]),
        headers=headers,
        body=body,
        http_version=str(meta.get("http_version", "HTTP/1.1")),
        encoding=meta.get("encoding"),
        created_at=float(meta["created_at"]),
        expires_at=None if meta.get("expires_at") is None else float(meta["expires_at"]),
        metadata=dict(meta.get("metadata") or {}),
    )
