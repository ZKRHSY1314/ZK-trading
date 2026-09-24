"""Approved real-session contract: replay retained captures, never fetch or open DBs.

Expected keys come from the frozen calendar/listings and reviewed suspension facts,
not from observed dates. V1 files and V1 verdicts are inputs, never rewritten.
"""
from collections import Counter
from decimal import Decimal
from datetime import datetime
import csv
import importlib.util
import json
from pathlib import Path
import sys

import staging as old
import run_actual_staging as guard
import review_pilot52_blockers_v3 as gap_review
import qualification_pilot_rules as numeric

HERE = Path(__file__).resolve().parent
EXTEND = ("SZ002656", "SH600110", "SH600226")
EARLY = "2022-05-01"
PDF = "gap_evidence/bse_trading_explanation_browser_20211119.pdf"
PINS = {
    "qualification_pilot52.json": "e8235ece99314b690d70431bb38e81d10f7f6b207e97171097a9240f6c10d8df",
    "audit_recovered_pilot_52.json": "37d780872ede4a587d64dcf31e6acfe65e4dc64ad019c1f5841905e581222f2f",
    "pilot52_blocker_review_v3.json": "58214acbb4148d95ab572d1d0ecfd6833817bb5ce5c49a3572cf598ba24138a8",
    "acceptance_v2_authority.json": "4214896dd68cddabcc3767a5b3711e64e1f2dfd8609e940e6a3918198a10c8eb",
    "M2_ACCEPTANCE_REVISION_PROPOSAL.md": "939357d0e44428bc1f7f074e1edc60cb762b6d80fc4f100f411ac2c2849a35c1",
    PDF: "faa129e2c007361a854b18fd119a7e0814a891875fdcd843a3a1569fbafc0c9d",
    "staging.py": "ab976f630c235f5bd38bb9ab84730998eda662a3b6910c8f9bc131ce5b91f69c",
    "run_actual_staging.py": "d3a530e4dfbb9fd04f534ccbc58ea7eded738359ffcdd213fe34e7650b8d2a02",
}
SHORT = {s: 0 for s in ("BJ920002", "BJ920003", "BJ920005", "BJ920007", "BJ920519",
    "BJ920627", "SH603075", "SH688549", "SH688702", "SZ301251", "SZ301507", "SZ301529")}
SHORT.update(BJ920001=167, BJ920006=75)
require, sha, read, value_sha = old._require, old._sha, guard.read_json, old._hash_value


def pin_file(pins, path, expected=None):
    path = Path(path).resolve()
    old._safe_existing_chain(path)
    actual = sha(path)
    require(expected is None or actual == expected, "v2_input_changed:" + path.name)
    require(str(path) not in pins or pins[str(path)] == actual, "v2_conflicting_pin")
    pins[str(path)] = actual
    return actual


def native(parser, symbol):
    if symbol in old.BENCHMARKS:
        host, code = old.BENCHMARKS[symbol]
        return parser.SecuritySpec.benchmark(symbol, host_full_code=host,
            response_full_code=code, mapping_evidence="frozen_official_index_mapping")
    if symbol == "SH600289":
        evidence = "5ad4d502d552933d4f20f54abfa1c7b17b01ea19790bc42a34a56ee80304b1d0"
        require(sha(HERE / "identity_search_600289/response.bin") == evidence, "risk_board_mapping_changed")
        return parser.SecuritySpec.stock(symbol, host_full_code="USHT600289", mapping_evidence=evidence)
    return parser.SecuritySpec.stock(symbol)


