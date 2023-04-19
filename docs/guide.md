# User Guide

`httpx-cache` provides:

- A sync/async `httpx` compatible caching client and/or transport.
- Support for an in memeory dict cache and a file cache.
- Support for different serializers: dict, str, bytes, msgpack

## Client

`httpx` recommends usig a client instance of anything more that experimentation, one-off scripts, or prototypes.

Caching is one such advanced use cases, that's why `httpx-cache` provides it's own Custom client **that has exactly the same features** as the original `httpx.Client` (inherits from the `httpx.Client` class), but wraps the default (or custom) transport in an `httpx_cache.CacheControlTransport`.

### Usage with Default Values

Excluding the caching algorithms, `httpx_cache.Client` (or `AsyncClient`) behaves similary to `httpx.Client` (or `AsyncClient`).

For caching, `httpx_cache.Client` adds 3 new key-args to the table:

- `cache`: An optional value for which cache type to use, defaults to an in-memory dict cache if not provided.
- `cacheable_methods`: tuple of str http methods that support caching (if a request does not use one of these methods, it's corresponding response will not be cached), defaults to `('GET',)`
- `cacheable_status_codes`: tuple of int http status codes that supports caching (if response does not have one of these status codes, it will not be cached), defaults to: `(200, 203, 300, 301, 308)`
- `always_cache`: bool, if True, all **valid** responses will be cached, regardless of the `no-store` directive set in either the request or response, defaults to False.

Example usage:

```py
import httpx_cache

with httpx_cache.Client() as client:
  response1 = client.get("https://httpbin.org/get") # will be cached
  response2 = client.get("https://httpbin.org/get") # will get it from cache
```

### AsyncClient

Same as `httpx.AsyncClient`, `httpx_cache` also provides an `httpx_cache.AsyncClient` that supports samencaching args as `httpx_cache.Client`.

```py
import httpx_cache

async with httpx_cache.AsyncClient() as client:
  response1 = await client.get("https://httpbin.org/get") # will be cached
  response2 = await client.get("https://httpbin.org/get") # will get it from cache
```

### Response Stream

When using a streaming response, the response will not be cached until the stream is fully consumed. The reason being that to cache a response we need it to have a content property and this content is set only when the user has fully consumed the stream.

(httpx_cache handles this automatically with a callback, it should have no effect on the user usual routines when using a stream.)

```py
import logging
import tempfile

import rich.progress
from rich.logging import RichHandler

import httpx_cache

logging.basicConfig(
    level="DEBUG", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)
logger = logging.getLogger("httpx_cache.example")

with tempfile.NamedTemporaryFile() as download_file:
    url = "https://speed.hetzner.de/100MB.bin"
    with httpx_cache.Client() as client:
        logger.info(f"Running '{url}' download for the first time ...")
        with client.stream("GET", url) as response:
            total = int(response.headers["Content-Length"])
            logger.info(
                "A streaming response is cached only after the stream is consumed."
            )
            with rich.progress.Progress(
                "[progress.percentage]{task.percentage:>3.0f}%",
                rich.progress.BarColumn(bar_width=None),
                rich.progress.DownloadColumn(),
                rich.progress.TransferSpeedColumn(),
                rich.progress.TimeElapsedColumn(),
            ) as progress:
                download_task = progress.add_task("Download", total=total)
                for chunk in response.iter_bytes():
                    download_file.write(chunk)
                    progress.update(
                        download_task, completed=response.num_bytes_downloaded
                    )
        logger.info(f"Running same '{url}' download for the second time ...")
        logger.info(
            "The response is cached so it should take 0 seconds to iter over "
            "the bin again !"
        )
        with client.stream("GET", url) as response2:
            total = int(response2.headers["Content-Length"])
            with rich.progress.Progress(
                "[progress.percentage]{task.percentage:>3.0f}%",
                rich.progress.BarColumn(bar_width=None),
                rich.progress.DownloadColumn(),
                rich.progress.TransferSpeedColumn(),
                rich.progress.TimeElapsedColumn(),
            ) as progress:
                download_task = progress.add_task("Download", total=total)
                for chunk in response2.iter_bytes():
                    download_file.write(chunk)
                    progress.update(
                        download_task, completed=response2.num_bytes_downloaded
                    )
```

_(This script is complete, it should run "as is")_

## Transport

If you prefer to use the original httpx Client, `httpx-cache` also provides a transport that can be used dircetly with it:

The custom caching transport is created following the guilelines [here](https://www.python-httpx.org/advanced/#custom-transports).

The `(Async-)CacheControlTransport` also accepts the 3 key-args:

- `cache`: An optional value for which cache type to use, defaults to an in-memory dict cache if not provided.
- `cacheable_methods`: tuple of str http methods that support caching (if a request does not use one of these methods, it's corresponding response will not be cached), defaults to `('GET',)`
- `cacheable_status_codes`: tuple of int http status codes that supports caching (if response does not have one of these status codes, it will not be cached), defaults to: `(200, 203, 300, 301, 308)`

```py
import httpx
import httpx_cache

with httpx.Client(transport=httpx_cache.CacheControlTransport()) as client:
  response = client.get("https://httpbin.org/get")

# async with httpx.AsyncClient(transport=httpx_cache.AsyncCacheControlTransport()) as client:
#   response = await client.get("https://httpbin.org/get")
```

## Cache Types

### DictCache (default)

In-memory dict cache:

```py
import httpx
import httpx_cache

with httpx_cache.Client(cache=httpx_cache.DictCache()) as client:
  response = client.get("https://httpbin.org/get")
```

### FileCache

```py
import httpx_cache

with httpx_cache.Client(cache=httpx_cache.FileCache()) as client:
  response = client.get("https://httpbin.org/get")
```

By default the cached files will be saved in `$HOME/.cache/httpx-cache` folder.

It can be customized using the argument: `cache_dir`:

```py
import httpx_cache

with httpx_cache.Client(cache=httpx_cache.FileCache(cache_dir="./my-custom-dir")) as client:
  response = client.get("https://httpbin.org/get")
```

### RedisCache

You need to install `redis` package to use this cache type, or install `httpx-cache[redis]` to install it automatically.

```py
import httpx_cache
from httpx_cache.cache.redis import RedisCache

with httpx_cache.Client(cache=RedisCache(redis_url="redis://localhost:6379/0")) as client:
  response = client.get("https://httpbin.org/get")
```

By default all cached responses are saved under the namespace `htppx_cache`.

Optionally a TTL can be provided so that the cached responses expire after the given time (as a python timedelta).

It can also accepts direct instances of `redis.Redis` or `redis.StrictRedis` clients.

```py
import httpx_cache
from redis import Redis
from httpx_cache.cache.redis import RedisCache

redis_client = Redis(host="localhost", port=6379, db=0)
cache = RedisCache(redis=redis_client, namespace="my-custom-namespace", default_ttl=timedelta(hours=1))

with httpx_cache.Client(cache=cache) as client:
  response = client.get("https://httpbin.org/get")
```

## Serializer Types

Before caching an httpx.Response it needs to be serialized to a cacheable format supported by the used cache type (Dict/File).

|     Serializer       |      DictCache     |     FileCache      |     RedisCache     |
| -------------------- | ------------------ | ------------------ | ------------------ |
| DictSerializer       | :white_check_mark: |       :x:          |       :x:          |
| StringJsonSerializer | :white_check_mark: |       :x:          |       :x:          |
| BytesJsonSerializer  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| MsgPackSerializer    | :white_check_mark: | :white_check_mark: | :white_check_mark: |

A custom serializer can be used anytime with:

```py
import httpx_cache

with httpx.Client(cache=httpx_cache.DictCache(serializer=httpx_cache.DictSerializer())) as client:
  response = client.get("https://httpbin.org/get")
```

`httpx-cache` provides the following serializers:

### DictSerializer

The base serializer used in all other serializers, converts an `httpx.Response` object into python dict that represents the response. The idea is that using the created dict we should be able to recreate exactly the same response.

The serialized dict has the following elements:

```json
{
  "status_code": "int, required, status code of the response",
  "headers": "List[Tuple[str, str]], required, list of headers of the original response, can be an empty list",
  "encoding": "str, optional, encoding of the response if not Null",
  "_content": "bytes, optional, content of the response if exists (usually if stream is consumed, or response originally has just a basic content), if not found, 'stream_content' should be provided.",
  "stream_content": "bytes, optional, in case the response contains a stream that is loaded only after the transport finishies his work, will be converted to an httpx.BytesStream when recreating the response."
}
```

### StringJsonSerializer

Inherits from `DictSerializer`, this is the result of `json.dumps` of the above generated dict.

### BytesJsonSerializer

Inherits from `StringJsonSerializer`, `utf-8` encoded json string.

### MsgPackSerializer (default)

Inherits from `DictSerializer`, this is the result of `msgpack.dumps` of the above generated dict.
