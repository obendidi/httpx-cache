from __future__ import annotations

import fnmatch
import hashlib
import logging
import time
from collections.abc import Mapping, Sequence
from datetime import timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal

from httpx_cache.types import CacheEntry, PolicyName

logger = logging.getLogger(__name__)

DEFAULT_CACHEABLE_METHODS: tuple[str, ...] = ("GET", "HEAD")
DEFAULT_CACHEABLE_STATUS_CODES: tuple[int, ...] = (200, 203, 204, 300, 301, 308)
_PERMANENT_REDIRECT_STATUSES = frozenset((301, 308))
_BODY_LESS_METHODS = frozenset(("GET", "HEAD", "OPTIONS", "TRACE"))
_UNSET = object()

CacheDecision = Literal["fresh", "revalidate", "stale"]


def _normalize_ttl(value: float | timedelta | None) -> float | None:
    if isinstance(value, timedelta):
        seconds: float | None = value.total_seconds()
    elif value is not None:
        seconds = float(value)
    else:
        seconds = None
    if seconds is not None and seconds < 0:
        raise ValueError(f"ttl must be non-negative, got {seconds}")
    return seconds


def parse_cache_control(headers: Any) -> dict[str, str | None]:
    """Parse HTTP Cache-Control header directives into a lowercase mapping."""
    result: dict[str, str | None] = {}
    directives: list[str] = headers.get_list("cache-control", split_commas=True)
    for raw in directives:
        token = raw.strip()
        if not token:
            continue
        if "=" in token:
            name, value = token.split("=", maxsplit=1)
            cleaned = value.strip().strip('"')
            result[name.strip().lower()] = cleaned
        else:
            result[token.lower()] = None
    return result


def parse_http_date(value: str | None) -> float | None:
    """Parse an HTTP-date string into a UTC Unix timestamp, or None if invalid."""
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _parse_non_negative_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _entry_headers_get(headers: tuple[tuple[str, str], ...], name: str) -> str | None:
    target = name.lower()
    for k, v in headers:
        if k.lower() == target:
            return v
    return None


