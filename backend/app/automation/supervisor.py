import json
from typing import Any

from app.candidates.auto_discovery import AutoDiscoveryScanner
from app.candidates.local_scanner import LocalCandidateScanner
from app.config import settings
from app.data.snapshot_builder import MarketDataError, MarketSnapshotBuilder
from app.decision import DecisionAnalyzer
from app.simulation.planner import SimulationPlanner
from app.storage.sqlite_store import SQLiteStore


class AutomationSupervisor:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def capabilities(self) -> dict[str, Any]:
        return {
            "mode": "simulation_first",
            "live_trading_enabled": settings.enable_live_trading,
            "supported_steps": [
                "auto_discovery_limit_up_scan",
                "candidate_scan",
                "decision_analysis",
                "candidate_pool_batch_phase_guardrail",
                "phase_similarity_guardrail",
                "simulation_plan",
                "learning_report",
                "intraday_monitoring",
                "realtime_refresh_simulation_only",
                "realtime_monitoring_sync_review_only",
                "realtime_cycle_scheduler_safe",
                "single_symbol_review",
                "offhour_potential_search",
                "event_logging",
            ],
            "reserved_adapters": [
                "browser_screen_control",
                "codex_skill_control",
                "broker_client_control_disabled",
            ],
            "realtime_capabilities": {
                "refresh": "simulation-only cached market events",
                "monitoring_sync": "review-only monitoring alerts from persisted realtime events",
                "cycle": "scheduler-safe refresh -> monitoring sync -> replay evidence loop",
                "recommended_cadence": ["10:00", "13:00", "16:00"],
                "pause_control": "pause the external automation that calls realtime-cycle; do not switch to broker or screen control",
                "forbidden": ["broker_order", "credential_access", "screen_click_trading", "live_auto_trading"],
            },
            "guardrails": [
                "实盘交易默认禁用",
                "自动化进程只生成模拟计划和事件日志",
                "屏幕控制和券商客户端控制必须先通过人工确认和风控审计",
            ],
        }

    def run_once(self, limit: int = 30) -> dict[str, Any]:
        run_id = self._start_run("simulation_once")
        self._event(run_id, "automation_started", None, {"limit": limit})

        discovery = AutoDiscoveryScanner().scan(limit=max(20, limit * 4), persist=True)
        self._event(
            run_id,
            "auto_discovery_completed",
            None,
            {
                "status": discovery.get("status"),
                "discovered_count": discovery.get("discovered_count", 0),
                "limit_up_count": discovery.get("limit_up_count", 0),
                "error": discovery.get("error"),
            },
        )

        scan = LocalCandidateScanner().scan(limit=limit, persist=True)
        self._event(
            run_id,
            "candidate_scan_completed",
            None,
            {
                "scan_id": scan.get("scan_id"),
                "strong_count": scan["strong_count"],
                "watch_count": scan["watch_count"],
                "rejected_count": scan["rejected_count"],
            },
        )

        phase_matches = self._run_phase_guardrails(scan)
        if phase_matches:
            self._event(
                run_id,
                "phase_guardrails_completed",
                None,
                {"matches": phase_matches},
            )

        candidates = scan["buckets"]["strong"] + scan["buckets"]["watch"]
        processed = []
        for candidate in candidates[:10]:
            symbol = candidate["symbol"]
            try:
                snapshot = MarketSnapshotBuilder().build(symbol, candidate.get("name"))
                analysis = DecisionAnalyzer().analyze(snapshot)
                plan = SimulationPlanner().create_plan(snapshot)
            except (ValueError, MarketDataError) as exc:
                payload = {"reason": str(exc), "candidate": candidate}
                self._event(run_id, "plan_skipped", symbol, payload)
                processed.append({"symbol": symbol, "status": "skipped", "reason": str(exc)})
                continue

            payload = {
                "candidate": candidate,
                "snapshot": snapshot.model_dump(mode="json"),
                "decision": analysis.decision.model_dump(mode="json"),
                "plan": plan.model_dump(mode="json"),
                "risk_notes": analysis.risk_notes,
            }
            self._event(run_id, "simulation_plan_created", symbol, payload)
            item = {
                "symbol": symbol,
                "status": "planned",
                "action": plan.action,
                "allowed": plan.allowed,
                "quantity": plan.quantity,
                "tier": analysis.decision.tier.value,
            }
            phase_guardrail = self._phase_guardrail_for(symbol, phase_matches)
            if phase_guardrail:
                item["action"] = "observe"
                item["allowed"] = False
                item["quantity"] = 0
                item["phase_guardrail"] = phase_guardrail
            processed.append(item)

        self._event(
            run_id,
            "screen_control_reserved",
            None,
            {
                "status": "disabled",
                "reason": "屏幕/券商客户端控制已纳入架构预留，但当前版本保持模拟优先。",
            },
        )

        guarded_count = len([item for item in processed if item.get("phase_guardrail")])
        summary = {
            "auto_discovery": {
                "status": discovery.get("status"),
                "discovered_count": discovery.get("discovered_count", 0),
                "limit_up_count": discovery.get("limit_up_count", 0),
                "near_limit_up_count": discovery.get("near_limit_up_count", 0),
                "strong_mover_count": discovery.get("strong_mover_count", 0),
                "scored_count": discovery.get("scored_count", 0),
                "error": discovery.get("error"),
            },
            "scan_id": scan.get("scan_id"),
            "lifecycle": scan.get("lifecycle"),
            "scoring": scan.get("scoring"),
            "processed_count": len(processed),
            "planned_count": len([item for item in processed if item["status"] == "planned"]),
            "skipped_count": len([item for item in processed if item["status"] == "skipped"]),
            "phase_matches": phase_matches,
            "phase_match_count": len(
                [item for item in phase_matches if item.get("status", "completed") == "completed"]
            ),
            "phase_guarded_count": guarded_count,
            "items": processed,
        }
        self._finish_run(run_id, summary)
        try:
            from app.learning.service import LearningService

            report = LearningService().generate_review_report(run_id)
            summary["learning_report_id"] = report.id
            self._event(
                run_id,
                "learning_report_created",
                None,
                {"report_id": report.id, "title": report.title},
            )
            self._finish_run(run_id, summary)
        except Exception as exc:
            self._event(run_id, "learning_report_failed", None, {"reason": str(exc)})
        return {"run_id": run_id, "status": "completed", "summary": summary}

    def _run_phase_guardrails(self, scan: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            from app.learning.phase_matcher import PhaseSimilarityService

            service = PhaseSimilarityService()
            targets = []
            seen = set()
            for bucket in ("strong", "watch"):
                for item in scan["buckets"].get(bucket, []):
                    symbol = item.get("symbol")
                    if not symbol or symbol in seen:
                        continue
                    seen.add(symbol)
                    if symbol in {"SZ002081", "SZ002115"}:
                        continue
                    targets.append(item)
            targets.sort(
                key=lambda item: (
                    0 if item.get("tier") == "strong" else 1,
                    -float(item.get("score") or 0),
                )
            )
            results = []
            for item in targets[:5]:
                try:
                    match = service.create_match(
                        symbol=item["symbol"],
                        name=item.get("name"),
                        lookback_years=3,
                    )
                except Exception as exc:
                    results.append(
                        {
                            "target_symbol": item.get("symbol"),
                            "target_name": item.get("name"),
                            "status": "failed",
                            "reason": str(exc),
                        }
                    )
                    continue
                best = match.get("summary", {}).get("best_match") or {}
                results.append(
                    {
                        "target_symbol": match.get("target_symbol"),
                        "target_name": match.get("target_name"),
                        "status": "completed",
                        "match_id": match.get("id"),
                        "best_core_symbol": best.get("core_symbol"),
                        "score": best.get("score"),
                        "target_latest_phase": match.get("summary", {}).get("target_latest_phase"),
                        "diagnosis": match.get("summary", {}).get("diagnosis"),
                    }
                )
            return results
        except Exception as exc:
            return [{"status": "failed", "reason": str(exc)}]

    def _phase_guardrail_for(
        self,
        symbol: str,
        phase_matches: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        match = next(
            (
                item
                for item in phase_matches
                if item.get("target_symbol") == symbol
                and item.get("status", "completed") == "completed"
                and item.get("best_core_symbol") == "SZ002081"
                and float(item.get("score") or 0) >= 70
                and item.get("target_latest_phase") in {"distribution", "post_distribution_watch"}
            ),
            None,
        )
        if not match:
            return None
        return {
            "match_id": match.get("match_id"),
            "best_core_symbol": match.get("best_core_symbol"),
            "score": match.get("score"),
            "diagnosis": match.get("diagnosis"),
        }

    def run_cycle(
        self,
        limit: int = 5,
        monitor_limit: int = 5,
        review_symbol: str = "SZ002081",
    ) -> dict[str, Any]:
        """Run the safe observe-plan-monitor-review loop once."""
        cycle: dict[str, Any] = {
            "status": "completed",
            "live_trading_enabled": settings.enable_live_trading,
        }
        cycle["automation"] = self.run_once(limit=limit)

        try:
            from app.learning.service import LearningService

            report = LearningService().latest_report()
            cycle["learning_report"] = report.model_dump(mode="json") if report else None
        except Exception as exc:
            cycle["status"] = "partial"
            cycle["learning_error"] = str(exc)

        try:
            from app.monitoring.service import MonitoringService

            monitoring_service = MonitoringService()
            monitoring = monitoring_service.run_once(limit=monitor_limit)
            cycle["monitoring"] = monitoring
            if review_symbol:
                cycle["monitoring_review"] = monitoring_service.create_symbol_review(
                    symbol=review_symbol,
                    session_id=monitoring.get("session_id"),
                )
        except Exception as exc:
            cycle["status"] = "partial"
            cycle["monitoring_error"] = str(exc)

        return cycle

    def latest_run(self) -> dict[str, Any] | None:
        run = self.store.fetch_one(
            """
            SELECT id, mode, status, summary_json, created_at, completed_at
            FROM automation_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not run:
            return None
        return self._hydrate_run(run)

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        run = self.store.fetch_one(
            """
            SELECT id, mode, status, summary_json, created_at, completed_at
            FROM automation_runs
            WHERE id = ?
            """,
            (run_id,),
        )
        if not run:
            return None
        return self._hydrate_run(run)

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT id, mode, status, summary_json, created_at, completed_at
            FROM automation_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        result = []
        for row in rows:
            row["summary"] = json.loads(row.pop("summary_json") or "{}")
            result.append(row)
        return result

    def _hydrate_run(self, run: dict[str, Any]) -> dict[str, Any]:
        events = self.store.fetch_all(
            """
            SELECT event_type, symbol, payload_json, created_at
            FROM automation_events
            WHERE run_id = ?
            ORDER BY id
            """,
            (run["id"],),
        )
        run["summary"] = json.loads(run.pop("summary_json") or "{}")
        run["events"] = [
            {
                **event,
                "payload": json.loads(event.pop("payload_json") or "{}"),
            }
            for event in events
        ]
        return run

    def start_external_run(self, mode: str) -> dict[str, Any]:
        run_id = self._start_run(mode)
        self._event(run_id, "external_run_started", None, {"mode": mode})
        return {"run_id": run_id, "status": "running", "mode": mode}

    def record_external_event(
        self,
        run_id: int,
        event_type: str,
        symbol: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._run_exists(run_id):
            raise ValueError(f"自动化运行不存在: {run_id}")
        self._event(run_id, event_type, symbol, payload)
        return {"run_id": run_id, "event_type": event_type, "status": "recorded"}

    def finish_external_run(
        self,
        run_id: int,
        status: str,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._run_exists(run_id):
            raise ValueError(f"自动化运行不存在: {run_id}")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE automation_runs
                SET status = ?, summary_json = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, json.dumps(summary, ensure_ascii=False), run_id),
            )
        return {"run_id": run_id, "status": status, "summary": summary}

    def _start_run(self, mode: str) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO automation_runs(mode, status)
                VALUES (?, ?)
                """,
                (mode, "running"),
            )
            return int(cursor.lastrowid)

    def _run_exists(self, run_id: int) -> bool:
        return bool(
            self.store.fetch_one(
                "SELECT id FROM automation_runs WHERE id = ?",
                (run_id,),
            )
        )

    def _finish_run(self, run_id: int, summary: dict[str, Any]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE automation_runs
                SET status = ?, summary_json = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                ("completed", json.dumps(summary, ensure_ascii=False), run_id),
            )

    def _event(self, run_id: int, event_type: str, symbol: str | None, payload: dict[str, Any]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO automation_events(run_id, event_type, symbol, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, event_type, symbol, json.dumps(payload, ensure_ascii=False, default=str)),
            )
