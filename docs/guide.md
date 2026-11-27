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

- **`SqliteCache(path=None, max_size_bytes=None, compress=True)`** (default): WAL-mode SQLite file (`~/.cache/httpx-cache/cache.sqlite3`, or `":memory:"`), indexed TTL expiry, `zlib` body compression (>1 KB), LRU eviction, `.purge_expired()`.
- **`MemoryCache(max_entries=None, max_size_bytes=None)`**: thread-safe in-memory LRU.
- **`FileCache(cache_dir=None, compress=True)`**: one atomically written file per key.
- **`RedisCache(redis_url=..., redis=..., aredis=..., namespace="httpx_cache", default_ttl=None)`**: `redis>=5` sync/async backend (`pip install "httpx-cache[redis]"`).

Every store implements `.get(key)`, `.set(key, entry)`, `.delete(key)`, `.clear()`, `.stats()`, and async `a*` variants.

## Streaming Responses

With `client.stream(...)`, chunks pass through untouched as you iterate. The entry is written to the cache only once the stream reaches normal EOF — aborting early never caches a partial body, and raw `Content-Encoding` wire streams are preserved without double-decoding.

## Custom Cache Keys

Pass `key_fn` to override default `METHOD:URL[|body=<sha256>]` keying:

```python
client = httpx_cache.wrap(
    httpx.Client(),
    key_fn=lambda req: f"{req.method}:{req.url.path}",
)
```

Invalidate any response directly via `cache.delete(response.extensions["cache_key"])`.