def _entry_cache_control(headers: tuple[tuple[str, str], ...]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for k, v in headers:
        if k.lower() != "cache-control":
            continue
        for raw in v.split(","):
            token = raw.strip()
            if not token:
                continue
            if "=" in token:
                name, value = token.split("=", maxsplit=1)
                result[name.strip().lower()] = value.strip().strip('"')
            else:
                result[token.lower()] = None
    return result


def _entry_has_validators(entry: CacheEntry) -> bool:
    return (
        _entry_headers_get(entry.headers, "etag") is not None
        or _entry_headers_get(entry.headers, "last-modified") is not None
    )


def _vary_header_names(headers: Any) -> tuple[str, ...]:
    names: list[str] = []
    for raw in headers.get_list("vary", split_commas=True):
        token = raw.strip().lower()
        if token and token not in names:
            names.append(token)
    return tuple(sorted(names))


def vary_variant_key(base_key: str, request: Any, vary_headers: Sequence[str]) -> str:
    """Derive a deterministic variant storage key for an RFC 9111 ``Vary`` response."""
    pairs = [
        f"{name}={','.join(request.headers.get_list(name))}"
        for name in sorted({h.lower() for h in vary_headers})
    ]
    digest = hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()[:16]
    return f"{base_key}|vary={digest}"


class PolicyController:
    """Evaluates cacheability, freshness, revalidation, and entry TTL under a policy."""

    def __init__(
        self,
        *,
        policy: PolicyName = "force",
        ttl: float | timedelta | None = None,
        cache_post: bool = False,
        cacheable_methods: Sequence[str] | None = None,
        cacheable_status_codes: Sequence[int] | None = None,
        shared: bool = False,
        urls_expire_after: Mapping[str, float | timedelta | None] | None = None,
        stale_if_error: bool | float | timedelta = False,
        scrub_headers: Sequence[str] = (),
    ) -> None:
        if policy not in ("force", "rfc9111", "replay"):
            raise ValueError(
                f"Invalid policy {policy!r}. Expected one of 'force', 'rfc9111', 'replay'."
            )
        self.policy: PolicyName = policy
        self.shared = shared
        self.ttl: float | None = _normalize_ttl(ttl)

        methods = (
            tuple(m.upper() for m in cacheable_methods)
            if cacheable_methods is not None
            else DEFAULT_CACHEABLE_METHODS
        )
        if cache_post and "POST" not in methods:
            methods = (*methods, "POST")
        self.cacheable_methods: tuple[str, ...] = methods
        self.cacheable_status_codes: tuple[int, ...] = (
            tuple(cacheable_status_codes)
            if cacheable_status_codes is not None
            else DEFAULT_CACHEABLE_STATUS_CODES
        )

        self.urls_expire_after: tuple[tuple[str, float | None], ...] = tuple(
            (pattern, _normalize_ttl(val))
            for pattern, val in (urls_expire_after.items() if urls_expire_after else ())
        )

        if isinstance(stale_if_error, bool):
            self.stale_if_error_enabled = stale_if_error
            self.stale_if_error_window: float | None = None
        else:
            window = _normalize_ttl(stale_if_error)
            self.stale_if_error_enabled = True
            self.stale_if_error_window = window

        self.scrub_headers: frozenset[str] = frozenset(h.lower() for h in scrub_headers)

    def resolve_request_ttl(
        self,
        request: Any,
        *,
        override_ttl: Any = _UNSET,
    ) -> tuple[bool, float | None]:
        """Resolve ``(cache_allowed, ttl_seconds)`` for a request.

        Precedence: per-request extension ``ttl`` > ``urls_expire_after`` > default ``self.ttl``.
        A resolved TTL of ``0`` disables caching for that request.
        """
        if override_ttl is not _UNSET:
            resolved = _normalize_ttl(override_ttl)
            if resolved == 0.0:
                return False, 0.0
            return True, resolved

        if self.urls_expire_after:
            url_str = str(request.url)
            url_path = str(getattr(request.url, "path", ""))
            for pattern, pattern_ttl in self.urls_expire_after:
                if fnmatch.fnmatchcase(url_str, pattern) or (
                    url_path and fnmatch.fnmatchcase(url_path, pattern)
                ):
                    if pattern_ttl == 0.0:
                        return False, 0.0
                    return True, pattern_ttl

        return True, self.ttl

    def can_serve_stale_on_error(
        self,
        entry: CacheEntry,
        *,
        now: float | None = None,
    ) -> bool:
        """Return True if a stale entry is eligible to serve on upstream error."""
        if not self.stale_if_error_enabled:
            return False
        if self.stale_if_error_window is None:
            return True
        if entry.expires_at is None:
            return True
        current = time.time() if now is None else now
        stale_for = max(0.0, current - entry.expires_at)
        return stale_for <= self.stale_if_error_window

    def vary_headers_for_response(self, response: Any) -> tuple[str, ...]:
        """Return normalized Vary header names when using RFC 9111 policy."""
        if self.policy != "rfc9111":
            return ()
        names = _vary_header_names(response.headers)
        if "*" in names:
            return ()
        return names

    def needs_request_body(self, request: Any) -> bool:
        """Return True if the request body should be read before computing the cache key."""
        method = str(request.method).upper()
        if method in _BODY_LESS_METHODS:
            return False
        if self.policy == "replay":
            return True
        return method in self.cacheable_methods

    def should_lookup(self, request: Any, *, override_ttl: Any = _UNSET) -> bool:
        """Return True if the transport should query the cache for this request."""
        if self.policy == "replay":
            return True
        if getattr(request.url, "is_relative_url", False):
            return False
        if str(request.method).upper() not in self.cacheable_methods:
            return False
        allowed, _ = self.resolve_request_ttl(request, override_ttl=override_ttl)
        if not allowed:
            return False
        if self.policy == "rfc9111":
            req_cc = parse_cache_control(request.headers)
            if "no-store" in req_cc:
                return False
        return True

    def should_store(self, request: Any, response: Any, *, override_ttl: Any = _UNSET) -> bool:
        """Return True if the response may be written to the cache."""
        if self.policy == "replay":
            return False
        if getattr(request.url, "is_relative_url", False):
            return False
        if str(request.method).upper() not in self.cacheable_methods:
            return False
        if int(response.status_code) not in self.cacheable_status_codes:
            return False
        allowed, _ = self.resolve_request_ttl(request, override_ttl=override_ttl)
        if not allowed:
            return False
        if self.policy == "force":
            return True

        # RFC 9111 storage rules
        req_cc = parse_cache_control(request.headers)
        resp_cc = parse_cache_control(response.headers)
        if "no-store" in req_cc or "no-store" in resp_cc:
            return False
        if self.shared and "private" in resp_cc:
            return False
        return "*" not in _vary_header_names(response.headers)

    def evaluate_cached(
        self,
        request: Any,
        entry: CacheEntry,
        *,
        now: float | None = None,
    ) -> CacheDecision:
        """Decide whether a cached entry is fresh, needs revalidation, or is stale."""
        current = time.time() if now is None else now

        if self.policy == "replay":
            return "fresh"

        if self.policy == "force":
            return "stale" if entry.is_expired(current) else "fresh"

        # RFC 9111 evaluation
        if not self._vary_matches(request, entry):
            return "stale"

        req_cc = parse_cache_control(request.headers)
        resp_cc = _entry_cache_control(entry.headers)
        has_validators = _entry_has_validators(entry)

        req_max_age = _parse_non_negative_int(req_cc.get("max-age"))
        if "no-cache" in req_cc or req_max_age == 0:
            return "revalidate" if has_validators else "stale"
        if "no-cache" in resp_cc:
            return "revalidate" if has_validators else "stale"

        if entry.is_expired(current):
            return "revalidate" if has_validators else "stale"

        freshness = self._rfc9111_freshness_lifetime(entry, resp_cc)
        age = self._rfc9111_age(entry, current)

        req_min_fresh = _parse_non_negative_int(req_cc.get("min-fresh"))
        effective_age = age + (req_min_fresh if req_min_fresh is not None else 0)

        if req_max_age is not None and effective_age >= req_max_age:
            return "revalidate" if has_validators else "stale"

        if effective_age < freshness:
            return "fresh"

        return "revalidate" if has_validators else "stale"

    def conditional_headers(self, entry: CacheEntry) -> dict[str, str]:
        """Extract conditional revalidation headers from a stale entry."""
        headers: dict[str, str] = {}
        etag = _entry_headers_get(entry.headers, "etag")
        if etag:
            headers["If-None-Match"] = etag
        last_modified = _entry_headers_get(entry.headers, "last-modified")
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def _filter_headers(self, raw_items: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
        if not self.scrub_headers:
            return tuple((str(k), str(v)) for k, v in raw_items)
        return tuple(
            (str(k), str(v)) for k, v in raw_items if str(k).lower() not in self.scrub_headers
        )

    def build_entry(
        self,
        request: Any,
        response: Any,
        *,
        body: bytes,
        raw_stream: bool,
        now: float | None = None,
        override_ttl: Any = _UNSET,
    ) -> CacheEntry:
        """Create a CacheEntry from a live response and request."""
        current = time.time() if now is None else now
        headers = self._filter_headers(response.headers.multi_items())
        http_version = getattr(response, "http_version", "HTTP/1.1") or "HTTP/1.1"
        encoding = getattr(response, "encoding", None)
        metadata: dict[str, Any] = {"raw_stream": raw_stream}

        if self.policy == "rfc9111":
            vary_names = _vary_header_names(response.headers)
            if vary_names:
                metadata["vary"] = {
                    name: ",".join(request.headers.get_list(name)) for name in vary_names
                }

        _, effective_ttl = self.resolve_request_ttl(request, override_ttl=override_ttl)
        expires_at = self._compute_expires_at(
            status_code=int(response.status_code),
            headers=headers,
            created_at=current,
            effective_ttl=effective_ttl,
        )
        return CacheEntry(
            status_code=int(response.status_code),
            headers=headers,
            body=body,
            http_version=http_version,
            encoding=encoding,
            created_at=current,
            expires_at=expires_at,
            metadata=metadata,
        )

    def merge_revalidated_entry(
        self,
        request: Any,
        old_entry: CacheEntry,
        response_304: Any,
        *,
        now: float | None = None,
        override_ttl: Any = _UNSET,
    ) -> CacheEntry:
        """Merge headers from a 304 Not Modified response into an existing cached entry."""
        current = time.time() if now is None else now
        updated_items = list(self._filter_headers(response_304.headers.multi_items()))
        updated_keys = {k.lower() for k, _ in updated_items}

        merged_headers = [
            (k, v)
            for k, v in old_entry.headers
            if k.lower() not in updated_keys and k.lower() not in self.scrub_headers
        ]
        merged_headers.extend(updated_items)
        headers_tuple = tuple(merged_headers)

        metadata = dict(old_entry.metadata)
        vary_names = _vary_header_names(response_304.headers)
        if vary_names:
            metadata["vary"] = {
                name: ",".join(request.headers.get_list(name)) for name in vary_names
            }

        _, effective_ttl = self.resolve_request_ttl(request, override_ttl=override_ttl)
        expires_at = self._compute_expires_at(
            status_code=old_entry.status_code,
            headers=headers_tuple,
            created_at=current,
            effective_ttl=effective_ttl,
        )
        return CacheEntry(
            status_code=old_entry.status_code,
            headers=headers_tuple,
            body=old_entry.body,
            http_version=old_entry.http_version,
            encoding=old_entry.encoding,
            created_at=current,
            expires_at=expires_at,
            metadata=metadata,
        )

    def _compute_expires_at(
        self,
        *,
        status_code: int,
        headers: tuple[tuple[str, str], ...],
        created_at: float,
        effective_ttl: float | None,
    ) -> float | None:
        if self.policy == "force":
            return None if effective_ttl is None else created_at + effective_ttl

        has_validators = (
            _entry_headers_get(headers, "etag") is not None
            or _entry_headers_get(headers, "last-modified") is not None
        )
        if has_validators:
            return None if effective_ttl is None else created_at + effective_ttl

        resp_cc = _entry_cache_control(headers)
        temp_entry = CacheEntry(
            status_code=status_code,
            headers=headers,
            body=b"",
            created_at=created_at,
        )
        lifetime = self._rfc9111_freshness_lifetime(temp_entry, resp_cc, fallback_ttl=effective_ttl)
        if lifetime == float("inf"):
            return None if effective_ttl is None else created_at + effective_ttl
        if lifetime <= 0:
            return created_at
        if effective_ttl is not None:
            lifetime = min(lifetime, effective_ttl)
        return created_at + lifetime

    def _rfc9111_freshness_lifetime(
        self,
        entry: CacheEntry,
        resp_cc: dict[str, str | None],
        *,
        fallback_ttl: float | None = None,
    ) -> float:
        if self.shared:
            s_maxage = _parse_non_negative_int(resp_cc.get("s-maxage"))
            if s_maxage is not None:
                return float(s_maxage)

        max_age = _parse_non_negative_int(resp_cc.get("max-age"))
        if max_age is not None:
            return float(max_age)

        date_ts = parse_http_date(_entry_headers_get(entry.headers, "date"))
        ref_date = date_ts if date_ts is not None else entry.created_at

        expires_raw = _entry_headers_get(entry.headers, "expires")
        if expires_raw is not None:
            expires_ts = parse_http_date(expires_raw)
            if expires_ts is None:
                return 0.0
            return max(0.0, expires_ts - ref_date)

        if entry.status_code in _PERMANENT_REDIRECT_STATUSES:
            return float("inf")

        last_modified_ts = parse_http_date(_entry_headers_get(entry.headers, "last-modified"))
        if last_modified_ts is not None and ref_date > last_modified_ts:
            return (ref_date - last_modified_ts) * 0.1

        ttl_to_use = self.ttl if fallback_ttl is None else fallback_ttl
        if ttl_to_use is not None:
            return ttl_to_use
        return 0.0

    def _rfc9111_age(self, entry: CacheEntry, now: float) -> float:
        date_ts = parse_http_date(_entry_headers_get(entry.headers, "date"))
        ref_time = date_ts if date_ts is not None else entry.created_at
        resident_age = max(0.0, now - ref_time)
        age_header = _parse_non_negative_int(_entry_headers_get(entry.headers, "age"))
        if age_header is not None:
            return max(resident_age, float(age_header))
        return resident_age

    def _vary_matches(self, request: Any, entry: CacheEntry) -> bool:
        vary_map: dict[str, str] | None = entry.metadata.get("vary")
        if not vary_map:
            return True
        for name, expected in vary_map.items():
            actual = ",".join(request.headers.get_list(name))
            if actual != expected:
                return False
        return True
