"""Read-only canonical forecast evidence report for a local SQLite database.

Replaces the pooled measurement scripts in the ``claude methods/verify`` archive
(which joined every repeated snapshot, ignored scope and the canonical policy,
and ranked ties arbitrarily) with the same read model the cockpit scoreboard
uses: canonical snapshots only, decision-date folds, due-based coverage and the
strategy-evidence eligibility policy.

The database is opened with ``mode=ro`` and ``query_only``; schema initialisation
is skipped, so running this against the production file cannot write to it.

    python backend/scripts/forecast_evidence_report.py --database trading_local.sqlite3 \
        [--as-of 2026-09-24T15:30:00+08:00] [--include-inferred]

Exit codes: 0 report printed (whatever the evidence says), 2 unusable input.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.forecasting.evidence import ForecastEvidenceService  # noqa: E402
from app.storage.sqlite_store import SQLiteStore  # noqa: E402


class ReadOnlyStore(SQLiteStore):
    """SQLiteStore that can only read: no schema init, read-only URI, query_only."""

    def init(self) -> None:  # never create or migrate anything
        return None

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(Path(self.db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--as-of", help="timezone-aware ISO timestamp; default now")
    parser.add_argument("--include-inferred", action="store_true",
                        help="admit inferred snapshots (exploratory, never eligible)")
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error(f"database not found: {args.database}")
    as_of = None
    if args.as_of:
        as_of = datetime.fromisoformat(args.as_of)
        if as_of.tzinfo is None:
            parser.error("--as-of must include a timezone offset")
    try:
        report = ForecastEvidenceService(ReadOnlyStore(args.database)).summary(
            as_of, include_inferred=args.include_inferred
        )
    except sqlite3.Error as exc:
        print(json.dumps({"status": "unavailable", "reason": type(exc).__name__}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
