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
