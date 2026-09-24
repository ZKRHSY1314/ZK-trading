# U-6 readiness assessment — can a vendor-basis sufficiency rule yet be proposed?

> **Status: `proposed for review`. Documentation only.** Task `U6-READINESS-20260909`.
> Existing retained artifacts only — **no network, no source query, no new extract, no SQLite
> open, no capture, no replay, no test run, no ratio recomputation, no script, no output
> directory.** Every file named below was read and left unchanged; this document is the only
> file created.
>
> **This adopts nothing.** U-6 remains deferred, P1 open, every eligibility result false,
> source capability FAIL, both capture authorizations consumed. No threshold, tolerance,
> sample-count cutoff or calibration is defined; no rule, positive eligibility branch, code or
> gate wiring follows. This is not M2 completion and not vendor-basis acceptance.

---

## 1. Six statements that must not be merged

The P1 proposal (`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §1) separates three; this assessment needs
six, because G-1 and G-3 introduced three more places where an error could hide.

| # | Statement | Whose property | Present state |
|---|---|---|---|
| **1. Adapter transformation** | what *our* code does to the series on the `adjust=""` path | ours | **Established.** `adapter_transform = none` for all three symbols, from S1/B1 ∧ B2 ∧ R1 with current pins |
| **2. Vendor price basis** | what Sina *serves* — as-traded, or adjusted by some convention | the vendor's | **`unverified`** for all three symbols. This is what U-6 is about |
| **3. Reference-basis reliability** | whether the cached reference's stored `qfq`/`none` label is true of every row it covers | the cache's | **Not established.** See §3.5 — one stored label spans rows from three different upstream sources |
| **4. Identity** | that the vendor series and the reference series are the same instrument | both | Corroborated (I2/B4 identity leg); for BJ it additionally crosses an unexplained code change — **G-g** |
| **5. Source / fetch-time homogeneity** | that a compared span has no recorded `source` or `updated_at` change | the extract's | **Established and measured**, per segment. It removes *recorded metadata differences* — nothing more |
| **6. Coverage** | that the compared span reaches far enough, and that the event set inside it is complete | the evidence set's | **Not established.** G-5 (no earlier reference rows) and G-e (event set not exhaustive) both bite |

**The standing prohibition, restated because this assessment is where it would most easily be
broken:** statement 5 is a fact about metadata columns. It is *not* evidence about statement 2
or 3. A span homogeneous in `source` and `updated_at` is not thereby homogeneous in price
convention — `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §4 says this explicitly, and nothing in G-1 or
G-3 changes it.

---

## 2. The old U-6 deferral, and what has actually changed

### 2.1 The three premises the deferral rested on

`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` U-6 (§5, lines 556–578) called U-6 **evidence-blocked, not
policy-blocked**, on three named gaps:

| Premise as written | State now | Changed by |
|---|---|---|
| **G-1** — "no corporate action is established inside any available span" | **False now.** Six cash implementations are established at Tier A, with ex-dates inside the retained comparison span | G1, accepted |
| **G-3** — "the wider ratio series has never been computed; only the 10-session tail exists" | **False now.** The full ratio and difference series exist over every usable common date for all three symbols | G3, accepted |
| **G-5** — "no comparison is possible before each symbol's earliest date in the extract" | **Still true, unchanged.** No reference row before 2024-06-21 (SH600011), 2024-06-19 (SH000300), 2024-08-13 (BJ920000) | — |

So **two of three premises no longer hold.** The Codex G1 acceptance states the same thing:
*"The old U-6 proposal's premise … is now outdated: G1 and G3 supplied those bounded
observations. That changes the basis for considering a review; it does not adopt U-6."*

### 2.2 The §3.3 necessary conditions, one by one

`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §3.3 lists five necessary conditions. Their present state:

| # | Necessary condition | BJ920000 | SH600011 | Evidence |
|---|---|---|---|---|
| 1 | valid `adapter_transform` under D-1a, current pins | **met** | **met** | `basis_records.json`, `adapter_transform = none`, `pins_stale: false` |
| 2 | comparison span homogeneous in **both** `source` and `updated_at` | **met** — 470 rows, 2024-08-13 … 2026-07-23 | **met** — 470 rows, same span; and separately 37 rows, 2024-06-21 … 2024-08-12 | G3 `REPORT.md` segment tables |
| 3 | an **independently established** corporate action inside that span, from outside this evidence set | **met** — four | **met** — two inside the 470-row segment, one inside the 37-row segment | G1 Tier A notices |
| 4 | a reference whose own basis is known | **recorded as `qfq`** — but see §3.5; "recorded" is not "known" | same | G3 `REPORT.md` L27, L85 |
| 5 | observed behaviour consistent in **direction and magnitude** with that action | **direction yes; magnitude exact at 3 interior transitions** | **direction yes; magnitude exact at 1 of 2 interior comparisons** | G3 difference runs vs G1 amounts |

**Conditions 1, 2, 3 and 5 have moved from unmet to met for the first time. Condition 4 is
weaker than it looks.** That is the whole substantive change.

### 2.3 V-13 has now actually occurred

The proposal's validation matrix (§3.5) anticipated exactly this state:

> **V-13** — ratio step over a span homogeneous in source **and** `updated_at`, with an
> independently established action → *necessary conditions met; **no automatic upgrade** —
> stays `unverified` pending U-6.*

That row was hypothetical when written. It is now a description of the retained evidence. The
proposal pre-committed to no automatic upgrade in precisely this circumstance, and **that
pre-commitment is honoured here**: nothing in §3 below upgrades any label.

What changes is only the *character* of U-6. It was deferred as **evidence-blocked** — nothing
observable could bear on it. It is now better described as **evidence-available but
under-determined**: observations that bear on it exist, and they do not yet determine an answer.
Those are different states and they call for different next steps.

---

## 3. What the retained evidence does and does not say about vendor basis

Everything in this section is read off the accepted G3 report and the accepted G1 report. **No
series was recomputed, re-derived or re-joined for this assessment.**

### 3.1 The two simplest hypotheses, and what each predicts

The reference stores basis `qfq` for both stocks and `none` for the index. Taking the reference
at its stored label, two mechanisms could produce a vendor-minus-reference gap:

* **H-add — additive.** The reference's qfq is formed by subtracting cumulative future cash
  dividends. Prediction: `difference = vendor − reference` is **piecewise constant** between
  ex-dates, stepping down by exactly the per-share cash amount on each ex-date, and reaching
  zero at the anchor. The **ratio** then varies with price level.
* **H-mul — multiplicative.** The reference's qfq is formed by dividing by a cumulative factor.
  Prediction: the **ratio** is piecewise constant between ex-dates. The **difference** then
  varies with price level.

These are not exhaustive, and neither is a claim about what any provider actually does. They are
the two shapes the retained series can be checked against without computing anything new.

### 3.2 BJ920000 — matches H-add, on three interior transitions

From G3 `REPORT.md` (L89, L106–112): difference has **5 distinct values in 5 runs**; ratio has
**383 distinct values in 422 runs**. So the difference is piecewise constant and the ratio is
not — the H-add shape, not the H-mul shape.

| Difference level | Span | Sessions | Transition into the next level | Disclosed cash/share | Disclosed ex-date |
|---|---|---|---|---|---|
| `+0.29` | 2024-08-13 … 2024-09-27 | 32 | −0.06 on 2024-09-30 | 0.06 (`2024-068`) | 2024-09-30 |
| `+0.23` | 2024-09-30 … 2025-05-14 | 147 | −0.08 on 2025-05-15 | 0.08 (`2025-047`) | 2025-05-15 |
| `+0.15` | 2025-05-15 … 2025-09-17 | 89 | −0.07 on 2025-09-18 | 0.070 (`2025-103`) | 2025-09-18 |
| `+0.08` | 2025-09-18 … 2026-05-22 | 159 | −0.08 on 2026-05-25 | 0.08 (`2026-037`) | 2026-05-25 |
| `+0.00` | 2026-05-25 … 2026-09-04 | 74 (43 inside the task interval) | — | — | — |

All four transitions fall inside the 470-row segment homogeneous in both keys, and G1 §5.2
records `metadata_boundary = false` for every one of them.

### 3.3 SH600011 — the "five exact comparisons" headline needs decomposing

From G3 `REPORT.md` (L29–31): difference has **31 distinct values in 233 runs**; ratio has **241
distinct values in 468 runs**. **Neither is piecewise constant** — SH600011 matches neither H-add
nor H-mul as the series stand.

More importantly, the six comparisons are **not six equally informative tests**. Two of them are
anchor-adjacent:

| Comparison | Segment | Interior or anchor-adjacent | Result |
|---|---|---|---|
| E-5, ex 2024-09-30 | BJ 470-row | interior | exact |
| E-6, ex 2025-05-15 | BJ 470-row | interior | exact |
| E-3, ex 2025-09-18 | BJ 470-row | interior | exact |
| E-4, ex 2026-05-25 | BJ 470-row | **anchor-adjacent** (difference falls to 0.00 and stays there to the extract's end) | exact |
| E-1, ex 2025-07-10 | SH 470-row | interior | **0.28 observed vs 0.27 disclosed** |
| E-2, ex 2026-07-03 | SH 470-row | **anchor-adjacent** (difference falls to 0.00 and stays there to the extract's end) | exact |

**Why anchor-adjacency matters.** `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §2.1 already warns that a
flat ratio at the cached qfq tail "is what one expects anyway … because that tail is re-anchored
at every refresh". The last pre-anchor transition inherits that weakness: under H-add the
difference immediately before the anchor equals the cumulative dividends still to come, which for
the final event is that event's own amount. Its "exact match" is therefore **tied to the same
terminal-zero fact the proposal already discounted**, and is far less independent than the
interior transitions.

**The honest scoreboard is therefore: four interior comparisons, of which BJ920000 supplies three
exact and SH600011 supplies one discrepant.** "Five of six exact" is arithmetically true and
analytically misleading; it should not be used as the headline in any future basis argument.

There is one further SH observation, correctly excluded from G1's in-interval counts and worth
keeping visible here: **E-0** (ex 2024-07-11, disclosed 0.20) sits in SH's *other* homogeneous
segment, the 37-row `akshare.stock_zh_a_hist` span, where the difference moves 0.87 → 0.67
(Δ −0.20, exact) with no metadata boundary. That segment records **2 distinct differences in 37
rows** — piecewise constant, the H-add shape.

### 3.4 A reframing the retained numbers suggest — and why it is only a hypothesis

Grouping the three symbols' segments by the *reference source* of the rows, rather than by
instrument, the distinct-difference counts from G3 `REPORT.md`'s segment tables line up this way:

| Reference source of the segment | Symbol | Rows | Distinct differences | Shape |
|---|---|---|---|---|
| `akshare.stock_zh_a_hist` | SH600011 | 37 | **2** | piecewise constant |
| `tonghuasun.local.quotes.candle` | BJ920000 | 470 | **5** | piecewise constant |
| `akshare.stock_zh_a_daily` | SH600011 | 470 | **30** | not piecewise constant |
| `tonghuasun.local.quotes.candle` | SH600011 | 30 | 1 | constant (all zero, post-anchor) |
| `tonghuasun.local.quotes.candle` | BJ920000 | 30 | 1 | constant (all zero, post-anchor) |

**The one segment that fails the H-add shape is also the only long segment sourced from
`akshare.stock_zh_a_daily`.** That suggests the non-constancy may be a property of the
**reference source** (statement 3) rather than of the vendor's basis (statement 2) or of the
instrument.

**Three reasons this must not be treated as established:**

1. **It is not a controlled comparison.** The 470-row `stock_zh_a_daily` segment spans two years
   and a much wider price range than the 37-row segment; more distinct differences would be
   expected under *any* mechanism that interacts with price level or with 2-decimal storage. The
   counts alone cannot separate "different source convention" from "same convention, longer span,
   wider price range".
2. **Testing it requires a computation that is not authorized here** and was deliberately not
   performed: see M-1 in §6.
3. **Only one instrument populates each cell.** BJ920000 has exactly one `stock_zh_a_daily` row
   (2026-07-24), so the source-versus-instrument confound cannot be broken inside the retained
   extract.

### 3.5 Reference-basis reliability — the weak link in necessary condition 4

G3 `REPORT.md` records, for SH600011, `Reference basis stored: qfq` alongside **three** upstream
sources (`akshare.stock_zh_a_daily`, `akshare.stock_zh_a_hist`, `tonghuasun.local.quotes.candle`)
and 4 distinct fetch times; for BJ920000, `qfq` alongside **two** sources and 3 fetch times.

**A single stored basis label therefore spans rows produced by different upstream pipelines, and
the retained evidence contains nothing that verifies each pipeline actually applied that
convention.** Necessary condition 4 asks for "a reference whose own basis is *known*". What the
extract supplies is a *recorded* label. The distinction is exactly the one P1 §1 draws for the
vendor side, and it applies to the reference side too.

This matters specifically because **BJ920000's cleanest evidence — the 470-row additive-clean
segment — is sourced entirely from `tonghuasun.local.quotes.candle`**, a local provider whose own
data-source acceptance is explicitly incomplete under `CODEX_CLAUDE_COLLABORATION.md` §7 (the
four states — skill installed / plugin configured / local quote call succeeded / project data
source accepted — "不可相互代替"). The best-fitting evidence for a vendor-basis conclusion rests
on the reference leg that is least independently validated.

### 3.6 The index control, and what it is worth

SH000300: reference basis `none`, ratio exactly **1** on all 538 compared dates, difference
exactly **0**, across 4 fetch times and 3 recorded metadata boundaries.

**What it supports:** the decode path and the reference store agree *exactly*, to stored
precision, when no adjustment convention is in play on either side. That eliminates a whole class
of alternative explanations for the stock gaps — systematic decode error, unit or scale error,
transport corruption, or a rounding defect in the comparison itself.

**What it does not support:** anything about a stock's basis. `M2B_P1_BASIS_CONTRACT_PROPOSAL.md`
U-7 forbids using an index observation as evidence about a stock's basis, and that stands. The
index is a *control on the machinery*, not evidence on the question.

### 3.7 What is now eliminated, and what remains open

**Eliminated by the retained series (weak, but real, and unavailable before G-3):**

* The vendor series is **not** the same series as the reference's stored `qfq` over the retained
  span — the differences are non-zero (SH max +0.87, BJ max +0.29) and structured.
* The vendor series is **not** backward-adjusted (`hfq`) against this reference's anchor — the
  sign is uniformly `vendor ≥ reference` with equality only at the recent end, which is the
  opposite of what an `hfq` series would show.

**Not eliminated, and not decidable from the retained artifacts:**

* that the vendor applies *some* adjustment that is smaller than, or different in kind from, the
  reference's;
* that part or all of the observed structure originates in the **reference** rather than the
  vendor (§3.4, §3.5);
* that the event set is complete — **G-e is not established**, and a share-count-changing action
  (送股 / 转增 / 配股) would break both H-add and H-mul outright rather than perturb them;
* that BJ's series is one continuous instrument across the `832000 → 920000` change — **G-g is
  unknown**; the only support is the exchange's own continuity statement (G1 observation N-3,
  北证公告〔2024〕231号), which is explicitly recorded there as saying nothing about any vendor's
  adjustment behaviour.

