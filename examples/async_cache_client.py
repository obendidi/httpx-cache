import logging

import anyio
from rich.logging import RichHandler

import httpx_cache

logging.basicConfig(
    level="DEBUG", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)
logger = logging.getLogger("httpx_cache.example")


async def main():
    async with httpx_cache.AsyncClient(
        base_url="https://httpbin.org/",
        cache=httpx_cache.DictCache(serializer=httpx_cache.DictSerializer()),
    ) as client:
        logger.info("Running first request ...")
        await client.get("/get", params={"num": "1"})
        logger.info("Running second request ...")
        await client.get("/get", params={"num": "1"})


anyio.run(main)
