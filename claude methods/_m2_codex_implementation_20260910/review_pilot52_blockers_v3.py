"""Add observed exchange evidence; retain frozen failures and raw source values."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import review_pilot52_blockers_v2 as previous

HERE = Path(__file__).resolve().parent
OBSERVATION = "gap_evidence/exchange_dom_observations_20260910.json"
OBSERVATION_PIN = "babcf2122da863f9f4add210b4e4e74ea2255d9710ffc8f5e36a010336d1f530"
PREVIOUS_PIN = "c07306ce2e5f801e4bdd7e8b8bb1f43a619475241b3ddd3f2fa4329236e3783c"


def run():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_PIN:
        raise ValueError("previous_review_changed")
    if hashlib.sha256((HERE / OBSERVATION).read_bytes()).hexdigest() != OBSERVATION_PIN:
        raise ValueError("exchange_observation_changed")
    observations = json.loads((HERE / OBSERVATION).read_bytes())
    indexed = {entry["id"]: entry for entry in observations["observations"]}
    suspension = indexed["sse_600110_20221020"]["rows"][0]
    if (suspension["security_code"], suspension["suspension_start"], suspension["suspension_end"], suspension["duration"]) != ("600110", "2022-10-20", "2022-10-20", "全天"):
        raise ValueError("suspension_record_mismatch")
    result = previous.run()
    if result["unresolved_keys"] != [{"symbol": "SH600110", "date": "2022-10-20"}]:
        raise ValueError("unexpected_previous_unresolved_keys")
    for gap in result["gap_ledger"]:
        if (gap["symbol"], gap["date"]) == ("SH600110", "2022-10-20"):
            gap["status"] = "exchange_confirmed_suspension"
            gap["evidence"].append({"source": OBSERVATION, "sha256": OBSERVATION_PIN, "observation_id": "sse_600110_20221020", "raw_http_response_retained": False})
    result["unresolved_keys"] = []
    result["missing_status_counts"] = dict(Counter(gap["status"] for gap in result["gap_ledger"]))
    result.pop("remaining_lead")
    block = indexed["bse_837006_20231204"]["rows"][0]
    if (block["date"], block["code"]) != ("2023-12-04", "837006"):
        raise ValueError("block_trade_record_mismatch")
    volume = Decimal(block["volume_shares"])
    amount = volume * Decimal(block["price_CNY"])
    source = result["P4_failure"]["source_values"]
    residual_volume = Decimal(source["transaction_volume"]) - volume
    residual_amount = Decimal(source["transaction_amount"]) - amount
    if residual_volume <= 0 or residual_amount <= 0:
        raise ValueError("block_trade_exceeds_vendor_totals")
    result["P4_failure"]["block_trade_lead"] = {
        "status": "exchange_trade_observed_vendor_amount_scope_pending",
        "observation_source": OBSERVATION, "sha256": OBSERVATION_PIN,
        "observation_id": "bse_837006_20231204",
        "exchange_record_obtained": True, "raw_http_response_retained": False,
        "reported_shares": int(volume), "derived_amount_CNY": str(amount),
        "reported_price_CNY": block["price_CNY"],
        "hypothetical_non_block_ratio": str(residual_amount / residual_volume),
        "hypothesis_within_auction_price_range": Decimal(source["low"]) <= residual_amount / residual_volume <= Decimal(source["high"]),
        "exchange_volume_includes_block_trades": True,
        "source_total_scope_verified": False,
        "correction_applied": False, "eligibility_granted": False,
    }
    result["schema"] = "m2.ths.pilot52_blocker_review.v3"
    result["inputs"] = {**result["inputs"], OBSERVATION: OBSERVATION_PIN, "review_pilot52_blockers_v2.py": PREVIOUS_PIN}
    result["producer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


if __name__ == "__main__":
    destination = Path(sys.argv[1]).resolve()
    if not destination.is_relative_to(HERE) or destination.exists():
        raise SystemExit("new output inside current phase required")
    result = run()
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({key: result[key] for key in ("actual_rows", "missing_count", "missing_status_counts", "unresolved_keys", "staging_eligible")}, ensure_ascii=False))
