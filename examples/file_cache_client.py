import logging
from pathlib import Path

from rich.logging import RichHandler

import httpx_cache

logging.basicConfig(
    level="DEBUG", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)
logger = logging.getLogger("httpx_cache.example")
cache_dir = Path(__file__).parent.absolute() / "__cache__"
logger.info(f"Cache directory is: {cache_dir}")

with httpx_cache.Client(
    base_url="https://httpbin.org/",
    cache=httpx_cache.FileCache(
        serializer=httpx_cache.BytesJsonSerializer(), cache_dir=cache_dir
    ),
) as client:
    logger.info("Running first request ...")
    resp1 = client.get("/get", params={"num": "1"})
    logger.info("Running second request ...")
    resp2 = client.get("/get", params={"num": "1"})
