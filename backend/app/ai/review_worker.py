"""AI parameter proposals: generation, fail-closed validation and review.

Validation compares a proposal with the configuration of the latest measured
backtest through the deterministic A/B harness (``app.backtest.ab_harness``):
arm A is that base configuration, arm B is the base with the proposal's patch.
The caller predeclares the experiment - a fixed universe, an explicit
train / out-of-sample split, capital, costs and the causal fill policy - and
the decision is taken on the out-of-sample window only.

Fail closed
-----------
Whatever the decision needs and cannot see is a failure, never a pass: no
declared experiment, no measured base run, an empty base configuration (the
engine would silently substitute the current rules.yaml), a patch part the
merge does not apply, an out-of-sample window that overlaps what the proposal
could have seen, a declared symbol without bars, missing input provenance,
a non-causal or unrecorded execution policy, a failed or missing control, a
missing out-of-sample metric (``None`` is the absence of a measurement, not a
zero return) and too few closed trades. Nothing runs unless every
precondition holds.

Engineering diagnostic versus strategy evidence
-----------------------------------------------
Every comparison available today is an engineering diagnostic: the harness
never qualifies a result for a strategy claim, and no evidence class is
qualified (``QUALIFIED_EVIDENCE_CLASSES`` is empty). A comparison whose checks
all pass therefore ends as ``diagnostic_only``, which authorizes neither a
positive strategy claim nor simulation approval. ``validation_passed`` also
needs qualified evidence, so it stays unreachable until dated tradability, fee,
capacity and universe evidence exist (docs/RESEARCH_EVIDENCE_PLAN_20260924.md).
Approval re-checks the stored validation, so a legacy ``validation_passed`` row
written by the old comparison cannot be approved either.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import json
import math
from typing import Any

from app.ai.model_gateway import DisabledModelGateway, ModelGatewayResult
from app.backtest.ab_harness import (
    CONTROLS,
    MANIFEST_SCHEMA,
    ManifestError,
    input_fingerprint,
    run_ab,
    sha256_json,
    validate_manifest,
)
from app.backtest.execution_contract import EXECUTION_CONTRACT_VERSION, FILL_POLICY_PRE_OPEN
from app.config import settings
from app.storage.sqlite_store import SQLiteStore

VALIDATION_SCHEMA = "ai_proposal_validation.v2"
EXPERIMENT_SCHEMA = "ai_proposal_experiment.v1"
WINDOWS = ("train", "out_of_sample")
DECISION_WINDOW = "out_of_sample"
DECISION_METRICS = ("total_return", "max_drawdown")
MIN_OUT_OF_SAMPLE_CLOSED_TRADES = 20
# No evidence class qualifies a comparison for a strategy claim yet; see the
# module docstring. Adding one needs dated historical evidence, not a flag.
QUALIFIED_EVIDENCE_CLASSES: frozenset[str] = frozenset()
CHECKS = (
    "experiment_predeclared",
    "has_completed_backtest",
    "base_config_present",
    "patch_fully_applied",
    "hard_blocks_preserved",
    "live_trading_disabled",
    "out_of_sample_unseen",
    "declared_inputs_present",
    "causal_execution_policy",
    "input_provenance_recorded",
    "inputs_unchanged",
    "a_a_reproducibility",
    "out_of_sample_runs_completed",
    "metrics_present",
    "sample_size",
    "out_of_sample_not_worse",
)
_EXPERIMENT_REQUIRED = {
    "schema_version", "experiment_id", "hypothesis", "universe", "benchmark_symbol",
    "split", "capital", "execution", "costs", "evidence_class",
}
_EXPERIMENT_OPTIONAL = {"expected_input_sha256", "notes"}
# The only patch parts _merge_patch applies; anything else was never tested.
_MERGED_PATCH_KEYS = {"candidate_tiers", "rules"}


class AIReviewWorker:
    def __init__(self):
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.gateway = DisabledModelGateway()

    def generate_review(self) -> dict:
        trades = self.store.fetch_all(
            """
            SELECT *
            FROM historical_backtest_trades
            ORDER BY trade_date DESC, id DESC
            LIMIT 50
            """
        )
        gateway_result = self.gateway.propose_parameter_patch([dict(row) for row in trades])
        self._record_audit(gateway_result)
        proposed_patch = gateway_result.response["proposed_patch"]
        applied_blocks = gateway_result.safety["safety_blocks_applied"]
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_parameter_proposals (
                    trades_analyzed, proposed_patch_json, safety_blocks_json, status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    len(trades),
                    json.dumps(proposed_patch, ensure_ascii=False),
                    json.dumps(applied_blocks, ensure_ascii=False),
                    "draft",
                ),
            )
            proposal_id = int(cursor.lastrowid)
        return {
            "id": proposal_id,
            "status": "success",
            "trades_analyzed": len(trades),
            "proposed_patch": proposed_patch,
            "safety_blocks_applied": applied_blocks,
            "timestamp": datetime.now().isoformat(),
            "provider": gateway_result.provider,
            "simulation_only": True,
        }

    def list_proposals(self, limit: int = 20) -> list[dict]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM ai_parameter_proposals
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [self._proposal_model(row) for row in rows]

    def validate_proposal(self, proposal_id: int, experiment: dict[str, Any] | None = None) -> dict:
        proposal = self._get_proposal(proposal_id)
        patch = proposal["proposed_patch"]
        checks = dict.fromkeys(CHECKS, False)
        reasons: list[str] = []
        validation: dict[str, Any] = {
            "schema_version": VALIDATION_SCHEMA,
            "status": "validation_failed",
            "checks": checks,
            "failure_reasons": reasons,
            "experiment": None,
            "base_run": None,
            "patch_sha256": sha256_json(patch),
            "decision_window": DECISION_WINDOW,
            "in_sample": {},
            "out_of_sample": {},
            "evidence": {
                "evidence_class": None,
                "qualified_for_strategy_claim": False,
                "unqualified_reasons": [],
                "positive_strategy_claim_authorized": False,
                "simulation_approval_authorized": False,
            },
            "validated_at": datetime.now().isoformat(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": bool(settings.enable_live_trading),
        }

        checks["hard_blocks_preserved"] = self._hard_blocks_preserved(patch)
        if not checks["hard_blocks_preserved"]:
            reasons.append("hard_block_disabled_by_patch")
        checks["live_trading_disabled"] = settings.enable_live_trading is False
        if not checks["live_trading_disabled"]:
            reasons.append("live_trading_enabled")

        base_run = self._base_run()
        checks["has_completed_backtest"] = base_run is not None
        base_config: dict[str, Any] | None = None
        if base_run is None:
            reasons.append("no_completed_backtest_with_fills")
        else:
            base_config = self._base_config(base_run)
            validation["base_run"] = {
                "id": int(base_run["id"]),
                "start_date": base_run.get("start_date"),
                "end_date": base_run.get("end_date"),
                "config_sha256": sha256_json(base_config) if base_config is not None else None,
            }
            checks["base_config_present"] = base_config is not None
            if base_config is None:
                reasons.append("base_config_missing")
        proposed_config = None
        if base_config is not None:
            unapplied = self._unapplied_patch_parts(base_config, patch)
            checks["patch_fully_applied"] = not unapplied
            if unapplied:
                reasons.append(f"patch_not_fully_applied: {unapplied}")
            proposed_config = self._merge_patch(base_config, patch)

        manifests: dict[str, dict[str, Any]] | None = None
        if experiment is None:
            reasons.append("experiment_not_predeclared")
        else:
            arms = {"A": {"config": base_config or {}}, "B": {"config": proposed_config or {}}}
            try:
                manifests = self._window_manifests(experiment, arms)
            except ManifestError as exc:
                reasons.append(f"experiment_invalid: {exc}")
            else:
                checks["experiment_predeclared"] = True
                validation["experiment"] = {"sha256": sha256_json(experiment), "declaration": experiment}
                validation["evidence"]["evidence_class"] = experiment["evidence_class"]
                for name in WINDOWS:
                    window = manifests[name]["window"]
                    validation[self._summary_key(name)] = {
                        "period": {"start": window["start_date"], "end": window["end_date"]}
                    }
                cutoff = self._proposal_information_cutoff(base_run)
                oos_start = manifests[DECISION_WINDOW]["window"]["start_date"]
                checks["out_of_sample_unseen"] = cutoff is not None and oos_start > cutoff
                if not checks["out_of_sample_unseen"]:
                    reasons.append(
                        f"out_of_sample_overlaps_proposal_information: start={oos_start} cutoff={cutoff}"
                    )
                absent = self._absent_declared_inputs(manifests)
                checks["declared_inputs_present"] = not absent
                if absent:
                    reasons.append(f"declared_inputs_missing: {absent}")

        if reasons or manifests is None:
            # Fail closed before running anything: a comparison built on a
            # missing precondition cannot be evidence of anything.
            return self._save_validation(proposal_id, validation)

        span_before = input_fingerprint(self.store, manifests[DECISION_WINDOW])["sha256"]
        reports: dict[str, dict[str, Any]] = {}
        try:
            for name in WINDOWS:
                reports[name] = run_ab(manifests[name], database_path=settings.database_path)
        except ManifestError as exc:
            # validate_manifest already passed, so only a pinned input
            # fingerprint that no longer matches the data can raise here.
            reasons.append(f"pinned_input_fingerprint_mismatch: {exc}")
            return self._save_validation(proposal_id, validation)
        span_after = input_fingerprint(self.store, manifests[DECISION_WINDOW])["sha256"]

        policy_ok = provenance_ok = True
        inputs_ok = span_before == span_after
        if not inputs_ok:
            reasons.append("inputs_changed_between_windows")
        a_a_ok = True
        for name in WINDOWS:
            report = reports[name]
            summary = validation[self._summary_key(name)]
            summary.update(self._window_summary(report))
            controls = report.get("controls") or {}
            for control in CONTROLS:
                if controls.get(control) is not True:
                    reasons.append(f"control_failed_or_missing: {name}.{control}")
            if controls.get("a_a_reproducibility") is not True:
                a_a_ok = False
            if controls.get("input_fingerprint_unchanged") is not True:
                inputs_ok = False
            source = report.get("input") or {}
            if not source.get("sha256") or not source.get("bar_rows") or not report.get("manifest_sha256"):
                provenance_ok = False
                reasons.append(f"input_provenance_missing: {name}")
            for arm_name in ("A", "B"):
                arm = (report.get("arms") or {}).get(arm_name) or {}
                contract = arm.get("execution_contract") or {}
                if contract.get("version") != EXECUTION_CONTRACT_VERSION:
                    policy_ok = False
                    reasons.append(f"execution_contract_missing: {name}.{arm_name}")
                if contract.get("fill_policy") != FILL_POLICY_PRE_OPEN:
                    policy_ok = False
                    reasons.append(
                        f"execution_policy_not_causal: {name}.{arm_name}={contract.get('fill_policy')}"
                    )
                if arm.get("fundamental_point_in_time") is not True:
                    policy_ok = False
                    reasons.append(f"fundamentals_not_point_in_time: {name}.{arm_name}")
        checks["causal_execution_policy"] = policy_ok
        checks["input_provenance_recorded"] = provenance_ok
        checks["inputs_unchanged"] = inputs_ok
        checks["a_a_reproducibility"] = a_a_ok

        decision = self._out_of_sample_decision(reports[DECISION_WINDOW])
        checks.update(decision["checks"])
        reasons.extend(decision["reasons"])
        validation["out_of_sample"]["comparison"] = decision["comparison"]

        evidence = validation["evidence"]
        evidence["unqualified_reasons"] = sorted(
            {reason for report in reports.values() for reason in report.get("unqualified_reasons") or []}
        )
        qualified = (
            all(report.get("qualified_for_strategy_claim") is True for report in reports.values())
            and evidence["evidence_class"] in QUALIFIED_EVIDENCE_CLASSES
        )
        evidence["qualified_for_strategy_claim"] = qualified
        if not qualified:
            evidence["unqualified_reasons"].append("evidence_class_not_qualified_for_strategy_claims")
        if all(checks.values()):
            validation["status"] = "validation_passed" if qualified else "diagnostic_only"
        passed = validation["status"] == "validation_passed"
        evidence["positive_strategy_claim_authorized"] = passed
        evidence["simulation_approval_authorized"] = passed
        return self._save_validation(proposal_id, validation)

    def approve_for_simulation(
        self,
        proposal_id: int,
        reviewed_by: str = "user",
        note: str | None = None,
    ) -> dict:
        proposal = self._get_proposal(proposal_id)
        refusal = self._approval_refusal(proposal)
        if refusal:
            raise ValueError(f"AI proposal cannot be approved for simulation: {refusal}.")
        return self._review(proposal_id, "approved_for_simulation", reviewed_by, note)

    def reject(
        self,
        proposal_id: int,
        reviewed_by: str = "user",
        note: str | None = None,
    ) -> dict:
        self._get_proposal(proposal_id)
        return self._review(proposal_id, "rejected", reviewed_by, note)

    def _approval_refusal(self, proposal: dict[str, Any]) -> str | None:
        # Re-checked from the stored validation, not trusted from the status
        # column: a legacy validation_passed row carries no evidence at all.
        validation = proposal.get("validation") or {}
        checks = validation.get("checks") or {}
        evidence = validation.get("evidence") or {}
        if settings.enable_live_trading is not False:
            return "live trading is enabled"
        if proposal["status"] != "validation_passed":
            return f"status is {proposal['status']}, not validation_passed"
        if validation.get("schema_version") != VALIDATION_SCHEMA:
            return "validation predates the fail-closed evidence controls"
        if set(checks) != set(CHECKS) or not all(value is True for value in checks.values()):
            return "not every validation check passed"
        if (
            evidence.get("qualified_for_strategy_claim") is not True
            or evidence.get("evidence_class") not in QUALIFIED_EVIDENCE_CLASSES
        ):
            return "an engineering diagnostic is not qualified strategy evidence"
        return None

    def _base_run(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM historical_backtest_runs
            WHERE status = 'completed'
              AND json_valid(metrics_json)
              AND COALESCE(
                    json_extract(metrics_json, '$.entry_fill_count'),
                    json_extract(metrics_json, '$.trade_count'),
                    0
                  ) > 0
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return dict(row) if row else None

    @staticmethod
    def _base_config(base_run: dict[str, Any]) -> dict[str, Any] | None:
        # BacktestEngine replaces an empty config with the current rules.yaml,
        # which would compare the proposal against an undeclared baseline.
        try:
            config = json.loads(base_run.get("config_json") or "{}")
        except json.JSONDecodeError:
            return None
        if not isinstance(config, dict) or not isinstance(config.get("rules"), list) or not config["rules"]:
            return None
        return config

    def _proposal_information_cutoff(self, base_run: dict[str, Any] | None) -> str | None:
        # The proposal is built from the latest backtest trades; its exact
        # inputs are not recorded, so the out-of-sample window must start after
        # every stored trade and after the base run it modifies.
        row = self.store.fetch_one("SELECT MAX(trade_date) AS latest FROM historical_backtest_trades")
        candidates = [value for value in (row["latest"] if row else None, (base_run or {}).get("end_date")) if value]
        return max(str(value)[:10] for value in candidates) if candidates else None

    def _absent_declared_inputs(self, manifests: dict[str, dict[str, Any]]) -> list[str]:
        absent = []
        for name in WINDOWS:
            manifest = manifests[name]
            for symbol in [*manifest["universe"], manifest["benchmark_symbol"]]:
                variants = sorted({symbol, symbol.upper(), symbol.lower()})
                placeholders = ",".join("?" for _ in variants)
                row = self.store.fetch_one(
                    f"""
                    SELECT COUNT(*) AS bars
                    FROM daily_bar_cache
                    WHERE symbol IN ({placeholders}) AND quality_status = 'ready'
                      AND trade_date >= ? AND trade_date <= ?
                    """,
                    (*variants, manifest["window"]["start_date"], manifest["window"]["end_date"]),
                )
                if not row or not row["bars"]:
                    absent.append(f"{name}.{symbol}")
        return absent

    @staticmethod
    def _window_manifests(experiment: Any, arms: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if not isinstance(experiment, dict):
            raise ManifestError("experiment must be an object")
        missing = sorted(_EXPERIMENT_REQUIRED - set(experiment))
        extra = sorted(set(experiment) - _EXPERIMENT_REQUIRED - _EXPERIMENT_OPTIONAL)
        if missing or extra:
            raise ManifestError(f"experiment keys: missing={missing} unexpected={extra}")
        if experiment["schema_version"] != EXPERIMENT_SCHEMA:
            raise ManifestError(f"schema_version must be {EXPERIMENT_SCHEMA}")
        split = experiment["split"]
        if not isinstance(split, dict) or set(split) != set(WINDOWS):
            raise ManifestError(f"split must declare exactly {list(WINDOWS)}")
        for name in WINDOWS:
            window = split[name]
            if not isinstance(window, dict):
                raise ManifestError(f"split.{name} must be an object")
            for key in ("start_date", "end_date"):
                value = window.get(key)
                try:
                    # Canonical YYYY-MM-DD only: windows are compared as strings.
                    canonical = isinstance(value, str) and date.fromisoformat(value).isoformat() == value
                except ValueError:
                    canonical = False
                if not canonical:
                    raise ManifestError(f"split.{name}.{key} must be a YYYY-MM-DD date")
        if str(split["train"]["end_date"]) >= str(split[DECISION_WINDOW]["start_date"]):
            raise ManifestError("split.train must end before split.out_of_sample starts")
        pinned = experiment.get("expected_input_sha256") or {}
        if not isinstance(pinned, dict) or not set(pinned) <= set(WINDOWS):
            raise ManifestError(f"expected_input_sha256 may only pin {list(WINDOWS)}")
        manifests = {}
        for name in WINDOWS:
            manifest = {
                "schema_version": MANIFEST_SCHEMA,
                "experiment_id": f"{experiment['experiment_id']}:{name}",
                "hypothesis": experiment["hypothesis"],
                "window": {"start_date": split[name]["start_date"], "end_date": split[name]["end_date"]},
                "universe": experiment["universe"],
                "benchmark_symbol": experiment["benchmark_symbol"],
                "capital": experiment["capital"],
                "execution": experiment["execution"],
                "costs": experiment["costs"],
                "arms": arms,
                "primary_metric": "total_return",
                "controls": list(CONTROLS),
                "evidence_class": experiment["evidence_class"],
            }
            if name in pinned:
                manifest["expected_input_sha256"] = pinned[name]
            manifests[name] = validate_manifest(manifest)
        return manifests

    @staticmethod
    def _summary_key(window: str) -> str:
        return "in_sample" if window == "train" else window

    @staticmethod
    def _window_summary(report: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_status": report.get("status"),
            "manifest_sha256": report.get("manifest_sha256"),
            "input": report.get("input"),
            "controls": report.get("controls"),
            "arms": {
                name: {
                    "status": arm.get("status"),
                    "metrics": arm.get("metrics"),
                    "fill_policy": (arm.get("execution_contract") or {}).get("fill_policy"),
                    "execution_contract_version": (arm.get("execution_contract") or {}).get("version"),
                    "fundamental_point_in_time": arm.get("fundamental_point_in_time"),
                    "result_sha256": arm.get("result_sha256"),
                }
                for name, arm in (report.get("arms") or {}).items()
            },
        }

    @classmethod
    def _out_of_sample_decision(cls, report: dict[str, Any]) -> dict[str, Any]:
        arms = report.get("arms") or {}
        reasons: list[str] = []
        completed = True
        present = True
        sample = True
        for arm_name in ("A", "B"):
            arm = arms.get(arm_name) or {}
            if arm.get("status") != "completed":
                completed = False
                reasons.append(f"out_of_sample_run_not_completed: {arm_name}={arm.get('status')}")
            metrics = arm.get("metrics") or {}
            for metric in DECISION_METRICS:
                if not cls._is_measured(metrics.get(metric)):
                    present = False
                    reasons.append(f"metric_missing: out_of_sample.{arm_name}.{metric}")
            closed = metrics.get("closed_trade_count")
            if not isinstance(closed, int) or isinstance(closed, bool) or closed < MIN_OUT_OF_SAMPLE_CLOSED_TRADES:
                sample = False
                reasons.append(
                    f"insufficient_sample: out_of_sample.{arm_name}.closed_trade_count={closed} "
                    f"< {MIN_OUT_OF_SAMPLE_CLOSED_TRADES}"
                )
        comparison = None
        not_worse = False
        if present:
            before = arms["A"]["metrics"]
            after = arms["B"]["metrics"]
            comparison = {
                "total_return_b_minus_a": round(after["total_return"] - before["total_return"], 10),
                "max_drawdown_b_minus_a": round(after["max_drawdown"] - before["max_drawdown"], 10),
            }
            not_worse = (
                after["total_return"] >= before["total_return"]
                and after["max_drawdown"] <= before["max_drawdown"]
            )
            if not not_worse:
                reasons.append("out_of_sample_worse_than_base")
        return {
            "checks": {
                "out_of_sample_runs_completed": completed,
                "metrics_present": present,
                "sample_size": sample,
                "out_of_sample_not_worse": not_worse,
            },
            "reasons": reasons,
            "comparison": comparison,
        }

    @staticmethod
    def _is_measured(value: Any) -> bool:
        # A genuine 0.0 is a measurement; None, NaN or a non-number is not.
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def _save_validation(self, proposal_id: int, validation: dict[str, Any]) -> dict[str, Any]:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE ai_parameter_proposals
                SET status = ?, validation_json = ?
                WHERE id = ?
                """,
                (
                    validation["status"],
                    json.dumps(validation, ensure_ascii=False),
                    proposal_id,
                ),
            )
        return validation

    def _merge_patch(self, base_config: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base_config)
        if "candidate_tiers" in patch:
            merged.setdefault("candidate_tiers", {}).update(patch["candidate_tiers"])
        patch_rules = {rule.get("id"): rule for rule in patch.get("rules", []) if rule.get("id")}
        for rule in merged.get("rules", []):
            if rule.get("id") in patch_rules:
                rule.update(patch_rules[rule["id"]])
        return merged

    @staticmethod
    def _unapplied_patch_parts(base_config: dict[str, Any], patch: dict[str, Any]) -> list[str]:
        base_ids = {rule.get("id") for rule in base_config.get("rules", [])}
        unapplied = [f"key:{key}" for key in sorted(patch) if key not in _MERGED_PATCH_KEYS]
        unapplied += [
            f"rule:{rule.get('id')}" for rule in patch.get("rules", []) if rule.get("id") not in base_ids
        ]
        return unapplied

    def _record_audit(self, result: ModelGatewayResult) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_model_audit_logs(
                    provider, operation, prompt_json, response_json, safety_json, simulation_only
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.provider,
                    result.operation,
                    json.dumps(result.prompt, ensure_ascii=False),
                    json.dumps(result.response, ensure_ascii=False),
                    json.dumps(result.safety, ensure_ascii=False),
                    1,
                ),
            )

    def _review(
        self,
        proposal_id: int,
        status: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict:
        reviewed_at = datetime.now().isoformat()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE ai_parameter_proposals
                SET status = ?, reviewed_by = ?, review_note = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (status, reviewed_by, note, reviewed_at, proposal_id),
            )
        proposal = self._get_proposal(proposal_id)
        proposal["reviewed_at"] = reviewed_at
        return proposal

    def _get_proposal(self, proposal_id: int) -> dict:
        row = self.store.fetch_one(
            "SELECT * FROM ai_parameter_proposals WHERE id = ?",
            (proposal_id,),
        )
        if not row:
            raise ValueError("AI proposal not found.")
        return self._proposal_model(row)

    def _proposal_model(self, row) -> dict:
        item = dict(row)
        item["proposed_patch"] = json.loads(item.pop("proposed_patch_json") or "{}")
        item["safety_blocks"] = json.loads(item.pop("safety_blocks_json") or "[]")
        item["validation"] = json.loads(item.pop("validation_json") or "{}")
        return item

    def _hard_blocks_preserved(self, patch: dict) -> bool:
        return all(rule.get("hard_block", True) for rule in patch.get("rules", []))
