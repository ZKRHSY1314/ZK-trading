from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
import hashlib
import json
import time as monotonic_time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.config import settings
from app.data.trading_calendar import trading_session_age
from app.forecasting import FORECAST_HORIZONS, ForecastDecision, ForecastLedger
from app.models import AgentTaskInput
from app.storage.sqlite_store import SQLiteStore


ControlProfile = Literal["adaptive", "pulse", "training", "maintenance", "full"]
SHANGHAI = ZoneInfo("Asia/Shanghai")


class ControlPlaneService:
    """Deep module joining capture, simulation, feedback, and decision review.

    The interface deliberately exposes only a read-only status snapshot and one
    auditable run command.  Internal adapters remain injectable so tests never
    need network access or the project database.
    """

    def __init__(
        self,
        *,
        store: SQLiteStore | None = None,
        public_opinion_factory: Callable[[], Any] | None = None,
        agent_control_factory: Callable[[], Any] | None = None,
        feedback_factory: Callable[[], Any] | None = None,
        selection_factory: Callable[[], Any] | None = None,
        market_data_factory: Callable[[datetime, int], dict[str, Any]] | None = None,
        market_data_refresh_factory: Callable[[int], dict[str, Any]] | None = None,
        candidate_universe_factory: Callable[[int], list[str]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self._public_opinion_factory = public_opinion_factory or self._default_public_opinion
        self._agent_control_factory = agent_control_factory or self._default_agent_control
        self._feedback_factory = feedback_factory or self._default_feedback
        self._selection_factory = selection_factory or self._default_selection
        self._market_data_factory = market_data_factory or self._market_data_snapshot
        self._market_data_refresh_factory = (
            market_data_refresh_factory or self._default_market_data_refresh
        )
        self._candidate_universe_factory = (
            candidate_universe_factory or self._default_candidate_universe
        )
        self._clock = clock or (lambda: datetime.now(SHANGHAI))

    def status(self) -> dict[str, Any]:
        now = self._clock()
        stage = self._market_stage(now)
        pulse = self._safe_call(
            "market_pulse",
            lambda: self._public_opinion_factory().latest_context(limit=8),
            fallback={"status": "unavailable", "top_sectors": []},
        )
        feedback = self._safe_call(
            "training_feedback",
            lambda: self._feedback_factory().snapshot(),
            fallback={"status": "unavailable"},
        )
        market_data = self._market_data_factory(now, 30)
        counts = {
            table: self._count(table)
            for table in (
                "automation_runs",
                "automation_events",
                "agent_control_tasks",
                "agent_learning_samples",
                "agent_learning_outcomes",
                "public_opinion_runs",
                "forecast_decisions",
                "forecast_outcomes",
            )
        }
        latest_automation = self._latest_row(
            "SELECT id, mode, status, created_at, completed_at FROM automation_runs ORDER BY id DESC LIMIT 1"
        )
        latest_task = self._latest_row(
            "SELECT id, task_type, status, created_at, completed_at FROM agent_control_tasks ORDER BY id DESC LIMIT 1"
        )
        blockers: list[str] = []
        if settings.enable_live_trading:
            blockers.append("live_trading_enabled")
        if pulse.get("status") in {"unavailable", "stale"}:
            blockers.append(f"market_pulse_{pulse.get('status')}")
        if market_data["status"] != "fresh":
            blockers.append(f"market_data_{market_data['status']}")
        if market_data.get("trading_calendar_source") == "weekday_fallback":
            blockers.append("trading_calendar_fallback")
        feedback_status = str(feedback.get("status") or "unavailable")
        if feedback_status not in {"ready", "completed"}:
            blockers.append(f"training_feedback_{feedback_status}")
        elif counts["agent_learning_outcomes"] == 0:
            blockers.append("no_labeled_outcomes")

        return {
            "schema_version": "control_plane_status.v1",
            "status": "blocked" if settings.enable_live_trading else ("attention" if blockers else "ready"),
            "market_stage": stage,
            "recommended_profile": self._profile_for_stage(stage),
            "checked_at": now.isoformat(timespec="seconds"),
            "market_pulse": pulse,
            "market_data": market_data,
            "training_feedback": feedback,
            "latest_automation": latest_automation,
            "latest_task": latest_task,
            "counts": counts,
            "blocking_reasons": blockers if settings.enable_live_trading else [],
            "attention_reasons": [] if settings.enable_live_trading else blockers,
            "safety": self._safety(),
        }

    def run_once(
        self,
        *,
        profile: ControlProfile = "adaptive",
        limit: int = 30,
        monitor_limit: int = 5,
        review_symbol: str = "SZ002081",
        requested_by: str = "codex_control_plane",
    ) -> dict[str, Any]:
        started = monotonic_time.perf_counter()
        now = self._clock()
        selected_profile = self._profile_for_stage(self._market_stage(now)) if profile == "adaptive" else profile
        safe_limit = max(5, min(int(limit), 120))
        safe_monitor_limit = max(1, min(int(monitor_limit), 20))
        steps: list[dict[str, Any]] = []
        market_data = self._market_data_factory(now, safe_limit)

        if settings.enable_live_trading:
            return {
                "schema_version": "control_plane_run.v1",
                "status": "blocked",
                "profile": selected_profile,
                "steps": [],
                "reason": "live_trading_enabled",
                "duration_ms": 0,
                "safety": self._safety(),
            }

        if selected_profile in {"pulse", "maintenance", "full"}:
            steps.append(
                self._run_step(
                    "market_pulse",
                    lambda: self._public_opinion_factory().run(
                        limit=safe_limit,
                        persist=True,
                        requested_by=requested_by,
                    ),
                    compact=self._compact_pulse,
                )
            )

        if (
            selected_profile in {"pulse", "maintenance", "full"}
            and market_data["status"] != "fresh"
        ):
            refresh_payload = self._run_market_data_refresh(limit=safe_limit, now=now)
            steps.append(refresh_payload["step"])
            market_data = refresh_payload["market_data"]

        decision_payload: dict[str, Any] | None = None
        if selected_profile in {"pulse", "maintenance", "full"}:
            decision_payload = self._run_decision_step(limit=safe_limit, now=now)
            steps.append(decision_payload["step"])

        task_payload: dict[str, Any] | None = None
        if selected_profile == "full":
            decision_snapshot = (decision_payload or {}).get("result") or {}
            decision_ready = (
                market_data["status"] == "fresh"
                and (decision_payload or {}).get("step", {}).get("status") == "completed"
                and bool(decision_snapshot.get("daily_candidate_snapshot"))
            )
            task_payload = (
                self._run_simulation_task(
                    limit=safe_limit,
                    monitor_limit=safe_monitor_limit,
                    review_symbol=review_symbol,
                    requested_by=requested_by,
                    decision_snapshot=decision_snapshot,
                )
                if decision_ready
                else self._skip_simulation_task(
                    market_data,
                    decision_status=(decision_payload or {}).get("step", {}).get("status"),
                )
            )
            steps.append(task_payload["step"])

        if selected_profile in {"training", "maintenance", "full"}:
            steps.append(
                self._run_step(
                    "training_feedback",
                    lambda: self._feedback_factory().run(
                        limit=safe_limit,
                        horizon_days=5,
                    ),
                    compact=self._compact_feedback,
                )
            )

        status = self._rollup_status(steps)
        return {
            "schema_version": "control_plane_run.v1",
            "status": status,
            "profile": selected_profile,
            "requested_profile": profile,
            "market_stage": self._market_stage(now),
            "market_data": market_data,
            "started_at": now.isoformat(timespec="seconds"),
            "steps": steps,
            "task_id": (task_payload or {}).get("task_id"),
            "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
            "next_action": self._next_action(status, selected_profile),
            "safety": self._safety(),
        }

    def _run_simulation_task(
        self,
        *,
        limit: int,
        monitor_limit: int,
        review_symbol: str,
        requested_by: str,
        decision_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        started = monotonic_time.perf_counter()
        try:
            control = self._agent_control_factory()
            task = control.create_task(
                AgentTaskInput(
                    task_type="full_simulation_cycle",
                    requested_by=requested_by,
                    payload={
                        "limit": limit,
                        "monitor_limit": monitor_limit,
                        "review_symbol": review_symbol,
                        "decision_snapshot": decision_snapshot,
                    },
                )
            )
            completed = control.execute_task(int(task.id))
            payload = completed.model_dump(mode="json")
            business_status = str((payload.get("result") or {}).get("status") or payload.get("status") or "completed")
            step_status = self._normalize_status(business_status)
            return {
                "task_id": payload.get("id"),
                "step": {
                    "step_id": "simulation_cycle",
                    "status": step_status,
                    "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                    "details": {
                        "task_id": payload.get("id"),
                        "task_status": payload.get("status"),
                        "business_status": business_status,
                        "error": payload.get("error"),
                    },
                },
            }
        except Exception as exc:
            return {
                "task_id": None,
                "step": {
                    "step_id": "simulation_cycle",
                    "status": "failed",
                    "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                    "reason": str(exc),
                },
            }

    @staticmethod
    def _skip_simulation_task(
        market_data: dict[str, Any],
        *,
        decision_status: str | None = None,
    ) -> dict[str, Any]:
        reason = (
            f"daily_bar_cache_{market_data['status']}"
            if market_data.get("status") != "fresh"
            else f"decision_snapshot_{decision_status or 'unavailable'}"
        )
        return {
            "task_id": None,
            "step": {
                "step_id": "simulation_cycle",
                "status": "partial",
                "duration_ms": 0,
                "reason": reason,
                "details": {
                    "business_status": "skipped_decision_not_ready",
                    "market_data": market_data,
                    "decision_status": decision_status,
                },
            },
        }

    def _run_decision_step(self, *, limit: int, now: datetime) -> dict[str, Any]:
        started = monotonic_time.perf_counter()
        try:
            result = self._run_decision_snapshot(limit=limit, now=now)
            business_status = self._normalize_status(str(result.get("status") or "completed"))
            return {
                "result": result,
                "step": {
                    "step_id": "decision_snapshot",
                    "status": business_status,
                    "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                    "details": self._compact_selection(result),
                },
            }
        except Exception as exc:
            return {
                "result": None,
                "step": {
                    "step_id": "decision_snapshot",
                    "status": "failed",
                    "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                    "reason": str(exc),
                },
            }

    def _run_market_data_refresh(
        self,
        *,
        limit: int,
        now: datetime,
    ) -> dict[str, Any]:
        started = monotonic_time.perf_counter()
        try:
            refresh = self._market_data_refresh_factory(limit)
            market_data = self._market_data_factory(now, limit)
            status = "completed" if market_data["status"] == "fresh" else "partial"
            return {
                "market_data": market_data,
                "step": {
                    "step_id": "market_data_refresh",
                    "status": status,
                    "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                    "details": {
                        "processed": refresh.get("processed", 0),
                        "ready_count": len(
                            [
                                item
                                for item in refresh.get("results") or []
                                if item.get("status") == "success"
                            ]
                        ),
                        "market_data": market_data,
                    },
                },
            }
        except Exception as exc:
            market_data = self._market_data_factory(now, limit)
            return {
                "market_data": market_data,
                "step": {
                    "step_id": "market_data_refresh",
                    "status": "failed",
                    "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                    "reason": str(exc),
                    "details": {"market_data": market_data},
                },
            }

    def _run_step(
        self,
        step_id: str,
        action: Callable[[], dict[str, Any]],
        *,
        compact: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        started = monotonic_time.perf_counter()
        try:
            result = action()
            business_status = self._normalize_status(str(result.get("status") or "completed"))
            return {
                "step_id": step_id,
                "status": business_status,
                "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                "details": compact(result),
            }
        except Exception as exc:
            return {
                "step_id": step_id,
                "status": "failed",
                "duration_ms": int((monotonic_time.perf_counter() - started) * 1000),
                "reason": str(exc),
            }

    def _run_decision_snapshot(self, *, limit: int, now: datetime) -> dict[str, Any]:
        market_data = self._market_data_factory(now, limit)
        if market_data["status"] != "fresh":
            return {
                "status": "partial",
                "reason": f"daily_bar_cache_{market_data['status']}",
                "summary": {"candidate_count": 0, "decision_skipped": True},
                "daily_candidate_snapshot": [],
                "data_gap_candidates": [],
                "market_data": market_data,
            }
        result = {
            **self._selection_factory().run(mode="balanced", limit=limit),
            "market_data": market_data,
        }
        return self._record_decision_forecasts(result, now=now)

    def _record_decision_forecasts(
        self,
        result: dict[str, Any],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        candidates = [
            item
            for item in result.get("daily_candidate_snapshot") or []
            if isinstance(item, dict) and item.get("symbol")
        ]
        canonical = json.dumps(
            {
                "decision_cutoff": now.isoformat(),
                "schema_version": result.get("schema_version"),
                "config_version": result.get("config_version"),
                "candidates": candidates,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        decision_id = f"decision-{now.strftime('%Y%m%dT%H%M%S')}-{digest}"
        cutoff = now.isoformat()
        market_data = result.get("market_data") or {}
        data_version = str(
            market_data.get("latest_trade_date")
            or result.get("date")
            or now.date().isoformat()
        )
        model_version = ".".join(
            part
            for part in (
                str(result.get("schema_version") or "strategy_selection_v2"),
                str(result.get("config_version") or "unversioned"),
            )
            if part
        )
        prompt_version = str(
            (result.get("public_opinion_context") or {}).get("schema_version")
            or "codex_market_pulse.v1"
        )
        ledger = ForecastLedger(self.store)
        recorded = 0
        for rank, candidate in enumerate(candidates, start=1):
            raw_evidence = candidate.get("evidence")
            if isinstance(raw_evidence, list):
                evidence = [item for item in raw_evidence if isinstance(item, dict)]
            elif isinstance(raw_evidence, dict):
                evidence = [{"kind": "selection_evidence", "payload": raw_evidence}]
            else:
                evidence = []
            structure = (candidate.get("features") or {}).get("structure_signal") or {}
            probability = structure.get("pre_markup_probability")
            if probability is not None:
                try:
                    probability = max(0.0, min(1.0, float(probability)))
                except (TypeError, ValueError):
                    probability = None
            score = candidate.get("final_score")
            try:
                score = float(score) if score is not None else None
            except (TypeError, ValueError):
                score = None
            reasons = [str(item) for item in candidate.get("reasons") or []]
            for horizon in sorted(FORECAST_HORIZONS):
                ledger.record_forecast(
                    ForecastDecision(
                        decision_id=decision_id,
                        scope="stock",
                        subject=str(candidate["symbol"]),
                        decision_cutoff=cutoff,
                        available_at=cutoff,
                        horizon_days=horizon,
                        rank=rank,
                        score=score,
                        probability=probability,
                        model_version=model_version,
                        prompt_version=prompt_version,
                        data_version=data_version,
                        features=self._json_safe(candidate.get("features") or {}),
                        evidence=self._json_safe(evidence),
                        reasons=reasons,
                        status="pending_outcome",
                    )
                )
                recorded += 1
        result["snapshot_id"] = decision_id
        result["decision_cutoff"] = cutoff
        result["forecast_ledger"] = {
            "status": "recorded" if recorded else "empty",
            "recorded_count": recorded,
            "candidate_count": len(candidates),
            "horizons": sorted(FORECAST_HORIZONS),
            "review_only": True,
        }
        return result

    @staticmethod
    def _json_safe(value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))

    def _market_data_snapshot(self, now: datetime, limit: int = 30) -> dict[str, Any]:
        scope_limit = max(5, min(int(limit), 120))
        symbols = list(
            dict.fromkeys(
                str(symbol).strip().upper()
                for symbol in self._candidate_universe_factory(scope_limit)
                if str(symbol).strip()
            )
        )[:scope_limit]
        base_query = """
            SELECT symbol, MAX(trade_date) AS latest_trade_date
            FROM daily_bar_cache
            WHERE trade_date != 'ERROR'
              AND open > 0 AND high > 0 AND low > 0 AND close > 0
              AND (quality_status IS NULL OR LOWER(quality_status) IN ('ready', 'ok', 'valid'))
        """
        params: tuple[Any, ...] = ()
        if symbols:
            placeholders = ",".join("?" for _ in symbols)
            base_query += f" AND symbol IN ({placeholders})"
            params = tuple(symbols)
        base_query += " GROUP BY symbol ORDER BY symbol ASC"
        if not symbols:
            base_query += " LIMIT ?"
            params = (scope_limit,)
        rows = self.store.fetch_all(base_query, params)
        latest_values = [str(row["latest_trade_date"]) for row in rows if row.get("latest_trade_date")]
        latest_value = max(latest_values) if latest_values else None
        total_symbol_count = len(symbols) if symbols else len(rows)
        latest_symbol_count = sum(
            1 for row in rows if str(row.get("latest_trade_date") or "") == latest_value
        )
        universe_source = "selection_v2" if symbols else "daily_bar_cache_fallback"
        if not latest_value:
            return {
                "status": "missing",
                "latest_trade_date": None,
                "business_session_age": None,
                "total_symbol_count": total_symbol_count,
                "latest_symbol_count": 0,
                "latest_coverage_ratio": 0.0,
                "scope_limit": scope_limit,
                "universe_source": universe_source,
                "decision_allowed": False,
            }
        try:
            latest_date = datetime.fromisoformat(str(latest_value)[:10]).date()
        except ValueError:
            return {
                "status": "invalid",
                "latest_trade_date": str(latest_value),
                "business_session_age": None,
                "decision_allowed": False,
            }

        current = now.astimezone(SHANGHAI)
        today = current.date()
        calendar_age = max(0, (today - latest_date).days)
        business_age, calendar_source = trading_session_age(
            latest_date,
            today,
            exclude_target_session=current.time() <= time(15, 0),
        )
        total_symbols = total_symbol_count
        latest_symbols = latest_symbol_count
        coverage_ratio = latest_symbols / total_symbols if total_symbols else 0.0
        status = "fresh" if latest_date <= today and business_age == 0 else "stale"
        if latest_date > today:
            status = "future"
        elif status == "fresh" and coverage_ratio < 0.8:
            status = "incomplete"
        return {
            "status": status,
            "latest_trade_date": latest_date.isoformat(),
            "calendar_age_days": calendar_age,
            "business_session_age": business_age,
            "trading_calendar_source": calendar_source,
            "total_symbol_count": total_symbols,
            "latest_symbol_count": latest_symbols,
            "latest_coverage_ratio": round(coverage_ratio, 4),
            "scope_limit": scope_limit,
            "universe_source": universe_source,
            "decision_allowed": status == "fresh",
        }

    def _count(self, table: str) -> int:
        try:
            row = self.store.fetch_one(f"SELECT COUNT(*) AS count FROM {table}")
            return int((row or {}).get("count") or 0)
        except Exception:
            return 0

    def _latest_row(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        try:
            return self.store.fetch_one(query, params)
        except Exception:
            return None

    def _safe_call(
        self,
        name: str,
        action: Callable[[], dict[str, Any]],
        *,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return action()
        except Exception as exc:
            return {**fallback, "module": name, "error": str(exc)}

    @staticmethod
    def _compact_pulse(result: dict[str, Any]) -> dict[str, Any]:
        source_stats = result.get("source_stats") or {}
        return {
            "run_id": result.get("run_id"),
            "item_count": result.get("item_count", 0),
            "sector_count": result.get("sector_count", 0),
            "source_count": result.get("source_count", 0),
            "attempted_source_count": source_stats.get("attempted_count"),
            "successful_source_count": source_stats.get("succeeded_count"),
            "quality_warnings": source_stats.get("quality_warnings") or [],
            "error_count": len(result.get("errors") or []),
            "top_sectors": list(result.get("sector_signals") or [])[:5],
        }

    @staticmethod
    def _compact_feedback(result: dict[str, Any]) -> dict[str, Any]:
        steps = result.get("steps") or {}
        extraction = steps.get("extract_recent") or {}
        labeling = steps.get("label_recent_with_maturity_guard") or {}
        return {
            "status": result.get("status"),
            "created_samples": result.get(
                "created_samples",
                extraction.get("total_created", result.get("total_created", 0)),
            ),
            "labeled_outcomes": result.get(
                "labeled_outcomes",
                labeling.get("outcome_count", result.get("outcome_count", 0)),
            ),
            "mature_outcome_count": result.get(
                "mature_outcome_count",
                result.get("resolved_market_sample_count"),
            ),
            "quality": result.get("quality") or result.get("performance"),
            "blocked_reasons": result.get("blocked_reasons") or [],
        }

    @staticmethod
    def _compact_selection(result: dict[str, Any]) -> dict[str, Any]:
        summary = result.get("summary") or {}
        candidates = list(result.get("daily_candidate_snapshot") or [])
        return {
            "snapshot_id": result.get("snapshot_id"),
            "decision_cutoff": result.get("decision_cutoff"),
            "forecast_ledger": result.get("forecast_ledger"),
            "summary": summary,
            "top_candidates": [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "plan_type": item.get("plan_type"),
                    "final_score": item.get("final_score"),
                    "risk_flags": item.get("risk_flags") or [],
                }
                for item in candidates[:10]
            ],
            "data_gap_count": len(result.get("data_gap_candidates") or []),
            "reason": result.get("reason"),
            "market_data": result.get("market_data"),
        }

    @staticmethod
    def _normalize_status(value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"failed", "error"}:
            return "failed"
        if normalized in {"blocked", "rejected"}:
            return "blocked"
        if normalized in {
            "partial",
            "degraded",
            "attention",
            "empty",
            "stale",
            "insufficient_samples",
            "needs_outcomes",
            "not_ready",
        }:
            return "partial"
        return "completed"

    @staticmethod
    def _rollup_status(steps: list[dict[str, Any]]) -> str:
        statuses = {step.get("status") for step in steps}
        if "failed" in statuses:
            return "failed"
        if "blocked" in statuses:
            return "blocked"
        if "partial" in statuses:
            return "partial"
        return "completed"

    @staticmethod
    def _market_stage(now: datetime) -> str:
        current = now.astimezone(SHANGHAI)
        if current.weekday() >= 5:
            return "offhour"
        value = current.time()
        if time(8, 30) <= value < time(9, 30):
            return "preopen"
        if time(9, 30) <= value <= time(11, 30) or time(13, 0) <= value <= time(15, 0):
            return "intraday"
        if time(15, 0) < value <= time(16, 30):
            return "close_review"
        return "offhour"

    @staticmethod
    def _profile_for_stage(stage: str) -> ControlProfile:
        if stage in {"intraday", "close_review"}:
            return "full"
        if stage == "preopen":
            return "pulse"
        return "maintenance"

    @staticmethod
    def _next_action(status: str, profile: str) -> str:
        if status == "completed":
            return f"Schedule the next {profile} control-plane slot."
        if status == "partial":
            return "Review degraded source or data-freshness steps before the next slot."
        if status == "blocked":
            return "Keep live trading disabled and resolve the recorded blocker."
        return "Inspect the failed step and retry with the same review-only profile."

    @staticmethod
    def _safety() -> dict[str, Any]:
        return {
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "broker_access": False,
            "real_order_placement": False,
        }

    def _default_public_opinion(self) -> Any:
        from app.public_opinion.service import CodexPublicOpinionService

        return CodexPublicOpinionService(store=self.store)

    @staticmethod
    def _default_agent_control() -> Any:
        from app.agent_control.service import AgentControlService

        return AgentControlService()

    def _default_feedback(self) -> Any:
        from app.agent_control.training_feedback import TrainingFeedbackModule

        return TrainingFeedbackModule(store=self.store)

    def _default_selection(self) -> Any:
        from app.candidates.selection_v2 import StrategySelectionV2Service

        return StrategySelectionV2Service(store=self.store)

    def _default_candidate_universe(self, limit: int) -> list[str]:
        from app.candidates.selection_v2 import StrategySelectionV2Service

        return StrategySelectionV2Service(store=self.store).candidate_universe(limit=limit)

    def _default_market_data_refresh(self, limit: int) -> dict[str, Any]:
        from app.data.daily_bar_cache import DailyBarCacheService

        scope_limit = max(5, min(int(limit), 120))
        symbols = list(dict.fromkeys(self._candidate_universe_factory(scope_limit)))
        if not symbols:
            return {"processed": 0, "results": [], "reason": "candidate_universe_empty"}
        placeholders = ",".join("?" for _ in symbols)
        rows = self.store.fetch_all(
            f"""
            SELECT symbol, MAX(CASE WHEN trade_date != 'ERROR' THEN trade_date END) AS latest_trade_date
            FROM daily_bar_cache
            WHERE symbol IN ({placeholders})
            GROUP BY symbol
            """,
            tuple(symbols),
        )
        latest_by_symbol = {
            str(row["symbol"]): str(row.get("latest_trade_date") or "") for row in rows
        }
        batch = sorted(
            symbols,
            key=lambda symbol: (latest_by_symbol.get(symbol, ""), symbol),
        )[:25]
        result = DailyBarCacheService(store=self.store).refresh_symbols(batch, days=180)
        result["scope_limit"] = scope_limit
        result["batch_symbols"] = batch
        return result
