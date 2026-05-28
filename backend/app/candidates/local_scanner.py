import json
from typing import Any

from app.candidates.auto_discovery import AutoDiscoveryScanner
from app.candidates.lifecycle import CandidateLifecycleService
from app.candidates.scoring import CandidateScoringService
from app.config import settings
from app.learning.phase_matcher import PhaseSimilarityService
from app.storage.sqlite_store import SQLiteStore


class LocalCandidateScanner:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.phase_similarity = PhaseSimilarityService()
        self.auto_discovery = AutoDiscoveryScanner()
        self.lifecycle = CandidateLifecycleService()
        self.scoring = CandidateScoringService()

    def scan(self, limit: int = 100, persist: bool = True) -> dict[str, Any]:
        rows = self.store.fetch_all(
            """
            SELECT symbol, name, current_price, pct_change, five_day_pct,
                   operation_cost_line, sell_target, stop_loss, risk_level,
                   profit_rate, pb, pe_ttm, limit_up_count, test_line_count,
                   score, rating, dataset_name, source_file
            FROM stock_profiles
            WHERE current_price IS NOT NULL
            ORDER BY
                CASE rating WHEN '优秀' THEN 0 WHEN '及格' THEN 1 ELSE 2 END,
                score DESC,
                symbol
            """
        )

        merged_rows = rows + self._auto_discovered_rows()
        deduped = self._with_user_notes(self._dedupe(merged_rows))
        buckets = {"strong": [], "watch": [], "rejected": []}
        for row in deduped[: max(1, min(limit, 500))]:
            tier, reasons = self._classify(row)
            enriched = dict(row)
            phase_guardrail = self.phase_similarity.latest_guardrail(enriched["symbol"])
            if phase_guardrail:
                tier = "watch" if tier == "strong" else tier
                enriched["phase_guardrail"] = phase_guardrail
                reasons.append(phase_guardrail["reason"])
            enriched["tier"] = tier
            enriched["reasons"] = reasons
            buckets[tier].append(enriched)

        result = {
            "source": "local_stock_profiles+auto_discovery",
            "total_scanned": len(deduped),
            "strong_count": len(buckets["strong"]),
            "watch_count": len(buckets["watch"]),
            "rejected_count": len(buckets["rejected"]),
            "buckets": buckets,
        }
        if persist:
            result["scan_id"] = self._persist(result)
            result["lifecycle"] = self.lifecycle.sync_from_scan(result)
            result["scoring"] = self.scoring.score_from_lifecycle(limit=min(limit, 500), persist=True)
        return result

    def _dedupe(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best: dict[str, dict[str, Any]] = {}
        for row in rows:
            symbol = row.get("symbol")
            if not symbol or not self._is_a_share(symbol):
                continue
            current = best.get(symbol)
            if current is None or self._rank(row) < self._rank(current):
                best[symbol] = row
        return sorted(best.values(), key=self._rank)

    def _is_a_share(self, symbol: str) -> bool:
        if len(symbol) != 8:
            return False
        exchange = symbol[:2]
        code = symbol[2:]
        return exchange in {"SH", "SZ"} and code.isdigit()

    def _rank(self, row: dict[str, Any]) -> tuple[int, float, str]:
        rating_rank = {
            "limit_up_priority": -2,
            "near_limit_up_priority": -1,
            "auto_discovered_strong_mover": 1,
            "重点关注": -1,
            "优秀": 0,
            "训练关注": 1,
            "及格": 2,
            "不关注": 4,
        }.get(row.get("rating"), 3)
        score = row.get("score")
        return (rating_rank, -(float(score) if score is not None else -999), row.get("symbol") or "")

    def _auto_discovered_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.auto_discovery.latest_by_symbol(limit=200):
            discovery_type = item.get("discovery_type")
            if discovery_type == "limit_up":
                rating = "limit_up_priority"
            elif discovery_type == "near_limit_up":
                rating = "near_limit_up_priority"
            else:
                rating = "auto_discovered_strong_mover"
            rows.append(
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "current_price": item.get("current_price"),
                    "pct_change": item.get("pct_change"),
                    "five_day_pct": None,
                    "operation_cost_line": None,
                    "sell_target": None,
                    "stop_loss": None,
                    "risk_level": "auto_discovery_pending_review",
                    "profit_rate": None,
                    "pb": None,
                    "pe_ttm": None,
                    "limit_up_count": 1 if discovery_type == "limit_up" else None,
                    "test_line_count": None,
                    "score": item.get("priority"),
                    "rating": rating,
                    "dataset_name": "auto_discovery",
                    "source_file": item.get("source"),
                    "auto_discovery": {
                        "id": item.get("id"),
                        "discovery_type": discovery_type,
                        "pct_change": item.get("pct_change"),
                        "priority": item.get("priority"),
                        "reasons": item.get("reasons", []),
                        "created_at": item.get("created_at"),
                    },
                }
            )
        return rows

    def _with_user_notes(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_symbol = {row["symbol"]: dict(row) for row in rows if row.get("symbol")}
        notes = self.store.fetch_all(
            """
            SELECT symbol, name, note_type, priority, content
            FROM user_stock_notes
            ORDER BY priority DESC
            """
        )
        for note in notes:
            symbol = note["symbol"]
            existing = by_symbol.get(symbol)
            if existing:
                existing["user_note_type"] = note["note_type"]
                existing["user_note_priority"] = note["priority"]
                existing["user_note"] = note["content"]
                if note["note_type"] == "focus_priority":
                    existing["rating"] = "重点关注"
                    existing["score"] = max(float(existing.get("score") or 0), float(note["priority"]))
                elif note["note_type"] == "completed_distribution_training":
                    existing["rating"] = "出货完成训练样本"
                    existing["risk_level"] = "短期不追高"
                    existing["score"] = max(float(existing.get("score") or 0), float(note["priority"]))
                by_symbol[symbol] = existing
                continue

            by_symbol[symbol] = {
                "symbol": symbol,
                "name": note["name"],
                "current_price": None,
                "pct_change": None,
                "five_day_pct": None,
                "operation_cost_line": None,
                "sell_target": None,
                "stop_loss": None,
                "risk_level": "短期不追高"
                if note["note_type"] == "completed_distribution_training"
                else "待验证",
                "profit_rate": None,
                "pb": None,
                "pe_ttm": None,
                "limit_up_count": None,
                "test_line_count": None,
                "score": note["priority"],
                "rating": "出货完成训练样本"
                if note["note_type"] == "completed_distribution_training"
                else "训练关注",
                "dataset_name": "用户确认知识",
                "source_file": "user_knowledge_seed.json",
                "user_note_type": note["note_type"],
                "user_note_priority": note["priority"],
                "user_note": note["content"],
            }
        return sorted(by_symbol.values(), key=self._rank)

    def _classify(self, row: dict[str, Any]) -> tuple[str, list[str]]:
        reasons: list[str] = []
        score = float(row.get("score") or 0)
        rating = row.get("rating")
        risk = row.get("risk_level")
        pb = row.get("pb")

        if rating:
            reasons.append(f"档案评价: {rating}")
        if score:
            reasons.append(f"自选股积分: {score:g}")
        if risk:
            reasons.append(f"风险标记: {risk}")
        if pb is not None:
            reasons.append(f"市净率: {float(pb):.2f}")

        if row.get("user_note"):
            reasons.append(str(row["user_note"]))
        if row.get("auto_discovery"):
            discovery = row["auto_discovery"]
            reasons.extend(discovery.get("reasons", []))

        if rating in {"limit_up_priority", "near_limit_up_priority", "auto_discovered_strong_mover"}:
            return "watch", reasons + ["auto-discovered candidate; observe first and require phase guardrail"]
        if risk == "短期不追高" or rating == "出货完成训练样本":
            return "watch", reasons + ["主力拉升出货完成训练样本，短期只复盘不追高"]
        if rating == "重点关注":
            return "strong", reasons
        if rating == "优秀" and score >= 15 and risk in (None, "小"):
            return "strong", reasons
        if rating in ("优秀", "及格", "训练关注") and risk != "大":
            return "watch", reasons
        return "rejected", reasons or ["缺少足够的候选池评分依据"]

    def _persist(self, result: dict[str, Any]) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO candidate_scans(
                    source, total_scanned, strong_count, watch_count, rejected_count
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result["source"],
                    result["total_scanned"],
                    result["strong_count"],
                    result["watch_count"],
                    result["rejected_count"],
                ),
            )
            scan_id = int(cursor.lastrowid)
            for tier, items in result["buckets"].items():
                for item in items:
                    conn.execute(
                        """
                        INSERT INTO candidate_scan_items(
                            scan_id, symbol, name, tier, score, rating, risk_level,
                            current_price, operation_cost_line, sell_target,
                            reasons_json, raw_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            scan_id,
                            item.get("symbol"),
                            item.get("name"),
                            tier,
                            item.get("score"),
                            item.get("rating"),
                            item.get("risk_level"),
                            item.get("current_price"),
                            item.get("operation_cost_line"),
                            item.get("sell_target"),
                            json.dumps(item.get("reasons", []), ensure_ascii=False),
                            json.dumps(item, ensure_ascii=False, default=str),
                        ),
                    )
            return scan_id

    def latest_scan(self) -> dict[str, Any] | None:
        scan = self.store.fetch_one(
            """
            SELECT id, source, total_scanned, strong_count, watch_count,
                   rejected_count, created_at
            FROM candidate_scans
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not scan:
            return None
        items = self.store.fetch_all(
            """
            SELECT symbol, name, tier, score, rating, risk_level, current_price,
                   operation_cost_line, sell_target, reasons_json, raw_json
            FROM candidate_scan_items
            WHERE scan_id = ?
            ORDER BY
                CASE tier WHEN 'strong' THEN 0 WHEN 'watch' THEN 1 ELSE 2 END,
                score DESC,
                symbol
            """,
            (scan["id"],),
        )
        buckets = {"strong": [], "watch": [], "rejected": []}
        for item in items:
            tier = item["tier"]
            parsed = json.loads(item["raw_json"])
            parsed["reasons"] = json.loads(item["reasons_json"])
            buckets[tier].append(parsed)
        scan["buckets"] = buckets
        return scan
