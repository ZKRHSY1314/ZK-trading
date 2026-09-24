# U-6 retained-artifact study — additive and multiplicative relations, E-1, source stratification

> **Status `proposed for review`.** Task `U6-RETAINED-STUDY-20260909`, executing
> `_m2_codex_review/u6_retained_study_dispatch_20260909.txt` (M-1 + M-2 with M-3 source
> stratification) under the user's continuous offline-analysis authorization.
>
> **Retained JSON only.** No network, no source query, no new extract, no SQLite open, no
> capture, no adapter replay, no fresh decoding run, no service, no token or account access. No
> module that initialises a runtime service or data provider was imported. Nothing outside this
> one file was created or modified.
>
> **This adopts nothing.** No vendor-basis sufficiency rule, no threshold, no tolerance, no
> calibration, no label, gate or eligibility change, no policy adoption. **P1 open, U-6 deferred,
> every eligibility result false, source capability FAIL (including the retained EV6
> disagreements), both capture authorizations consumed.** Not M2 completion.
>
> **What it is.** Two conditional relations are tested for **feasibility** inside identified
> inter-event intervals, under one rounding model stated before any comparison. Feasibility of a
> relation is **not** identification of a supplier algorithm, a cause, a reference basis, or a
> price basis for either leg.

---

## 1. Inputs, with hashes verified before use

Both inputs were hash-checked against the pins recorded in the **accepted** G3 provenance
(`_m2_smoke/g3_ratio_analysis_20260909_r2/PROVENANCE.json`, `1a262d74…`) at the start of the run;
both matched.

| Input | SHA-256 | Verified |
|---|---|---|
| `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/results.json` | `538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd` | **match** |
| `claude methods/_m2_smoke/revision_20260908T082833Z_r2abc_v2/reference/reference_extract.json` | `ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2` | **match** |

The extract's own `content_sha256` reads `3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9`,
agreeing with the G3 provenance field of the same name; `row_counts` reads
`{SH600011: 538, SH000300: 538, BJ920000: 501}`.

**Disclosed cash amounts** are taken from the accepted G1 delivery — `REPORT.md` `77941f8c…` §2,
each backed by a retained Tier A notice: `2024-068` `6f22f7be…` (BJ 0.06, ex 2024-09-30),
`2025-047` `aba4cb40…` (BJ 0.08, ex 2025-05-15), `2025-103` `157dc615…` (BJ 0.070, ex 2025-09-18),
`2026-037` `c8bcf19f…` (BJ 0.08, ex 2026-05-25), `2025-036` `439ceb65…` (SH 0.27, ex 2025-07-10),
`2026-036` `269ed39f…` (SH 0.40, ex 2026-07-03), and — contextual, outside the task interval —
`2024-034` `ffe858d9…` (SH 0.20, ex 2024-07-11).

**No adapter, decoder or raw vendor body was read.** `results.json`'s `vendor` block carries only
metadata (`branch: O`, `js_variable`, row count, first/last date); it holds no vendor closes.

---

## 2. Assumptions, stated before any comparison

**R1 — rounding model.** Every stored price is a 2-decimal value, and the pre-rounding quantity it
represents lies within **half a cent** of it: writing `Rc` and `Vc` for the stored reference and
vendor values in integer cents, `100·R* ∈ [Rc − 0.5, Rc + 0.5]` and `100·V* ∈ [Vc − 0.5, Vc + 0.5]`.
Closed intervals are used, which is the choice that **favours feasibility**; no rounding *rule*
(half-up, half-even, truncation) is assumed, and none is tested.

**H-add(j) and H-mul(j) — the two conditional relations,** stated directly on pre-rounding
quantities as `M2B_U6_READINESS_ASSESSMENT.md` §3.1 requires, with no intermediate claim about how
either quantity is built:

* **H-add(j):** `V* − R* = C_j`, a constant, throughout interval `j`.
* **H-mul(j):** `V* / R* = K_j`, a constant, throughout interval `j`.

**A1 — interval boundaries.** Intervals are cut at the **identified** Tier A ex-dates. The event
set is **not established as complete** (G-e), so a relation found feasible inside an interval is
feasible *given these boundaries*.

**A2 — reference basis.** The extract *records* `adjustment_mode` per row. It is **not
independently certified** here. Nothing below establishes it.

**A3 — mapping assumption, used only in §5.5, and not established.** A cash amount `D` at an
ex-date scales a multiplicative reference factor by `(P − D)/P`, where `P` is the prior session's
**unadjusted** close. Under H-mul this predicts `K_before / K_after = P/(P − D)`.

**A4 — orientation assumption, used only in §5.5, and not established.** A3's `P` is taken to be
the **vendor** leg. Both relations constrain the *pair* of series; **neither identifies which leg
is unadjusted**, and A4 supplies that orientation by assumption rather than by evidence.

**Retained versus reconstructed.** Reference closes are **retained** fields of the extract.
Ratios and differences are **retained** fields of `results.json`. Vendor closes are **not
retained anywhere readable under this authorization**; they are **reconstructed** as
`Vc = Rc + round(100 × retained difference)` and are labelled `(recon)` throughout. **A
reconstructed vendor close is never presented as an independently retained raw close.**

---

## 3. The two feasibility tests, derived from R1 alone

No tolerance is chosen, fitted or tuned. Each test is the exact condition under which a constant
exists that is compatible with every stored pair in the interval under R1.

**H-add.** Let `x_t = 100·R*_t`, so `Rc_t = round(x_t)` gives `x_t ∈ [Rc_t − 0.5, Rc_t + 0.5]`, and
`Vc_t = round(x_t + c)` for `c = 100·C_j`. For a single date, some admissible `x_t` exists iff
`c ∈ [d_t − 1, d_t + 1]` where `d_t = Vc_t − Rc_t`. Intersecting over the interval:

> **H-add(j) is feasible ⟺ `max_t d_t − min_t d_t ≤ 2` cents.**

**H-mul.** `Vc_t ∈ [K(Rc_t − 0.5) − 0.5, K(Rc_t + 0.5) + 0.5]` gives, per date,
`K ∈ [(Vc_t − 0.5)/(Rc_t + 0.5), (Vc_t + 0.5)/(Rc_t − 0.5)]`. Intersecting over the interval:

> **H-mul(j) is feasible ⟺ `max_t (2Vc_t − 1)/(2Rc_t + 1) ≤ min_t (2Vc_t + 1)/(2Rc_t − 1)`.**

Both were evaluated in exact rational arithmetic (`fractions.Fraction`), so no floating-point
comparison decides any feasibility verdict.

**Note the asymmetry these tests exploit.** Within an interval the reference price *moves*. A
constant difference and a constant ratio therefore make different predictions, and the wider the
price range the more sharply they separate. This is why the tests discriminate at all — and why
they discriminate nothing on an interval whose differences are all zero.

---

## 4. Exact code, as executed

Three passes were run from the session scratchpad with the project virtual environment; **no
script was added to the repository and no output directory was created**, per the dispatch's
compute-in-memory instruction. The code is reproduced verbatim so the review can re-run it.

```
"D:/codex-A股交易/backend/.venv/Scripts/python.exe" -B -X utf8 u6_study.py
"D:/codex-A股交易/backend/.venv/Scripts/python.exe" -B -X utf8 u6_study2.py
"D:/codex-A股交易/backend/.venv/Scripts/python.exe" -B -X utf8 u6_study3.py
```

Scratchpad copies, for reference only: `u6_study.py` 8,634 B
`7d7a10c9aaf942799cc1c7f8c5f955763e976cf05719b836f14788754929e4a6`; `u6_study2.py` 7,270 B
`a49b8495ac3e2e15b4a9433efb75c0fcff5325cac51d674913d99a8239c33d7a`; `u6_study3.py` 4,791 B
`4f8ae0f47ae9d14d12852588df2a6b2f023c4399b2dcdbe4543037c064a26425`.

### 4.1 Pass 1 — hashes, metadata inventory, reconstruction, interval feasibility

```python
import hashlib, json, os
from fractions import Fraction as F

ROOT = r"D:\codex-A股交易\claude methods\_m2_smoke"
RESULTS = os.path.join(ROOT, "g3_ratio_analysis_20260909_r2", "results.json")
REFEXT  = os.path.join(ROOT, "revision_20260908T082833Z_r2abc_v2", "reference",
                       "reference_extract.json")
PINS = {RESULTS: "538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd",
        REFEXT:  "ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2"}

# Identified Tier A ex-dates (G1 accepted). Not an exhaustive event set (G-e).
EXDATES = {"sh600011": {"2024-07-11": ("E-0", F(20,100)), "2025-07-10": ("E-1", F(27,100)),
                        "2026-07-03": ("E-2", F(40,100))},
           "bj920000": {"2024-09-30": ("E-5", F(6,100)),  "2025-05-15": ("E-6", F(8,100)),
                        "2025-09-18": ("E-3", F(7,100)),  "2026-05-25": ("E-4", F(8,100))}}
REFKEY = {"sh600011": "SH600011", "bj920000": "BJ920000", "sh000300": "SH000300"}

def sha256(path): return hashlib.sha256(open(path, "rb").read()).hexdigest()
def cents(x):     return int(round(x * 100))   # exact cents of a stored 2-dp value

for p, pin in PINS.items():
    got = sha256(p); print(os.path.basename(p), got, "match=", got == pin)

res = json.load(open(RESULTS, encoding="utf-8"))
ref = json.load(open(REFEXT,  encoding="utf-8"))

# reference metadata inventory
for sym in ("SH600011", "BJ920000", "SH000300"):
    rows = ref["rows"][sym]
    print(sym, len(rows), sorted({r["adjustment_mode"] for r in rows}),
          len({r["source"] for r in rows}), len({r["updated_at"] for r in rows}))
    for s in sorted({r["source"] for r in rows}):
        sub = [r for r in rows if r["source"] == s]
        print("   ", s, len(sub), sorted({r["adjustment_mode"] for r in sub}))

for symkey in ("sh600011", "bj920000"):
    comp  = res["results"][symkey]["comparison"]
    ratio = dict(comp["ratio"]["series"]); diff = dict(comp["difference"]["series"])
    rrows = {r["trade_date"]: r for r in ref["rows"][REFKEY[symkey]]}

    rec, maxdev = {}, 0.0
    for d, dv in diff.items():                      # Vc is RECONSTRUCTED, not retained
        rr = rrows[d]; Rc = cents(rr["close"]); Dc = cents(dv); Vc = Rc + Dc
        rec[d] = (Rc, Vc, Dc, rr["source"], rr["updated_at"])
        if Rc: maxdev = max(maxdev, abs(F(Vc, Rc) - F(ratio[d]).limit_denominator(10**15)))
    dates = sorted(rec)
    print(symkey, len(dates), dates[0], dates[-1], "max|Vc/Rc-ratio|=%.3e" % float(maxdev))

    segs, cur = [], None                            # contiguous source AND updated_at
    for d in dates:
        key = (rec[d][3], rec[d][4])
        if cur is None or cur[0] != key: cur = (key, [d]); segs.append(cur)
        else:                                        cur[1].append(d)

    for si, ((src, up), sdates) in enumerate(segs):
        exs    = sorted(d for d in EXDATES[symkey] if sdates[0] <= d <= sdates[-1])
        bounds = [sdates[0]] + exs
        for bi, start in enumerate(bounds):
            end = bounds[bi+1] if bi+1 < len(bounds) else None
            iv  = [d for d in sdates if d >= start and (end is None or d < end)]
            if not iv: continue
            ds  = [rec[d][2] for d in iv]; Rcs = [rec[d][0] for d in iv]
            add_lo, add_hi = max(ds) - 1, min(ds) + 1          # H-add feasible C, cents
            klo = max(F(2*rec[d][1] - 1, 2*rec[d][0] + 1) for d in iv)   # H-mul feasible K
            khi = min(F(2*rec[d][1] + 1, 2*rec[d][0] - 1) for d in iv)
            print("S%d" % si, iv[0], iv[-1], len(iv), min(Rcs), max(Rcs),
                  max(ds) - min(ds),
                  ("[%d,%d]" % (add_lo, add_hi)) if add_lo <= add_hi else "INFEASIBLE",
                  ("[%.6f,%.6f]" % (klo, khi)) if klo <= khi else "INFEASIBLE")
        print("   segment S%d" % si, src, up, len(sdates))

    for d in sorted(EXDATES[symkey]):                # observed cent step at each ex-date
        if d not in rec: continue
        i = dates.index(d)
        if i == 0: continue
        p    = dates[i-1]
        same = (rec[p][3], rec[p][4]) == (rec[d][3], rec[d][4])
        step = rec[p][2] - rec[d][2]; disc = int(EXDATES[symkey][d][1] * 100)
        print(d, EXDATES[symkey][d][0], p, rec[p][2], rec[d][2], step, disc,
              step - disc, "same_segment=", same)
```

### 4.2 Pass 2 — infeasibility margins, disclosed amounts, source stratification

```python
# same loaders as pass 1; intervals() reproduces the segment x ex-date partition above
for iv in intervals(rec, dates, sym):
    ds  = [rec[d][2] for d in iv["dates"]]
    klo = max(F(2*rec[d][1] - 1, 2*rec[d][0] + 1) for d in iv["dates"])
    khi = min(F(2*rec[d][1] + 1, 2*rec[d][0] - 1) for d in iv["dates"])
    spread = max(ds) - min(ds)
    print("H-add", spread, "FEASIBLE" if spread <= 2 else
          "INFEASIBLE exceeds bound by %dc" % (spread - 2))
    print("H-mul", ("FEASIBLE [%.6f,%.6f]" % (klo, khi)) if klo <= khi else
          ("INFEASIBLE by %.6f" % float(klo - khi)))

# disclosed amount against the surviving relation
P       = F(rec[prev][1], 100)          # RECONSTRUCTED prior-session vendor close
implied = P / (P - F(disc, 100))        # A3 + A4
lo, hi  = ka[0] / kb[1], ka[1] / kb[0]  # feasible K_before / K_after
print("K-ratio in [%.6f,%.6f]; A3-implied %.6f; inside=%s"
      % (lo, hi, implied, lo <= implied <= hi))
lo, hi  = ca[0] - cb[1], ca[1] - cb[0]  # feasible C_before - C_after, cents
print("C-step in [%dc,%dc]; disclosed %dc; inside=%s" % (lo, hi, disc, lo <= disc <= hi))
```

### 4.3 Pass 3 — reciprocal consistency and the SH source comparison

```python
if mul_ok and not add_ok:               # does H-mul predict how far H-add misses?
    kmid = (klo + khi) / 2
    print("observed d spread %dc ; predicted (K-1)*(Rc_max-Rc_min) = %.1fc"
          % (max(ds) - min(ds), float((kmid - 1) * (max(Rc) - min(Rc)))))
elif add_ok and not mul_ok:             # does H-add predict the observed ratio range?
    cmid = (max(ds) + min(ds)) / 2
    print("observed ratio %.6f..%.6f ; predicted by constant C=%.0fc -> %.6f..%.6f"
          % (min(ratio[d] for d in iv), max(ratio[d] for d in iv), cmid,
             1 + cmid / max(Rc), 1 + cmid / min(Rc)))
```

---

## 5. Results

### 5.1 Reference metadata inventory (retained fields)

| Symbol | rows | `adjustment_mode` values | distinct sources | distinct `updated_at` |
|---|---|---|---|---|
| SH600011 | 538 | **`qfq`** only | 3 | 4 |
| BJ920000 | 501 | **`qfq`** only | 2 | 3 |
| SH000300 | 538 | **`none`** only | 1 | 4 |

Per source: SH600011 — `stock_zh_a_daily` 471, `stock_zh_a_hist` 37, `local.quotes.candle` 30, all
labelled `qfq`; BJ920000 — `local.quotes.candle` 500, `stock_zh_a_daily` 1, both `qfq`.

**New, and narrow:** the label is **internally uniform** per symbol — there is no mixed-basis row
inside either stock. That removes one failure mode (a visibly mixed label) and leaves §2's A2
exactly where it was: **one uniform label spanning two or three different upstream pipelines, none
of them independently certified here.**

### 5.2 Reconstruction cross-check

| Symbol | compared dates | span | `max │Vc/Rc − retained ratio│` |
|---|---|---|---|
| sh600011 | 538 | 2024-06-21 … 2026-09-04 | `2.302e-16` |
| bj920000 | 501 | 2024-08-13 … 2026-09-04 | `2.253e-16` |

The reconstruction agrees with the independently stored `ratio` field to double-precision noise.
That is an **internal-consistency check on two retained fields**, not independent retrieval of a
vendor close.

### 5.3 Interval feasibility — the main result

Intervals are `segment (source + updated_at) × identified ex-dates`. `dsprd` is the stored
difference spread in cents; H-add needs `≤ 2`.

**SH600011**

| Seg | Interval | n | `Rc` range | dsprd | H-add | H-mul |
|---|---|---|---|---|---|---|
| S0 `stock_zh_a_hist` / `…07-15T14:16:19` | 2024-06-21 … 2024-07-10 | 14 | 820–894 | 0 | **feasible** `C ∈ [86,88]c` | **infeasible** by 0.006325 |
| S0 | 2024-07-11 … 2024-08-12 *(from E-0)* | 23 | 669–830 | 0 | **feasible** `C ∈ [66,68]c` | **infeasible** by 0.016604 |
| S1 `stock_zh_a_daily` / `…09-03T17:21:19` | 2024-08-13 … 2025-07-09 | 218 | 569–725 | **15** | **infeasible** (exceeds by 13c) | **feasible** `K ∈ [1.094440, 1.096000]` |
| S1 | 2025-07-10 … 2026-07-02 *(from E-1)* | 237 | 637–925 | **16** | **infeasible** (exceeds by 14c) | **feasible** `K ∈ [1.054795, 1.056145]` |
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

**In every interval whose differences are not all zero, exactly one of the two tested relations is
feasible** — and the survivor is not the same one everywhere. BJ920000's second interval is the
most decisive single observation in the set: the stored difference is **exactly constant across a
4.85× reference price range** (737 → 3577 cents), which no constant ratio can accommodate under
R1, infeasible by 0.0231.

### 5.4 Reciprocal consistency — each survivor predicts how far the other misses

Derived from the surviving interval constant, not fitted:

| Interval | Rejected relation | Observed | Predicted by the survivor |
|---|---|---|---|
| SH S1 2024-08-13 … 2025-07-09 | H-add | d spread **15c** | `(K−1)(Rc_max−Rc_min)` at `K=1.095220` → **14.9c** |
| SH S1 2025-07-10 … 2026-07-02 | H-add | d spread **16c** | `(K−1)(Rc_max−Rc_min)` at `K=1.055470` → **16.0c** |
| SH S0 2024-06-21 … 2024-07-10 | H-mul | ratio 1.097315–1.106098 | constant `C=87c` → 1.097315–1.106098 |
| SH S0 2024-07-11 … 2024-08-12 | H-mul | ratio 1.080723–1.100149 | constant `C=67c` → 1.080723–1.100149 |
| BJ S0 2024-08-13 … 2024-09-27 | H-mul | ratio 1.043413–1.049914 | constant `C=29c` → 1.043413–1.049914 |
| BJ S0 2024-09-30 … 2025-05-14 | H-mul | ratio 1.006430–1.031208 | constant `C=23c` → 1.006430–1.031208 |
| BJ S0 2025-05-15 … 2025-09-17 | H-mul | ratio 1.005803–1.007481 | constant `C=15c` → 1.005803–1.007481 |
| BJ S0 2025-09-18 … 2026-05-22 | H-mul | ratio 1.002994–1.005416 | constant `C=8c` → 1.002994–1.005416 |

The rejections are therefore **quantitatively coherent**, not marginal: on each interval the
"failing" series varies by very nearly exactly the amount the surviving relation implies. This is
arithmetic on the retained values; it identifies no mechanism.

### 5.5 The disclosed amounts against the surviving relation

For each identified ex-date inside one segment, the feasible interval constants on both sides give
a feasible **step**. Additive side: `C_before − C_after ∈ [·,·]` cents. Multiplicative side:
`K_before/K_after ∈ [·,·]`, compared with A3+A4's `P/(P − D)` using the **reconstructed** prior
close `P`.

| Event | ex-date | Disclosed | Surviving relation | Feasible step | Disclosed amount inside? |
|---|---|---|---|---|---|
| E-0 (contextual, pre-interval) | 2024-07-11 | 0.20 | H-add | `C` step `[18,22]c` | **yes** (20c) |
| E-1 | 2025-07-10 | 0.27 | H-mul | `K` ratio `[1.036260, 1.039065]` | **yes** — A3 implies `7.44/(7.44−0.27) = 1.037657` |
| E-2 | 2026-07-03 | 0.40 | H-mul | `K` ratio `[1.053376, 1.057567]` | **yes** — A3 implies `7.61/(7.61−0.40) = 1.055479` |
| E-5 | 2024-09-30 | 0.06 | H-add | `C` step `[4,8]c` | **yes** (6c) |
| E-6 | 2025-05-15 | 0.08 | H-add | `C` step `[6,10]c` | **yes** (8c) |
| E-3 | 2025-09-18 | 0.070 | H-add | `C` step `[5,9]c` | **yes** (7c) |
| E-4 | 2026-05-25 | 0.08 | H-add | `C` step `[6,10]c` | **yes** (8c) |

**Seven for seven — and the windows are wide.** Each `C` step window is 5 cents wide because each
side's constant is itself pinned only to ±1 cent under R1. The wide feasibility window is the
weaker, more conservative statement, and it is the one these tests license.

G1's exact-step observations are unchanged and are the stronger statement where they apply. The
observed stored-difference step **exactly** equalled the disclosed amount at **E-0, E-5, E-6, E-3,
E-4 and E-2**, and differed by one cent at **E-1** — preserving G1's count of six identified
in-interval comparisons with five exact matches (E-2, E-3, E-4, E-5, E-6) and one discrepancy,
plus contextual E-0. Two cautions on that list. E-5, E-6, E-3, E-4 and E-0 sit on
additive-feasible segments, where an exact difference step is the natural reading. **E-2 does
not**: it sits on SH's multiplicative-feasible segment, where a constant difference step is not
what the feasible relation predicts, so its exactness is a numerical coincidence of the price
level at that date rather than support for the additive reading. E-2 is also the transition into
an observed zero-difference tail, as the assessment records.

### 5.6 E-1 — what the 0.28-versus-0.27 step is, and is not

Preserved unchanged: the **observed stored difference step at E-1 is 28 cents against a disclosed
27**, and G1's count of **six identified in-interval comparisons with five exact difference
matches** stands.

What this study adds is where that step comes from. The exact retained fields around it:

| Date | retained reference close | retained difference | retained ratio |
|---|---|---|---|
| 2025-07-08 | `6.87` | `0.65` | `1.0946142649199417` |
| 2025-07-09 | `6.79` | `0.65` | `1.0957290132547866` |
| **2025-07-10** | `6.74` | `0.37` | `1.0548961424332344` |
| 2025-07-11 | `6.65` | `0.37` | `1.0556390977443608` |
| 2025-07-14 | `6.76` | `0.38` | `1.0562130177514792` |

A 28-cent step is an **additive** reading of the pair — and **H-add is infeasible on this segment**
(§5.3, by 13 and 14 cents on the two intervals). On the relation that *is* feasible there, the
disclosed 0.27 sits inside the feasible `K` ratio (§5.5). Two consequences, both conditional:

* **Conditional on R1, A3 and A4, the E-1 "discrepancy" is an artefact of reading a
  multiplicative-feasible segment additively** — not a mismatch between the retained series and
  the disclosed amount.
* Separately, and independently of A3/A4: even *within* an additive reading, a true 27-cent
  amount admits an observed step of **25–29 cents** under R1 alone, because each side's `d_t` is
  pinned only to ±1 cent. The observed 28 is inside that range. So rounding alone already
  accommodates it.

**What this does not do.** It does not identify a cause, does not establish the reference's basis,
does not establish which leg is unadjusted, and does not make E-1 a settled fact about the vendor.
It relocates the discrepancy from "unexplained numerical mismatch" to "artefact of an infeasible
reading, under stated assumptions". **E-1 remains unresolved as a matter of established fact.**

