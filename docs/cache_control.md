# Cache Control

By defaults `httpx-cache` caches every response that:

- has a cacheable status_code in `(200, 203, 300, 301, 308)` (can be modified)
- corresponding request has a cacheable method in `('GET',)` (can be modified)
- corresponding request has an absolute url

Enabling/Disabling cache can also be configured at the operation level using `cache-control` headers directives ([https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control))


## Disable Checking Cache

Disabling cache on a particular request can be achieved by setting either the `cache-control: no-cache` or `cache-control: max-age=0` headers.

> The `no-cache` request directive asks caches to validate the response with the origin server before reuse. `no-cache` allows clients to request the most up-to-date response even if the cache has a fresh response. Browsers usually add no-cache to requests when users are force reloading a page.

```py
import httpx_cache

with httpx_cache.Client() as client:
  response1 = client.get("https://httpbin.org/get") # will be cached
  response2 = client.get("https://httpbin.org/get", headers={"cache-control": "no-cache"})
  # will NOT get it from cache, but it will make a new request that then will be re-cached again (refreched in the cache)
```

## Disable Storing in Cache

Sometimes we want to make a request but not store a response in cache. So that we always get the freshest response. This can be achieved with `cache-control: no-store` header.

> The no-store response/request directive indicates that any caches of any kind (private or shared) should not store this response.

**NOTE**: a `no-store` cache-control directive can also be set on the response headers by the server, in that case it will not be cached too.

```py
import httpx_cache

with httpx_cache.Client() as client:
  response1 = client.get("https://httpbin.org/get", headers={"cache-control": "no-cache"}) # will not be stored in cache
  response2 = client.get("https://httpbin.org/get")
  # cache is empty since previous request was not stored, will make a new request.
```

## Cache Expiration

### Max-Age Directive

Cache expiration can be controlled with the request (or response) `max-age` direvtive (directives found in a request take precedence over those in a response.)

> The `max-age=N` request or response directive indicates that the client allows a stored response that is generated on the origin server within N seconds. Ff the response with `cache-control: max-age=604800` was stored in caches 3 hours ago, `httpx-cache` couldn't reuse that response.

```py
import httpx_cache
import time

with httpx_cache.Client() as client:
  response1 = client.get("https://httpbin.org/get") # store in cache at time T
  time.sleep(10) # sleep for 10s (T+10)
  response2 = client.get("https://httpbin.org/get", headers={"cache-control": "max-age=5"}) # response in cache has expried since T+5 < T+10
  # cached response will be deleted
```

### Expires Header

In addition to the `max-age` directive, we can achieve the same effect with the `expires` header.
