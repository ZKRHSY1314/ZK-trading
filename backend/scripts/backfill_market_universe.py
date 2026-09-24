from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.config import settings
from app.data.universe_backfill import UniverseBackfillService


DEFAULT_CHECKPOINT_PATH = (
    Path(__file__).resolve().parents[1] / "logs" / "universe_backfill_checkpoint.json"
)
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "logs" / "current_a_share_universe.json"
)


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
        "--source-policy",
        choices=(
            "tonghuasun_first",
            "tonghuasun_only",
            "tencent_first",
            "akshare_first",
            "sina_first",
            "sina_only",
            "akshare_only",
        ),
        default=None,
        help=(
            "Daily-bar source order; defaults to DAILY_BAR_SOURCE_POLICY from "
            "settings. Only tonghuasun_* and sina_* carry 成交额 - a run that "
            "lands on Tencent qfq leaves the execution model on its proxy."
        ),
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Bounded concurrent symbol fetches (clamped to 1-20).",
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
    parser.add_argument(
        "--checkpoint-path",
        default=str(DEFAULT_CHECKPOINT_PATH),
        help="Atomic batch checkpoint path; written only with --apply.",
    )
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Independent atomic current-official-universe manifest path.",
    )
    parser.add_argument(
        "--resume-from-checkpoint",
        action="store_true",
        help="Resume after the last processed symbol in --checkpoint-path.",
    )
    parser.add_argument(
        "--retry-symbol",
        action="append",
        default=[],
        help="Explicit stock symbol to retry; repeat the flag for multiple symbols.",
    )
    parser.add_argument(
        "--retry-quality-gaps",
        action="store_true",
        help="Retry current-universe symbols with ERROR, non-ready, or non-qfq cache rows.",
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
        resume_after = args.resume_after
        retry_symbols: list[str] = list(args.retry_symbol)
        expected_universe_hash = None
        if args.resume_from_checkpoint:
            if resume_after:
                raise ValueError("use either --resume-after or --resume-from-checkpoint")
            checkpoint = Path(args.checkpoint_path)
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            if payload.get("checkpoint_kind") not in {
                None,
                "run_state",
                "resume_state",
            }:
                raise ValueError("checkpoint_kind is not resumable")
            resume_after = payload.get("last_processed_symbol")
            if not resume_after:
                raise ValueError("checkpoint has no last_processed_symbol")
            expected_universe_hash = payload.get("universe_hash")
            if not expected_universe_hash:
                raise ValueError("checkpoint has no universe_hash")
            if payload.get("source_policy") not in {None, args.source_policy}:
                raise ValueError("checkpoint source_policy does not match requested policy")
            if payload.get("days") not in {None, args.days}:
                raise ValueError("checkpoint days does not match requested days")
            retry_symbols = list(
                dict.fromkeys(
                    [
                        *retry_symbols,
                        *payload.get("error_symbols", []),
                        *payload.get("isolated_symbols", []),
                    ]
                )
            )
        result = runner.run(
            apply=args.apply,
            days=args.days,
            batch_size=args.batch_size,
            rate_limit_seconds=args.rate_limit_seconds,
            source_policy=args.source_policy,
            max_workers=args.max_workers,
            resume_after=resume_after,
            retry_symbols=retry_symbols,
            retry_quality_gaps=args.retry_quality_gaps,
            expected_universe_hash=expected_universe_hash,
            limit=args.limit,
            checkpoint_path=args.checkpoint_path,
            manifest_path=args.manifest_path,
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
    status = str(result.get("status") or "error")
    if status == "error":
        return 1
    if status in {"blocked", "partial", "degraded", "empty"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
