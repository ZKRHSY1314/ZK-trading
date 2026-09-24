"""Deterministic same-input A/B comparison of two strategy configurations.

A run is defined entirely by a predeclared manifest: a fixed universe and
window, fixed capital, the execution contract, the cost assumptions that must be
in effect, the two arms (rule configurations), the primary metric and the
controls. Both arms read the same fingerprinted inputs under the same costs and
the same causal fill policy; nothing but the rule configuration differs.

What a result is - and is not
-----------------------------
* It is an engineering comparison of two configurations over the given rows.
* It is never qualified strategy evidence. Daily bars cannot prove historical
  auction fills, fees are configured rates, capacity is a participation
  assumption, the universe is whatever rows exist (survivorship unknown) and
  fundamentals may not be point-in-time. ``qualified_for_strategy_claim`` is
  always False and the reasons say why.
* Missing metrics stay missing: a difference is None when either side is None.
* Controls are checked, not assumed: an A/A rerun must reproduce arm A exactly,
  and the input fingerprint must be unchanged after both arms ran. A failed
  control makes the whole result ``invalid``.

Nothing is persisted: the engine runs with ``persist=False``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.backtest.engine import BacktestEngine
from app.backtest.execution import BacktestExecutionModel
from app.backtest.execution_contract import FILL_POLICY_PRE_OPEN
from app.config import settings
from app.storage.sqlite_store import SQLiteStore

MANIFEST_SCHEMA = "backtest_ab_manifest.v1"
REPORT_SCHEMA = "backtest_ab_report.v1"
REGIME_INDEX_SYMBOLS = ("SH000001", "SH000300")
PRIMARY_METRICS = ("total_return", "excess_return", "max_drawdown", "win_rate", "closed_trade_count")
CONTROLS = ("a_a_reproducibility", "input_fingerprint_unchanged")
EVIDENCE_CLASSES = ("engineering_synthetic", "development_diagnostic")
REPORTED_METRICS = (
    "total_return", "excess_return", "max_drawdown", "win_rate", "trade_count",
    "closed_trade_count", "entry_signal_count", "entry_attempt_count", "entry_fill_count",
    "rejected_execution_count", "partial_fill_count", "open_position_count", "order_intent_count",
)
_REQUIRED_KEYS = {
    "schema_version", "experiment_id", "hypothesis", "window", "universe", "benchmark_symbol",
    "capital", "execution", "costs", "arms", "primary_metric", "controls", "evidence_class",
}


class ManifestError(ValueError):
    """The manifest is not a valid, fully predeclared experiment."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def effective_costs() -> dict[str, float]:
    """The cost assumptions the engine will actually apply in this process."""

    model = BacktestExecutionModel()
    return {
        "commission_rate": float(settings.commission_rate),
        "stamp_tax_rate": float(settings.stamp_tax_rate),
        "slippage_rate": float(settings.slippage_rate),
        "min_order_lot": int(settings.min_order_lot),
        "max_participation_rate": float(model.max_participation_rate),
    }


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be an object")
    missing = sorted(_REQUIRED_KEYS - set(manifest))
    extra = sorted(set(manifest) - _REQUIRED_KEYS - {"expected_input_sha256", "notes"})
    if missing or extra:
        raise ManifestError(f"manifest keys: missing={missing} unexpected={extra}")
    if manifest["schema_version"] != MANIFEST_SCHEMA:
        raise ManifestError(f"schema_version must be {MANIFEST_SCHEMA}")
    universe = manifest["universe"]
    if not isinstance(universe, list) or not universe or len(set(universe)) != len(universe):
        # An empty list makes the engine load every cached symbol - an input
        # set nobody declared. The universe must be explicit and fixed.
        raise ManifestError("universe must be a non-empty list of distinct symbols")
    window = manifest["window"]
    if not isinstance(window, dict) or not window.get("start_date") or not window.get("end_date"):
        raise ManifestError("window needs start_date and end_date")
    if str(window["start_date"]) > str(window["end_date"]):
        raise ManifestError("window start_date is after end_date")
    capital = manifest["capital"]
    for key in ("initial_cash", "max_positions", "per_symbol_cap"):
        if key not in capital:
            raise ManifestError(f"capital.{key} is required")
    execution = manifest["execution"]
    if execution.get("fill_policy") != FILL_POLICY_PRE_OPEN:
        # Comparing returns under retrospective daily-bar fills would let later
        # session prices decide which arm "traded better".
        raise ManifestError(f"execution.fill_policy must be {FILL_POLICY_PRE_OPEN}")
    if execution.get("allow_projected_fundamentals") is not False:
        raise ManifestError("execution.allow_projected_fundamentals must be explicitly false")
    arms = manifest["arms"]
    if set(arms) != {"A", "B"} or not all(isinstance(arms[k].get("config"), dict) for k in arms):
        raise ManifestError("arms must be exactly A and B, each with a rule config")
    if manifest["primary_metric"] not in PRIMARY_METRICS:
        raise ManifestError(f"primary_metric must be one of {PRIMARY_METRICS}")
    if sorted(manifest["controls"]) != sorted(CONTROLS):
        raise ManifestError(f"controls must be exactly {sorted(CONTROLS)}")
    if manifest["evidence_class"] not in EVIDENCE_CLASSES:
        raise ManifestError(f"evidence_class must be one of {EVIDENCE_CLASSES}")
    declared = manifest["costs"]
    actual = effective_costs()
    if {key: declared.get(key) for key in actual} != actual:
        raise ManifestError(f"declared costs {declared} differ from effective costs {actual}")
    return manifest


