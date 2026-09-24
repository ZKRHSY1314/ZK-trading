# U-6 retained-artifact study — additive and multiplicative relations, E-1, source stratification

> **Revision 2** — status `proposed for review`. Task `U6-STUDY-R1-20260909`, correcting revision 1
> (`99039500…`) against `M2B_U6_RETAINED_STUDY_CODEX_REVIEW.md` findings **US-R1 … US-R4**. The
> review independently reproduced all 14 interval rows and the seven conditional step comparisons;
> those outcomes are preserved unchanged. What is corrected is the delivery of the code, and
> several inferences that reached past the evidence.
>
> **Retained JSON only.** No network, no source query, no new extract, no SQLite open, no capture,
> no adapter replay, no fresh decoding run, no service, no token or account access. No module that
> initialises a runtime service or data provider was imported.
>
> **Files.** In the **repository**, this is the only file created by this task or by revision 1,
> and nothing else was modified. **Outside the repository**, revision 1's run did create three
> scratch scripts in the session scratchpad — see §4.4, which states their paths, records that
> this departed from the assignment's in-memory single-file execution form, and confirms they are
> retained unaltered.
>
> **This adopts nothing.** No vendor-basis sufficiency rule, no threshold, no tolerance, no
> calibration, no label, gate or eligibility change, no policy adoption. **P1 open, U-6 deferred,
> every eligibility result false, source capability FAIL (including the retained EV6
> disagreements), both capture authorizations consumed.** Not M2 completion.
>
> **What it is.** Two conditional relations are tested for **feasibility** inside identified
> inter-event intervals, under one rounding envelope stated before any comparison. Feasibility is
> **not** identification of a supplier algorithm, a cause, a reference basis, a price basis for
> either leg, or which side of a comparison is wrong.

---

## 0. What revision 2 corrects

| Finding | Correction |
|---|---|
| **US-R1(a)** — §4 claimed three passes "reproduced verbatim", but §4.2/§4.3 were fragments with undefined names; the delivered commands were not executable as given | §4 now carries **one complete self-contained program** between explicit sentinel markers, with pinned-input assertions before any computation, exact-representation parsing, the full interval/event/stratification loops, and **every** calculation behind §§5.1–5.7. §4.1 gives a **stdin command that needs no scratch script**: it extracts the program from this file and pipes it to Python. It was executed that way and its output is what §5 reports |
| **US-R1(b)** — the header said nothing outside this file was created, while §4 said scratch scripts were used | **Contradiction resolved in favour of the facts.** §4.4 names the three scratch scripts, their absolute paths and sizes, records that creating them **departed from the assigned in-memory single-file form**, distinguishes repository scope from filesystem scope, and confirms they are **retained unaltered** rather than deleted to tidy the history |
| **US-R2** — E-1's discrepancy was called an "artefact" of an additive reading | **Withdrawn throughout** (§5.5, §5.6, §7) and replaced with **conditional compatibility**: the disclosed 0.27 is *not excluded* by the examined multiplicative mapping and rounding envelope; its causal role is **unestablished**. The 28-versus-27 comparison remains a real stored observation and is **not** erroneous. The pairwise additive calculation is restated as resting on **its own conditional premise** (a latent 27-cent step), which it does not establish. E-2's exact step is left as an observation with **no asserted cause and no evidentiary ranking** |
| **US-R3(a)** — "the instrument confound is broken"; "a narrower price range does not account for it" | **Both withdrawn.** The observation excludes only the simplistic reading in which **instrument identity alone fixes one relation for all dates**; it does not exclude an instrument/time interaction or a vendor-side change. Comparable price-range ratios (×1.24 vs ×1.27) do **not** control for effect size, precision, sample size or price path, so no price-range explanation is eliminated |
| **US-R3(b)** — the stratification was assigned to the reference side and read as reducing confidence in the `qfq` label | **Withdrawn.** The pairwise findings cannot be attributed to the reference leg while excluding the vendor leg, and they do not establish that the uniform label is unreliable or that differing conventions caused anything. §5.7 is now descriptive. The reference basis remains **unverified**, which was already sufficient to withhold certification |
| **US-R3(c)** — §9's proposed follow-up promised to separate a pipeline cause from market variation | **Withdrawn.** Restated as detecting and describing **field or unit inconsistencies and candidate anomalies**, with alternative explanations preserved: a change at a source boundary does not establish a pipeline cause, and its absence does not isolate price adjustment. **Not executed in this correction** |
| **US-R4(a)** — C-step intervals described as "5 cents wide" | Corrected: `[18,22]` cents has **continuous width 4 cents** and contains five integer-cent grid points. The unknown constants are **continuous** under the envelope. Endpoints unchanged |
| **US-R4(b)** — §5.4 presented as prediction | Relabelled a **within-sample algebraic consistency check**: the constant is estimated from the same observations, so it is not an independent prediction or a validation |
| **US-R4(c)** — the reconstruction residual mixed representations | The program now compares against the **exact JSON decimal token** (`parse_float=Decimal`), and §5.2 reports **both** metrics side by side with the representation named for each, stating that they differ because the representations differ — not because reconstruction fails |
| **US-R4(d)** — the envelope's scope | R1 is now stated as a closed half-cent **nearest-rounding** envelope, **not** an envelope for arbitrary truncation. Feasibility is **existential** within it and does not imply any deterministic tie rule holds; infeasibility is robust only to **subsets** of it |
| **US-R4(e)** — "an unidentified event would appear as an infeasibility" | **Withdrawn.** Some events could preserve a relation or stay inside the rounding bounds. **G-e remains unestablished**, with no detection property claimed |

Preserved unchanged: the 14 interval outcomes, the seven conditional step comparisons, the source
evidence, and the certification-withheld conclusion.

---

## 1. Inputs, with hashes asserted before use

The program **asserts** both pins before computing anything, so a mismatch aborts rather than
producing numbers. Pins are those recorded in the **accepted** G3 provenance
(`_m2_smoke/g3_ratio_analysis_20260909_r2/PROVENANCE.json`, `1a262d74…`).

| Input | SHA-256 | Asserted |
|---|---|---|
| `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/results.json` | `538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd` | **match** |
| `claude methods/_m2_smoke/revision_20260908T082833Z_r2abc_v2/reference/reference_extract.json` | `ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2` | **match** |

The extract's own `content_sha256` is asserted equal to
`3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9`, agreeing with the G3
provenance field of the same name; `row_counts` reads `{SH600011: 538, SH000300: 538, BJ920000: 501}`.

