# AGENTS.md — `httpx-cache`

Zero-config, zero-extra-dependency response caching and deterministic replay layer for `httpx` and `httpx2`.

## Commands

- Install dev env: `uv sync --python 3.12`
- Test (both `httpx` & `httpx2`): `uv run pytest`
- Test with coverage: `uv run pytest --cov=httpx_cache`
- Lint: `uv run ruff check .`
- Typecheck (strict, Py 3.10 target): `uv run mypy httpx_cache`
- Build sdist/wheel: `uv build`

## Architecture

- `httpx_cache/types.py` — pure stdlib data models (`CacheEntry`, `CacheStats`, `CacheMissError`, type aliases).
- `httpx_cache/_backend.py` — dual-backend adapter detecting `httpx` vs `httpx2` via MRO, building backend-native `Response` and `SyncByteStream`/`AsyncByteStream` wrappers.
- `httpx_cache/keys.py` — `default_key_fn` (`METHOD:URL` + SHA-256 body hash when body is non-empty) and safe sync/async body readers.
- `httpx_cache/policy.py` — `PolicyController` implementing `force`, `rfc9111` (incl. `Vary` & `ETag`/`Last-Modified` 304 revalidation), and `replay`.
- `httpx_cache/cache/` — string-keyed `BaseCache`, WAL `SqliteCache` (default), `MemoryCache`, `FileCache`, `_codec.py`, and lazy-imported optional `RedisCache`.
- `httpx_cache/transport.py` — `SyncCacheTransport` & `AsyncCacheTransport`.
- `httpx_cache/client.py` & `httpx_cache/httpx2.py` — `wrap(client)` and `Client`/`AsyncClient` subclasses.

## Invariants

- Core package MUST have `dependencies = []` (stdlib only). Never import `httpx`, `httpx2`, or `redis` eagerly at module import time.
- Stores MUST stay string-keyed and backend-agnostic so `httpx` and `httpx2` share caches cleanly.
- Streaming responses MUST NOT be cached unless the stream is consumed to completion, and raw wire streams MUST preserve `Content-Encoding` without double-decoding.
- Transports close only caches they created themselves (`_owns_cache=True`), never caller-provided `cache=` instances.
- Maintain Python 3.10 compatibility (`mypy --python-version=3.10` must pass without `typing_extensions`).
