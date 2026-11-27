# API Reference

## Entry Points

- `httpx_cache.wrap(client, *, cache=None, policy="force", ttl=None, cache_post=False, cacheable_methods=None, cacheable_status_codes=None, key_fn=None, shared=False)`
- `httpx_cache.Client`, `httpx_cache.AsyncClient`
- `httpx_cache.httpx2.Client`, `httpx_cache.httpx2.AsyncClient`
- `httpx_cache.SyncCacheTransport`, `httpx_cache.AsyncCacheTransport`

## Stores

- `httpx_cache.BaseCache`
- `httpx_cache.SqliteCache`
- `httpx_cache.MemoryCache`
- `httpx_cache.FileCache`
- `httpx_cache.RedisCache`

## Models, Keys & Exceptions

- `httpx_cache.CacheEntry`
- `httpx_cache.CacheStats`
- `httpx_cache.CacheMissError`
- `httpx_cache.PolicyController`
- `httpx_cache.default_key_fn`
