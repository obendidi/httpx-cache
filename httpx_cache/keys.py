from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any


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
