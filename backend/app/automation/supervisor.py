from datetime import datetime
from pathlib import Path
from typing import Any
from collections import Counter
import json
import time
import uuid

from app.candidates.auto_discovery import AutoDiscoveryScanner
from app.candidates.local_scanner import LocalCandidateScanner
from app.config import settings
from app.data.snapshot_builder import MarketDataError, MarketSnapshotBuilder
from app.decision import DecisionAnalyzer
from app.sim_cockpit.service import SimCockpitService
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
                "tonghuashun_simulation_cockpit_gateway",
                "simulation_cockpit_run",
                "dataset2_training_status",
                "dataset2_training_run_in_memory",
                "sim_cockpit_supervised_cycle",
                "offhour_research_loop",
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
            "simulation_cockpit": {
                "status": "enabled_after_verified_mncg_window",
                "scope": "tonghuashun_simulated_account_only",
                "allowed_actions": ["simulated_buy", "simulated_sell", "simulated_cancel", "simulated_submit_audit"],
                "default_execution_mode": "dry_run_screen",
                "screen_click_execution_mode": "screen_click_simulation_requires_explicit_confirmation",
                "requires": [
                    "tonghuashun_process_marker",
                    "window_or_page_text",
                    "mncg_or_simulation_marker",
                    "desktop_adapter_verification_for_screen_click",
                    "coordinate_anchors_for_screen_click",
                    "SIMULATION_SCREEN_CLICK_confirmation_for_screen_click",
                    "simulation_allowed_true",
                    "risk_gates_passed",
                ],
                "hard_blocks": [
                    "real_trading_window",
                    "broker_login",
                    "credential_entry",
                    "fund_account",
                    "bank_transfer",
                    "live_order_submit",
                ],
                "real_broker_api_enabled": False,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "dataset2_training": {
                "status": "controlled_dry_run_only",
                "sources": [
                    "dataset2_staging_records",
                    "sim_cockpit_actions",
                    "sim_cockpit_readbacks",
                ],
                "training_mode": "in_memory_majority_label_baseline",
                "model_artifact_write_enabled": False,
                "requires_health_live_trading_disabled": True,
                "cli_modes": [
                    "dataset2-training-status",
                    "dataset2-training-run",
                    "sim-cockpit-supervised-cycle",
                ],
                "live_trading_enabled": settings.enable_live_trading,
            },
            "offhour_research_loop": {
                "status": "enabled_for_non_trading_hours",
                "mode": "balanced_potential_search_and_dataset2_replay",
                "allowed_outputs": [
                    "potential_search_audit",
                    "dataset2_strategy_replay",
                    "historical_backtest_review",
                    "sandbox_outcome_review",
                    "candidate_model_artifact",
                ],
                "artifact_policy": "candidate_only_not_auto_loaded",
                "cli_modes": ["offhour-research-status", "offhour-research-loop"],
                "requires_health_live_trading_disabled": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "guardrails": [
                "实盘交易默认禁用",
                "自动化进程只生成模拟计划和事件日志",
                "屏幕控制和券商客户端控制必须先通过人工确认和风控审计",
            ],
        }

    def run_preflight(self) -> dict[str, Any]:
        preflight_id = str(uuid.uuid4())
        checks: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []

        self._append_preflight_check(
            checks,
            blockers,
            "preflight.health.live_trading_disabled",
            "health_live_trading_check",
            "fail" if settings.enable_live_trading else "pass",
            "critical",
            {
                "live_trading_enabled": settings.enable_live_trading,
                "expected": False,
                "source": "settings.enable_live_trading / /health",
            },
            "Set enable_live_trading=false before run preflight.",
        )

        capabilities = self.capabilities()
        capabilities_supported = "simulation_plan" in capabilities.get("supported_steps", [])
        self._append_preflight_check(
            checks,
            blockers,
            "preflight.automation.capabilities",
            "automation_capabilities",
            "pass"
            if (capabilities_supported and not capabilities.get("live_trading_enabled", True))
            else "fail",
            "critical",
            {
                "mode": capabilities.get("mode"),
                "live_trading_enabled": capabilities.get("live_trading_enabled"),
                "simulation_step_supported": capabilities_supported,
                "realtime_capabilities": capabilities.get("realtime_capabilities"),
            },
            (
                "Check /api/automation/capabilities returns simulation-first mode and live trading disabled."
            ),
        )

        self._append_preflight_check(
            checks,
            blockers,
            "preflight.data_source.market_snapshot",
            "market_data_readiness",
            self._check_data_readiness(),
            "warning",
            self._market_data_readiness_details,
            "Verify AKShare reachability and fallback source quality. Run again after network/API recovery.",
        )
        self._append_preflight_check(
            checks,
            blockers,
            "preflight.database.path_consistency",
            "sqlite_path_consistency",
            self._check_database_path(),
            "warning",
            self._database_check_details,
            "Align database_path to repository root trading_local.sqlite3 and ensure writable.",
        )
        self._append_preflight_check(
            checks,
            blockers,
            "preflight.automation.run_log",
            "automation_log_readability",
            self._check_automation_log_readability(),
            "warning",
            self._automation_log_readability_details,
            "Restore automation_runs / automation_events table schema and ensure recent rows are JSON-valid.",
        )

        status = "fail" if any(item.get("status") == "fail" for item in checks) else "pass"
        return {
            "preflight_required": True,
            "preflight_id": preflight_id,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "status": status,
            "checks": checks,
            "blockers": blockers,
        }

    def _append_preflight_check(
        self,
        checks: list[dict[str, Any]],
        blockers: list[dict[str, Any]],
        check_id: str,
        name: str,
        status: str,
        severity: str,
        details: dict[str, Any],
        recommendation: str,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "name": name,
                "status": status,
                "severity": severity,
                "details": details,
            }
        )
        if status == "fail":
            blockers.append(
                {
                    "check_id": check_id,
                    "severity": severity,
                    "reason": details.get("reason") or f"{name} check failed",
                    "recommendation": recommendation,
                }
            )

    def _check_data_readiness(self) -> str:
        self._market_data_readiness_details = {}
        builder = MarketSnapshotBuilder()
        symbols = ["000001", "000002", "399001"]
        snapshots: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for symbol in symbols:
            try:
                snapshot = builder.build(symbol)
                source = str(snapshot.metadata.get("source", "unknown"))
                snapshots.append(
                    {
                        "symbol": symbol,
                        "source": source,
                        "fallback": "fallback" in source.lower(),
                        "quality": snapshot.metadata.get("data_quality"),
                    }
                )
            except MarketDataError as exc:
                errors.append({"symbol": symbol, "error": str(exc)})
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})

        details = {
            "symbols": symbols,
            "snapshots": snapshots,
            "errors": errors,
            "cache_readable": True,
            "cache_sample_rows": 0,
        }

        if not snapshots:
            details["reason"] = "No symbol snapshot could be built."
            self._market_data_readiness_details = details
            return "fail"

        used_all_fallback = all(item["fallback"] for item in snapshots)
        try:
            cache_row = self.store.fetch_one(
                "SELECT COUNT(*) as cnt FROM daily_bar_cache WHERE symbol IN (?, ?, ?)",
                ("000001", "000002", "399001"),
            )
            details["cache_sample_rows"] = int(cache_row["cnt"]) if cache_row else 0
        except Exception as exc:
            details["cache_readable"] = False
            details["status_hint"] = "cache_read_error"
            details["reason"] = f"Failed to read daily_bar_cache: {exc}"
            self._market_data_readiness_details = details
            return "fail"

        if used_all_fallback:
            details["status_hint"] = "fallback_used"
            self._market_data_readiness_details = details
            return "warn"

        details["status_hint"] = "primary_ok"
        self._market_data_readiness_details = details
        return "pass"

    def _check_database_path(self) -> str:
        self._database_check_details = {}
        details = {
            "configured_database_path": str(Path(settings.database_path).resolve()),
            "expected_database_path": str(Path(__file__).resolve().parents[3] / "trading_local.sqlite3"),
        }
        self._database_check_details = details

        try:
            with self.store.connect() as conn:
                conn.execute("SELECT 1")
        except Exception as exc:
            details["reason"] = f"Failed to open sqlite database: {exc}"
            return "fail"

        if details["configured_database_path"] != details["expected_database_path"]:
            details["note"] = "database_path does not point to repository-root default db"
            return "warn"

        return "pass"

    def _check_automation_log_readability(self) -> str:
        self._automation_log_readability_details = {}
        details = {
            "automation_runs_table": "automation_runs",
            "automation_events_table": "automation_events",
        }
        self._automation_log_readability_details = details

        try:
            latest_run = self.store.fetch_one(
                """
                SELECT id, mode, summary_json, created_at, completed_at
                FROM automation_runs
                ORDER BY id DESC
                LIMIT 1
                """
            )
        except Exception as exc:
            details["reason"] = f"Failed to query automation_runs: {exc}"
            return "fail"

        if latest_run is None:
            details["reason"] = "No automation_runs found yet."
            details["status_hint"] = "no_history"
            return "warn"

        try:
            summary = json.loads(latest_run.get("summary_json") or "{}")
            details["latest_run"] = {
                "run_id": latest_run.get("id"),
                "mode": latest_run.get("mode"),
                "has_summary": isinstance(summary, dict),
                "created_at": latest_run.get("created_at"),
            }
        except Exception as exc:
            details["reason"] = f"Failed to parse latest run summary_json: {exc}"
            return "fail"

        run_id = latest_run.get("id")
        if run_id is None:
            details["reason"] = "latest run record is missing id."
            return "fail"

        try:
            latest_events = self.store.fetch_all(
                """
                SELECT id, event_type, payload_json
                FROM automation_events
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT 3
                """,
                (run_id,),
            )
            parsed_count = 0
            for event in latest_events:
                json.loads(event.get("payload_json") or "{}")
                parsed_count += 1
            details["latest_events_parsed"] = parsed_count
            details["latest_events_total_checked"] = len(latest_events)
        except Exception as exc:
            details["reason"] = f"Failed to parse latest automation_events: {exc}"
            return "fail"

        return "pass"

    def run_once(self, limit: int = 30) -> dict[str, Any]:
        run_id = self._start_run("simulation_once")
        started_at = time.perf_counter()
        self._event(run_id, "automation_started", None, {"limit": limit})

        run_steps: list[dict[str, Any]] = []
        failed_steps: list[dict[str, Any]] = []
        next_action = "建议检查日志后重试对应步骤。"
        overall_status = "completed"

        def _step_entry(
            step_id: str,
            name: str,
            step_status: str,
            start: float,
            details: dict[str, Any] | None = None,
            reason: str | None = None,
        ) -> dict[str, Any]:
            entry: dict[str, Any] = {
                "step_id": step_id,
                "name": name,
                "status": step_status,
                "duration_ms": int((time.perf_counter() - start) * 1000),
            }
            if details is not None:
                entry["details"] = details
            if reason is not None:
                entry["reason"] = reason
            return entry

        def _append_failure(
            step_id: str,
            name: str,
            reason: str,
            payload: dict[str, Any] | None = None,
        ) -> None:
            failed_steps.append(
                {
                    "step_id": step_id,
                    "name": name,
                    "status": "failed",
                    "reason": reason,
                    **({"details": payload} if payload else {}),
                }
            )

        discovery: dict[str, Any] = {
            "status": "failed",
            "discovered_count": 0,
            "limit_up_count": 0,
            "near_limit_up_count": 0,
            "strong_mover_count": 0,
            "scored_count": 0,
        }
        scan: dict[str, Any] = {
            "scan_id": None,
            "buckets": {"strong": [], "watch": [], "rejected": []},
            "lifecycle": None,
            "scoring": None,
            "strong_count": 0,
            "watch_count": 0,
            "rejected_count": 0,
        }
        phase_matches: list[dict[str, Any]] = []
        processed: list[dict[str, Any]] = []

        step_start = time.perf_counter()
        try:
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
            run_steps.append(
                _step_entry(
                    "auto_discovery",
                    "auto_discovery",
                    "completed",
                    step_start,
                    {
                        "status": discovery.get("status"),
                        "discovered_count": discovery.get("discovered_count", 0),
                        "limit_up_count": discovery.get("limit_up_count", 0),
                        "error": discovery.get("error"),
                    },
                )
            )
        except Exception as exc:
            reason = str(exc)
            run_steps.append(
                _step_entry(
                    "auto_discovery",
                    "auto_discovery",
                    "failed",
                    step_start,
                    {"limit": limit},
                    reason,
                )
            )
            _append_failure("auto_discovery", "auto_discovery", reason, {"limit": limit})
            self._event(
                run_id,
                "automation_step_failed",
                None,
                {"step_id": "auto_discovery", "reason": reason, "payload": {"limit": limit}},
            )
            overall_status = "failed"
            next_action = "请检查 auto_discovery 数据源与数据库可写性后重试。"

            summary = {
                "auto_discovery": discovery,
                "scan_id": None,
                "lifecycle": None,
                "scoring": None,
                "processed_count": 0,
                "planned_count": 0,
                "skipped_count": 0,
                "phase_matches": phase_matches,
                "phase_match_count": 0,
                "phase_guarded_count": 0,
                "items": processed,
                "run_steps": run_steps,
                "failed_steps": failed_steps,
                "next_action": next_action,
                "status": overall_status,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            }
            self._finish_run(run_id, summary, status=overall_status)
            return {"run_id": run_id, "status": overall_status, "summary": summary}

        step_start = time.perf_counter()
        try:
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
            run_steps.append(
                _step_entry(
                    "candidate_scan",
                    "candidate_scan",
                    "completed",
                    step_start,
                    {
                        "scan_id": scan.get("scan_id"),
                        "strong_count": scan["strong_count"],
                        "watch_count": scan["watch_count"],
                        "rejected_count": scan["rejected_count"],
                    },
                )
            )
        except Exception as exc:
            reason = str(exc)
            run_steps.append(
                _step_entry(
                    "candidate_scan",
                    "candidate_scan",
                    "failed",
                    step_start,
                    {"requested_limit": limit},
                    reason,
                )
            )
            _append_failure("candidate_scan", "candidate_scan", reason, {"requested_limit": limit})
            self._event(
                run_id,
                "automation_step_failed",
                None,
                {"step_id": "candidate_scan", "reason": reason, "payload": {"limit": limit}},
            )
            overall_status = "failed"
            next_action = "请检查候选扫描数据源与扫描参数后重试。"

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
                "scan_id": None,
                "lifecycle": None,
                "scoring": None,
                "processed_count": 0,
                "planned_count": 0,
                "skipped_count": 0,
                "phase_matches": phase_matches,
                "phase_match_count": 0,
                "phase_guarded_count": 0,
                "items": processed,
                "run_steps": run_steps,
                "failed_steps": failed_steps,
                "next_action": next_action,
                "status": overall_status,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            }
            self._finish_run(run_id, summary, status=overall_status)
            return {"run_id": run_id, "status": overall_status, "summary": summary}

        step_start = time.perf_counter()
        try:
            phase_matches = self._run_phase_guardrails(scan)
            if phase_matches:
                self._event(
                    run_id,
                    "phase_guardrails_completed",
                    None,
                    {"matches": phase_matches},
                )
            run_steps.append(
                _step_entry(
                    "phase_guardrails",
                    "phase_guardrails",
                    "completed",
                    step_start,
                    {"matches": phase_matches},
                )
            )
        except Exception as exc:
            reason = str(exc)
            run_steps.append(
                _step_entry(
                    "phase_guardrails",
                    "phase_guardrails",
                    "failed",
                    step_start,
                    {"scan_id": scan.get("scan_id")},
                    reason,
                )
            )
            _append_failure(
                "phase_guardrails",
                "phase_guardrails",
                reason,
                {"scan_id": scan.get("scan_id")},
            )
            self._event(
                run_id,
                "automation_step_failed",
                None,
                {
                    "step_id": "phase_guardrails",
                    "reason": reason,
                    "payload": {"scan_id": scan.get("scan_id")},
                },
            )
            if overall_status == "completed":
                overall_status = "partial"
            next_action = "阶段风控服务异常，核心扫描已完成，建议检查服务后重试。"

        step_start = time.perf_counter()
        try:
            candidates = scan["buckets"].get("strong", []) + scan["buckets"].get("watch", [])
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
                    "risk_blocked": [
                        blocked.model_dump(mode="json") for blocked in plan.risk_blocked
                    ],
                    "risk_notes": analysis.risk_notes,
                }
                self._event(run_id, "simulation_plan_created", symbol, payload)
                plan_risk_blocked = [
                    blocked.model_dump(mode="json") for blocked in plan.risk_blocked
                ]
                item = {
                    "symbol": symbol,
                    "status": "blocked" if not plan.allowed else "planned",
                    "action": plan.action,
                    "allowed": plan.allowed,
                    "quantity": plan.quantity,
                    "tier": analysis.decision.tier.value,
                    "risk_blocked": plan_risk_blocked,
                    "risk_blocked_count": len(plan_risk_blocked),
                    "blocked_reason": plan.blocked_reason,
                    "evidence": plan.risk_notes,
                }
                phase_guardrail = self._phase_guardrail_for(symbol, phase_matches)
                if phase_guardrail:
                    item["action"] = "observe"
                    item["allowed"] = False
                    item["quantity"] = 0
                    item["phase_guardrail"] = phase_guardrail
                    if item["status"] != "blocked":
                        item["status"] = "blocked"
                        item["reason"] = "phase_guardrail_hit"
                    if not item.get("risk_blocked"):
                        item["risk_blocked"] = [
                            {
                                "rule_id": "phase_guardrail",
                                "rule_name": "Phase similarity guardrail",
                                "layer": "execution",
                                "trigger_level": "hard",
                                "reason": "Phase similarity guardrail triggered",
                                "threshold": {
                                    "best_core_symbol": phase_guardrail.get("best_core_symbol")
                                },
                                "evidence": phase_guardrail,
                                "evidence_snippet": phase_guardrail.get("diagnosis"),
                                "source": "automation_supervisor",
                            }
                        ]
                        item["risk_blocked_count"] = len(item["risk_blocked"])
                        item["blocked_reason"] = item["risk_blocked"][0].get("rule_id")
                if not plan.allowed:
                    self._event(
                        run_id,
                        "automation_risk_blocked",
                        symbol,
                        {
                            "step_id": "plan_generation",
                            "risk_blocked": item.get("risk_blocked", []),
                            "blocked_reason": item.get("blocked_reason"),
                            "tier": item.get("tier"),
                        },
                    )
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
            run_steps.append(
                _step_entry(
                    "plan_generation",
                    "plan_generation",
                    "completed",
                    step_start,
                    {
                        "candidate_count": len(candidates),
                        "processed_count": len(processed),
                        "planned_count": len([item for item in processed if item["status"] == "planned"]),
                        "blocked_count": len([item for item in processed if item["status"] == "blocked"]),
                        "skipped_count": len([item for item in processed if item["status"] == "skipped"]),
                    },
                )
            )
        except Exception as exc:
            reason = str(exc)
            run_steps.append(
                _step_entry(
                    "plan_generation",
                    "plan_generation",
                    "failed",
                    step_start,
                    {"scan_id": scan.get("scan_id")},
                    reason,
                )
            )
            _append_failure("plan_generation", "plan_generation", reason, {"scan_id": scan.get("scan_id")})
            self._event(
                run_id,
                "automation_step_failed",
                None,
                {
                    "step_id": "plan_generation",
                    "reason": reason,
                    "payload": {"scan_id": scan.get("scan_id")},
                },
            )
            overall_status = "failed"
            next_action = "请检查候选数据结构与扫描字段后重试。"

        guarded_count = len([item for item in processed if item.get("phase_guardrail")])
        summary: dict[str, Any] = {
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
            "risk_blocked_summary": self._risk_blocked_summary(processed),
            "run_steps": run_steps,
            "failed_steps": failed_steps,
            "next_action": next_action,
            "status": overall_status,
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        }

        step_start = time.perf_counter()
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
            run_steps.append(
                _step_entry(
                    "learning_report",
                    "learning_report",
                    "completed",
                    step_start,
                    {"report_id": report.id, "title": report.title},
                )
            )
        except Exception as exc:
            reason = str(exc)
            if overall_status == "completed":
                overall_status = "partial"
            next_action = "学习报告生成失败，已保留扫描与计划结果，可再次执行完成。"
            _append_failure("learning_report", "learning_report", reason, {"scan_id": scan.get("scan_id")})
            run_steps.append(
                _step_entry(
                    "learning_report",
                    "learning_report",
                    "failed",
                    step_start,
                    {"scan_id": scan.get("scan_id")},
                    reason,
                )
            )
            self._event(run_id, "learning_report_failed", None, {"reason": reason})
            self._event(
                run_id,
                "automation_step_failed",
                None,
                {"step_id": "learning_report", "reason": reason, "payload": {"scan_id": scan.get("scan_id")}},
            )

        summary["status"] = overall_status
        summary["run_steps"] = run_steps
        summary["failed_steps"] = failed_steps
        summary["next_action"] = next_action
        summary["duration_ms"] = int((time.perf_counter() - started_at) * 1000)
        self._finish_run(run_id, summary, status=overall_status)
        return {"run_id": run_id, "status": overall_status, "summary": summary}

    def _risk_blocked_summary(self, processed: list[dict[str, Any]]) -> dict[str, Any]:
        rules = Counter()
        layers = Counter()
        reasons = Counter()
        samples = []
        for item in processed:
            for blocked in item.get("risk_blocked", []) or []:
                if isinstance(blocked, dict):
                    rule_id = blocked.get("rule_id") or "unknown"
                    rule_name = blocked.get("rule_name") or rule_id
                    layer = blocked.get("layer") or "unknown"
                    reason = blocked.get("reason") or ""
                    rules[rule_id] += 1
                    layers[layer] += 1
                    reasons[reason] += 1
                    if len(samples) < 5:
                        samples.append({"symbol": item.get("symbol"), "rule_id": rule_id, "rule_name": rule_name})
                elif hasattr(blocked, "model_dump"):
                    payload = blocked.model_dump(mode="json")
                    rule_id = payload.get("rule_id") or "unknown"
                    rule_name = payload.get("rule_name") or rule_id
                    layer = payload.get("layer") or "unknown"
                    reason = payload.get("reason") or ""
                    rules[rule_id] += 1
                    layers[layer] += 1
                    reasons[reason] += 1
                    if len(samples) < 5:
                        samples.append({"symbol": item.get("symbol"), "rule_id": rule_id, "rule_name": rule_name})

        return {
            "total": sum(rules.values()),
            "top_rules": rules.most_common(10),
            "by_layer": dict(layers),
            "top_reasons": reasons.most_common(10),
            "samples": samples,
        }

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
        cycle_started_at = time.perf_counter()
        cycle: dict[str, Any] = {
            "status": "completed",
            "live_trading_enabled": settings.enable_live_trading,
            "quality_gates": [],
            "quality_events_count": 0,
            "suppressed_by_quality_symbols": [],
            "quality_next_action": "continue_with_alerts",
        }
        cycle["run_steps"] = []
        cycle["failed_steps"] = []
        cycle["next_action"] = "继续后续监控与复盘。"

        run_steps = cycle["run_steps"]
        failed_steps = cycle["failed_steps"]

        step_start = time.perf_counter()
        automation = self.run_once(limit=limit)
        cycle["automation"] = automation
        automation_status = automation.get("status", "failed")
        run_steps.append(
            {
                "step_id": "automation_once",
                "name": "run_once",
                "status": automation_status,
                "duration_ms": max(0, int((time.perf_counter() - step_start) * 1000)),
                "details": {"automation_status": automation_status},
            }
        )

        if automation_status == "failed":
            cycle["status"] = "failed"
            cycle["next_action"] = "修复 run_once 失败项后重试。"
            failed_steps.append(
                {
                    "step_id": "automation_once",
                    "name": "run_once",
                    "status": "failed",
                    "reason": (automation.get("summary") or {}).get("next_action", "run_once 未完成"),
                }
            )
            run_steps.append(
                {
                    "step_id": "learning_report",
                    "name": "latest_learning_report",
                    "status": "skipped",
                    "duration_ms": 0,
                    "details": {"reason": "run_once 未完成，跳过 latest_learning_report"},
                }
            )
            run_steps.append(
                {
                    "step_id": "monitoring",
                    "name": "monitoring_sync",
                    "status": "skipped",
                    "duration_ms": 0,
                    "details": {"reason": "run_once 未完成，跳过 monitoring.run_once"},
                }
            )
            cycle["duration_ms"] = int((time.perf_counter() - cycle_started_at) * 1000)
            return cycle

        if (automation.get("summary") or {}).get("status") == "partial":
            cycle["status"] = "partial"
            cycle["next_action"] = (automation.get("summary") or {}).get(
                "next_action",
                "继续执行学习与监控并记录回溯差异。",
            )
            failed_steps.extend((automation.get("summary") or {}).get("failed_steps", []))

        try:
            from app.learning.service import LearningService

            step_start = time.perf_counter()
            report = LearningService().latest_report()
            cycle["learning_report"] = report.model_dump(mode="json") if report else None
            run_steps.append(
                {
                    "step_id": "learning_report",
                    "name": "latest_learning_report",
                    "status": "completed",
                    "duration_ms": max(0, int((time.perf_counter() - step_start) * 1000)),
                    "details": {"has_report": bool(report)},
                }
            )
        except Exception as exc:
            reason = str(exc)
            step_duration = max(0, int((time.perf_counter() - step_start) * 1000))
            run_steps.append(
                {
                    "step_id": "learning_report",
                    "name": "latest_learning_report",
                    "status": "failed",
                    "duration_ms": step_duration,
                    "reason": reason,
                    "details": {"monitor_mode": "latest_report"},
                }
            )
            failed_steps.append(
                {
                    "step_id": "learning_report",
                    "name": "latest_learning_report",
                    "status": "failed",
                    "reason": reason,
                }
            )
            cycle["learning_error"] = str(exc)
            cycle["status"] = "partial"
            cycle["next_action"] = "检查 learning service 后重试 latest_report。"

        try:
            from app.monitoring.service import MonitoringService

            step_start = time.perf_counter()
            monitoring_service = MonitoringService()
            monitoring = monitoring_service.run_once(limit=monitor_limit)
            cycle["monitoring"] = monitoring
            cycle["quality_gates"] = monitoring.get("quality_gates", []) if isinstance(monitoring.get("quality_gates"), list) else []
            cycle["quality_events_count"] = monitoring.get("quality_events_count", 0) or 0
            cycle["suppressed_by_quality_symbols"] = (
                monitoring.get("suppressed_by_quality_symbols", []) if isinstance(monitoring.get("suppressed_by_quality_symbols"), list) else []
            )
            cycle["quality_next_action"] = (
                monitoring.get("quality_next_action", "continue_with_alerts") or "continue_with_alerts"
            )
            if review_symbol:
                cycle["monitoring_review"] = monitoring_service.create_symbol_review(
                    symbol=review_symbol,
                    session_id=monitoring.get("session_id"),
                )
            run_steps.append(
                {
                    "step_id": "monitoring",
                    "name": "monitoring_sync",
                    "status": "completed",
                    "duration_ms": max(0, int((time.perf_counter() - step_start) * 1000)),
                    "details": {
                        "monitor_limit": monitor_limit,
                        "review_symbol": review_symbol,
                        "has_monitoring_review": bool(review_symbol and cycle.get("monitoring_review")),
                    },
                }
            )
            monitoring_quality_gates = cycle.get("quality_gates") or []
            for gate in monitoring_quality_gates:
                gate_quality_grade = str(gate.get("quality_grade") or "good").lower()
                if gate_quality_grade == "good":
                    continue
                self._event(
                    run_id,
                    "automation_monitoring_quality_gate",
                    gate.get("symbol"),
                    {
                        "run_id": run_id,
                        "symbol": gate.get("symbol"),
                        "quality_context": gate,
                        "risk_blocked": gate.get("risk_blocked") or [],
                        "suppress_actions": bool(gate.get("suppress_actions")),
                        "quality_grade": gate_quality_grade,
                        "quality_source": gate.get("quality_source"),
                    },
                )
                if cycle.get("quality_next_action") == "review_pause":
                    failed_steps.append(
                    {
                        "step_id": "monitoring_quality_gate",
                        "name": "monitoring_quality_gate",
                        "status": "failed",
                        "reason": f"quality_grade={gate_quality_grade}",
                        "details": {
                            "symbol": gate.get("symbol"),
                            "quality_grade": gate_quality_grade,
                        },
                    }
                    )
            if cycle.get("quality_next_action") in {"degrade_only", "review_pause"}:
                run_steps.append(
                    {
                        "step_id": "monitoring_quality_gate",
                        "name": "monitoring_quality_gate",
                        "status": "failed" if cycle.get("quality_next_action") == "review_pause" else "completed",
                        "duration_ms": 0,
                        "details": {
                            "quality_next_action": cycle.get("quality_next_action"),
                            "quality_events_count": cycle.get("quality_events_count"),
                            "suppressed_by_quality_symbols": cycle.get("suppressed_by_quality_symbols"),
                        },
                        "reason": "market_data_quality_gate",
                    }
                )
                if cycle.get("quality_next_action") == "review_pause":
                    cycle["status"] = "partial"
                    cycle["next_action"] = cycle.get("quality_next_action", "review_pause")
                elif cycle.get("status") == "completed":
                    cycle["next_action"] = cycle.get("quality_next_action", cycle["next_action"])
            else:
                run_steps.append(
                    {
                        "step_id": "monitoring_quality_gate",
                        "name": "monitoring_quality_gate",
                        "status": "completed",
                        "duration_ms": 0,
                        "details": {
                            "quality_next_action": cycle.get("quality_next_action"),
                            "quality_events_count": cycle.get("quality_events_count"),
                        },
                    }
                )
                if cycle["status"] == "completed" and (automation.get("summary") or {}).get("status") != "partial":
                    cycle["next_action"] = cycle["quality_next_action"]
        except Exception as exc:
            reason = str(exc)
            step_duration = max(0, int((time.perf_counter() - step_start) * 1000))
            run_steps.append(
                {
                    "step_id": "monitoring",
                    "name": "monitoring_sync",
                    "status": "failed",
                    "duration_ms": step_duration,
                    "reason": reason,
                    "details": {"monitor_limit": monitor_limit},
                }
            )
            failed_steps.append(
                {
                    "step_id": "monitoring",
                    "name": "monitoring_sync",
                    "status": "failed",
                    "reason": reason,
                }
            )
            cycle["monitoring_error"] = str(exc)
            cycle["status"] = "partial"
            cycle["next_action"] = "检查 monitoring service 后重试。"

        cycle["duration_ms"] = int((time.perf_counter() - cycle_started_at) * 1000)
        if cycle["status"] == "completed" and (automation.get("summary") or {}).get("status") == "partial":
            cycle["status"] = "partial"

        if cycle["status"] == "completed":
            cycle["next_action"] = "继续下一个周期。"

        return cycle

    def simulation_cockpit_run(self, limit: int = 5) -> dict[str, Any]:
        run_id = self._start_run("simulation_cockpit_run")
        self._event(
            run_id,
            "simulation_cockpit_started",
            None,
            {
                "limit": limit,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
        )
        result = SimCockpitService().simulation_cockpit_run(
            limit=limit,
            requested_by="automation_supervisor",
        )
        self._event(run_id, "simulation_cockpit_completed", None, result)
        self._finish_run(run_id, result)
        return {"run_id": run_id, "status": result.get("status", "completed"), "summary": result}

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

    def _finish_run(self, run_id: int, summary: dict[str, Any], status: str = "completed") -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE automation_runs
                SET status = ?, summary_json = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, json.dumps(summary, ensure_ascii=False), run_id),
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
