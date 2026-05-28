import json
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


class CandidateScoringService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def score_from_lifecycle(self, limit: int = 200, persist: bool = True) -> dict[str, Any]:
        rows = self.store.fetch_all(
            """
            SELECT symbol, name, state, score, rating, risk_level, source,
                   reason, raw_json, updated_at
            FROM candidate_lifecycle
            ORDER BY updated_at DESC, score DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        )
        scores = [self.score_row(row, persist=persist) for row in rows]
        ordered_scores = sorted(scores, key=lambda item: item["total_score"], reverse=True)
        return {
            "scored_count": len(scores),
            "scores": ordered_scores,
            "top_scores": ordered_scores[:10],
        }

    def score_symbols(
        self,
        symbols: list[str],
        source: str,
        persist: bool = True,
    ) -> list[dict[str, Any]]:
        results = []
        for symbol in symbols:
            row = self.store.fetch_one(
                """
                SELECT symbol, name, state, score, rating, risk_level, source,
                       reason, raw_json, updated_at
                FROM candidate_lifecycle
                WHERE symbol = ?
                """,
                (symbol,),
            )
            if not row:
                continue
            row["source"] = source
            results.append(self.score_row(row, persist=persist))
        return results

    def score_row(self, row: dict[str, Any], persist: bool = True) -> dict[str, Any]:
        raw = json.loads(row.get("raw_json") or "{}")
        auto = raw.get("auto_discovery") or raw if raw.get("discovery_type") else {}
        phase = self._latest_phase(row["symbol"])
        components = {
            "discovery_score": self._discovery_score(auto, row),
            "volume_score": self._volume_score(auto, raw),
            "phase_score": self._phase_score(phase),
            "lifecycle_score": self._lifecycle_score(row.get("state")),
            "focus_score": self._focus_score(row, raw),
            "risk_penalty": self._risk_penalty(row, raw, phase),
        }
        total = (
            components["discovery_score"]
            + components["volume_score"]
            + components["phase_score"]
            + components["lifecycle_score"]
            + components["focus_score"]
            - components["risk_penalty"]
        )
        total = round(max(0.0, min(100.0, total)), 2)
        reasons = self._reasons(row, auto, phase, components, total)
        result = {
            "symbol": row["symbol"],
            "name": row.get("name"),
            "total_score": total,
            "rating": row.get("rating"),
            "state": row.get("state"),
            "state_score": row.get("score"),
            "reasons": reasons,
            "components": components,
            "source": row.get("source") or "candidate_scoring",
            "phase": phase,
            "raw": raw,
        }
        if persist:
            result["id"] = self._persist(result)
        return result

    def latest_scores(
        self,
        limit: int = 50,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if state:
            where = "WHERE cs.state = ?"
            params.append(state)
        params.append(max(1, min(limit, 300)))
        rows = self.store.fetch_all(
            f"""
            SELECT cs.*
            FROM candidate_scores cs
            JOIN (
                SELECT symbol, MAX(id) AS latest_id
                FROM candidate_scores
                GROUP BY symbol
            ) latest ON latest.latest_id = cs.id
            {where}
            ORDER BY cs.total_score DESC, cs.id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._hydrate_score(row) for row in rows]

    def summary(self, limit: int = 10) -> dict[str, Any]:
        latest = self.latest_scores(limit=limit)
        rows = self.store.fetch_all(
            """
            SELECT state, COUNT(*) AS count, AVG(total_score) AS avg_score, MAX(total_score) AS max_score
            FROM (
                SELECT cs.*
                FROM candidate_scores cs
                JOIN (
                    SELECT symbol, MAX(id) AS latest_id
                    FROM candidate_scores
                    GROUP BY symbol
                ) latest ON latest.latest_id = cs.id
            )
            GROUP BY state
            """
        )
        return {
            "top_scores": latest,
            "state_score_summary": rows,
        }

    def _latest_phase(self, symbol: str) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT id, summary_json, matches_json, created_at
            FROM main_force_phase_matches
            WHERE target_symbol = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (symbol,),
        )
        if not row:
            return None
        summary = json.loads(row["summary_json"] or "{}")
        best = summary.get("best_match") or {}
        return {
            "match_id": row["id"],
            "best_core_symbol": best.get("core_symbol"),
            "best_core_name": best.get("core_name"),
            "score": float(best.get("score") or 0),
            "target_latest_phase": summary.get("target_latest_phase"),
            "diagnosis": summary.get("diagnosis"),
            "created_at": row.get("created_at"),
        }

    def _discovery_score(self, auto: dict[str, Any], row: dict[str, Any]) -> float:
        discovery_type = auto.get("discovery_type") or row.get("rating")
        pct_change = self._float(auto.get("pct_change"))
        base = {
            "limit_up": 25.0,
            "limit_up_priority": 25.0,
            "near_limit_up": 18.0,
            "near_limit_up_priority": 18.0,
            "strong_mover": 10.0,
            "auto_discovered_strong_mover": 10.0,
        }.get(discovery_type, 0.0)
        pct_bonus = min(max(float(pct_change or 0), 0.0), 20.0) * 0.35
        return round(min(35.0, base + pct_bonus), 4)

    def _volume_score(self, auto: dict[str, Any], raw: dict[str, Any]) -> float:
        turnover = self._float(auto.get("turnover_rate") or raw.get("turnover_rate"))
        amount = self._float(auto.get("amount") or raw.get("amount"))
        turnover_score = min(float(turnover or 0), 30.0) * 0.35
        amount_score = min(float(amount or 0) / 100_000_000, 30.0) * 0.15
        return round(min(15.0, turnover_score + amount_score), 4)

    def _phase_score(self, phase: dict[str, Any] | None) -> float:
        if not phase:
            return 0.0
        score = float(phase.get("score") or 0)
        latest_phase = phase.get("target_latest_phase")
        core = phase.get("best_core_symbol")
        if core == "SZ002115":
            return round(min(25.0, score * 0.25), 4)
        if core == "SZ002081" and latest_phase == "markup":
            return round(min(10.0, score * 0.12), 4)
        if core == "SZ002081":
            return round(min(5.0, score * 0.05), 4)
        return round(min(12.0, score * 0.12), 4)

    def _lifecycle_score(self, state: str | None) -> float:
        return {
            "focus_watch": 12.0,
            "pending_review": 8.0,
            "auto_discovered": 5.0,
            "phase_guarded": -8.0,
            "rejected": -15.0,
        }.get(state or "", 0.0)

    def _focus_score(self, row: dict[str, Any], raw: dict[str, Any]) -> float:
        rating = row.get("rating") or raw.get("rating")
        if rating == "重点关注":
            return 15.0
        if rating == "优秀":
            return 8.0
        if rating == "及格":
            return 4.0
        return 0.0

    def _risk_penalty(
        self,
        row: dict[str, Any],
        raw: dict[str, Any],
        phase: dict[str, Any] | None,
    ) -> float:
        penalty = 0.0
        risk = row.get("risk_level") or raw.get("risk_level")
        rating = row.get("rating") or raw.get("rating")
        if risk in {"短期不追高", "大"}:
            penalty += 25.0
        if rating == "出货完成训练样本":
            penalty += 25.0
        if row.get("state") == "rejected":
            penalty += 15.0
        if row.get("state") == "phase_guarded":
            penalty += 18.0
        if phase:
            score = float(phase.get("score") or 0)
            if (
                phase.get("best_core_symbol") == "SZ002081"
                and phase.get("target_latest_phase") in {"distribution", "post_distribution_watch"}
            ):
                penalty += min(40.0, score * 0.45)
        return round(penalty, 4)

    def _reasons(
        self,
        row: dict[str, Any],
        auto: dict[str, Any],
        phase: dict[str, Any] | None,
        components: dict[str, float],
        total: float,
    ) -> list[str]:
        reasons = [f"综合潜力分 {total:.1f}"]
        if components["discovery_score"] > 0:
            reasons.append(f"涨停/强势发现 +{components['discovery_score']:.1f}")
        if components["volume_score"] > 0:
            reasons.append(f"成交与换手 +{components['volume_score']:.1f}")
        if phase:
            reasons.append(
                f"阶段最像 {phase.get('best_core_symbol')}，相似度 {phase.get('score'):.1f}"
            )
        if components["focus_score"] > 0:
            reasons.append(f"档案/重点关注 +{components['focus_score']:.1f}")
        if components["risk_penalty"] > 0:
            reasons.append(f"风险扣分 -{components['risk_penalty']:.1f}")
        if row.get("reason"):
            reasons.append(str(row["reason"]))
        if auto.get("reasons"):
            reasons.extend(str(item) for item in auto["reasons"][:3])
        return reasons[:10]

    def _persist(self, result: dict[str, Any]) -> int:
        components = result["components"]
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO candidate_scores(
                    symbol, name, total_score, discovery_score, volume_score,
                    phase_score, lifecycle_score, focus_score, risk_penalty,
                    rating, state, source, reasons_json, components_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["symbol"],
                    result.get("name"),
                    result["total_score"],
                    components["discovery_score"],
                    components["volume_score"],
                    components["phase_score"],
                    components["lifecycle_score"],
                    components["focus_score"],
                    components["risk_penalty"],
                    result.get("rating"),
                    result.get("state"),
                    result.get("source") or "candidate_scoring",
                    json.dumps(result.get("reasons", []), ensure_ascii=False),
                    json.dumps(components, ensure_ascii=False, default=str),
                    json.dumps(result, ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def _hydrate_score(self, row: dict[str, Any]) -> dict[str, Any]:
        row["reasons"] = json.loads(row.pop("reasons_json") or "[]")
        row["components"] = json.loads(row.pop("components_json") or "{}")
        row["raw"] = json.loads(row.pop("raw_json") or "{}")
        return row

    def _float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