**And the standing prohibition, applied to this section:** every date agreement above is a
**coincidence of dates and magnitudes**. None of it attributes causation, and none of it
certifies a price basis. G1 `REPORT.md` §5.6 says the same, and this assessment does not go
beyond it.

---

## 4. Prerequisite ledger

### Newly satisfied

| # | Prerequisite | Evidence |
|---|---|---|
| P-1 | An independently sourced corporate-action date inside a span homogeneous in both `source` and `updated_at` | Six Tier A implementations; four BJ + two SH inside the respective 470-row segments; one SH inside the 37-row segment |
| P-2 | The bounded offline ratio computation over that span using retained artifacts | G3 r2, accepted; 538 / 501 / 538 ratio points, 537 / 500 / 537 consecutive-date changes |
| P-3 | A discriminating observation of any kind exists | The 470-row segments contain non-zero, structured differences — the 10-session tail contained none |
| P-4 | Machine-level control that decode/units/transport are not the explanation | SH000300 ratio exactly 1 on 538 dates |
| P-5 | Metadata confounders identified and excluded at the compared pairs | `metadata_boundary = false` at all six ex-date pairs; all boundaries lie outside the interval |

### Still unmet

| # | Prerequisite | Why it is still unmet |
|---|---|---|
| Q-1 | A **single** mechanism consistent with **both** instruments | BJ fits H-add; SH's 470-row segment fits neither H-add nor H-mul (§3.2–3.3) |
| Q-2 | An explanation for E-1's 0.28 vs 0.27 | Unresolved. G1 §5.5 offers none, invents no tolerance, and does not treat it as immaterial |
| Q-3 | Reference-basis reliability per source | One stored label spans two or three upstream pipelines; none independently verified (§3.5) |
| Q-4 | A complete event set inside the compared span | **G-e not established** — publication-window and title-only search limits, asymmetric period evidence, sampled bases, uncovered July 2026 tail |
| Q-5 | Instrument continuity across the code change | **G-g unknown** |
| Q-6 | Any comparison before 2024-08-13 / 2024-06-21 | **G-5 unchanged** — no earlier reference rows in this extract; whether the cache holds any is *not determined* |
| Q-7 | Out-of-sample confirmation | All four interior comparisons come from one extract, one anchor, and (for the three that match) one reference source |

