# HTTPX-CACHE

httpx-cache is an implementation of the caching algorithms in [httplib2](https://github.com/httplib2/httplib2) and [CacheControl](https://github.com/ionrock/cachecontrol) for use with [httpx](https://github.com/encode/httpx) transport object.

It is is heavily insipired by:

- [https://github.com/ionrock/cachecontrol](https://github.com/ionrock/cachecontrol)
- [https://github.com/johtso/httpx-caching](https://github.com/johtso/httpx-caching)

## Installation

Install with pip:

```sh
$ pip install httpx-cache
```

Requires Python 3.6+ and HTTPX 0.21+.

## Quickstart

### Usage with Client

```py
import httpx
import httpx_cache

# create a default httpx_cache transport (by default it's a sync transport)
transport = httpx_cache.CacheControlTransport()

# use the httpx client with our httpx_cache transport, and that's it!
with httpx.Client(transport=transport) as client:
  response = client.get("https://httpbin.org/get")
```

### Usage with AsyncClient

```py
import httpx
import httpx_cache

# create a an async cache-control transport
# equivalent to: transport = httpx_cache.CacheControlTransport(transport=httpx.AsyncHTTPTransport())
transport = httpx_cache.AsyncCacheControlTransport()

# use the httpx client with our httpx_cache transport, and that's it!
async with httpx.AsyncClient(transport=transport) as client:
  response = await client.get("https://httpbin.org/get")
```

### Usage with custom httpx transport

httpx_cache can be used with any httpx transport as long as it supports the basic methods for an httpx transport (`handle_request`, `handle_async_request`, ..):

```py
import httpx
import httpx_cache

# create an AsyncHTTPTransport with custom args
# NOTE: an AsyncHTTPTransport should be used with an AsyncCacheControlTransport
my_custom_transport = httpx.AsyncHTTPTransport(verify=False, http2=True, retries=10)

# create a an async cache-control transport
transport = httpx_cache.AsyncCacheControlTransport(transport=my_custom_transport)

# use the httpx client with our httpx_cache transport, and that's it!
async with httpx.AsyncClient(transport=transport) as client:
  response = await client.get("https://httpbin.org/get")
```

> Read the [User Guide](./guide.md) for a complete walk-through.