def capture(pins, parser, symbol, directory, number, entrypoint, start, end):
    directory = HERE / directory
    manifest = read(directory / "producer_pins.json")
    for name, expected in manifest.items():
        pin_file(pins, name, expected)
    collector = pin_file(pins, HERE / entrypoint)
    require(manifest.get(str((HERE / entrypoint).resolve())) == collector, "collector_not_bound")
    for name in ("plan.json", "producer_pins.json", "summary.json", f"completed_{number}.json",
                 f"preflight_{number}.json", f"response_{number}.bin"):
        pin_file(pins, directory / name)
    receipt_path = directory / f"completed_{number}.json"
    receipt = read(receipt_path)
    job = receipt["job"]
    require(job in read(directory / "plan.json")["jobs"], "job_not_in_retained_plan")
    require(job["symbol"] == symbol and job["id"] == number, "capture_business_scope_mismatch")
    require(receipt["http_status"] == 200 and receipt.get("stop_reason") is None, "capture_not_successful")
    spec = native(parser, symbol)
    request = parser.build_history_request(spec, start, end)
    request["security"] = {"hostFullCode": spec.host_full_code}
    actual = job["payload"]
    require(set(actual) == set(request), "request_field_inventory_changed")
    for field, expected in request.items():
        if field in ("startTimeUtc", "endTimeUtc"):
            require(old._observed(actual[field]) == old._observed(expected), "capture_window_changed")
        else:
            require(type(actual[field]) is type(expected) and actual[field] == expected, "capture_request_changed")
    require(job["host_full_code"] == spec.host_full_code, "capture_host_identity_changed")
    request_file = directory / f"request_{number}.json"
    if request_file.exists():
        pin_file(pins, request_file)
        require(read(request_file) == actual and receipt["request_sha256"] == sha(request_file), "request_receipt_mismatch")
    raw_path = directory / f"response_{number}.bin"
    require(receipt["raw_sha256"] == sha(raw_path), "capture_raw_changed")
    if "raw_bytes" in receipt:
        require(receipt["raw_bytes"] == raw_path.stat().st_size, "capture_size_changed")
    preflight = read(directory / f"preflight_{number}.json")
    require(preflight["passed"] is True and preflight["endpoint_identity"]["passed"] is True and
            preflight["host_process"]["adapter_sha256"] == guard.PLUGIN_SHA, "capture_endpoint_not_verified")
    observed = old._observed(receipt["observed_at"])
    require(old._observed(receipt["reserved_at"]) <= observed, "capture_time_order_invalid")
    decoded = parser.parse_history_response(raw_path.read_bytes(), spec, start, end)
    require(receipt.get("source_security", decoded["response_identity"]) == decoded["response_identity"], "source_identity_disagreement")
    capture_ref = dict(raw_sha256=sha(raw_path), request_sha256=value_sha(actual), producer_sha256=collector,
        parser_sha256=sha(old.PARSER), capture_receipt_sha256=sha(receipt_path),
        capture_producer_manifest_sha256=sha(directory / "producer_pins.json"), observed_at=observed)
    diagnostics = {d["row_index"]: d["code"] for d in decoded["name_diagnostics"]}
    records = []
    for i, row in enumerate(decoded["rows"]):
        old._observed(observed, row["date"])
        records.append(dict(symbol=symbol, trade_date=row["date"], source=old.SOURCE,
            **{f: row[f] for f in old.NUMBER_FIELDS}, **capture_ref, point_index=i,
            source_name=row["source_name"], source_name_status=diagnostics.get(i, "source_name_observed")))
    return records, dict(**capture_ref, directory=directory.name, job_id=number,
        start=start, end=end, rows=len(records), response_identity=decoded["response_identity"])


def partition(expected, observed, suspended):
    require(len(observed) == len(set(observed)), "duplicate_observed_date")
    require(len(suspended) == len(set(suspended)), "duplicate_suspension_date")
    e, o, s = set(expected), set(observed), set(suspended)
    require(not (o & s), "bar_suspension_conflict")
    require(not (o - e or s - e), "date_outside_contract")
    require(o | s == e, "unexplained_missing_date")


