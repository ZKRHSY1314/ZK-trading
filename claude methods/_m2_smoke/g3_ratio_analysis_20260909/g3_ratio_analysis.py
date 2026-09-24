"""G-3: an exploratory offline comparison of retained vendor closes with the retained
reference extract, over ALL available common dates.

Scope and discipline
--------------------
This is **exploratory measurement only**. It invents **no acceptance threshold**, infers
**no corporate action**, changes **no basis label and no eligibility**, does **not** close
U-6 or P1, and does **not** upgrade the capability verdict, which remains **FAIL**. It
answers gap **G-3** of `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` only in the sense of computing
the comparison that had never been computed; what the numbers *mean* is left open.

Inputs, all retained and read-only
----------------------------------
`revision_20260908T082833Z_r2abc_v2/`: `capture_manifest.json`, the `raw/*.bin` history
bodies and `reference/reference_extract.json`. The vendor closes are obtained with the
existing offline decoder (`sina_klc_decoder.decode_klc`) and the pinned `hk_js_decode`
routine. **The adapter is never replayed**; `stock_zh_a_daily` and the index adapter are
not called. No network, no SQLite, no capture, no service.

Ratio direction and normalization - stated, not implied
-------------------------------------------------------
* **ratio = vendor_close / reference_close** - the live Sina close divided by the cached
  reference close. This is the direction `I2`/`B4` use.
* **difference = vendor_close - reference_close**, reported alongside, because an additive
  and a multiplicative relationship are not distinguishable from the ratio alone.
* **Normalization: none.** No rebasing, no scaling, no unit conversion, no re-rounding of
  the stored values. Run-grouping rounds ratios and differences to 6 decimal places
  **solely** to group exact repeats; that rounding is reported and is not a tolerance.

The index is treated separately: its reference is stored on basis `none`, as is the served
index series, so it cannot discriminate anything about stock adjustment. It is reported as
a control, not as evidence about the stocks.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import itertools
import json
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
NORMALIZATION = ("none - no rebasing, scaling, unit conversion or re-rounding of stored "
                 "values; run-grouping rounds to %d decimal places only to group exact "
                 "repeats, which is not a tolerance" % RUN_ROUNDING_DP)
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


# ------------------------------------------------------------------------- loading
def load_inputs(revision=DEFAULT_REVISION, *, routine=None, racer_factory=None):
    """Retained manifest, reference extract and DECODED vendor history rows.

    Decoding only: the pinned routine is verified by `decode_klc` itself, and no adapter
    function is called.
    """
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
    for value, group in itertools.groupby(ordered, key=lambda r: tuple(r.get(k)
                                                                      for k in keys)):
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


# --------------------------------------------------------------------- comparison
def compare_series(vendor_rows, reference_rows):
    """Date coverage, data validity, and the per-date ratio and difference."""
    vendor = {}
    duplicate_vendor = []
    for row in vendor_rows:
        if row["date"] in vendor:
            duplicate_vendor.append(row["date"])
        vendor[row["date"]] = row
    reference = {}
    duplicate_reference = []
    for row in reference_rows:
        if row["trade_date"] in reference:
            duplicate_reference.append(row["trade_date"])
        reference[row["trade_date"]] = row

    def invalid(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return True
        return not (number > 0) or number != number or number in (float("inf"),
                                                                  float("-inf"))

    invalid_vendor = sorted(d for d, r in vendor.items() if invalid(r.get("close")))
    invalid_reference = sorted(d for d, r in reference.items()
                               if invalid(r.get("close")))

    span_low = min(reference) if reference else None
    span_high = max(reference) if reference else None
    vendor_in_span = {d for d in vendor if span_low and span_low <= d <= span_high}
    matched = sorted(d for d in reference if d in vendor)
    usable = [d for d in matched
              if d not in invalid_vendor and d not in invalid_reference]

    ratios, differences = [], []
    for date in usable:
        live = float(vendor[date]["close"])
        cached = float(reference[date]["close"])
        ratios.append((date, live / cached))
        differences.append((date, round(live - cached, 10)))

    values = [value for _d, value in ratios]
    deltas = [value for _d, value in differences]
    return {
        "reference_rows": len(reference_rows),
        "vendor_rows": len(vendor_rows),
        "reference_span": [span_low, span_high],
        "vendor_dates_within_reference_span": len(vendor_in_span),
        "matched_dates": len(matched),
        "reference_dates_missing_from_vendor": sorted(d for d in reference
                                                      if d not in vendor),
        "vendor_dates_in_span_missing_from_reference": sorted(vendor_in_span
                                                              - set(reference)),
        "duplicate_vendor_dates": sorted(set(duplicate_vendor)),
        "duplicate_reference_dates": sorted(set(duplicate_reference)),
        "invalid_vendor_closes": invalid_vendor,
        "invalid_reference_closes": invalid_reference,
        "compared_dates": len(usable),
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
    }


def per_segment(vendor_rows, reference_rows):
    """The same comparison restricted to each source+updated_at segment."""
    vendor = {r["date"]: r for r in vendor_rows}
    out = []
    for segment in contiguous_segments(reference_rows, ("source", "updated_at")):
        block = [r for r in reference_rows
                 if segment["first_date"] <= r["trade_date"] <= segment["last_date"]]
        pairs = [(r["trade_date"], float(vendor[r["trade_date"]]["close"]),
                  float(r["close"]))
                 for r in sorted(block, key=lambda x: x["trade_date"])
                 if r["trade_date"] in vendor and float(r["close"]) > 0
                 and float(vendor[r["trade_date"]]["close"]) > 0]
        ratios = [live / cached for _d, live, cached in pairs]
        deltas = [round(live - cached, 10) for _d, live, cached in pairs]
        out.append({
            **segment,
            "compared_dates": len(pairs),
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
        reference_rows = sorted(extract["rows"][symbol],
                                key=lambda r: r["trade_date"])
        results[job_name] = {
            "instrument_class": jobs[job_name]["instrument_class"],
            "manifest_symbol": symbol,
            "vendor": {"js_variable": decoded.get("js_variable"),
                       "branch": decoded.get("branch"),
                       "rows": len(decoded["rows"]),
                       "first_date": decoded["rows"][0]["date"],
                       "last_date": decoded["rows"][-1]["date"]},
            "reference_basis_stored": sorted({r.get("adjustment_mode")
                                              for r in reference_rows}),
            "reference_sources": sorted({r.get("source") for r in reference_rows}),
            "reference_fetch_times": sorted({r.get("updated_at")
                                             for r in reference_rows}),
            "boundaries": boundaries(reference_rows),
            "segments": per_segment(decoded["rows"], reference_rows),
            "comparison": compare_series(decoded["rows"], reference_rows),
        }
    return results


def documented_470_row_segments(results):
    """Verify the segment figures the P1 proposal documents (§4)."""
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
    lines = ["# G-3 ratio analysis — retained vendor closes versus the retained reference",
             "",
             "> **Exploratory measurement only.** " + DISCLAIMER,
             "> Offline: the vendor closes were **decoded** from retained bodies with the",
             "> pinned routine; **the adapter was not replayed**. No network, SQLite,",
             "> capture, service, production write, staging, commit or push.",
             "",
             "* **Ratio direction:** " + RATIO_DIRECTION,
             "* **Difference:** difference = vendor_close - reference_close",
             "* **Normalization:** " + NORMALIZATION,
             "* Selected revision: `%s`" % payload["inputs"]["revision"],
             "",
             "## Coverage, duplicates and validity",
             "",
             "| symbol | class | vendor rows | reference rows | reference span | compared "
             "dates | ref dates missing from vendor | vendor dates in span missing from "
             "ref | duplicate dates | invalid closes |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for job, data in payload["results"].items():
        c = data["comparison"]
        lines.append("| `%s` | %s | %d | %d | %s..%s | %d | %d | %d | vendor %d / ref %d "
                     "| vendor %d / ref %d |"
                     % (job, data["instrument_class"], c["vendor_rows"],
                        c["reference_rows"], c["reference_span"][0],
                        c["reference_span"][1], c["compared_dates"],
                        len(c["reference_dates_missing_from_vendor"]),
                        len(c["vendor_dates_in_span_missing_from_reference"]),
                        len(c["duplicate_vendor_dates"]),
                        len(c["duplicate_reference_dates"]),
                        len(c["invalid_vendor_closes"]),
                        len(c["invalid_reference_closes"])))
    for job, data in payload["results"].items():
        c = data["comparison"]
        lines += ["", "## `%s` (%s)" % (job, data["instrument_class"]), "",
                  "Reference basis stored: %s. Sources: %s. Distinct fetch times: %d."
                  % (", ".join(map(str, data["reference_basis_stored"])),
                     ", ".join(map(str, data["reference_sources"])),
                     len(data["reference_fetch_times"])),
                  "",
                  "Ratio over %d compared dates: min %.10g, median %.10g, max %.10g; "
                  "%d distinct rounded values in %d piecewise-constant runs."
                  % (c["compared_dates"], c["ratio"]["min"], c["ratio"]["median"],
                     c["ratio"]["max"], c["ratio"]["distinct_rounded"],
                     len(c["ratio"]["runs"])),
                  "",
                  "Difference over the same dates: min %+.4f, median %+.4f, max %+.4f; "
                  "%d distinct rounded values in %d runs."
                  % (c["difference"]["min"], c["difference"]["median"],
                     c["difference"]["max"], c["difference"]["distinct_rounded"],
                     len(c["difference"]["runs"])),
                  "",
                  "| segment (source / updated_at) | rows | span | compared | ratio "
                  "min..max | distinct ratios | distinct differences |",
                  "|---|---|---|---|---|---|---|"]
        for segment in data["segments"]:
            lines.append("| `%s` / `%s` | %d | %s..%s | %d | %s | %d | %d |"
                         % (segment["key"]["source"], segment["key"]["updated_at"],
                            segment["rows"], segment["first_date"],
                            segment["last_date"], segment["compared_dates"],
                            ("%.10g..%.10g" % (segment["ratio_min"],
                                               segment["ratio_max"]))
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
            inside = [d for d in c["invalid_vendor_closes"]
                      if c["reference_span"][0] <= d <= c["reference_span"][1]]
            lines += ["", "Non-positive closes: vendor %s; reference %s. %d of the vendor "
                      "ones fall inside the reference span and are therefore excluded "
                      "from the comparison; the rest lie outside it."
                      % (c["invalid_vendor_closes"] or "none",
                         c["invalid_reference_closes"] or "none", len(inside))]
    lines += ["", "## Documented 470-row segments",
              "", "```json",
              json.dumps(payload["documented_segments"], indent=2, ensure_ascii=False),
              "```", "",
              "## What this does and does not establish", "",
              "It establishes the measured coverage, validity and the ratio and difference "
              "series over every available common date, per source-and-fetch-time segment. "
              "It **does not** interpret any change as a corporate action, define any "
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
        ("evidence_", "revision_", "receipts_", "frozen_impl_", "basis_eval_")))
    def tree(root):
        return {p.relative_to(root).as_posix(): sha256_file(p)
                for p in sorted(Path(root).rglob("*")) if p.is_file()}
    before = {p.name: tree(p) for p in guarded}

    manifest, extract, vendor = load_inputs(revision)
    results = analyse(manifest, extract, vendor)
    payload = {
        "schema": "m2b.g3_ratio_analysis.v1",
        "disclaimer": DISCLAIMER,
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
            "sina_klc_decoder.py": sha256_file(SMOKE / "sina_klc_decoder.py"),
            "smoke_capture.py": sha256_file(SMOKE / "smoke_capture.py"),
        },
        "results": results,
        "documented_segments": documented_470_row_segments(results),
    }
    after = {p.name: tree(p) for p in guarded}
    changed = sorted(name for name in before if before[name] != after[name])
    payload["preservation"] = {
        "guarded_directories": len(guarded),
        "changed_during_analysis": changed,
        "unchanged": not changed,
    }

    (out_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    (out_dir / "REPORT.md").write_text(render_report(payload), encoding="utf-8")
    (out_dir / "PROVENANCE.json").write_text(
        json.dumps({
            "schema": "m2b.g3_ratio_analysis.provenance.v1",
            "generated_at_utc": _dt.datetime.now(_dt.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "inputs": payload["inputs"],
            "code_hashes": payload["code_hashes"],
            "preservation": payload["preservation"],
            "disclaimer": DISCLAIMER,
        }, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [repo_relative(out_dir / n) for n in
                                  ("results.json", "REPORT.md", "PROVENANCE.json")],
                      "documented_segments_verified":
                          payload["documented_segments"]["verified"],
                      "preservation": payload["preservation"],
                      "summary": {job: {
                          "compared_dates": d["comparison"]["compared_dates"],
                          "ratio_runs": len(d["comparison"]["ratio"]["runs"]),
                          "difference_runs": len(d["comparison"]["difference"]["runs"]),
                      } for job, d in results.items()}},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
