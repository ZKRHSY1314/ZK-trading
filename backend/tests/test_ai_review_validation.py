"""Fail-closed validation of AI parameter proposals.

Every database here is a synthetic temporary SQLite file. The comparisons
prove engineering behaviour only (determinism, controls, refusals); nothing
here is evidence about a strategy.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import app.ai.review_worker as review_worker
import app.backtest.ab_harness as ab_harness
from app.ai.review_worker import CHECKS, VALIDATION_SCHEMA, AIReviewWorker
from app.backtest.ab_harness import effective_costs, input_fingerprint
from app.config import settings
from app.main import app
from app.storage.sqlite_store import SQLiteStore

SYMBOLS = [f"SH6003{index:02d}" for index in range(1, 9)]
BENCHMARK = "SH000300"


def _weekdays(start: date, count: int) -> list[str]:
    days, current = [], start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


DAYS = _weekdays(date(2020, 3, 2), 60)
TRAIN = {"start_date": DAYS[0], "end_date": DAYS[29]}
OUT_OF_SAMPLE = {"start_date": DAYS[30], "end_date": DAYS[59]}


def _config(min_volume_ratio: float = 1.0) -> dict:
    return {
        "candidate_tiers": {"strong_min_score": 20, "watch_min_score": 10},
        "rules": [{"id": "dengzhan_forced_divergence", "name": "volume", "group": "strategy",
                   "enabled": True, "weight": 100, "hard_block": False,
                   "params": {"min_volume_ratio": min_volume_ratio}}],
        "exit_rules": {"stop_loss_pct": 6.0, "partial_take_profit_pct": 15.0,
                       "partial_take_profit_ratio": 0.5, "break_ma_window": 5,
                       "require_below_limit_up_avg": False, "max_holding_days": 3},
    }


# Changes nothing the engine uses, so both arms trade identically.
NEUTRAL_PATCH = {"candidate_tiers": {"strong_min_score": 20}}
# A threshold no synthetic bar reaches: arm B never signals, so it has no return.
SILENT_PATCH = {"rules": [{"id": "dengzhan_forced_divergence", "params": {"min_volume_ratio": 50.0}}]}


def _experiment(**overrides) -> dict:
    experiment = {
        "schema_version": "ai_proposal_experiment.v1",
        "experiment_id": "synthetic-proposal-check",
        "hypothesis": "Synthetic engineering check of the proposal validation path.",
        "universe": list(SYMBOLS),
        "benchmark_symbol": BENCHMARK,
        "split": {"train": dict(TRAIN), "out_of_sample": dict(OUT_OF_SAMPLE)},
        "capital": {"initial_cash": 1_000_000, "max_positions": 4, "per_symbol_cap": 0.2},
        "execution": {"fill_policy": "pre_open_causal", "allow_projected_fundamentals": False},
        "costs": effective_costs(),
        "evidence_class": "engineering_synthetic",
    }
    experiment.update(overrides)
    return experiment


@pytest.fixture
def synthetic_db(tmp_path, monkeypatch) -> SQLiteStore:
    path = tmp_path / "ai-review-synthetic.sqlite3"
    monkeypatch.setattr(settings, "database_path", path)
    store = SQLiteStore(path)
    store.init()
    rows = []
    for index, day in enumerate(DAYS):
        rows.append((BENCHMARK, day, 100 + index * 0.1, 101 + index * 0.1, 99 + index * 0.1,
                     100 + index * 0.1, 1e6, 1e10))
        for offset, symbol in enumerate(SYMBOLS):
            base = 10 + offset * 2 + ((index * (offset + 3)) % 7) * 0.15
            volume = 1e6 * (2.5 if (index + offset) % 3 == 0 else 1.0)
            rows.append((symbol, day, base, base * 1.03, base * 0.98, base * 1.01, volume, 1e9))
    with store.connect() as conn:
        conn.executemany(
            "INSERT INTO daily_bar_cache(symbol, trade_date, open, high, low, close, volume, amount, "
            "source, quality_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synthetic', 'ready')", rows)
    return store


def _base_run(store: SQLiteStore, *, config: dict | None = None, end_date: str = TRAIN["end_date"]) -> int:
    with store.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status, benchmark_symbol,
                initial_cash, final_cash, metrics_json
            ) VALUES (?, 'synthetic', ?, ?, 'completed', ?, 1000000, 1000000, ?)
            """,
            (json.dumps(_config() if config is None else config), TRAIN["start_date"], end_date,
             BENCHMARK, json.dumps({"trade_count": 4, "entry_fill_count": 2})),
        )
        return int(cursor.lastrowid)


