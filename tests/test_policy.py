from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import ModuleType

import pytest

from httpx_cache import CacheEntry, PolicyController


def test_force_policy_ignores_no_store_and_private(http_mod: ModuleType) -> None:
    ctrl = PolicyController(policy="force", ttl=60, cache_post=True)
    req = http_mod.Request(
        "POST",
        "https://api.example.com/v1/chat",
        headers={"cache-control": "no-store, no-cache"},
        json={"prompt": "hi"},
    )
    resp = http_mod.Response(
        200,
        headers={"cache-control": "private, no-store, max-age=0"},
        content=b"ok",
    )
    assert ctrl.should_lookup(req) is True
    assert ctrl.should_store(req, resp) is True

    now = 1000.0
    entry = ctrl.build_entry(req, resp, body=b"ok", raw_stream=False, now=now)
    assert entry.expires_at == 1060.0
    assert ctrl.evaluate_cached(req, entry, now=1059.0) == "fresh"
    assert ctrl.evaluate_cached(req, entry, now=1060.0) == "stale"

    # Non-cacheable status code is still skipped
    assert ctrl.should_store(req, http_mod.Response(500, content=b"err")) is False


def test_force_policy_rejects_post_unless_enabled(http_mod: ModuleType) -> None:
    ctrl = PolicyController(policy="force")
    post_req = http_mod.Request("POST", "https://api.example.com/v1/chat", content=b"{}")
    assert ctrl.should_lookup(post_req) is False
    assert ctrl.should_store(post_req, http_mod.Response(200)) is False


def test_rfc9111_no_store_and_private_shared(http_mod: ModuleType) -> None:
    private_ctrl = PolicyController(policy="rfc9111", shared=False)
    shared_ctrl = PolicyController(policy="rfc9111", shared=True)
    req = http_mod.Request("GET", "https://example.com/profile")

    no_store_resp = http_mod.Response(200, headers={"cache-control": "no-store"})
    assert private_ctrl.should_store(req, no_store_resp) is False

    private_resp = http_mod.Response(200, headers={"cache-control": "private, max-age=60"})
    assert private_ctrl.should_store(req, private_resp) is True
    assert shared_ctrl.should_store(req, private_resp) is False

    vary_star = http_mod.Response(200, headers={"vary": "*"})
    assert private_ctrl.should_store(req, vary_star) is False


def test_rfc9111_freshness_max_age_expires_and_vary(http_mod: ModuleType) -> None:
    ctrl = PolicyController(policy="rfc9111")
    now = time.time()
    date_hdr = format_datetime(datetime.fromtimestamp(now, tz=timezone.utc), usegmt=True)
    expires_hdr = format_datetime(
        datetime.fromtimestamp(now + 120, tz=timezone.utc), usegmt=True
    )

    req_en = http_mod.Request(
        "GET", "https://example.com/doc", headers={"accept-language": "en"}
    )
    req_fr = http_mod.Request(
        "GET", "https://example.com/doc", headers={"accept-language": "fr"}
    )
    resp = http_mod.Response(
        200,
        headers={
            "date": date_hdr,
            "expires": expires_hdr,
            "vary": "Accept-Language",
        },
        content=b"hello",
    )
    entry = ctrl.build_entry(req_en, resp, body=b"hello", raw_stream=False, now=now)
    assert ctrl.evaluate_cached(req_en, entry, now=now + 30) == "fresh"
    assert ctrl.evaluate_cached(req_en, entry, now=now + 130) == "stale"
    assert ctrl.evaluate_cached(req_fr, entry, now=now + 30) == "stale"


def test_rfc9111_etag_revalidation_and_304_merge(http_mod: ModuleType) -> None:
    ctrl = PolicyController(policy="rfc9111")
    now = time.time()
    req = http_mod.Request("GET", "https://example.com/item")
    resp = http_mod.Response(
        200,
        headers={"cache-control": "max-age=10", "etag": '"v1"', "x-keep": "yes"},
        content=b"payload",
    )
    entry = ctrl.build_entry(req, resp, body=b"payload", raw_stream=False, now=now)
    assert ctrl.evaluate_cached(req, entry, now=now + 5) == "fresh"
    assert ctrl.evaluate_cached(req, entry, now=now + 20) == "revalidate"
    assert ctrl.conditional_headers(entry) == {"If-None-Match": '"v1"'}

    resp_304 = http_mod.Response(
        304,
        headers={"cache-control": "max-age=60", "etag": '"v2"'},
    )
    merged = ctrl.merge_revalidated_entry(req, entry, resp_304, now=now + 20)
    assert merged.status_code == 200
    assert merged.body == b"payload"
    assert dict(merged.headers)["etag"] == '"v2"'
    assert dict(merged.headers)["x-keep"] == "yes"
    assert ctrl.evaluate_cached(req, merged, now=now + 50) == "fresh"


