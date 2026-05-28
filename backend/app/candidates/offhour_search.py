"""Off-hour potential stock search service.

Runs after market close or on non-trading days to collect broader
potential candidates, score them via the existing CandidateScoringService,
track lifecycle state via CandidateLifecycleService, and persist
auditable run records to SQLite.

This module is observation/simulation only — no live trading.
"""

import json
from datetime import datetime
from typing import Any

from app.candidates.auto_discovery import AutoDiscoveryScanner
from app.candidates.lifecycle import CandidateLifecycleService
from app.candidates.scoring import CandidateScoringService
from app.config import settings
from app.storage.sqlite_store import SQLiteStore


class OffhourPotentialSearchService:
    """Broader off-hour scan → lifecycle → score → persist pipeline."""

    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, limit: int = 100, persist: bool = True) -> dict[str, Any]:
        """Execute a full off-hour potential search run.

        1. Fetch market-wide spot data (reuses AutoDiscoveryScanner).
        2. Register candidates in lifecycle service.
        3. Score all via CandidateScoringService.
        4. Persist run record + items.
        5. Return structured result.
        """
        safe_limit = max(1, min(limit, 500))
        run_id: int | None = None
        errors: list[str] = []

        # Step 1 — auto-discovery scan (broader limit for off-hour)
        try:
            discovery = AutoDiscoveryScanner().scan(
                limit=safe_limit,
                persist=persist,
            )
        except Exception as exc:
            errors.append(f"auto_discovery_scan_failed: {exc}")
            return self._failed_result(
                source="offhour_potential_search",
                errors=errors,
                persist=persist,
            )

        discovery_status = discovery.get("status", "unknown")
        source = discovery.get("source", "offhour_potential_search")
        total_scanned = int(discovery.get("total_scanned", 0))
        items_raw: list[dict[str, Any]] = discovery.get("items", [])
        stored_count = int(discovery.get("stored_count", len(items_raw)))

        if discovery_status == "failed":
            errors.append(f"discovery_failed: {discovery.get('error', 'unknown')}")

        if discovery.get("fallback_error"):
            errors.append(f"primary_source_fallback: {discovery['fallback_error']}")

        # Step 2 — score all lifecycle candidates
        scored_items: list[dict[str, Any]] = []
        scored_count = 0
        try:
            scoring_svc = CandidateScoringService()
            score_result = scoring_svc.score_from_lifecycle(
                limit=safe_limit,
                persist=persist,
            )
            scored_count = int(score_result.get("scored_count", 0))
            scored_items = score_result.get("scores", score_result.get("top_scores", []))
        except Exception as exc:
            errors.append(f"scoring_failed: {exc}")

        # Step 3 — build enriched item list
        enriched = self._enrich_items(items_raw, scored_items)

        # Step 4 — top scored symbols
        top_scored = sorted(enriched, key=lambda x: -float(x.get("potential_score") or 0))[:10]
        top_symbols = [item["symbol"] for item in top_scored[:5]]

        # Step 5 — persist run
        notes = (
            f"off-hour search at {datetime.now().isoformat(timespec='seconds')}; "
            f"scanned {total_scanned}, stored {stored_count}, scored {scored_count}"
        )
        summary = {
            "discovery_status": discovery_status,
            "total_scanned": total_scanned,
            "stored_count": stored_count,
            "scored_count": scored_count,
            "top_symbols": top_symbols,
            "discovery_counts": {
                "limit_up": int(discovery.get("limit_up_count", 0)),
                "near_limit_up": int(discovery.get("near_limit_up_count", 0)),
                "strong_mover": int(discovery.get("strong_mover_count", 0)),
            },
            "errors": errors,
        }

        if persist:
            run_id = self._persist_run(
                status="completed" if discovery_status != "failed" else "partial",
                source=source,
                total_scanned=total_scanned,
                stored_count=stored_count,
                scored_count=scored_count,
                notes=notes,
                errors=errors,
                summary=summary,
            )
            self._persist_items(run_id, enriched, source)

        return {
            "run_id": run_id,
            "status": "completed" if discovery_status != "failed" else "partial",
            "source": source,
            "total_scanned": total_scanned,
            "stored_count": stored_count,
            "scored_count": scored_count,
            "top_scored_symbols": top_symbols,
            "top_scored_items": top_scored[:5],
            "notes": notes,
            "errors": errors,
        }

    def latest_run(self) -> dict[str, Any] | None:
        """Return the most recent potential search run with its items."""
        run = self.store.fetch_one(
            """
            SELECT id, status, source, total_scanned, stored_count,
                   scored_count, notes, errors_json, summary_json,
                   created_at, completed_at
            FROM potential_search_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not run:
            return None
        return self._hydrate_run(run)

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent potential search runs (without items)."""
        rows = self.store.fetch_all(
            """
            SELECT id, status, source, total_scanned, stored_count,
                   scored_count, notes, errors_json, summary_json,
                   created_at, completed_at
            FROM potential_search_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        result = []
        for row in rows:
            row["errors"] = json.loads(row.pop("errors_json") or "[]")
            row["summary"] = json.loads(row.pop("summary_json") or "{}")
            result.append(row)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _failed_result(
        self,
        source: str,
        errors: list[str],
        persist: bool,
    ) -> dict[str, Any]:
        run_id = None
        if persist:
            run_id = self._persist_run(
                status="failed",
                source=source,
                total_scanned=0,
                stored_count=0,
                scored_count=0,
                notes="; ".join(errors),
                errors=errors,
                summary={"errors": errors},
            )
        return {
            "run_id": run_id,
            "status": "failed",
            "source": source,
            "total_scanned": 0,
            "stored_count": 0,
            "scored_count": 0,
            "top_scored_symbols": [],
            "top_scored_items": [],
            "notes": "; ".join(errors),
            "errors": errors,
        }

    def _enrich_items(
        self,
        discovery_items: list[dict[str, Any]],
        scored_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge discovery items with scored data."""
        scored_map: dict[str, dict[str, Any]] = {}
        for item in scored_items:
            scored_map[item["symbol"]] = item

        lifecycle_svc = CandidateLifecycleService()
        lifecycle_map: dict[str, dict[str, Any]] = {}
        try:
            for row in lifecycle_svc.list_current(limit=500):
                lifecycle_map[row["symbol"]] = row
        except Exception:
            pass

        enriched: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in discovery_items:
            symbol = item.get("symbol", "")
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            score_data = scored_map.get(symbol, {})
            lc_data = lifecycle_map.get(symbol, {})
            enriched.append({
                "symbol": symbol,
                "name": item.get("name"),
                "current_price": item.get("current_price"),
                "pct_change": item.get("pct_change"),
                "turnover_rate": item.get("turnover_rate"),
                "amount": item.get("amount"),
                "lifecycle_state": lc_data.get("state", "unknown"),
                "potential_score": float(score_data.get("total_score") or 0),
                "reasons": score_data.get("reasons", item.get("reasons", [])),
                "components": score_data.get("components", {}),
                "source": item.get("source", "offhour_search"),
                "raw": item.get("raw", {}),
            })

        # Also include scored items not in discovery (already in lifecycle)
        for symbol, score_data in scored_map.items():
            if symbol in seen:
                continue
            seen.add(symbol)
            lc_data = lifecycle_map.get(symbol, {})
            enriched.append({
                "symbol": symbol,
                "name": score_data.get("name"),
                "current_price": None,
                "pct_change": None,
                "turnover_rate": None,
                "amount": None,
                "lifecycle_state": lc_data.get("state", score_data.get("state", "unknown")),
                "potential_score": float(score_data.get("total_score") or 0),
                "reasons": score_data.get("reasons", []),
                "components": score_data.get("components", {}),
                "source": "lifecycle_scored",
                "raw": {},
            })

        return enriched

    def _persist_run(
        self,
        status: str,
        source: str,
        total_scanned: int,
        stored_count: int,
        scored_count: int,
        notes: str,
        errors: list[str],
        summary: dict[str, Any],
    ) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO potential_search_runs(
                    status, source, total_scanned, stored_count, scored_count,
                    notes, errors_json, summary_json, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    status,
                    source,
                    total_scanned,
                    stored_count,
                    scored_count,
                    notes,
                    json.dumps(errors, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def _persist_items(
        self,
        run_id: int,
        items: list[dict[str, Any]],
        source: str,
    ) -> int:
        count = 0
        with self.store.connect() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT INTO potential_search_items(
                        run_id, symbol, name, current_price, pct_change,
                        turnover_rate, amount, lifecycle_state, potential_score,
                        reasons_json, components_json, source, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        item.get("symbol"),
                        item.get("name"),
                        item.get("current_price"),
                        item.get("pct_change"),
                        item.get("turnover_rate"),
                        item.get("amount"),
                        item.get("lifecycle_state"),
                        item.get("potential_score"),
                        json.dumps(item.get("reasons", []), ensure_ascii=False),
                        json.dumps(item.get("components", {}), ensure_ascii=False, default=str),
                        item.get("source") or source,
                        json.dumps(item.get("raw", {}), ensure_ascii=False, default=str),
                    ),
                )
                count += 1
        return count

    def _hydrate_run(self, run: dict[str, Any]) -> dict[str, Any]:
        run["errors"] = json.loads(run.pop("errors_json") or "[]")
        run["summary"] = json.loads(run.pop("summary_json") or "{}")
        items = self.store.fetch_all(
            """
            SELECT id, run_id, symbol, name, current_price, pct_change,
                   turnover_rate, amount, lifecycle_state, potential_score,
                   reasons_json, components_json, source, raw_json, created_at
            FROM potential_search_items
            WHERE run_id = ?
            ORDER BY potential_score DESC, id
            """,
            (run["id"],),
        )
        for item in items:
            item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
            item["components"] = json.loads(item.pop("components_json") or "{}")
            item["raw"] = json.loads(item.pop("raw_json") or "{}")
        run["items"] = items
        run["top_scored_items"] = items[:5]
        run["top_scored_symbols"] = [item["symbol"] for item in items[:5]]
        return run
