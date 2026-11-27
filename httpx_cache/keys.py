from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from httpx_cache.types import KeyFn


def read_request_body_sync(request: Any) -> bytes:
    """Return request body bytes safely, reading the sync stream if needed."""
    if hasattr(request, "_content"):
        return bytes(request.content)
    if hasattr(request, "read"):
        return bytes(request.read())
    return b""


async def read_request_body_async(request: Any) -> bytes:
    """Return request body bytes safely, awaiting the async stream if needed."""
    if hasattr(request, "_content"):
        return bytes(request.content)
    if hasattr(request, "aread"):
        return bytes(await request.aread())
    return b""


def _canonical_url(url_str: str, ignore_params: frozenset[str]) -> str:
    if not ignore_params:
        return url_str
    parts = urlsplit(url_str)
    if not parts.query:
        return url_str
    filtered = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in ignore_params
    ]
    filtered.sort()
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(filtered), parts.fragment))


def _canonical_body(body: bytes, *, normalize_json: bool) -> bytes:
    if not normalize_json or not body:
        return body
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body
    return json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")


def default_key_fn(
    request: Any,
    *,
    vary_headers: Sequence[str] = (),
) -> str:
    """Build a deterministic cache key from method, URL, optional body hash, and vary headers.

    For requests with an empty body (e.g. standard GET/HEAD), returns ``METHOD:URL``.
    When a request carries a body (e.g. POST/GraphQL/LLM RPC), appends its SHA-256 hex digest
    so identical endpoints with different payloads never collide and ``force`` + ``replay``
    always compute the exact same key.
    """
    method = str(request.method).upper()
    url = str(request.url)
    parts = [f"{method}:{url}"]

    body = request.content if hasattr(request, "_content") else b""
    if body:
        body_hash = hashlib.sha256(body).hexdigest()
        parts.append(f"body={body_hash}")

    if vary_headers:
        header_pairs = []
        for name in sorted({h.lower() for h in vary_headers}):
            values = request.headers.get_list(name)
            header_pairs.append(f"{name}={','.join(values)}")
        vary_hash = hashlib.sha256("\n".join(header_pairs).encode("utf-8")).hexdigest()[:16]
        parts.append(f"vary={vary_hash}")

    return "|".join(parts)


def make_key_fn(
    *,
    ignore_params: Sequence[str] = (),
    include_headers: Sequence[str] = (),
    include_body: bool = True,
    normalize_json_body: bool = False,
    prefix: str = "",
) -> KeyFn:
    """Build a reusable custom ``key_fn`` with query filtering, header hashing, and JSON sorting.

    Args:
        ignore_params: Case-insensitive query parameter names to strip before keying.
            Remaining query parameters are sorted for deterministic keys.
        include_headers: Case-insensitive request header names to include via SHA-256 hash
            (safe for credentials like ``Authorization`` since raw values are not stored).
        include_body: Include SHA-256 of non-empty request bodies (default True).
        normalize_json_body: Parse JSON bodies and re-serialize with sorted keys before hashing.
        prefix: Optional namespace prefix prepended to every key.
    """
    ignored = frozenset(p.lower() for p in ignore_params)
    header_names = tuple(sorted({h.lower() for h in include_headers}))

    def _key(request: Any) -> str:
        method = str(request.method).upper()
        url = _canonical_url(str(request.url), ignored)
        parts = [f"{prefix}:{method}:{url}" if prefix else f"{method}:{url}"]

        if include_body:
            raw_body = request.content if hasattr(request, "_content") else b""
            if raw_body:
                canon = _canonical_body(raw_body, normalize_json=normalize_json_body)
                parts.append(f"body={hashlib.sha256(canon).hexdigest()}")

        if header_names:
            header_pairs = [
                f"{name}={','.join(request.headers.get_list(name))}" for name in header_names
            ]
            hdr_hash = hashlib.sha256("\n".join(header_pairs).encode("utf-8")).hexdigest()[:16]
            parts.append(f"hdr={hdr_hash}")

        return "|".join(parts)

    return _key
