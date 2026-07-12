from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from app.config import settings
from app.data.universe_backfill import UniverseBackfillService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply a review-only Shanghai/Shenzhen A-share daily-bar backfill. "
            "The default is a read-only dry run."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly allow writes to daily_bar_cache; omitted means dry-run.",
    )
    parser.add_argument("--days", type=int, default=500, help="History per symbol (1-500).")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Symbols per refresh call (clamped to 1-200).",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=0.5,
        help="Delay between batches; use 0 only for controlled tests.",
    )
    parser.add_argument(
        "--resume-after",
        default=None,
        help="Continue deterministically after this normalized or six-digit symbol.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum symbols for this invocation.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service: Any | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    runner = service or UniverseBackfillService()
    try:
        result = runner.run(
            apply=args.apply,
            days=args.days,
            batch_size=args.batch_size,
            rate_limit_seconds=args.rate_limit_seconds,
            resume_after=args.resume_after,
            limit=args.limit,
        )
    except Exception as exc:
        result = {
            "status": "error",
            "mode": "apply" if args.apply else "dry_run",
            "error": str(exc),
            "safety": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
                "writes_enabled": bool(args.apply),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in {"error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