def _proposal(store: SQLiteStore, patch: dict, *, status: str = "draft", validation: dict | None = None) -> int:
    with store.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO ai_parameter_proposals(trades_analyzed, proposed_patch_json, safety_blocks_json, "
            "status, validation_json) VALUES (0, ?, '[]', ?, ?)",
            (json.dumps(patch), status, json.dumps(validation or {})),
        )
        return int(cursor.lastrowid)


def _status(store: SQLiteStore, proposal_id: int) -> str:
    return store.fetch_one("SELECT status FROM ai_parameter_proposals WHERE id = ?", (proposal_id,))["status"]


def _run_count(store: SQLiteStore) -> int:
    return store.fetch_one("SELECT COUNT(*) AS n FROM historical_backtest_runs")["n"]


def _forbid_comparison(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("no comparison may run when a precondition failed")

    monkeypatch.setattr(review_worker, "run_ab", refuse)


def _tamper_reports(monkeypatch, mutate):
    real = review_worker.run_ab

    def tampered(manifest, *, database_path):
        report = real(manifest, database_path=database_path)
        window = manifest["experiment_id"].rsplit(":", 1)[1]
        mutate(window, report)
        return report

    monkeypatch.setattr(review_worker, "run_ab", tampered)


# --- the one path where every check passes -------------------------------------


def test_every_check_passing_is_only_an_engineering_diagnostic(synthetic_db):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    runs_before = _run_count(synthetic_db)
    pinned = {
        name: input_fingerprint(synthetic_db, {"universe": SYMBOLS, "benchmark_symbol": BENCHMARK,
                                               "window": window})["sha256"]
        for name, window in (("train", TRAIN), ("out_of_sample", OUT_OF_SAMPLE))
    }

    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment(expected_input_sha256=pinned))

    assert validation["failure_reasons"] == []
    assert set(validation["checks"]) == set(CHECKS) and all(validation["checks"].values())
    assert validation["status"] == "diagnostic_only"
    assert validation["schema_version"] == VALIDATION_SCHEMA
    evidence = validation["evidence"]
    assert evidence["evidence_class"] == "engineering_synthetic"
    assert evidence["qualified_for_strategy_claim"] is False
    assert evidence["positive_strategy_claim_authorized"] is False
    assert evidence["simulation_approval_authorized"] is False
    assert "evidence_class_not_qualified_for_strategy_claims" in evidence["unqualified_reasons"]
    assert "daily_bars_cannot_prove_historical_auction_fills" in evidence["unqualified_reasons"]
    # The split is explicit and the decision uses only the out-of-sample window.
    assert validation["decision_window"] == "out_of_sample"
    assert validation["in_sample"]["period"] == {"start": TRAIN["start_date"], "end": TRAIN["end_date"]}
    oos = validation["out_of_sample"]
    assert oos["period"] == {"start": OUT_OF_SAMPLE["start_date"], "end": OUT_OF_SAMPLE["end_date"]}
    assert oos["input"]["sha256"] == pinned["out_of_sample"]
    assert oos["comparison"] == {"total_return_b_minus_a": 0.0, "max_drawdown_b_minus_a": 0.0}
    for window in (validation["in_sample"], oos):
        for arm in window["arms"].values():
            assert arm["fill_policy"] == "pre_open_causal"
            assert arm["fundamental_point_in_time"] is True
    assert oos["arms"]["B"]["metrics"]["closed_trade_count"] >= review_worker.MIN_OUT_OF_SAMPLE_CLOSED_TRADES
    # Review-only: nothing persisted but the validation itself; live trading stays off.
    assert _run_count(synthetic_db) == runs_before
    assert validation["live_trading_enabled"] is False and validation["simulation_only"] is True
    assert _status(synthetic_db, proposal_id) == "diagnostic_only"
    with pytest.raises(ValueError, match="diagnostic_only, not validation_passed"):
        AIReviewWorker().approve_for_simulation(proposal_id)
    assert _status(synthetic_db, proposal_id) == "diagnostic_only"


