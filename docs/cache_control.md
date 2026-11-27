# Policies & RFC 9111

`httpx-cache` v1.0 provides three explicit policies:

## 1. `policy="force"` (default)

- Ignores `Cache-Control: no-store`, `private`, `no-cache`, and `max-age=0`.
- Caches `GET` and `HEAD` by default; pass `cache_post=True` (or `cacheable_methods=...`) to cache `POST` requests keyed by SHA-256 of the request body.
- Set `ttl` (seconds or `timedelta`) for fixed expiration, or `ttl=None` to keep entries until evicted/cleared.

## 2. `policy="replay"`

- Strictly offline deterministic playback for unit tests and eval suites.
- Never calls the upstream transport.
- Ignores store TTL expiry so recorded cassettes stay reproducible over time.
- Raises `httpx_cache.CacheMissError(key, request)` on any unrecorded request.

## 3. `policy="rfc9111"`

- Honors `Cache-Control` (`no-store`, `no-cache`, `max-age`, `s-maxage`, `min-fresh`, `private` when `shared=True`), `Expires`, `Date`, `Age`, `Vary` (including rejecting `Vary: *`), and permanent redirects (`301`/`308`).
- Performs conditional revalidation with `If-None-Match` (`ETag`) and `If-Modified-Since` (`Last-Modified`). On `304 Not Modified`, headers are merged into the cached entry and the response is returned with `response.extensions["from_cache"] = True` and `response.extensions["revalidated"] = True`.
