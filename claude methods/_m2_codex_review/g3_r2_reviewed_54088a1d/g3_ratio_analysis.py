"""G-3 (r2): retained vendor closes versus the retained reference extract, over ALL
available common dates - with G3-R1 and G3-R2 corrected.

Scope and discipline
--------------------
Exploratory measurement only. It invents **no acceptance threshold**, infers **no corporate
action**, changes **no basis label and no eligibility**, does **not** close U-6 or P1, and
does **not** upgrade the capability verdict, which remains **FAIL**.

What changed since `g3_ratio_analysis_20260909/`
------------------------------------------------
* **G3-R1.** One strict price validator, `usable_price`, is shared by the full-span and the
  per-segment analysis. Booleans, `None`, strings and non-finite values are **invalid, not
  coerced**, and nothing raises on them. The usable pairing is computed **once** and both
  views consume it, so the overall usable count and the sum of the segment counts agree by
  construction rather than by coincidence. Matched and missing counts are unaffected by
  invalidity: a date matched on both sides stays matched even when its price is unusable.
* **G3-R2.** Consecutive-usable-common-date **ratio changes** are emitted explicitly:
  `from_date`, `to_date`, both unrounded ratios, the **unrounded** difference
  `ratio(to) - ratio(from)`, the intervening dates that were skipped and why, and
  `source` / `updated_at` boundary flags. Price differences are retained as an additional
  measurement.

**Consecutive usable common dates are not necessarily consecutive exchange sessions.** A
pair is adjacent in the *usable* series, which excludes weekends and holidays, any date
missing from either side, and any date whose price failed `usable_price`. Every change
record names the calendar gap and lists what was skipped, so no adjacency is implied that
the data does not support.

Inputs, all retained and read-only
----------------------------------
`revision_20260908T082833Z_r2abc_v2/`: `capture_manifest.json`, the `raw/*.bin` history
bodies and `reference/reference_extract.json`. Vendor closes come from the existing offline
decoder (`sina_klc_decoder.decode_klc`) with the pinned `hk_js_decode` routine. **The
adapter is never replayed.** No network, SQLite, capture or service action.

Ratio direction and normalization - stated, not implied
-------------------------------------------------------
* **ratio = vendor_close / reference_close** (live Sina close ÷ cached reference close).
* **difference = vendor_close - reference_close**.
* **change = ratio(to_date) - ratio(from_date)**, unrounded.
* **Normalization: none.** No rebasing, scaling, unit conversion or re-rounding. Run
  grouping rounds to 6 decimal places solely to collapse exact repeats; that is not a
  tolerance, and the change records are never rounded.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import itertools
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE.parent
REPO_ROOT = SMOKE.parents[1]
if str(SMOKE) not in sys.path:
    sys.path.insert(0, str(SMOKE))
import sina_klc_decoder as dec                                    # noqa: E402
import smoke_capture as cap                                       # noqa: E402

DEFAULT_REVISION = SMOKE / "revision_20260908T082833Z_r2abc_v2"
JOB_TO_MANIFEST_SYMBOL = {"sh600011": "SH600011", "sh000300": "SH000300",
                          "bj920000": "BJ920000"}
RUN_ROUNDING_DP = 6

RATIO_DIRECTION = ("ratio = vendor_close / reference_close (the live Sina close divided "
                   "by the cached reference close)")
CHANGE_DEFINITION = ("change = ratio(to_date) - ratio(from_date), unrounded, over "
                     "CONSECUTIVE USABLE COMMON dates")
ADJACENCY_NOTE = ("consecutive usable common dates are not necessarily consecutive "
                  "exchange sessions: the usable series excludes weekends and holidays, "
                  "dates absent from either side, and dates whose price failed the "
                  "validator. Each record names its calendar gap and what was skipped")
NORMALIZATION = ("none - no rebasing, scaling, unit conversion or re-rounding of stored "
                 "values; run grouping rounds to %d decimal places only to collapse exact "
                 "repeats, which is not a tolerance, and change records are never rounded"
                 % RUN_ROUNDING_DP)
VALIDITY_RULE = ("a price is usable only if it is a real, finite, strictly positive int "
                 "or float; booleans, None, strings and non-finite values are invalid and "
                 "are never coerced")
DISCLAIMER = ("Exploratory measurement. No acceptance threshold is defined, no corporate "
              "action is inferred, no basis label or eligibility changes, U-6 and P1 stay "
              "open, and source capability remains FAIL.")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repo_relative(path):
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return Path(path).name


# ================================================================== G3-R1: validity
def usable_price(value):
    """The ONE price-validity rule, shared by the full-span and per-segment analysis.

    Strict by design: a `bool` is not a price, a numeric string is not coerced, and NaN
    and the infinities are rejected. Nothing here raises on hostile input.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0


def describe_value(value):
    """A JSON-safe description of a rejected value - never the raw non-finite float."""
    return {"type": type(value).__name__, "repr": repr(value)[:64]}


# ------------------------------------------------------------------------- loading
def load_inputs(revision=DEFAULT_REVISION, *, routine=None, racer_factory=None):
    """Retained manifest, reference extract and DECODED vendor history rows."""
    revision = Path(revision)
    manifest = json.loads((revision / "capture_manifest.json").read_text("utf-8"))
    extract = json.loads((revision / "reference" / "reference_extract.json")
                         .read_text("utf-8"))
    if routine is None:
        from akshare.stock.cons import hk_js_decode as routine
    vendor = {}
    with cap.no_remote_connections("the G-3 analysis must not reach a host"):
        for record in manifest.get("requests", []):
            if record.get("kind") != "klc" or record.get("outcome") != "ok":
                continue
            body = (revision / "raw" / record["raw_file"]).read_bytes()
            kwargs = {"routine": routine}
            if racer_factory is not None:
                kwargs["racer_factory"] = racer_factory
            vendor[record["job"]] = dec.decode_klc(body, record.get("encoding"), **kwargs)
    return manifest, extract, vendor


# ------------------------------------------------------------------- partitioning
def contiguous_segments(rows, keys):
    """Contiguous runs of date-ordered reference rows sharing every key in `keys`."""
    ordered = sorted(rows, key=lambda r: r["trade_date"])
    out = []
    for value, group in itertools.groupby(ordered,
                                          key=lambda r: tuple(r.get(k) for k in keys)):
        block = list(group)
        out.append({"key": dict(zip(keys, value)), "rows": len(block),
                    "first_date": block[0]["trade_date"],
                    "last_date": block[-1]["trade_date"]})
    return out


def runs(series, ndigits=RUN_ROUNDING_DP):
    """Piecewise-constant runs of `[(date, value)]`, grouped on the rounded value."""
    out = []
    for date, value in series:
        rounded = round(value, ndigits)
        if out and out[-1]["value"] == rounded:
            out[-1]["last_date"] = date
            out[-1]["sessions"] += 1
        else:
            out.append({"value": rounded, "first_date": date, "last_date": date,
                        "sessions": 1})
    return out


# ============================================================ the single pairing pass
def pair_series(vendor_rows, reference_rows):
    """Join the two series ONCE. Every later view consumes this result (G3-R1).

    `matched` counts dates present on both sides regardless of price validity; `usable`
    is the subset whose prices both satisfy `usable_price`.
    """
    vendor, duplicate_vendor = {}, []
    for row in vendor_rows:
        if row["date"] in vendor:
            duplicate_vendor.append(row["date"])
        vendor[row["date"]] = row
    reference, duplicate_reference = {}, []
    for row in reference_rows:
        if row["trade_date"] in reference:
            duplicate_reference.append(row["trade_date"])
        reference[row["trade_date"]] = row

    invalid_vendor = [{"date": d, **describe_value(r.get("close"))}
                      for d, r in sorted(vendor.items())
                      if not usable_price(r.get("close"))]
    invalid_reference = [{"date": d, **describe_value(r.get("close"))}
                         for d, r in sorted(reference.items())
                         if not usable_price(r.get("close"))]

    span_low = min(reference) if reference else None
    span_high = max(reference) if reference else None
    vendor_in_span = sorted(d for d in vendor
                            if span_low is not None and span_low <= d <= span_high)
    matched = sorted(d for d in reference if d in vendor)
    unusable_matched = [d for d in matched
                        if not (usable_price(vendor[d].get("close"))
                                and usable_price(reference[d].get("close")))]
    usable = []
    for date in matched:
        if date in unusable_matched:
            continue
        usable.append((date, float(vendor[date]["close"]),
                       float(reference[date]["close"])))
    return {
        "vendor": vendor,
        "reference": reference,
        "vendor_rows": len(vendor_rows),
        "reference_rows": len(reference_rows),
        "reference_span": [span_low, span_high],
        "vendor_dates_within_reference_span": len(vendor_in_span),
        "matched_dates": matched,
        "reference_dates_missing_from_vendor": sorted(d for d in reference
                                                      if d not in vendor),
        "vendor_dates_in_span_missing_from_reference": sorted(
            d for d in vendor_in_span if d not in reference),
        "duplicate_vendor_dates": sorted(set(duplicate_vendor)),
        "duplicate_reference_dates": sorted(set(duplicate_reference)),
        "invalid_vendor_closes": invalid_vendor,
        "invalid_reference_closes": invalid_reference,
        "matched_dates_excluded_as_unusable": sorted(unusable_matched),
        "usable": usable,
    }


# ============================================ G3-R2: consecutive usable-date changes
def ratio_changes(pairing):
    """Unrounded `ratio(to) - ratio(from)` over consecutive USABLE COMMON dates."""
    usable = pairing["usable"]
    reference, vendor = pairing["reference"], pairing["vendor"]
    unusable = set(pairing["matched_dates_excluded_as_unusable"])
    out = []
    for (from_date, live_a, cached_a), (to_date, live_b, cached_b) in zip(usable,
                                                                          usable[1:]):
        ratio_from = live_a / cached_a
        ratio_to = live_b / cached_b
        skipped_unusable = sorted(d for d in unusable if from_date < d < to_date)
        skipped_reference_only = sorted(d for d in reference
                                        if from_date < d < to_date and d not in vendor)
        skipped_vendor_only = sorted(d for d in vendor
                                     if from_date < d < to_date and d not in reference)
        row_from, row_to = reference[from_date], reference[to_date]
        source_changed = row_from.get("source") != row_to.get("source")
        fetch_changed = row_from.get("updated_at") != row_to.get("updated_at")
        change = ratio_to - ratio_from
        out.append({
            "from_date": from_date,
            "to_date": to_date,
            "ratio_from": ratio_from,
            "ratio_to": ratio_to,
            "change": change,                       # unrounded, by contract
            "is_zero_change": change == 0.0,
            "difference_from": live_a - cached_a,
            "difference_to": live_b - cached_b,
            "calendar_days_between": (_dt.date.fromisoformat(to_date)
                                      - _dt.date.fromisoformat(from_date)).days,
            "skipped_matched_but_unusable": skipped_unusable,
            "skipped_reference_only_dates": skipped_reference_only,
            "skipped_vendor_only_dates": skipped_vendor_only,
            "adjacent_with_no_skipped_dates": not (skipped_unusable
                                                   or skipped_reference_only
                                                   or skipped_vendor_only),
            "source_from": row_from.get("source"),
            "source_to": row_to.get("source"),
            "updated_at_from": row_from.get("updated_at"),
            "updated_at_to": row_to.get("updated_at"),
            "source_changed": source_changed,
            "updated_at_changed": fetch_changed,
            "metadata_boundary": source_changed or fetch_changed,
        })
    return out


def summarize_changes(changes):
    magnitudes = [abs(c["change"]) for c in changes]
    return {
        "definition": CHANGE_DEFINITION,
        "adjacency": ADJACENCY_NOTE,
        "pairs": len(changes),
        "zero_changes": sum(1 for c in changes if c["is_zero_change"]),
        "nonzero_changes": sum(1 for c in changes if not c["is_zero_change"]),
        "pairs_at_a_metadata_boundary": sum(1 for c in changes
                                            if c["metadata_boundary"]),
        "pairs_with_skipped_dates": sum(1 for c in changes
                                        if not c["adjacent_with_no_skipped_dates"]),
        "largest_absolute_change": max(magnitudes) if magnitudes else None,
        "largest_absolute_change_note": ("reported as a magnitude only; it is not a "
                                         "threshold and implies no finding"),
    }


# --------------------------------------------------------------------- comparison
def compare_series(vendor_rows=None, reference_rows=None, *, pairing=None):
    """Coverage, validity, per-date ratio and difference, and consecutive-date changes."""
    if pairing is None:
        pairing = pair_series(vendor_rows or [], reference_rows or [])
    ratios = [(date, live / cached) for date, live, cached in pairing["usable"]]
    differences = [(date, round(live - cached, 10))
                   for date, live, cached in pairing["usable"]]
    values = [v for _d, v in ratios]
    deltas = [v for _d, v in differences]
    changes = ratio_changes(pairing)
    return {
        "validity_rule": VALIDITY_RULE,
        "reference_rows": pairing["reference_rows"],
        "vendor_rows": pairing["vendor_rows"],
        "reference_span": pairing["reference_span"],
        "vendor_dates_within_reference_span":
            pairing["vendor_dates_within_reference_span"],
        "matched_dates": len(pairing["matched_dates"]),
        "reference_dates_missing_from_vendor":
            pairing["reference_dates_missing_from_vendor"],
        "vendor_dates_in_span_missing_from_reference":
            pairing["vendor_dates_in_span_missing_from_reference"],
        "duplicate_vendor_dates": pairing["duplicate_vendor_dates"],
        "duplicate_reference_dates": pairing["duplicate_reference_dates"],
        "invalid_vendor_closes": pairing["invalid_vendor_closes"],
        "invalid_reference_closes": pairing["invalid_reference_closes"],
        "matched_dates_excluded_as_unusable":
            pairing["matched_dates_excluded_as_unusable"],
        "compared_dates": len(pairing["usable"]),
        "ratio": {
            "direction": RATIO_DIRECTION,
            "normalization": NORMALIZATION,
            "min": min(values) if values else None,
            "median": statistics.median(values) if values else None,
            "max": max(values) if values else None,
            "distinct_rounded": len({round(v, RUN_ROUNDING_DP) for v in values}),
            "runs": runs(ratios),
            "series": [[d, v] for d, v in ratios],
        },
        "difference": {
            "definition": "difference = vendor_close - reference_close",
            "min": min(deltas) if deltas else None,
            "median": statistics.median(deltas) if deltas else None,
            "max": max(deltas) if deltas else None,
            "distinct_rounded": len({round(v, RUN_ROUNDING_DP) for v in deltas}),
            "runs": runs(differences),
            "series": [[d, v] for d, v in differences],
        },
        "ratio_changes": {**summarize_changes(changes), "records": changes},
    }


def per_segment(vendor_rows=None, reference_rows=None, *, pairing=None):
    """The same comparison per source+updated_at segment, over the SAME usable set."""
    if pairing is None:
        pairing = pair_series(vendor_rows or [], reference_rows or [])
    usable = {date: (live, cached) for date, live, cached in pairing["usable"]}
    rows = list(pairing["reference"].values())
    out = []
    for segment in contiguous_segments(rows, ("source", "updated_at")):
        dates = [d for d in sorted(usable)
                 if segment["first_date"] <= d <= segment["last_date"]]
        ratios = [usable[d][0] / usable[d][1] for d in dates]
        deltas = [round(usable[d][0] - usable[d][1], 10) for d in dates]
        excluded = [d for d in pairing["matched_dates_excluded_as_unusable"]
                    if segment["first_date"] <= d <= segment["last_date"]]
        out.append({
            **segment,
            "compared_dates": len(dates),
            "matched_dates_excluded_as_unusable": excluded,
            "ratio_min": min(ratios) if ratios else None,
            "ratio_median": statistics.median(ratios) if ratios else None,
            "ratio_max": max(ratios) if ratios else None,
            "ratio_distinct_rounded": len({round(v, RUN_ROUNDING_DP) for v in ratios}),
            "difference_distinct_rounded": len({round(v, RUN_ROUNDING_DP)
                                                for v in deltas}),
            "difference_min": min(deltas) if deltas else None,
            "difference_max": max(deltas) if deltas else None,
        })
    return out


def boundaries(reference_rows):
    """Where source and/or fetch time change - the confounders, listed as dates."""
    by_both = contiguous_segments(reference_rows, ("source", "updated_at"))
    by_source = contiguous_segments(reference_rows, ("source",))
    return {
        "source_and_updated_at_segments": by_both,
        "source_only_spans": by_source,
        "source_boundaries": [s["first_date"] for s in by_source[1:]],
        "source_or_fetch_time_boundaries": [s["first_date"] for s in by_both[1:]],
        "note": ("a change at one of these dates is confounded with the metadata change "
                 "itself; grouping on both keys removes exactly two recorded metadata "
                 "differences and establishes nothing further"),
    }


def analyse(manifest, extract, vendor):
    results = {}
    jobs = {job["job"]: job for job in cap.JOBS}
    for job_name, symbol in JOB_TO_MANIFEST_SYMBOL.items():
        if job_name not in vendor or symbol not in extract.get("rows", {}):
            continue
        decoded = vendor[job_name]
        reference_rows = sorted(extract["rows"][symbol], key=lambda r: r["trade_date"])
        pairing = pair_series(decoded["rows"], reference_rows)
        comparison = compare_series(pairing=pairing)
        segments = per_segment(pairing=pairing)
        results[job_name] = {
            "instrument_class": jobs[job_name]["instrument_class"],
            "manifest_symbol": symbol,
            "vendor": {"js_variable": decoded.get("js_variable"),
                       "branch": decoded.get("branch"),
                       "rows": len(decoded["rows"]),
                       "first_date": decoded["rows"][0]["date"] if decoded["rows"] else None,
                       "last_date": decoded["rows"][-1]["date"] if decoded["rows"] else None},
            "reference_basis_stored": sorted({r.get("adjustment_mode")
                                              for r in reference_rows}, key=str),
            "reference_sources": sorted({r.get("source") for r in reference_rows}, key=str),
            "reference_fetch_times": sorted({r.get("updated_at")
                                             for r in reference_rows}, key=str),
            "boundaries": boundaries(reference_rows),
            "segments": segments,
            "comparison": comparison,
            "usable_count_agreement": {
                "overall_compared_dates": comparison["compared_dates"],
                "sum_of_segment_compared_dates": sum(s["compared_dates"]
                                                     for s in segments),
                "agree": comparison["compared_dates"] == sum(s["compared_dates"]
                                                             for s in segments),
                "note": ("both views consume one pairing, so agreement is structural; it "
                         "is asserted here and in the suite"),
            },
        }
    return results


def documented_470_row_segments(results):
    """Verify the segment figures the P1 proposal documents (section 4)."""
    checked = {}
    for job in ("sh600011", "bj920000"):
        found = [s for s in results.get(job, {}).get("boundaries", {})
                 .get("source_and_updated_at_segments", []) if s["rows"] == 470]
        checked[job] = [{"rows": s["rows"], "first_date": s["first_date"],
                         "last_date": s["last_date"], "key": s["key"]} for s in found]
    source_only = [s for s in results.get("sh600011", {}).get("boundaries", {})
                   .get("source_only_spans", []) if s["rows"] == 471]
    return {
        "expected": ("each stock carries one 470-row segment sharing source AND "
                     "updated_at over 2024-08-13..2026-07-23; SH600011's same-source span "
                     "is 471 rows because 2026-07-24 has a different updated_at"),
        "sh600011_470_row_segments": checked["sh600011"],
        "bj920000_470_row_segments": checked["bj920000"],
        "sh600011_471_row_source_only_spans": [
            {"rows": s["rows"], "first_date": s["first_date"],
             "last_date": s["last_date"]} for s in source_only],
        "verified": (len(checked["sh600011"]) == 1 and len(checked["bj920000"]) == 1
                     and len(source_only) == 1
                     and checked["sh600011"][0]["first_date"] == "2024-08-13"
                     and checked["sh600011"][0]["last_date"] == "2026-07-23"
                     and checked["bj920000"][0]["first_date"] == "2024-08-13"
                     and checked["bj920000"][0]["last_date"] == "2026-07-23"),
    }