# --- missing versus genuine zero ------------------------------------------------


def test_a_missing_out_of_sample_metric_fails_instead_of_counting_as_zero(synthetic_db):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, SILENT_PATCH)

    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    arms = validation["out_of_sample"]["arms"]
    assert arms["A"]["metrics"]["total_return"] is not None
    assert arms["B"]["status"] == "no_signal"
    assert arms["B"]["metrics"]["total_return"] is None and arms["B"]["metrics"]["max_drawdown"] is None
    # The legacy comparison read None as 0.0, so this silent arm looked "not worse".
    a, b = arms["A"]["metrics"], arms["B"]["metrics"]
    assert (float(b["total_return"] or 0) >= float(a["total_return"] or 0)
            and float(b["max_drawdown"] or 0) <= float(a["max_drawdown"] or 0))
    assert validation["status"] == "validation_failed"
    assert validation["checks"]["metrics_present"] is False
    assert validation["checks"]["out_of_sample_not_worse"] is False
    assert validation["out_of_sample"]["comparison"] is None
    assert "metric_missing: out_of_sample.B.total_return" in validation["failure_reasons"]
    assert "metric_missing: out_of_sample.B.max_drawdown" in validation["failure_reasons"]
    assert "out_of_sample_run_not_completed: B=no_signal" in validation["failure_reasons"]


def _arm(total_return, max_drawdown, closed=25, status="completed") -> dict:
    return {"status": status, "metrics": {"total_return": total_return, "max_drawdown": max_drawdown,
                                          "closed_trade_count": closed}}


def test_a_genuine_zero_is_a_measurement_and_none_nan_or_bool_are_not():
    decide = AIReviewWorker._out_of_sample_decision
    zero = decide({"arms": {"A": _arm(0.0, 0.0), "B": _arm(0.0, 0.0)}})
    assert zero["checks"] == {"out_of_sample_runs_completed": True, "metrics_present": True,
                              "sample_size": True, "out_of_sample_not_worse": True}
    assert zero["comparison"] == {"total_return_b_minus_a": 0.0, "max_drawdown_b_minus_a": 0.0}

    worse = decide({"arms": {"A": _arm(0.0, 0.0), "B": _arm(-0.01, 0.0)}})
    assert worse["checks"]["metrics_present"] is True
    assert worse["checks"]["out_of_sample_not_worse"] is False
    assert "out_of_sample_worse_than_base" in worse["reasons"]

    for missing in (None, float("nan"), float("inf"), True, "0.0"):
        result = decide({"arms": {"A": _arm(0.0, 0.0), "B": _arm(missing, 0.0)}})
        assert result["checks"]["metrics_present"] is False, missing
        assert result["checks"]["out_of_sample_not_worse"] is False, missing
        assert result["comparison"] is None
        assert "metric_missing: out_of_sample.B.total_return" in result["reasons"]

    empty = decide({})
    assert not any(empty["checks"].values())


# --- insufficient samples -------------------------------------------------------


