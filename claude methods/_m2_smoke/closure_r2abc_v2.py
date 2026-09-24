"""Closure driver for `revision_20260908T082833Z_r2abc_v2` (the R2-ABC C1/C2 round).

Separately versioned on purpose. Codex's `review_m2b_r2abc.py` is pinned to the PREVIOUS
revision and stays unchanged; running it after these corrections must - and does - report
a cross-version producer-pin and hash mismatch against that older revision. That
disagreement is a fact to report, not something to erase, so it is asserted here
explicitly rather than silenced.

Read-only. No HTTP, no SQLite open, no service action, no write to any retained
directory: the connection and database guards are held over every step that touches the
implementation, and every retained tree is hashed before and after.

Exit 1 means a closure expectation failed, not that this driver crashed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pandas                                          # noqa: E402  (before the guard)
import smoke_capture as cap                            # noqa: E402
import smoke_checks as chk                             # noqa: E402
import sina_klc_decoder as dec                         # noqa: E402

REVISION = HERE / "revision_20260908T082833Z_r2abc_v2"
PRIOR = HERE / "revision_20260908T082833Z_r2abc"
PARENT = HERE / "evidence_20260908T082833Z"
PRODUCERS = ("smoke_capture.py", "smoke_checks.py", "smoke_outcomes.py",
             "sina_klc_decoder.py", "test_m2_smoke.py")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path):
    return {p.relative_to(path).as_posix(): digest(p)
            for p in sorted(path.rglob("*")) if p.is_file()}


def db_metadata():
    return {p.name: {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns}
            for p in (cap.TRADING_DB, cap.MARKET_DB, cap.MARKET_WAL) if p.exists()}


def main():
    results = []

    def check(name, expected, actual):
        results.append(dict(name=name, expected=expected, actual=actual,
                            passed=actual == expected))

    retained = [p for p in HERE.iterdir() if p.is_dir() and p.name.startswith(
        ("evidence_", "revision_", "receipts_", "frozen_impl_"))]
    before = {p.name: tree(p) for p in retained}
    db_before = db_metadata()

    provenance = json.loads((REVISION / "PROVENANCE.json").read_text("utf-8"))
    pins = provenance["producer_implementation"]
    check("current implementation matches this revision's producer pins", pins,
          {name: digest(HERE / name) for name in pins})
    for relative, sha in provenance["input_hashes"].items():
        check("parent input pin: " + relative, sha, digest(PARENT / relative))
        check("revision input pin: " + relative, sha, digest(REVISION / relative))

    # The cross-version disagreement, asserted as such: the prior revision is preserved
    # byte-for-byte and its pins no longer describe the current implementation.
    prior = json.loads((PRIOR / "PROVENANCE.json").read_text("utf-8"))
    changed = provenance["cross_version_producer_pins"]["changed"]
    check("the superseded revision's pins are recorded as changed, not rewritten",
          {name: prior["producer_implementation"][name] for name in changed},
          {name: changed[name]["accepted_in_" + PRIOR.name] for name in changed})
    check("the superseded revision still carries its own accepted hash",
          prior["revised_offline_result"]["deterministic_sha256"],
          json.loads((PRIOR / "checks.json").read_text("utf-8"))["deterministic_sha256"])
    check("this revision's hash differs from the superseded one", True,
          provenance["revised_offline_result"]["deterministic_sha256"]
          != prior["revised_offline_result"]["deterministic_sha256"])

    with cap.no_remote_connections("the R2-ABC closure driver must not reach a host"), \
            cap.db_guard("the R2-ABC closure driver must not open a database"):
        replay = chk.replay(REVISION)
        check("independent offline replay equals the stored checks", True,
              replay["matches_stored"])
        check("independent deterministic hash",
              provenance["revised_offline_result"]["deterministic_sha256"],
              replay["deterministic_sha256"])
        deterministic = replay["deterministic"]
        check("capability remains FAIL", "FAIL",
              deterministic["verdicts"]["capability"])
        check("EV6 stays visible as the only failing gate",
              [("EV6", "sh600011"), ("EV6", "bj920000")],
              [(c["id"], c["symbol"]) for c in deterministic["checks"]
               if c["status"] == "FAIL"])
        for c in deterministic["checks"]:
            if c["id"] in ("D1", "D5", "R1"):
                check(c["id"] + " on the retained bytes: " + c["symbol"], "PASS",
                      c["status"])

        # ---- C1: an explicit invalid observation interrupts denominator validity ----
        body = (b'var KKE_ShareAmount_sh600011 = ('
                b'[{"date":"2020-01-01","amount":100},'
                b'{"date":"2020-01-03","amount":0},'
                b'{"date":"2020-01-05","amount":200}]);')
        rows = dec.parse_outstanding_share(body, None, expected_symbol="sh600011")
        check("the zero is preserved in the series with its reason",
              [(r["date"], r["outstanding_share_wan"], r["usable"]) for r in rows],
              [("2020-01-01", 100.0, True), ("2020-01-03", 0.0, False),
               ("2020-01-05", 200.0, True)])
        check("an older count is not restored on the zero's own date", None,
              dec.outstanding_share_as_of(rows, "2020-01-03"))
        check("... nor on any day the zero remains in force", None,
              dec.outstanding_share_as_of(rows, "2020-01-04"))
        check("a later valid observation restores the denominator", 200.0,
              dec.outstanding_share_as_of(rows, "2020-01-05")["outstanding_share_wan"])
        check("the value in force before the zero is unaffected", 100.0,
              dec.outstanding_share_as_of(rows, "2020-01-02")["outstanding_share_wan"])
        check("nothing is ever backfilled from the future", None,
              dec.outstanding_share_as_of(rows, "2019-12-31"))
        quality = dec.share_series_quality(rows, ("2020-01-04", "2020-01-05"))
        check("coverage cannot bridge an explicit invalid observation", False,
              quality["covers_window_start"])
        check("the withheld zero stays visible in the quality summary",
              ("2020-01-03", 0.0, False),
              (quality["state_at_window_start"]["date"],
               quality["state_at_window_start"]["outstanding_share_wan"],
               quality["state_at_window_start"]["usable"]))
        check("the invalid interval is reported with the date that restores validity",
              [("2020-01-03", "2020-01-05")],
              [(s["from"], s["until"])
               for s in quality["invalid_denominator_intervals"]])
        check("the installed pandas ffill agrees: an explicit zero is kept",
              [100.0, 0.0, 0.0, 200.0],
              pandas.Series([100.0, 0.0, None, 200.0]).ffill().tolist())

        # ---- C2: R1 validates the actual returned dates ----------------------------
        forged = dict(rows=1, first_date="2023-01-03", last_date=None, dates=[])
        check("R1 rejects row metadata with no actual date sequence", "FAIL",
              chk._replay_verdict(forged, [], False, None)[0])
        real = ["2023-01-03", "2023-01-04", "2023-01-05"]
        good = dict(rows=3, first_date=real[0], last_date=real[-1], dates=real)
        check("R1 accepts an internally consistent stock result", "PASS",
              chk._replay_verdict(good, [], False, None)[0])
        check("R1 rejects a row count that disagrees with the returned dates", "FAIL",
              chk._replay_verdict(dict(good, rows=978), [], False, None)[0])
        check("R1 rejects first/last metadata that does not bound the sequence", "FAIL",
              chk._replay_verdict(dict(good, last_date=None), [], False, None)[0])
        outside = ["2019-01-02", "2023-01-03"]
        drifted = dict(rows=2, first_date=outside[0], last_date=outside[-1],
                       dates=outside)
        check("the declared stock window binds the stock replay", "FAIL",
              chk._replay_verdict(drifted, [], False, None)[0])
        check("... and is not imposed on the index's full-series interface", "PASS",
              chk._replay_verdict(drifted, [], False, None, window=None,
                                  label="index adapter")[0])
        check("the index interface is still held to a real date sequence", "FAIL",
              chk._replay_verdict(forged, [], False, None, window=None)[0])

    check("every retained tree is unchanged by this driver", before,
          {p.name: tree(p) for p in retained})
    check("production database size and mtime unchanged", db_before, db_metadata())

    for result in results:
        if result["passed"]:
            print("[PASS] " + result["name"])
        else:
            print("[FAIL] " + json.dumps(result, ensure_ascii=False, default=str))
    print(json.dumps(dict(revision=REVISION.name,
                          total=len(results),
                          passed=sum(r["passed"] for r in results),
                          failed=sum(not r["passed"] for r in results),
                          retained_directories=len(retained),
                          replay_sha256=replay["deterministic_sha256"],
                          capability=deterministic["verdicts"]["capability"],
                          per_job=deterministic["verdicts"]["per_job"],
                          ev6=[{"symbol": c["symbol"], "status": c["status"],
                                "detail": c["detail"]}
                               for c in deterministic["checks"] if c["id"] == "EV6"]),
                     ensure_ascii=False, indent=2))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