# ------------------------------------------------------------------------ reporting
def render_report(payload):
    lines = ["# G-3 ratio analysis, r2 — retained vendor closes versus the retained "
             "reference",
             "",
             "> **Exploratory measurement only.** " + DISCLAIMER,
             "> Vendor closes were **decoded** from retained bodies with the pinned",
             "> routine; **the adapter was not replayed**. No network, SQLite, capture,",
             "> service, production write, staging, commit or push.",
             "",
             "* **Ratio direction:** " + RATIO_DIRECTION,
             "* **Difference:** difference = vendor_close - reference_close",
             "* **Change:** " + CHANGE_DEFINITION,
             "* **Adjacency:** " + ADJACENCY_NOTE,
             "* **Price validity (one shared rule):** " + VALIDITY_RULE,
             "* **Normalization:** " + NORMALIZATION,
             "* Selected revision: `%s`" % payload["inputs"]["revision"],
             "",
             "## Coverage, duplicates and validity",
             "",
             "| symbol | class | vendor rows | reference rows | reference span | matched |"
             " compared (usable) | ref dates missing from vendor | vendor dates in span "
             "missing from ref | duplicates | invalid closes (vendor/ref) | matched but "
             "unusable |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for job, data in payload["results"].items():
        c = data["comparison"]
        lines.append("| `%s` | %s | %d | %d | %s..%s | %d | %d | %d | %d | v %d / r %d | "
                     "%d / %d | %d |"
                     % (job, data["instrument_class"], c["vendor_rows"],
                        c["reference_rows"], c["reference_span"][0],
                        c["reference_span"][1], c["matched_dates"],
                        c["compared_dates"],
                        len(c["reference_dates_missing_from_vendor"]),
                        len(c["vendor_dates_in_span_missing_from_reference"]),
                        len(c["duplicate_vendor_dates"]),
                        len(c["duplicate_reference_dates"]),
                        len(c["invalid_vendor_closes"]),
                        len(c["invalid_reference_closes"]),
                        len(c["matched_dates_excluded_as_unusable"])))
    for job, data in payload["results"].items():
        c = data["comparison"]
        changes = c["ratio_changes"]
        lines += ["", "## `%s` (%s)" % (job, data["instrument_class"]), "",
                  "Reference basis stored: %s. Sources: %s. Distinct fetch times: %d. "
                  "Overall usable %d == sum of segment usable %d: %s."
                  % (", ".join(map(str, data["reference_basis_stored"])),
                     ", ".join(map(str, data["reference_sources"])),
                     len(data["reference_fetch_times"]),
                     data["usable_count_agreement"]["overall_compared_dates"],
                     data["usable_count_agreement"]["sum_of_segment_compared_dates"],
                     data["usable_count_agreement"]["agree"]),
                  "",
                  "Ratio over %d compared dates: min %.10g, median %.10g, max %.10g; "
                  "%d distinct rounded values in %d piecewise-constant runs."
                  % (c["compared_dates"], c["ratio"]["min"], c["ratio"]["median"],
                     c["ratio"]["max"], c["ratio"]["distinct_rounded"],
                     len(c["ratio"]["runs"])),
                  "",
                  "Difference: min %+.4f, median %+.4f, max %+.4f; %d distinct rounded "
                  "values in %d runs."
                  % (c["difference"]["min"], c["difference"]["median"],
                     c["difference"]["max"], c["difference"]["distinct_rounded"],
                     len(c["difference"]["runs"])),
                  "",
                  "**Consecutive-usable-date ratio changes:** %d pairs — %d zero, %d "
                  "nonzero; %d at a source/fetch-time boundary; %d with skipped "
                  "intervening dates; largest absolute change %s (a magnitude, not a "
                  "threshold)."
                  % (changes["pairs"], changes["zero_changes"],
                     changes["nonzero_changes"],
                     changes["pairs_at_a_metadata_boundary"],
                     changes["pairs_with_skipped_dates"],
                     ("%.10g" % changes["largest_absolute_change"])
                     if changes["largest_absolute_change"] is not None else "n/a"),
                  ""]
        boundary_records = [r for r in changes["records"] if r["metadata_boundary"]]
        if boundary_records:
            lines += ["Pairs that straddle a metadata boundary:", "",
                      "| from | to | change (unrounded) | source changed | updated_at "
                      "changed | skipped dates |", "|---|---|---|---|---|---|"]
            for record in boundary_records:
                lines.append("| %s | %s | %+.12g | %s | %s | %d |"
                             % (record["from_date"], record["to_date"], record["change"],
                                record["source_changed"], record["updated_at_changed"],
                                len(record["skipped_matched_but_unusable"])
                                + len(record["skipped_reference_only_dates"])
                                + len(record["skipped_vendor_only_dates"])))
            lines.append("")
        lines += ["| segment (source / updated_at) | rows | span | compared | ratio "
                  "min..max | distinct ratios | distinct differences |",
                  "|---|---|---|---|---|---|---|"]
        for segment in data["segments"]:
            lines.append("| `%s` / `%s` | %d | %s..%s | %d | %s | %d | %d |"
                         % (segment["key"]["source"], segment["key"]["updated_at"],
                            segment["rows"], segment["first_date"], segment["last_date"],
                            segment["compared_dates"],
                            ("%.10g..%.10g" % (segment["ratio_min"], segment["ratio_max"]))
                            if segment["compared_dates"] else "n/a",
                            segment["ratio_distinct_rounded"],
                            segment["difference_distinct_rounded"]))
        if len(c["difference"]["runs"]) <= 12:
            lines += ["", "Difference runs, in full:", ""]
            for run in c["difference"]["runs"]:
                lines.append("* `%+.4f` over %s .. %s (%d sessions)"
                             % (run["value"], run["first_date"], run["last_date"],
                                run["sessions"]))
        lines += ["", "Source / fetch-time boundary dates: %s."
                  % (", ".join("`%s`" % d for d in
                               data["boundaries"]["source_or_fetch_time_boundaries"])
                     or "none")]
        if c["invalid_vendor_closes"] or c["invalid_reference_closes"]:
            low, high = c["reference_span"]
            inside = [e for e in c["invalid_vendor_closes"] if low <= e["date"] <= high]
            lines += ["", "Invalid closes — vendor: %s; reference: %s. %d of the vendor "
                      "ones fall inside the reference span; the rest lie outside it. "
                      "Matched counts are unaffected by invalidity."
                      % ([e["date"] for e in c["invalid_vendor_closes"]] or "none",
                         [e["date"] for e in c["invalid_reference_closes"]] or "none",
                         len(inside))]
    lines += ["", "## Documented 470-row segments", "", "```json",
              json.dumps(payload["documented_segments"], indent=2, ensure_ascii=False),
              "```", "",
              "## What this does and does not establish", "",
              "It establishes measured coverage, validity, the ratio and difference series "
              "over every usable common date, the consecutive-usable-date changes with "
              "their skipped-date and metadata context, and the per-segment breakdown. It "
              "**does not** interpret any change as a corporate action, define any "
              "tolerance or acceptance threshold, assign or alter a basis label, alter any "
              "eligibility result, close U-6 or P1, or change the capability verdict, "
              "which remains **FAIL**.", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------ main
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--revision", default=str(DEFAULT_REVISION))
    parser.add_argument("--out-dir", default=str(HERE))
    args = parser.parse_args(argv)

    revision = Path(args.revision).resolve()
    out_dir = Path(args.out_dir).resolve()
    if out_dir != HERE:
        raise SystemExit("this analysis writes only into its own directory (%s)" % HERE)

    guarded = sorted(p for p in SMOKE.iterdir() if p.is_dir() and p.name.startswith(
        ("evidence_", "revision_", "receipts_", "frozen_impl_", "basis_eval_",
         "g3_ratio_analysis_20260909")))
    guarded = [p for p in guarded if p != HERE]

    def tree(root):
        return {p.relative_to(root).as_posix(): sha256_file(p)
                for p in sorted(Path(root).rglob("*")) if p.is_file()}

    before = {p.name: tree(p) for p in guarded}
    manifest, extract, vendor = load_inputs(revision)
    results = analyse(manifest, extract, vendor)
    payload = {
        "schema": "m2b.g3_ratio_analysis.v2",
        "supersedes": ("claude methods/_m2_smoke/g3_ratio_analysis_20260909/ "
                       "(preserved unchanged; this directory is additive)"),
        "corrections": {
            "G3-R1": ("one strict finite-positive price validator shared by the full-span "
                      "and per-segment analysis; booleans, None, strings and non-finite "
                      "values are invalid and never coerced; one pairing feeds both views "
                      "so usable counts agree structurally"),
            "G3-R2": ("explicit consecutive-usable-common-date ratio changes with from/to "
                      "dates, unrounded ratio(t) - ratio(previous usable date), skipped "
                      "intervening dates and source/updated_at boundary flags; price "
                      "differences retained"),
        },
        "disclaimer": DISCLAIMER,
        "definitions": {"ratio": RATIO_DIRECTION, "change": CHANGE_DEFINITION,
                        "adjacency": ADJACENCY_NOTE, "validity": VALIDITY_RULE,
                        "normalization": NORMALIZATION},
        "inputs": {
            "revision": repo_relative(revision),
            "capture_run_id": manifest.get("run_id"),
            "reference_extract_content_sha256": extract.get("content_sha256"),
            "input_hashes": {
                name: sha256_file(revision / name)
                for name in ["capture_manifest.json", "reference/reference_extract.json"]
                + ["raw/" + r["raw_file"] for r in manifest.get("requests", [])
                   if r.get("kind") == "klc" and r.get("raw_file")]},
            "hk_js_decode_sha256_pinned": dec.HK_JS_DECODE_SHA256,
            "adapter_replayed": False,
        },
        "code_hashes": {
            "g3_ratio_analysis.py": sha256_file(Path(__file__).resolve()),
            "test_g3_ratio_analysis.py": (
                sha256_file(HERE / "test_g3_ratio_analysis.py")
                if (HERE / "test_g3_ratio_analysis.py").exists() else None),
            "sina_klc_decoder.py": sha256_file(SMOKE / "sina_klc_decoder.py"),
            "smoke_capture.py": sha256_file(SMOKE / "smoke_capture.py"),
        },
        "results": results,
        "documented_segments": documented_470_row_segments(results),
    }
    after = {p.name: tree(p) for p in guarded}
    changed = sorted(name for name in before if before[name] != after[name])
    payload["preservation"] = {"guarded_directories": len(guarded),
                               "changed_during_analysis": changed,
                               "unchanged": not changed}

    # allow_nan=False proves no non-finite value reached the output.
    (out_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True,
                   allow_nan=False) + "\n", encoding="utf-8")
    (out_dir / "REPORT.md").write_text(render_report(payload), encoding="utf-8")
    provenance = {
        "schema": "m2b.g3_ratio_analysis.provenance.v2",
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "supersedes": payload["supersedes"],
        "corrections": payload["corrections"],
        "inputs": payload["inputs"],
        "code_hashes": payload["code_hashes"],
        "output_hashes": {name: sha256_file(out_dir / name)
                          for name in ("results.json", "REPORT.md")},
        "preservation": payload["preservation"],
        "disclaimer": DISCLAIMER,
    }
    (out_dir / "PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False, sort_keys=True,
                   allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": [repo_relative(out_dir / n) for n in
                    ("results.json", "REPORT.md", "PROVENANCE.json")],
        "documented_segments_verified": payload["documented_segments"]["verified"],
        "preservation": payload["preservation"],
        "summary": {job: {
            "matched": d["comparison"]["matched_dates"],
            "compared": d["comparison"]["compared_dates"],
            "usable_counts_agree": d["usable_count_agreement"]["agree"],
            "ratio_change_pairs": d["comparison"]["ratio_changes"]["pairs"],
            "zero_changes": d["comparison"]["ratio_changes"]["zero_changes"],
            "boundary_pairs": d["comparison"]["ratio_changes"][
                "pairs_at_a_metadata_boundary"],
        } for job, d in results.items()},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
