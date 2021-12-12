import typing as tp

import httpx
from httpx._utils import get_logger

logger = get_logger(__name__)

# https://tools.ietf.org/html/rfc7234#section-5.2
KNOWN_DIRECTIVES = {
    "max-age": (int, True),
    "max-stale": (int, False),
    "min-fresh": (int, True),
    "no-cache": (None, False),
    "no-store": (None, False),
    "no-transform": (None, False),
    "only-if-cached": (None, False),
    "must-revalidate": (None, False),
    "public": (None, False),
    "private": (None, False),
    "proxy-revalidate": (None, False),
    "s-maxage": (int, True),
}


def parse_cache_control_headers(
    headers: httpx.Headers,
) -> tp.Dict[str, tp.Union[None, int]]:
    """Parse cache-control headers.

    Args:
        headers: An instance of httpx headers.

    Returns:
        parsed cache-control headers as dict.
    """

    parsed_cc: tp.Dict[str, tp.Any] = {}
    directives = headers.get_list("cache-control", split_commas=True)
    for directive in directives:
        name, value = directive.split("=", 1) if "=" in directive else (directive, None)
        if name not in KNOWN_DIRECTIVES:
            logger.debug(f"Unknown cache-control directive: {name}")
            continue
        value_type, required = KNOWN_DIRECTIVES[name]
        if value_type is None or not required:
            parsed_cc[name] = None
        elif value_type is not None:
            if value is not None:
                try:
                    parsed_cc[name] = value_type(value)
                except ValueError:
                    logger.debug(
                        f"Invalid value for cache-control directive: {name}."
                        f"Expected {value_type}, got {value} ({type(value)})"
                    )
            elif value is None and required:
                logger.debug(f"Missing value for cache-control directive: {name}")
    return parsed_cc
