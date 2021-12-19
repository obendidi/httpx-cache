# HTTPX-CACHE

## Quickstart

httpx-cache is a simple utility for caching (sync/async) responses from httpx.

It provides a custom transport that can be used with any httpx Client.

```py
import httpx
import httpx_cache

transport = httpx_cache.CacheControlTransport()
with httpx.Client(transport=transport) as client:
  response = client.get("https://httpbin.org/get")
```

> Read the [User Guide](./guide.md) for a complete walk-through.

## Installation

Install with pip:

```sh
$ pip install httpx-cache
```

Requires Python 3.6+ and HTTPX 0.21+.