def input_fingerprint(store: SQLiteStore, manifest: dict[str, Any]) -> dict[str, Any]:
    """Hash of every row the engine can read for this manifest, up to end_date."""

    symbols = sorted(
        {variant for symbol in [*manifest["universe"], manifest["benchmark_symbol"], *REGIME_INDEX_SYMBOLS]
         for variant in (symbol, symbol.upper(), symbol.lower())}
    )
    placeholders = ",".join("?" for _ in symbols)
    bars = store.fetch_all(
        f"""
        SELECT symbol, trade_date, open, high, low, close, volume, amount, quality_status
        FROM daily_bar_cache
        WHERE symbol IN ({placeholders}) AND trade_date <= ?
        ORDER BY symbol, trade_date, quality_status
        """,
        (*symbols, manifest["window"]["end_date"]),
    )
    fundamentals = store.fetch_all(
        f"SELECT * FROM symbol_fundamental_snapshot WHERE symbol IN ({placeholders}) "
        "ORDER BY symbol, as_of, source",
        tuple(symbols),
    )
    return {
        "sha256": sha256_json({"bars": bars, "fundamentals": fundamentals}),
        "bar_rows": len(bars),
        "fundamental_rows": len(fundamentals),
        "last_trade_date": max((row["trade_date"] for row in bars), default=None),
    }


@contextmanager
def _database(path: Path) -> Iterator[SQLiteStore]:
    """Point the engine (which reads settings) at ``path`` for the duration."""

    previous = settings.database_path
    settings.database_path = Path(path)
    try:
        yield SQLiteStore(path)
    finally:
        settings.database_path = previous


def _run_arm(manifest: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    capital = manifest["capital"]
    result = BacktestEngine(config=copy.deepcopy(config)).run(
        start_date=manifest["window"]["start_date"],
        end_date=manifest["window"]["end_date"],
        symbols=list(manifest["universe"]),
        initial_cash=float(capital["initial_cash"]),
        max_positions=int(capital["max_positions"]),
        per_symbol_cap=float(capital["per_symbol_cap"]),
        benchmark_symbol=manifest["benchmark_symbol"],
        persist=False,
        allow_projected_fundamentals=False,
        fill_policy=manifest["execution"]["fill_policy"],
        include_intents=True,
    )
    metrics = result["metrics"]
    return {
        "status": result["status"],
        "metrics": {key: metrics.get(key) for key in REPORTED_METRICS},
        "execution_contract": metrics.get("execution_contract"),
        "fundamental_point_in_time": metrics.get("fundamental_point_in_time"),
        "execution_warning_count": len(result["execution_warnings"]),
        # Identity of everything the arm decided and filled, for reproducibility.
        "result_sha256": sha256_json(
            {"status": result["status"], "metrics": metrics, "benchmark": result["benchmark"],
             "warnings": result["execution_warnings"], "intents": result["order_intents"]}
        ),
    }


def run_ab(manifest: dict[str, Any], *, database_path: str | Path) -> dict[str, Any]:
    validate_manifest(manifest)
    manifest_sha256 = sha256_json(manifest)
    with _database(Path(database_path)) as store:
        before = input_fingerprint(store, manifest)
        expected = manifest.get("expected_input_sha256")
        if expected is not None and expected != before["sha256"]:
            raise ManifestError(
                f"input fingerprint {before['sha256']} differs from the manifest's {expected}"
            )
        arm_a = _run_arm(manifest, manifest["arms"]["A"]["config"])
        arm_b = _run_arm(manifest, manifest["arms"]["B"]["config"])
        arm_a_rerun = _run_arm(manifest, manifest["arms"]["A"]["config"])
        after = input_fingerprint(store, manifest)

    controls = {
        "a_a_reproducibility": arm_a["result_sha256"] == arm_a_rerun["result_sha256"],
        "input_fingerprint_unchanged": before["sha256"] == after["sha256"],
    }
    primary = manifest["primary_metric"]
    a_value = arm_a["metrics"].get(primary)
    b_value = arm_b["metrics"].get(primary)
    difference = None if a_value is None or b_value is None else round(float(b_value) - float(a_value), 10)
    valid = all(controls.values())
    return {
        "schema_version": REPORT_SCHEMA,
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": manifest_sha256,
        "input": before,
        "status": "completed" if valid else "invalid",
        "controls": controls,
        "arms": {"A": arm_a, "B": arm_b},
        "primary_metric": primary,
        "primary_difference_b_minus_a": difference,
        "primary_difference_unavailable_reason": (
            None if difference is not None else f"{primary}_unavailable_in_at_least_one_arm"
        ),
        "evidence_class": manifest["evidence_class"],
        "qualified_for_strategy_claim": False,
        "unqualified_reasons": [
            "daily_bars_cannot_prove_historical_auction_fills",
            "fees_are_configured_rates_not_effective_dated_tariffs",
            "capacity_is_a_participation_assumption",
            "universe_membership_and_survivorship_not_point_in_time",
            "price_limits_use_inferred_board_threshold_st_unknown",
            f"evidence_class_{manifest['evidence_class']}",
        ],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }
