from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from httpx_cache.cache.sqlite import DEFAULT_SQLITE_PATH, SqliteCache


def _format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="httpx-cache",
        description="Inspect, purge, clear, export, or import an httpx-cache SQLite database.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_SQLITE_PATH,
        help=f"Path to SQLite cache database (default: {DEFAULT_SQLITE_PATH})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="Show entry count and stored byte size.")

    inspect_p = sub.add_parser("inspect", help="List cached keys.")
    inspect_p.add_argument("--prefix", default="", help="Only show keys starting with prefix.")
    inspect_p.add_argument("--limit", type=int, default=50, help="Max keys to print (default: 50).")

    sub.add_parser("purge", help="Delete expired entries from the database.")

    clear_p = sub.add_parser("clear", help="Delete all entries (or those matching --prefix).")
    clear_p.add_argument("--prefix", default="", help="Only delete keys starting with prefix.")

    export_p = sub.add_parser("export", help="Export cache entries to a diffable JSON file.")
    export_p.add_argument("output", type=Path, help="Destination JSON file path.")

    import_p = sub.add_parser("import", help="Import cache entries from a JSON file.")
    import_p.add_argument("input", type=Path, help="Source JSON file path.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    db_path: Path = args.db

    if args.command in ("stats", "inspect", "purge", "clear", "export") and not db_path.exists():
        print(f"Cache database not found: {db_path}", file=sys.stderr)
        return 1

    with SqliteCache(db_path) as cache:
        if args.command == "stats":
            st = cache.stats()
            print(f"path:       {db_path}")
            print(f"entries:    {st.entries}")
            print(f"size_bytes: {st.size_bytes} ({_format_bytes(st.size_bytes)})")
            return 0

        if args.command == "inspect":
            keys = cache.keys(prefix=args.prefix)
            shown = keys[: max(0, args.limit)]
            for key in shown:
                print(key)
            if len(keys) > len(shown):
                print(f"... ({len(keys) - len(shown)} more)")
            return 0

        if args.command == "purge":
            removed = cache.purge_expired()
            print(f"Purged {removed} expired entr{'y' if removed == 1 else 'ies'}.")
            return 0

        if args.command == "clear":
            if args.prefix:
                removed = cache.delete_prefix(args.prefix)
                noun = "entry" if removed == 1 else "entries"
                print(f"Deleted {removed} {noun} matching {args.prefix!r}.")
            else:
                cache.clear()
                print(f"Cleared all entries in {db_path}.")
            return 0

        if args.command == "export":
            count = cache.export_json(args.output)
            print(f"Exported {count} entr{'y' if count == 1 else 'ies'} to {args.output}.")
            return 0

        if args.command == "import":
            count = cache.import_json(args.input)
            print(f"Imported {count} entr{'y' if count == 1 else 'ies'} into {db_path}.")
            return 0

    return 0