def test_too_few_out_of_sample_closed_trades_fail_closed(synthetic_db):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    short = {"start_date": DAYS[30], "end_date": DAYS[33]}

    validation = AIReviewWorker().validate_proposal(
        proposal_id, _experiment(split={"train": dict(TRAIN), "out_of_sample": short}))

    closed = validation["out_of_sample"]["arms"]["A"]["metrics"]["closed_trade_count"]
    assert closed < review_worker.MIN_OUT_OF_SAMPLE_CLOSED_TRADES
    assert validation["status"] == "validation_failed"
    assert validation["checks"]["sample_size"] is False
    assert any(reason.startswith("insufficient_sample: out_of_sample.A.closed_trade_count=")
               for reason in validation["failure_reasons"])


def test_closed_trade_count_must_be_a_real_count():
    for closed in (19, None, 20.0, True):
        result = AIReviewWorker._out_of_sample_decision({"arms": {"A": _arm(0.0, 0.0), "B": _arm(0.0, 0.0, closed)}})
        assert result["checks"]["sample_size"] is False, closed


# --- unequal or changing inputs -------------------------------------------------


def test_data_changing_while_an_arm_runs_fails_the_input_control(synthetic_db, monkeypatch):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    real_run_arm = ab_harness._run_arm
    calls = {"n": 0}

    def run_arm_then_edit_data(manifest, config):
        result = real_run_arm(manifest, config)
        calls["n"] += 1
        if calls["n"] == 1:
            # Arm B of the train window now sees different bars from arm A.
            with sqlite3.connect(settings.database_path) as conn:
                conn.execute("UPDATE daily_bar_cache SET close = close * 1.05 WHERE symbol = ? AND trade_date = ?",
                             (SYMBOLS[0], DAYS[5]))
        return result

    monkeypatch.setattr(ab_harness, "_run_arm", run_arm_then_edit_data)
    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    assert validation["status"] == "validation_failed"
    assert validation["checks"]["inputs_unchanged"] is False
    assert "control_failed_or_missing: train.input_fingerprint_unchanged" in validation["failure_reasons"]
    assert "inputs_changed_between_windows" in validation["failure_reasons"]


def test_data_changing_between_the_two_windows_fails_closed(synthetic_db, monkeypatch):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    real = review_worker.run_ab

    def run_then_edit_out_of_sample_bars(manifest, *, database_path):
        report = real(manifest, database_path=database_path)
        if manifest["experiment_id"].endswith(":train"):
            with sqlite3.connect(settings.database_path) as conn:
                conn.execute("UPDATE daily_bar_cache SET volume = volume * 3 WHERE trade_date = ?", (DAYS[40],))
        return report

    monkeypatch.setattr(review_worker, "run_ab", run_then_edit_out_of_sample_bars)
    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    # Each window's own controls pass; only the span check sees the change.
    assert validation["in_sample"]["controls"]["input_fingerprint_unchanged"] is True
    assert validation["out_of_sample"]["controls"]["input_fingerprint_unchanged"] is True
    assert validation["checks"]["inputs_unchanged"] is False
    assert validation["status"] == "validation_failed"
    assert "inputs_changed_between_windows" in validation["failure_reasons"]


def test_a_pinned_input_fingerprint_that_no_longer_matches_fails_closed(synthetic_db):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)

    validation = AIReviewWorker().validate_proposal(
        proposal_id, _experiment(expected_input_sha256={"out_of_sample": "0" * 64}))

    assert validation["status"] == "validation_failed"
    assert validation["checks"]["inputs_unchanged"] is False
    assert any(reason.startswith("pinned_input_fingerprint_mismatch:") for reason in validation["failure_reasons"])


def test_a_declared_symbol_without_bars_in_a_window_fails_before_running(synthetic_db, monkeypatch):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    with synthetic_db.connect() as conn:
        conn.execute("DELETE FROM daily_bar_cache WHERE symbol = ? AND trade_date >= ?",
                     (SYMBOLS[2], OUT_OF_SAMPLE["start_date"]))
    _forbid_comparison(monkeypatch)

    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment(universe=[*SYMBOLS, "SH600999"]))

    assert validation["status"] == "validation_failed"
    assert validation["checks"]["declared_inputs_present"] is False
    reason = next(r for r in validation["failure_reasons"] if r.startswith("declared_inputs_missing:"))
    assert f"out_of_sample.{SYMBOLS[2]}" in reason and "train.SH600999" in reason
    assert f"train.{SYMBOLS[2]}" not in reason


# --- failed or missing controls, provenance and execution policy ----------------


def test_a_real_a_a_failure_fails_validation(synthetic_db, monkeypatch):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    real_run_arm = ab_harness._run_arm
    calls = {"n": 0}

    def nondeterministic(manifest, config):
        result = real_run_arm(manifest, config)
        calls["n"] += 1
        if calls["n"] % 3 == 0:  # the A rerun of each window
            result["result_sha256"] = "f" * 64
        return result

    monkeypatch.setattr(ab_harness, "_run_arm", nondeterministic)
    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    assert validation["in_sample"]["report_status"] == "invalid"
    assert validation["checks"]["a_a_reproducibility"] is False
    assert validation["status"] == "validation_failed"
    assert "control_failed_or_missing: out_of_sample.a_a_reproducibility" in validation["failure_reasons"]


def _set_arm(window, arm, key, value):
    def mutate(name, report):
        if name == window:
            report["arms"][arm][key] = value
    return mutate


@pytest.mark.parametrize("mutate,check,reason", [
    (lambda name, report: report["controls"].update(a_a_reproducibility=False),
     "a_a_reproducibility", "control_failed_or_missing: train.a_a_reproducibility"),
    (lambda name, report: report.pop("controls"),
     "inputs_unchanged", "control_failed_or_missing: out_of_sample.input_fingerprint_unchanged"),
    (lambda name, report: report.update(input={}),
     "input_provenance_recorded", "input_provenance_missing: train"),
    (lambda name, report: report.pop("manifest_sha256"),
     "input_provenance_recorded", "input_provenance_missing: out_of_sample"),
    (_set_arm("out_of_sample", "B", "execution_contract",
              {"version": "backtest_execution.v2", "fill_policy": "daily_bar_retrospective"}),
     "causal_execution_policy", "execution_policy_not_causal: out_of_sample.B=daily_bar_retrospective"),
    (_set_arm("train", "A", "execution_contract", None),
     "causal_execution_policy", "execution_contract_missing: train.A"),
    (_set_arm("out_of_sample", "A", "fundamental_point_in_time", False),
     "causal_execution_policy", "fundamentals_not_point_in_time: out_of_sample.A"),
], ids=["a_a_false", "controls_missing", "input_missing", "manifest_hash_missing",
        "retrospective_fills_reported", "contract_missing", "fundamentals_projected"])
def test_missing_or_failed_report_evidence_fails_closed(synthetic_db, monkeypatch, mutate, check, reason):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    _tamper_reports(monkeypatch, mutate)

    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    assert validation["status"] == "validation_failed"
    assert validation["checks"][check] is False
    assert reason in validation["failure_reasons"]


# --- retrospective fills and other undeclared or invalid experiments ------------


def _without(key):
    def mutate(experiment):
        experiment.pop(key)
    return mutate


@pytest.mark.parametrize("mutate,match", [
    (lambda e: e["execution"].update(fill_policy="daily_bar_retrospective"), "fill_policy must be pre_open_causal"),
    (lambda e: e["execution"].pop("fill_policy"), "fill_policy must be pre_open_causal"),
    (lambda e: e["execution"].update(allow_projected_fundamentals=True), "projected"),
    (_without("split"), "missing=['split']"),
    (lambda e: e["split"].pop("out_of_sample"), "split must declare exactly"),
    (lambda e: e["split"].update(holdout=dict(OUT_OF_SAMPLE)), "split must declare exactly"),
    (lambda e: e["split"]["train"].update(end_date=OUT_OF_SAMPLE["start_date"]), "must end before"),
    (lambda e: e["split"]["out_of_sample"].update(start_date="20200413"), "YYYY-MM-DD"),
    (lambda e: e.update(universe=[]), "universe"),
    (lambda e: e["costs"].update(commission_rate=0.0), "costs"),
    (lambda e: e.update(evidence_class="qualified_historical"), "evidence_class"),
    (lambda e: e.update(schema_version="ai_proposal_experiment.v0"), "schema_version"),
    (lambda e: e.update(primary_metric="sharpe"), "unexpected=['primary_metric']"),
    (lambda e: e.update(expected_input_sha256={"holdout": "0" * 64}), "may only pin"),
], ids=["retrospective_fills", "fill_policy_missing", "projected_fundamentals", "no_split",
        "one_window", "extra_window", "overlapping_windows", "non_canonical_date", "empty_universe",
        "cost_mismatch", "self_declared_qualified", "schema", "undeclared_knob", "pin_unknown_window"])
def test_an_invalid_experiment_is_refused_before_anything_runs(synthetic_db, monkeypatch, mutate, match):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    experiment = copy.deepcopy(_experiment())
    mutate(experiment)
    _forbid_comparison(monkeypatch)

    validation = AIReviewWorker().validate_proposal(proposal_id, experiment)

    assert validation["status"] == "validation_failed"
    assert validation["checks"]["experiment_predeclared"] is False
    assert validation["experiment"] is None
    reason = next(r for r in validation["failure_reasons"] if r.startswith("experiment_invalid:"))
    assert match in reason


def test_no_experiment_empty_base_config_and_unapplied_patch_fail_before_running(synthetic_db, monkeypatch):
    _base_run(synthetic_db, config={})
    gateway_like_patch = {"rules": [{"id": "constitution_no_high_position", "weight": 20, "hard_block": True}],
                          "min_market_cap": 5_000_000_000, "candidate_tiers": {"strong_min_score": 85}}
    proposal_id = _proposal(synthetic_db, gateway_like_patch)
    _forbid_comparison(monkeypatch)

    validation = AIReviewWorker().validate_proposal(proposal_id)

    assert validation["status"] == "validation_failed"
    assert "experiment_not_predeclared" in validation["failure_reasons"]
    # An empty config would make the engine silently use the current rules.yaml.
    assert "base_config_missing" in validation["failure_reasons"]
    assert validation["base_run"]["config_sha256"] is None

    _base_run(synthetic_db)  # now a real base configuration exists
    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())
    assert validation["checks"]["base_config_present"] is True
    assert validation["checks"]["patch_fully_applied"] is False
    assert ("patch_not_fully_applied: ['key:min_market_cap', 'rule:constitution_no_high_position']"
            in validation["failure_reasons"])


def test_the_out_of_sample_window_must_start_after_what_the_proposal_could_see(synthetic_db, monkeypatch):
    _base_run(synthetic_db, end_date=OUT_OF_SAMPLE["start_date"])
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    _forbid_comparison(monkeypatch)

    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    assert validation["status"] == "validation_failed"
    assert validation["checks"]["out_of_sample_unseen"] is False
    assert (f"out_of_sample_overlaps_proposal_information: start={OUT_OF_SAMPLE['start_date']} "
            f"cutoff={OUT_OF_SAMPLE['start_date']}") in validation["failure_reasons"]


# --- approval gating ------------------------------------------------------------


