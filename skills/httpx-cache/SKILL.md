---
name: httpx-cache
description: Add persistent HTTP response caching or deterministic offline replay to Python projects using httpx or httpx2 (APIs, scrapers, AI agent SDKs, evals, and pytest suites) via httpx-cache v1.0.
---

# Using `httpx-cache` v1.0

`httpx-cache` is a zero-dependency caching and replay transport for both `httpx` (`>=0.27,<1`) and Pydantic's `httpx2` (`>=2.5`).

## Install

```bash
uv add httpx-cache            # when httpx or httpx2 is already in the project
uv add "httpx-cache[httpx]"   # with httpx
uv add "httpx-cache[httpx2]"  # with httpx2
uv add "httpx-cache[redis]"   # optional RedisCache (redis>=5)
```

## Choose the Right Policy

| Use case | Policy & flags | Behavior |
| --- | --- | --- |
| LLM APIs, GraphQL, RPC, scrapers | `policy="force", ttl=3600, cache_post=True` | Ignores `no-store`/`private`; hashes POST bodies into cache key |
| Offline evals & unit tests | `policy="replay"` | Never hits network; ignores TTL; raises `CacheMissError(key, request)` on miss |
| Standard HTTP caching | `policy="rfc9111"` | Honors `Cache-Control`, `Expires`, `Vary`, and `ETag`/`Last-Modified` 304 revalidation |

## Preferred Integration Pattern: `wrap(client)`

Wrap any existing `httpx.Client`, `httpx.AsyncClient`, `httpx2.Client`, `httpx2.AsyncClient`, or SDK subclass in place:

```python
import httpx, httpx_cache

cache = httpx_cache.SqliteCache(".cache/http.sqlite3", max_size_bytes=100 * 1024 * 1024)
client = httpx_cache.wrap(httpx.Client(), cache=cache, policy="force", ttl=3600, cache_post=True)

resp = client.post("https://api.example.com/v1/query", json={"q": "status"})
assert resp.extensions["from_cache"] is False
cache_key = resp.extensions["cache_key"]
```

For SDKs that accept an `http_client=` (e.g., OpenAI, Anthropic), pass a wrapped client:

```python
import httpx2, httpx_cache
from openai import OpenAI

http_client = httpx_cache.wrap(
    httpx2.Client(),
    cache=httpx_cache.SqliteCache(".cache/openai.sqlite3"),
    policy="force",
    cache_post=True,
)
ai = OpenAI(http_client=http_client)
```

## Record-Once, Replay-Offline Workflow for Tests/Evals

1. Record with `policy="force", cache_post=True` into a committed or fixture `SqliteCache("tests/fixtures/eval.sqlite3")`.
2. In CI/tests, switch to `policy="replay"` against the same SQLite file. Any unexpected or changed request raises `CacheMissError` with `.key` and `.request` instead of making live calls.

## Store Selection & Lifecycle

- **`SqliteCache(path, max_size_bytes=..., compress=True)`** (default): WAL mode, thread-safe + async-safe, indexed TTL expiry, `.purge_expired()`, `.delete(key)`, `.clear()`, `.stats()`.
- **`MemoryCache(max_entries=..., max_size_bytes=...)`**: fast in-memory LRU for short-lived processes/tests.
- **`FileCache(cache_dir)`**: one atomically written file per key.
- **`RedisCache(redis_url=..., namespace=...)`**: shared cache across workers (`httpx-cache[redis]`).

Caller-passed `cache=` instances are **not** closed when the wrapped client closes — close them yourself (or use `with cache:`).

## Common Pitfalls

- **Dynamic headers or timestamps in URLs**: pass `key_fn=lambda req: ...` to strip ephemeral query params or include specific headers (e.g. `Authorization` tenant hash when sharing one cache across accounts).
- **Streaming responses (`client.stream(...)`)**: responses are only written to cache once the stream finishes completely; breaking early leaves the cache untouched.
- **Explicit `httpx2` subclasses**: when both `httpx` and `httpx2` are installed, use `httpx_cache.wrap(httpx2.Client())` or `from httpx_cache.httpx2 import Client, AsyncClient`.
