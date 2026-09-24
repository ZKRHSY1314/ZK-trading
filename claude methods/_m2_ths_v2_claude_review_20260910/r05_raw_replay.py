"""R05 - independent raw-capture replay against both candidate stores.

Loads the pinned pure parser module (backend/app/data/tonghuasun_history.py, stdlib-only
imports) by file path - never the `app` package - and re-parses every retained response
body named in the reviewed v2 bundle. Rebuilds the expected per-row values from the raw
bytes alone, then compares every OHLCVA value, adjustment/source/unit/quality field and
the full row_evidence lineage against both stores (mode=ro, query_only). Recomputes the
bundle's row_records_sha256 from raw replay + capture receipts. Also checks the three
warmup extensions (overlap equality, added-row selection) and the source-name diagnostics.
Writes r05_raw_replay.json.
"""
import hashlib
import importlib.util
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CM = HERE.parent
PROJECT = CM.parent
PHASE = CM / "_m2_codex_implementation_20260910"
RUN_ID = "ths_v2_20260910_041710_97ef9c09"
RUN = PHASE / "staging_runs" / RUN_ID / f"run_{RUN_ID}"
PARSER = PROJECT / "backend/app/data/tonghuasun_history.py"
PARSER_PIN = "605d65965b1aee56f0f64c5c2446078aefa8d237d7a3d09b5f7403e4a24c2779"
QUAL = PHASE / "qualification_v2_reviewed.json"
QUAL_PIN = "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37"
BENCHMARKS = {"SH000300": ("USZI399300", "399300.SZ"), "SH000001": ("USHI1A0001", "10001.SH")}
NUM = ("open", "high", "low", "close", "volume", "amount")
WS, WE, RS, RE, EARLY = "2022-08-24", "2023-09-01", "2023-09-04", "2026-09-04", "2022-05-01"
EXTEND = ("SZ002656", "SH600110", "SH600226")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hv(v):
    return hashlib.sha256(canonical(v).encode("utf-8")).hexdigest()


def observed_utc(value):
    m = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return m.astimezone(timezone.utc).isoformat()