def test_a_forged_qualified_flag_on_a_synthetic_comparison_is_not_evidence(synthetic_db, monkeypatch):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    _tamper_reports(monkeypatch, lambda name, report: report.update(qualified_for_strategy_claim=True))

    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    assert all(validation["checks"].values())
    assert validation["status"] == "diagnostic_only"
    assert validation["evidence"]["qualified_for_strategy_claim"] is False
    assert validation["evidence"]["simulation_approval_authorized"] is False
    with pytest.raises(ValueError):
        AIReviewWorker().approve_for_simulation(proposal_id)


def _all_passing_validation(**overrides) -> dict:
    validation = {
        "schema_version": VALIDATION_SCHEMA,
        "checks": dict.fromkeys(CHECKS, True),
        "evidence": {"evidence_class": "engineering_synthetic", "qualified_for_strategy_claim": True},
    }
    validation.update(overrides)
    return validation


@pytest.mark.parametrize("status,validation,match", [
    # Written by the legacy comparison: all its old checks true, no evidence.
    ("validation_passed", {"status": "validation_passed", "checks": {
        "has_completed_backtest": True, "sample_size": True, "out_of_sample_not_worse": True,
        "hard_blocks_preserved": True, "live_trading_disabled": True}}, "predates"),
    ("validation_passed", _all_passing_validation(), "not qualified strategy evidence"),
    ("validation_passed", _all_passing_validation(checks={**dict.fromkeys(CHECKS, True), "sample_size": False}),
     "not every validation check passed"),
    ("validation_passed", _all_passing_validation(checks={}), "not every validation check passed"),
    ("diagnostic_only", _all_passing_validation(), "not validation_passed"),
    ("validation_failed", _all_passing_validation(), "not validation_passed"),
    ("draft", {}, "not validation_passed"),
], ids=["legacy_passed_row", "forged_synthetic_evidence", "failed_check", "no_checks",
        "diagnostic", "failed", "never_validated"])
def test_approval_re_checks_the_stored_validation(synthetic_db, status, validation, match):
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH, status=status, validation=validation)

    with pytest.raises(ValueError, match=match):
        AIReviewWorker().approve_for_simulation(proposal_id, reviewed_by="pytest")

    assert _status(synthetic_db, proposal_id) == status


# --- live trading stays disabled ------------------------------------------------


def test_enabled_live_trading_fails_validation_and_blocks_approval(synthetic_db, monkeypatch):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    legacy_row = _proposal(synthetic_db, NEUTRAL_PATCH, status="validation_passed",
                           validation={"checks": {"live_trading_disabled": True}})
    monkeypatch.setattr(settings, "enable_live_trading", True)
    _forbid_comparison(monkeypatch)

    validation = AIReviewWorker().validate_proposal(proposal_id, _experiment())

    assert validation["status"] == "validation_failed"
    assert validation["checks"]["live_trading_disabled"] is False
    assert validation["live_trading_enabled"] is True
    assert "live_trading_enabled" in validation["failure_reasons"]
    with pytest.raises(ValueError, match="live trading is enabled"):
        AIReviewWorker().approve_for_simulation(legacy_row)


def test_api_validation_without_an_experiment_fails_closed_and_approval_is_refused(synthetic_db):
    _base_run(synthetic_db)
    proposal_id = _proposal(synthetic_db, NEUTRAL_PATCH)
    with TestClient(app) as client:
        response = client.post(f"/api/ai/review/proposals/{proposal_id}/validate")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "validation_failed"
        assert "experiment_not_predeclared" in body["failure_reasons"]
        assert body["live_trading_enabled"] is False

        declared = client.post(f"/api/ai/review/proposals/{proposal_id}/validate",
                               json={"experiment": _experiment()})
        assert declared.status_code == 200
        assert declared.json()["status"] == "diagnostic_only"

        approval = client.post(f"/api/ai/review/proposals/{proposal_id}/approve-for-simulation")
        assert approval.status_code == 400
        assert "not validation_passed" in approval.json()["detail"]
        assert client.post("/api/ai/review/proposals/999999/validate").status_code == 404

