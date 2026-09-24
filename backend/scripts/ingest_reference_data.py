from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from app.config import settings
from app.reference_data import ReferenceIngestService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch sector memberships, share-buyback disclosures, and global-market bars "
            "into review-only point-in-time ledgers. The default is a no-record-write dry run."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly write ledger records; omitted means dry-run.",
    )
    parser.add_argument(
        "--board-limit",
        type=int,
        default=None,
        help="Optional maximum mapped boards whose constituents are fetched.",
    )
    parser.add_argument(
        "--disclosure-limit",
        type=int,
        default=None,
        help="Optional maximum share-buyback rows processed.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=0.2,
        help="Delay between constituent requests (default: 0.2).",
    )
    parser.add_argument(
        "--global-days",
        type=int,
        default=30,
        help="Recent daily bars retained per global symbol; minimum 6 (default: 30).",
    )
    parser.add_argument(
        "--global-symbol-limit",
        type=int,
        default=None,
        help="Optional maximum global sources fetched in deterministic order.",
    )
    parser.add_argument(
        "--skip-global",
        action="store_true",
        help="Disable global-market fetching for this invocation.",
    )
    parser.add_argument(
        "--skip-sox",
        action="store_true",
        help="Skip the slower Philadelphia Semiconductor Index source.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service: Any | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    if settings.enable_live_trading:
        result = {
            "schema_version": "reference_ingest.v1",
            "status": "blocked",
            "mode": "apply" if args.apply else "dry_run",
            "reason": "live_trading_enabled",
            "safety": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": True,
                "writes_enabled": False,
                "broker_operations_enabled": False,
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    runner = service or ReferenceIngestService()
    try:
        result = runner.run(
            apply=args.apply,
            board_limit=args.board_limit,
            disclosure_limit=args.disclosure_limit,
            rate_limit_seconds=args.rate_limit_seconds,
            global_days=args.global_days,
            include_global=not args.skip_global,
            include_sox=not args.skip_sox,
            global_symbol_limit=args.global_symbol_limit,
        )
    except Exception as exc:
        result = {
            "schema_version": "reference_ingest.v1",
            "status": "error",
            "mode": "apply" if args.apply else "dry_run",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "safety": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "writes_enabled": bool(args.apply),
                "write_outcome_known": not args.apply,
                "broker_operations_enabled": False,
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    status = str(result.get("status") or "error")
    if status == "error":
        return 1
    if status in {"blocked", "partial", "degraded", "empty", "unsupported"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
