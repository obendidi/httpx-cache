from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import pytest

if TYPE_CHECKING:
    from httpx_cache.cache.base import BaseCache
    from httpx_cache.types import KeyFn, PolicyName

RecordMode = Literal["once", "replay", "rewrite"]
CassetteFormat = Literal["sqlite", "json"]
TClient = TypeVar("TClient")

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _sanitize_node_name(name: str) -> str:
    return _SAFE_NAME_RE.sub("_", name).strip("_") or "test"


class Cassette:
    """Per-test SQLite or JSON cassette bound to the active ``--httpx-cache-record`` mode."""

    def __init__(
        self,
        path: Path,
        mode: RecordMode,
        *,
        format: CassetteFormat = "sqlite",
    ) -> None:
        self.path = path
        self.mode = mode
        self.format: CassetteFormat = format
        if mode == "rewrite" and path.exists():
            path.unlink()
            if format == "sqlite":
                for suffix in ("-wal", "-shm"):
                    sidecar = Path(f"{path}{suffix}")
                    if sidecar.exists():
                        sidecar.unlink()
        self._cache: BaseCache | None = None

    @property
    def policy(self) -> PolicyName:
        return "replay" if self.mode == "replay" else "force"

    @property
    def cache(self) -> BaseCache:
        if self._cache is None:
            if self.format == "json":
                from httpx_cache.cache.json_store import JsonCache

                self._cache = JsonCache(self.path)
            else:
                from httpx_cache.cache.sqlite import SqliteCache

                self._cache = SqliteCache(self.path)
        return self._cache

    def wrap(
        self,
        client: TClient,
        *,
        cache_post: bool = True,
        ttl: float | None = None,
        key_fn: KeyFn | None = None,
        **kwargs: Any,
    ) -> TClient:
        """Wrap an ``httpx`` or ``httpx2`` client against this test's cassette."""
        from httpx_cache.client import wrap

        return wrap(
            client,
            cache=self.cache,
            policy=self.policy,
            ttl=ttl,
            cache_post=cache_post,
            key_fn=key_fn,
            **kwargs,
        )

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()
            self._cache = None


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("httpx-cache")
    group.addoption(
        "--httpx-cache-record",
        action="store",
        default="once",
        choices=("once", "replay", "rewrite"),
        help="Record/replay mode for httpx_cache_cassette: once (default), replay, or rewrite.",
    )
    group.addoption(
        "--httpx-cache-format",
        action="store",
        default="sqlite",
        choices=("sqlite", "json"),
        help="Cassette storage format: sqlite (default) or diffable json.",
    )


@pytest.fixture
def httpx_cache_record_mode(request: pytest.FixtureRequest) -> RecordMode:
    """Return the active ``--httpx-cache-record`` mode."""
    mode: RecordMode = request.config.getoption("--httpx-cache-record")
    return mode


@pytest.fixture
def httpx_cache_cassette(
    request: pytest.FixtureRequest,
    httpx_cache_record_mode: RecordMode,
) -> Iterator[Cassette]:
    """Provide a per-test SQLite or JSON cassette for recording or offline replay."""
    fmt: CassetteFormat = request.config.getoption("--httpx-cache-format")
    ext = "json" if fmt == "json" else "sqlite3"
    test_file = Path(str(request.path))
    cassette_dir = test_file.parent / "__cassettes__" / test_file.stem
    cassette_path = cassette_dir / f"{_sanitize_node_name(request.node.name)}.{ext}"
    cassette = Cassette(cassette_path, mode=httpx_cache_record_mode, format=fmt)
    try:
        yield cassette
    finally:
        cassette.close()
