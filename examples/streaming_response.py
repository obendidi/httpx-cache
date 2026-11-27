import httpx

import httpx_cache

cache = httpx_cache.SqliteCache(":memory:")
with httpx_cache.wrap(httpx.Client(), cache=cache, policy="force") as client:
    with client.stream("GET", "https://httpbin.org/bytes/4096") as r1:
        data1 = b"".join(r1.iter_bytes())
        print("first from_cache:", r1.extensions["from_cache"], "bytes:", len(data1))

    with client.stream("GET", "https://httpbin.org/bytes/4096") as r2:
        data2 = b"".join(r2.iter_bytes())
        print("second from_cache:", r2.extensions["from_cache"], "bytes:", len(data2))
        assert data1 == data2
cache.close()
