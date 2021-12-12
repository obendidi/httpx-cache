import typing as tp

import attr
import httpx
from httpx._utils import get_logger

from httpx_cache.utils import parse_cache_control_headers

logger = get_logger(__name__)


@attr.s
class CacheControlTransportMixin:

    cacheable_methods: tp.Tuple[str, ...] = attr.ib(kw_only=True, default=("GET",))
    cacheable_status_codes: tp.Tuple[int, ...] = attr.ib(
        kw_only=True,
        default=(
            200,
            203,
            300,
            301,
            308,
        ),
    )

    def is_request_cacheable(self, request: httpx.Request) -> bool:
        if request.url.is_relative_url:
            logger.trace("Only absolute urls are supported, skipping cache!")
            return False
        if request.method not in self.cacheable_methods:
            logger.trace(
                f"Request method '{request.method}' is not supported, skipping cache!"
            )
            return False

        cache_control = parse_cache_control_headers(request.headers)
        if "no-cache" in cache_control:
            logger.trace("Request header has 'no-cache', skipping cache!")
            return False

        if "no-store" in cache_control:
            logger.debug("Request header has 'no-store', skipping cache!")
            return False

        if cache_control.get("max-age") == 0:
            logger.trace("Request header has 'max-age' as 0, skipping cache!")
            return False

        return True

    def is_response_cacheable(self, response: httpx.Response) -> bool:
        if response.status_code not in self.cacheable_status_codes:
            logger.trace(
                f"Response has a non cacheable status code '{response.status_code}', "
                "skipping cache!"
            )
            return False
        cache_control = parse_cache_control_headers(response.headers)

        if "no-store" in cache_control:
            logger.debug("Response header has 'no-store', skipping cache!")
            return False

        return True
