from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.candidates.offhour_search import OffhourPotentialSearchService  # noqa: E402
from app.config import settings  # noqa: E402
from app.storage.sqlite_store import SQLiteStore  # noqa: E402


TRACKED_TABLES = [
    "potential_search_runs",
    "potential_search_items",
    "auto_discovered_candidates",
    "candidate_lifecycle",
    "candidate_lifecycle_events",
    "candidate_scores",
]


def _table_count(store: SQLiteStore, table: str) -> int:
    row = store.fetch_one(f"SELECT COUNT(*) AS count FROM {table}") or {}
    return int(row.get("count") or 0)


def _counts(store: SQLiteStore) -> dict[str, int]:
    return {table: _table_count(store, table) for table in TRACKED_TABLES}


def _latest_potential_search(store: SQLiteStore) -> dict[str, Any] | None:
    row = store.fetch_one(
        """
        SELECT id, status, source, total_scanned, stored_count, scored_count,
               errors_json, created_at, completed_at
        FROM potential_search_runs
        ORDER BY id DESC
        LIMIT 1
        """
    )
    if not row:
        return None
    item = dict(row)
    try:
        item["errors"] = json.loads(item.pop("errors_json") or "[]")
    except json.JSONDecodeError:
        item["errors"] = []
    return item


def _classify_retry(result: dict[str, Any], database_mutated: bool) -> str:
    errors = result.get("errors") or []
    if database_mutated:
        return "failed_persist_false_mutated_database"
    if result.get("status") == "completed" and not errors:
        return "retry_succeeded_persist_false"
    if any("discovery" in str(item).lower() or "remote end" in str(item).lower() for item in errors):
        return "external_source_still_failing"
    if errors:
        return "retry_completed_with_errors"
    return f"retry_status_{result.get('status', 'unknown')}"


def build_preflight(
    *,
    limit: int = 100,
    persist_review_run: bool = False,
    store: SQLiteStore | None = None,
    service_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if settings.enable_live_trading:
        raise RuntimeError("Refusing discovery retry preflight while live trading is enabled.")

    store = store or SQLiteStore(settings.database_path)
    latest_before = _latest_potential_search(store)
    before_counts = _counts(store)
    service = service_factory() if service_factory else OffhourPotentialSearchService()
    result = service.run(limit=max(1, min(int(limit), 500)), persist=False)
    after_no_write_counts = _counts(store)
    latest_after = _latest_potential_search(store)
    no_write_database_mutated = before_counts != after_no_write_counts
    retry_status = _classify_retry(result, no_write_database_mutated)
    errors = result.get("errors") or []
    persist_result: dict[str, Any] | None = None
    after_persist_counts = after_no_write_counts
    persist_database_mutated = False
    persist_status = "not_requested"

    if persist_review_run:
        if retry_status != "retry_succeeded_persist_false":
            persist_status = "skipped_preflight_not_clean"
        elif no_write_database_mutated:
            persist_status = "skipped_preflight_mutated_database"
        else:
            persist_service = service_factory() if service_factory else OffhourPotentialSearchService()
            persist_result = persist_service.run(limit=max(1, min(int(limit), 500)), persist=True)
            after_persist_counts = _counts(store)
            latest_after = _latest_potential_search(store)
            persist_database_mutated = after_no_write_counts != after_persist_counts
            persist_status = (
                "persisted_review_run"
                if persist_result.get("status") == "completed" and persist_database_mutated
                else f"persist_status_{persist_result.get('status', 'unknown')}"
            )

    database_mutated = no_write_database_mutated or persist_database_mutated

    return {
        "schema_version": "v1_discovery_retry_preflight.v1",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": settings.enable_live_trading,
        "persist_requested": persist_review_run,
        "writes_database": persist_review_run,
        "database_mutated": database_mutated,
        "no_write_database_mutated": no_write_database_mutated,
        "persist_database_mutated": persist_database_mutated,
        "retry_status": retry_status,
        "persist_status": persist_status,
        "limit": max(1, min(int(limit), 500)),
        "latest_run_before": latest_before,
        "latest_run_after": latest_after,
        "database_counts": {
            "before": before_counts,
            "after_no_write": after_no_write_counts,
            "after": after_persist_counts,
        },
        "result": {
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "source": result.get("source"),
            "total_scanned": int(result.get("total_scanned") or 0),
            "stored_count": int(result.get("stored_count") or 0),
            "scored_count": int(result.get("scored_count") or 0),
            "top_scored_symbols": result.get("top_scored_symbols") or [],
            "errors": errors,
        },
        "persist_result": None if persist_result is None else {
            "run_id": persist_result.get("run_id"),
            "status": persist_result.get("status"),
            "source": persist_result.get("source"),
            "total_scanned": int(persist_result.get("total_scanned") or 0),
            "stored_count": int(persist_result.get("stored_count") or 0),
            "scored_count": int(persist_result.get("scored_count") or 0),
            "top_scored_symbols": persist_result.get("top_scored_symbols") or [],
            "errors": persist_result.get("errors") or [],
        },
        "downstream_candidate_evidence_available": _table_count(store, "candidate_scores") > 0,
        "next_action": (
            "refresh_v1_stability_expect_discovery_attention_clear"
            if persist_status == "persisted_review_run"
            else
            "persist_discovery_run_can_replace_partial_status"
            if retry_status == "retry_succeeded_persist_false"
            else "continue_with_downstream_candidates_and_retry_later"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="V1 no-write potential-search retry preflight.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--persist-review-run",
        action="store_true",
        help="After a clean persist=false preflight, persist a review-only potential search run.",
    )
    args = parser.parse_args(argv)
    summary = build_preflight(limit=args.limit, persist_review_run=args.persist_review_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if summary["no_write_database_mutated"]:
        return 1
    if args.persist_review_run and summary["persist_status"] != "persisted_review_run":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
