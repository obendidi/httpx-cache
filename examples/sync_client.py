import logging

import httpx
from httpx._utils import get_logger

from httpx_cache import CacheControlTransport

logging.basicConfig(level="TRACE")
logger = get_logger("example-sync")


def main():

    client = httpx.Client(
        transport=CacheControlTransport(), base_url="https://httpbin.org/"
    )
    logger.info("Sending a first /get request ...")
    response = client.get("/get", params={"la": "lo", "li": "lu"})
    logger.info(f"Got response: {response}")

    logger.info("Sending a second /get request ...")
    response2 = client.get("/get", params={"la": "lo", "li": "lu"})
    logger.info(f"Got response: {response2}")
    client.close()


if __name__ == "__main__":
    main()
