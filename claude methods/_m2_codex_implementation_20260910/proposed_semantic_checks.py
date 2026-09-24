"""Reviewable alternative checks, never imported by accepted staging gates.

This models the proposed calendar/auction-domain contract only. It cannot
grant source qualification, remove raw rows, change prices, or publish a DB.
"""
from decimal import Decimal
import json
from pathlib import Path
import sys
import review_pilot52_blockers_v3 as review


def covered_inventory(expected, observed, confirmed_suspensions):
    expected, observed, suspended = map(set, (expected, observed, confirmed_suspensions))
    return {"missing_unexplained": sorted(expected - observed - suspended),
            "extra_observed": sorted(observed - expected),
            "unexpected_suspensions": sorted(suspended - expected),
            "conflicting_traded_suspensions": sorted(observed & suspended),
            "partition_complete": not (expected - observed - suspended or observed - expected or suspended - expected or observed & suspended)}


def auction_residual_check(symbol, day, source, block, *, scope_verified=False):
    if (block.get("symbol"), block.get("date")) != (symbol, day):
        raise ValueError("block_trade_business_key_mismatch")
    volume, amount, low, high = (Decimal(str(source[k])) for k in ("volume", "amount", "low", "high"))
    block_volume, price = (Decimal(str(block[k])) for k in ("volume", "price"))
    if not all(n.is_finite() and n > 0 for n in (volume, amount, low, high, block_volume, price)) or low > high:
        raise ValueError("invalid_measures")
    residual_volume, residual_amount = volume - block_volume, amount - block_volume * price
    if residual_volume <= 0 or residual_amount <= 0:
        raise ValueError("block_trade_exceeds_totals")
    # Preserve the existing 2% envelope; no fitted tolerance or value replacement.
    lower, upper = low * Decimal("0.98") * residual_volume, high * Decimal("1.02") * residual_volume
    consistent = lower <= residual_amount <= upper
    return {"numerically_consistent": consistent,
            "status": "SCOPE_EVIDENCE_REQUIRED" if not scope_verified else "PASS" if consistent else "FAIL",
            "total_volume": str(volume), "total_amount": str(amount),
            "block_volume": str(block_volume), "block_amount": str(block_volume * price),
            "derived_auction_volume": str(residual_volume), "derived_auction_amount": str(residual_amount),
            "derived_auction_average": str(residual_amount / residual_volume),
            "source_values_modified": False, "eligibility_granted": False}


def run():
    old = review.run()
    audit = json.loads((review.HERE / "audit_recovered_pilot_52.json").read_bytes())
    observed = {(s["symbol"], key[1]) for s in audit["scopes"] for key in s["business_keys"]}
    missing = {(s["symbol"], day) for s in audit["scopes"] for day in s["missing_dates"]}
    # The separately pinned audit constructed expected dates from the frozen
    # calendar and listing date; it also verifies there are no extra dates.
    if audit["extra_key_count"] != 0:
        raise ValueError("unexpected_extra_dates")
    suspension = {(g["symbol"], g["date"]) for g in old["gap_ledger"] if g["evidence"]}
    coverage = covered_inventory(observed | missing, observed, suspension)
    raw = old["P4_failure"]["source_values"]
    source = {"volume": raw["transaction_volume"], "amount": raw["transaction_amount"], "low": raw["low"], "high": raw["high"]}
    numerical = auction_residual_check("BJ920006", "2023-12-04", source,
        {"symbol": "BJ920006", "date": "2023-12-04", "volume": 400000, "price": "9.25"})
    return {"schema": "m2.proposed_semantic_diagnostic.v1", "proposed_contract_only": True,
            "coverage": coverage, "observed_rows": len(observed), "confirmed_suspension_keys": len(suspension),
            "unchanged_frozen_expected_keys": len(observed | missing), "block_trade_diagnostic": numerical,
            "warmup_more_history_required": old["additional_mature_stock_warmup_shortfalls"],
            "frozen_acceptance": "FAIL", "staging_eligible": False, "M2_complete": False,
            "network_requests": 0, "database_connections": 0, "live_trading": False}


if __name__ == "__main__":
    destination = Path(sys.argv[1]).resolve()
    if not destination.is_relative_to(review.HERE) or destination.exists():
        raise SystemExit("new output inside current phase required")
    result = run()
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
