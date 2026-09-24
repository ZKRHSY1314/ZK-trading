"""Read-only independent review of boundary-1b run 20260908T082833Z.

No HTTP capture, SQLite opens, service operations or evidence writes.
Exit 0 means the diagnostic assertions reproduced, NOT source capability PASS.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_m2b_d1d2 as prior

RUN = prior.SMOKE / "evidence_20260908T082833Z"
FROZEN = prior.SMOKE / "frozen_impl_20260908_d1d2_accepted"
PINS = {
    "smoke_capture.py": "0ed93f05a8d8ab87da7dc57fa4c9c874806cc04d57b7ed93e53617cedc27daa2",
    "test_m2_smoke.py": "d14a4f9822b8b249afe2366fc82eea80f1e9ed78de6e208c4b13c569e669df37",
    "sina_klc_decoder.py": "d39e02c8cd736e10c29ae6efc12ce540eeadf790552dcdc14debcf5f18461fee",
    "smoke_checks.py": "b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c",
    "smoke_outcomes.py": "53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e",
}


def main():
    results, observations = [], {}

    def check(name, actual, expected=True):
        results.append({"name": name, "actual": actual, "expected": expected,
                        "pass": actual == expected})

    directories = [p for p in prior.SMOKE.iterdir() if p.is_dir()]
    before = {p.name: prior.tree(p) for p in directories}
    db_before = prior.db_metadata()
    manifest = json.loads((RUN / "capture_manifest.json").read_text("utf-8"))
    stored = json.loads((RUN / "checks.json").read_text("utf-8"))
    reference = json.loads((RUN / "reference/reference_extract.json").read_text("utf-8"))
    for name, pin in PINS.items():
        check("accepted source: " + name, prior.digest(prior.SMOKE / name), pin)
        check("frozen source: " + name, prior.digest(FROZEN / name), pin)
    check("ten retained evidence files", len(before[RUN.name]), 10)
    check("run completed", manifest["run_status"], "completed")
    check("capture invalidation set empty", manifest["invalidating_changes"], [])
    attempts = manifest["attempts"]
    check("five attempts", len(attempts), 5)
    check("no retries", [a["attempt_no"] for a in attempts], [1] * 5)
    check("five HTTP 200", [a["status"] for a in attempts], [200] * 5)
    gaps = [round(b["started_at_monotonic"] - a["started_at_monotonic"], 6)
            for a, b in zip(attempts, attempts[1:])]
    check("all actual wire gaps >= 1.5 seconds", all(g >= 1.5 for g in gaps))
    starts = [dt.datetime.fromisoformat(a["started_at_utc"].replace("Z", "+00:00"))
              .astimezone(dt.timezone(dt.timedelta(hours=8))) for a in attempts]
    check("all recorded wire starts in approved window",
          all(x.date().isoformat() == "2026-09-08" and x.time() > dt.time(15, 30)
              for x in starts))
    observations["wire"] = {"starts_shanghai": [x.isoformat() for x in starts],
                            "gaps_sec": gaps, "first_to_fifth_sec": sum(gaps),
                            "capture_inventory": manifest["environment"]["process_inventory_size"]}
    expected = prior.cap.expected_requests(manifest["environment"]["adapter_constants"])
    check("URLs match accepted plan", [r["requested_url"] for r in manifest["requests"]],
          [r["url"] for r in expected])
    bodies = {}
    for record in manifest["requests"]:
        path = RUN / "raw" / record["raw_file"]
        check("raw hash request " + str(record["index"]), prior.digest(path), record["body_sha256"])
        check("raw byte count request " + str(record["index"]), path.stat().st_size, record["bytes"])
        bodies[record["requested_url"]] = (path.read_bytes(), record["encoding"])

    with prior.cap.no_remote_connections("Codex run-2 offline review"), \
            prior.cap.db_guard("Codex review forbids every SQLite open"):
        replay = prior.chk.replay(RUN)
        check("exact stored replay", replay["matches_stored"])
        check("deterministic hash", replay["deterministic_sha256"],
              "8ffb30b06a70aee4d301f4d7cea53c34e0ea8374dc0587d69b8848cb4f2ed5c2")
        check("capability remains FAIL", replay["deterministic"]["verdicts"]["capability"], "FAIL")
        observations["replayed_capability"] = replay["deterministic"]["verdicts"]
        observations["reproduced_failures"] = [c for c in replay["deterministic"]["checks"]
                                                if c["status"] == "FAIL"]
        observations["decoded"] = {}
        calendar, _ = prior.chk.load_calendar(prior.cap.CALENDAR)
        expected_window = {d for d in calendar if prior.cap.WARMUP_START <= d <= prior.cap.RESEARCH_END}
        check("accepted warmup plus research calendar sessions", len(expected_window), 978)
        for record, count in ((manifest["requests"][0], 5935),
                              (manifest["requests"][2], 5987),
                              (manifest["requests"][3], 1393)):
            payload = prior.dec.decode_klc(*bodies[record["requested_url"]], routine=prior.cons.hk_js_decode)
            rows = payload["rows"]
            dates = [r["date"] for r in rows]
            name = record["job"]
            check("decoded row count: " + name, len(rows), count)
            check("unique ordered dates: " + name, dates, sorted(set(dates)))
            check("pinned calendar coverage: " + name, sorted(expected_window - set(dates)), [])
            digit_check = "".join(c for c in payload["js_variable"] if c.isdigit())
            observations["decoded"][name] = {"rows": len(rows), "first": dates[0], "last": dates[-1],
                                              "variable": payload["js_variable"],
                                              "current_D1_digit_string": digit_check,
                                              "pinned_window_dates": len(set(dates) & expected_window)}
            if name != "sh000300":
                check("stock D1 prefix false rejection: " + name, digit_check not in name)
                local = reference["rows"][name.upper()]
                by_date = {r["date"]: r for r in rows}
                overlap = sorted((r for r in local if r["trade_date"] in by_date
                                  and r.get("volume") and r.get("amount")),
                                 key=lambda r: r["trade_date"])[-10:]
                ratios = {"volume": [float(by_date[r["trade_date"]]["volume"]) / float(r["volume"])
                                      for r in overlap],
                          "amount": [float(by_date[r["trade_date"]]["amount"]) / float(r["amount"])
                                     for r in overlap]}
                check("ten usable overlap sessions: " + name, len(overlap), 10)
                check("volume ratio 100: " + name, all(abs(r - 100) < 1e-8 for r in ratios["volume"]))
                # Use the accepted +/-1% currency check, not exact float equality.
                # The raw stock values differ from 1 by at most about 1.4e-8.
                check("amount ratio within accepted 1%: " + name,
                      all(abs(r - 1) <= prior.chk.AMOUNT_TOL_REL for r in ratios["amount"]))
                observations["decoded"][name]["overlap_ratios"] = ratios

        observations["auxiliary"] = {}
        for record in (manifest["requests"][1], manifest["requests"][4]):
            content, encoding = bodies[record["requested_url"]]
            text = prior.dec.bytes_to_text(content, encoding)
            # Diagnostic JSON inspection only: never evaluate the remote wrapper/comment.
            data = json.loads(text[text.index("["):text.rindex("]") + 1])
            zeroes = [r for r in data if r["amount"] == 0]
            try:
                prior.dec.parse_outstanding_share(content, encoding)
            except prior.dec.DecodeError as exc:
                error = str(exc)
            else:
                error = None
            check("object-array rejection reproduced: " + record["job"],
                  error is not None and "not a [date, value] pair" in error)
            pairs = json.dumps([[r["date"], r["amount"]] for r in data]).encode()
            try:
                normalized = prior.dec.parse_outstanding_share(pairs, "utf-8")
                pair_result = {"rows": len(normalized)}
            except prior.dec.DecodeError as exc:
                pair_result = {"error": str(exc)}
            if record["job"] == "bj920000":
                check("two BJ zero observations", len(zeroes), 2)
                check("BJ zero observations precede research/warmup",
                      all(r["date"] < prior.cap.WARMUP_START for r in zeroes))
                check("shape conversion alone still fails BJ", "non-positive" in pair_result.get("error", ""))
            observations["auxiliary"][record["job"]] = {
                "entry_count": len(data), "object_keys": sorted(data[0]), "zero_rows": zeroes,
                "current_parser_error": error, "pair_shape_only_diagnostic": pair_result}

        calls = [(j["job"], "stock", "stock_zh_a_daily",
                  (j["adapter_symbol"], prior.cap.WINDOW_START.replace("-", ""),
                   prior.cap.WINDOW_END.replace("-", ""))) if j["instrument_class"] == "stock"
                 else (j["job"], "index", "stock_zh_index_daily", (j["adapter_symbol"],))
                 for j in prior.cap.JOBS]
        corrected_args = prior.chk.adapter_replay(bodies, calls)
        observations["explicit_dates_diagnostic"] = {
            name: {key: value for key, value in item.items() if key != "dates"}
            for name, item in corrected_args.items() if name != "_requested_urls"}
        check("explicit-date diagnostic reaches all three adapters",
              sorted(observations["explicit_dates_diagnostic"]), ["bj920000", "sh000300", "sh600011"])
        check("explicit-date diagnostic uses captured URLs only",
              set(corrected_args["_requested_urls"]).issubset(bodies))
        observations["explicit_dates_diagnostic_not_implementation_fix"] = True

    check("all retained trees unchanged", {p.name: prior.tree(p) for p in directories}, before)
    check("production metadata unchanged", prior.db_metadata(), db_before)
    failed = [r for r in results if not r["pass"]]
    print(json.dumps({"assertions": len(results), "passed": len(results) - len(failed),
                      "failures": failed, "observations": observations,
                      "evidence_hashes": before[RUN.name], "production_metadata": db_before},
                     ensure_ascii=False, indent=2))
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
