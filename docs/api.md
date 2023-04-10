# API documentation

## Client

::: httpx_cache.Client
    :docstring:
    :members:

::: httpx_cache.AsyncClient
    :docstring:
    :members:

## Transport

::: httpx_cache.CacheControlTransport
    :docstring:
    :members:

::: httpx_cache.AsyncCacheControlTransport
    :docstring:
    :members:

## CacheControl

::: httpx_cache.CacheControl
    :docstring:
    :members:

## Cache

::: httpx_cache.DictCache
    :docstring:
    :members:

::: httpx_cache.FileCache
    :docstring:
    :members:

::: httpx_cache.cache.redis.RedisCache
    :docstring:
    :members:

!!! **Note** FileCache and RedisCache only supports `httpx_cache.MsgPackSerializer` and `httpx_cache.BytesJsonSerializer` serializers.

## Serializer

::: httpx_cache.DictSerializer
    :docstring:
    :members:

::: httpx_cache.StringJsonSerializer
    :docstring:
    :members:

::: httpx_cache.BytesJsonSerializer
    :docstring:
    :members:

::: httpx_cache.MsgPackSerializer
    :docstring:
    :members:
