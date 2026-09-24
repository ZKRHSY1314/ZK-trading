"""Deterministic same-input A/B harness. Synthetic bars; proves engineering behaviour only."""
from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.backtest.ab_harness import (
    ManifestError,
    effective_costs,
    input_fingerprint,
    run_ab,
    validate_manifest,
)
from app.storage.sqlite_store import SQLiteStore

SYMBOLS = ["SH600201", "SH600202", "SH600203"]
DAYS = [f"2020-02-{day:02d}" for day in range(3, 15)]


def _database(tmp_path) -> Path:
    path = tmp_path / "ab-synthetic.sqlite3"
    store = SQLiteStore(path)
    store.init()
    rows = []
    for index, day in enumerate(DAYS):
        rows.append(("SH000300", day, 100 + index, 101 + index, 99 + index, 100 + index, 1e6, 1e10))
        for offset, symbol in enumerate(SYMBOLS):
            base = 10 + offset * 5 + index * 0.1 * (offset + 1)
            volume = 1e6 * (2.5 if (index + offset) % 4 == 0 else 1.0)
            rows.append((symbol, day, base, base * 1.03, base * 0.98, base * 1.01, volume, 1e9))
    with store.connect() as conn:
        conn.executemany(
            "INSERT INTO daily_bar_cache(symbol, trade_date, open, high, low, close, volume, amount, "
            "source, quality_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synthetic', 'ready')", rows)
    return path


def _config(min_volume_ratio: float) -> dict:
    return {
        "candidate_tiers": {"strong_min_score": 20, "watch_min_score": 10},
        "rules": [{"id": "dengzhan_forced_divergence", "name": "volume", "group": "strategy",
                   "enabled": True, "weight": 100, "hard_block": False,
                   "params": {"min_volume_ratio": min_volume_ratio}}],
        "exit_rules": {"stop_loss_pct": 6.0, "partial_take_profit_pct": 15.0,
                       "partial_take_profit_ratio": 0.5, "break_ma_window": 5,
                       "require_below_limit_up_avg": False, "max_holding_days": 3},
    }


def _manifest(**overrides) -> dict:
    manifest = {
        "schema_version": "backtest_ab_manifest.v1",
        "experiment_id": "synthetic-volume-threshold",
        "hypothesis": "Synthetic engineering check: a stricter volume threshold trades less.",
        "window": {"start_date": DAYS[0], "end_date": DAYS[-1]},
        "universe": list(SYMBOLS),
        "benchmark_symbol": "SH000300",
        "capital": {"initial_cash": 1_000_000, "max_positions": 2, "per_symbol_cap": 0.3},
        "execution": {"fill_policy": "pre_open_causal", "allow_projected_fundamentals": False},
        "costs": effective_costs(),
        "arms": {"A": {"config": _config(1.0)}, "B": {"config": _config(2.0)}},
        "primary_metric": "total_return",
        "controls": ["a_a_reproducibility", "input_fingerprint_unchanged"],
        "evidence_class": "engineering_synthetic",
    }
    manifest.update(overrides)
    return manifest