**Disclosed cash amounts** come from the accepted G1 delivery — `REPORT.md` `77941f8c…` §2 — each
backed by a retained Tier A notice: `2024-068` `6f22f7be…` (BJ 0.06, ex 2024-09-30), `2025-047`
`aba4cb40…` (BJ 0.08, ex 2025-05-15), `2025-103` `157dc615…` (BJ 0.070, ex 2025-09-18), `2026-037`
`c8bcf19f…` (BJ 0.08, ex 2026-05-25), `2025-036` `439ceb65…` (SH 0.27, ex 2025-07-10), `2026-036`
`269ed39f…` (SH 0.40, ex 2026-07-03), and — contextual, outside the task interval — `2024-034`
`ffe858d9…` (SH 0.20, ex 2024-07-11).

**No adapter, decoder or raw vendor body was read.** `results.json`'s `vendor` block carries only
metadata (`branch: O`, `js_variable`, row count, first/last date); it holds no vendor closes.

---

## 2. Assumptions, stated before any comparison

**R1 — rounding envelope.** Every stored price is a 2-decimal value, and the pre-rounding quantity
it represents lies within **half a cent** of it: writing `Rc`, `Vc` for the stored reference and
vendor values in integer cents, `100·R* ∈ [Rc − 0.5, Rc + 0.5]` and `100·V* ∈ [Vc − 0.5, Vc + 0.5]`.

Three properties of this envelope, stated because the verdicts depend on them:

* It is a **nearest-rounding** envelope. It is **not** an envelope for arbitrary truncation or for
  a rule with a larger error bound, and no such rule is covered by any verdict below.
* Feasibility is **existential**: a "feasible" verdict says some admissible pre-rounding values and
  some constant satisfy the relation. It does **not** say any deterministic tie-breaking rule
  (half-up, half-even, …) is satisfied, and none is tested.
* Because narrowing each per-date admissible set cannot create an intersection, **infeasibility
  verdicts survive any restriction to a subset of this envelope** — but they say nothing about
  envelopes *wider* than it.

Closed intervals are used, which is the choice that **favours feasibility**.

**H-add(j) and H-mul(j) — the two conditional relations,** stated directly on pre-rounding
quantities as `M2B_U6_READINESS_ASSESSMENT.md` §3.1 requires, with no intermediate claim about how
either quantity is built:

* **H-add(j):** `V* − R* = C_j`, a constant, throughout interval `j`.
* **H-mul(j):** `V* / R* = K_j`, a constant, throughout interval `j`.

`C_j` and `K_j` are **continuous** unknowns; only the stored values are on a cent grid.

**A1 — interval boundaries.** Intervals are cut at the **identified** Tier A ex-dates. The event
set is **not established as complete** (G-e), so a relation found feasible inside an interval is
feasible *given these boundaries*.

**A2 — reference basis.** The extract *records* `adjustment_mode` per row. It is **not
independently certified** here, and nothing below establishes it.

**A3 — mapping premise, used only in §5.5, and not established.** A cash amount `D` at an ex-date
scales a multiplicative reference factor by `(P − D)/P`, where `P` is the prior session's
**unadjusted** close. Under H-mul this gives `K_before / K_after = P/(P − D)`.

**A4 — orientation premise, used only in §5.5, and not established.** A3's `P` is taken to be the
**vendor** leg. Both relations constrain the *pair* of series; **neither identifies which leg is
unadjusted**, and A4 supplies orientation by assumption rather than by evidence.

**A5 — latent-step premise, used only in §5.6, and not established.** The latent difference step at
an ex-date equals the disclosed amount in cents.

**Retained versus reconstructed.** Reference closes are **retained** fields of the extract. Ratios
and differences are **retained** fields of `results.json`. Vendor closes are **not retained
anywhere readable under this authorization**; they are **reconstructed** as
`Vc = Rc + round(100 × retained difference)` and labelled `(recon)`. **A reconstructed vendor close
is never presented as an independently retained raw close.**

**Representation.** The program parses both JSON files with `parse_float=Decimal`, so every value
is the **exact decimal token as written in the file**. Reference closes convert to integer cents
exactly (asserted). Difference tokens are float serialisations of an exact cent count, so they are
taken to the **nearest** integer cent with the residual asserted below `1e-6` cents.

---

## 3. The two feasibility tests, derived from R1 alone

No tolerance is chosen, fitted or tuned. Each test is the exact condition under which a constant
exists that is compatible with every stored pair in the interval under R1. **These are derived
rational bounds, not acceptance thresholds**: they follow from the stated envelope, and no verdict
below is compared against a number anyone selected.

**H-add.** Let `x_t = 100·R*_t`, so `Rc_t = round(x_t)` gives `x_t ∈ [Rc_t − 0.5, Rc_t + 0.5]`, and
`Vc_t = round(x_t + c)` for `c = 100·C_j`. For a single date some admissible `x_t` exists iff
`c ∈ [d_t − 1, d_t + 1]` where `d_t = Vc_t − Rc_t`. Intersecting over the interval:

> **H-add(j) is feasible ⟺ `max_t d_t − min_t d_t ≤ 2` cents**, and the feasible set is then the
> continuous interval `[max_t d_t − 1, min_t d_t + 1]`.

**H-mul.** `Vc_t ∈ [K(Rc_t − 0.5) − 0.5, K(Rc_t + 0.5) + 0.5]` gives, per date,
`K ∈ [(Vc_t − 0.5)/(Rc_t + 0.5), (Vc_t + 0.5)/(Rc_t − 0.5)]`. Intersecting:

> **H-mul(j) is feasible ⟺ `max_t (2Vc_t − 1)/(2Rc_t + 1) ≤ min_t (2Vc_t + 1)/(2Rc_t − 1)`.**

Both are evaluated in exact rational arithmetic (`fractions.Fraction`), so no floating-point
comparison decides any feasibility verdict.

**Why they discriminate at all.** Within an interval the reference price moves, so a constant
difference and a constant ratio make different predictions — the wider the price range, the more
sharply they separate. Equally, they discriminate **nothing** on an interval whose stored
differences are all zero.

---

## 4. The calculation, complete and runnable

### 4.1 Execution command — no scratch script

The program below is delimited by the sentinel comments
`# --- BEGIN U6_STUDY_PROGRAM ---` and `# --- END U6_STUDY_PROGRAM ---`. Extract it from this file
and pipe it to Python on stdin:

```bash
sed -n '/^# --- BEGIN U6_STUDY_PROGRAM ---$/,/^# --- END U6_STUDY_PROGRAM ---$/p' "claude methods/M2B_U6_RETAINED_STUDY.md" | "D:/codex-A股交易/backend/.venv/Scripts/python.exe" -X utf8 -B -
```

Run from the repository root. The sentinels are Python comments, so the extracted text is a valid
program. **Everything reported in §5 is produced by this one run**; no measured value below is
hardcoded in place of a calculation.

### 4.2 Complete program

```python
# --- BEGIN U6_STUDY_PROGRAM ---
"""U6-RETAINED-STUDY-20260909 / U6-STUDY-R1-20260909.

Retained-JSON-only feasibility study of two conditional pre-rounding relations
inside identified inter-event intervals. Asserts input pins before computing.
No network, SQLite, adapter replay, decoding run or data acquisition. Prints
only; writes nothing.
"""
import hashlib
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction as F

ROOT = r"D:\codex-A股交易\claude methods\_m2_smoke"
RESULTS = os.path.join(ROOT, "g3_ratio_analysis_20260909_r2", "results.json")
REFEXT = os.path.join(ROOT, "revision_20260908T082833Z_r2abc_v2", "reference",
                      "reference_extract.json")
PINS = {
    RESULTS: "538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd",
    REFEXT: "ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2",
}
CONTENT_SHA = "3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9"

# Identified Tier A ex-dates and disclosed cash amounts in cents, from the accepted
# G1 delivery. NOT an exhaustive event set (G-e).
EXD = {
    "sh600011": [("2024-07-11", "E-0", 20), ("2025-07-10", "E-1", 27),
                 ("2026-07-03", "E-2", 40)],
    "bj920000": [("2024-09-30", "E-5", 6), ("2025-05-15", "E-6", 8),
                 ("2025-09-18", "E-3", 7), ("2026-05-25", "E-4", 8)],
}
REFKEY = {"sh600011": "SH600011", "bj920000": "BJ920000", "sh000300": "SH000300"}

# ---------------------------------------------------------------- 0. pins first
print("=== 0. pinned inputs asserted before any computation ===")
for path, pin in sorted(PINS.items()):
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert got == pin, ("input hash mismatch", path, got, pin)
    print("  OK %-24s %s" % (os.path.basename(path), got))

# parse_float=Decimal keeps every number as the EXACT decimal token in the file
res = json.load(open(RESULTS, encoding="utf-8"), parse_float=Decimal)
ref = json.load(open(REFEXT, encoding="utf-8"), parse_float=Decimal)
assert ref["content_sha256"] == CONTENT_SHA, "extract content_sha256 mismatch"
print("  OK extract content_sha256 %s" % ref["content_sha256"])
print("  row_counts %s" % dict(ref["row_counts"]))


def cents_exact(dec):
    """Reference closes are exact 2-dp decimals -> exact integer cents."""
    x = dec * 100
    assert x == x.to_integral_value(), ("close is not an exact cent value", dec)
    return int(x)


def cents_nearest(dec, tol=Decimal("1e-6")):
    """Difference tokens are float serialisations of an exact cent count."""
    x = dec * 100
    n = int(x.to_integral_value(rounding=ROUND_HALF_UP))
    assert abs(x - n) < tol, ("difference token not near an integer cent", dec, n)
    return n


def load(symkey):
    """Retained fields + the RECONSTRUCTED vendor cent value, per date."""
    comp = res["results"][symkey]["comparison"]
    ratio = {d: v for d, v in comp["ratio"]["series"]}
    diff = {d: v for d, v in comp["difference"]["series"]}
    rrows = {r["trade_date"]: r for r in ref["rows"][REFKEY[symkey]]}
    rec = {}
    for d, dv in diff.items():
        rr = rrows[d]
        Rc = cents_exact(rr["close"])          # retained
        Dc = cents_nearest(dv)                 # retained (nearest cent of the token)
        rec[d] = dict(Rc=Rc, Vc=Rc + Dc, Dc=Dc, src=rr["source"],
                      up=rr["updated_at"], close=rr["close"], diff=dv,
                      ratio=ratio[d])          # Vc is RECONSTRUCTED, not retained
    return rec, sorted(rec)


def segments(rec, dates):
    """Contiguous runs sharing BOTH source and updated_at."""
    out, cur = [], None
    for d in dates:
        key = (rec[d]["src"], rec[d]["up"])
        if cur is None or cur[0] != key:
            cur = (key, [d])
            out.append(cur)
        else:
            cur[1].append(d)
    return out


def intervals(rec, dates, symkey):
    """segment x identified ex-dates."""
    exs = {d: (n, c) for d, n, c in EXD[symkey]}
    out = []
    for si, ((src, up), sd) in enumerate(segments(rec, dates)):
        cuts = [sd[0]] + sorted(d for d in exs if sd[0] <= d <= sd[-1])
        for i, start in enumerate(cuts):
            end = cuts[i + 1] if i + 1 < len(cuts) else None
            iv = [d for d in sd if d >= start and (end is None or d < end)]
            if iv:
                out.append(dict(seg=si, src=src, up=up, dates=iv,
                                opened_by=exs[start][0] if start in exs else None))
    return out


def add_set(rec, iv):
    """Feasible continuous C interval in cents, or None. Derived from R1."""
    ds = [rec[d]["Dc"] for d in iv]
    lo, hi = F(max(ds) - 1), F(min(ds) + 1)
    return (lo, hi) if lo <= hi else None


def mul_set(rec, iv):
    """Feasible continuous K interval, or None. Derived from R1."""
    lo = max(F(2 * rec[d]["Vc"] - 1, 2 * rec[d]["Rc"] + 1) for d in iv)
    hi = min(F(2 * rec[d]["Vc"] + 1, 2 * rec[d]["Rc"] - 1) for d in iv)
    return (lo, hi) if lo <= hi else None


def mul_gap(rec, iv):
    lo = max(F(2 * rec[d]["Vc"] - 1, 2 * rec[d]["Rc"] + 1) for d in iv)
    hi = min(F(2 * rec[d]["Vc"] + 1, 2 * rec[d]["Rc"] - 1) for d in iv)
    return lo - hi

# ------------------------------------------------- 1. reference metadata (5.1)
print()
print("=== 1. retained reference metadata inventory (5.1) ===")
for sym in ("SH600011", "BJ920000", "SH000300"):
    rows = ref["rows"][sym]
    print("  %-9s rows=%3d adjustment_mode=%s sources=%d updated_at=%d"
          % (sym, len(rows), sorted({r["adjustment_mode"] for r in rows}),
             len({r["source"] for r in rows}), len({r["updated_at"] for r in rows})))
    for s in sorted({r["source"] for r in rows}):
        sub = [r for r in rows if r["source"] == s]
        print("      %-32s n=%-4d modes=%s"
              % (s, len(sub), sorted({r["adjustment_mode"] for r in sub})))

# ------------------------------------- 2. reconstruction, two representations (5.2)
print()
print("=== 2. reconstruction check, both representations named (5.2) ===")
STORE = {}
for symkey in ("sh600011", "bj920000"):
    rec, dates = load(symkey)
    STORE[symkey] = (rec, dates)
    dec_max = F(0)
    flo_max = 0.0
    for d in dates:
        r = rec[d]
        q = F(r["Vc"], r["Rc"])
        dec_max = max(dec_max, abs(q - F(r["ratio"])))                       # exact token
        flo_max = max(flo_max, abs(float(q) - float(r["ratio"])))            # float
    print("  %-9s n=%3d %s..%s" % (symkey, len(dates), dates[0], dates[-1]))
    print("      max |Vc/Rc - ratio| vs EXACT JSON decimal token : %.15e" % float(dec_max))
    print("      max |Vc/Rc - ratio| vs IEEE-754 double of token : %.15e" % flo_max)

# ------------------------------------------------ 3. interval feasibility (5.3)
print()
print("=== 3. interval feasibility: segment x identified ex-dates (5.3) ===")
ROWS = []
for symkey in ("sh600011", "bj920000"):
    rec, dates = STORE[symkey]
    print("--", symkey)
    for iv in intervals(rec, dates, symkey):
        dd = iv["dates"]
        ds = [rec[d]["Dc"] for d in dd]
        Rc = [rec[d]["Rc"] for d in dd]
        A, M = add_set(rec, dd), mul_set(rec, dd)
        allzero = max(ds) == 0 and min(ds) == 0
        ROWS.append(dict(sym=symkey, iv=iv, A=A, M=M, ds=ds, Rc=Rc, allzero=allzero))
        print("  S%d %s..%s n=%-4d Rc %4d..%4d (x%.3f) dsprd=%2dc opened_by=%-4s"
              % (iv["seg"], dd[0], dd[-1], len(dd), min(Rc), max(Rc),
                 max(Rc) / min(Rc), max(ds) - min(ds), iv["opened_by"] or "-"))
        print("      H-add %s%s"
              % (("FEASIBLE C in [%s,%s]c continuous width %s"
                  % (A[0], A[1], A[1] - A[0])) if A else
                 "INFEASIBLE (spread exceeds 2c by %dc)" % (max(ds) - min(ds) - 2),
                 ""))
        print("      H-mul %s"
              % (("FEASIBLE K in [%.6f,%.6f] width %.3e" % (M[0], M[1], float(M[1] - M[0])))
                 if M else "INFEASIBLE by %.6f" % float(mul_gap(rec, dd))))
    print("      segments:", [(s[0][0].split(".", 1)[-1], s[0][1], len(s[1]))
                              for s in segments(rec, dates)])
print("  interval rows produced: %d" % len(ROWS))

# ------------------------------- 4. within-sample algebraic consistency (5.4)
print()
print("=== 4. within-sample algebraic consistency (5.4) ===")
print("  The constant is estimated from the SAME observations; this is an algebraic")
print("  consistency check, not an independent prediction or a validation.")
for row in ROWS:
    rec, _ = STORE[row["sym"]]
    dd, ds, Rc, A, M = row["iv"]["dates"], row["ds"], row["Rc"], row["A"], row["M"]
    if M and not A:
        kmid = (M[0] + M[1]) / 2
        print("  %-9s %s..%s H-mul feasible: observed d spread %dc ; "
              "(K-1)(Rc_max-Rc_min) at K=%.6f -> %.1fc"
              % (row["sym"], dd[0], dd[-1], max(ds) - min(ds), float(kmid),
                 float((kmid - 1) * (max(Rc) - min(Rc)))))
    elif A and not M:
        cmid = F(max(ds) + min(ds), 2)
        obs = [rec[d]["ratio"] for d in dd]
        print("  %-9s %s..%s H-add feasible: observed ratio %.6f..%.6f ; "
              "constant C=%.1fc -> %.6f..%.6f"
              % (row["sym"], dd[0], dd[-1], float(min(obs)), float(max(obs)),
                 float(cmid), float(1 + cmid / max(Rc)), float(1 + cmid / min(Rc))))

# --------------------------- 5. seven conditional step comparisons (5.5)
print()
print("=== 5. disclosed amounts against the surviving relation (5.5) ===")
print("  A3 (mapping) and A4 (orientation) are premises, not findings.")
for symkey in ("sh600011", "bj920000"):
    rec, dates = STORE[symkey]
    ivs = intervals(rec, dates, symkey)
    disc_of = {n: c for _, n, c in EXD[symkey]}
    for i in range(1, len(ivs)):
        a, b = ivs[i - 1], ivs[i]
        if b["opened_by"] is None or a["seg"] != b["seg"]:
            continue
        name = b["opened_by"]
        disc = disc_of[name]
        prev = a["dates"][-1]
        obs_step = rec[prev]["Dc"] - rec[b["dates"][0]]["Dc"]
        print("  %-9s %-4s ex=%s disclosed=%dc observed stored step=%dc (delta %+dc)"
              % (symkey, name, b["dates"][0], disc, obs_step, obs_step - disc))
        Aa, Ab = add_set(rec, a["dates"]), add_set(rec, b["dates"])
        if Aa and Ab:
            lo, hi = Aa[0] - Ab[1], Aa[1] - Ab[0]
            print("      additive: feasible C_before-C_after in [%s,%s]c "
                  "(continuous width %s) contains disclosed %dc = %s"
                  % (lo, hi, hi - lo, disc, lo <= disc <= hi))
        else:
            print("      additive: INFEASIBLE on the %s side -> no C step defined"
                  % ("before" if not Aa else "after"))
        Ma, Mb = mul_set(rec, a["dates"]), mul_set(rec, b["dates"])
        if Ma and Mb:
            lo, hi = Ma[0] / Mb[1], Ma[1] / Mb[0]
            P = F(rec[prev]["Vc"], 100)          # RECONSTRUCTED prior vendor close
            implied = P / (P - F(disc, 100))     # A3 + A4
            print("      multiplicative: feasible K_before/K_after in [%.6f,%.6f] ; "
                  "A3+A4 implied P/(P-D)=%.6f with P=%.2f(recon) -> not excluded = %s"
                  % (lo, hi, implied, float(P), lo <= implied <= hi))
        else:
            print("      multiplicative: INFEASIBLE on the %s side -> no K ratio defined"
                  % ("before" if not Ma else "after"))

# ------------------------------------------- 6. E-1 neighbourhood (5.6)
print()
print("=== 6. E-1 neighbourhood: exact retained tokens + reconstruction (5.6) ===")
rec, dates = STORE["sh600011"]
i = dates.index("2025-07-10")
for d in dates[i - 5:i + 6]:
    r = rec[d]
    print("  %s close=%-6s diff=%-22s ratio=%-22s Rc=%4d Vc=%4d(recon) d=%3dc src=%s"
          % (d, r["close"], r["diff"], r["ratio"], r["Rc"], r["Vc"], r["Dc"],
             r["src"].split(".", 1)[-1]))
prev, ex = dates[i - 1], dates[i]
print("  observed stored step %s -> %s : %dc  (disclosed 27c)"
      % (prev, ex, rec[prev]["Dc"] - rec[ex]["Dc"]))
print("  A5 premise (latent step = 27c) + R1 -> permitted observed steps %dc..%dc"
      % (27 - 2, 27 + 2))
print("  A5 is a premise. Permitting the observation neither establishes A5 nor")
print("  makes the segment-wide H-add infeasibility go away.")

# ------------------------------------- 7. source stratification (5.7)
print()
print("=== 7. descriptive stratification by retained source/fetch metadata (5.7) ===")
print("  %-24s %-21s %-9s %5s %-10s %-10s %s"
      % ("source", "updated_at", "symbol", "n", "H-add", "H-mul", "all-zero d"))
for row in sorted(ROWS, key=lambda r: (r["iv"]["src"], r["iv"]["up"], r["iv"]["dates"][0])):
    iv = row["iv"]
    print("  %-24s %-21s %-9s %5d %-10s %-10s %s"
          % (iv["src"].split(".", 1)[-1], iv["up"], row["sym"], len(iv["dates"]),
             "feasible" if row["A"] else "infeasible",
             "feasible" if row["M"] else "infeasible", row["allzero"]))
print()
print("  Descriptive only. Source, updated_at, calendar span, event set, price path")
print("  and the vendor-side path covary; nothing here attributes a pattern to the")
print("  reference leg rather than the vendor leg, or to any convention.")
# --- END U6_STUDY_PROGRAM ---
```

