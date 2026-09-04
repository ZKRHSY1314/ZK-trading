"""Fetch market cap / PB snapshots for the A-share universe.

Read-only quote fetch, no credentials, no order path. Dry-run by default;
``--apply`` is required before anything is written.

The values are a *current* snapshot. The rule layer projects them onto historical
closes (see ``app.data.fundamentals``), which is an approximation, not an
observed point-in-time fact. Run this often enough that the newest snapshot is
close to the dates you care about.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from app.config import settings
from app.data.fundamentals import (
    METHOD,
    SOURCE,
    FundamentalsStore,
    TencentFundamentalProvider,
)
from app.storage.sqlite_store import SQLiteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly write snapshots; omitted means dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum symbols fetched (for verification runs).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-batch HTTP timeout in seconds (default: 10).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if settings.enable_live_trading:
        print(json.dumps({"status": "blocked", "reason": "live_trading_enabled"}))
        return 2

    store = SQLiteStore(settings.database_path)
    store.init()
    symbols = [
        row["symbol"]
        for row in store.fetch_all(
            "SELECT DISTINCT symbol FROM daily_bar_cache "
            "WHERE quality_status = 'ready' ORDER BY symbol"
        )
    ]
    if args.limit:
        symbols = symbols[: args.limit]

    snapshots = TencentFundamentalProvider(timeout=args.timeout).fetch(symbols)
    with_cap = [item for item in snapshots if item.market_cap_billion]
    with_pb = [item for item in snapshots if item.pb]

    written = 0
    if args.apply and snapshots:
        written = FundamentalsStore(store).upsert(snapshots)

    result = {
        "status": "completed" if snapshots else "failed",
        "mode": "apply" if args.apply else "dry_run",
        "source": SOURCE,
        "method": METHOD,
        "review_only": True,
        "live_trading_enabled": settings.enable_live_trading,
        "requested_symbols": len(symbols),
        "fetched_symbols": len(snapshots),
        "fetch_coverage": round(len(snapshots) / len(symbols), 4) if symbols else None,
        "market_cap_coverage": (
            round(len(with_cap) / len(symbols), 4) if symbols else None
        ),
        "pb_coverage": round(len(with_pb) / len(symbols), 4) if symbols else None,
        "written": written,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if snapshots else 1


if __name__ == "__main__":
    raise SystemExit(main())