def test_replay_policy_ignores_expiry_and_never_stores(http_mod: ModuleType) -> None:
    ctrl = PolicyController(policy="replay")
    req = http_mod.Request("POST", "https://example.com/rpc", content=b'{"id": 1}')
    expired_entry = CacheEntry(
        status_code=200,
        headers=(),
        body=b"recorded",
        created_at=100.0,
        expires_at=101.0,
    )
    assert ctrl.should_lookup(req) is True
    assert ctrl.should_store(req, http_mod.Response(200)) is False
    assert ctrl.evaluate_cached(req, expired_entry, now=99999.0) == "fresh"


def test_invalid_policy_and_negative_ttl() -> None:
    with pytest.raises(ValueError, match="Invalid policy"):
        PolicyController(policy="bogus")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-negative"):
        PolicyController(policy="force", ttl=-1)
    ctrl = PolicyController(policy="force", ttl=timedelta(minutes=5))
    assert ctrl.ttl == 300.0


def test_rfc9111_shared_s_maxage_last_modified_permanent_redirect_and_request_directives(
    http_mod: ModuleType,
) -> None:
    now = time.time()
    shared_ctrl = PolicyController(policy="rfc9111", shared=True)
    req = http_mod.Request("GET", "https://example.com/shared")
    resp = http_mod.Response(
        200,
        headers={"cache-control": "max-age=10, s-maxage=120", "age": "20"},
        content=b"shared",
    )
    entry = shared_ctrl.build_entry(req, resp, body=b"shared", raw_stream=False, now=now)
    assert shared_ctrl.evaluate_cached(req, entry, now=now + 5) == "fresh"

    # Request min-fresh and max-age constraints
    tight_req = http_mod.Request(
        "GET", "https://example.com/shared", headers={"cache-control": "min-fresh=110"}
    )
    assert shared_ctrl.evaluate_cached(tight_req, entry, now=now + 5) == "stale"

    req_max_age = http_mod.Request(
        "GET", "https://example.com/shared", headers={"cache-control": "max-age=15"}
    )
    assert shared_ctrl.evaluate_cached(req_max_age, entry, now=now + 5) == "stale"

    # Permanent redirect (301) is fresh without Cache-Control
    ctrl = PolicyController(policy="rfc9111")
    redirect_resp = http_mod.Response(301, headers={"location": "https://example.com/new"})
    redirect_entry = ctrl.build_entry(req, redirect_resp, body=b"", raw_stream=False, now=now)
    assert ctrl.evaluate_cached(req, redirect_entry, now=now + 99999) == "fresh"

    # Last-Modified heuristic freshness (10% of Date - Last-Modified)
    date_hdr = format_datetime(datetime.fromtimestamp(now, tz=timezone.utc), usegmt=True)
    lm_hdr = format_datetime(datetime.fromtimestamp(now - 1000, tz=timezone.utc), usegmt=True)
    lm_resp = http_mod.Response(
        200, headers={"date": date_hdr, "last-modified": lm_hdr}, content=b"lm"
    )
    lm_entry = ctrl.build_entry(req, lm_resp, body=b"lm", raw_stream=False, now=now)
    assert ctrl.evaluate_cached(req, lm_entry, now=now + 50) == "fresh"
    assert ctrl.evaluate_cached(req, lm_entry, now=now + 150) == "revalidate"
    assert ctrl.conditional_headers(lm_entry) == {"If-Modified-Since": lm_hdr}

    # Request no-store skips lookup & store; relative URL rejected
    no_store_req = http_mod.Request(
        "GET", "https://example.com/x", headers={"cache-control": "no-store"}
    )
    assert ctrl.should_lookup(no_store_req) is False
    assert ctrl.should_store(no_store_req, http_mod.Response(200)) is False
    rel_req = http_mod.Request("GET", "/relative")
    assert ctrl.should_lookup(rel_req) is False
    assert ctrl.should_store(rel_req, http_mod.Response(200)) is False
