"""Build claude_03a/qualification.json and QUALIFICATION_MATRIX.md for M4-03A from pinned frozen metadata only.

Every number in the matrix comes from an already-authorized read (the Codex development-input audit result, the M3
metadata index, the M2 qualification bundle, the pilot manifest) or from static text of the accepted source modules
(line anchors are located by substring and re-checked by validate_qualification.py).  No SQLite connection, no
network, no app import.  Writes only the two output files in claude_03a/.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03a/build_qualification.py"
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
START, END = "2023-09-04", "2025-03-31"
VALIDATION = ("2025-04-01", "2025-12-31")
HOLDOUT = ("2026-01-01", "2026-09-04")
M2_RUN = "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09"
PINS = {
    "audit_result": ("claude methods/_m3_20260910/codex/development_input_audit_01/result.json", "dd3ac6ffde13ba0127a39163d23e3cebb148ca9a93f90d25c17cd4a22402d157"),
    "audit_source": ("claude methods/_m3_20260910/codex/development_input_audit_01/source.py", "e785aaa2e8fa26d0b70dad4522ef9609deaff07982b65e33e44cd4714faf1344"),
    "audit_readme": ("claude methods/_m3_20260910/codex/development_input_audit_01/README.md", "488ae416e0f29537ea5afee01db9b7e5925fef1a4d4bb849688779384fe62f0b"),
    "audit_manifest": ("claude methods/_m3_20260910/codex/development_input_audit_01/manifest.json", "c7ad14131bb95c4878c3d9b6b85b06897ebbf0d6b805792700331037f618f66d"),
    "m3_completion": ("claude methods/_m3_20260910/codex/final_acceptance_01/completion.json", "f273f4dacb92c56870194a23d15615f961505b2374811188e6f96b9415195821"),
    "m3_policy_freeze": ("claude methods/_m3_20260910/policy_freeze.json", "925ae86f772908babef6bc6a08a1ace58c2db7a5e71c7f97af8ad52f2c7a891f"),
    "qualification_v2": ("claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json", "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37"),
    "metadata_index": ("claude methods/_m3_20260910/codex/metadata_index_01/index.json", "14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9"),
    "metadata_index_readme": ("claude methods/_m3_20260910/codex/metadata_index_01/README.md", None),
    "pilot_symbols": ("claude methods/_m1_closure/pilot_symbols.csv", "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe"),
    "candidate_json": (f"{M2_RUN}/candidate.json", "3594868de797812522d333b4118aefaf490f72b2eef28073f70c83965a58551b"),
    "contract_v2_json": (f"{M2_RUN}/contract_v2.json", "b3aeb7e86ace9fbc66b23766592cacfe1837dc939909c52dddc86df87eb71031"),
    "calendar_json": ("backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json", "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656"),
    "m3_frozen_reader": ("backend/app/research/m3_frozen_reader.py", "288594cf0acf977c5ede3f5dec6584134a879889793c4c3542d01b1d7f7ae5af"),
    "m3_labels": ("backend/app/research/m3_labels.py", "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393"),
    "m4_execution": ("backend/app/research/m4_execution.py", "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7"),
    "m4_portfolio": ("backend/app/research/m4_portfolio.py", "2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360"),
    "m4_risk": ("backend/app/research/m4_risk.py", "faec444ee98ed6ee8c20da217a6cb29ced53d7de2ceae1e2198b1cbc73b665f2"),
    "kernel_contract": ("claude methods/_m4_20260912/claude_01/CONTRACT.md", None),
    "ledger_contract": ("claude methods/_m4_20260912/claude_02a/CONTRACT.md", None),
    "risk_contract": ("claude methods/_m4_20260912/claude_02b/CONTRACT.md", None),
}
DATABASES = {
    "trading": (f"{M2_RUN}/trading.sqlite3", "c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca", 38969344),
    "history": (f"{M2_RUN}/history.sqlite3", "eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003", 10604544),
}
# Static text anchors: (pin key, substring).  The builder records the 1-based line of the first occurrence; the
# validator re-reads the file and checks the substring is on that line.
ANCHORS = {
    "reader.FROZEN_M2": ("m3_frozen_reader", "FROZEN_M2 = FrozenInputs("),
    "reader.development_window": ("m3_frozen_reader", 'DEVELOPMENT_START = "2023-09-04"'),
    "reader.evidence_assembly_at": ("m3_frozen_reader", "EVIDENCE_ASSEMBLY_AT = "),
    "reader.cutoff_offset": ("m3_frozen_reader", "CUTOFF_OFFSET_SECONDS = 3600"),
    "reader.query.daily_bar_cache": ("m3_frozen_reader", 'SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, adjustment_mode, volume_unit'),
    "reader.query.daily_bars": ("m3_frozen_reader", 'SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, provider, fetched_at, ingest_run_id'),
    "reader.query.row_evidence": ("m3_frozen_reader", 'SELECT symbol, trade_date, raw_sha256, request_sha256, producer_sha256, parser_sha256, capture_receipt_sha256'),
    "reader.query.coverage_inventory": ("m3_frozen_reader", 'SELECT symbol, trade_date, classification FROM coverage_inventory'),
    "reader.query.suspension_records": ("m3_frozen_reader", 'SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records'),
    "reader.query.instruments": ("m3_frozen_reader", 'SELECT symbol FROM instruments'),
    "reader.price_available_at_is_observed_at": ("m3_frozen_reader", 'kind="price", available_at=r["observed_at"]'),
    "reader.suspension_available_at_is_assembly": ("m3_frozen_reader", 'available_at=EVIDENCE_ASSEMBLY_AT, source_ref=f"suspension#'),
    "reader.security_context_unknowns": ("m3_frozen_reader", 'name=None, st_status="unknown", corporate_action_status=status'),
    "reader.security_context_float_turnover": ("m3_frozen_reader", "float_shares=None, turnover_available=False"),
    "reader.known_events": ("m3_frozen_reader", "def known_events(metadata_index"),
    "reader.exclusion.adjustment": ("m3_frozen_reader", '"adjustment_mode_not_none"'),
    "labels.required_price_fields": ("m3_labels", '"required_price_fields"'),
    "labels.availability_rule": ("m3_labels", '"availability_rule": "available_at must not precede the historical close time'),
    "labels.usable_retrospective": ("m3_labels", '"usable_retrospective"'),
    "labels.warmup_required": ("m3_labels", '"warmup_required_sessions": 250'),
    "labels.limit_thresholds": ("m3_labels", '"limit_thresholds_pct": {'),
    "labels.limit_hypothesis": ("m3_labels", '"hypothesis": "app/data/price_limits.py:31-37 DEFAULT_LIMIT_UP_THRESHOLDS'),
    "labels.st_unknown_rule": ("m3_labels", '"st_unknown_rule"'),
    "labels.ca_unknown_rule": ("m3_labels", '"unknown_rule": "returns and positions carry adjustment_uncertainty=true'),
    "labels.ca_partial_facts": ("m3_labels", '"m2_partial_facts"'),
    "labels.scope_exception_bj920006": ("m3_labels", '"symbol": "BJ920006", "trade_date": "2023-12-04", "kind": "bse_block_trade_total_scope_interpretation"'),
    "labels.tradability_unverified": ("m3_labels", '"tradability": "always \'unverified\' in this policy version"'),
    "labels.liquidity_bands": ("m3_labels", '"liquidity_bands_amount_20_cny"'),
    "labels.benchmark_rows": ("m3_labels", '"benchmark_rows": {"volume_unit": "not_applicable"'),
    "audit.queries": ("audit_source", "'trading_prices': 'SELECT * FROM daily_bar_cache WHERE trade_date <= ? ORDER BY symbol,trade_date'"),
    "audit.source_provider": ("audit_source", "require(row['source'] == hist['provider'] == 'tonghuashun' and row['quality_status'] == 'qualified_candidate', 'source_status')"),
    "audit.adjustment": ("audit_source", "require(row['adjustment_mode'] == hist['adjustment_mode'] == 'none', 'adjustment_mismatch')"),
    "audit.ohlc_order": ("audit_source", "require(0 < row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high'], 'ohlc_order')"),
    "audit.segment": ("audit_source", "segment = 'development' if START <= key[1] else 'warmup'"),
    "audit.observed_at_lineage": ("audit_source", "require(hist['fetched_at'] == ev['observed_at'] and hist['ingest_run_id'] == ingest[0]['id'], 'history_time_lineage')"),
    "audit.calendar_cohort": ("audit_source", "expected = [d for d in calendar if instrument['listing_date'] is None or d >= instrument['listing_date']]"),
    "audit.not_proved_flags": ("audit_source", "original_historical_availability_proved=False, raw_capture_bodies_parsed=False"),
    "audit.uri": ("audit_source", "URIS = {p.as_uri() + '?mode=ro&immutable=1' for p in DBS}"),
    "audit.authorizer": ("audit_source", "return sqlite3.SQLITE_OK if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION} else sqlite3.SQLITE_DENY"),
    "kernel.Instrument_board_declared": ("m4_execution", "reference), not inferred from the code prefix"),
    "kernel.TradabilityEvidence": ("m4_execution", "class TradabilityEvidence:"),
    "kernel.PriceObservation": ("m4_execution", "class PriceObservation:"),
    "kernel.LiquidityCapacity": ("m4_execution", "class LiquidityCapacity:"),
    "kernel.FeeSchedule": ("m4_execution", "class FeeSchedule:"),
    "kernel.fee_provenances": ("m4_execution", 'FEE_PROVENANCES = ("hypothetical_fixture", "sourced_verified")'),
    "kernel.ExecutionAssumptions": ("m4_execution", "class ExecutionAssumptions:"),
    "kernel.SettlementPolicy": ("m4_execution", "class SettlementPolicy:"),
    "kernel.LotPolicy": ("m4_execution", "class LotPolicy:"),
    "kernel.input_not_available_at_decision": ("m4_execution", 'raise _Reject("input_not_available_at_decision"'),
    "kernel.calendar_not_available": ("m4_execution", 'raise _Reject("calendar_not_available"'),
    "kernel.evidence_available_after_execution_price": ("m4_execution", 'raise _Reject("evidence_available_after_execution", f"contemporaneous price available at'),
    "kernel.tradability_unknown": ("m4_execution", 'raise _Reject("tradability_unknown"'),
    "kernel.unknown_state": ("m4_execution", 'raise _Reject("unknown_state"'),
    "kernel.band_prices_missing": ("m4_execution", 'raise _Reject("band_prices_missing"'),
    "kernel.capacity_unproven": ("m4_execution", 'raise _Unfilled("capacity_unproven"'),
    "kernel.st_flag": ("m4_execution", 'flags.append("st_security")'),
    "kernel.new_listing_flag": ("m4_execution", 'flags.append("new_listing")'),
    "kernel.evidence_grade": ("m4_execution", '"evidence_grade": EVIDENCE_CONTEMPORANEOUS if not assumptions_used else "assumed"'),
    "kernel.non_tradable_role": ("m4_execution", 'raise _Reject("non_tradable_role"'),
    "risk.evidence_time": ("m4_risk", '"evidence_time": "observed_at <= decided_at and available_at <= decided_at'),
    "risk.benchmark": ("m4_risk", '"benchmark": {"series": "injected index levels; symbol role benchmark; never traded"'),
    "risk.delisting": ("m4_risk", '"delisting": {"status_at": "latest security status with available_at <= decided_at"'),
    "risk.exits_reference": ("m4_risk", '"reference": "entry_cost_reference = FIFO cost_remaining / quantity_remaining'),
    "ledger.InitialLot": ("m4_portfolio", "class InitialLot:"),
    "ledger.settlement_view": ("m4_portfolio", "def settlement_view(self, session: str, calendar: Any, sellable_after_sessions: int)"),
}
MODES = {
    "strict_historical_execution": "fill evidence that was contemporaneously available at the historical attempt instant (kernel evidence_grade=contemporaneous); the only mode that can satisfy the M4 requirement 'on eligible historical data'",
    "retrospective_bar_diagnostics": "bar-level checks computed after the fact from the frozen daily OHLCVA (2026 capture) - counts, would-have-crossed conditions, gap/halt exposure; no fill is claimed",
    "hypothetical_execution_assumptions": "replay through the frozen kernel/ledger/risk layer where every non-contemporaneous input is a declared, labelled assumption (kernel evidence_grade=assumed; provenance hypothetical_fixture); results are conditional on the assumption set and are never historical execution evidence",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(key: str):
    rel, expected = PINS[key]
    p = PROJECT / rel
    actual = sha256(p)
    if expected is not None and actual != expected:
        raise SystemExit(f"pin mismatch {rel}: {actual} != {expected}")
    return p, actual


def anchor_lines() -> dict[str, dict]:
    cache: dict[str, list[str]] = {}
    out = {}
    for name, (key, needle) in ANCHORS.items():
        rel = PINS[key][0]
        if rel not in cache:
            cache[rel] = (PROJECT / rel).read_text(encoding="utf-8").splitlines()
        hits = [i + 1 for i, line in enumerate(cache[rel]) if needle in line]
        if not hits:
            raise SystemExit(f"anchor not found: {name} in {rel}")
        out[name] = {"path": rel, "line": hits[0], "contains": needle}
    return out


def main() -> int:
    pins = {}
    for key in PINS:
        p, actual = load(key)
        pins[key] = {"path": PINS[key][0], "sha256": actual, "bytes": p.stat().st_size}
    dbs = {}
    for key, (rel, expected, size) in DATABASES.items():
        p = PROJECT / rel
        st = p.stat()
        actual = sha256(p)
        if actual != expected or st.st_size != size:
            raise SystemExit(f"database pin mismatch {rel}")
        dbs[key] = {"path": rel, "sha256": actual, "bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
                    "sidecars_absent": not any((PROJECT / (rel + s)).exists() for s in ("-wal", "-shm", "-journal")), "access_in_this_task": "byte hash + stat only; no sqlite3 connection"}
    anchors = anchor_lines()
    audit = json.loads((PROJECT / PINS["audit_result"][0]).read_text(encoding="utf-8"))
    qual = json.loads((PROJECT / PINS["qualification_v2"][0]).read_text(encoding="utf-8"))
    index = json.loads((PROJECT / PINS["metadata_index"][0]).read_text(encoding="utf-8"))
    completion = json.loads((PROJECT / PINS["m3_completion"][0]).read_text(encoding="utf-8"))
    policy_freeze = json.loads((PROJECT / PINS["m3_policy_freeze"][0]).read_text(encoding="utf-8"))
    pilot = list(csv.DictReader((PROJECT / PINS["pilot_symbols"][0]).open(encoding="utf-8")))
    candidate = json.loads((PROJECT / PINS["candidate_json"][0]).read_text(encoding="utf-8"))
    contract_v2 = json.loads((PROJECT / PINS["contract_v2_json"][0]).read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- derived facts (metadata only)
    per_symbol = audit["per_symbol"]
    stocks = [s for s in per_symbol if s["role"] == "stock"]
    benchmarks = [s for s in per_symbol if s["role"] == "benchmark"]
    instruments = {i["symbol"]: i for i in index["instruments"]}
    sessions = [d for d in index["calendar"]["sessions"] if START <= d <= END]
    ledger = qual["suspension_ledger"]
    dev_halts = [x for x in ledger if START <= x["date"] <= END]
    warm_halts = [x for x in ledger if x["date"] < START]
    known_events = {s: [e["ex_date"] for e in i["known_cash_events"]] for s, i in instruments.items() if i["known_cash_events"]}
    dev_events = {s: [d for d in v if START <= d <= END] for s, v in known_events.items()}
    strata = Counter(r["stratum"] for r in pilot)
    names_with_st = sorted((r["symbol"], r["name"]) for r in pilot if "ST" in r["name"])
    listing_kinds = Counter((i["listing_evidence"].get("status") or i["listing_evidence"].get("identity_kind")) for i in instruments.values())
    ipo_in_window = sorted((s["symbol"], s["listing_date"], s["expected_development_sessions"]) for s in stocks if s["listing_date"] and s["listing_date"] > START)
    unlisted_in_development = sorted(s["symbol"] for s in stocks if s["expected_development_sessions"] == 0)
    warm_depth = Counter(s["warmup_prices"] for s in stocks)
    code_prefix = Counter()
    for r in pilot:
        if r["exchange"] == "INDEX":
            code_prefix["index"] += 1
        elif r["symbol"].startswith("SH688"):
            code_prefix["SH688 (STAR by code prefix - not declared board evidence)"] += 1
        elif r["symbol"].startswith(("SZ300", "SZ301")):
            code_prefix["SZ30x (ChiNext by code prefix - not declared board evidence)"] += 1
        elif r["symbol"].startswith("BJ"):
            code_prefix["BJ (BSE; 9 official listing/code facts)"] += 1
        elif r["symbol"].startswith("SH"):
            code_prefix["SH main (by code prefix)"] += 1
        else:
            code_prefix["SZ main (by code prefix)"] += 1
    consistency = {
        "development_sessions_audit": audit["development_sessions"], "development_sessions_from_index_calendar": len(sessions),
        "stock_development_price_rows": sum(s["development_prices"] for s in stocks), "audit_stock_development_count": next(x["count"] for x in audit["prices_by_role_and_segment"] if x["role"] == "stock" and x["segment"] == "development"),
        "index_development_price_rows": sum(s["development_prices"] for s in benchmarks), "development_halt_keys_per_symbol_sum": sum(s["development_halts"] for s in stocks),
        "development_halt_keys_from_ledger": len(dev_halts), "warmup_halt_keys_from_ledger": len(warm_halts), "ledger_keys_total": len(ledger),
        "stocks": len(stocks), "benchmarks": len(benchmarks), "listed_stocks_first_session": audit["per_date"][0]["listed_stocks"], "listed_stocks_last_session": audit["per_date"][-1]["listed_stocks"],
        "sessions_with_halt_keys": sum(1 for d in audit["per_date"] if d["halt_keys"]), "min_daily_price_availability": min(d["price_availability"] for d in audit["per_date"]),
        "observed_at_min": audit["observed_at_min"], "observed_at_max": audit["observed_at_max"], "source_name_status_counts": audit["source_name_status_counts"],
        "null_counts": audit["null_counts"], "units": audit["units"], "candidate_source": candidate["source"], "candidate_rows_per_view": candidate["rows_per_view"],
        "contract_v2_expected_suspensions": contract_v2["expected_suspensions"], "contract_v2_original_verdict": contract_v2["original_contract_verdict"],
        "m3_completion": {k: completion[k] for k in ("status", "M3_complete", "dual_reviewed_positive_episodes", "disputed_episodes", "strict_pit", "training_eligible")},
        "m3_policy_windows": {"development": policy_freeze["development"], "validation": policy_freeze["validation"], "final_holdout": policy_freeze["final_holdout"], "cutoff_convention": policy_freeze["cutoff_convention"]},
    }
    assert consistency["development_sessions_audit"] == len(sessions) == 378
    assert consistency["stock_development_price_rows"] == consistency["audit_stock_development_count"] == 17402
    assert consistency["development_halt_keys_per_symbol_sum"] == len(dev_halts) == 152 and consistency["index_development_price_rows"] == 756
    assert len(stocks) == 50 and len(benchmarks) == 2 and len(ledger) == 298 and contract_v2["expected_suspensions"] == 298

    facts = {
        "development_window": [START, END], "validation_window_unused": list(VALIDATION), "final_holdout_unused": list(HOLDOUT),
        "development_sessions": 378, "stock_price_rows": 17402, "confirmed_full_day_halt_keys": 152, "index_rows": 756, "index_symbols": ["SH000001", "SH000300"],
        "pool": {"stocks": 50, "benchmarks": 2, "listed_at_first_session": consistency["listed_stocks_first_session"], "listed_at_last_session": consistency["listed_stocks_last_session"],
                 "unlisted_throughout_development": unlisted_in_development, "ipo_inside_development": [{"symbol": s, "listing_date": d, "development_sessions": n} for s, d, n in ipo_in_window]},
        "warmup": {"stock_rows_before_development": next(x["count"] for x in audit["prices_by_role_and_segment"] if x["role"] == "stock" and x["segment"] == "warmup"),
                   "index_rows_before_development": next(x["count"] for x in audit["prices_by_role_and_segment"] if x["role"] == "benchmark" and x["segment"] == "warmup"),
                   "stocks_with_250_bars_before_first_development_decision": warm_depth[250], "stocks_with_partial_depth": {s["symbol"]: s["warmup_prices"] for s in stocks if 0 < s["warmup_prices"] < 250},
                   "stocks_with_zero_warmup": sorted(s["symbol"] for s in stocks if s["warmup_prices"] == 0), "warmup_halt_keys": len(warm_halts),
                   "warmup_first_selected_date_min": min(c["first_selected"] for c in qual["warmup_extension"]) if qual.get("warmup_extension") else None},
        "halts": {"symbols": {s["symbol"]: s["development_halts"] for s in stocks if s["development_halts"]}, "sessions_with_halts": consistency["sessions_with_halt_keys"],
                  "ledger_statuses": dict(Counter(x["status"] for x in dev_halts)), "evidence_kind": "issuer announcements incl. subsequent resumption notices (retrospective); one exchange DOM observation in warmup"},
        "capture": {"observed_at_min": audit["observed_at_min"], "observed_at_max": audit["observed_at_max"], "source": "tonghuashun", "two_stores_same_source": True,
                    "source_name_status": audit["source_name_status_counts"], "raw_vendor_value_accuracy_reproved": audit["raw_vendor_value_accuracy_reproved"],
                    "original_historical_availability_proved": audit["original_historical_availability_proved"], "independent_market_source_corroboration": audit["independent_market_source_corroboration"]},
        "units": audit["units"], "adjustment_mode": "none (vendor_basis 'unadjusted' verified for 52 scopes)", "price_domain_exception": index["block_scope_condition"],
        "known_cash_events": {s: {"all": v, "inside_development": dev_events[s]} for s, v in known_events.items()},
        "corporate_action_completeness": dict(Counter(i["corporate_action_completeness"] for i in instruments.values())),
        "historical_st_status": dict(Counter(i["historical_st_status"] for i in instruments.values())), "name_used_as_historical_status": dict(Counter(i["name_used_as_historical_status"] for i in instruments.values())),
        "capture_time_is_original_market_availability": dict(Counter(i["capture_time_is_original_market_availability"] for i in instruments.values())),
        "pilot_names_containing_ST_2026_only": names_with_st, "listing_evidence_kinds": dict(listing_kinds), "pilot_strata": dict(strata), "code_prefix_groups": dict(code_prefix),
        "calendar": {"path": index["calendar"]["path"], "sha256": index["calendar"]["sha256"], "sessions_total": index["calendar"]["sessions"], "historical_available_at": index["calendar"]["historical_available_at"],
                     "source": index["calendar"]["source"]},
    }

    CAP = "retrospective_capture_2026"          # value observed/captured in 2026 for a historical session
    ASM = "evidence_assembly_2026"               # fact assembled from documents in 2026 (suspension ledger, listing facts, cash events)
    NA = "not_established"
    def row(rid, title, kernel_need, evidence, coverage, availability, verdict, strict, retro, hypo, consequence, notes=()):
        return {"id": rid, "requirement": title, "accepted_contract_need": kernel_need, "evidence": evidence, "development_coverage": coverage,
                "availability_semantics": availability, "verdict": verdict,
                "modes": {"strict_historical_execution": strict, "retrospective_bar_diagnostics": retro, "hypothetical_execution_assumptions": hypo},
                "consequence": consequence, "notes": list(notes)}

    def ev(kind, ref, detail):
        return {"kind": kind, "ref": ref, "detail": detail}

    requirements = [
        row("R01_unadjusted_ohlc_units", "Unadjusted OHLC prices and units",
            "PriceObservation(price, field, observed_at, available_at, source_ref, kind) [kernel.PriceObservation]; risk marks Mark(price, observed_at, available_at) [risk.evidence_time]; money CNY, volume shares",
            [ev("table", "trading.sqlite3:daily_bar_cache(symbol, trade_date, open, high, low, close, volume, amount, source='tonghuashun', quality_status='qualified_candidate', adjustment_mode='none', volume_unit='share')", "columns as selected by reader.query.daily_bar_cache and audit.queries; audited 27,900 rows <= 2025-03-31 with OHLC order, finite values, non-negative aggregates (audit.ohlc_order)"),
             ev("table", "history.sqlite3:daily_bars(symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, provider, fetched_at, ingest_run_id)", "same-source mirror; numeric equality for all 27,900 rows (audit.source_provider, audit.adjustment); not independent corroboration"),
             ev("table", "trading.sqlite3:row_evidence(raw_sha256, request_sha256, producer_sha256, parser_sha256, capture_receipt_sha256, capture_producer_manifest_sha256, observed_at, point_index, qualification_sha256, source_name, source_name_status)", "capture lineage per row (reader.query.row_evidence); observed_at is the 2026 capture instant (audit.observed_at_lineage)"),
             ev("metadata", "qualification_v2_reviewed.json:scopes[*].{vendor_basis='unadjusted', vendor_basis_status='verified', unit_status, volume_unit, amount_unit}", "52 scopes; stock share/CNY, index not_applicable (labels.benchmark_rows)"),
             ev("metadata", "metadata_index_01/index.json:block_scope_condition", "BJ920006 2023-12-04 block-trade total inside volume/amount (labels.scope_exception_bj920006)")],
            {"stock_rows": 17402, "index_rows": 756, "sessions": 378, "null_counts": audit["null_counts"], "min_daily_price_availability": consistency["min_daily_price_availability"]},
            CAP, "present",
            "ineligible: a daily bar captured 2026-09-09/10 cannot be contemporaneous execution evidence for 2023-2025 (kernel.evidence_available_after_execution_price); no intraday/auction print exists",
            "eligible: bar-level diagnostics (crossings, gaps, halts, would-have-been fills reported as conditions, never as fills)",
            "eligible_with_label: PriceObservation.kind='predeclared_assumption' + assumption_ref ('daily bar open = 09:30 auction print' / 'close = 15:00 close-auction print'); evidence_grade becomes 'assumed' (kernel.evidence_grade)",
            "Prices support diagnostics and labelled replay only; vendor value accuracy is not re-proved (raw_vendor_value_accuracy_reproved=false); the BJ920006 2023-12-04 bar must keep its scoped block-trade interpretation.",
            ("two candidate stores mirror one Tonghuashun capture; independent_market_source_corroboration=false", "numeric_extrema in result.json are mixed-record diagnostics, not a single-instrument statistic")),
        row("R02_calendar_session_next_legal_point", "Session calendar, next legal execution point, expiry and settlement counting",
            "SessionCalendar(sessions, tz, open/close, source_ref, available_at, synthetic, halted_sessions) with available_at <= decided_at (kernel.calendar_not_available); next legal point = next session open; settlement counts sessions (kernel.SettlementPolicy, ledger.settlement_view)",
            [ev("file", f"{index['calendar']['path']} sha256 {index['calendar']['sha256']}", "retained M2 AkShare calendar file, 8,797 sessions; not a new exchange fetch"),
             ev("metadata", "metadata_index_01/index.json:calendar.{sessions, research_start, research_end, research_session_count=728, historical_available_at=null}", "development subset 2023-09-04..2025-03-31 = 378 sessions (audit.calendar_cohort)"),
             ev("code", "reader.development_window / reader.cutoff_offset", "development bounds and close+3600s retrospective cutoff convention"),
             ev("metadata", "m3 policy_freeze.json: development / validation / final_holdout windows", "validation 2025-04-01..2025-12-31 and holdout 2026-01-01..2026-09-04 are unused here")],
            {"sessions": 378, "first": START, "last": END, "next_session_after_end": "2025-04-01", "market_wide_halted_sessions_recorded": "none recorded in the frozen metadata (absence is not proof of none)"},
            NA, "assumption_only",
            "ineligible: the calendar file carries no historical publication instant (historical_available_at=null); the kernel needs calendar.available_at <= decided_at",
            "eligible: session ordering, gap and holding-period counting use the injected sessions",
            "eligible_with_label: declare calendar.available_at as an assumption ('exchange calendar published before the session year') in source_ref; halted_sessions=() must be declared as 'none known', not 'none'",
            "Session order and next-open eligibility are computable; the historical publication time of the calendar and intraday session clocks (09:30/15:00 assumed uniform) are assumptions.",
            ("open/close times 09:30/15:00 +08:00 are declared uniformly; lunch break and auction sub-phases are not in the frozen data",)),
        row("R03_listing_board_lot_tick", "Listing date / state, board, lot size and tick",
            "Instrument(board declared with listing_evidence_ref, not inferred from code prefix) [kernel.Instrument_board_declared]; listing_state seasoned/new_listing (kernel.new_listing_flag); LotPolicy / tick_size in ExecutionAssumptions (kernel.LotPolicy)",
            [ev("metadata", "metadata_index_01/index.json:instruments[*].{listing_date, listing_evidence{status|identity_kind, document_sha256}}", f"listing evidence kinds: {dict(listing_kinds)}; 9 BJ symbols carry official listing/code facts, 41 stocks are pilot-CSV level only, 2 indices not applicable"),
             ev("file", "claude methods/_m1_closure/pilot_symbols.csv:{symbol, exchange, list_date, stratum}", "exchange = SH/SZ/BJ/INDEX only; no board column; STAR (688) / ChiNext (30x) are code-prefix inferences (labels.limit_hypothesis)"),
             ev("metadata", "qualification_v2_reviewed.json:input_pins gap_evidence/bse_trading_explanation_browser_20211119.pdf", "BSE trading explanation reviewed by M2 for the block-trade rule (page 12) only; lot/tick rules were not extracted"),
             ev("code", "labels.limit_thresholds / labels.limit_hypothesis", "board thresholds re-declared as a hypothesis from app/data/price_limits.py, not sourced rules")],
            {"listing_dates": "52 (9 official BJ, 41 pilot-level, 2 N/A)", "ipo_inside_development": [s for s, _, _ in ipo_in_window], "unlisted_throughout_development": unlisted_in_development, "board_declaration": "none in frozen evidence", "lot_tick_documents": "none extracted"},
            ASM, "assumption_only",
            "ineligible: no declared board / lot / tick evidence with provenance; listing dates for 41 stocks are pilot-level and their historical availability is not established",
            "eligible: listing_date bounds the per-symbol session cohort (audit.calendar_cohort); IPO-in-window symbols have 369-377 development sessions, BJ920002 203",
            "eligible_with_label: board by code prefix, 100-share lots / 0.01 tick (BSE odd increments) as ExecutionAssumptions with provenance='hypothetical_fixture' and an explicit rule-source reference to be supplied later",
            "Instrument.board, lot policy and tick are declared assumptions; new-listing sessions (first days after IPO) have no band and different lot rules, so they must be excluded or flagged (listing_state='new_listing').",
            ("BJ920003 / BJ920005 / BJ920007 list after the development window: no development rows by construction, not a data gap",)),
        row("R04_historical_st_and_price_bands", "Historical ST status and daily price bands (limit_up/limit_down)",
            "TradabilityEvidence.st_status in {st, not_st, unknown}; band_state + limit_up_price/limit_down_price tick-aligned (kernel.band_prices_missing); unknown -> reject unless ExecutionAssumptions.unknown_state_assumptions declares a value (kernel.unknown_state); 'st' only flags (kernel.st_flag)",
            [ev("metadata", "metadata_index_01/index.json:instruments[*].historical_st_status='unknown', name_used_as_historical_status=false", f"{dict(Counter(i['historical_st_status'] for i in instruments.values()))}"),
             ev("table", "trading.sqlite3:row_evidence.source_name_status", f"{audit['source_name_status_counts']} - vendor name field invalid for every row; cannot establish historical ST"),
             ev("file", "claude methods/_m1_closure/pilot_symbols.csv:name", f"2026 names containing 'ST': {names_with_st} - current names, never a historical status"),
             ev("code", "labels.st_unknown_rule / labels.limit_thresholds", "M3 policy: unknown ST -> lowest plausible threshold, limit-like is 'possible' not 'confirmed'; thresholds main 9.8 / st 4.8 / chinext 19.5 / star 19.5 / bse 29.0 are a re-declared hypothesis"),
             ev("table", "daily_bar_cache.close of the previous session", "previous close exists for band computation; the ratio, ST status and rounding rule do not")],
            {"st_status_known_symbol_sessions": 0, "band_price_evidence_rows": 0, "previous_close_rows": 17402},
            NA, "missing",
            "ineligible: st_status and band_state are unknown for every symbol-session; the kernel rejects unknown states without a declared assumption",
            "eligible_with_label: 'limit-like' bar conditions (close at +/- threshold vs previous close) can be reported as possible, never confirmed",
            "assumption_required: unknown_state_assumptions=(('st_status','not_st'),('band_state','band'),('listing_state','seasoned')) plus band = round(prev_close x (1 +/- assumed ratio by code-prefix board) to 0.01) declared in assumption_ref; evidence_grade 'assumed'",
            "No fill can be proven inside a historical band; a replay must label every band as assumed and must not treat a missing ST record as 'not ST'. SH600289 / SZ002731 carry ST names in 2026 - their historical status on any development session is still unknown.",
            ("absence of ST evidence is not evidence of absence", "new-listing sessions have no band under exchange rules; the assumption must exclude them explicitly")),
        row("R05_suspension_timing", "Suspension timing (full-day, intraday) and tradability at the attempt phase",
            "TradabilityEvidence.status in {tradable, suspended, unknown} for the execution session, observed_at/available_at <= executed_at (kernel.tradability_unknown); ledger counts halted sessions for settlement",
            [ev("table", "trading.sqlite3:suspension_records(symbol, trade_date, evidence_sha256, record_json) + coverage_inventory.classification in {price, full_day_suspension}", f"{len(dev_halts)} confirmed full-day halt keys inside development (reader.query.suspension_records, reader.query.coverage_inventory)"),
             ev("metadata", "qualification_v2_reviewed.json:suspension_ledger[*].{symbol, date, status, evidence[{start, resume, sources|source, sha256}]}", f"{dict(Counter(x['status'] for x in dev_halts))} in development; evidence = issuer announcements incl. resumption notices (retrospective)"),
             ev("code", "reader.suspension_available_at_is_assembly", "the M3 reader assigns available_at = EVIDENCE_ASSEMBLY_AT (2026-09-10) to every suspension observation"),
             ev("code", "labels.tradability_unverified", "M3 policy: tradability 'always unverified'"),
             ev("table", "daily_bar_cache.volume > 0 on price days (audit null_counts / extrema)", "a traded bar shows trading occurred on that day, not tradability at 09:30 or at any specific phase")],
            {"full_day_halt_keys": 152, "halt_symbols": {s["symbol"]: s["development_halts"] for s in stocks if s["development_halts"]}, "sessions_with_halts": consistency["sessions_with_halt_keys"], "intraday_halt_evidence_rows": 0},
            ASM, "present",
            "ineligible: suspension facts became available in 2026 (assembly) and no per-phase tradability record exists; 'tradable' on a price day is an inference from the bar, not evidence",
            "eligible: full-day halt exposure per symbol/session is exact for the frozen pool (152 keys; 5 symbols); intraday halts unknown",
            "eligible_with_label: status='suspended' on ledger keys and status='tradable' on price days as an assumption ('bar exists => tradable all day'), availability assumed; resumption dates from later notices must not be used before their session",
            "Full-day suspensions are known retrospectively and exactly for the pool; intraday halts and phase-level tradability are unknown; an exit intent on a halted session stays unfilled (kernel 'suspended') only if the replay injects the halt.",
            ("never treat absence of a suspension record as proof of tradability outside the confirmed-coverage pool", "resumption notices are later information: usable for retrospective gap causes, not as knowledge on the halt day")),
        row("R06_corporate_actions_adjustments", "Corporate actions, ex-dates and price adjustment",
            "Unadjusted prices feed marks, stop-loss reference (risk.exits_reference) and FIFO cost; the ledger posts no dividends/splits; the risk layer has no corporate-action input",
            [ev("metadata", "metadata_index_01/index.json:instruments[*].known_cash_events (BJ920000: 6, SH600011: 3) and corporate_action_completeness='unknown' for 52", f"inside development: {dev_events}"),
             ev("metadata", "qualification_v2_reviewed.json:controls.{BJ920000, SH600011}.boundaries[*].{ex_date, observed_cash_step}", "adjusted-vs-unadjusted control diagnostic on two symbols only (reader.known_events)"),
             ev("code", "labels.ca_unknown_rule / labels.ca_partial_facts", "M3 policy: unknown -> adjustment_uncertainty=true; partial known -> gates windows, completeness unknown"),
             ev("table", "daily_bar_cache.adjustment_mode='none' (reader.exclusion.adjustment)", "no adjustment factors, splits, bonus shares or rights records exist in either store")],
            {"symbols_with_any_known_events": 2, "known_ex_dates_inside_development": sum(len(v) for v in dev_events.values()), "symbols_with_unknown_completeness": 52, "split_bonus_rights_register_rows": 0},
            ASM, "missing",
            "ineligible: no complete register; a holding across an unrecorded split/bonus would produce a fictitious stop-loss or gain",
            "eligible_with_label: bar diagnostics must carry adjustment_uncertainty=true for every symbol; known ex-dates (3 inside development) can exclude windows",
            "assumption_required: exclude positions spanning known ex-dates; label every other holding period 'adjustment_uncertainty'; dividends are not posted to the ledger (no cash accrual), so realized PnL is understated/overstated by unknown amounts",
            "Realized PnL, stop-loss triggers and holding-period returns are conditional on an unknown corporate-action set for all 52 instruments; results cannot be reported as historical performance.",
            ("no event rows for 50 symbols is not evidence that no events occurred",)),
        row("R07_delisting_terminal_value", "Delisting and terminal value of unresolved holdings",
            "SecurityStatus in {listed, suspended, delisting_announced, delisted} with available_at (risk.delisting); delisted holdings retained unresolved; benchmarks never traded (kernel.non_tradable_role)",
            [ev("metadata", "metadata_index_01/index.json:instruments[*].{research_price_rows=728 for symbols listed before 2023-09-04, expected_price_dates through 2026-09-04}", "every pool stock has rows to the research end: no delisting inside the pool by construction"),
             ev("file", "claude methods/_m1_closure/pilot_symbols.csv (2026 pilot manifest)", "the pool was assembled in 2026 from then-listed securities (survivorship: delisted names cannot appear)"),
             ev("metadata", "metadata_index_01/index.json:limits[*] 'SZ002115 and SZ002081 are absent; no seed case evidence is fabricated'", "seed names outside the pool are not evidence of delisting handling either")],
            {"delisting_events_in_pool": 0, "delisting_announcement_records": 0, "pool_selection_time": "2026 (survivor pool)"},
            NA, "missing",
            "ineligible: no delisting event or announcement record exists; the survivor pool cannot exercise the requirement on real data",
            "ineligible: nothing to diagnose; the absence is structural (selection in 2026), not a finding of 'no delistings'",
            "ineligible: synthetic proof only (M4-02B delisting.unresolved scenario); a replay must report 'delisting handling untested on historical data'",
            "The M4 acceptance item 'benchmarks and delisted securities do not create survivorship leakage' is provable only synthetically; the frozen pool itself embodies survivorship selection.",
            ()),
        row("R08_capacity_auction_vs_full_day_volume", "Contemporaneous auction/continuous capacity versus full-day volume",
            "LiquidityCapacity(quantity, unit, basis, observed_at, available_at, kind, consumed_quantity) for the attempt phase; missing -> unfilled capacity_unproven (kernel.capacity_unproven); max_participation_rate applies to proven capacity",
            [ev("table", "daily_bar_cache.volume / amount (full-day aggregates; volume_unit='share', amount_unit='CNY')", "full-day totals observed at the close; no auction-matched quantity, no intraday volume, no order-book depth in either store"),
             ev("code", "kernel contract claude_01/CONTRACT.md 'a full-day close/high/low/amount is observed at the close and therefore cannot decide an opening fill'", "tested consequence evidence.full_day_amount_capacity_for_open"),
             ev("code", "labels.liquidity_bands", "M3 uses amount_20 bands for matching, not executable capacity")],
            {"auction_capacity_rows": 0, "intraday_volume_rows": 0, "full_day_volume_rows": 17402},
            NA, "missing",
            "ineligible: no phase-level capacity evidence; every strict attempt is unfilled:capacity_unproven",
            "eligible_with_label: full-day volume/amount can bound a liquidity band for diagnostics (order size vs daily amount), never an opening capacity",
            "assumption_required: a declared LiquidityCapacity(kind='predeclared_assumption', basis='hypothetical_participation_of_full_day_volume', assumption_ref=...) may be injected ONLY as a labelled hypothesis; it must not be described as opening capacity or as evidence",
            "Fill quantities in any replay are hypothetical; the honest strict result is zero proven fills (capacity_unproven). Daily volume is not opening capacity.",
            ()),
        row("R09_fees_effective_dates", "Fees (commission, transfer fee, stamp duty) with effective dates",
            "FeeSchedule(schedule_id, version, provenance in {hypothetical_fixture, sourced_verified}, source_ref, effective_from/to, applies_to_boards, rates, verification_ref) (kernel.FeeSchedule, kernel.fee_provenances)",
            [ev("metadata", "all three M4 freezes / acceptances: 'hypothetical fee schedules only'", "no sourced tariff document, effective date or verification_ref exists in the frozen evidence set"),
             ev("code", "kernel.FeeSchedule", "the kernel has no default rates; a sourced schedule needs verification_ref")],
            {"sourced_fee_schedules": 0, "effective_dated_tariff_documents": 0},
            NA, "missing",
            "ineligible: no sourced, effective-dated schedule; strict historical cost accounting is not possible",
            "not_applicable: bar diagnostics carry no fees",
            "assumption_required: provenance='hypothetical_fixture' schedule with declared effective window covering 2023-09-04..2025-03-31 and applies_to_boards; values are fixtures, never cited as real tariffs",
            "All replay PnL is conditional on fixture fees; sourcing official tariff notices (with dates) is a separate evidence task outside M4-03B.",
            ()),
        row("R10_marks_and_benchmark_alignment", "Valuation marks and benchmark alignment",
            "Mark(price, observed_at, available_at) with observed_at/available_at <= decided_at (risk.evidence_time); BenchmarkObservation levels on exactly the decision sessions (risk.benchmark)",
            [ev("table", "daily_bar_cache.close for stocks (marks) and for SH000001 / SH000300 (index levels, units not_applicable)", "756 index rows = 2 x 378 sessions, aligned one-to-one with the development calendar; stock closes on every price day"),
             ev("code", "reader.price_available_at_is_observed_at", "the M3 reader sets available_at = row_evidence.observed_at (2026 capture)"),
             ev("code", "labels.usable_retrospective", "retrospective mode counts availability violations instead of refusing; the M4 risk layer has no such mode")],
            {"stock_close_marks": 17402, "index_levels": 756, "benchmark_sessions_missing": 0},
            CAP, "present",
            "ineligible: every mark/level is available in 2026; the risk layer refuses them as future_evidence for any 2023-2025 decision instant",
            "eligible: closes and index levels align exactly per session; benchmark return diagnostics over the development window are computable",
            "eligible_with_label: inject marks with an assumed availability (trade_date close + declared offset) while keeping the 2026 capture instant in source_ref; the whole run is then 'assumed availability'",
            "Benchmark alignment is exact; availability is the blocker. Missing marks on halt days are explicit (valuation incomplete), not zero.",
            ("index volume/amount are retained uninterpreted aggregates (labels.benchmark_rows), never liquidity",)),
        row("R11_signal_input_cutoff", "Signal input cutoff and decision instant",
            "Decision.inputs[*].available_at <= decided_at (kernel.input_not_available_at_decision); decided_at >= session close and < next open; risk decisions consume only evidence with available_at <= decided_at",
            [ev("code", "reader.cutoff_offset / labels.usable_retrospective", "M3 convention close+3600s, retrospective; strict mode requires available_at <= as_of within 72h of the close"),
             ev("table", "row_evidence.observed_at", f"{audit['observed_at_min']} .. {audit['observed_at_max']} for all 27,900 rows"),
             ev("code", "labels.warmup_required", f"250-session warmup: {warm_depth[250]} stocks have 250 bars before the first development decision; partial {dict((s['symbol'], s['warmup_prices']) for s in stocks if 0 < s['warmup_prices'] < 250)}; 12 stocks have none")],
            {"rows_with_historical_availability": 0, "rows_with_2026_capture_availability": 27900, "stocks_with_full_warmup": warm_depth[250]},
            CAP, "assumption_only",
            "ineligible: zero inputs carry a historical availability instant; the kernel rejects input_not_available_at_decision for every real decision",
            "eligible: bar-based signals evaluated at the decision close are computable retrospectively",
            "eligible_with_label: assumed availability 'trade_date 15:00+08:00 + declared offset' for bars; the decision record must carry the assumption id and the true capture instant",
            "Strict PIT is false for the whole dataset (whole_record_strict_pit=false for 52 instruments); any signal replay is retrospective by construction.",
            ()),
        row("R12_frozen_universe_selection_bias", "Frozen universe and selection bias",
            "FrozenUniverse / UniverseMember fixed at construction; membership recorded, never inferred; results are pool-conditional",
            [ev("file", f"claude methods/_m1_closure/pilot_symbols.csv strata {dict(strata)}", "selected in 2026 by data-quality strata (suspected unit switch, BJ code history, IPO in window, largest interior gap, ordinary control) from then-listed securities"),
             ev("metadata", "metadata_index_01/index.json:instruments[*].pilot_selection_stratum; limits 'Pilot strata are selection provenance'", "strata are provenance, not a market-representative sample"),
             ev("metadata", "qualification_v2_reviewed.json:listing_depth_shortfalls (14 symbols)", "warmup depth shortfalls are structural")],
            {"stocks": 50, "strata": dict(strata), "largest_interior_gap_symbols": [r["symbol"] for r in pilot if r["stratum"] == "largest_interior_gap"]},
            ASM, "present",
            "ineligible: the pool is a 2026 survivor/quality-stratified selection; no strict claim about the market universe is possible",
            "eligible: pool-conditional diagnostics with the selection provenance attached",
            "eligible_with_label: replay on the frozen 50 with the bias statement; never widen the universe or drop symbols by result",
            "Any baseline trade count is a statement about this pool under its selection; 5 of 50 names were chosen for having the largest suspension gaps, 2 carry ST names in 2026.",
            ()),
    ]

    # ---------------------------------------------------------------- eligibility funnel (structural, metadata-derived; no price rows consumed)
    funnel = {
        "note": "structural counts from the frozen audit metadata; NOT execution eligibility counts (those need the authorized M4-03B read); no price row was consumed here",
        "symbol_sessions_in_development_calendar": 50 * 378,
        "listed_symbol_sessions": sum(s["expected_development_sessions"] for s in stocks),
        "price_keys": 17402, "confirmed_full_day_halt_keys": 152,
        "symbols_with_full_250_warmup": warm_depth[250], "symbols_with_partial_warmup": sum(1 for s in stocks if 0 < s["warmup_prices"] < 250), "symbols_with_zero_warmup": sum(1 for s in stocks if s["warmup_prices"] == 0),
        "known_ex_dates_inside_development": sum(len(v) for v in dev_events.values()),
        "strict_contemporaneous_execution_evidence_rows": 0,
        "phase_level_capacity_rows": 0,
        "sourced_fee_schedules": 0,
    }

    verdict_counts = Counter(r["verdict"] for r in requirements)
    strict_eligible = [r["id"] for r in requirements if r["modes"]["strict_historical_execution"].startswith("eligible")]
    summary = {
        "requirements": len(requirements), "verdicts": dict(verdict_counts), "strict_historical_execution_eligible_requirements": strict_eligible,
        "strict_historical_baseline_provable_now": False,
        "reason": "no frozen field carries a historical availability instant (all 27,900 rows observed 2026-09-09/10; suspension/listing/event facts assembled 2026-09-10); no phase-level capacity, band, ST or sourced fee evidence exists; the frozen kernel rejects such inputs as contemporaneous evidence",
        "retrospective_bar_diagnostics_possible": True,
        "hypothetical_replay_possible": "yes, under a declared assumption set (availability offset, board/lot/tick, not_st + assumed bands, bar-open/close prints, hypothetical capacity, fixture fees, adjustment uncertainty) and labelled as such in every record",
        "m4_historical_requirement": "unmet: 'at least one deliberately simple baseline generates expected non-zero trades ... on eligible historical data' cannot pass now; a truthful M4-03B result can only be an assumed-grade replay count plus the strict count 0",
        "codex_contract_gaps_to_note": [
            "the frozen kernel's InputAvailability and SessionCalendar carry no assumption kind; an assumed availability can only be labelled through source_ref and a run-level evidence grade",
            "the risk layer's evidence_time rule has no retrospective mode; replay decisions need injected (assumed) availability instants with the original capture instant preserved",
        ],
    }
    doc = {
        "schema": "m4.claude_03a.qualification.v1",
        "task_id": "M4-03A-HISTORICAL-QUALIFICATION-20260912",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_review",
        "path_root_convention": "relative to project root D:\\codex-A股交易, forward slashes",
        "development_window": [START, END], "validation_window_unused": list(VALIDATION), "final_holdout_unused": list(HOLDOUT),
        "modes": MODES,
        "verdict_vocabulary": {"present": "the field/path exists in the frozen stores or metadata for the development window with the stated availability semantics",
                               "assumption_only": "usable only as a declared, labelled assumption (no evidence with provenance for the exact requirement)",
                               "missing": "no evidence and no honest assumption path other than an explicit hypothetical label; absence of rows is never proof of no event"},
        "availability_vocabulary": {CAP: "value captured 2026-09-09/10 for a historical session (row_evidence.observed_at)", ASM: "fact assembled from documents in 2026 (metadata index assembled 2026-09-10T06:52:37Z)",
                                    NA: "no availability instant exists", "historical_contemporaneous": "available at the historical instant - present in no frozen field"},
        "pinned_sources": pins, "candidate_databases": dbs, "source_anchors": anchors,
        "facts": facts, "consistency": consistency, "requirements": requirements, "eligibility_funnel_structural": funnel, "summary": summary,
        "safety": {"sqlite_connections": 0, "network_requests": 0, "historical_trades_run": 0, "price_rows_consumed": 0, "review_only": True, "live_trading_enabled": False,
                   "training_eligible": False, "strict_pit": False, "M4_complete": False, "M3_complete": False, "M5_started": False},
    }
    (HERE / "qualification.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "QUALIFICATION_MATRIX.md").write_text(render_markdown(doc), encoding="utf-8")
    print(json.dumps({"requirements": len(requirements), "verdicts": dict(verdict_counts), "strict_eligible": strict_eligible, "anchors": len(anchors), "pins": len(pins)}, ensure_ascii=False))
    return 0


def render_markdown(doc: dict) -> str:
    f, s, c = doc["facts"], doc["summary"], doc["consistency"]
    L = []
    L.append("# M4-03A qualification matrix — development-period historical inputs versus the accepted execution / ledger / risk contracts\n")
    L.append("Task `M4-03A-HISTORICAL-QUALIFICATION-20260912`. Status **ready_for_review — static qualification, not acceptance.** Sources: the Codex development-input audit (`_m3_20260910/codex/development_input_audit_01`, result `dd3ac6ff…`, source `e785aaa2…`), the M3 metadata index (`14f1bad7…`), the M2 qualification bundle (`992bd79c…`), the pilot manifest (`97e251ae…`), the M3 reader / label modules (text and AST only) and the three accepted M4 modules (text only). This task opened **no SQLite connection**, ran **no historical trade**, consumed **no price row**; the two candidate databases were byte-hashed and stat-checked only (`trading.sqlite3` `c0b26660…` 38 969 344 B, `history.sqlite3` `eda17434…` 10 604 544 B, no sidecars). Machine-readable twin: `qualification.json` (same numbers, verified by `validate_qualification.py`).\n")
    L.append("## 1. Development evidence actually on file (from the authorized audit, not re-read)\n")
    L.append(f"* Window {f['development_window'][0]} … {f['development_window'][1]}: **{f['development_sessions']} sessions** (index calendar and audit agree). Validation {f['validation_window_unused'][0]}…{f['validation_window_unused'][1]} and holdout {f['final_holdout_unused'][0]}…{f['final_holdout_unused'][1]} untouched.")
    L.append(f"* Stock price rows **{f['stock_price_rows']}** + confirmed full-day halt keys **{f['confirmed_full_day_halt_keys']}** (5 symbols: {f['halts']['symbols']}; {f['halts']['sessions_with_halts']} sessions carry a halt); index rows **{f['index_rows']}** ({', '.join(f['index_symbols'])}, 378 each). Listed stocks {f['pool']['listed_at_first_session']} at the first session, {f['pool']['listed_at_last_session']} at the last; {', '.join(f['pool']['unlisted_throughout_development'])} list after the window. Minimum daily price availability among listed names {c['min_daily_price_availability']:.5f} (halts counted separately, never back-filled).")
    L.append(f"* Warmup before 2023-09-04: {f['warmup']['stock_rows_before_development']} stock rows, {f['warmup']['index_rows_before_development']} index rows; **{f['warmup']['stocks_with_250_bars_before_first_development_decision']} stocks** have the 250-bar depth the M3 policy requires, {f['warmup']['stocks_with_partial_depth']} are partial, {len(f['warmup']['stocks_with_zero_warmup'])} have none ({', '.join(f['warmup']['stocks_with_zero_warmup'])}); {f['warmup']['warmup_halt_keys']} warmup halt keys.")
    L.append(f"* Units: stocks `share` / `CNY`, indices `not_applicable`; adjustment `none` (vendor basis `unadjusted` verified for 52 scopes); one scoped price-domain exception (BJ920006 2023-12-04 block-trade total inside volume/amount).")
    L.append(f"* Availability: every row was observed **{f['capture']['observed_at_min']} … {f['capture']['observed_at_max']}** (2026 capture); suspension, listing and cash-event facts were assembled 2026-09-10. `original_historical_availability_proved=false`, `raw_vendor_value_accuracy_reproved=false`, `independent_market_source_corroboration=false`; both stores mirror one Tonghuashun capture. `source_name_status=invalid_source_name` for all 27 900 rows — names cannot establish historical ST; the pilot names `{f['pilot_names_containing_ST_2026_only']}` are 2026 names only.")
    ca = "; ".join(f"{k}: {len(v['all'])} cash events ({len(v['inside_development'])} inside development: {v['inside_development']})" for k, v in f["known_cash_events"].items())
    L.append(f"* Known corporate actions: {ca}; completeness `unknown` for all 52 instruments; no split / bonus / rights register.")
    L.append(f"* Listing evidence: {f['listing_evidence_kinds']}; pilot strata {f['pilot_strata']}; code-prefix groups {f['code_prefix_groups']} (boards are not declared anywhere in the frozen evidence).\n")
    L.append("## 2. Requirement matrix\n")
    L.append("Verdicts: `present` = exists for the development window with the stated availability; `assumption_only` = usable only as a declared, labelled assumption; `missing` = no evidence and no honest path other than an explicit hypothetical label. Availability: `retrospective_capture_2026` (row captured 2026-09-09/10), `evidence_assembly_2026` (documents assembled 2026-09-10), `not_established`. **No frozen field is `historical_contemporaneous`.** Modes: strict historical execution / retrospective bar diagnostics / hypothetical execution assumptions (definitions in `qualification.json:modes`).\n")
    L.append("| # | Requirement | Exact field / path / source line | Development coverage | Availability | Verdict | Strict historical execution | Retrospective bar diagnostics | Hypothetical execution assumptions | Consequence |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in doc["requirements"]:
        refs = "<br>".join(f"`{e['ref']}` — {e['detail']}" for e in r["evidence"])
        cov = "; ".join(f"{k}={v}" for k, v in r["development_coverage"].items())
        m = r["modes"]
        L.append(f"| {r['id']} | {r['requirement']}<br>*needs:* {r['accepted_contract_need']} | {refs} | {cov} | `{r['availability_semantics']}` | **{r['verdict']}** | {m['strict_historical_execution']} | {m['retrospective_bar_diagnostics']} | {m['hypothetical_execution_assumptions']} | {r['consequence']}" + (("<br>*" + "; ".join(r['notes']) + "*") if r['notes'] else "") + " |")
    L.append("\nSource-line anchors (path:line, re-checked by the validator): " + "; ".join(f"`{k}` → `{v['path']}:{v['line']}`" for k, v in doc["source_anchors"].items()) + "\n")
    L.append("## 3. Three answers Codex asked for\n")
    L.append(f"1. **Strict historical execution eligibility:** {len(s['strict_historical_execution_eligible_requirements'])} of {s['requirements']} requirements are strictly eligible. Structural funnel (metadata only, no price rows consumed): {doc['eligibility_funnel_structural']}. **A nonzero genuine historical baseline is not provable now** — {s['reason']}.")
    L.append("2. **Retrospective bar-based diagnostics:** possible for the 378 development sessions on the frozen pool (closes, index levels, halt exposure, would-have-crossed conditions, gap sizes) with `adjustment_uncertainty=true` everywhere, ST/band conditions reported as *possible*, and no fill claimed.")
    L.append(f"3. **Hypothetical execution assumptions:** {s['hypothetical_replay_possible']}. Such a replay yields *assumed-grade* fills and pool-conditional PnL; it can prove that the accepted engine is deterministic and non-degenerate on real bar shapes, not that a strategy executed historically.\n")
    L.append(f"**M4 historical requirement:** {s['m4_historical_requirement']}. A truthful missing result passes this qualification work but does not pass that requirement.\n")
    L.append("Contract gaps for Codex to weigh before M4-03B: " + " ".join(f"({i + 1}) {g}." for i, g in enumerate(s["codex_contract_gaps_to_note"])) + "\n")
    L.append("## 4. What was deliberately not done\n")
    L.append("* No `sqlite3.connect`, no SQL, no raw capture body, no new client capture, no Sina/other source; no eligibility count that would need a row read (the structural funnel above uses audit aggregates only).")
    L.append("* No synthetic field injected into real evidence; no 2026 `observed_at` moved into the past; daily volume never treated as opening capacity; no future close used for opening sizing.")
    L.append("* No accepted module, freeze, M2/M3 artifact, PLAN or coordination state touched; nothing staged or committed; automation unchanged.\n")
    L.append("Safety flags: `review_only=true`, `live_trading_enabled=false`, `training_eligible=false`, `strict_pit=false`, `M4_complete=false`, `M3_complete=false`, no M5.\n")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