---

## 5. Can a discriminating rule responsibly be proposed now?

**No.** Not a sufficiency rule, and not a weaker "discriminating test" that would function as one.

Four independent reasons, any one of which is sufficient:

1. **No single mechanism fits both instruments (Q-1).** A rule calibrated on BJ920000's
   additive-clean behaviour would be contradicted by SH600011's own 470-row segment. A rule loose
   enough to admit both would have to be loose enough to admit almost anything.
2. **It would require inventing a tolerance (Q-2).** The only interior SH comparison **inside the
   task interval** is off by 0.01. Any rule that counts it as a match needs a tolerance; any rule
   that counts it as a failure declares the vendor basis *not* unadjusted on the strength of one
   unexplained cent. Inventing that number is explicitly out of scope, and there is nothing to
   calibrate it against. Note that SH's *other* interior comparison, E-0 in the 37-row segment,
   is exact — so the discrepancy is not a uniform property of the instrument either, which is
   what makes §3.4's source hypothesis worth testing rather than dismissing.
3. **The mechanism may not be the vendor's at all (Q-3, §3.4).** If the non-constancy originates
   in the reference source, a rule written now would encode a property of `stock_zh_a_daily` as
   though it were a property of Sina's payload — the exact category error P1 §1 exists to prevent.
4. **The event set is not established (Q-4).** H-add and H-mul both assume cash-only events. G-e
   leaves that assumption unverified, and a single unidentified 送股/转增/配股 would invalidate
   both shapes rather than perturb them.