### 4.3 Independent reproduction

The review reproduced all 14 interval rows — sample counts, reference-price ranges, difference
spreads, both feasibility verdicts and the stated factor windows — and the seven event-step
comparisons, with
`python -X utf8 -B "claude methods/_m2_codex_review/review_u6_retained_study_r1.py"`, exit 0,
reading only the two pinned JSON files with explicit decimal-token parsing and rational interval
intersection. It also reports that for E-1 and E-2 a construction holding the latent prior vendor
close at the reconstructed cent value admits a joint pairwise feasibility witness — which
**strengthens numerical compatibility and identifies no cause**.

### 4.4 Accurate account of the three scratch scripts

Revision 1's assignment specified in-memory computation with one output file. **The run departed
from that form**: the three passes were written as scripts in the session scratchpad and executed
from there, and revision 1's header nonetheless said nothing outside this file was created. **That
header statement was wrong as written**; the two scopes it conflated are now separated.

* **Repository scope.** `claude methods/M2B_U6_RETAINED_STUDY.md` is the only file created, by
  revision 1 or by this correction, and nothing else in the repository was modified. No script,
  output directory or dataset was added to the repository at any point.
* **Filesystem scope, outside the repository.** Three scripts were created in the session
  scratchpad directory
  `C:\Users\Administrator\AppData\Local\Temp\claude\D--codex-A---\a4a3be61-cd46-4bdf-9381-23d97fee303a\scratchpad\`:
  `u6_study.py` (8,634 B, `7d7a10c9aaf942799cc1c7f8c5f955763e976cf05719b836f14788754929e4a6`),
  `u6_study2.py` (7,270 B, `a49b8495ac3e2e15b4a9433efb75c0fcff5325cac51d674913d99a8239c33d7a`),
  `u6_study3.py` (4,791 B, `4f8ae0f47ae9d14d12852588df2a6b2f023c4399b2dcdbe4543037c064a26425`).
  They are **retained unaltered**: not deleted, not edited, not moved. Naming their hashes was not
  a substitute for delivering their content, which is why §4.2 now carries the program in full.

**This correction added no new scratch file.** The §4.2 program was executed by the §4.1 stdin
command, which reads the program out of this document.

---

## 5. Results

### 5.1 Retained reference metadata inventory

| Symbol | rows | `adjustment_mode` values | distinct sources | distinct `updated_at` |
|---|---|---|---|---|
| SH600011 | 538 | **`qfq`** only | 3 | 4 |
| BJ920000 | 501 | **`qfq`** only | 2 | 3 |
| SH000300 | 538 | **`none`** only | 1 | 4 |

Per source: SH600011 — `stock_zh_a_daily` 471, `stock_zh_a_hist` 37, `local.quotes.candle` 30, all
labelled `qfq`; BJ920000 — `local.quotes.candle` 500, `stock_zh_a_daily` 1, both `qfq`.

**Narrow observation:** the label is **internally uniform** per symbol — no mixed-basis row inside
either stock. That removes one failure mode (a visibly mixed label). It leaves A2 exactly where it
was: one uniform label spanning more than one upstream pipeline, none independently certified here.
**No inference is drawn about the label's reliability.**

### 5.2 Reconstruction check — two representations, named

`Vc/Rc` is an exact rational. The retained `ratio` field can be compared against it under two
different representations of that field, and the two give different residual maxima **because the
representations differ, not because reconstruction fails**:

| Symbol | compared dates | span | vs **exact JSON decimal token** | vs **IEEE-754 double** of the same token |
|---|---|---|---|---|
| sh600011 | 538 | 2024-06-21 … 2026-09-04 | `2.881355932203390e-16` | `2.220446049250313e-16` |
| bj920000 | 501 | 2024-08-13 … 2026-09-04 | `2.761743067345784e-16` | `2.220446049250313e-16` |

The decimal-token column matches the review's independently computed maxima
(`2.88135593220339e-16` SH, `2.761743067345784e-16` BJ). Revision 1 reported `2.302e-16` and
`2.253e-16`; those came from comparing against
`Fraction(float(token)).limit_denominator(10**15)`, i.e. a **third** representation — a rational
approximation of the double — which revision 1 did not name. That metric is superseded here rather
than equated with either column above.

All three are double-precision noise. This is an **internal-consistency check on two retained
fields**, not independent retrieval of a vendor close.

### 5.3 Interval feasibility — 14 rows, reproduced by the review

Intervals are `segment (source + updated_at) × identified ex-dates`. `dsprd` is the stored
difference spread in cents; H-add needs `≤ 2`. Feasible sets are **continuous** intervals.

**SH600011**

| Seg | Interval | n | `Rc` range | dsprd | H-add | H-mul |
|---|---|---|---|---|---|---|
| S0 `stock_zh_a_hist` / `…07-15T14:16:19` | 2024-06-21 … 2024-07-10 | 14 | 820–894 | 0 | **feasible** `C ∈ [86,88]c` | **infeasible** by 0.006325 |
| S0 | 2024-07-11 … 2024-08-12 *(from E-0)* | 23 | 669–830 | 0 | **feasible** `C ∈ [66,68]c` | **infeasible** by 0.016604 |
| S1 `stock_zh_a_daily` / `…09-03T17:21:19` | 2024-08-13 … 2025-07-09 | 218 | 569–725 | **15** | **infeasible** (exceeds 2c by 13c) | **feasible** `K ∈ [1.094440, 1.096000]` |
| S1 | 2025-07-10 … 2026-07-02 *(from E-1)* | 237 | 637–925 | **16** | **infeasible** (exceeds 2c by 14c) | **feasible** `K ∈ [1.054795, 1.056145]` |
| S1 | 2026-07-03 … 2026-07-23 *(from E-2)* | 15 | 670–743 | 0 | feasible `C ∈ [−1,1]c` | feasible `K ∈ [0.998655, 1.001347]` |
| S2 `stock_zh_a_daily` / `…09-04T15:09:56` | 2026-07-24 | 1 | 709 | 0 | feasible | feasible |
| S3 `local.quotes.candle` / `…09-04T18:06:09` | 2026-07-27 … 2026-09-04 | 30 | 660–729 | 0 | feasible | feasible |

**BJ920000**

| Seg | Interval | n | `Rc` range | dsprd | H-add | H-mul |
|---|---|---|---|---|---|---|
| S0 `local.quotes.candle` / `…09-03T19:39:41` | 2024-08-13 … 2024-09-27 | 32 | 581–668 | 0 | **feasible** `C ∈ [28,30]c` | **infeasible** by 0.003208 |
| S0 | 2024-09-30 … 2025-05-14 *(from E-5)* | 147 | **737–3577** | 0 | **feasible** `C ∈ [22,24]c` | **infeasible** by 0.023120 |
| S0 | 2025-05-15 … 2025-09-17 *(from E-6)* | 89 | 2005–2585 | 0 | **feasible** `C ∈ [14,16]c` | **infeasible** by 0.000790 |
| S0 | 2025-09-18 … 2026-05-22 *(from E-3)* | 159 | 1477–2672 | 0 | **feasible** `C ∈ [7,9]c` | **infeasible** by 0.001369 |
| S0 | 2026-05-25 … 2026-07-23 *(from E-4)* | 43 | 1122–1498 | 0 | feasible `C ∈ [−1,1]c` | feasible `K ∈ [0.999333, 1.000668]` |
| S1 `stock_zh_a_daily` / `…09-04T15:02:08` | 2026-07-24 | 1 | 1418 | 0 | feasible | feasible |
| S2 `local.quotes.candle` / `…09-04T18:06:31` | 2026-07-27 … 2026-09-04 | 30 | 1280–1547 | 0 | feasible | feasible |

**In every interval whose stored differences are not all zero, exactly one of the two tested
relations is feasible** — and not the same one everywhere. BJ920000's second interval is the most
strongly separated single case: the stored difference is exactly constant across a 4.85× reference
price range (737 → 3577 cents), which no constant ratio accommodates under R1, infeasible by
0.0231. Each `C` set has continuous width 2 cents; each 5-cent-looking bracket like `[86,88]`
contains three integer-cent grid points and a continuum between them.

### 5.4 Within-sample algebraic consistency

For each interval where one relation is feasible and the other is not, the feasible relation's
constant — **estimated from the same observations** — reproduces the magnitude by which the other
misses. This is an **algebraic consistency check on one dataset, not an independent prediction and
not a validation**:

| Interval | Rejected | Observed | From the surviving constant (same data) |
|---|---|---|---|
| SH S1 2024-08-13 … 2025-07-09 | H-add | d spread **15c** | `(K−1)(Rc_max−Rc_min)` at `K=1.095220` → **14.9c** |
| SH S1 2025-07-10 … 2026-07-02 | H-add | d spread **16c** | `(K−1)(Rc_max−Rc_min)` at `K=1.055470` → **16.0c** |
| SH S0 2024-06-21 … 2024-07-10 | H-mul | ratio 1.097315–1.106098 | constant `C=87c` → 1.097315–1.106098 |
| SH S0 2024-07-11 … 2024-08-12 | H-mul | ratio 1.080723–1.100149 | constant `C=67c` → 1.080723–1.100149 |
| BJ S0 2024-08-13 … 2024-09-27 | H-mul | ratio 1.043413–1.049914 | constant `C=29c` → 1.043413–1.049914 |
| BJ S0 2024-09-30 … 2025-05-14 | H-mul | ratio 1.006430–1.031208 | constant `C=23c` → 1.006430–1.031208 |
| BJ S0 2025-05-15 … 2025-09-17 | H-mul | ratio 1.005803–1.007481 | constant `C=15c` → 1.005803–1.007481 |
| BJ S0 2025-09-18 … 2026-05-22 | H-mul | ratio 1.002994–1.005416 | constant `C=8c` → 1.002994–1.005416 |

The rejections are therefore internally coherent rather than marginal. That coherence is a
property of the arithmetic on this one dataset; it identifies no mechanism.

### 5.5 The disclosed amounts against the surviving relation

For each identified ex-date inside one segment, the feasible constants on both sides give a
feasible **step**. Additive side: `C_before − C_after` in cents. Multiplicative side:
`K_before/K_after`, compared with A3+A4's `P/(P − D)` using the **reconstructed** prior close `P`.

| Event | ex-date | Disclosed | Surviving relation | Feasible step | Disclosed amount excluded? |
|---|---|---|---|---|---|
| E-0 (contextual, pre-interval) | 2024-07-11 | 0.20 | H-add | `C` step `[18,22]c` | **not excluded** (20c inside) |
| E-1 | 2025-07-10 | 0.27 | H-mul | `K` ratio `[1.036260, 1.039065]` | **not excluded** — A3+A4 give `7.44/(7.44−0.27) = 1.037657` |
| E-2 | 2026-07-03 | 0.40 | H-mul | `K` ratio `[1.053376, 1.057567]` | **not excluded** — A3+A4 give `7.61/(7.61−0.40) = 1.055479` |
| E-5 | 2024-09-30 | 0.06 | H-add | `C` step `[4,8]c` | **not excluded** (6c inside) |
| E-6 | 2025-05-15 | 0.08 | H-add | `C` step `[6,10]c` | **not excluded** (8c inside) |
| E-3 | 2025-09-18 | 0.070 | H-add | `C` step `[5,9]c` | **not excluded** (7c inside) |
| E-4 | 2026-05-25 | 0.08 | H-add | `C` step `[6,10]c` | **not excluded** (8c inside) |

**Seven for seven not excluded — and the windows are wide and continuous.** Each `C`-step window
has **continuous width 4 cents** and contains five integer-cent grid points, because each side's
constant is itself pinned only to ±1 cent under R1. **"Not excluded" is the whole content of these
rows**: a disclosed amount lying inside a feasible set is compatible with the tested relation, and
compatibility is not confirmation, identification or a causal role.

The observed stored-difference step **exactly** equalled the disclosed amount at **E-0, E-5, E-6,
E-3, E-4 and E-2**, and differed by one cent at **E-1** — preserving G1's count of six identified
in-interval comparisons with five exact matches (E-2, E-3, E-4, E-5, E-6) and one discrepancy, plus
contextual E-0. **No evidentiary ranking is assigned among these seven, and no cause is asserted
for any of them**, including E-2, whose exact step sits on a segment where H-add is infeasible and
is recorded as an observation with no explanation offered. E-2 is also the transition into an
observed zero-difference tail, as the assessment records.

### 5.6 E-1 — what is observed, and what is only compatible

Preserved unchanged and **not** reinterpreted: the **observed stored difference step at E-1 is 28
cents against a disclosed 27**. That is a real comparison between two retained fields and a
disclosed figure. Reporting it asserts no constant-difference model over the segment, and the
segment-wide infeasibility of H-add does **not** make the comparison erroneous, nor explain why it
came out at 28.

The exact retained tokens around it, with the reconstruction alongside:

| Date | retained close | retained difference | retained ratio | `Rc` | `Vc` (recon) | `d` |
|---|---|---|---|---|---|---|
| 2025-07-08 | `6.87` | `0.65` | `1.0946142649199417` | 687 | 752 | 65c |
| 2025-07-09 | `6.79` | `0.65` | `1.0957290132547866` | 679 | 744 | 65c |
| **2025-07-10** | `6.74` | `0.37` | `1.0548961424332344` | 674 | 711 | **37c** |
| 2025-07-11 | `6.65` | `0.37` | `1.0556390977443608` | 665 | 702 | 37c |
| 2025-07-14 | `6.76` | `0.38` | `1.0562130177514792` | 676 | 714 | 38c |

Two statements, each conditional, and neither an explanation:

* **Multiplicative reading.** On this segment H-mul is the feasible relation, and under A3+A4 the
  disclosed 0.27 lies inside the feasible `K_before/K_after` set (§5.5). So the disclosed amount is
  **not excluded** by that relation and rounding envelope. **This does not show that the
  multiplicative relation generated the observations, does not identify why the observed step is
  28, and leaves E-1's causal role unestablished.**
* **Additive reading, on its own premise.** Under **A5** — a latent difference step of exactly 27
  cents — plus R1, each side's `d_t` is pinned only to ±1 cent, so observed steps of **25–29
  cents** are permitted and 28 is among them. **Permitting the observation neither establishes A5
  nor rescues the segment's globally infeasible H-add intervals.**

**Revision 1 called the discrepancy "an artefact" of an additive reading. That verdict is
withdrawn.** Feasibility of one candidate under stated premises is not proof that the candidate
generated the data. **E-1 remains unresolved as a matter of established fact.**

### 5.7 Descriptive stratification by retained source and fetch metadata

| Reference source | `updated_at` | Symbol | intervals with non-zero d | Feasible relation |
|---|---|---|---|---|
| `akshare.stock_zh_a_hist` | `2026-07-15T14:16:19` | SH600011 | 2 | H-add (H-mul infeasible) |
| `tonghuasun.local.quotes.candle` | `2026-09-03T19:39:41` | BJ920000 | 4 | H-add (H-mul infeasible) |
| `akshare.stock_zh_a_daily` | `2026-09-03T17:21:19` | SH600011 | 2 | H-mul (H-add infeasible) |
| all remaining intervals | — | both | 0 (all-zero d) | both feasible — not discriminating |

**What the SH600011 pair does show.** The same instrument yields an additive-feasible relation on
its `stock_zh_a_hist` segment and a multiplicative-feasible relation on its `stock_zh_a_daily`
segment. That is inconsistent with **one simplistic reading only** — that instrument identity alone
fixes a single relation for all of that instrument's dates.

**What it does not show.** It does **not** exclude an instrument/time interaction, a change on the
vendor side, or any other explanation. The two segments are **disjoint in time** and differ
together in source, `updated_at`, calendar span (37 versus 470 sessions), event set, exact price
path and the vendor-side path. Revision 1 said the "instrument confound is broken"; **that is
withdrawn** — no confound is generally broken here. Revision 1 also argued that comparable
price-range ratios (×1.24 versus ×1.27) ruled out a narrower-price-range explanation; **that is
withdrawn too** — a similar range ratio controls for none of effect size, precision, sample size or
price path.

**No side is assigned.** These are pairwise findings about a *relation between two series*. They
cannot be attributed to the reference leg while excluding the vendor leg, and they do **not**
establish that the uniform `qfq` label is unreliable or that differing conventions caused anything.
Revision 1's framing — that this bears on statement 3 and gives "less confidence in the recorded
label" — is **withdrawn**. The reference basis remains **unverified**, which was already sufficient
to withhold certification and needs no support from this section.

### 5.8 The shared zero-difference tails

Both stocks' `local.quotes.candle` tails (2026-07-27 … 2026-09-04, 30 sessions each, `updated_at`
`18:06:09` and `18:06:31`), the two single 2026-07-24 rows, and the post-E-4 / post-E-2 zero runs
all have **all-zero stored differences**, and **both relations are feasible in every one of them**
(`C ∈ [−1,1]c`, `K ≈ 1 ± 0.0014`). These are matched same-source, same-calendar spans and they
**discriminate nothing**, because a zero difference is compatible with `C = 0` and `K = 1` alike.

---

## 6. Limitations, and what is not established

1. **Only two relations were tested.** Feasibility of exactly one of two is **not identification**.
   Other relations — piecewise factors, other rounding rules, mixed constructions — were not tested
   and could also be feasible. No relation family is claimed exhaustive.
2. **No supplier algorithm, and no causality.** Nothing here says how Sina or any reference
   pipeline computes anything. Date and magnitude agreements remain coincidences of dates and
   magnitudes.
3. **Neither leg is identified as unadjusted**, and no side of any comparison is identified as
   wrong. Both relations constrain the *pair*; A4 supplies orientation by premise in §5.5 only.
4. **The reference basis is still not certified (A2).** §5.1 shows the label is internally uniform;
   §5.7 draws no conclusion about its reliability. The assessment's decisive reason for withholding
   certification is untouched and unsupported by this study either way.
5. **No basis candidate is disproved.** H-add failing on SH's `stock_zh_a_daily` segment rejects
   **one relation on one segment under one envelope**. It disproves no price-basis candidate.
6. **The event set is not established as complete (G-e, A1).** Intervals were cut at identified
   ex-dates only. **No detection property is claimed**: revision 1 said an unidentified event
   "would appear as an infeasibility", which is **withdrawn** — an event could preserve a relation
   or stay inside the rounding bounds and leave no trace in these tests. G-e remains unestablished.
7. **No anchor is demonstrated.** Zero-difference tails are observed; nothing establishes where or
   how either series is anchored.
8. **G-g unchanged.** The legal effective date of `832000 → 920000` remains unknown; identity and
   exchange continuity remain as G1 established them. This study addresses neither.
9. **Missing early overlap unchanged (G-5).** No reference row before 2024-06-21 (SH600011) /
   2024-08-13 (BJ920000). Every interval is inside one extract with one set of fetch times; nothing
   here is out-of-sample, and §5.4 is explicitly within-sample.
10. **Vendor closes are reconstructed** (§2, §5.2), never independently retrieved. Full-precision
    pre-rounding values are **not recoverable** from the permitted JSON — a reported bound, not a
    solved problem, and the reason these are feasibility tests rather than fits.
11. **The envelope's scope (R1).** Verdicts hold for a closed half-cent **nearest-rounding**
    envelope only. Feasibility there is **existential** and implies no deterministic tie rule.
    Infeasibility is robust to **subsets** of the envelope; it says nothing about wider envelopes,
    arbitrary truncation, or larger error bounds.
12. **One long segment per source.** §5.7 rests on three source groups with two, four and two
    non-zero-difference intervals respectively, and its segments are disjoint in time.

---

## 7. What this changes for U-6 — and what it does not

**Changed, narrowly.** The assessment's §3.1 caution that "exact non-constancy refutes nothing" is
now **quantified**: it is exactly right for a stored ratio under H-mul, and it does **not** rescue
H-add on SH's `stock_zh_a_daily` segment, where the miss is 13–14 cents against a derived 2-cent
bound. On E-1 (Q-2), the study adds two **conditional compatibility** statements (§5.6) — the
disclosed 0.27 is not excluded by the feasible relation under A3+A4, and an observed 28-cent step is
permitted under A5 plus R1. **Q-2 is not closed:** E-1's cause is unestablished and the 28-versus-27
comparison stands as observed.

**Not changed.** Q-3 — the reference basis is recorded, not independently certified — remains the
decisive reason to withhold certification, and this study neither strengthens nor weakens it.
Q-4 (G-e), Q-5 (G-g), Q-6 (early coverage) and Q-7 are untouched. **U-6 stays deferred; no
sufficiency rule is proposed, and none of these results is offered as one.** `vendor_basis` stays
`unverified`; the outcome remains **fail-closed, not a disproof**.

---

## 8. Preservation

**Created in the repository:** this file only. **Modified:** nothing. See §4.4 for the accurate
account of the three pre-existing scratch scripts outside the repository, which are retained
unaltered; this correction created no new scratch file.

Verified after the run: the accepted G1 delivery is **46/46 byte-identical** to the frozen
`_m2_codex_review/g1_review_20260909_r3_doc1/reviewed_delivery` with no file added or removed; the
five accepted G3 r2 pins match; `results.json` `538adc5c…` and `reference_extract.json`
`ea021004…` are unchanged after reading; the basis module, its tests and both `basis_eval_*`
outputs match; the five smoke producers and `closure_r2abc_v2.py` match; the P1 proposal
`71e0dc52…`, goal `f8b699e5…`, request `c39726d0…`, the U-6 readiness assessment `de130cf0…`, all
G1/G3/U-6 acceptance and review documents including this study's review `1dbbe955…`, the dispatch
`ccbac34d…`, all reviewer snapshots and the coordination state are unchanged. No test, replay,
adapter run, decoding run, network call, SQLite open, capture or service action occurred. Git was
not staged, committed or pushed.

---

## 9. Candidate next offline analysis under the same authorization

**Not executed here**, and stated without a promised payoff.

**Candidate — describe field and unit consistency across the same retained boundaries.** The
retained extract holds `volume`, `amount` and `volume_unit` per row for all three symbols, and
`results.json` holds the index series where both legs are basis `none` and agree exactly. A bounded
study could **describe** whether those non-price fields show discontinuities or unit inconsistencies
at the same `source`+`updated_at` boundaries as the price relations, and flag candidate anomalies
for later attention.

**What such a study could not do.** A change in `volume` or `amount` at a source boundary would
**not** establish a pipeline cause rather than real market variation, and the **absence** of a
change would **not** isolate price adjustment as the affected quantity. Alternative explanations —
genuine market variation, differing unit conventions, coincident calendar effects — would remain
open. Its value would be descriptive: locating inconsistencies worth understanding, not
attributing them.

**Not worth doing.** Further variations on §5.3's price-relation tests over these same intervals:
the feasibility verdicts are already exact under R1, the infeasibility verdicts are robust to
subsets of it, and more relation families fitted to the same 470-session windows would add
candidates without adding evidence. And no retained-JSON study can substitute for independent
reference-basis evidence.

**Stop: `proposed for review`.** This study is not M2 completion, does not certify a vendor basis,
and authorizes nothing.
