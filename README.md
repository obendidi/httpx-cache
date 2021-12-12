# HTTPX-CACHE

[![codecov](https://codecov.io/gh/bendidi/httpx-cache/branch/main/graph/badge.svg?token=FHHRA6F17X)](https://codecov.io/gh/bendidi/httpx-cache)

Note: Early development / alpha, use at your own risk.

httpx-cache is yet another implementation/port is a port of the caching algorithms in httplib2 for use with httpx Transport object.

It is is heavily insipired by:

- [https://github.com/ionrock/cachecontrol](https://github.com/ionrock/cachecontrol)
- [https://github.com/johtso/httpx-caching](https://github.com/johtso/httpx-caching)

This project supports the latest version of httpx (at of the time of writing): `httpx@0.21.1`, when `httpx` releases a v1 version, the update should be straithforward for this project.

## TODO

- [ ] support etags
- [ ] support cache expiry dates
- [ ] support file cach
- [ ] support redis (sync/async) cache

## Features

- In memory dict cache store
- Support for cache-controle headers
- Sync cache transport for httpx
- Async cache transport for httpx

## Quickstart

The lib provides an `httpx` compliant transport that you can use instead of the the defult one when creating your `httpx` client:

```py
import httpx

from httpx_cache import CacheControlTransport

with httpx.Client(transport=CacheControlTransport()) as client:
  response = client.get("https://httpbin.org/get")

  # the response is effectively cached, calling teh same request with return a response from the cache

  response2 = client.get("https://httpbin.org/get")
```

You can also wrap an existing transport with `CacheControlTransport`. The `CacheControlTransport` will use the existing transport for making the request call and then cach the result if it satisfies the cache-control headers.

```py
import httpx

from httpx_cache import CacheControlTransport

my_transport = httpx.HTTPTransport(http2=True, verify=False)

with httpx.Client(transport=CacheControlTransport(transport=my_transport)) as client:
  response = client.get("https://httpbin.org/get")

  # the response is effectively cached, calling teh same request with return a response from the cache

  response2 = client.get("https://httpbin.org/get")
```

## Examples

 more examples in [./examples](./examples).