**Two things that must not be mistaken for a reason to proceed anyway.** First, that all five
§3.3 necessary conditions are now arguably met: §3.3 states in terms that meeting them all still
leaves `vendor_basis` at `unverified` absent an agreed sufficiency rule, and V-13 pre-committed
to exactly that. Second, that the numbers "look convincing": three exact interior matches on one
instrument is a real observation and is still a sample of three, from one extract, against one
anchor, on the reference leg with the least independent validation.

---

## 6. The concrete minimum evidence needed, and why each item would discriminate

Ordered cheapest-first. **None of these is requested, prepared, scoped or authorized by this
document.** Items M-1 to M-3 need **no new data of any kind** — they are computations over
artifacts already retained and already accepted, the same class of work G-3 was.

| # | Evidence needed | Why it discriminates | What it needs |
|---|---|---|---|
| **M-1** | Per-date decomposition of `difference` and `ratio` against reference price level, **within each single inter-event segment**, for both stocks | This is the decisive test between §3.1's two shapes. Under H-add, `difference` is constant within a segment and `ratio` varies; under H-mul, `ratio` is constant and `difference` varies with price. SH600011's 470-row segment currently fits neither at whole-segment granularity — but 2-decimal storage of a multiplicative relation would produce exactly a small, price-tracking wander. Testing constancy *within* segments, at full stored precision, separates "a different mechanism" from "the same mechanism plus rounding". **If SH's within-segment `ratio` is constant to stored precision, Q-1 collapses and the two instruments are reconciled; if neither is constant, both shapes are refuted and no rule of this family is available at all.** | Retained artifacts only. No network, capture or SQLite |
| **M-2** | The E-1 neighbourhood at full stored precision — the ex-date pair and adjacent dates, against the disclosed 0.27 gross | Distinguishes three candidate explanations that a rule would treat very differently: (i) rounding of a multiplicative factor, which M-1 would corroborate; (ii) a different amount being applied — note `2026-036` discloses a QFII net of 0.36 against a gross of 0.40, so net-versus-gross conventions demonstrably exist in these documents; (iii) an unrelated data difference on that date. Only (i) is compatible with an exact-match sufficiency rule | Retained artifacts only |
| **M-3** | Source-stratified comparison of within-segment shape: `stock_zh_a_hist` vs `stock_zh_a_daily` vs `tonghuasun.local.quotes.candle` | Directly tests §3.4's reframing — whether the shape difference tracks the **reference source** (statement 3) or the **instrument**. Determines whether U-6 is even the right question, or whether the open question is reference-basis reliability instead | Retained artifacts only. Note the confound named in §3.4: only one long segment per source exists |
| **M-4** | G-e closure, or an explicit bound on what a title-and-publication-window search can miss | H-add and H-mul both assume cash-only events. Until the event set is bounded, an exact match is consistent with "the model is right" *and* with "an unidentified event is hiding inside a level" | Not closable by more of the same query — see G1 §4.5 |
| **M-5** | Reference coverage earlier than 2024-08-13 / 2024-06-21 (**G-5**), containing further events | Every interior comparison now available comes from one extract with one anchor. An earlier span is the only out-of-sample test of a model fitted on three points, and it is the only way to observe the reference's behaviour across more than one anchoring | **Requires a fresh read-only extract (G-6) — an authorization that does not exist and is not requested here.** Both capture authorizations remain consumed |