### 5.7 Source stratification (M-3), and the one confound this breaks

| Reference source | `updated_at` | Symbol | intervals with non-zero d | Feasible relation |
|---|---|---|---|---|
| `akshare.stock_zh_a_hist` | `2026-07-15T14:16:19` | SH600011 | 2 | **H-add** (H-mul infeasible) |
| `tonghuasun.local.quotes.candle` | `2026-09-03T19:39:41` | BJ920000 | 4 | **H-add** (H-mul infeasible) |
| `akshare.stock_zh_a_daily` | `2026-09-03T17:21:19` | SH600011 | 2 | **H-mul** (H-add infeasible) |
| all remaining intervals | — | both | 0 (all-zero d) | both feasible — not discriminating |

**The instrument confound is broken for SH600011.** The same instrument yields an
additive-feasible relation under `stock_zh_a_hist` and a multiplicative-feasible relation under
`stock_zh_a_daily`. Since the instrument is held fixed across those two segments, **the instrument
alone cannot explain which relation is feasible.** The price ranges also overlap and are of
comparable width — `x1.24` on the additive-feasible `hist` interval versus `x1.27` on the
multiplicative-feasible `daily` interval — so a "narrower price range" explanation does not
account for it either.

**What remains confounded.** Source and `updated_at` move together, as do calendar span (37 versus
470 sessions) and the exact price path. So the observation is that **the feasible relation tracks
the reference `source`+`updated_at` identity rather than the instrument** — it does not isolate
which of those covarying attributes is responsible, and it says nothing about *why*.

**Direction of the finding, stated carefully.** This bears on statement 3 of the assessment
(reference-basis reliability), not statement 2 (vendor basis): two reference pipelines carrying the
**same** `qfq` label relate to the vendor series by **different** feasible relations. That is a
reason for less confidence in the recorded label, not more.

### 5.8 The shared zero-difference tails

Both stocks' `local.quotes.candle` tails (2026-07-27 … 2026-09-04, 30 sessions each,
`updated_at` `18:06:09` and `18:06:31`), the two single 2026-07-24 rows, and the post-E-4 / post-E-2
zero runs all have **all-zero stored differences**, and **both relations are feasible in every one
of them** (`C ∈ [−1,1]c`, `K ≈ 1 ± 0.0014`). They confirm the assessment's R2-B point
quantitatively: these are matched same-source, same-calendar spans, and they **discriminate
nothing**, because a zero difference is compatible with `C = 0` and with `K = 1` alike.

---

## 6. Limitations, and what is not established

1. **Only two relations were tested.** Feasibility of exactly one of two is **not identification**.
   Other relations — piecewise factors, different rounding rules, mixed constructions — were not
   tested and could also be feasible. No relation family is claimed exhaustive.
2. **No supplier algorithm, and no causality.** Nothing here says how Sina or any reference
   pipeline computes anything. Date and magnitude agreements remain coincidences of dates and
   magnitudes.
3. **Neither leg is identified as unadjusted.** Both relations constrain the *pair*. A4 supplies
   orientation by assumption in §5.5 only.
4. **The reference basis is still not certified (A2).** §5.1 shows the label is uniform per symbol;
   §5.7 gives a reason for *less* confidence that one uniform label means one convention. The
   assessment's decisive reason for withholding certification is untouched.
5. **No basis candidate is disproved.** H-add failing on SH's `stock_zh_a_daily` segment rejects
   **one relation on one segment under one rounding model**. It disproves no price-basis candidate,
   universally or otherwise.
6. **The event set is not established as complete (G-e, A1).** Intervals were cut at identified
   ex-dates only. An unidentified event inside an interval would appear as an infeasibility, and
   none of the additive-feasible intervals shows one — but that is a weak consistency observation,
   **not** evidence that the event set is complete, and not an exhaustive event set.
7. **No anchor is demonstrated.** Zero-difference tails are observed; nothing establishes where or
   how either series is anchored.
8. **G-g unchanged.** The legal effective date of `832000 → 920000` remains unknown; identity and
   exchange continuity remain as G1 established them. This study addresses neither.
