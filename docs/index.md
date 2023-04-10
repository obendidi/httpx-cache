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

To use `RedisCache`, install with `redis` extra:

```sh
$ pip install httpx-cache[redis]
```

Requires Python 3.6+ and HTTPX 0.21+.

## Quickstart

### Usage with Client

```py
import httpx_cache

with httpx_cache.Client() as client:
  response = client.get("https://httpbin.org/get")
```

### Usage with AsyncClient

```py
import httpx_cache

async with httpx_cache.AsyncClient() as client:
  response = await client.get("https://httpbin.org/get")
```

When using `httpx-cache.Client`/`httpx_cache.AsyncClient`, the interface and features (except caching) are exactly the same as `httpx.Client`/`httpx.AsyncClient`

> Read the [User Guide](./guide.md) for a complete walk-through.

## Supported Cache Types and Serializers

|     Serializer       |      DictCache     |     FileCache      |     RedisCache     |
| -------------------- | ------------------ | ------------------ | ------------------ |
| DictSerializer       | :white_check_mark: |       :x:          |       :x:          |
| StringJsonSerializer | :white_check_mark: |       :x:          |       :x:          |
| BytesJsonSerializer  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| MsgPackSerializer    | :white_check_mark: | :white_check_mark: | :white_check_mark: |