**Why M-1 is the right first step and M-5 is not.** M-5 is the strongest evidence and the most
expensive: it needs an authorization nobody holds. M-1 costs nothing beyond effort, uses bytes
already accepted twice over, and can plausibly resolve Q-1 outright — the single largest obstacle
in §5. Spending an authorization before running the free test would be the wrong order.

---

## 7. Evidence-to-claim table

Every row cites a retained artifact with its accepted hash. Paths are relative to the repository
root. **All were read read-only for this assessment and are unchanged.**

| Claim in this document | Artifact | SHA-256 | Location within it |
|---|---|---|---|
| `adapter_transform = none`, `vendor_basis = unverified`, all eligibility false | `claude methods/_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4/basis_records.json` | `c5b1bf3c2f660dcca84c1f3d44fba8252b1580d98fbce300d5412340d32448de` | `records.*.adapter_transform`; `eligibility.*` (`vendor_basis_unverified`); `view_eligibility` |
| Records digest, no `eligible=true` path, detection limits | `claude methods/_m2_smoke/basis_eval_.../PROVENANCE.json` | `a1b662a2cf67bb331202cec7e086887e59115994abd9828d4bcde7d4aafee514` | `records_sha256 = f9bef731…`; `eligibility_summary`; `detection_limits` |
| Evaluator/derivation rules and producer pin | same | same | `record_producer` (`p1.derivation.rev6`, `p1.evaluator.rev6`, `basis_record.py 0fda4f7e…`) |
| U-6's original three premises; necessary vs sufficient; V-13/V-14; §4 gaps | `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` | `71e0dc52b8cf93281b1c09f501a62695915ef070a740dc378df2f1637a66007c` | §1; §2.1; §3.3 (L239–256); §3.5 V-13/V-14; §4 (L325–424); §5.0; U-6 (L556–578); U-7; §5.9 |
| BJ difference: 5 values / 5 runs; ratio 383 / 422 | `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/REPORT.md` | `8f7bf13637f0d418237a0f969a71ea25930380c3f8f10601aa611e69995edabd` | L87–91; difference runs L106–112 |
| SH difference: 31 values / 233 runs; ratio 241 / 468 | same | same | L29–31 |
| Index ratio exactly 1, difference 0, basis `none` | same | same | L54–58, L79 |
| Per-segment sources, fetch times, distinct-difference counts | same | same | L43–50 (SH), L100–104 (BJ), L70–75 (index) |
| One stored basis label across multiple sources | same | same | L27 (SH: `qfq`, three sources, 4 fetch times); L85 (BJ: `qfq`, two sources, 3 fetch times) |
| 470-row both-key segments; SH's 471-row source span splits | same | same | L118–154 |
| Metadata boundaries all outside the compared ex-date pairs | same | same | L35–41 (SH), L93–98 (BJ), L50, L114 |
| Underlying series, coverage, validity | `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/results.json` | `538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd` | `results.*.comparison.difference.runs`, `.ratio`, `.ratio_changes.records`, `.segments` |
| Reference extract identity and decoder pins | `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/PROVENANCE.json` | `1a262d74110e30ef33e32d291038fc6c78a8c70204ccdad581017e9330575456` | `inputs.input_hashes` (`reference_extract.json ea021004…`); `reference_extract_content_sha256 3a599027…`; `hk_js_decode_sha256_pinned 39a599c9…`; `adapter_replayed: false` |
| G3 technically validated; 29/29 and 60/60 | `claude methods/M2B_G3_RATIO_ACCEPTANCE_CODEX.md` | `bb1b295999a5d3791481a35d354daa47ddab23cd7882087bd0f3fb1338ca2110` | "Validated files"; "Evidence and test results" |
| Six Tier A implementations; interior vs anchor-adjacent inputs; E-1 unresolved; G-e/G-g | `claude methods/_m2_smoke/g1_corporate_actions_20260909/REPORT.md` | `77941f8c1344ebe20be93c8377e15e68188670c69021d7b03f3925f016e6617a` | §2 (E-1…E-6); §4.4–§4.5 (G-e limits); §1 G-g; §5.2 direction-1 table; §5.4 counts; §5.5 E-1; §5.6 |
| Structured event/evidence index, gap ledger | `claude methods/_m2_smoke/g1_corporate_actions_20260909/events.json` | `7eb0e34d07b158bc8e46001d83faff4d6f62c0cc89b1212943c885b4214f366b` | `events_in_interval`; `whole_interval_bonus_conversion_rights.coverage_limits`; `gap_ledger`; `bounded_observations.N-3` |
| Retained-notice hashes, retrieval scope, preservation | `claude methods/_m2_smoke/g1_corporate_actions_20260909/PROVENANCE.json` | `b2d7b5c782d4afd99b0cb03d61f6bf957b6b8ff3e4cad90772d576f7a127f3b1` | `retained_files`; `standing_position.remaining_open_gaps` |
| BJ 0.06 / ex 2024-09-30 | `…/official_notices/cninfo_832000_2024-068_2024H1_equity_distribution_implementation.pdf` | `6f22f7be812355c9520cde6647fdf1e56d2937ee24b8695f52e9085f7704f9df` | pp. 1–2 |
| BJ 0.08 / ex 2025-05-15 | `…/official_notices/cninfo_832000_2025-047_FY2024_equity_distribution_implementation.pdf` | `aba4cb40278dc6a01d13824cb70cda8342dc510223534f7e654ccb09fee642ca` | pp. 1–2 |
| BJ 0.070 / ex 2025-09-18 | `…/official_notices/bse_832000_2025-103_2025H1_equity_distribution_implementation.pdf` | `157dc6157c27ea99b19793a08c71a6464c1e68caa5119b0c558157bae3624ef8` | pp. 1–2 |
| BJ 0.08 / ex 2026-05-25 (anchor-adjacent) | `…/official_notices/cninfo_920000_2026-037_FY2025_equity_distribution_implementation.pdf` | `c8bcf19fd6ec333eeec5604c585ed96aba2262e22f42362d3dce5e0aa40971a2` | pp. 1–2 |
| SH 0.27 / ex 2025-07-10 (the discrepant interior comparison) | `…/official_notices/cninfo_600011_2025-036_FY2024_equity_distribution_implementation.pdf` | `439ceb651b59383506e46055692a94756fd6a0b8fb136108d5dbe6c33f00e222` | p. 1 |
| SH 0.40 / ex 2026-07-03 (anchor-adjacent); QFII net 0.36 vs gross 0.40 | `…/official_notices/cninfo_600011_2026-036_FY2025_equity_distribution_implementation.pdf` | `269ed39f77af653f72c171be12068561b4f5ea0e5a934c90f8a37c0c4b8fdedb` | pp. 1–2 |
| SH 0.20 / ex 2024-07-11, in the 37-row segment | `…/official_notices/cninfo_600011_2024-034_FY2023_equity_distribution_implementation.pdf` | `ffe858d9423e6f75795ead65faad93788910bb24c1cf0eaab5589cca354570a2` | p. 1 |
| G1 technically validated; U-6 premise outdated; recommended next decision | `claude methods/M2B_G1_CORPORATE_ACTIONS_CODEX_ACCEPTANCE.md` | `0558bc6a92b5e986a90ae4f9ff70bb42f222ab3f41d04db8593c2ccf45c7954d` | "Evidence and preservation"; "What is complete and what needs a separate decision" |
| Tonghuashun's four non-substitutable states; data-source acceptance incomplete | `CODEX_CLAUDE_COLLABORATION.md` | `f17d42e4d56713ade00eb31010494f76fdfecb8c68be2eb9f2ea9f86c6191992` | §7; §2 roles; §5 status vocabulary |
| Degrade-to-review-only when data evidence is unclear | `AGENTS.md` | `cb6b114f1a88521873c632d12fea9e67579ab30b1b60864e9e7d5d5a522a85c3` | "Safety Boundaries" |