9. **Missing early overlap unchanged (G-5).** No reference row before 2024-06-21 (SH600011) /
   2024-08-13 (BJ920000). Every interval here is inside one extract with one set of fetch times;
   nothing here is out-of-sample.
10. **Vendor closes are reconstructed** (§2, §5.2), never independently retrieved. Full-precision
    pre-rounding values are **not recoverable** from the permitted JSON — that is a reported bound,
    not a solved problem, and it is why the tests are feasibility tests rather than fits.
11. **R1's closed intervals favour feasibility.** A stricter rounding rule would make some
    "feasible" verdicts fail; it would not rescue an infeasible one, since narrowing per-date sets
    cannot create an intersection. So the **infeasibility** verdicts are robust to tightening R1;
    the feasibility verdicts are not.
12. **One long segment per source.** §5.7's stratification rests on three source groups with two,
    four and two non-zero-difference intervals respectively.

---

## 7. What this changes for U-6 — and what it does not

**Changed.** The assessment's Q-2 (E-1 unexplained) is **narrowed**: under stated assumptions the
28-versus-27 step is accounted for as an artefact of an infeasible additive reading, and under R1
alone it is inside the rounding-feasible range anyway. The assessment's §3.1 caution that "exact
non-constancy refutes nothing" is now **quantified**: it is exactly right for a stored ratio under
H-mul, and it does **not** rescue H-add on SH's `stock_zh_a_daily` segment, where the miss is
13–14 cents against a 2-cent bound.

**Not changed.** Q-3 — the reference basis is recorded, not independently certified — remains the
decisive reason to withhold certification, and §5.7 arguably **strengthens** it by showing two
pipelines under one label behaving differently. Q-4 (G-e), Q-5 (G-g), Q-6 (early coverage) and Q-7
are untouched. **U-6 stays deferred; no sufficiency rule is proposed, and none of these results is
offered as one.** `vendor_basis` stays `unverified`; the outcome remains **fail-closed, not a
disproof**.

---

## 8. Preservation

**Created:** this file only. **Modified:** nothing. Verified after the run: the accepted G1
delivery is **46/46 byte-identical** to the frozen
`_m2_codex_review/g1_review_20260909_r3_doc1/reviewed_delivery` with no file added or removed; the
five accepted G3 r2 pins match; `results.json` `538adc5c…` and `reference_extract.json`
`ea021004…` are unchanged after reading; the basis module, its tests and both `basis_eval_*`
outputs match; the five smoke producers and `closure_r2abc_v2.py` match; the P1 proposal
`71e0dc52…`, goal `f8b699e5…`, request `c39726d0…`, all G1/G3/U-6 acceptance and review documents,
the U-6 readiness assessment `de130cf0…`, all reviewer snapshots and the coordination state are
unchanged. No test, replay, adapter run, decoding run, network call, SQLite open, capture or
service action occurred. No script or output directory was added to the repository. Git was not
staged, committed or pushed.

---

## 9. Highest-value next offline analysis under the same authorization

**One candidate, and one non-candidate.**

**Worth doing — bound what the reference label can and cannot mean, from retained bytes only.**
§5.7 is the first evidence that two pipelines carrying the same `qfq` label relate to the vendor
series differently. The retained extract also holds `volume`, `amount` and `volume_unit` per row
for all three symbols, and `results.json` holds the index series where both legs are basis `none`
and agree exactly. A bounded study could ask whether the **non-price** retained fields (volume and
amount, and their unit labels) show the same source-stratified discontinuities at the same
`source`+`updated_at` boundaries as the price relations do. If they do, the boundary is a property
of the pipeline rather than of price adjustment specifically; if they do not, the price relation is
isolated. Either answer sharpens statement 3 — the decisive open item — using only retained JSON,
no new acquisition, and no threshold.

**Not worth doing.** Any further variation on §5.3's price-relation tests over these same
intervals. The feasibility verdicts are already exact under R1, the infeasibility verdicts are
robust to tightening it, and more relation families fitted to the same 470-session windows would
add candidates without adding evidence. And nothing here can substitute for independent
reference-basis evidence, which no retained-JSON study can supply.

**Stop: `proposed for review`.** This study is not M2 completion, does not certify a vendor basis,
and authorizes nothing.
