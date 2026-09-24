"""Extend the retained first review with explicit additional issuer facts only."""
import hashlib
import json
from pathlib import Path
import sys
import review_pilot52_blockers as base

HERE = Path(__file__).resolve().parent
FACTS_PIN = "3da963f14508cfc066ab64fdbb9298cad7e064b20cfc1260d362b9af6b10ab45"
BASE_PIN = "a47d4526949a241ff477abe033bffc1b712c8d2209949e63cc15055c467a676a"


def contains(fact, day):
    if day < fact["start"]:
        return False
    if fact.get("resume") is not None:
        return day < fact["resume"]
    through = fact.get("confirmed_suspended_through")
    return through is not None and day <= through


def run():
    path = HERE / "reviewed_suspension_facts_v2.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != FACTS_PIN or hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest() != BASE_PIN:
        raise ValueError("reviewed_fact_or_base_rule_changed")
    facts = json.loads(path.read_bytes())["facts"]
    pins = dict(base.PINS)
    pins.update({"reviewed_suspension_facts_v2.json": FACTS_PIN, "review_pilot52_blockers.py": BASE_PIN})
    for fact in facts:
        for source in fact["sources"]:
            if hashlib.sha256((HERE / source["path"]).read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError("reviewed_issuer_source_changed")
            pins[source["path"]] = source["sha256"]
    original_classify, original_pins = base.classify, base.PINS

    def classify(symbol, day):
        result = original_classify(symbol, day)
        matches = [fact for fact in facts if fact["symbol"] == symbol and contains(fact, day)]
        if matches:
            result["status"] = "issuer_confirmed_suspension"
            result["evidence"].extend(matches)
        return result

    try:
        base.classify, base.PINS = classify, pins
        result = base.run()
    finally:
        base.classify, base.PINS = original_classify, original_pins
    result["schema"] = "m2.ths.pilot52_blocker_review.v2"
    result["producer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["strict_pit"] = False
    result["unresolved_keys"] = [{"symbol": g["symbol"], "date": g["date"]} for g in result["gap_ledger"] if not g["evidence"]]
    result["remaining_lead"] = {
        "symbol": "SH600110", "date": "2022-10-20",
        "status": "secondary_suspension_lead_only",
        "url": "https://q.stock.sohu.com/cn/600110/bw_63.shtml",
        "reported_reason": "Important matter not announced; whole-day suspension preceding the issuer's restructuring suspension.",
        "exchange_record_obtained": False, "classified_as_verified": False,
    }
    return result


if __name__ == "__main__":
    destination = Path(sys.argv[1]).resolve()
    if not destination.is_relative_to(HERE) or destination.exists():
        raise SystemExit("new output inside current phase required")
    result = run()
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: result[k] for k in ("actual_rows", "missing_count", "missing_status_counts", "unresolved_keys", "staging_eligible")}, ensure_ascii=False))
