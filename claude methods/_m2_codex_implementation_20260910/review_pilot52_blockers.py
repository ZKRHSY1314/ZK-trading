"""Offline, pinned gap classification and P4 diagnosis; grants no eligibility.

Only explicitly reviewed issuer suspension intervals classify a missing key.
Unexplained dates are never inferred to be suspensions from missing vendor bars.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PINS = {
    "audit_recovered_pilot_52.json": "37d780872ede4a587d64dcf31e6acfe65e4dc64ad019c1f5841905e581222f2f",
    "qualification_pilot52.json": "e8235ece99314b690d70431bb38e81d10f7f6b207e97171097a9240f6c10d8df",
    "gap_evidence/issuer_688115_20240925.html": "aabae31978590bbd90ba6fb248da56e6da03b7402b9e736674b87624371aff92",
    "gap_evidence/issuer_002656_20250307.pdf": "068971f4a1018fb13f773ec69577341011dac2ae6e6d9c4667c77654275ce1bf",
    "remaining_capture_after_login/response_15.bin": "380199de508b7dea8d5d66f35801f187925c6a3c117ccb41dcab3db1e50f1ad6",
}
FACTS = [
    {"symbol": "SH688115", "start": "2024-09-09", "resume": "2024-09-25",
     "source": "gap_evidence/issuer_688115_20240925.html",
     "url": "https://paper.cnstock.com/html/2024-09/25/content_1971652.htm",
     "location": "Issuer announcements 2024-052 and 2024-054; start and resumption paragraphs",
     "review": "Issuer-authored announcement on its designated disclosure newspaper; exact start and resumption read."},
    {"symbol": "SZ002656", "start": "2024-11-11", "resume": "2025-01-14",
     "source": "gap_evidence/issuer_002656_20250307.pdf",
     "url": "https://static.cninfo.com.cn/finalpage/2025-03-07/1222733694.PDF",
     "location": "Announcement 2025-045 page 3 section 2(a)",
     "review": "All five pages read; complete pages 2 and 3 rendered and visually checked."},
    {"symbol": "SZ002656", "start": "2025-03-07", "resume": "2025-03-10",
     "source": "gap_evidence/issuer_002656_20250307.pdf",
     "url": "https://static.cninfo.com.cn/finalpage/2025-03-07/1222733694.PDF",
     "location": "Announcement 2025-045 page 2 special notice and section 1",
     "review": "Explicit single-session suspension; same visual review as the preceding fact."},
]


def classify(symbol, day, facts=FACTS):
    matches = [fact for fact in facts if fact["symbol"] == symbol and fact["start"] <= day < fact["resume"]]
    return {"symbol": symbol, "date": day,
            "window": "research" if day >= "2023-09-04" else "warmup",
            "status": "issuer_confirmed_suspension" if matches else "unresolved_missing_bar",
            "evidence": [{**fact, "sha256": PINS[fact["source"]]} for fact in matches],
            "frozen_gate_exemption": False}


def run():
    for name, expected in PINS.items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError("reviewed_input_changed:" + name)
    audit = json.loads((HERE / "audit_recovered_pilot_52.json").read_bytes())
    bundle = json.loads((HERE / "qualification_pilot52.json").read_bytes())
    gaps = [classify(scope["symbol"], day) for scope in audit["scopes"] for day in scope["missing_dates"]]
    if len(gaps) != 298 or len({(g["symbol"], g["date"]) for g in gaps}) != 298:
        raise ValueError("frozen_missing_inventory_changed")
    # Contradictory source bars during an asserted full-day suspension invalidate
    # the classification; publication dates alone never define an interval.
    for scope in audit["scopes"]:
        for key in scope["business_keys"]:
            if classify(scope["symbol"], key[1])["evidence"]:
                raise ValueError("source_bar_contradicts_reviewed_suspension")
    raw = json.loads((HERE / "remaining_capture_after_login/response_15.bin").read_bytes(), parse_float=Decimal)
    points = raw["data"]["items"][0]["points"]
    rows = [(i, p["values"]) for i, p in enumerate(points) if p["values"]["date_time"] == 20231204]
    if len(rows) != 1:
        raise ValueError("P4_row_not_unique")
    index, row = rows[0]
    amount, volume = Decimal(row["transaction_amount"]), Decimal(row["transaction_volume"])
    low, high = Decimal(row["low"]), Decimal(row["high"])
    ratio = amount / volume
    if low * Decimal("0.98") <= ratio <= high * Decimal("1.02"):
        raise ValueError("reviewed_P4_failure_changed")
    additional_warmup = [
        {"symbol": s["symbol"], "expected": s["expected_windows"]["warmup"],
         "observed": s["candidate_windows"]["warmup"]}
        for s in audit["scopes"]
        if s["expected_windows"]["warmup"] == 250 and s["candidate_windows"]["warmup"] < 250]
    if len(additional_warmup) != 3:
        raise ValueError("additional_warmup_inventory_changed")
    return {
        "schema": "m2.ths.pilot52_blocker_review.v1", "at_utc": datetime.now(timezone.utc).isoformat(),
        "source_requests": 0, "database_connections": 0, "production_modified": False,
        "live_trading": False, "staging_eligible": False, "M2_complete": False,
        "scope_count": 52, "actual_rows": audit["validated_rows"], "frozen_expected_rows": audit["expected_rows"],
        "missing_count": len(gaps), "missing_status_counts": dict(Counter(g["status"] for g in gaps)),
        "gap_ledger": gaps, "additional_mature_stock_warmup_shortfalls": additional_warmup,
        "qualifications": {field: dict(Counter(s[field] for s in bundle["scopes"])) for field in
                           ("vendor_basis_status", "identity_status", "unit_status")},
        "P4_failure": {"symbol": "BJ920006", "date": "2023-12-04", "point_index": index,
            "raw_sha256": PINS["remaining_capture_after_login/response_15.bin"],
            "source_values": {k: str(row[k]) for k in ("open", "high", "low", "latest", "transaction_volume", "transaction_amount")},
            "amount_per_share": str(ratio), "frozen_lower_bound": str(low * Decimal("0.98")),
            "frozen_upper_bound": str(high * Decimal("1.02")), "frozen_P4": "FAIL",
            "block_trade_lead": {"status": "unverified_secondary_lead_only",
                "url": "https://q.stock.sohu.com/cn/837006/dzjy.shtml", "reported_shares": 400000,
                "reported_amount_CNY": 3700000, "reported_price_CNY": "9.25",
                "hypothetical_non_block_ratio": str((amount - Decimal(3700000)) / (volume - Decimal(400000))),
                "exchange_record_obtained": False, "source_total_scope_verified": False,
                "correction_applied": False, "eligibility_granted": False}},
        "decision": "Research and warmup acceptance remain FAIL under the unchanged M1 contract. Classification is diagnostic and does not remove required keys or relax P4.",
        "inputs": PINS, "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    destination = Path(sys.argv[1]).resolve()
    if not destination.is_relative_to(HERE) or destination.exists():
        raise SystemExit("new output inside current phase required")
    result = run()
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: result[k] for k in ("actual_rows", "missing_count", "missing_status_counts", "additional_mature_stock_warmup_shortfalls", "staging_eligible")}, ensure_ascii=False))