def p4_row(row, block=None):
    """Same 2% envelope; the one reviewed scope is an exact pinned business key."""
    vals = {k: Decimal(str(row[k])) for k in ("low", "high", "volume", "amount")}
    require(all(v.is_finite() and v > 0 for v in vals.values()), "p4_nonpositive_or_nonfinite")
    v, a = vals["volume"], vals["amount"]
    if block is not None:
        require((row["symbol"], row["trade_date"]) == (block["symbol"], block["date"]), "block_business_key_mismatch")
        require(block["scope_evidence_verified"] is True and block["official_rule_sha256"] == PINS[PDF], "block_scope_unverified")
        require(block["volume_shares"] == 400000 and Decimal(block["price_CNY"]) == Decimal("9.25"), "block_values_changed")
        require(Decimal(block["amount_CNY"]) == Decimal(block["volume_shares"]) * Decimal(block["price_CNY"]), "block_amount_not_price_times_volume")
        v -= Decimal(block["volume_shares"])
        a -= Decimal(block["amount_CNY"])
        require(v > 0 and a > 0, "block_residual_nonpositive")
    ratio = a / v
    require(vals["low"] * Decimal("0.98") <= ratio <= vals["high"] * Decimal("1.02"), "p4_price_domain_contradiction")
    return str(ratio)


