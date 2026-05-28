import json
import re
from statistics import mean
from typing import Any

from app.candidates.local_scanner import LocalCandidateScanner
from app.config import settings
from app.models import LearningBacktestResult, LearningReport, LearningSample
from app.storage.sqlite_store import SQLiteStore


POSITIVE_LABELS = {"success", "method_success", "focus_priority"}
NEGATIVE_LABELS = {"failure", "risk_failure"}
PENDING_LABELS = {"training_candidate", "watch", "pending"}
NO_BUY_TRAINING_LABELS = {"completed_distribution_training", "distribution_completed"}


class LearningService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def rebuild_samples(self) -> dict[str, Any]:
        samples = []
        samples.extend(self._samples_from_cases())
        samples.extend(self._samples_from_records())
        samples.extend(self._samples_from_user_notes())
        samples.extend(self._samples_from_stock_profiles())
        samples.extend(self._samples_from_main_force_patterns())

        with self.store.connect() as conn:
            for sample in samples:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO learning_samples(
                        id, source_type, source_id, symbol, name, label, outcome_score,
                        entry_price, exit_price, return_pct, risk_level, rating,
                        features_json, lessons_json, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sample["id"],
                        sample["source_type"],
                        sample["source_id"],
                        sample.get("symbol"),
                        sample.get("name"),
                        sample["label"],
                        sample["outcome_score"],
                        sample.get("entry_price"),
                        sample.get("exit_price"),
                        sample.get("return_pct"),
                        sample.get("risk_level"),
                        sample.get("rating"),
                        json.dumps(sample.get("features", {}), ensure_ascii=False, default=str),
                        json.dumps(sample.get("lessons", []), ensure_ascii=False, default=str),
                        json.dumps(sample.get("raw", {}), ensure_ascii=False, default=str),
                    ),
                )

        return {
            "sample_count": len(samples),
            "by_label": self.sample_counts_by_label(),
            "sources": {
                "trade_cases": len([item for item in samples if item["source_type"] == "trade_case"]),
                "trade_records": len(
                    [item for item in samples if item["source_type"] == "trade_record"]
                ),
                "user_stock_notes": len(
                    [item for item in samples if item["source_type"] == "user_stock_note"]
                ),
                "stock_profiles": len(
                    [item for item in samples if item["source_type"] == "stock_profile"]
                ),
                "main_force_phase_patterns": len(
                    [
                        item
                        for item in samples
                        if item["source_type"] == "main_force_phase_pattern"
                    ]
                ),
            },
        }

    def sample_counts_by_label(self) -> dict[str, int]:
        rows = self.store.fetch_all(
            """
            SELECT label, COUNT(*) AS count
            FROM learning_samples
            GROUP BY label
            ORDER BY count DESC, label
            """
        )
        return {row["label"]: int(row["count"]) for row in rows}

    def list_samples(
        self,
        label: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[LearningSample]:
        clauses = []
        params: list[Any] = []
        if label:
            clauses.append("label = ?")
            params.append(label)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM learning_samples
            {where}
            ORDER BY created_at DESC, id
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._sample_model(row) for row in rows]

    def run_backtest(self, strategy_name: str = "local_rule_v1") -> LearningBacktestResult:
        if not self.sample_counts_by_label():
            self.rebuild_samples()

        rows = self.store.fetch_all("SELECT * FROM learning_samples ORDER BY id")
        closed_rows = [row for row in rows if row["label"] not in PENDING_LABELS]
        predictions = []
        returns = []
        blocked_success_count = 0
        false_positive_count = 0
        pending_count = len(rows) - len(closed_rows)

        for row in closed_rows:
            features = json.loads(row["features_json"] or "{}")
            predicted_buy = self._predict_buy(row, features)
            actual_positive = row["label"] in POSITIVE_LABELS
            actual_negative = row["label"] in NEGATIVE_LABELS
            return_pct = self._sample_return(row)

            if predicted_buy and actual_positive:
                predictions.append(True)
                returns.append(return_pct)
            elif predicted_buy and actual_negative:
                predictions.append(False)
                returns.append(return_pct)
                false_positive_count += 1
            elif not predicted_buy and actual_positive:
                blocked_success_count += 1

        win_rate = (sum(1 for ok in predictions if ok) / len(predictions)) if predictions else 0.0
        avg_return = mean(returns) if returns else 0.0
        total_return = sum(returns) if returns else 0.0
        profit_loss_ratio = self._profit_loss_ratio(returns)
        max_drawdown = self._max_drawdown(returns)

        # Determine skipped due to missing data
        skipped_count = sum(1 for row in rows if "skipped" in str(row.get("label", "")).lower())

        result = LearningBacktestResult(
            strategy_name=strategy_name,
            sample_count=len(closed_rows),
            win_rate=round(win_rate, 4),
            avg_return=round(avg_return, 4),
            profit_loss_ratio=round(profit_loss_ratio, 4),
            max_drawdown=round(max_drawdown, 4),
            blocked_success_count=blocked_success_count,
            false_positive_count=false_positive_count,
            pending_count=pending_count,
            summary={
                "rule": "重点关注/优秀/高分样本优先，风险标记为大或有时降级观察",
                "predicted_trade_count": len(predictions),
                "total_return": round(total_return, 4),
                "skipped_count": skipped_count,
                "data_source_quality": "High (Local SQLite fallback)",
                "positive_labels": sorted(POSITIVE_LABELS),
                "negative_labels": sorted(NEGATIVE_LABELS),
                "pending_labels": sorted(PENDING_LABELS),
                "guardrail": "该结果只用于模拟权重评估，不产生实盘下单权限",
            },
        )
        result.id = self._persist_backtest(result)
        return result

    def generate_review_report(
        self,
        automation_run_id: int | None = None,
        report_type: str = "daily",
    ) -> LearningReport:
        if not self.sample_counts_by_label():
            self.rebuild_samples()
        backtest = self.run_backtest()

        latest_scan = LocalCandidateScanner().latest_scan()
        automation = None
        from app.automation.supervisor import AutomationSupervisor
        from app.monitoring.service import MonitoringService

        supervisor = AutomationSupervisor()
        if automation_run_id is not None:
            automation = supervisor.get_run(automation_run_id)
        else:
            automation = supervisor.latest_run()

        monitoring = MonitoringService().summary()

        strong = latest_scan["buckets"]["strong"] if latest_scan else []
        watch = latest_scan["buckets"]["watch"] if latest_scan else []
        skipped = []
        if automation:
            skipped = [
                item
                for item in automation.get("summary", {}).get("items", [])
                if item.get("status") == "skipped"
            ]

        focus_symbols = [
            {
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "rating": item.get("rating"),
                "risk_level": item.get("risk_level"),
                "reasons": item.get("reasons", [])[:4],
            }
            for item in (strong + watch)[:8]
        ]
        report = LearningReport(
            automation_run_id=automation_run_id,
            report_type=report_type,
            title="每日模拟学习复盘",
            summary={
                "candidate_snapshot": {
                    "strong_count": latest_scan.get("strong_count", 0) if latest_scan else 0,
                    "watch_count": latest_scan.get("watch_count", 0) if latest_scan else 0,
                    "rejected_count": latest_scan.get("rejected_count", 0) if latest_scan else 0,
                    "focus_symbols": focus_symbols,
                },
                "automation": automation.get("summary", {}) if automation else {},
                "monitoring_alerts": monitoring.get("alerts", [])[:10],
                "paper_simulation_outcomes": {
                    "win_rate": backtest.win_rate,
                    "avg_return": backtest.avg_return,
                    "profit_loss_ratio": backtest.profit_loss_ratio,
                    "max_drawdown": backtest.max_drawdown,
                },
                "readiness_fallback_quality": {
                    "skipped_count": len(skipped),
                    "fallback_note": "部分数据源由于接口限制或网络问题导致兜底或跳过，将在复盘中继续追踪。",
                },
                "lessons_learned": backtest.summary.get("rule"),
                "open_review_items": {
                    "pending_count": backtest.pending_count,
                    "false_positives": backtest.false_positive_count,
                },
                "learning": {
                    "sample_counts": self.sample_counts_by_label(),
                    "backtest": backtest.model_dump(mode="json"),
                    "skipped": skipped,
                },
                "main_force_patterns": self.main_force_pattern_summary(),
                "phase_matches": self.phase_match_summary(),
                "next_actions": self._next_actions(backtest, skipped, focus_symbols),
                "safety": {
                    "live_trading_enabled": settings.enable_live_trading,
                    "note": "当前报告只服务模拟交易、复盘和权重评估。",
                },
            },
        )
        report.id = self._persist_report(report)
        return report

    def latest_report(self) -> LearningReport | None:
        row = self.store.fetch_one(
            """
            SELECT id, automation_run_id, report_type, title, summary_json, created_at
            FROM learning_reports
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._report_model(row) if row else None

    def main_force_pattern_summary(self) -> dict[str, Any]:
        rows = self.store.fetch_all(
            """
            SELECT symbol, name, pattern_type, status, priority,
                   phase_timeline_json, theory_tags_json, training_focus_json,
                   caution_notes_json
            FROM main_force_phase_patterns
            ORDER BY priority DESC, id
            LIMIT 20
            """
        )
        patterns = []
        for row in rows:
            timeline = json.loads(row["phase_timeline_json"] or "[]")
            patterns.append(
                {
                    "symbol": row["symbol"],
                    "name": row.get("name"),
                    "pattern_type": row["pattern_type"],
                    "status": row["status"],
                    "priority": row["priority"],
                    "phase_count": len(timeline),
                    "current_phase": timeline[-1]["phase"] if timeline else row["status"],
                    "theory_tags": json.loads(row["theory_tags_json"] or "[]"),
                    "training_focus": json.loads(row["training_focus_json"] or "[]")[:4],
                    "caution_notes": json.loads(row["caution_notes_json"] or "[]")[:4],
                }
            )
        return {"pattern_count": len(patterns), "patterns": patterns}

    def phase_match_summary(self) -> dict[str, Any]:
        rows = self.store.fetch_all(
            """
            SELECT id, target_symbol, target_name, summary_json, created_at
            FROM main_force_phase_matches
            ORDER BY id DESC
            LIMIT 10
            """
        )
        matches = []
        for row in rows:
            summary = json.loads(row["summary_json"] or "{}")
            best = summary.get("best_match") or {}
            matches.append(
                {
                    "id": row["id"],
                    "target_symbol": row["target_symbol"],
                    "target_name": row.get("target_name"),
                    "target_latest_phase": summary.get("target_latest_phase"),
                    "best_core_symbol": best.get("core_symbol"),
                    "best_core_name": best.get("core_name"),
                    "score": best.get("score"),
                    "diagnosis": summary.get("diagnosis"),
                    "created_at": row.get("created_at"),
                }
            )
        guarded = [
            item
            for item in matches
            if item.get("best_core_symbol") == "SZ002081"
            and float(item.get("score") or 0) >= 70
        ]
        return {
            "match_count": len(matches),
            "guarded_count": len(guarded),
            "matches": matches,
        }

    def _samples_from_cases(self) -> list[dict[str, Any]]:
        rows = self.store.fetch_all("SELECT * FROM trade_cases")
        samples = []
        for row in rows:
            raw = json.loads(row["raw_json"] or "{}")
            label = "success" if row["case_type"] == "success" else "failure"
            symbol, name = self._extract_symbol_name(row.get("stock_text") or "")
            samples.append(
                {
                    "id": f"case:{row['id']}",
                    "source_type": "trade_case",
                    "source_id": row["id"],
                    "symbol": symbol,
                    "name": name,
                    "label": label,
                    "outcome_score": 1 if label == "success" else -1,
                    "features": {
                        "case_type": row["case_type"],
                        "operation": row.get("operation"),
                        "result": row.get("result"),
                    },
                    "lessons": self._compact_lessons(row.get("lesson"), row.get("result")),
                    "raw": raw,
                }
            )
        return samples

    def _samples_from_records(self) -> list[dict[str, Any]]:
        rows = self.store.fetch_all("SELECT * FROM trade_records")
        samples = []
        for row in rows:
            label = self._label_from_text(row.get("result"), row.get("remarks"))
            samples.append(
                {
                    "id": f"record:{row['id']}",
                    "source_type": "trade_record",
                    "source_id": str(row["id"]),
                    "symbol": row.get("stock_code"),
                    "name": row.get("stock_name"),
                    "label": label,
                    "outcome_score": 1 if label == "success" else (-1 if label == "failure" else 0),
                    "entry_price": row.get("reference_price"),
                    "risk_level": None,
                    "features": {
                        "operation_type": row.get("operation_type"),
                        "pct_change_text": row.get("pct_change_text"),
                        "turnover_text": row.get("turnover_text"),
                        "float_ratio_text": row.get("float_ratio_text"),
                    },
                    "lessons": self._compact_lessons(row.get("result"), row.get("remarks")),
                    "raw": json.loads(row["raw_json"] or "{}"),
                }
            )
        return samples

    def _samples_from_user_notes(self) -> list[dict[str, Any]]:
        rows = self.store.fetch_all("SELECT * FROM user_stock_notes")
        samples = []
        for row in rows:
            label = row["note_type"]
            samples.append(
                {
                    "id": f"user_note:{row['id']}",
                    "source_type": "user_stock_note",
                    "source_id": row["id"],
                    "symbol": row.get("symbol"),
                    "name": row.get("name"),
                    "label": label,
                    "outcome_score": 1 if label in POSITIVE_LABELS else 0,
                    "features": {
                        "note_type": row["note_type"],
                        "priority": row["priority"],
                        "tags": json.loads(row["tags_json"] or "[]"),
                    },
                    "lessons": self._compact_lessons(row.get("content")),
                    "raw": json.loads(row["raw_json"] or "{}"),
                }
            )
        return samples

    def _samples_from_stock_profiles(self) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM stock_profiles
            WHERE symbol IS NOT NULL
            ORDER BY score DESC
            """
        )
        samples = []
        seen = set()
        for row in rows:
            symbol = row["symbol"]
            if symbol in seen:
                continue
            seen.add(symbol)
            score = float(row.get("score") or 0)
            rating = row.get("rating")
            label = "watch"
            if rating == "优秀" and score >= 15:
                label = "success"
            elif row.get("risk_level") in {"大", "有"}:
                label = "risk_failure"
            elif row.get("risk_level") == "短期不追高" or rating == "出货完成训练样本":
                label = "distribution_completed"
            samples.append(
                {
                    "id": f"profile:{symbol}",
                    "source_type": "stock_profile",
                    "source_id": symbol,
                    "symbol": symbol,
                    "name": row.get("name"),
                    "label": label,
                    "outcome_score": 1 if label == "success" else (-0.5 if label == "risk_failure" else 0),
                    "entry_price": row.get("operation_cost_line"),
                    "exit_price": row.get("sell_target"),
                    "return_pct": row.get("profit_rate"),
                    "risk_level": row.get("risk_level"),
                    "rating": rating,
                    "features": {
                        "score": row.get("score"),
                        "pb": row.get("pb"),
                        "pe_ttm": row.get("pe_ttm"),
                        "limit_up_count": row.get("limit_up_count"),
                        "test_line_count": row.get("test_line_count"),
                        "dataset_name": row.get("dataset_name"),
                    },
                    "lessons": self._compact_lessons(row.get("rating"), row.get("risk_level")),
                    "raw": json.loads(row["raw_json"] or "{}"),
                }
            )
        return samples

    def _samples_from_main_force_patterns(self) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM main_force_phase_patterns
            ORDER BY priority DESC, id
            """
        )
        samples = []
        for row in rows:
            timeline = json.loads(row["phase_timeline_json"] or "[]")
            training_focus = json.loads(row["training_focus_json"] or "[]")
            caution_notes = json.loads(row["caution_notes_json"] or "[]")
            current_phase = timeline[-1]["phase"] if timeline else row["status"]
            label = (
                "distribution_completed"
                if row["status"] == "completed_distribution"
                else "phase_training"
            )
            samples.append(
                {
                    "id": f"main_force_pattern:{row['id']}",
                    "source_type": "main_force_phase_pattern",
                    "source_id": row["id"],
                    "symbol": row.get("symbol"),
                    "name": row.get("name"),
                    "label": label,
                    "outcome_score": -0.2 if label == "distribution_completed" else 0,
                    "risk_level": "短期不追高" if label == "distribution_completed" else None,
                    "rating": "主力阶段训练样本",
                    "features": {
                        "pattern_type": row["pattern_type"],
                        "status": row["status"],
                        "priority": row["priority"],
                        "phase_count": len(timeline),
                        "current_phase": current_phase,
                        "phases": [item.get("phase") for item in timeline],
                        "theory_tags": json.loads(row["theory_tags_json"] or "[]"),
                    },
                    "lessons": training_focus[:4] + caution_notes[:3],
                    "raw": json.loads(row["raw_json"] or "{}"),
                }
            )
        return samples

    def _sample_model(self, row: dict[str, Any]) -> LearningSample:
        return LearningSample(
            id=row["id"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            symbol=row.get("symbol"),
            name=row.get("name"),
            label=row["label"],
            outcome_score=float(row.get("outcome_score") or 0),
            entry_price=row.get("entry_price"),
            exit_price=row.get("exit_price"),
            return_pct=row.get("return_pct"),
            risk_level=row.get("risk_level"),
            rating=row.get("rating"),
            features=json.loads(row["features_json"] or "{}"),
            lessons=json.loads(row["lessons_json"] or "[]"),
        )

    def _persist_backtest(self, result: LearningBacktestResult) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO learning_backtests(
                    strategy_name, sample_count, win_rate, avg_return,
                    profit_loss_ratio, max_drawdown, blocked_success_count,
                    false_positive_count, pending_count, summary_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.strategy_name,
                    result.sample_count,
                    result.win_rate,
                    result.avg_return,
                    result.profit_loss_ratio,
                    result.max_drawdown,
                    result.blocked_success_count,
                    result.false_positive_count,
                    result.pending_count,
                    json.dumps(result.summary, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def _persist_report(self, report: LearningReport) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO learning_reports(
                    automation_run_id, report_type, title, summary_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    report.automation_run_id,
                    report.report_type,
                    report.title,
                    json.dumps(report.summary, ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def _report_model(self, row: dict[str, Any]) -> LearningReport:
        return LearningReport(
            id=row["id"],
            automation_run_id=row.get("automation_run_id"),
            report_type=row["report_type"],
            title=row["title"],
            summary=json.loads(row["summary_json"] or "{}"),
            created_at=row.get("created_at"),
        )

    def _predict_buy(self, row: dict[str, Any], features: dict[str, Any]) -> bool:
        if row["label"] in NO_BUY_TRAINING_LABELS:
            return False
        risk = row.get("risk_level")
        if risk == "短期不追高":
            return False
        if risk in {"大", "有"}:
            return False
        rating = row.get("rating")
        score = float(features.get("score") or 0)
        note_type = features.get("note_type")
        if note_type in {"method_success", "focus_priority"}:
            return True
        return rating in {"重点关注", "优秀"} or score >= 15

    def _sample_return(self, row: dict[str, Any]) -> float:
        if row.get("return_pct") is not None:
            return float(row["return_pct"])
        if row["label"] in POSITIVE_LABELS:
            return 0.08
        if row["label"] in NEGATIVE_LABELS:
            return -0.04
        return 0.0

    def _profit_loss_ratio(self, returns: list[float]) -> float:
        wins = [item for item in returns if item > 0]
        losses = [abs(item) for item in returns if item < 0]
        if not wins or not losses:
            return 0.0
        return mean(wins) / mean(losses)

    def _max_drawdown(self, returns: list[float]) -> float:
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        for item in returns:
            equity *= 1 + item
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
        return max_drawdown

    def _label_from_text(self, *values: str | None) -> str:
        text = " ".join(value or "" for value in values)
        if any(word in text for word in ("成功", "盈利", "赚", "胜")):
            return "success"
        if any(word in text for word in ("失败", "亏", "错", "风险")):
            return "failure"
        return "pending"

    def _compact_lessons(self, *values: str | None) -> list[str]:
        lessons = []
        for value in values:
            if value and value not in lessons:
                lessons.append(value)
        return lessons[:5]

    def _extract_symbol_name(self, text: str) -> tuple[str | None, str | None]:
        match = re.search(r"([036]\d{5}|SH\d{6}|SZ\d{6})", text)
        symbol = match.group(1) if match else None
        return symbol, text.strip() or None

    def _next_actions(
        self,
        backtest: LearningBacktestResult,
        skipped: list[dict[str, Any]],
        focus_symbols: list[dict[str, Any]],
    ) -> list[str]:
        actions = [
            "继续把自动化运行结果写入学习样本，优先标注失败原因和未买原因。",
            "对乐凯胶片、三维通信保留用户确认标签；对金螳螂按吸筹-试盘-拉升-出货完成样本训练，短期不追高。",
        ]
        if skipped:
            actions.append("补齐跳过股票的本地价格或行情源兜底，减少训练候选无法生成模拟计划的情况。")
        if backtest.false_positive_count:
            actions.append("复核误判为买入的失败样本，优先收紧风险标记和高位红线。")
        if focus_symbols:
            actions.append("下一轮模拟优先观察强候选的量价、成本线和是否突破硬红线。")
        return actions
