"""Run a predeclared A/B manifest against a COPY of a local database.

    python backend/scripts/run_backtest_ab.py --manifest experiment.json \
        --database trading_local.sqlite3 [--label my_experiment]

The source database is never opened for writing: it is copied through SQLite's
online backup API (read-only source connection) into a temporary file, the
harness runs there with persistence off, and the copy is deleted. ``--label``
writes only ``<project-root>/logs/backtest_ab_<label>.json``.

The report is an engineering comparison; it is never qualified strategy
evidence (see app/backtest/ab_harness.py). Exit codes: 0 completed, 1 a control
failed (result invalid), 2 unusable manifest or input.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import re
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

os.environ["ENABLE_LIVE_TRADING"] = "false"
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.backtest.ab_harness import ManifestError, run_ab  # noqa: E402

ROOT = BACKEND.parent
LABEL = re.compile(r"^[a-z0-9_-]{1,40}$")


def copy_database(source: Path, target: Path) -> None:
    # closing(), not the connection's own context manager: that one only ends
    # the transaction and would leave both files open.
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as reader:
        with closing(sqlite3.connect(target)) as writer:
            reader.backup(writer)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--label")
    args = parser.parse_args(argv)
    if args.label is not None and not LABEL.match(args.label):
        parser.error("--label must match [a-z0-9_-]{1,40}")
    if not args.database.is_file():
        parser.error(f"database not found: {args.database}")
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"manifest unreadable: {exc}")
    with tempfile.TemporaryDirectory(prefix="zk-ab-") as scratch:
        working_copy = Path(scratch) / "ab_input_copy.sqlite3"
        try:
            copy_database(args.database, working_copy)
            report = run_ab(manifest, database_path=working_copy)
        except ManifestError as exc:
            print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
            return 2
        except sqlite3.Error as exc:
            print(json.dumps({"status": "unavailable", "reason": type(exc).__name__}))
            return 2
        finally:
            # The engine's services open SQLite connections they never close;
            # some sit in reference cycles and are only finalised by the cycle
            # collector. Windows refuses to delete a file that is still open,
            # so finalise them before the temporary directory is removed.
            gc.collect()
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.label is not None:
        target = args.project_root.resolve() / "logs" / f"backtest_ab_{args.label}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(encoded + "\n", encoding="utf-8")
        temporary.replace(target)
    print(encoded)
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
