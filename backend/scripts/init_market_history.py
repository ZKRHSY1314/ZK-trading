from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from app.data.market_history import DEFAULT_MARKET_HISTORY_PATH, MarketHistoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect or initialize the independent, research-only historical market "
            "database. The default is a read-only inspection; no data is backfilled."
        )
    )
    parser.add_argument(
        "--database-path",
        default=str(DEFAULT_MARKET_HISTORY_PATH),
        help="History database path (default: project-root market_history.sqlite3).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly create or idempotently initialize the schema.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = MarketHistoryStore(args.database_path)
    try:
        result = store.initialize() if args.apply else store.inspect()
    except ValueError as exc:
        result = {
            "status": "blocked",
            "mode": "apply" if args.apply else "inspect",
            "database_path": str(store.database_path.resolve()),
            "writes_enabled": False,
            "error": str(exc),
            "safety": {
                "research_only": True,
                "live_trading_enabled": False,
                "broker_or_order_capability": False,
            },
        }
    except Exception as exc:
        result = {
            "status": "error",
            "mode": "apply" if args.apply else "inspect",
            "database_path": str(store.database_path.resolve()),
            "writes_enabled": False,
            "error": str(exc),
            "safety": {
                "research_only": True,
                "live_trading_enabled": False,
                "broker_or_order_capability": False,
            },
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"planned", "ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
