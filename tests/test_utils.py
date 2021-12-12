from httpx_cache.utils import parse_cache_control_headers


def test_parse_cache_control_headers(httpx_headers_cache_control):
    headers, expected = httpx_headers_cache_control
    parsed = parse_cache_control_headers(headers)
    assert parsed == expected
