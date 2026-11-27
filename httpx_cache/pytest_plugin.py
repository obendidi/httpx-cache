from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import pytest

if TYPE_CHECKING:
    from httpx_cache.cache.sqlite import SqliteCache
    from httpx_cache.types import KeyFn, PolicyName

RecordMode = Literal["once", "replay", "rewrite"]
TClient = TypeVar("TClient")

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _sanitize_node_name(name: str) -> str:
    return _SAFE_NAME_RE.sub("_", name).strip("_") or "test"


class Cassette:
    """Per-test SQLite cassette bound to the active ``--httpx-cache-record`` mode."""

    def __init__(self, path: Path, mode: RecordMode) -> None:
        self.path = path
        self.mode = mode
        if mode == "rewrite" and path.exists():
            path.unlink()
            for suffix in ("-wal", "-shm"):
                sidecar = Path(f"{path}{suffix}")
                if sidecar.exists():
                    sidecar.unlink()
        self._cache: SqliteCache | None = None

    @property
    def policy(self) -> PolicyName:
        return "replay" if self.mode == "replay" else "force"

    @property
    def cache(self) -> SqliteCache:
        if self._cache is None:
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
        """Wrap an ``httpx`` or ``httpx2`` client against this test's SQLite cassette."""
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
    """Provide a per-test SQLite cassette for recording or offline replay."""
    test_file = Path(str(request.path))
    cassette_dir = test_file.parent / "__cassettes__" / test_file.stem
    cassette_path = cassette_dir / f"{_sanitize_node_name(request.node.name)}.sqlite3"
    cassette = Cassette(cassette_path, mode=httpx_cache_record_mode)
    try:
        yield cassette
    finally:
        cassette.close()