Supporting reviews consulted and unchanged: `M2B_P1_BASIS_CONTRACT_CODEX_REVIEW.md`
`e9fcab23…`, `M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW.md` `418bba5f…`,
`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md` `f90de3d1…`,
`M2B_P1_HANDOFF_DOCS_CODEX_REVIEW.md` `ba99cba2…`, `M2B_G3_RATIO_CODEX_REVIEW.md` `91388af5…`,
`M2B_G3_RATIO_CODEX_REVIEW_R2.md` `6b9c01fe…`, `M2B_NEXT_STAGE_DECISION_MEMO.md` `536505ea…`.

---

## 8. Recommended decision, alternatives, consequences

### Recommended

**Reclassify U-6 from *evidence-blocked* to *evidence-available but under-determined*, keep it
deferred as a rule, and — as a separate user decision — authorize one bounded,
documentation-and-computation-only study over retained artifacts covering M-1, M-2 and M-3.**

Nothing else changes: no sufficiency rule, no threshold, no tolerance, no label change, no
eligibility branch, no gate wiring, no capture, no extract.

*Rationale.* The deferral's stated grounds were G-1 and G-3, and both have been overtaken. But
the four obstacles in §5 are real and none is a policy preference — they are gaps in what the
evidence can currently distinguish. M-1 to M-3 attack the largest of them (Q-1 and Q-3) at the
cost of effort alone, on bytes already accepted twice, and could reconcile the two instruments or
refute both candidate shapes. Either outcome is decision-relevant; neither requires an
authorization anyone would have to grant.