def build():
    pins = {}
    for name, expected in PINS.items():
        pin_file(pins, HERE / name, expected)
    for path, expected in guard.FIXED_PINS.items():
        pin_file(pins, path, expected)
    pin_file(pins, old.PARSER, "605d65965b1aee56f0f64c5c2446078aefa8d237d7a3d09b5f7403e4a24c2779")
    prior = read(HERE / "qualification_pilot52.json")
    for artifact in prior["artifacts"]:
        pin_file(pins, artifact["path"], artifact["sha256"])
    review = gap_review.run()
    require(review["gap_ledger"] == read(HERE / "pilot52_blocker_review_v3.json")["gap_ledger"], "reviewed_gap_ledger_changed")
    for name, expected in review["inputs"].items():
        pin_file(pins, HERE / name, expected)
    for module in (gap_review, gap_review.previous, gap_review.previous.base, numeric):
        pin_file(pins, module.__file__)
    pin_file(pins, __file__)
    pdf_receipt = HERE / "gap_evidence/bse_trading_explanation_browser_20211119.receipt.json"
    pin_file(pins, pdf_receipt)
    # Page 12 was extracted from these exact retained PDF bytes and visually read.
    observations = read(HERE / gap_review.OBSERVATION)
    official_block = next(o for o in observations["observations"] if o["id"] == "bse_837006_20231204")["rows"]
    require(len(official_block) == 1 and official_block[0]["code"] == "837006" and
            official_block[0]["date"] == "2023-12-04", "official_block_inventory_mismatch")
    identity = next(i for i in prior["official_identity_facts"] if i["symbol"] == "BJ920006")
    require(identity["old_code"] == "837006", "block_issuer_mapping_mismatch")
    block = dict(symbol="BJ920006", date="2023-12-04", volume_shares=int(official_block[0]["volume_shares"]),
        price_CNY=official_block[0]["price_CNY"], amount_CNY=str(Decimal(official_block[0]["volume_shares"]) * Decimal(official_block[0]["price_CNY"])),
        official_rule_sha256=PINS[PDF], official_rule_page=12, scope_evidence_verified=True,
        block_observation_sha256=gap_review.OBSERVATION_PIN, raw_block_http_retained=False,
        basis="BSE daily-total rule + reviewed native Volume/Turnover fields + issuer/code mapping + observed official trade; source totals preserved",
        scope_interpretation="reviewed source interpretation, not a proprietary vendor specification or exact-value certification")
    require(Decimal(block["amount_CNY"]) == Decimal("3700000"), "block_amount_mismatch")
    # Replay the existing independent unit-anchor and cash-event computations.
    spec = importlib.util.spec_from_file_location("m2_v2_old_builder", HERE / "official/build_pilot52_qualification.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    semantics, anchors, unit_files = builder.unit_inputs()
    for artifact in unit_files:
        pin_file(pins, artifact["path"], artifact["sha256"])
    controls = {}
    for symbol, numbers in (("SH600011", (3, 4, 5)), ("BJ920000", (6, 7, 8))):
        series = {str(i): {r["date"]: r for r in builder.projection(HERE / f"qualification_capture/response_{n}.bin")[1]} for i, n in enumerate(numbers)}
        controls[symbol] = numeric.cash_forward_relation(series, [e for e in prior["official_cash_events"] if e["symbol"] == symbol])
        require(controls[symbol]["status"] == "PASS" and controls[symbol] == prior["controls"][symbol], "basis_control_replay_failed")
    with guard.MANIFEST.open(encoding="utf-8-sig") as handle:
        entries = {r["symbol"]: r for r in csv.DictReader(handle)}
    require(len(entries) == 52, "frozen_population_changed")
    calendar = [datetime.fromisoformat(str(d)).date().isoformat() for d in read(guard.CALENDAR)]
    require(len(calendar) == len(set(calendar)), "duplicate_calendar_date")
    calendar.sort()
    parser = old._history_parser()
    audit = read(HERE / "audit_recovered_pilot_52.json")
    scopes_old = {s["symbol"]: s for s in prior["scopes"]}
    ledger = review["gap_ledger"]
    halt_keys = {(g["symbol"], g["date"]) for g in ledger}
    require(len(halt_keys) == len(ledger) == 298, "suspension_inventory_changed")
    results, all_rows, warm_audit = [], [], []
    for item in audit["scopes"]:
        symbol = item["symbol"]; entry = entries[symbol]; previous = scopes_old[symbol]
        records, first = capture(pins, parser, symbol, item["capture_directory"], item["job_id"],
            previous["collector_entrypoint"], old.WARMUP_START, old.RESEARCH_END)
        require(first["raw_sha256"] == previous["raw_body_sha256"] and
                first["request_sha256"] == previous["request_sha256"] and
                first["capture_receipt_sha256"] == previous["capture_receipt_sha256"], "v1_scope_binding_changed")
        require(previous["identity_status"] == "verified", "identity_not_qualified")
        listed = lambda day: (not entry.get("list_date") or day >= entry["list_date"]) and (not entry.get("delist_date") or day <= entry["delist_date"])
        old_expected = [d for d in calendar if old.WARMUP_START <= d <= old.RESEARCH_END and listed(d)]
        suspended = [d for s, d in halt_keys if s == symbol]
        partition(old_expected, [r["trade_date"] for r in records], suspended)
        captures = [first]
        expected = set(old_expected) - set(suspended)
        if symbol in EXTEND:
            number = EXTEND.index(symbol) + 1
            extra, cap = capture(pins, parser, symbol, "warmup3_capture", number, "collect_warmup3.py", EARLY, old.WARMUP_END)
            early_expected = [d for d in calendar if EARLY <= d <= old.WARMUP_END and listed(d)]
            early_halts = [d for d in suspended if d <= old.WARMUP_END]
            partition(early_expected, [r["trade_date"] for r in extra], early_halts)
            eligible = sorted(set(early_expected) - set(early_halts))
            require(len(eligible) >= 250, "mature_warmup_depth_short")
            selected = set(eligible[-250:])
            original = {r["trade_date"]: r for r in records}
            overlap = [r for r in extra if r["trade_date"] in original]
            require(all(all(r[f] == original[r["trade_date"]][f] for f in old.NUMBER_FIELDS) for r in overlap), "warmup_overlap_value_changed")
            added = [r for r in extra if r["trade_date"] in selected and r["trade_date"] not in original]
            require(set(d for d in expected if d <= old.WARMUP_END) <= selected, "original_warmup_row_would_be_dropped")
            records += added; expected |= selected; captures.append(cap)
            warm_audit.append(dict(symbol=symbol, captured=len(extra), overlap=len(overlap), overlap_numeric_checks=len(overlap)*6,
                added=len(added), selected=250, first_selected=min(selected), last_selected=max(selected),
                retained_audit_only=len(extra)-len(overlap)-len(added), response_coverage_complete=True))
        actual_dates = [r["trade_date"] for r in records]
        require(len(actual_dates) == len(set(actual_dates)) and set(actual_dates) == expected, "selected_contract_key_mismatch")
        benchmark = entry["stratum"] == "benchmark"
        if not benchmark:
            # Recompute source-unit support independently; V1 P4 itself stays unchanged.
            old_projection = [{"date":r["trade_date"], **{f:r[f] for f in old.NUMBER_FIELDS}} for r in records]
            unit = numeric.absolute_unit_evidence(old_projection, first["response_identity"]["hostMarketCode"], semantics, anchors)
            require(all(unit["semantic_requirements"].values()) and unit["known_unit_scale_hypotheses_support_unscaled"] is True, "unit_source_or_anchor_failed")
            exceptions = []
            for row in records:
                scoped = block if (symbol, row["trade_date"]) == (block["symbol"], block["date"]) else None
                ratio = p4_row(row, scoped)
                if scoped:
                    exceptions.append({"date": row["trade_date"], "auction_residual_average": ratio, "raw_values_modified": False})
        else:
            exceptions = []
        results.append(dict(symbol=symbol, instrument_class="benchmark" if benchmark else "stock",
            vendor_basis="unadjusted", vendor_basis_status="verified", identity_status="verified",
            unit_status="not_applicable" if benchmark else "verified", volume_unit="not_applicable" if benchmark else "share",
            amount_unit="not_applicable" if benchmark else "CNY", captures=captures,
            expected_price_dates=sorted(expected), suspended_dates=sorted(suspended), rows=len(records),
            research_rows=sum(d >= old.RESEARCH_START for d in expected), warmup_rows=sum(d <= old.WARMUP_END for d in expected),
            price_domain_exceptions=exceptions, prior_qualification_record_sha256=value_sha(previous)))
        all_rows.extend(records)
    short = {s["symbol"]:s["warmup_rows"] for s in results if s["instrument_class"] == "stock" and s["warmup_rows"] < 250}
    require(short == SHORT, "warmup_shortfall_inventory_changed")
    require(sum(w["added"] for w in warm_audit) == 48, "unexpected_extension_count")
    all_rows.sort(key=lambda r: (r["symbol"], r["trade_date"]))
    return dict(schema="m2.ths.qualification_evidence.v2", acceptance_contract="real_session_v2",
        authority_sha256=PINS["acceptance_v2_authority.json"], evidence_mode="retained_market_capture",
        rules_sha256=sha(__file__), scopes=sorted(results, key=lambda s:s["symbol"]), suspension_ledger=ledger,
        block_scope=block, controls=controls, warmup_extension=warm_audit, listing_depth_shortfalls=short,
        rows_per_view=len(all_rows), research_rows=sum(r["trade_date"] >= old.RESEARCH_START for r in all_rows),
        warmup_rows=sum(r["trade_date"] <= old.WARMUP_END for r in all_rows), row_records_sha256=value_sha(all_rows),
        source_rejections=prior["rejected_capture_attempts"], input_pins=pins,
        original_contract_verdict="FAIL_preserved", staging_eligible=True,
        live_trading=False, production_promoted=False, strict_pit=False, all_value_accuracy_verified=False), all_rows


if __name__ == "__main__":
    bundle, _ = build()
    destination = Path(sys.argv[1]).resolve()
    require(destination.parent == HERE and not destination.exists(), "new_phase_output_required")
    old.StagingRun._json_new(destination, bundle)
    print(json.dumps({k:bundle[k] for k in ("rows_per_view", "research_rows", "warmup_rows", "warmup_extension", "listing_depth_shortfalls", "staging_eligible")}, ensure_ascii=False))
    print("qualification_sha256=" + sha(destination))
