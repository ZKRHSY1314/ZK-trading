"""Focused synthetic checks for the G-3 ratio analysis, plus retained-artifact checks.

Offline only: no network, no SQLite, no adapter replay, no capture, no production write.
The G- cases exercise the pure functions on synthetic inputs; the R- cases assert what the
retained artifacts actually contain. Every retained tree is hashed before and after.

These checks measure. They define no acceptance threshold, infer no corporate action, and
change no label, eligibility or verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(SMOKE) not in sys.path:
    sys.path.insert(0, str(SMOKE))
import smoke_capture as cap                                       # noqa: E402
import g3_ratio_analysis as g3                                    # noqa: E402

_GUARD = cap.no_remote_connections("the G-3 suite attempted a network connection")
_GUARD.__enter__()

GUARDED = tuple(sorted(p for p in SMOKE.iterdir() if p.is_dir() and p.name.startswith(
    ("evidence_", "revision_", "receipts_", "frozen_impl_", "basis_eval_"))))
CASES = []
_LOADED = {}


def case(name):
    def wrap(fn):
        CASES.append((name, fn))
        return fn
    return wrap


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def retained():
    """Decode the retained bodies once and reuse them across the R- cases."""
    if not _LOADED:
        manifest, extract, vendor = g3.load_inputs()
        _LOADED["results"] = g3.analyse(manifest, extract, vendor)
    return _LOADED["results"]


def ref(date, close, source="s", updated_at="t"):
    return {"trade_date": date, "close": close, "source": source,
            "updated_at": updated_at}


def ven(date, close):
    return {"date": date, "close": close}


# ================================================================ G-: synthetic checks
@case("G-1 segments split on a change of source OR of updated_at, and on neither else")
def _():
    rows = [ref("2024-01-01", 1, "a", "t1"), ref("2024-01-02", 1, "a", "t1"),
            ref("2024-01-03", 1, "a", "t2"), ref("2024-01-04", 1, "b", "t2"),
            ref("2024-01-05", 1, "b", "t2")]
    both = g3.contiguous_segments(rows, ("source", "updated_at"))
    assert [s["rows"] for s in both] == [2, 1, 2], both
    assert [s["first_date"] for s in both] == ["2024-01-01", "2024-01-03", "2024-01-04"]
    source_only = g3.contiguous_segments(rows, ("source",))
    assert [s["rows"] for s in source_only] == [3, 2], source_only
    # a same-source span can hide a fetch-time boundary - exactly the SH600011 shape
    assert len(source_only) < len(both)


@case("G-2 runs group exact repeats only; the 6-dp rounding is not a tolerance")
def _():
    series = [("d1", 1.0), ("d2", 1.0), ("d3", 1.2), ("d4", 1.2), ("d5", 1.0)]
    assert [r["sessions"] for r in g3.runs(series)] == [2, 2, 1]
    assert [r["value"] for r in g3.runs(series)] == [1.0, 1.2, 1.0]
    # a difference smaller than the rounding is grouped; one larger is not. This is
    # grouping of exact repeats after rounding, NOT an acceptance tolerance.
    assert len(g3.runs([("a", 1.0), ("b", 1.0 + 1e-9)])) == 1
    assert len(g3.runs([("a", 1.0), ("b", 1.0 + 1e-4)])) == 2


@case("G-3 the ratio direction is vendor / reference, and the difference vendor - ref")
def _():
    out = g3.compare_series([ven("2024-01-02", 12.0)], [ref("2024-01-02", 10.0)])
    assert out["ratio"]["series"] == [["2024-01-02", 1.2]], out["ratio"]["series"]
    assert out["difference"]["series"] == [["2024-01-02", 2.0]]
    assert "vendor_close / reference_close" in out["ratio"]["direction"]
    assert out["compared_dates"] == 1


@case("G-4 missing dates are reported separately in each direction")
def _():
    vendor = [ven("2024-01-01", 1.0), ven("2024-01-03", 1.0), ven("2023-12-01", 1.0)]
    reference = [ref("2024-01-01", 1.0), ref("2024-01-02", 1.0)]
    out = g3.compare_series(vendor, reference)
    assert out["reference_dates_missing_from_vendor"] == ["2024-01-02"]
    assert out["vendor_dates_in_span_missing_from_reference"] == []
    # a vendor date inside the reference span but absent from the reference is reported
    out = g3.compare_series(vendor, [ref("2024-01-01", 1.0), ref("2024-01-04", 1.0)])
    assert out["vendor_dates_in_span_missing_from_reference"] == ["2024-01-03"]
    # and a vendor date outside the span is not counted as missing
    assert "2023-12-01" not in out["vendor_dates_in_span_missing_from_reference"]


@case("G-5 duplicate dates on either side are reported")
def _():
    out = g3.compare_series([ven("2024-01-01", 1.0), ven("2024-01-01", 2.0)],
                            [ref("2024-01-01", 1.0), ref("2024-01-01", 1.0)])
    assert out["duplicate_vendor_dates"] == ["2024-01-01"]
    assert out["duplicate_reference_dates"] == ["2024-01-01"]


@case("G-6 non-positive, missing and non-finite closes are excluded and listed")
def _():
    vendor = [ven("2024-01-01", 0.0), ven("2024-01-02", -1.0), ven("2024-01-03", None),
              ven("2024-01-04", float("nan")), ven("2024-01-05", 10.0)]
    reference = [ref(d, 10.0) for d in ("2024-01-01", "2024-01-02", "2024-01-03",
                                        "2024-01-04", "2024-01-05")]
    out = g3.compare_series(vendor, reference)
    assert out["invalid_vendor_closes"] == ["2024-01-01", "2024-01-02", "2024-01-03",
                                            "2024-01-04"]
    assert out["compared_dates"] == 1 and out["matched_dates"] == 5
    assert out["ratio"]["series"] == [["2024-01-05", 1.0]]
    out = g3.compare_series([ven("2024-01-01", 10.0)], [ref("2024-01-01", 0.0)])
    assert out["invalid_reference_closes"] == ["2024-01-01"] and out["compared_dates"] == 0


@case("G-7 nothing is normalized: a 100x scale difference is reported as 100x")
def _():
    out = g3.compare_series([ven("2024-01-02", 1000.0)], [ref("2024-01-02", 10.0)])
    assert out["ratio"]["series"] == [["2024-01-02", 100.0]]
    assert "no rebasing" in out["ratio"]["normalization"]


@case("G-8 an additive relation gives constant differences; a factor gives constant ratios")
def _():
    dates = ["2024-01-0%d" % i for i in range(1, 6)]
    base = [10.0, 11.0, 12.0, 13.0, 14.0]
    additive = g3.compare_series([ven(d, b + 0.5) for d, b in zip(dates, base)],
                                 [ref(d, b) for d, b in zip(dates, base)])
    assert len(additive["difference"]["runs"]) == 1
    assert additive["difference"]["runs"][0]["value"] == 0.5
    assert len(additive["ratio"]["runs"]) == 5          # the ratio drifts with price
    factored = g3.compare_series([ven(d, b * 1.25) for d, b in zip(dates, base)],
                                 [ref(d, b) for d, b in zip(dates, base)])
    assert len(factored["ratio"]["runs"]) == 1 and factored["ratio"]["runs"][0]["value"] == 1.25
    assert len(factored["difference"]["runs"]) == 5
    # neither shape is labelled: the analysis reports both views and interprets neither
    assert "corporate action" not in json.dumps(additive)


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


@case("R-2 the index compares exactly equal on every common date")
def _():
    index = retained()["sh000300"]
    assert index["instrument_class"] == "benchmark"
    assert index["reference_basis_stored"] == ["none"]
    comparison = index["comparison"]
    assert comparison["compared_dates"] == 538
    assert comparison["ratio"]["min"] == comparison["ratio"]["max"] == 1.0
    assert len(comparison["ratio"]["runs"]) == 1
    assert len(comparison["difference"]["runs"]) == 1
    assert comparison["difference"]["runs"][0]["value"] == 0.0
    # four fetch times, and the equality holds across all of them
    assert len(index["reference_fetch_times"]) == 4


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
    # the same series is NOT piecewise constant in ratio terms
    assert len(comparison["ratio"]["runs"]) > 400


@case("R-4 SH600011 is constant in neither view over the compared span")
def _():
    comparison = retained()["sh600011"]["comparison"]
    assert comparison["compared_dates"] == 538
    assert len(comparison["difference"]["runs"]) == 233
    assert len(comparison["ratio"]["runs"]) == 468
    assert comparison["ratio"]["min"] == 1.0
    assert math.isclose(comparison["ratio"]["max"], 1.1060975609756099, rel_tol=1e-12)
    assert comparison["difference"]["min"] == 0.0 and comparison["difference"]["max"] == 0.87


@case("R-5 date coverage is complete in both directions; BJ's two bad closes are outside")
def _():
    results = retained()
    for job in ("sh600011", "sh000300", "bj920000"):
        comparison = results[job]["comparison"]
        assert comparison["reference_dates_missing_from_vendor"] == [], job
        assert comparison["vendor_dates_in_span_missing_from_reference"] == [], job
        assert comparison["duplicate_vendor_dates"] == [] == \
            comparison["duplicate_reference_dates"], job
        assert comparison["invalid_reference_closes"] == [], job
    bj = results["bj920000"]["comparison"]
    assert bj["invalid_vendor_closes"] == ["2019-05-23", "2019-07-12"]
    low, high = bj["reference_span"]
    assert all(not (low <= d <= high) for d in bj["invalid_vendor_closes"])
    assert bj["compared_dates"] == bj["matched_dates"] == 501


@case("R-6 the boundary dates are reported, and the source-only view hides one")
def _():
    results = retained()
    assert results["sh600011"]["boundaries"]["source_or_fetch_time_boundaries"] == [
        "2024-08-13", "2026-07-24", "2026-07-27"]
    assert results["sh600011"]["boundaries"]["source_boundaries"] == [
        "2024-08-13", "2026-07-27"]          # 2026-07-24 is a fetch-time-only boundary
    assert results["bj920000"]["boundaries"]["source_or_fetch_time_boundaries"] == [
        "2026-07-24", "2026-07-27"]
    assert results["sh000300"]["boundaries"]["source_boundaries"] == []


@case("R-7 the analysis states its scope and invents no threshold")
def _():
    source = (HERE / "g3_ratio_analysis.py").read_text(encoding="utf-8")
    for phrase in ("no acceptance threshold", "no corporate action", "remains **FAIL**"):
        assert phrase in g3.DISCLAIMER or phrase in source, phrase
    assert "vendor_close / reference_close" in g3.RATIO_DIRECTION
    assert g3.NORMALIZATION.startswith("none")
    # no tolerance-like constant is defined anywhere in the module
    for banned in ("TOLERANCE", "THRESHOLD", "_TOL", "PASS_IF", "ACCEPT"):
        assert banned not in source, banned
    # the adapter is never replayed. Checked on the parsed module rather than by
    # substring, because the docstring legitimately NAMES the functions it does not call.
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
        assert banned not in called, ("calls %s" % banned)
        assert not any(banned in name for name in imported), ("imports %s" % banned)
    assert "akshare.stock.cons" in imported          # the pinned routine, nothing more


def main():
    print("G-3 ratio-analysis suite (offline; no network, SQLite, replay or capture)")
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