*What would still be true afterwards.* Even a clean M-1 result would not by itself justify a
sufficiency rule: Q-2, Q-4, Q-5, Q-6 and Q-7 would remain, and §3.3's no-automatic-upgrade rule
would still apply. M-1's value is that it tells us whether a rule is *conceivable* on this
evidence family, before anyone spends an authorization finding out.

### Alternatives

| | Alternative | Consequence |
|---|---|---|
| **A** | **Keep U-6 fully deferred and do nothing further.** | Honest and fail-closed; `vendor_basis = unverified` remains an accurate recorded state (N-2). But it leaves P1 blocked by a premise that is now factually outdated, and leaves a free, decision-relevant test unrun. Boundary 2 stays blocked indefinitely — the proposal's own Option A caution, that this should be chosen *deliberately rather than by inaction*, applies with more force now than when it was written |
| **B** | **Adopt a sufficiency rule now on the strength of the exact matches.** | **Not defensible.** Requires a tolerance for E-1 (Q-2), is contradicted by SH's own segment (Q-1), may encode a reference-source property as a vendor property (Q-3), and assumes an event set that is not established (Q-4). It would also breach §3.3's explicit no-automatic-upgrade commitment and V-13 |
| **C** | **Recommended** — reclassify, keep deferred, authorize M-1/M-2/M-3 separately | Costs effort only. Resolves or refutes Q-1 and bears directly on Q-3. Leaves every label, gate and eligibility result untouched |
| **D** | **Seek a fresh read-only extract or new capture (M-5) now.** | Premature and expensive: both capture authorizations are consumed, G-6 authorization does not exist, and M-1 may make the question moot. Correct only *after* C, and only if C leaves the mechanism question open |

