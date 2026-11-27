from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

from httpx_cache import MemoryCache, SqliteCache


def _available_http_backends() -> list[ModuleType]:
    backends: list[ModuleType] = []
    for name in ("httpx", "httpx2"):
        try:
            backends.append(importlib.import_module(name))
        except ImportError:
            continue
    return backends


_HTTP_BACKENDS = _available_http_backends()


@pytest.fixture(params=_HTTP_BACKENDS, ids=lambda mod: mod.__name__)
def http_mod(request: pytest.FixtureRequest) -> ModuleType:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
def sqlite_cache(tmp_path: Path) -> SqliteCache:
    cache = SqliteCache(tmp_path / "cache.sqlite3")
    yield cache  # type: ignore[misc]
    cache.close()


@pytest.fixture
def memory_cache() -> MemoryCache:
    return MemoryCache()


@pytest.fixture(params=["sqlite", "memory"])
def cache(request: pytest.FixtureRequest, tmp_path: Path) -> SqliteCache | MemoryCache:
    if request.param == "sqlite":
        store = SqliteCache(tmp_path / "cache.sqlite3")
        yield store  # type: ignore[misc]
        store.close()
    else:
        yield MemoryCache()  # type: ignore[misc]
