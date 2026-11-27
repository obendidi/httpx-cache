# Changelog

## v1.1.0

- **Composable cache key helper (`make_key_fn`)**: strip ephemeral query parameters (`ignore_params`), hash selected request headers safely (`include_headers`), and canonicalize JSON request bodies (`normalize_json_body=True`).
- **Built-in pytest record/replay plugin**: registers the `httpx_cache_cassette` fixture and `--httpx-cache-record=once|replay|rewrite` CLI option via `pytest11` entry point with zero runtime dependency on `pytest`.
- **Live Redis CI coverage & automated MkDocs deployment**: added live `redis:7-alpine` integration tests in CI and automated GitHub Pages deployment (including `/llms.txt` at site root).

## v1.0.0

- **Dual `httpx` and `httpx2` support**: `httpx_cache.wrap(client)` auto-detects `httpx` (`>=0.27,<1`), Pydantic's `httpx2` (`>=2.5`), and SDK client subclasses, allowing both libraries to share the same cache even in one process. Explicit `httpx_cache.httpx2.Client` and `AsyncClient` subclasses are also included.
- **Zero forced runtime dependencies**: pure Python stdlib core (Python 3.10+); bring whichever client you already use, with optional `[httpx]`, `[httpx2]`, and `[redis]` (`redis>=5`) extras.
- **Three explicit caching policies**:
  - `policy="force"` (default): ignores `no-store`/`private`/`no-cache`, supports `ttl` and opt-in `cache_post=True` SHA-256 request-body keying for GraphQL, RPC, and LLM APIs.
  - `policy="replay"`: offline-only deterministic playback that ignores expiry and raises `CacheMissError(key, request)` on misses without touching the network.
  - `policy="rfc9111"`: honors `Cache-Control`, `Expires`, `Vary`, permanent redirects, and `ETag`/`Last-Modified` `304 Not Modified` revalidation.
- **Persistent WAL-mode `SqliteCache` by default**: thread-safe and async-safe, indexed TTL expiry, `zlib` body compression, LRU `max_size_bytes` eviction, `.delete(key)`, `.clear()`, `.purge_expired()`, and `.stats()`.
- **Refreshed `MemoryCache`, `FileCache`, and optional `RedisCache`**: string-keyed stores with atomic file writes, lossless binary encoding, and `SCAN`-based Redis clear/stats.
- **Response metadata, custom keys & safe streaming**: sets `response.extensions["from_cache"]`, `response.extensions["cache_key"]`, and `response.extensions["revalidated"]`; supports custom `key_fn`; caches streamed responses only on full consumption while preserving `Content-Encoding` fidelity.
- **Typing & agent docs**: added `py.typed`, `AGENTS.md`, `docs/llms.txt`, and `skills/httpx-cache/SKILL.md`.
