# httpx-cache

Zero-config, minimal-dependency response caching and deterministic replay for `httpx` and `httpx2`.

## Installation

```bash
pip install httpx-cache            # when httpx or httpx2 is already installed
pip install "httpx-cache[httpx]"   # install with httpx
pip install "httpx-cache[httpx2]"  # install with httpx2
pip install "httpx-cache[redis]"   # install with RedisCache support
```

Requires Python 3.10+ (`httpx2>=2.15` requires Python 3.11+).

## Quickstart

```python
import httpx, httpx_cache

client = httpx_cache.wrap(httpx.Client(), policy="force", ttl=3600)
r1 = client.get("https://httpbin.org/get")
r2 = client.get("https://httpbin.org/get")
assert r1.extensions["from_cache"] is False
assert r2.extensions["from_cache"] is True
```

See the [User Guide](./guide.md), [Policies & RFC 9111](./cache_control.md), [API Reference](./api.md), and [llms.txt](./llms.txt).
