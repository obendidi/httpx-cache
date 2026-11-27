# httpx-cache

Zero-config, minimal-dependency response caching and deterministic replay for [`httpx`](https://github.com/encode/httpx) and [`httpx2`](https://github.com/pydantic/httpx2).

Built for API clients, scrapers, AI agents, and eval/test suites — with strict RFC 9111 caching when you want it.

- **Zero forced runtime dependencies**: pure Python stdlib (`sqlite3`, `json`, `zlib`, `threading`, `asyncio`). Bring whichever client you already use (`httpx>=0.27,<1` or `httpx2>=2.5`), plus optional `[redis]` (`redis>=5`).
- **Wrap any existing client**: `httpx_cache.wrap(client)` works on `httpx.Client`, `httpx.AsyncClient`, `httpx2.Client`, `httpx2.AsyncClient`, and SDK subclasses (e.g., OpenAI/Anthropic HTTP clients).
- **Three explicit policies**: `force` (TTL + opt-in POST body hashing, ignoring `no-store`/`private`), `replay` (offline-only deterministic playback, raises `CacheMissError` on miss), and `rfc9111` (`Cache-Control`, `Expires`, `Vary`, `ETag`/`Last-Modified` 304 revalidation).
- **Persistent SQLite by default**: WAL-mode `SqliteCache` with indexed TTL expiry, `zlib` body compression, LRU `max_size_bytes` cap, `.delete(key)`, `.clear()`, and `.stats()`.

## Installation

If your project already depends on `httpx` or `httpx2`:

```bash
pip install httpx-cache
```

Or install with a client or Redis extra:

```bash
pip install "httpx-cache[httpx]"
pip install "httpx-cache[httpx2]"
pip install "httpx-cache[redis]"
```

Requires Python 3.10+ (`httpx2>=2.15` requires Python 3.11+).

## Quickstart

```python
import httpx, httpx_cache

client = httpx_cache.wrap(httpx.Client(), policy="force", ttl=3600)
r1 = client.get("https://httpbin.org/get")  # hits network, saved to WAL SqliteCache
r2 = client.get("https://httpbin.org/get")  # served from cache
assert r1.extensions["from_cache"] is False and r2.extensions["from_cache"] is True
```

The exact same `wrap()` call works with `httpx2.Client()`, `httpx.AsyncClient()`, `httpx2.AsyncClient()`, and custom client subclasses.

## Policies

### `policy="force"` (default)
Ignores server `Cache-Control: no-store` / `private` / `no-cache` headers so APIs, scrapers, and LLM endpoints cache immediately. Opt into `POST` body-hash caching with `cache_post=True`:

```python
import httpx2, httpx_cache

cache = httpx_cache.SqliteCache(".cache/llm.sqlite3", max_size_bytes=50 * 1024 * 1024)
client = httpx_cache.wrap(
    httpx2.Client(),
    cache=cache,
    policy="force",
    ttl=86400,
    cache_post=True,
)
resp = client.post("https://api.example.com/v1/chat", json={"prompt": "hello"})
print(resp.extensions["from_cache"], resp.extensions["cache_key"])
```

### `policy="replay"` (offline evals & tests)
Never opens a network connection. Serves recorded entries (even past TTL) and raises `httpx_cache.CacheMissError(key, request)` on any unrecorded request:

```python
import httpx, httpx_cache

cache = httpx_cache.SqliteCache("tests/fixtures/cassette.sqlite3")
client = httpx_cache.wrap(httpx.Client(), cache=cache, policy="replay")
resp = client.post("https://api.example.com/v1/chat", json={"prompt": "hello"})
```

### `policy="rfc9111"` (HTTP caching semantics)
Honors `Cache-Control` (`no-store`, `no-cache`, `max-age`, `s-maxage`, `min-fresh`, `private` when `shared=True`), `Expires`, `Vary`, permanent redirects (`301`/`308`), and conditional revalidation (`ETag`/`If-None-Match`, `Last-Modified`/`If-Modified-Since` → `304 Not Modified` with `response.extensions["revalidated"] = True`).

```python
with httpx_cache.Client(policy="rfc9111") as client:
    r = client.get("https://api.github.com/repos/obendidi/httpx-cache")
```

## `httpx-cache` vs `hishel`

Both libraries cache `httpx` requests, with different goals:

| Capability | `httpx-cache` v1.0 | `hishel` |
| --- | --- | --- |
| Primary focus | Pragmatic API/agent/scraper caching & deterministic offline replay | Full RFC 9111 HTTP specification compliance |
| Runtime dependencies | Zero (stdlib only; bring `httpx` or `httpx2`) | `httpx` + `typing-extensions` / serializer deps |
| `httpx` + `httpx2` dual support | Yes (`wrap()` auto-detects both, even in one process) | `httpx` |
| Wrap an existing client / SDK | `httpx_cache.wrap(client)` in one line | Construct transport/client explicitly |
| Default store | Persistent WAL `SqliteCache` (indexed TTL, LRU cap, stats) | File / SQLite / Redis / S3 controllers |
| Force-cache `no-store` + `POST` body hashing | First-class (`policy="force", cache_post=True`) | Requires custom controller/policy config |
| Offline-only fail-loud replay | First-class (`policy="replay"` → `CacheMissError`) | Not a primary mode |
| Strict shared-proxy RFC 9111 edge cases | Core subset (`policy="rfc9111"`) | Best choice |

Choose **`hishel`** if you need exhaustive RFC 9111 proxy semantics. Choose **`httpx-cache`** if you want zero-dependency persistence, one-line wrapping of `httpx`/`httpx2` SDK clients, `POST`/LLM caching, or offline test/eval replay.

## Stores & Metadata

| Store | Persistence | Concurrency | Notes |
| --- | --- | --- | --- |
| `SqliteCache(path, max_size_bytes=...)` | Single WAL SQLite file (default `~/.cache/httpx-cache/cache.sqlite3`) | Thread-safe + async (`asyncio.to_thread`) | Default; indexed TTL expiry, `zlib` compression >1 KB, `.purge_expired()` |
| `MemoryCache(max_entries=..., max_size_bytes=...)` | In-process | Thread-safe + async | O(1) LRU eviction |
| `FileCache(cache_dir=...)` | One file per key | Thread-safe + async | Atomic temp-file writes, `zlib` compression |
| `RedisCache(redis_url=..., namespace=...)` | Redis (`pip install "httpx-cache[redis]"`) | Sync + async `redis>=5` | `SCAN`-based `.clear()` / `.stats()`, TTL passthrough |

Every cache store exposes `.get(key)`, `.set(key, entry)`, `.delete(key)`, `.clear()`, `.stats()` (`CacheStats(entries, size_bytes, hits, misses, expired)`) and async `a*` equivalents.

Every response sets:
- `response.extensions["from_cache"]` (`bool`)
- `response.extensions["cache_key"]` (`str`) — pass directly to `cache.delete(key)` to invalidate
- `response.extensions["revalidated"]` (`True`, when refreshed via `304 Not Modified`)

Custom cache keys and streaming (`stream=True`) work out of the box:

```python
client = httpx_cache.wrap(
    httpx.Client(),
    key_fn=lambda req: f"{req.method}:{req.url.path}",
)
with client.stream("GET", "https://example.com/large") as r:
    for chunk in r.iter_bytes():
        ...  # cached only if the stream finishes completely
```

## Explicit `httpx2` Client Subclasses

When both `httpx` and `httpx2` are installed in the same environment, `httpx_cache.wrap()` always matches the passed client automatically. For explicit subclasses:

```python
import httpx_cache
import httpx_cache.httpx2 as httpx2_cache

c1 = httpx_cache.Client()         # httpx.Client subclass
c2 = httpx2_cache.Client()        # httpx2.Client subclass
```

## Development

```bash
uv sync --python 3.12
uv run pytest --cov=httpx_cache
uv run ruff check .
uv run mypy httpx_cache
```