def ro(path):
    conn = sqlite3.connect("file:" + quote(Path(path).as_posix(), safe="/:") + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def load_parser():
    assert sha(PARSER) == PARSER_PIN, "parser pin mismatch"
    spec = importlib.util.spec_from_file_location("ths_history_pure", PARSER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ths_history_pure"] = mod  # dataclass + postponed annotations need the module registered
    spec.loader.exec_module(mod)
    return mod


def spec_for(parser, symbol):
    if symbol in BENCHMARKS:
        host, code = BENCHMARKS[symbol]
        return parser.SecuritySpec.benchmark(symbol, host_full_code=host, response_full_code=code,
                                             mapping_evidence="frozen_official_index_mapping")
    if symbol == "SH600289":
        ev = "5ad4d502d552933d4f20f54abfa1c7b17b01ea19790bc42a34a56ee80304b1d0"
        assert sha(PHASE / "identity_search_600289/response.bin") == ev, "600289 mapping evidence changed"
        return parser.SecuritySpec.stock(symbol, host_full_code="USHT600289", mapping_evidence=ev)
    return parser.SecuritySpec.stock(symbol)


def main():
    assert sha(QUAL) == QUAL_PIN, "qualification pin mismatch"
    qual = json.load(open(QUAL, encoding="utf-8"))
    parser = load_parser()
    out = {"parser_sha256": sha(PARSER), "qualification_sha256": sha(QUAL), "problems": [], "scopes": {},
           "opened": [], "name_diagnostics": Counter(), "raw_name_samples": []}
    replayed = []           # records rebuilt exactly as the bundle would build them
    values_by_key = {}      # (symbol, date) -> tuple of 6 floats
    for scope in qual["scopes"]:
        sym = scope["symbol"]
        spec = spec_for(parser, sym)
        rows_by_date = {}
        srec = {"captures": [], "expected_price_dates": len(scope["expected_price_dates"])}
        for i, cap in enumerate(scope["captures"]):
            d = PHASE / cap["directory"]
            n = cap["job_id"]
            raw = d / f"response_{n}.bin"
            receipt = json.load(open(d / f"completed_{n}.json", encoding="utf-8"))
            plan = json.load(open(d / "plan.json", encoding="utf-8"))
            job = receipt["job"]
            crec = {"directory": cap["directory"], "job_id": n, "raw_sha256_match": sha(raw) == cap["raw_sha256"] == receipt["raw_sha256"],
                    "receipt_sha256_match": sha(d / f"completed_{n}.json") == cap["capture_receipt_sha256"],
                    "manifest_sha256_match": sha(d / "producer_pins.json") == cap["capture_producer_manifest_sha256"],
                    "request_sha256_match": hv(job["payload"]) == cap["request_sha256"],
                    "job_in_plan": job in plan["jobs"], "job_symbol": job["symbol"] == sym and job["id"] == n,
                    "http_200": receipt["http_status"] == 200 and receipt.get("stop_reason") is None,
                    "observed_at_match": observed_utc(receipt["observed_at"]) == cap["observed_at"],
                    "producer_sha256_match": sha(PHASE / scope_entry_point(qual, scope, i)) == cap["producer_sha256"] if scope_entry_point(qual, scope, i) else None,
                    "parser_sha256_match": cap["parser_sha256"] == PARSER_PIN}
            for k, v in crec.items():
                if v is False:
                    out["problems"].append(f"{sym}:capture{i}:{k}")
            decoded = parser.parse_history_response(raw.read_bytes(), spec, cap["start"], cap["end"])
            crec["rows"] = len(decoded["rows"]); crec["rows_match_bundle"] = len(decoded["rows"]) == cap["rows"]
            crec["response_identity_match"] = decoded["response_identity"] == cap["response_identity"]
            crec["response_adjustment"] = decoded.get("response_adjustment"); crec["requested_adjustment"] = decoded.get("requested_adjustment")
            crec["vendor_basis_from_parser"] = decoded["vendor_basis"]; crec["eligible_from_parser"] = decoded["eligible"]
            if not crec["rows_match_bundle"] or not crec["response_identity_match"]:
                out["problems"].append(f"{sym}:capture{i}:rows_or_identity")
            diag = {x["row_index"]: x["code"] for x in decoded["name_diagnostics"]}
            capture_ref = dict(raw_sha256=sha(raw), request_sha256=hv(job["payload"]), producer_sha256=cap["producer_sha256"],
                               parser_sha256=PARSER_PIN, capture_receipt_sha256=sha(d / f"completed_{n}.json"),
                               capture_producer_manifest_sha256=sha(d / "producer_pins.json"), observed_at=observed_utc(receipt["observed_at"]))
            recs = []
            for j, row in enumerate(decoded["rows"]):
                out["name_diagnostics"][diag.get(j, "source_name_observed")] += 1
                if len(out["raw_name_samples"]) < 5 and row.get("raw_security_name") is not None:
                    out["raw_name_samples"].append({"symbol": sym, "date": row["date"], "raw_security_name": repr(row["raw_security_name"])[:80]})
                recs.append(dict(symbol=sym, trade_date=row["date"], source="tonghuashun", **{f: row[f] for f in NUM}, **capture_ref,
                                 point_index=j, source_name=row["source_name"], source_name_status=diag.get(j, "source_name_observed")))
            crec["date_range"] = (decoded["first_date"], decoded["last_date"])
            srec["captures"].append(crec)
            if i == 0:
                rows_by_date = {r["trade_date"]: r for r in recs}
                original = dict(rows_by_date)
            else:
                # extension: overlap must be value-identical; add only selected dates not already present
                overlap = [r for r in recs if r["trade_date"] in original]
                mism = [r["trade_date"] for r in overlap if any(r[f] != original[r["trade_date"]][f] for f in NUM)]
                crec["overlap_rows"] = len(overlap); crec["overlap_value_mismatches"] = mism
                if mism:
                    out["problems"].append(f"{sym}:extension_overlap_mismatch:{mism[:5]}")
                selected = set(scope["expected_price_dates"])
                added = [r for r in recs if r["trade_date"] in selected and r["trade_date"] not in original]
                crec["added_rows"] = len(added)
                for r in added:
                    rows_by_date[r["trade_date"]] = r
        expected = set(scope["expected_price_dates"])
        chosen = [rows_by_date[d] for d in sorted(rows_by_date) if d in expected]
        srec["rows_selected"] = len(chosen)
        if {r["trade_date"] for r in chosen} != expected:
            out["problems"].append(f"{sym}:selected_dates_ne_expected")
        for r in chosen:
            values_by_key[(sym, r["trade_date"])] = tuple(r[f] for f in NUM)
        replayed.extend(chosen)
        out["scopes"][sym] = srec
    replayed.sort(key=lambda r: (r["symbol"], r["trade_date"]))
    out["replayed_rows"] = len(replayed)
    out["row_records_sha256_recomputed"] = hv(replayed)
    out["row_records_sha256_bundle"] = qual["row_records_sha256"]
    out["row_records_sha256_match"] = out["row_records_sha256_recomputed"] == qual["row_records_sha256"]
    out["name_diagnostics"] = dict(out["name_diagnostics"])

    # compare with both stores
    for role, path, table, srccol in (("trading", RUN / "trading.sqlite3", "daily_bar_cache", "source"),
                                      ("history", RUN / "history.sqlite3", "daily_bars", "provider")):
        conn = ro(path); out["opened"].append(str(path))
        try:
            rows = conn.execute(f"SELECT symbol,trade_date,open,high,low,close,volume,amount,adjustment_mode,{srccol} FROM {table} ORDER BY symbol,trade_date").fetchall()
            st = {"rows": len(rows), "value_mismatches": [], "extra_keys": [], "missing_keys": 0, "adjustment_modes": Counter(), "sources": Counter(), "field_comparisons": 0}
            seen = set()
            for r in rows:
                key = (r[0], r[1]); seen.add(key)
                st["adjustment_modes"][r[8]] += 1; st["sources"][r[9]] += 1
                exp = values_by_key.get(key)
                if exp is None:
                    st["extra_keys"].append(key); continue
                st["field_comparisons"] += 6
                if tuple(r[2:8]) != exp:
                    st["value_mismatches"].append({"key": key, "store": r[2:8], "raw": exp})
            st["missing_keys"] = len(set(values_by_key) - seen)
            st["adjustment_modes"] = dict(st["adjustment_modes"]); st["sources"] = dict(st["sources"])
            if role == "trading":
                st["quality_status"] = dict(Counter(x[0] for x in conn.execute("SELECT quality_status FROM daily_bar_cache")))
                st["volume_unit_by_class"] = conn.execute("SELECT volume_unit, COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1").fetchall()
                lineage = conn.execute("SELECT symbol,trade_date,raw_sha256,request_sha256,producer_sha256,parser_sha256,capture_receipt_sha256,capture_producer_manifest_sha256,observed_at,point_index,qualification_sha256,source_name,source_name_status FROM row_evidence ORDER BY symbol,trade_date").fetchall()
                qrec = {s: hv(sc) for s, sc in ((sc["symbol"], sc) for sc in qual["scopes"])}
                exp_lineage = [(r["symbol"], r["trade_date"], r["raw_sha256"], r["request_sha256"], r["producer_sha256"], r["parser_sha256"],
                                r["capture_receipt_sha256"], r["capture_producer_manifest_sha256"], r["observed_at"], r["point_index"],
                                qrec[r["symbol"]], r["source_name"], r["source_name_status"]) for r in replayed]
                st["lineage_rows"] = len(lineage); st["lineage_match"] = lineage == exp_lineage
                if not st["lineage_match"]:
                    diffs = [(a, b) for a, b in zip(lineage, exp_lineage) if a != b][:3]
                    st["lineage_diff_sample"] = [{"store": a, "raw": b} for a, b in diffs]
                    out["problems"].append(f"{role}:lineage_mismatch")
                # stored qualification records must equal the reviewed scopes
                stored_q = conn.execute("SELECT symbol,record_sha256,record_json FROM qualification_records ORDER BY symbol").fetchall()
                exp_q = sorted((sc["symbol"], hv(sc), canonical(sc)) for sc in qual["scopes"])
                st["qualification_records_match"] = stored_q == exp_q
                if not st["qualification_records_match"]:
                    out["problems"].append("trading:qualification_records_mismatch")
                st["ingest_provenance"] = conn.execute("SELECT instrument_class, declared_basis, derived_basis, derived_unit, run_mode, COUNT(*) FROM ingest_provenance GROUP BY 1,2,3,4,5").fetchall()
                st["source_name_null_rows"] = conn.execute("SELECT COUNT(*) FROM row_evidence WHERE source_name IS NULL").fetchone()[0]
            if st["value_mismatches"] or st["extra_keys"] or st["missing_keys"]:
                out["problems"].append(f"{role}:value_or_key_mismatch")
            out[f"store_{role}"] = st
        finally:
            conn.close()
    json.dump(out, open(HERE / "r05_raw_replay.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)
    print("parser pin ok; replayed rows:", out["replayed_rows"])
    print("row_records_sha256 recomputed:", out["row_records_sha256_recomputed"])
    print("row_records_sha256 bundle    :", out["row_records_sha256_bundle"], "match:", out["row_records_sha256_match"])
    print("name diagnostics:", out["name_diagnostics"]); print("raw name samples:", out["raw_name_samples"][:3])
    for role in ("trading", "history"):
        s = out[f"store_{role}"]
        print(f"{role}: rows={s['rows']} field_comparisons={s['field_comparisons']} value_mismatches={len(s['value_mismatches'])} extra={len(s['extra_keys'])} missing={s['missing_keys']} adj={s['adjustment_modes']} src={s['sources']}")
        if role == "trading":
            print("   lineage rows", s["lineage_rows"], "match", s["lineage_match"], "| qualification_records match", s["qualification_records_match"],
                  "| quality", s["quality_status"], "| units", s["volume_unit_by_class"], "| source_name NULL rows", s["source_name_null_rows"])
            print("   ingest_provenance:", s["ingest_provenance"])
    ext = {sym: [c for c in v["captures"] if "added_rows" in c] for sym, v in out["scopes"].items() if sym in EXTEND}
    for sym, caps in ext.items():
        for c in caps:
            print(f"extension {sym}: captured={c['rows']} overlap={c['overlap_rows']} overlap_mismatches={len(c['overlap_value_mismatches'])} added={c['added_rows']} range={c['date_range']}")
    adj = Counter((c["requested_adjustment"], c["response_adjustment"]) for v in out["scopes"].values() for c in v["captures"])
    print("requested/response adjustment across captures:", dict(adj))
    print("problems:", out["problems"])
    return 0 if not out["problems"] and out["row_records_sha256_match"] else 1


def scope_entry_point(qual, scope, i):
    # capture 0 uses the scope's original collector; the extension uses collect_warmup3.py
    if i == 0:
        prior = json.load(open(PHASE / "qualification_pilot52.json", encoding="utf-8"))
        return {s["symbol"]: s["collector_entrypoint"] for s in prior["scopes"]}[scope["symbol"]]
    return "collect_warmup3.py"


if __name__ == "__main__":
    sys.exit(main())
