"""Reproducible micro-benchmarks for httpx-cache stores on httpx and httpx2.

Run with:
    uv run python benchmarks/bench.py
"""

from __future__ import annotations

import asyncio
import importlib
import platform
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx_cache

ITERATIONS = 500
PAYLOAD = (
    b'{"status":"ok","items":['
    + b'{"id":1,"name":"widget"},' * 40
    + b'{"id":41,"name":"end"}]}'
)


def _bench_sync(label: str, fn: Any, iterations: int = ITERATIONS) -> tuple[str, float, float]:
    # Warmup
    for _ in range(10):
        fn()
    samples_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    median = statistics.median(samples_ms)
    p95 = sorted(samples_ms)[int(iterations * 0.95)]
    return label, median, p95


async def _bench_async(
    label: str, fn: Any, iterations: int = ITERATIONS
) -> tuple[str, float, float]:
    for _ in range(10):
        await fn()
    samples_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await fn()
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    median = statistics.median(samples_ms)
    p95 = sorted(samples_ms)[int(iterations * 0.95)]
    return label, median, p95


def main() -> None:
    print(
        f"Python {platform.python_version()} | {platform.platform()} "
        f"| payload={len(PAYLOAD)} B | n={ITERATIONS}\n"
    )

    results: list[tuple[str, float, float]] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for mod_name in ("httpx", "httpx2"):
            try:
                mod = importlib.import_module(mod_name)
            except ImportError:
                continue

            handler = lambda req, m=mod: m.Response(200, content=PAYLOAD)  # noqa: E731

            with mod.Client(transport=mod.MockTransport(handler)) as raw:
                results.append(
                    _bench_sync(
                        f"{mod_name} uncached (MockTransport)",
                        lambda c=raw: c.get("https://bench.local/item"),
                    )
                )

            mem = httpx_cache.MemoryCache()
            with httpx_cache.wrap(mod.Client(transport=mod.MockTransport(handler)), cache=mem) as c:
                c.get("https://bench.local/item")
                results.append(
                    _bench_sync(
                        f"{mod_name} + MemoryCache (hit)",
                        lambda cl=c: cl.get("https://bench.local/item"),
                    )
                )

            sq = httpx_cache.SqliteCache(tmp_path / f"{mod_name}.sqlite3")
            with httpx_cache.wrap(mod.Client(transport=mod.MockTransport(handler)), cache=sq) as c:
                c.get("https://bench.local/item")
                results.append(
                    _bench_sync(
                        f"{mod_name} + SqliteCache WAL (hit)",
                        lambda cl=c: cl.get("https://bench.local/item"),
                    )
                )
            sq.close()

            fc = httpx_cache.FileCache(tmp_path / f"{mod_name}_files")
            with httpx_cache.wrap(mod.Client(transport=mod.MockTransport(handler)), cache=fc) as c:
                c.get("https://bench.local/item")
                results.append(
                    _bench_sync(
                        f"{mod_name} + FileCache (hit)",
                        lambda cl=c: cl.get("https://bench.local/item"),
                    )
                )

            jc = httpx_cache.JsonCache(tmp_path / f"{mod_name}.json")
            with httpx_cache.wrap(mod.Client(transport=mod.MockTransport(handler)), cache=jc) as c:
                c.get("https://bench.local/item")
                results.append(
                    _bench_sync(
                        f"{mod_name} + JsonCache (hit)",
                        lambda cl=c: cl.get("https://bench.local/item"),
                    )
                )

        # Async SQLite hit benchmark (httpx)
        async def run_async() -> None:
            httpx = importlib.import_module("httpx")
            ahandler = lambda req: httpx.Response(200, content=PAYLOAD)  # noqa: E731
            sq_a = httpx_cache.SqliteCache(tmp_path / "async.sqlite3")
            client_a = httpx_cache.wrap(
                httpx.AsyncClient(transport=httpx.MockTransport(ahandler)), cache=sq_a
            )
            async with client_a as ac:
                await ac.get("https://bench.local/item")
                results.append(
                    await _bench_async(
                        "httpx async + SqliteCache WAL (hit)",
                        lambda: ac.get("https://bench.local/item"),
                    )
                )
            await sq_a.aclose()

        asyncio.run(run_async())

    print(f"| {'Benchmark':<40} | {'Median (ms)':>11} | {'P95 (ms)':>10} | {'Ops/sec':>10} |")
    print(f"| {'-' * 40} | {'-' * 11} | {'-' * 10} | {'-' * 10} |")
    for label, med, p95 in results:
        ops = 1000.0 / med if med > 0 else 0.0
        print(f"| {label:<40} | {med:>11.3f} | {p95:>10.3f} | {ops:>10,.0f} |")


if __name__ == "__main__":
    main()
