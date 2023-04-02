import logging
import typing as tp
from datetime import datetime, timedelta, timezone

import httpx

from httpx_cache.utils import parse_cache_control_headers, parse_headers_date

logger = logging.getLogger(__name__)

_PERMANENT_REDIRECT_STATUSES = (301, 308)


class CacheControl:
    """Cache controller for httpx-cache.

    Uses 'cache-contol' header direcrives for using/skipping cache.

    If no cache-control directive is set, the cache is used by default (except if there
    is an expires header in the response.)
    """

    def __init__(
        self,
        *,
        cacheable_methods: tp.Tuple[str, ...] = ("GET",),
        cacheable_status_codes: tp.Tuple[int, ...] = (200, 203, 300, 301, 308),
        always_cache: bool = False,
    ) -> None:
        self.cacheable_methods = cacheable_methods
        self.cacheable_status_codes = cacheable_status_codes
        self.always_cache = always_cache

    def is_request_cacheable(self, request: httpx.Request) -> bool:
        """Checks if an httpx request has the necessary requirement to support caching.

        A request is cacheable if:

            - url is absolute
            - method is defined as cacheable (by default only GET methods are cached)
            - request has no 'no-cache' cache-control header directive
            - request has no 'max-age=0' cache-control header directive

        Args:
            request: httpx.Request

        Returns:
            True if request cacheable else False
        """
        if request.url.is_relative_url:
            logger.debug(
                f"Only absolute urls are supported, got '{request.url}'. "
                "Request is not cacheable!"
            )
            return False
        if request.method not in self.cacheable_methods:
            logger.debug(
                f"Request method '{request.method}' is not supported, only "
                f"'{self.cacheable_methods}' are supported. Request is not cacheable!"
            )
            return False
        cc = parse_cache_control_headers(request.headers)
        if "no-cache" in cc or cc.get("max-age") == 0:
            logger.debug(
                "Request cache-control headers has a 'no-cache' directive. "
                "Request is not cacheable!"
            )
            return False
        return True

    def is_response_fresh(
        self, *, request: httpx.Request, response: httpx.Response
    ) -> bool:
        """Checks wether a cached response is fresh or not.

        Args:
            request: httpx.Request
            response: httpx.Response

        Returns:
            True if request is fresh else False
        """

        # check if response is a permanenet redirect
        if response.status_code in _PERMANENT_REDIRECT_STATUSES:
            logger.debug(
                "Cached response with permanent redirect status "
                f"'{response.status_code}' is always fresh."
            )
            return True

        # check that we do have a response Date header
        response_date = parse_headers_date(response.headers.get("date"))

        # extract cache_control for both request and response
        request_cc = parse_cache_control_headers(request.headers)
        response_cc = parse_cache_control_headers(response.headers)

        # get all values we need for freshness eval
        resp_max_age = response_cc.get("max-age")
        req_min_fresh = request_cc.get("min-fresh")
        req_max_age = request_cc.get("max-age")

        # check max-age in response
        if isinstance(req_max_age, int):
            max_freshness_age = timedelta(seconds=req_max_age)
            logger.debug(
                "Evaluating response freshness from request cache-control "
                "'max-age' header directive."
            )

        elif isinstance(resp_max_age, int):
            max_freshness_age = timedelta(seconds=resp_max_age)
            logger.debug(
                "Evaluating response freshness from response cache-control "
                "'max-age' header directive."
            )
        elif "expires" in response.headers and response_date is None:
            logger.warning(
                "Response is missing a valid 'Date' header, couldn't evaluate "
                "response freshness. Response is not fresh!"
            )
            return False
        elif "expires" in response.headers:
            resp_expires = parse_headers_date(response.headers.get("expires"))
            if resp_expires is None:
                logger.warning(
                    "Response has an invalid 'Expires' header, couldn't evaluate "
                    "response freshness. Response is not fresh!"
                )
                return False

            max_freshness_age = resp_expires - response_date  # type: ignore
            logger.debug(
                "Evaluating response freshness from response 'expires' header."
            )

        else:
            logger.debug(
                "Request/Response pair has no cache-control headers. Assuming "
                "response is fresh!"
            )
            return True

        if response_date is None:
            logger.warning(
                "Response is missing a valid 'Date' header, couldn't evaluate "
                "response freshness. Response is not fresh!"
            )
            return False

        # get response age (timedelta)
        now = datetime.now(tz=timezone.utc)
        response_age = now - response_date
        if isinstance(req_min_fresh, int):
            logger.debug(
                f"Adjsting response age ({response_age}) using request cache-control "
                "'min-fresh' header directive."
            )
            response_age += timedelta(seconds=req_min_fresh)

        logger.debug(f"Response age is: {response_age}")
        logger.debug(f"Response allowed max-age is: {max_freshness_age}")

        if response_age > max_freshness_age:
            logger.debug("Response is not fresh!")
            return False

        logger.debug("Response is fresh.")
        return True

    def is_response_cacheable(
        self, *, request: httpx.Request, response: httpx.Response
    ) -> bool:
        """Check if an httpx response is cacheable.

        A respons is cacheable if:

            - response status_code is cacheable
            - request method is cacheable
            - One of:
                - always_cache is True
            OR:
                - Response has no 'no-store' cache-control header
                - Request has no 'no-store' cache-control header

        Args:
            request: httpx.Request
            response: httpx.Response

        Returns:
            wether response is cacheable or not.
        """
        if request.url.is_relative_url:
            logger.debug(
                f"Only absolute urls are supported, got '{request.url}'. "
                "Request is not cacheable!"
            )
            return False

        if request.method not in self.cacheable_methods:
            logger.debug(
                f"Request method '{request.method}' is not supported, only "
                f"'{self.cacheable_methods}' are supported. Request is not cacheable!"
            )
            return False

        if response.status_code not in self.cacheable_status_codes:
            logger.debug(
                f"Response status_code '{response.status_code}' is not cacheable, only "
                f"'{self.cacheable_status_codes}' are cacheable. Response is not "
                "cacheable!"
            )
            return False

        # always cache request, eevent if 'no-store' is set as header
        if self.always_cache:
            logger.debug("Caching Response because 'always_cache' is set to True.'")
            return True

        # extract cache_control for both request and response
        request_cc = parse_cache_control_headers(request.headers)
        response_cc = parse_cache_control_headers(response.headers)

        if "no-store" in request_cc or "no-store" in response_cc:
            logger.debug(
                "Request/Response cache-control headers has a 'no-store' directive. "
                "Response is not cacheable!"
            )
            return False

        return True
