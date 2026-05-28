import json
import re
from collections.abc import Iterable
from typing import Any

from app.storage.sqlite_store import SQLiteStore


class KnowledgeRepository:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def list_principles(self) -> list[dict[str, Any]]:
        return self.store.fetch_all(
            """
            SELECT id, name, description, source, category, severity
            FROM principles
            ORDER BY id
            """
        )

    def list_strategies(self, category: str | None = None) -> list[dict[str, Any]]:
        if category:
            return self.store.fetch_all(
                """
                SELECT id, category, name, trigger_condition, operation_standard,
                       position_management, indicators, risk_control, notes, source
                FROM strategies
                WHERE category = ?
                ORDER BY id
                """,
                (category,),
            )
        return self.store.fetch_all(
            """
            SELECT id, category, name, trigger_condition, operation_standard,
                   position_management, indicators, risk_control, notes, source
            FROM strategies
            ORDER BY category, id
            """
        )

    def related_strategies(self, rule_ids: Iterable[str]) -> list[dict[str, Any]]:
        categories = {"buy", "sell", "position"}
        if any("dengzhan" in rule_id for rule_id in rule_ids):
            categories.add("selection")

        placeholders = ",".join("?" for _ in categories)
        return self.store.fetch_all(
            f"""
            SELECT id, category, name, trigger_condition, operation_standard,
                   position_management, indicators, risk_control, notes, source
            FROM strategies
            WHERE category IN ({placeholders})
            ORDER BY category, id
            """,
            tuple(sorted(categories)),
        )

    def search_cases(self, keywords: Iterable[str], case_type: str | None = None) -> list[dict[str, Any]]:
        keyword_list = [keyword for keyword in dict.fromkeys(keywords) if keyword]
        if not keyword_list and not case_type:
            return []

        clauses = []
        params: list[Any] = []
        if keyword_list:
            keyword_clauses = []
            for keyword in keyword_list:
                keyword_clauses.append("(stock_text LIKE ? OR operation LIKE ? OR lesson LIKE ?)")
                like = f"%{keyword}%"
                params.extend([like, like, like])
            clauses.append(f"({' OR '.join(keyword_clauses)})")
        if case_type:
            clauses.append("case_type = ?")
            params.append(case_type)

        return self.store.fetch_all(
            f"""
            SELECT id, case_type, trade_date, stock_text, operation, result, lesson
            FROM trade_cases
            WHERE {' AND '.join(clauses)}
            ORDER BY
                CASE case_type WHEN 'failure' THEN 0 ELSE 1 END,
                id
            LIMIT 20
            """,
            tuple(params),
        )

    def search_trade_records(self, keywords: Iterable[str]) -> list[dict[str, Any]]:
        keyword_list = [keyword for keyword in dict.fromkeys(keywords) if keyword]
        if not keyword_list:
            return []

        clauses = []
        params: list[Any] = []
        for keyword in keyword_list:
            clauses.append("(stock_code LIKE ? OR stock_name LIKE ? OR remarks LIKE ?)")
            like = f"%{keyword}%"
            params.extend([like, like, like])

        return self.store.fetch_all(
            f"""
            SELECT trade_date, stock_code, stock_name, operation_type, reference_price,
                   pct_change_text, result, remarks
            FROM trade_records
            WHERE {' OR '.join(clauses)}
            ORDER BY trade_date DESC, id DESC
            LIMIT 30
            """,
            tuple(params),
        )

    def search_user_notes(self, keywords: Iterable[str]) -> list[dict[str, Any]]:
        keyword_list = [keyword for keyword in dict.fromkeys(keywords) if keyword]
        if not keyword_list:
            return []

        clauses = []
        params: list[Any] = []
        for keyword in keyword_list:
            clauses.append("(symbol LIKE ? OR name LIKE ? OR content LIKE ?)")
            like = f"%{keyword}%"
            params.extend([like, like, like])

        return self.store.fetch_all(
            f"""
            SELECT id, symbol, name, note_type, priority, content, tags_json
            FROM user_stock_notes
            WHERE {' OR '.join(clauses)}
            ORDER BY priority DESC, id
            LIMIT 20
            """,
            tuple(params),
        )

    def list_main_force_patterns(
        self,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if symbol:
            where = "WHERE symbol = ?"
            params.append(symbol)
        params.append(max(1, min(limit, 200)))
        rows = self.store.fetch_all(
            f"""
            SELECT id, symbol, name, pattern_type, status, priority,
                   phase_timeline_json, theory_tags_json, training_focus_json,
                   caution_notes_json, created_at
            FROM main_force_phase_patterns
            {where}
            ORDER BY priority DESC, id
            LIMIT ?
            """,
            tuple(params),
        )
        for row in rows:
            row["phase_timeline"] = json.loads(row.pop("phase_timeline_json") or "[]")
            row["theory_tags"] = json.loads(row.pop("theory_tags_json") or "[]")
            row["training_focus"] = json.loads(row.pop("training_focus_json") or "[]")
            row["caution_notes"] = json.loads(row.pop("caution_notes_json") or "[]")
        return rows

    def search_stock_profiles(self, keywords: Iterable[str], limit: int = 10) -> list[dict[str, Any]]:
        keyword_list = [keyword for keyword in dict.fromkeys(keywords) if keyword]
        if not keyword_list:
            return []

        clauses = []
        params: list[Any] = []
        for keyword in keyword_list:
            clauses.append("(symbol LIKE ? OR name LIKE ?)")
            like = f"%{keyword}%"
            params.extend([like, like])
        params.append(limit)

        return self.store.fetch_all(
            f"""
            SELECT symbol, name, current_price, pct_change, five_day_pct,
                   operation_cost_line, sell_target, stop_loss, risk_level,
                   profit_rate, pb, pe_ttm, limit_up_count, test_line_count,
                   score, rating, dataset_name, source_file
            FROM stock_profiles
            WHERE {' OR '.join(clauses)}
            ORDER BY
                CASE WHEN current_price IS NOT NULL THEN 0 ELSE 1 END,
                score DESC,
                symbol
            LIMIT ?
            """,
            tuple(params),
        )

    def best_stock_profile(self, keywords: Iterable[str]) -> dict[str, Any] | None:
        profiles = self.search_stock_profiles(keywords, limit=1)
        return profiles[0] if profiles else None

    def keywords_for_stock(self, symbol: str, name: str | None = None) -> list[str]:
        keywords = [symbol]
        code_match = re.search(r"(\d{6})", symbol)
        if code_match:
            keywords.append(code_match.group(1))
        if name:
            keywords.append(name)
        return [keyword for keyword in keywords if keyword]