### If the recommendation is accepted, what must remain true of the follow-on work

It reads retained artifacts only; it recomputes nothing into any accepted directory; it produces
one document and no output directory, script or dataset; it defines no threshold, tolerance or
cutoff; it changes no label, gate or eligibility; and it stops at `proposed for review`. Should
its findings support a rule, the rule itself is a further, separately scoped decision — not a
consequence of the study.

---

## 9. What this document does not do, and preservation

* It **does not adopt U-6**, propose a sufficiency rule, or define any threshold, tolerance,
  sample-count cutoff or calibration.
* It **does not** assert a vendor basis, change any label, create any positive eligibility
  branch, or wire anything into a gate. All eligibility results remain `false` with reason
  `vendor_basis_unverified`.
* It **does not** treat any date or magnitude agreement as causal proof, and does not treat
  `source` / `updated_at` homogeneity as price-basis certification.
* It **does not** dispatch, prepare or request M-1 … M-5. It does not request a capture, an
  extract, a SQLite open or any network access.
* It **does not** claim M2 completion, source-capability acceptance, P1 closure, training
  readiness or vendor-basis acceptance. Source capability remains **FAIL**; both capture
  authorizations remain **consumed**.

**Preservation.** No file was modified. Every artifact in §7 was opened read-only; the accepted
G1 delivery (46 files), the accepted G3 r2 delivery (5 files), the basis module, its tests, both
`basis_eval_*` outputs, all reviewer snapshots and review documents, the P1 proposal, the goal
and request documents remain byte-for-byte unchanged, with the hashes recorded in §7 and in the
handoff accompanying this document. No test, replay, ratio calculation or script was run; no
supporting directory was created. Git was not staged, committed or pushed.

**A note on the two governance files.** `AGENTS.md` (`cb6b114f…`) and
`CODEX_CLAUDE_COLLABORATION.md` (`f17d42e4…`) are repository-root governance documents rather
than evidence artifacts. They are cited in §7 for the rules they state, and their hashes are
recorded there only as read-time preservation evidence — this document is not the register of
record for either file.

**Stop: `proposed for review`.**
