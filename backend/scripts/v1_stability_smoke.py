from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def get_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url} is unreachable: {exc.reason}") from exc
    return json.loads(payload)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Read-only V1 stability smoke check.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    health = get_json(args.base_url, "/health", args.timeout)
    diagnostics = get_json(args.base_url, "/api/system/v1-stability", args.timeout)

    safety = diagnostics.get("safety") or {}
    failures: list[str] = []

    if health.get("status") != "ok":
        failures.append(f"health_status={health.get('status')!r}")
    if health.get("live_trading_enabled") is not False:
        failures.append("health_live_trading_enabled_not_false")
    if diagnostics.get("schema_version") != "v1_stability_diagnostics.v1":
        failures.append("unexpected_schema_version")
    if diagnostics.get("review_only") is not True:
        failures.append("diagnostics_review_only_not_true")
    if diagnostics.get("simulation_only") is not True:
        failures.append("diagnostics_simulation_only_not_true")
    if diagnostics.get("live_trading_enabled") is not False:
        failures.append("diagnostics_live_trading_enabled_not_false")
    if safety.get("live_trading_enabled") is not False:
        failures.append("safety_live_trading_enabled_not_false")
    if safety.get("broker_api_enabled") is not False:
        failures.append("safety_broker_api_enabled_not_false")
    if safety.get("credential_storage_enabled") is not False:
        failures.append("safety_credential_storage_enabled_not_false")
    if safety.get("real_order_execution_enabled") is not False:
        failures.append("safety_real_order_execution_enabled_not_false")

    data_coverage = diagnostics.get("data_coverage") or {}
    data_freshness = diagnostics.get("data_freshness") or {}
    refresh_preflight = data_freshness.get("daily_bar_refresh_preflight") or {}
    discovery_recovery = data_freshness.get("discovery_recovery") or {}
    backtest = diagnostics.get("latest_backtest") or {}
    risk_diagnostics = backtest.get("risk_rejection_diagnostics") or {}
    hard_blocks = risk_diagnostics.get("hard_block_summary") or []
    attention_items = diagnostics.get("attention_items") or []
    accepted_attention_items = diagnostics.get("accepted_attention_items") or []
    blocking_attention_items = diagnostics.get("blocking_attention_items") or []
    if not isinstance(accepted_attention_items, list):
        failures.append("accepted_attention_items_not_list")
        accepted_attention_items = []
    if not isinstance(blocking_attention_items, list):
        failures.append("blocking_attention_items_not_list")
        blocking_attention_items = []
    if set(accepted_attention_items) - set(attention_items):
        failures.append("accepted_attention_items_not_subset_of_attention")
    if set(blocking_attention_items) - set(attention_items):
        failures.append("blocking_attention_items_not_subset_of_attention")
    if set(accepted_attention_items) & set(blocking_attention_items):
        failures.append("accepted_and_blocking_attention_overlap")
    strategy_safety_review = diagnostics.get("strategy_safety_review") or {}
    release_gate = diagnostics.get("release_gate") or {}
    if release_gate.get("schema_version") != "v1_release_gate.v1":
        failures.append("unexpected_release_gate_schema_version")
    if set(release_gate.get("accepted_attention_items") or []) != set(accepted_attention_items):
        failures.append("release_gate_accepted_attention_mismatch")
    if set(release_gate.get("blocking_attention_items") or []) != set(blocking_attention_items):
        failures.append("release_gate_blocking_attention_mismatch")
    sim_cockpit = diagnostics.get("sim_cockpit") or {}
    summary = {
        "ok": not failures,
        "failures": failures,
        "status": diagnostics.get("status"),
        "attention_items": attention_items,
        "accepted_attention_items": accepted_attention_items,
        "blocking_attention_items": blocking_attention_items,
        "latest_trade_date": data_coverage.get("latest_trade_date"),
        "calendar_lag_days": data_coverage.get("calendar_lag_days"),
        "daily_bar_refresh_preflight_status": refresh_preflight.get("status"),
        "stale_candidate_count": refresh_preflight.get("stale_candidate_count"),
        "missing_candidate_count": refresh_preflight.get("missing_candidate_count"),
        "discovery_recovery_status": discovery_recovery.get("status"),
        "downstream_candidate_evidence_available": discovery_recovery.get("downstream_candidate_evidence_available"),
        "backtest_reasons": backtest.get("diagnostic_reasons") or [],
        "risk_diagnostic_status": risk_diagnostics.get("status"),
        "strategy_safety_review_status": strategy_safety_review.get("status"),
        "strategy_safety_next_action": strategy_safety_review.get("next_action"),
        "release_gate_status": release_gate.get("status"),
        "release_gate_next_action": release_gate.get("next_action"),
        "release_gate_external_blockers": release_gate.get("external_blockers") or [],
        "top_hard_block": hard_blocks[0] if hard_blocks else None,
        "sim_cockpit_status": sim_cockpit.get("status"),
        "simulation_actions_allowed": sim_cockpit.get("simulation_actions_allowed"),
        "live_trading_enabled": diagnostics.get("live_trading_enabled"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    if failures:
        print("V1 stability smoke check failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
