# API Reference

## Entry Points

- `httpx_cache.wrap(client, *, cache=None, policy="force", ttl=None, cache_post=False, cacheable_methods=None, cacheable_status_codes=None, key_fn=None, shared=False, urls_expire_after=None, stale_if_error=False, scrub_headers=(), should_cache=None, coalesce=False, max_cacheable_bytes=None, on_hit=None, on_miss=None, on_store=None)`
- `httpx_cache.Client`, `httpx_cache.AsyncClient`
- `httpx_cache.httpx2.Client`, `httpx_cache.httpx2.AsyncClient`
- `httpx_cache.SyncCacheTransport`, `httpx_cache.AsyncCacheTransport`

## Stores

- `httpx_cache.BaseCache`
- `httpx_cache.SqliteCache`
- `httpx_cache.MemoryCache`
- `httpx_cache.JsonCache`
- `httpx_cache.FileCache`
- `httpx_cache.RedisCache`

## Models, Keys & Exceptions

- `httpx_cache.CacheEntry`
- `httpx_cache.CacheStats`
- `httpx_cache.CacheMissError`
- `httpx_cache.PolicyController`
- `httpx_cache.default_key_fn`
- `httpx_cache.make_key_fn(*, ignore_params=(), include_headers=(), include_body=True, normalize_json_body=False, prefix="")`

## Pytest Plugin

- Fixture: `httpx_cache_cassette` (`.path`, `.mode`, `.policy`, `.cache`, `.wrap(client, ...)`)
- Fixture: `httpx_cache_record_mode`
- CLI flag: `--httpx-cache-record=once|replay|rewrite`
