import httpx

import httpx_cache

cache = httpx_cache.MemoryCache(max_entries=100)
with httpx_cache.wrap(httpx.Client(), cache=cache, policy="force", ttl=60) as client:
    r1 = client.get("https://httpbin.org/get")
    r2 = client.get("https://httpbin.org/get")
    print("first from_cache:", r1.extensions["from_cache"])
    print("second from_cache:", r2.extensions["from_cache"])
    print("stats:", cache.stats())
