import json
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


LIFECYCLE_STATES = {
    "auto_discovered": "自动发现",
    "pending_review": "待复核",
    "focus_watch": "重点观察",
    "phase_guarded": "阶段风控",
    "rejected": "淘汰",
}


class CandidateLifecycleService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def record_auto_discovery(self, items: list[dict[str, Any]], source: str) -> None:
        for item in items:
            self.upsert_state(
                symbol=item["symbol"],
                name=item.get("name"),
                state="auto_discovered",
                source=source,
                score=item.get("priority"),
                rating=item.get("discovery_type"),
                risk_level="auto_discovery_pending_review",
                reason="; ".join(item.get("reasons", [])),
                payload=item,
                event_type="auto_discovery",
            )

    def sync_from_scan(self, scan: dict[str, Any]) -> dict[str, Any]:
        changes = []
        for tier, items in scan.get("buckets", {}).items():
            for item in items:
                state = self._state_from_scan_item(tier, item)
                change = self.upsert_state(
                    symbol=item["symbol"],
                    name=item.get("name"),
                    state=state,
                    source=f"candidate_scan:{scan.get('scan_id') or 'memory'}",
                    score=item.get("score"),
                    rating=item.get("rating"),
                    risk_level=item.get("risk_level"),
                    reason=self._reason(item),
                    payload=item,
                    event_type="candidate_scan_sync",
                )
                changes.append(change)
        return {
            "synced_count": len(changes),
            "changed_count": len([item for item in changes if item.get("changed")]),
            "state_counts": self.summary()["state_counts"],
        }

    def upsert_state(
        self,
        symbol: str,
        name: str | None,
        state: str,
        source: str,
        score: float | None = None,
        rating: str | None = None,
        risk_level: str | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
        event_type: str = "state_update",
    ) -> dict[str, Any]:
        if state not in LIFECYCLE_STATES:
            raise ValueError(f"Unknown candidate lifecycle state: {state}")
        current = self.store.fetch_one(
            "SELECT symbol, state FROM candidate_lifecycle WHERE symbol = ?",
            (symbol,),
        )
        from_state = current.get("state") if current else None
        changed = from_state != state
        raw_json = json.dumps(payload or {}, ensure_ascii=False, default=str)
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO candidate_lifecycle(
                    symbol, name, state, score, rating, risk_level,
                    source, reason, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    state = excluded.state,
                    score = excluded.score,
                    rating = excluded.rating,
                    risk_level = excluded.risk_level,
                    source = excluded.source,
                    reason = excluded.reason,
                    raw_json = excluded.raw_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    symbol,
                    name,
                    state,
                    score,
                    rating,
                    risk_level,
                    source,
                    reason,
                    raw_json,
                ),
            )
            if changed:
                conn.execute(
                    """
                    INSERT INTO candidate_lifecycle_events(
                        symbol, name, from_state, to_state, event_type,
                        source, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        name,
                        from_state,
                        state,
                        event_type,
                        source,
                        raw_json,
                    ),
                )
        return {
            "symbol": symbol,
            "from_state": from_state,
            "to_state": state,
            "changed": changed,
        }

    def list_current(
        self,
        state: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if state:
            where = "WHERE state = ?"
            params.append(state)
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT symbol, name, state, score, rating, risk_level, source,
                   reason, raw_json, first_seen_at, updated_at
            FROM candidate_lifecycle
            {where}
            ORDER BY
                CASE state
                    WHEN 'phase_guarded' THEN 0
                    WHEN 'focus_watch' THEN 1
                    WHEN 'pending_review' THEN 2
                    WHEN 'auto_discovered' THEN 3
                    ELSE 4
                END,
                score DESC,
                updated_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._hydrate(row) for row in rows]

    def events(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if symbol:
            where = "WHERE symbol = ?"
            params.append(symbol)
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT id, symbol, name, from_state, to_state, event_type,
                   source, payload_json, created_at
            FROM candidate_lifecycle_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        for row in rows:
            row["payload"] = json.loads(row.pop("payload_json") or "{}")
        return rows

    def summary(self) -> dict[str, Any]:
        rows = self.store.fetch_all(
            """
            SELECT state, COUNT(*) AS count
            FROM candidate_lifecycle
            GROUP BY state
            """
        )
        counts = {state: 0 for state in LIFECYCLE_STATES}
        for row in rows:
            counts[row["state"]] = row["count"]
        latest_events = self.events(limit=8)
        return {
            "state_counts": counts,
            "state_labels": LIFECYCLE_STATES,
            "latest_events": latest_events,
        }

    def _state_from_scan_item(self, tier: str, item: dict[str, Any]) -> str:
        if item.get("phase_guardrail"):
            return "phase_guarded"
        rating = item.get("rating")
        risk = item.get("risk_level")
        if risk == "短期不追高" or rating == "出货完成训练样本":
            return "phase_guarded"
        if tier == "strong" or rating == "重点关注":
            return "focus_watch"
        if tier == "watch":
            return "pending_review"
        return "rejected"

    def _reason(self, item: dict[str, Any]) -> str:
        reasons = item.get("reasons") or []
        if reasons:
            return "; ".join(str(reason) for reason in reasons[:6])
        return item.get("rating") or item.get("risk_level") or "candidate scan sync"

    def _hydrate(self, row: dict[str, Any]) -> dict[str, Any]:
        row["state_label"] = LIFECYCLE_STATES.get(row["state"], row["state"])
        row["raw"] = json.loads(row.pop("raw_json") or "{}")
        return row
