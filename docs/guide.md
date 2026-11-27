# User Guide

## Wrapping an Existing Client (`wrap`)

`httpx_cache.wrap(client, ...)` is the recommended entry point. It inspects `client` to detect sync vs async and `httpx` vs `httpx2`, wraps both `_transport` and `_mounts`, and returns the same client instance:

```python
import httpx, httpx_cache

cache = httpx_cache.SqliteCache(".cache/app.sqlite3", max_size_bytes=50 * 1024 * 1024)
client = httpx_cache.wrap(httpx.Client(), cache=cache, policy="force", ttl=3600)

with client:
    r1 = client.get("https://httpbin.org/get")
    r2 = client.get("https://httpbin.org/get")
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True
```

The same call works unchanged with `httpx.AsyncClient`, `httpx2.Client`, `httpx2.AsyncClient`, and third-party SDK subclasses.

## Drop-in Clients & Transports

- `httpx_cache.Client` / `httpx_cache.AsyncClient`: subclasses `httpx` (or `httpx2` if only `httpx2` is installed).
- `httpx_cache.httpx2.Client` / `httpx_cache.httpx2.AsyncClient`: explicit `httpx2` subclasses when both libraries are installed.
- `httpx_cache.SyncCacheTransport` / `httpx_cache.AsyncCacheTransport`: direct transport wrappers.

## Stores

- **`SqliteCache(path=None, max_size_bytes=None, compress=True)`** (default): WAL-mode SQLite file (`~/.cache/httpx-cache/cache.sqlite3`, or `":memory:"`), indexed TTL expiry, `zlib` body compression (>1 KB), LRU eviction, `.purge_expired()`, `.export_json()` / `.import_json()`.
- **`MemoryCache(max_entries=None, max_size_bytes=None)`**: thread-safe in-memory LRU.
- **`JsonCache(path)`**: single sorted, human-readable JSON file for git-diffable test/eval cassettes.
- **`FileCache(cache_dir=None, compress=True)`**: one atomically written file per key.
- **`RedisCache(redis_url=..., redis=..., aredis=..., namespace="httpx_cache", default_ttl=None)`**: `redis>=5` sync/async backend (`pip install "httpx-cache[redis]"`).

Every store implements `.get(key)`, `.set(key, entry)`, `.delete(key)`, `.keys(prefix="")`, `.delete_prefix(prefix)`, `.clear()`, `.stats()`, and async `a*` variants.

## Resilience, Coalescing & Filtering

- **Singleflight coalescing (`coalesce=True`)**: deduplicates concurrent sync/async cache misses on the same key so only one upstream call runs.
- **Stale-if-error (`stale_if_error=True | seconds`)**: returns the last expired entry (`response.extensions["stale"] = True`) if upstream raises a transport error or returns 5xx.
- **Per-request overrides (`extensions={"cache": {...}}`)**: pass `disabled=True`, `force_refresh=True`, `ttl=...`, or `key=...` on any individual request.
- **Filtering & scrubbing**: `urls_expire_after={"*/auth/*": 0, "*/prices": 30}`, `should_cache=lambda req, resp: ...`, `scrub_headers=("set-cookie",)`, and `max_cacheable_bytes=...` (prevents OOM on large streams while keeping LLM SSE streaming cached cleanly).
- **Observability hooks**: `on_hit(key, req)`, `on_miss(key, req)`, `on_store(key, req, entry)`.

## CLI

Inspect or manage SQLite caches from the terminal with `httpx-cache` (or `python -m httpx_cache`):

```bash
httpx-cache --db .cache/api.sqlite3 stats
httpx-cache --db .cache/api.sqlite3 inspect --prefix "POST:"
httpx-cache --db .cache/api.sqlite3 purge
httpx-cache --db .cache/api.sqlite3 export cassette.json
```

## Streaming Responses

With `client.stream(...)`, chunks pass through untouched as you iterate. The entry is written to the cache only once the stream reaches normal EOF — aborting early never caches a partial body, and raw `Content-Encoding` wire streams are preserved without double-decoding.

## Custom Cache Keys (`make_key_fn`)

Pass `key_fn` or use `httpx_cache.make_key_fn(...)` to strip ephemeral query parameters, hash selected headers (safe for `Authorization`), and canonicalize JSON request bodies:

```python
client = httpx_cache.wrap(
    httpx.Client(),
    cache_post=True,
    key_fn=httpx_cache.make_key_fn(
        ignore_params=("api_key", "ts"),
        include_headers=("x-tenant",),
        normalize_json_body=True,
    ),
)
```

Invalidate any response directly via `cache.delete(response.extensions["cache_key"])`.

## Pytest Record / Replay Fixture

`httpx-cache` exposes a built-in pytest plugin (`httpx_cache_cassette` + `--httpx-cache-record=once|replay|rewrite`) with zero runtime dependency on `pytest`:

```python
import httpx

def test_endpoint(httpx_cache_cassette):
    with httpx_cache_cassette.wrap(httpx.Client()) as client:
        resp = client.get("https://api.example.com/items")
        assert resp.status_code == 200
```
