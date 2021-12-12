import asyncio
import logging

import httpx
from httpx._utils import get_logger

from httpx_cache import AsyncCacheControlTransport

logging.basicConfig(level="TRACE")
logger = get_logger("example-sync")


async def main():

    client = httpx.AsyncClient(
        transport=AsyncCacheControlTransport(), base_url="https://httpbin.org/"
    )
    logger.info("Sending a first /get request ...")
    response = await client.get("/get", params={"la": "lo", "li": "lu"})
    logger.info(f"Got response: {response}")

    logger.info("Sending a second /get request ...")
    response2 = await client.get("/get", params={"la": "lo", "li": "lu"})
    logger.info(f"Got response: {response2}")
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
