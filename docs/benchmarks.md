# Benchmarks

Measured locally on Apple Silicon (Python 3.12, 1,048-byte JSON payload, 500 iterations after 10 warmup requests, using in-process `MockTransport` to isolate `httpx-cache` overhead from network latency).

| Benchmark | Median (ms) | P95 (ms) | Ops/sec |
| --- | ---: | ---: | ---: |
| `httpx` uncached (`MockTransport`) | 0.027 | 0.032 | 36,754 |
| `httpx` + `MemoryCache` (hit) | 0.031 | 0.035 | 31,915 |
| `httpx` + `JsonCache` (hit) | 0.032 | 0.035 | 31,579 |
| `httpx` + `SqliteCache` WAL (hit) | 0.054 | 0.063 | 18,590 |
| `httpx` + `FileCache` (hit) | 0.060 | 0.065 | 16,569 |
| `httpx2` uncached (`MockTransport`) | 0.018 | 0.020 | 56,338 |
| `httpx2` + `MemoryCache` (hit) | 0.023 | 0.025 | 43,478 |
| `httpx2` + `JsonCache` (hit) | 0.024 | 0.026 | 41,667 |
| `httpx2` + `SqliteCache` WAL (hit) | 0.045 | 0.049 | 22,049 |
| `httpx2` + `FileCache` (hit) | 0.051 | 0.054 | 19,672 |
| `httpx` async + `SqliteCache` WAL (hit) | 0.108 | 0.118 | 9,256 |

- `MemoryCache` and `JsonCache` add ~4–5 microseconds per hit.
- Persistent WAL `SqliteCache` adds ~27 microseconds per sync hit (~90 microseconds async via `asyncio.to_thread`).

## Reproduce

```bash
uv run python benchmarks/bench.py
```
