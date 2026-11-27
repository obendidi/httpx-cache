import httpx

import httpx_cache

cache = httpx_cache.FileCache("./.example-file-cache")
with httpx_cache.wrap(httpx.Client(), cache=cache, policy="force", ttl=3600) as client:
    r1 = client.get("https://httpbin.org/get")
    r2 = client.get("https://httpbin.org/get")
    print("first from_cache:", r1.extensions["from_cache"])
    print("second from_cache:", r2.extensions["from_cache"])
    print("stats:", cache.stats())
