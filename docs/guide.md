# User Guide

`httpx-cache` provides:

- A sync/async `httpx` compatible cache transport.
- Support for an in memeory dict cache and a file cache.
- Support for different serializers: dict, str, bytes, msgpack

## Transport

When doing anything more than experimentation, one-off scripts, or prototypes, `httpx` recommends using a Client instance. More on that [here](https://www.python-httpx.org/advanced/#why-use-a-client).

Luckilly for us `httpx` allows us to use custom transports for more advanced usage (like cache-control for example), more on that [here](https://www.python-httpx.org/advanced/#custom-transports).

`httpx-cache` provides it's own custom transport (that is fully compatible with `httpx`) with `httpx_cache.CacheControlTransport`.

### Usage

#### Defaults (HTTPTransport and DictCache)

When using the `httpx_cache.CacheControlTransport` with default arguments it will behave similiray to an `httpx.HTTPTransport` (also with default args, warning: they may change across `httpx` versions), with the added cache benefit of course :).

In addition to the default transport, `CacheControlTransport` also creates a default in-memory `DictCache` for storing cached responses

```py
import httpx
import httpx_cache

transport = httpx_cache.CacheControlTransport() # same as httpx.HTTPTransport()
with httpx.Client(transport=transport) as client:
  response = client.get("https://httpbin.org/get")
```

#### Custom Transport

It is possible to provide a custom transport to the `CacheControlTransport` transport.

A use-case is if we want to use an Async transport:

```py
import httpx
import httpx_cache

# we setup the the AsyncTransport of httpx
transport = httpx_cache.CacheControlTransport(transport=httpx.AsyncHTTPTransport())

# use an async client since we use an async transport
async with httpx.AsyncClient(transport=transport) as client:
  response = await client.get("https://httpbin.org/get")
```

Another use case is when there is a need to modify the args of httpx default transports:

```py
import httpx
import httpx_cache

# we setup the the AsyncTransport of httpx
transport = httpx_cache.AsyncCacheControlTransport(transport=httpx.AsyncHTTPTransport(verify=False, http2=True))

# use an async client since we use an async transport
async with httpx.AsyncClient(transport=transport) as client:
  response = await client.get("https://httpbin.org/get")
```

> Any other custom transport is also supported as long as they follow the `httpx` docs on [writing custom transports](https://www.python-httpx.org/advanced/#writing-custom-transports)

#### AsyncCacheControlTransport

Instead of having to each time create a custom transport for async usage, `httpx-cache` provides an `AsyncCacheControlTransport` for that:

(if we take the example from above)

```py
import httpx
import httpx_cache

# we setup the the AsyncTransport of httpx
# transport = httpx_cache.CacheControlTransport(transport=httpx.AsyncHTTPTransport())
transport = httpx_cache.AsyncCacheControlTransport()

# use an async client since we use an async transport
async with httpx.AsyncClient(transport=transport) as client:
  response = await client.get("https://httpbin.org/get")
```

## Cache Types

httpx-cache supports 2 types of caches:

### DictCache (defaults)

```py
import httpx
import httpx_cache

transport = httpx_cache.CacheControlTransport(cache=httpx_cache.DictCache())

with httpx.Client(transport=transport) as client:
  response = client.get("https://httpbin.org/get")
```

### FileCache

```py
import httpx
import httpx_cache

transport = httpx_cache.CacheControlTransport(cache=httpx_cache.FileCache())

with httpx.Client(transport=transport) as client:
  response = client.get("https://httpbin.org/get")
```

By default the cached files will be saved in `$HOME/.cache/httpx-cache` folder.

It can be customized using the argument: `cache_dir`:

```py
import httpx
import httpx_cache

transport = httpx_cache.CacheControlTransport(cache=httpx_cache.FileCache(cache_dir="./my-custom-dir"))

with httpx.Client(transport=transport) as client:
  response = client.get("https://httpbin.org/get")
```

## Serializer Types

Before caching an httpx.Response it needs to be serialized to a cacheable format supported by de cache type (Dict/File).

`httpx-cache` provides the following serializers:

### DictSerializer
### StringJsonSerializer

### BytesJsonSerializer
### MsgPackSerializer (default)
