# User Guide

httpx-cache provides a sync/async cache transport that can be configured to use multiple cache types and serializers

## Usage with httpx.Client

```py
import httpx
import httpx_cache

transport = httpx_cache.CacheControlTransport()
with httpx.Client(transport=transport) as client:
  response = client.get("https://httpbin.org/get")
```

> The created **transport** behaves the same way as the default `httpx.HTTPTransport` with defauls args and kwargs.

> By default the cache is stored in memory in a python dict and serialzed using `MsgPack`.

## Usage with httpx.AsyncClient

```py
import httpx
import httpx_cache

transport = httpx_cache.AsyncCacheControlTransport()
with httpx.AsyncClient(transport=transport) as client:
  response = await client.get("https://httpbin.org/get")
```

> The created **transport** behaves the same way as the default `httpx.AsyncHTTPTransport` with defauls args and kwargs.

> By default the cache is stored in memory in a python dict and serialzed using `MsgPack`.

## Cache

2 types of caches are supported for the time being:

### Dictcache/AsyncDictCache

```py
import httpx_cache

transport = httpx_cache.CacheControlTransport(cache=httpx_cache.DictCache())

async_transport = httpx_cache.AsyncCacheControlTransport(cache=httpx_cache.AsyncDictCache())
```

a DictCache can also take a dict with initial data as input but it's not recommended.

### FileCache/AsyncFileCache

```py
import httpx_cache

transport = httpx_cache.CacheControlTransport(cache=httpx_cache.FileCache())

async_transport = httpx_cache.AsyncCacheControlTransport(cache=httpx_cache.AsyncFileCache())
```

By default the cached files will be saved in `$HOME/.cache/httpx-cache` folder.

It can be customized using the argument: `cache_dir`
