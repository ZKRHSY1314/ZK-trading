"""Focused offline checks for the r2 G-3 analysis: G3-R1 validity, G3-R2 changes.

`V-` exercises the single price validator, `A-` drives the **public `analyse()`** path with
invalid prices on both sides, `C-` covers consecutive-usable-date ratio changes, and `R-`
validates against the retained artifacts.

Offline only: no network, no SQLite, no adapter replay, no capture, no production write.
Every guarded directory - including the preserved r1 analysis - is hashed before and after.
These checks measure; they define no threshold and attribute no corporate action.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE.parent
for path in (str(HERE), str(SMOKE)):
    if path not in sys.path:
        sys.path.insert(0, path)
import smoke_capture as cap                                       # noqa: E402
import g3_ratio_analysis as g3                                    # noqa: E402

_GUARD = cap.no_remote_connections("the r2 G-3 suite attempted a network connection")
_GUARD.__enter__()

GUARDED = tuple(sorted(p for p in SMOKE.iterdir() if p.is_dir() and p != HERE
                       and p.name.startswith(("evidence_", "revision_", "receipts_",
                                              "frozen_impl_", "basis_eval_",
                                              "g3_ratio_analysis_20260909"))))
CASES = []
_LOADED = {}
INVALID_PRICES = [("null", None), ("boolean_true", True), ("boolean_false", False),
                  ("nonnumeric_string", "12.30"), ("empty_string", ""),
                  ("nan", float("nan")), ("positive_infinity", float("inf")),
                  ("negative_infinity", float("-inf")), ("zero", 0.0),
                  ("negative", -1.5)]


def case(name):
    def wrap(fn):
        CASES.append((name, fn))
        return fn
    return wrap


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def retained():
    if not _LOADED:
        manifest, extract, vendor = g3.load_inputs()
        _LOADED["results"] = g3.analyse(manifest, extract, vendor)
    return _LOADED["results"]


DATES = ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07"]


def ref(date, close, source="src", updated_at="t1"):
    return {"trade_date": date, "close": close, "source": source,
            "updated_at": updated_at, "adjustment_mode": "qfq"}


def ven(date, close):
    return {"date": date, "close": close}


def scenario(vendor_rows, reference_rows, job="sh600011", symbol="SH600011"):
    """Drive the PUBLIC analyse() path on synthetic rows - no decoding, no manifest."""
    vendor = {job: {"js_variable": "KLC_K2_" + job, "branch": "O",
                    "rows": list(vendor_rows)}}
    extract = {"rows": {symbol: list(reference_rows)}}
    return g3.analyse({}, extract, vendor)[job]


# ============================================================ V-: the shared validator
@case("V-1 the validator accepts only real, finite, strictly positive numbers")
def _():
    assert g3.usable_price(1) and g3.usable_price(0.01) and g3.usable_price(1e300)
    for label, value in INVALID_PRICES:
        assert g3.usable_price(value) is False, label
    # a bool is never a price, even though bool is a subclass of int
    assert isinstance(True, int) and g3.usable_price(True) is False


@case("V-2 one pairing feeds both views, so their usable sets cannot diverge")
def _():
    vendor = [ven(DATES[0], 10.0), ven(DATES[1], float("inf")), ven(DATES[2], 12.0)]
    reference = [ref(DATES[0], 10.0), ref(DATES[1], 11.0), ref(DATES[2], 12.0)]
    pairing = g3.pair_series(vendor, reference)
    overall = g3.compare_series(pairing=pairing)
    segments = g3.per_segment(pairing=pairing)
    assert overall["compared_dates"] == 2
    assert sum(s["compared_dates"] for s in segments) == 2
    assert overall["matched_dates"] == 3          # matched is unaffected by invalidity
    assert overall["matched_dates_excluded_as_unusable"] == [DATES[1]]


# ================================== A-: public analyse() regressions for bad prices
@case("A-1 every invalid VENDOR price kind is reported, never crashes, never coerced")
def _():
    for label, value in INVALID_PRICES:
        data = scenario([ven(DATES[0], 10.0), ven(DATES[1], value), ven(DATES[2], 12.0)],
                        [ref(d, 10.0) for d in DATES[:3]])
        comparison = data["comparison"]
        assert comparison["matched_dates"] == 3, label
        assert comparison["compared_dates"] == 2, label
        reported = [e["date"] for e in comparison["invalid_vendor_closes"]]
        assert reported == [DATES[1]], (label, reported)
        assert comparison["invalid_reference_closes"] == [], label
        assert comparison["matched_dates_excluded_as_unusable"] == [DATES[1]], label
        assert data["usable_count_agreement"]["agree"] is True, label
        # the rejected value is described, not re-emitted as a raw float
        assert isinstance(comparison["invalid_vendor_closes"][0]["repr"], str)


@case("A-2 every invalid REFERENCE price kind is reported, never crashes, never coerced")
def _():
    for label, value in INVALID_PRICES:
        data = scenario([ven(d, 10.0) for d in DATES[:3]],
                        [ref(DATES[0], 10.0), ref(DATES[1], value), ref(DATES[2], 10.0)])
        comparison = data["comparison"]
        assert comparison["matched_dates"] == 3, label
        assert comparison["compared_dates"] == 2, label
        assert [e["date"] for e in comparison["invalid_reference_closes"]] == [DATES[1]], \
            label
        assert comparison["invalid_vendor_closes"] == [], label
        assert data["usable_count_agreement"]["agree"] is True, label


@case("A-3 overall usable totals equal the sum over segments, including across boundaries")
def _():
    reference = [ref(DATES[0], 10.0, "a", "t1"), ref(DATES[1], None, "a", "t1"),
                 ref(DATES[2], 10.0, "a", "t2"), ref(DATES[3], "bad", "b", "t2"),
                 ref(DATES[4], 10.0, "b", "t2")]
    data = scenario([ven(d, 11.0) for d in DATES], reference)
    comparison, segments = data["comparison"], data["segments"]
    assert comparison["matched_dates"] == 5
    assert comparison["compared_dates"] == 3
    assert [s["compared_dates"] for s in segments] == [1, 1, 1], segments
    assert sum(s["compared_dates"] for s in segments) == comparison["compared_dates"]
    assert data["usable_count_agreement"]["agree"] is True
    # each segment reports the matched-but-unusable dates that fall inside it
    assert segments[0]["matched_dates_excluded_as_unusable"] == [DATES[1]]
    assert segments[2]["matched_dates_excluded_as_unusable"] == [DATES[3]]


@case("A-4 invalidity does not disturb matched or missing counts")
def _():
    data = scenario([ven(DATES[0], float("nan")), ven(DATES[2], 10.0)],
                    [ref(DATES[0], 10.0), ref(DATES[1], 10.0), ref(DATES[2], 10.0)])
    comparison = data["comparison"]
    assert comparison["matched_dates"] == 2
    assert comparison["reference_dates_missing_from_vendor"] == [DATES[1]]
    assert comparison["vendor_dates_in_span_missing_from_reference"] == []
    assert comparison["compared_dates"] == 1


# ==================================== C-: consecutive-usable-date ratio changes
@case("C-1 a change carries from/to dates and the unrounded ratio difference")
def _():
    data = scenario([ven(DATES[0], 11.0), ven(DATES[1], 12.0)],
                    [ref(DATES[0], 10.0), ref(DATES[1], 10.0)])
    records = data["comparison"]["ratio_changes"]["records"]
    assert len(records) == 1
    record = records[0]
    assert (record["from_date"], record["to_date"]) == (DATES[0], DATES[1])
    assert record["ratio_from"] == 1.1 and record["ratio_to"] == 1.2
    assert record["change"] == 1.2 - 1.1                       # unrounded, exactly
    assert record["is_zero_change"] is False
    assert record["difference_from"] == 1.0 and record["difference_to"] == 2.0
    assert record["calendar_days_between"] == 1
    assert record["adjacent_with_no_skipped_dates"] is True


@case("C-2 an exactly zero change is reported as such, not omitted")
def _():
    data = scenario([ven(d, 11.0) for d in DATES[:3]],
                    [ref(d, 10.0) for d in DATES[:3]])
    changes = data["comparison"]["ratio_changes"]
    assert changes["pairs"] == 2 and changes["zero_changes"] == 2
    assert changes["nonzero_changes"] == 0
    assert all(r["change"] == 0.0 and r["is_zero_change"] for r in changes["records"])
    assert changes["largest_absolute_change"] == 0.0


@case("C-3 changes are never rounded away")
def _():
    tiny = 1.0 + 1e-12
    data = scenario([ven(DATES[0], 10.0), ven(DATES[1], 10.0 * tiny)],
                    [ref(DATES[0], 10.0), ref(DATES[1], 10.0)])
    record = data["comparison"]["ratio_changes"]["records"][0]
    assert record["change"] != 0.0 and record["is_zero_change"] is False
    # it survives at its true order of magnitude; float representation of the inputs
    # perturbs the last digits, which is exactly why nothing here is rounded.
    assert 1e-13 < record["change"] < 1e-11, record["change"]
    assert math.isclose(record["change"], 1e-12, rel_tol=1e-3), record["change"]


@case("C-4 a matched-but-invalid intervening date is skipped and named")
def _():
    data = scenario([ven(DATES[0], 11.0), ven(DATES[1], None), ven(DATES[2], 12.0)],
                    [ref(d, 10.0) for d in DATES[:3]])
    records = data["comparison"]["ratio_changes"]["records"]
    assert len(records) == 1, records
    record = records[0]
    assert (record["from_date"], record["to_date"]) == (DATES[0], DATES[2])
    assert record["skipped_matched_but_unusable"] == [DATES[1]]
    assert record["adjacent_with_no_skipped_dates"] is False
    assert record["calendar_days_between"] == 2
    assert data["comparison"]["ratio_changes"]["pairs_with_skipped_dates"] == 1


@case("C-5 intervening dates missing from one side are named on the correct side")
def _():
    # present in the reference only
    data = scenario([ven(DATES[0], 11.0), ven(DATES[2], 12.0)],
                    [ref(d, 10.0) for d in DATES[:3]])
    record = data["comparison"]["ratio_changes"]["records"][0]
    assert record["skipped_reference_only_dates"] == [DATES[1]]
    assert record["skipped_vendor_only_dates"] == []
    # present in the vendor only
    data = scenario([ven(d, 11.0) for d in DATES[:3]],
                    [ref(DATES[0], 10.0), ref(DATES[2], 10.0)])
    record = data["comparison"]["ratio_changes"]["records"][0]
    assert record["skipped_vendor_only_dates"] == [DATES[1]]
    assert record["skipped_reference_only_dates"] == []


@case("C-6 source and fetch-time boundaries are flagged on the straddling pair")
def _():
    reference = [ref(DATES[0], 10.0, "a", "t1"), ref(DATES[1], 10.0, "a", "t2"),
                 ref(DATES[2], 10.0, "b", "t2")]
    data = scenario([ven(d, 11.0) for d in DATES[:3]], reference)
    records = data["comparison"]["ratio_changes"]["records"]
    assert [r["updated_at_changed"] for r in records] == [True, False]
    assert [r["source_changed"] for r in records] == [False, True]
    assert all(r["metadata_boundary"] for r in records)
    assert data["comparison"]["ratio_changes"]["pairs_at_a_metadata_boundary"] == 2
    assert records[0]["updated_at_from"] == "t1" and records[0]["updated_at_to"] == "t2"


@case("C-7 adjacency is described, and no threshold or attribution is emitted")
def _():
    data = scenario([ven(d, 11.0) for d in DATES[:3]], [ref(d, 10.0) for d in DATES[:3]])
    changes = data["comparison"]["ratio_changes"]
    assert "not necessarily consecutive exchange sessions" in changes["adjacency"]
    assert "ratio(to_date) - ratio(from_date)" in changes["definition"]
    assert "not a threshold" in changes["largest_absolute_change_note"]
    blob = json.dumps(data, ensure_ascii=False)
    for banned in ("corporate action", "ex-date", "dividend", "threshold_exceeded",
                   "PASS", "FAIL"):
        assert banned not in blob, banned


# ============================================================ R-: retained artifacts
@case("R-1 the documented 470-row segments are verified on the retained reference")
def _():
    verified = g3.documented_470_row_segments(retained())
    assert verified["verified"] is True, verified
    for job in ("sh600011", "bj920000"):
        segments = verified["%s_470_row_segments" % job]
        assert len(segments) == 1 and segments[0]["rows"] == 470
        assert segments[0]["first_date"] == "2024-08-13"
        assert segments[0]["last_date"] == "2026-07-23"
    only = verified["sh600011_471_row_source_only_spans"]
    assert len(only) == 1 and only[0]["rows"] == 471 and only[0]["last_date"] == "2026-07-24"


@case("R-2 the index compares exactly equal, and every change is exactly zero")
def _():
    index = retained()["sh000300"]
    comparison = index["comparison"]
    assert index["instrument_class"] == "benchmark"
    assert index["reference_basis_stored"] == ["none"]
    assert comparison["matched_dates"] == comparison["compared_dates"] == 538
    assert comparison["ratio"]["min"] == comparison["ratio"]["max"] == 1.0
    changes = comparison["ratio_changes"]
    assert changes["pairs"] == 537 and changes["zero_changes"] == 537
    assert changes["nonzero_changes"] == 0 and changes["largest_absolute_change"] == 0.0


@case("R-3 BJ920000's difference is piecewise constant over five runs")
def _():
    comparison = retained()["bj920000"]["comparison"]
    observed = [(r["value"], r["first_date"], r["last_date"], r["sessions"])
                for r in comparison["difference"]["runs"]]
    assert observed == [(0.29, "2024-08-13", "2024-09-27", 32),
                        (0.23, "2024-09-30", "2025-05-14", 147),
                        (0.15, "2025-05-15", "2025-09-17", 89),
                        (0.08, "2025-09-18", "2026-05-22", 159),
                        (0.0, "2026-05-25", "2026-09-04", 74)], observed
    assert sum(r["sessions"] for r in comparison["difference"]["runs"]) == 501


@case("R-4 retained ratio changes are emitted for every symbol, with boundary flags")
def _():
    results = retained()
    for job, pairs in (("sh600011", 537), ("bj920000", 500), ("sh000300", 537)):
        changes = results[job]["comparison"]["ratio_changes"]
        assert changes["pairs"] == pairs, (job, changes["pairs"])
        assert changes["zero_changes"] + changes["nonzero_changes"] == pairs
        assert changes["pairs_at_a_metadata_boundary"] == len(
            results[job]["boundaries"]["source_or_fetch_time_boundaries"]), job
        assert all(set(("from_date", "to_date", "change", "metadata_boundary"))
                   <= set(r) for r in changes["records"])
    # every pair is a real consecutive-usable-date pair over the retained data
    sh = results["sh600011"]["comparison"]
    assert sh["compared_dates"] - 1 == sh["ratio_changes"]["pairs"]


@case("R-5 coverage is complete both ways; BJ's two invalid closes lie outside the span")
def _():
    results = retained()
    for job in ("sh600011", "sh000300", "bj920000"):
        comparison = results[job]["comparison"]
        assert comparison["reference_dates_missing_from_vendor"] == [], job
        assert comparison["vendor_dates_in_span_missing_from_reference"] == [], job
        assert comparison["duplicate_vendor_dates"] == [] == \
            comparison["duplicate_reference_dates"], job
        assert comparison["invalid_reference_closes"] == [], job
        assert comparison["matched_dates_excluded_as_unusable"] == [], job
        assert results[job]["usable_count_agreement"]["agree"] is True, job
    bj = results["bj920000"]["comparison"]
    assert [e["date"] for e in bj["invalid_vendor_closes"]] == ["2019-05-23", "2019-07-12"]
    low, high = bj["reference_span"]
    assert all(not (low <= e["date"] <= high) for e in bj["invalid_vendor_closes"])
    assert bj["matched_dates"] == bj["compared_dates"] == 501


@case("R-6 boundary dates are reported, and the source-only view hides one")
def _():
    results = retained()
    assert results["sh600011"]["boundaries"]["source_or_fetch_time_boundaries"] == [
        "2024-08-13", "2026-07-24", "2026-07-27"]
    assert results["sh600011"]["boundaries"]["source_boundaries"] == [
        "2024-08-13", "2026-07-27"]
    assert results["bj920000"]["boundaries"]["source_or_fetch_time_boundaries"] == [
        "2026-07-24", "2026-07-27"]
    assert results["sh000300"]["boundaries"]["source_boundaries"] == []


@case("R-7 the analysis states its scope, invents no threshold and replays no adapter")
def _():
    source = (HERE / "g3_ratio_analysis.py").read_text(encoding="utf-8")
    assert "vendor_close / reference_close" in g3.RATIO_DIRECTION
    assert g3.NORMALIZATION.startswith("none")
    assert "never coerced" in g3.VALIDITY_RULE or "never coerced" in source
    assert "not necessarily consecutive exchange sessions" in g3.ADJACENCY_NOTE
    for banned in ("TOLERANCE", "THRESHOLD", "_TOL", "PASS_IF", "ACCEPT"):
        assert banned not in source, banned
    import ast
    parsed = ast.parse(source)
    imported, called = set(), set()
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update("%s.%s" % (node.module or "", alias.name)
                            for alias in node.names)
        elif isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                called.add(target.id)
            elif isinstance(target, ast.Attribute):
                called.add(target.attr)
    for banned in ("stock_zh_a_daily", "index_stock_zh", "adapter_replay", "replay"):
        assert banned not in called, "calls %s" % banned
        assert not any(banned in name for name in imported), "imports %s" % banned
    assert "akshare.stock.cons" in imported


@case("R-8 the preserved r1 analysis directory is untouched by this suite")
def _():
    r1 = SMOKE / "g3_ratio_analysis_20260909"
    assert r1.is_dir() and r1 != HERE
    expected = {
        "g3_ratio_analysis.py":
            "557003e2d160cebd6bf848c8300169a3ea2de22b06dd8832d9ccda45ef67b8f6",
        "test_g3_ratio_analysis.py":
            "baa32b5ce119cb412cf1a325a31899f68e28e261d91e069cec4960406a5ee66b",
        "results.json":
            "41bbea11506c0953d7fe7477ce7eec080e94a38a624979e028be1c84231a676b",
        "REPORT.md":
            "75d114b35763933f14a9d3056ec86296825c56b845a18292bc77f86c9b9d3643",
        "PROVENANCE.json":
            "28185984fa7ebd738699918b2f4ca6f7ddf8c2ae1a1112ec1dd385929b39fc22",
    }
    assert tree(r1) == expected, "the r1 five-file delivery must stay byte-identical"


def main():
    print("G-3 r2 suite (offline; no network, SQLite, replay or capture)")
    before = {p.name: tree(p) for p in GUARDED}
    failures = 0
    for name, fn in CASES:
        try:
            fn()
            print("  [ok] %s" % name)
        except AssertionError as exc:
            failures += 1
            print("  [XX] %s\n       %s" % (name, exc))
        except Exception as exc:                                  # noqa: BLE001
            failures += 1
            print("  [XX] %s\n       unexpected %s: %s" % (name, type(exc).__name__, exc))
    after = {p.name: tree(p) for p in GUARDED}
    changed = sorted(name for name in before if before[name] != after[name])
    print("\n  guarded directories: %d, changed: %s" % (len(GUARDED), changed or "none"))
    if changed:
        failures += 1
    print("\n  %d cases, %d unexpected" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
