import asyncio

import httpx

import httpx_cache


async def main() -> None:
    cache = httpx_cache.SqliteCache(":memory:")
    async with httpx_cache.wrap(httpx.AsyncClient(), cache=cache, policy="force", ttl=60) as client:
        r1 = await client.get("https://httpbin.org/get")
        r2 = await client.get("https://httpbin.org/get")
        print("first from_cache:", r1.extensions["from_cache"])
        print("second from_cache:", r2.extensions["from_cache"])
        print("stats:", await cache.astats())
    await cache.aclose()


if __name__ == "__main__":
    asyncio.run(main())
