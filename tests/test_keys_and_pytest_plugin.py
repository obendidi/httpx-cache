from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from httpx_cache import CacheMissError, MemoryCache, make_key_fn, wrap
from httpx_cache.pytest_plugin import Cassette


def test_make_key_fn_ignores_params_sorts_query_and_normalizes_json(
    http_mod: ModuleType,
) -> None:
    key_fn = make_key_fn(
        ignore_params=("api_key", "ts"),
        include_headers=("X-Tenant", "Authorization"),
        normalize_json_body=True,
        prefix="v1",
    )

    req1 = http_mod.Request(
        "POST",
        "https://api.example.com/search?b=2&api_key=secret1&a=1&ts=100",
        headers={"x-tenant": "acme", "authorization": "Bearer tok1"},
        content=b'{"z": 1, "a": 2}',
    )
    req2 = http_mod.Request(
        "POST",
        "https://api.example.com/search?a=1&b=2&API_KEY=secret2&ts=999",
        headers={"X-Tenant": "acme", "Authorization": "Bearer tok1"},
        content=b'{"a":2,"z":1}',
    )
    req_diff_auth = http_mod.Request(
        "POST",
        "https://api.example.com/search?a=1&b=2",
        headers={"x-tenant": "acme", "authorization": "Bearer tok2"},
        content=b'{"a": 2, "z": 1}',
    )

    k1 = key_fn(req1)
    k2 = key_fn(req2)
    k3 = key_fn(req_diff_auth)

    assert k1 == k2
    assert k1 != k3
    assert k1.startswith("v1:POST:https://api.example.com/search?a=1&b=2")
    # Raw secret header value must never appear verbatim in the cache key
    assert "Bearer tok1" not in k1
    assert "secret1" not in k1


def test_make_key_fn_non_json_fallback_and_include_body_false(
    http_mod: ModuleType,
) -> None:
    non_json_fn = make_key_fn(normalize_json_body=True)
    r_raw = http_mod.Request("POST", "https://example.com/raw", content=b"not-json")
    assert "body=" in non_json_fn(r_raw)

    no_body_fn = make_key_fn(include_body=False)
    r_a = http_mod.Request("POST", "https://example.com/raw", content=b"one")
    r_b = http_mod.Request("POST", "https://example.com/raw", content=b"two")
    assert no_body_fn(r_a) == no_body_fn(r_b)


def test_make_key_fn_end_to_end_with_wrap(http_mod: ModuleType) -> None:
    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, json={"call": calls})

    client = wrap(
        http_mod.Client(transport=http_mod.MockTransport(handler)),
        cache=MemoryCache(),
        policy="force",
        cache_post=True,
        key_fn=make_key_fn(ignore_params=("nonce",), normalize_json_body=True),
    )
    with client:
        r1 = client.post("https://api.example.com/q?nonce=1", content=b'{"b": 2, "a": 1}')
        r2 = client.post("https://api.example.com/q?nonce=2", content=b'{"a": 1, "b": 2}')

    assert calls == 1
    assert r1.extensions["from_cache"] is False
    assert r2.extensions["from_cache"] is True


def test_cassette_once_replay_and_rewrite_modes(
    http_mod: ModuleType,
    tmp_path: Path,
) -> None:
    db = tmp_path / "cassettes" / "my_test.sqlite3"
    calls = 0

    def handler(req: Any) -> Any:
        nonlocal calls
        calls += 1
        return http_mod.Response(200, json={"call": calls})

    # Mode: once -> records first call, replays second
    c_once = Cassette(db, mode="once")
    try:
        with c_once.wrap(http_mod.Client(transport=http_mod.MockTransport(handler))) as client:
            r1 = client.post("https://api.example.com/run", json={"x": 1})
            r2 = client.post("https://api.example.com/run", json={"x": 1})
        assert calls == 1
        assert r1.extensions["from_cache"] is False
        assert r2.extensions["from_cache"] is True
    finally:
        c_once.close()

    # Mode: replay -> offline hit + loud miss
    def forbidden(req: Any) -> Any:
        raise AssertionError("Network must not be called in replay mode")

    c_replay = Cassette(db, mode="replay")
    try:
        with c_replay.wrap(http_mod.Client(transport=http_mod.MockTransport(forbidden))) as client:
            hit = client.post("https://api.example.com/run", json={"x": 1})
            assert hit.extensions["from_cache"] is True
            assert hit.json() == {"call": 1}
            with pytest.raises(CacheMissError):
                client.post("https://api.example.com/run", json={"x": 999})
    finally:
        c_replay.close()

    # Mode: rewrite -> wipes previous cassette and re-records
    c_rewrite = Cassette(db, mode="rewrite")
    try:
        with c_rewrite.wrap(http_mod.Client(transport=http_mod.MockTransport(handler))) as client:
            r3 = client.post("https://api.example.com/run", json={"x": 1})
        assert calls == 2
        assert r3.extensions["from_cache"] is False
        assert r3.json() == {"call": 2}
    finally:
        c_rewrite.close()


def test_pytest_plugin_fixtures_registered(
    httpx_cache_record_mode: str,
    httpx_cache_cassette: Cassette,
) -> None:
    assert httpx_cache_record_mode == "once"
    assert httpx_cache_cassette.policy == "force"
    # Opening no requests must not leave cassette files behind
    assert not httpx_cache_cassette.path.exists()