def _run_counts(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM historical_backtest_runs").fetchone()[0]


def test_same_manifest_and_inputs_reproduce_the_same_report(tmp_path):
    database = _database(tmp_path)
    first = run_ab(_manifest(), database_path=database)
    second = run_ab(_manifest(), database_path=database)
    assert first == second
    assert first["status"] == "completed"
    assert first["controls"] == {"a_a_reproducibility": True, "input_fingerprint_unchanged": True}
    # The arms really differ, so the comparison is not vacuous.
    assert first["arms"]["A"]["result_sha256"] != first["arms"]["B"]["result_sha256"]
    assert first["arms"]["A"]["metrics"]["entry_signal_count"] > first["arms"]["B"]["metrics"]["entry_signal_count"]
    for arm in first["arms"].values():
        assert arm["execution_contract"]["fill_policy"] == "pre_open_causal"
        assert arm["fundamental_point_in_time"] is True


def test_a_result_is_never_a_qualified_strategy_claim_and_nothing_is_persisted(tmp_path):
    database = _database(tmp_path)
    before = _run_counts(database)
    report = run_ab(_manifest(), database_path=database)
    assert _run_counts(database) == before
    assert report["qualified_for_strategy_claim"] is False
    assert "daily_bars_cannot_prove_historical_auction_fills" in report["unqualified_reasons"]
    assert report["live_trading_enabled"] is False


def test_identical_arms_have_zero_difference_and_missing_metrics_stay_missing(tmp_path):
    database = _database(tmp_path)
    same = _manifest(arms={"A": {"config": _config(1.0)}, "B": {"config": _config(1.0)}})
    report = run_ab(same, database_path=database)
    assert report["arms"]["A"]["result_sha256"] == report["arms"]["B"]["result_sha256"]
    assert report["primary_difference_b_minus_a"] == 0.0
    # A configuration that never signals has no return: the difference is None, not 0.
    silent = _manifest(arms={"A": {"config": _config(1.0)}, "B": {"config": _config(50.0)}})
    silent_report = run_ab(silent, database_path=database)
    assert silent_report["arms"]["B"]["status"] == "no_signal"
    assert silent_report["arms"]["B"]["metrics"]["total_return"] is None
    assert silent_report["primary_difference_b_minus_a"] is None
    assert silent_report["primary_difference_unavailable_reason"] == "total_return_unavailable_in_at_least_one_arm"


def test_pinned_input_fingerprint_rejects_changed_data(tmp_path):
    database = _database(tmp_path)
    pinned = input_fingerprint(SQLiteStore(database), _manifest())["sha256"]
    assert run_ab(_manifest(expected_input_sha256=pinned), database_path=database)["status"] == "completed"
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE daily_bar_cache SET close = close * 1.01 WHERE symbol = ? AND trade_date = ?",
                     (SYMBOLS[0], DAYS[4]))
    with pytest.raises(ManifestError, match="input fingerprint"):
        run_ab(_manifest(expected_input_sha256=pinned), database_path=database)


@pytest.mark.parametrize("mutation,match", [
    (lambda m: m.update(universe=[]), "universe"),
    (lambda m: m["execution"].update(fill_policy="daily_bar_retrospective"), "fill_policy"),
    (lambda m: m["execution"].pop("allow_projected_fundamentals"), "projected"),
    (lambda m: m["costs"].update(commission_rate=0.0), "costs"),
    (lambda m: m["arms"].update(C={"config": {}}), "arms"),
    (lambda m: m.update(primary_metric="sharpe_after_the_fact"), "primary_metric"),
    (lambda m: m.update(controls=["a_a_reproducibility"]), "controls"),
    (lambda m: m.update(evidence_class="qualified_historical"), "evidence_class"),
    (lambda m: m.update(unexpected_knob=1), "unexpected"),
    (lambda m: m["window"].update(start_date="2021-01-01"), "start_date is after"),
])
def test_manifest_must_be_fully_predeclared(mutation, match):
    manifest = copy.deepcopy(_manifest())
    mutation(manifest)
    with pytest.raises(ManifestError, match=match):
        validate_manifest(manifest)


def test_cli_runs_on_a_copy_and_never_touches_the_source(tmp_path):
    database = _database(tmp_path)
    before = database.read_bytes()
    manifest_path = tmp_path / "experiment.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts/run_backtest_ab.py"
    result = subprocess.run([sys.executable, "-B", str(script), "--manifest", str(manifest_path),
                             "--database", str(database), "--project-root", str(tmp_path),
                             "--label", "synthetic"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert database.read_bytes() == before
    report = json.loads((tmp_path / "logs/backtest_ab_synthetic.json").read_text(encoding="utf-8"))
    assert report["status"] == "completed" and report["qualified_for_strategy_claim"] is False
    bad = _manifest(universe=[])
    manifest_path.write_text(json.dumps(bad), encoding="utf-8")
    refused = subprocess.run([sys.executable, "-B", str(script), "--manifest", str(manifest_path),
                              "--database", str(database)], capture_output=True, text=True, timeout=120)
    assert refused.returncode == 2
    assert json.loads(refused.stdout)["status"] == "refused"
