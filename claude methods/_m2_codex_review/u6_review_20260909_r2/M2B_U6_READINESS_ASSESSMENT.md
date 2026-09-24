# U-6 readiness assessment — can a vendor-basis sufficiency rule yet be proposed?

> **Revision 2** — status `proposed for review`. Task `U6-DOC-R1-20260909`, correcting revision 1
> (`7f043094…`) against `M2B_U6_READINESS_CODEX_REVIEW.md` findings **U6-R1 … U6-R4**.
> Documentation only; the correction is to this document's analysis, not to any source artifact.
>
> Existing retained artifacts only — **no network, no source query, no new extract, no SQLite
> open, no capture, no replay, no test run, no ratio computation, no fitting, no calibration, no
> script, no output directory.** Every file named below was read and left unchanged; this
> document is the only file written.
>
> **This adopts nothing.** U-6 remains deferred, P1 open, every eligibility result false, source
> capability FAIL, both capture authorizations consumed. No threshold, tolerance, sample-count
> cutoff or calibration is defined; no rule, positive eligibility branch, code or gate wiring
> follows. Not M2 completion, not vendor-basis acceptance.
>
> **The outcome is fail-closed, not a disproof.** The reviewed evidence is insufficient to
> certify a vendor price basis, so the basis stays **`unverified`**. That is not a finding that
> any candidate basis is false.

---

## 0. What revision 2 corrects

| Finding | Correction |
|---|---|
| **U6-R1.1** — the sign of `vendor − reference` was used to exclude `hfq`, and non-zero differences to exclude the reference's own convention | **Both exclusions withdrawn.** `V = aP`, `R = bP` with `a > 1 > b > 0` also gives `V > R`, so the inequality cannot identify which side is adjusted. Non-zero differences establish only that the two retained numerical series differ — not that the *conventions* differ, and not that every `qfq` implementation with another anchor, amount or rounding rule is excluded. §3.7 and the handoff no longer claim any elimination |
| **U6-R1.2** — H-add / H-mul were treated as tested and one as refuted | Both are now stated as **candidate relational models with their assumptions written out**, not supplier algorithms. Revision 1 read aggregate distinct-value and run counts as a test of constancy *between* event dates; a rounded multiplicative relation can vary numerically inside an event interval, so **exact non-constancy of a stored series refutes nothing**. H-mul is **untested**, not refuted — that test is M-1 |
| **U6-R1.3** — E-2 / E-4 were downgraded to "anchor-adjacent" and the count restated as four | **Withdrawn.** The reasoning was circular: it assumed H-add to discount evidence for H-add. **Six identified comparisons and five exact difference matches are restored**, with E-2 and E-4 tagged factually as *transitions into an observed zero-difference tail*. No independence or evidentiary-weight claim is made for any pair, and the extract's end date is no longer called an anchor |
| **U6-R2** — the index control, G-g, and a governance rule were over-read | The index result is now a **bounded control observation** for that instrument and path only; it excludes nothing stock-specific. **G-g is narrowed to the missing legal effective date** — official old/new mapping, issuer identity and the exchange continuity statement *are* established. The `CODEX_CLAUDE_COLLABORATION.md` §7 citation as a current acceptance finding, and the "least independently validated" ranking, are both **withdrawn** |
| **U6-R3** — prerequisite and next-study claims carried invalid implications | Condition 5 is restored as **ratio** behaviour and reported as *direction observed, magnitude not assessed in ratio terms*. The blanket "1/2/3/5 met" and "V-13 literally describes the evidence" are withdrawn; the ledger is now per symbol and span with unknowns kept. The false claim that rejecting E-1 would *declare* the basis not unadjusted is corrected. The invented **common-mechanism prerequisite is withdrawn** and demoted to an exploratory preference. M-1/M-2/M-3 payoffs are restated as *narrowing*, not identification or refutation |
| **U6-R4** — "neither requires an authorization anyone would have to grant" | **Withdrawn.** The candidate study needs no newly acquired data but **does require a separately scoped authorization for computation and outputs**. None is granted by this task or requested by this document. The reclassification of U-6 is likewise **proposed**, not adopted |

**Preserved from revision 1** (the review lists these as valid): the G-1/G-3 premises are
outdated; early reference coverage is still absent; statements 1–3 must stay separate; six
identified implementations and five exact difference matches are observations with E-1 discrepant;
source/fetch-time homogeneity is metadata homogeneity only; new work and policy adoption are
separate decisions.

---

## 1. Six statements that must not be merged

`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §1 separates three; this assessment needs six, because G-1
and G-3 introduce three further places an error could hide.

| # | Statement | Whose property | Present state |
|---|---|---|---|
| **1. Adapter transformation** | what *our* code does on the `adjust=""` path | ours | **Established.** `adapter_transform = none` for all three symbols, from S1/B1 ∧ B2 ∧ R1 with current pins |
| **2. Vendor price basis** | what Sina *serves* | the vendor's | **`unverified`** for all three symbols. This is U-6's subject |
| **3. Reference-basis reliability** | whether the cached reference's stored `qfq` / `none` label is true of every row it covers | the cache's | **Not independently certified in this assessment.** One stored label spans rows from more than one upstream pipeline (§3.5) |
| **4. Identity** | that the vendor and reference series are the same instrument | both | Corroborated (I2/B4 identity leg). For BJ920000 the official old/new code mapping and issuer identity are additionally established in G1; what is missing is the **legal effective date** (G-g) and any evidence about how a given vendor implemented the mapping |
| **5. Source / fetch-time homogeneity** | that a compared span shows no recorded `source` or `updated_at` change | the extract's | **Established and measured** per segment. It removes *recorded metadata differences* — nothing more |
| **6. Coverage** | that the compared span reaches far enough, and that the event set inside it is complete | the evidence set's | **Not established.** G-5 (no earlier reference rows in this extract) and G-e (event set not established as complete) both apply |

**The standing prohibition, restated because this is where it would most easily break:** statement
5 is a fact about metadata columns. It is **not** evidence about statement 2 or 3. A span
homogeneous in `source` and `updated_at` is not thereby homogeneous in price convention —
`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §4 says so, and neither G-1 nor G-3 changes it.

---

## 2. The old U-6 deferral, and what has actually changed

### 2.1 The three premises the deferral rested on

`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` U-6 (§5, lines 556–578) called U-6 **evidence-blocked, not
policy-blocked**, on three named gaps:

| Premise as written | State now | Changed by |
|---|---|---|
| **G-1** — "no corporate action is established inside any available span" | **no longer holds.** Six cash implementations are established at Tier A with ex-dates inside the retained comparison span | G1, accepted |
| **G-3** — "the wider ratio series has never been computed; only the 10-session tail exists" | **no longer holds.** The full ratio and difference series exist over every usable common date for all three symbols | G3, accepted |
| **G-5** — "no comparison is possible before each symbol's earliest date in the extract" | **still holds, unchanged.** No reference row before 2024-06-21 (SH600011), 2024-06-19 (SH000300), 2024-08-13 (BJ920000) | — |

The Codex G1 acceptance records the same: *"The old U-6 proposal's premise … is now outdated: G1
and G3 supplied those bounded observations. That changes the basis for considering a review; it
does not adopt U-6."*

### 2.2 The §3.3 necessary conditions, per symbol and span, with unknowns kept

`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §3.3 lists five necessary conditions. Revision 1 declared
four of them met across the board; that was too coarse. Restated per span, with conditions 4 and
5 quoted as written:

| # | Condition (as written in §3.3) | BJ920000, 470-row segment | SH600011, 470-row segment | SH600011, 37-row segment |
|---|---|---|---|---|
| 1 | a valid `adapter_transform` label under D-1a/D-1b, with current pins | **observed** | **observed** | **observed** |
| 2 | a comparison span homogeneous in **both** `source` **and** `updated_at` | **observed** (2024-08-13 … 2026-07-23) | **observed** (same span) | **observed** (2024-06-21 … 2024-08-12) |
| 3 | an **independently established** corporate action inside that span, from a source outside this evidence set | **observed** — four | **observed** — two | **observed** — one |
| 4 | "a reference whose own basis is **known**" | **not established.** The extract *records* `qfq`; recording is not knowing (§3.5) | **not established** | **not established** |
| 5 | "an observed **ratio** behaviour consistent in **direction and magnitude** with that action" | **direction observed** at all four pairs; **magnitude not assessed in ratio terms** | **direction observed** at both pairs; **magnitude not assessed in ratio terms** | **direction observed**; **magnitude not assessed in ratio terms** |

**Why condition 5 is only partly addressed.** Revision 1 substituted an exact *difference* step
for the condition's *ratio* behaviour. The two are not interchangeable. What the retained
artifacts supply is:

* the stored ratio change at each of the six ex-date pairs, all **negative**:
  BJ `−0.014336056080001658` (2024-09-30), `−0.0032847626827969822` (2025-05-15),
  `−0.003123443162614592` (2025-09-18), `−0.005291005291005346` (2026-05-25);
  SH `−0.04083287082155218` (2025-07-10), `−0.0554785020804438` (2026-07-03);
* and, from the G3 report's own summary lines, that the **largest absolute consecutive-date ratio
  change in each stock's entire retained series** falls at a disclosed ex-date — BJ
  `0.01433605608` in 500 pairs, SH `0.05547850208` in 537 pairs. The report labels both "a
  magnitude, not a threshold", and so does this document.

Turning a disclosed per-share cash amount into a *predicted ratio change* requires the price
level and an assumed model — a computation that was not performed and is not authorized. So
condition 5's magnitude leg is **not assessed**, and the exact agreements reported in §3 are
**difference** agreements.

**Therefore: conditions 1, 2 and 3 are observed for three spans; condition 4 is not established;
condition 5 is half-addressed.** Revision 1's "all five arguably met" is withdrawn.

### 2.3 V-13, stated accurately

The proposal's matrix (§3.5) anticipated a state close to this one:

> **V-13** — ratio step over a span homogeneous in source **and** `updated_at`, with an
> independently established action → *necessary conditions met; **no automatic upgrade** —
> stays `unverified` pending U-6.*

Revision 1 said V-13 "is now a description of the retained evidence". **That overstates it**:
V-13 presumes the necessary conditions met, and condition 4 is not. What is true is narrower and
still worth recording — the retained evidence has moved materially **toward** V-13's situation,
and V-13's instruction for that situation is *no automatic upgrade*. Nothing in §3 upgrades any
label, so the instruction is honoured either way.

**Proposed** reclassification, not an adopted change: U-6 was deferred as **evidence-blocked** —
nothing observable could bear on it. It is better described now as **evidence-available but
under-determined**: observations that bear on it exist and do not determine an answer. Adopting
that relabelling is a user decision; `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` is unchanged by this
document.

---

## 3. What the retained series show

Everything here is read off the accepted G3 and G1 artifacts. **No series was recomputed,
re-derived, re-joined or fitted for this assessment.**

### 3.1 Two candidate relational models, and their assumptions

These are **candidate relational models written to organise observation**, not claims about any
supplier's algorithm. Each holds only under the assumptions listed, none of which is established:

**Shared assumptions (A1–A4), all unverified.**
A1 the vendor series and the reference series are two functions of one common underlying
as-traded price; A2 the reference's stored `qfq` label is true of every row in the span
(**explicitly not established** — §3.5); A3 the only corporate actions in the span are the
identified cash distributions (**not established** — G-e); A4 stored values are 2-decimal
roundings of the modelled quantities, with a rounding rule that is **not specified anywhere in
this document**.

* **H-add.** Additionally assumes the reference's adjustment is formed by *subtracting* cumulative
  future cash amounts from a fixed reference point. Then `difference = vendor − reference` is
  constant between ex-dates, stepping by the per-share amount on each ex-date.
* **H-mul.** Additionally assumes the reference's adjustment is formed by *dividing* by a
  cumulative factor. Then `ratio = vendor / reference` is constant between ex-dates.

**A caution that governs all of §3.** Under A4, neither model predicts an *exactly* constant
stored series: rounding perturbs both. **Exact non-constancy of a stored series therefore refutes
neither model.** Revision 1 treated it as refutation; that is withdrawn. Whether an observed
series is constant *to within a specified rounding model* is exactly what M-1 would examine, and
no rounding model is specified or authorized here.

### 3.2 BJ920000 — an observation consistent with H-add

From G3 `REPORT.md` (L89, L106–112): difference takes **5 distinct values in 5 runs**; ratio takes
**383 distinct values in 422 runs**.

| Difference level | Span | Sessions | Step into the next level | Disclosed cash/share | Disclosed ex-date |
|---|---|---|---|---|---|
| `+0.29` | 2024-08-13 … 2024-09-27 | 32 | −0.06 on 2024-09-30 | 0.06 (`2024-068`) | 2024-09-30 |
| `+0.23` | 2024-09-30 … 2025-05-14 | 147 | −0.08 on 2025-05-15 | 0.08 (`2025-047`) | 2025-05-15 |
| `+0.15` | 2025-05-15 … 2025-09-17 | 89 | −0.07 on 2025-09-18 | 0.070 (`2025-103`) | 2025-09-18 |
| `+0.08` | 2025-09-18 … 2026-05-22 | 159 | −0.08 on 2026-05-25 | 0.08 (`2026-037`) | 2026-05-25 |
| `+0.00` | 2026-05-25 … 2026-09-04 | 74 (43 inside the task interval) | — | — | — |

Two things are observed rather than inferred: the run boundaries **coincide with the four
disclosed ex-dates**, and each step equals the disclosed per-share amount. All four pairs carry
`metadata_boundary = false` (G1 §5.2). G1's arithmetic note also records that the opening level
`0.29` equals the sum of the four step magnitudes.

**What this is.** An observation consistent with H-add under A1–A4. It is **not** a demonstration
that H-add is the mechanism, and it does **not** exclude H-mul: whether a rounded multiplicative
relation could reproduce exactly five distinct differences with boundaries at those dates is
**not determined here**, and determining it needs the price-level computation of M-1.

### 3.3 SH600011 — an observation that H-add does not organise, with H-mul untested

From G3 `REPORT.md` (L29–31): difference takes **31 distinct values in 233 runs**; ratio takes
**241 distinct values in 468 runs**, over 538 compared dates with three identified events in the
full span.

**What the run counts do and do not license here.** The review rightly warns that aggregate
distinct-value counts do not test constancy *between* event dates. The one inference they do
license is a counting argument: three identified events divide the full span into at most four
intervals, so **232 difference changes and 467 ratio changes cannot all sit at event dates** —
both stored series must change *inside* intervals. That is a pigeonhole observation about counts,
not a fitted test, and it is the only thing drawn from them.

So the stored difference is not constant between event dates, and H-add does not organise this
segment even loosely. The stored **ratio** is not exactly constant either — but as §3.1 states,
**that does not refute H-mul**: under A4 a rounded multiplicative relation is *expected* to vary
numerically inside an event interval. **H-mul is untested for SH600011, not refuted**, and
distinguishing "varies because rounded" from "varies because misspecified" is precisely M-1.

The six identified comparisons and their outcomes, preserved in full:

| Comparison | Segment | Disclosed cash/share | Difference step | Factual tag |
|---|---|---|---|---|
| E-5, ex 2024-09-30 | BJ 470-row | 0.06 | −0.06 | exact |
| E-6, ex 2025-05-15 | BJ 470-row | 0.08 | −0.08 | exact |
| E-3, ex 2025-09-18 | BJ 470-row | 0.070 | −0.07 | exact |
| E-4, ex 2026-05-25 | BJ 470-row | 0.08 | −0.08 | exact; **transition into an observed zero-difference tail** (0.00 from 2026-05-25 to 2026-09-04) |
| E-1, ex 2025-07-10 | SH 470-row | 0.27 | −0.28 | **discrepant by 0.01, unresolved** |
| E-2, ex 2026-07-03 | SH 470-row | 0.40 | −0.40 | exact; **transition into an observed zero-difference tail** (0.00 from 2026-07-03 to 2026-09-04) |

**On the two tagged rows.** Revision 1 called them anchor-adjacent, argued their magnitudes were
forced, and restated the count as four interior comparisons. **That is withdrawn as circular** —
it used H-add to discount evidence bearing on H-add, and equality after a date does not by itself
force the preceding gap to equal an independently disclosed amount. The tag is retained because
the zero-difference tail is **observed**; no anchor is thereby demonstrated, and **no independence
or evidentiary weight is claimed or denied for any of the six pairs**. The count stands at **six
identified comparisons, five exact difference matches, one discrepant.**

Also preserved, and correctly outside G1's in-interval counts: **E-0** (ex 2024-07-11, disclosed
0.20) sits in SH's other homogeneous segment, the 37-row `akshare.stock_zh_a_hist` span, where the
difference moves 0.87 → 0.67 (step −0.20, exact) with no metadata boundary. That segment records
**2 distinct differences in 37 rows**.

### 3.4 A grouping observation, and the confound it cannot break

Grouping the segments by the *reference source* of their rows, the distinct-difference counts from
G3 `REPORT.md`'s segment tables fall out this way:

| Reference source of the segment | Symbol | Rows | Distinct differences |
|---|---|---|---|
| `akshare.stock_zh_a_hist` | SH600011 | 37 | **2** |
| `tonghuasun.local.quotes.candle` | BJ920000 | 470 | **5** |
| `akshare.stock_zh_a_daily` | SH600011 | 470 | **30** |
| `tonghuasun.local.quotes.candle` | SH600011 | 30 | 1 (all zero) |
| `tonghuasun.local.quotes.candle` | BJ920000 | 30 | 1 (all zero) |

The one long segment whose difference is not close to piecewise constant is also the only long
segment sourced from `akshare.stock_zh_a_daily`. **That is a grouping observation, and it is
consistent with the possibility that some of the structure originates in the reference
(statement 3) rather than the vendor (statement 2).** It also fits the possibility that
heterogeneous reference pipelines apply different transformations while the vendor uses one basis.

**Why it settles nothing.** Source, instrument, calendar span and price range vary *together*
across these cells: SH's `stock_zh_a_daily` segment covers two years and a far wider price range
than the 37-row segment, and more distinct differences would be expected under any relation
interacting with price level or 2-decimal storage. **Regrouping the same records cannot break that
confound** — no cell holds two instruments on one source over one span, and BJ920000 has exactly
one `stock_zh_a_daily` row (2026-07-24). Breaking it would need records this extract does not
contain.

### 3.5 Reference basis — recorded, not independently certified here

G3 `REPORT.md` records, for SH600011, `Reference basis stored: qfq` alongside **three** sources
(`akshare.stock_zh_a_daily`, `akshare.stock_zh_a_hist`, `tonghuasun.local.quotes.candle`) and 4
distinct fetch times; for BJ920000, `qfq` alongside **two** sources and 3 fetch times.

**A single stored basis label therefore spans rows produced by more than one upstream pipeline,
and this assessment has no independent certification that each pipeline applied that convention.**
Condition 4 asks for a reference whose basis is *known*; what the extract supplies is a *recorded*
label. That is the same distinction P1 §1 draws on the vendor side.

**Two revision-1 statements withdrawn here.** First, the citation of
`CODEX_CLAUDE_COLLABORATION.md` §7 as evidence of a current source-acceptance status: §7 is a
**governance rule** about states that must not be substituted for one another, not a retained
finding about today's acceptance status, and no such status review is cited in this document.
Second, the description of BJ920000's reference leg as "least independently validated": that is a
**comparative ranking this assessment cannot support**, since it holds no certification for any of
the pipelines. The accurate statement is uniform — **no reference pipeline's basis is
independently certified in the evidence read here.**

### 3.6 The index — a bounded control observation

SH000300: reference basis `none`, ratio exactly **1** on all 538 compared dates, difference exactly
**0**, across 4 fetch times and 3 recorded metadata boundaries.

**What it is.** A bounded control observation: on **that instrument, through that code path, at
stored precision**, the decode leg and the reference store agree exactly.

**What it is not.** Revision 1 said it "eliminates a whole class of alternative explanations" for
the stock gaps. **Withdrawn.** It does not rule out a stock-specific decode, source, rounding,
unit or transport difference; it does not rule out errors shared by both legs; and the stock code
path is a different path. `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` U-7 separately forbids using an
index observation as evidence about a stock's basis, and that stands.

### 3.7 What is shown, and what is not

**Shown by the retained artifacts:**

* The two retained numerical series **differ** over the compared spans, non-trivially and with
  structure — SH difference up to +0.87, BJ up to +0.29, with BJ's run boundaries coinciding with
  four disclosed ex-dates.
* The stored ratio change is **negative at all six** identified ex-date pairs, and the largest
  absolute consecutive-date ratio change in each stock's entire retained series falls at a
  disclosed ex-date.
* Five of six identified comparisons show a difference step **equal** to the disclosed per-share
  cash amount; one (E-1) differs by 0.01 and is unresolved.
* None of the six pairs sits at or crosses a recorded `source` / `updated_at` boundary.

**Not shown, and withdrawn from revision 1:**

* **No candidate basis is excluded.** The sign of `vendor − reference` cannot identify which side
  is adjusted — `V = aP` and `R = bP` with `a > 1 > b > 0` produce the same inequality — so
  revision 1's exclusion of a positively rescaled (`hfq`-like) candidate is **withdrawn**.
* **No convention is excluded.** Non-zero differences show the two *series* differ; they do not
  show the *conventions* differ, and they do not exclude a `qfq` implementation with a different
  reference point, amount basis or rounding rule. Revision 1's "vendor ≠ the reference's stored
  qfq convention" is **withdrawn**.
* No mechanism is identified for either instrument; H-add is unconfirmed and H-mul untested.
* No anchor is demonstrated. An observed zero-difference tail and a stored `qfq` label do not
  establish where or how either series is anchored.
* No claim about relative evidentiary weight or independence among the six comparisons.
* Nothing about causation. Every date and magnitude agreement above is **a coincidence of dates
  and magnitudes**, exactly as G1 `REPORT.md` §5.6 states; and no `source` / `updated_at` pin
  certifies a price basis.
* G-e leaves the identified event set not established as complete, so every model check inside
  the span is **conditional on the identified set** (assumption A3). This is a limit on what such
  a check could conclude — not a demand that G-e be closed first.
* **G-g, stated precisely.** What is missing is the **legal effective date** of the
  `832000 → 920000` change, plus any evidence of how a particular vendor implemented the mapping.
  What G1 *does* establish is retained and not in doubt: the official BSE old/new code mapping
  (row 214, retained page), the matching issuer identity across the retained filings, and the
  exchange's own continuity statement (observation N-3, 北证公告〔2024〕231号). Revision 1's
  broader framing — that instrument continuity is unknown — is **withdrawn**.

---

## 4. Observation ledger

Revision 1 titled this a prerequisite ledger and, in doing so, invented a prerequisite. Split in
two, with the invented item demoted.

### 4.1 What is newly observed

| # | Observation | Where |
|---|---|---|
| O-1 | Independently sourced corporate-action dates now exist inside spans homogeneous in both `source` and `updated_at` — four (BJ, 470-row), two (SH, 470-row), one (SH, 37-row) | G1 Tier A notices; G3 segment tables |
| O-2 | The wider ratio and difference series exist for all three symbols | G3 r2, accepted |
| O-3 | Discriminating *observations* of some kind now exist: the 470-row segments carry non-zero, structured differences, where the earlier 10-session tail carried none | G3 `REPORT.md`; proposal §2.1 |
| O-4 | On the index instrument and path, decode and reference agree exactly at stored precision — a bounded control | G3 `REPORT.md` L54–58 |
| O-5 | No recorded metadata boundary coincides with any of the six ex-date pairs; all recorded boundaries lie outside the task interval | G1 §5.2; G3 `REPORT.md` L35–41, L93–98 |

### 4.2 What remains unknown

| # | Unknown | Why |
|---|---|---|
| Q-2 | E-1's 0.28 against a disclosed 0.27 | Unresolved. G1 §5.5 offers no explanation, invents no tolerance, and does not call it immaterial |
| Q-3 | Reference-basis reliability per pipeline (**condition 4**) | One stored label spans more than one upstream source; no pipeline's basis is independently certified in the evidence read here (§3.5) |
| Q-4 | Whether the identified event set inside the compared spans is complete | **G-e not established** |
| Q-5 | The **legal effective date** of the `832000 → 920000` change, and how any vendor implemented the mapping | **G-g** — narrowly scoped as in §3.7; issuer identity and exchange continuity are *not* in question |
| Q-6 | Any comparison before 2024-08-13 / 2024-06-21 | **G-5 unchanged.** Whether the cache holds earlier rows is *not determined* |
| Q-7 | The magnitude leg of **condition 5**, in ratio terms | Requires a price-level computation that was not performed and is not authorized |

### 4.3 Withdrawn: the "single common mechanism" prerequisite

Revision 1 listed "a single mechanism consistent with both instruments" as an unmet prerequisite
and then used its failure as a reason no rule could exist. **It is not an adopted prerequisite
anywhere** — not in §3.3, not in §3.5's matrix, not in U-6. Heterogeneous reference pipelines
could apply different transformations while the vendor uses a single basis, in which case a
scoped, per-pipeline rule would not be contradicted by the instruments differing.

It is retained only as an **exploratory modelling preference**: a single mechanism covering both
would be easier to reason about and to state as a rule. Its absence is a reason for caution, not
a bar.

---

## 5. Can a discriminating rule responsibly be proposed now?

**No — and the correct form of that answer is fail-closed.** The reviewed evidence is insufficient
to certify a vendor price basis, so `vendor_basis` stays **`unverified`**. **That is not a finding
that any candidate basis is false**, and no universal impossibility is claimed. Three sufficient
practical reasons, in order of weight:

1. **The reference basis is not independently certified (Q-3, condition 4).** Every candidate
   model in §3.1 assumes the reference's stored label is true of every row (A2). It is a recorded
   label spanning more than one pipeline. **This reason alone is sufficient to withhold
   certification**, and it needs no additional prerequisite: a rule resting on an uncertified
   reference would certify the vendor on the strength of an unexamined assumption about the
   reference.
2. **No mechanism has been tested (§3.1–3.3, Q-7).** H-add is unconfirmed; H-mul is untested,
   because whether a stored series is constant to within a rounding model has not been examined
   and no rounding model is specified. A rule written now would encode a shape nobody has tested.
3. **E-1 is unexplained (Q-2).** A rule that admits it needs a tolerance — out of scope, and with
   nothing to calibrate against.

**A logical correction to revision 1.** It claimed that "any rule that counts E-1 as a failure
declares the vendor basis *not* unadjusted". **That is false.** A fail-closed rule declines to
certify and leaves `vendor_basis = unverified`; it asserts nothing about the opposite basis. The
existing contract already requires that distinction — `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §3.4 F-9
reserves `inconsistent` for contradictory evidence and N-2 makes `unverified` a normal state, not
a failure. Declining certification and disproving a hypothesis are different acts, and only the
first is warranted here.

**Two things that must not be mistaken for a reason to proceed anyway.** That conditions 1–3 are
now observed for three spans: §3.3 states that meeting *every* necessary condition still leaves
`vendor_basis` at `unverified` absent an agreed sufficiency rule, and V-13 pre-committed to that.
And that five of six comparisons match exactly: that is a real observation, and it remains five
agreements from one extract against a reference whose basis is recorded rather than certified.

---

## 6. What a bounded retained-data follow-up could narrow — and what it could not

**Nothing below is requested, prepared, scoped or authorized by this document.** M-1 to M-3 need
no newly acquired data, but each **requires a separately scoped user authorization for the
computation and its outputs** (see §8 and U6-R4). M-4 and M-5 are listed for completeness.

| # | Candidate | What it could **narrow** | What it could **not** establish |
|---|---|---|---|
| **M-1** | Examine `difference` and `ratio` against reference price level **within** single inter-event intervals, at stored precision, for both stocks | Whether either stored series is constant within an interval to within an explicitly stated rounding model. That would bear directly on which of §3.1's shapes organises each span, and would give H-mul its first test | It would **not** identify a mechanism or a cause. If BJ fits an additive relation and SH a multiplicative one, that does **not** show a single common mechanism — it may indicate **heterogeneous reference transformations**. If neither is constant under the stated rounding model, rounding-model misspecification, unidentified actions (Q-4) and other unmodelled relations all remain live. **No refutation of either model family should be promised**, and specifying a rounding/error model is itself work this task does not authorize |
| **M-2** | Read the E-1 neighbourhood — the ex-date pair and adjacent dates — at full stored precision | Whether the 0.01 is a boundary case of a rounding relation, or a discrete difference unlike its neighbours. That would narrow the candidate explanations | It would **not** identify the cause. In particular, revision 1's suggestion that a net-versus-gross convention could explain it is **withdrawn**: the QFII net figure noted in revision 1 comes from a **different announcement** (`2026-036`) and says nothing about `2025-036`. Nor is it established that "only rounding is compatible with an exact-match rule" |
| **M-3** | Compare within-interval shape stratified by reference source | Whether the §3.4 grouping observation survives a finer view of the same records | It **cannot break the source / instrument / span / price-range confound** — regrouping the same records leaves it intact (§3.4). Breaking it needs records this extract does not contain |
| **M-4** | A bound on what a publication-window, title-only search can miss (Q-4) | How far assumption A3 can be relied on | Not closable by more of the same query — G1 §4.5. Listed as a limit on interpretation, **not** as a demand that it be closed first |
| **M-5** | Reference coverage earlier than 2024-08-13 / 2024-06-21 (**G-5**) | It would add dates the present extract lacks | **Corrected from revision 1.** Earlier dates from *one extract* are **not automatically out-of-sample**, and they do **not** supply a second anchoring — a holdout needs a design that avoids selection and calibration leakage, and differently anchored snapshots are a different thing from more dates. Revision 1's "the only route" and "the only way to observe more than one anchoring" are **withdrawn**. It would in any case need a fresh read-only extract (G-6), an authorization that does not exist. **It is not requested here** |

**What would remain unidentifiable even after M-1 to M-3.** The vendor's own algorithm; whether
observed structure originates in the vendor or the reference, absent records that break §3.4's
confound; the completeness of the event set (Q-4); the legal effective date (Q-5); and the
behaviour of either series before the extract's earliest rows (Q-6). A clean M-1 result would
narrow the question — it would not certify a basis, and §3.3's no-automatic-upgrade rule would
still apply.

---

## 7. Evidence-to-claim table

Every row cites a retained artifact with its accepted hash. Paths are relative to the repository
root. **All were read read-only for this assessment and are unchanged.**

| Claim in this document | Artifact | SHA-256 | Location within it |
|---|---|---|---|
| `adapter_transform = none`, `vendor_basis = unverified`, all eligibility false | `claude methods/_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4/basis_records.json` | `c5b1bf3c2f660dcca84c1f3d44fba8252b1580d98fbce300d5412340d32448de` | `records.*.adapter_transform`; `eligibility.*` (`vendor_basis_unverified`); `view_eligibility` |
| Records digest; no `eligible=true` path; detection limits | `claude methods/_m2_smoke/basis_eval_.../PROVENANCE.json` | `a1b662a2cf67bb331202cec7e086887e59115994abd9828d4bcde7d4aafee514` | `records_sha256 = f9bef731…`; `eligibility_summary`; `detection_limits` |
| Evaluator / derivation rules and producer pin | same | same | `record_producer` (`p1.derivation.rev6`, `p1.evaluator.rev6`, `basis_record.py 0fda4f7e…`) |
| U-6's three premises; conditions 4 and 5 as written; `unverified` as a normal state (N-2) and `inconsistent` (F-9); V-13/V-14; §4 gaps; U-7's stock/index separation | `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` | `71e0dc52b8cf93281b1c09f501a62695915ef070a740dc378df2f1637a66007c` | §1; §2.1; §3.3 (L239–256); §3.4 (F-9, N-2); §3.5 V-13/V-14; §4 (L325–424); §5.0; U-6 (L556–578); U-7 (L580–598) |
| BJ difference 5 values / 5 runs; ratio 383 / 422; largest absolute ratio change `0.01433605608` in 500 pairs | `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/REPORT.md` | `8f7bf13637f0d418237a0f969a71ea25930380c3f8f10601aa611e69995edabd` | L87–91; difference runs L106–112 |
| SH difference 31 values / 233 runs; ratio 241 / 468; largest absolute ratio change `0.05547850208` in 537 pairs | same | same | L29–33 |
| Index ratio exactly 1, difference 0, basis `none`, 4 fetch times, 3 crossings — **bounded control only** | same | same | L54–60, L79 |
| Per-segment sources, fetch times, distinct-difference counts | same | same | L43–50 (SH), L100–104 (BJ), L70–75 (index) |
| One stored basis label across multiple sources | same | same | L27 (SH: `qfq`, three sources, 4 fetch times); L85 (BJ: `qfq`, two sources, 3 fetch times) |
| 470-row both-key segments; SH's 471-row source span splits | same | same | L118–154 |
| Stored ratio changes at the six ex-date pairs; `metadata_boundary = false` at each | `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/results.json` | `538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd` | `results.*.comparison.ratio_changes.records` (`change`, `difference_from`, `difference_to`, `metadata_boundary`); `.difference.runs`; `.segments` |
| Reference extract identity and decoder pins; adapter not replayed | `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/PROVENANCE.json` | `1a262d74110e30ef33e32d291038fc6c78a8c70204ccdad581017e9330575456` | `inputs.input_hashes` (`reference_extract.json ea021004…`); `reference_extract_content_sha256 3a599027…`; `hk_js_decode_sha256_pinned 39a599c9…`; `adapter_replayed: false` |
| G3 technically validated; 29/29 and 60/60 | `claude methods/M2B_G3_RATIO_ACCEPTANCE_CODEX.md` | `bb1b295999a5d3791481a35d354daa47ddab23cd7882087bd0f3fb1338ca2110` | "Validated files"; "Evidence and test results" |
| Six identified implementations; five exact difference matches; E-1 unresolved; G-e limits; G-g as the missing effective date; N-3 continuity statement; no causation | `claude methods/_m2_smoke/g1_corporate_actions_20260909/REPORT.md` | `77941f8c1344ebe20be93c8377e15e68188670c69021d7b03f3925f016e6617a` | §1 (mapping row 214, G-g, N-3 at §4.6); §2 (E-1…E-6); §4.4–§4.5; §5.2; §5.4; §5.5; §5.6 |
| Structured event/evidence index; gap ledger; coverage limits | `claude methods/_m2_smoke/g1_corporate_actions_20260909/events.json` | `7eb0e34d07b158bc8e46001d83faff4d6f62c0cc89b1212943c885b4214f366b` | `events_in_interval`; `identity.BJ920000.observation_classes_kept_separate`; `whole_interval_bonus_conversion_rights.coverage_limits`; `gap_ledger`; `bounded_observations.N-3` |
| Retained-notice hashes; retrieval scope; preservation | `claude methods/_m2_smoke/g1_corporate_actions_20260909/PROVENANCE.json` | `b2d7b5c782d4afd99b0cb03d61f6bf957b6b8ff3e4cad90772d576f7a127f3b1` | `retained_files`; `standing_position.remaining_open_gaps` |
| BJ 0.06 / ex 2024-09-30 | `…/official_notices/cninfo_832000_2024-068_2024H1_equity_distribution_implementation.pdf` | `6f22f7be812355c9520cde6647fdf1e56d2937ee24b8695f52e9085f7704f9df` | pp. 1–2 |
| BJ 0.08 / ex 2025-05-15 | `…/official_notices/cninfo_832000_2025-047_FY2024_equity_distribution_implementation.pdf` | `aba4cb40278dc6a01d13824cb70cda8342dc510223534f7e654ccb09fee642ca` | pp. 1–2 |
| BJ 0.070 / ex 2025-09-18 | `…/official_notices/bse_832000_2025-103_2025H1_equity_distribution_implementation.pdf` | `157dc6157c27ea99b19793a08c71a6464c1e68caa5119b0c558157bae3624ef8` | pp. 1–2 |
| BJ 0.08 / ex 2026-05-25 | `…/official_notices/cninfo_920000_2026-037_FY2025_equity_distribution_implementation.pdf` | `c8bcf19fd6ec333eeec5604c585ed96aba2262e22f42362d3dce5e0aa40971a2` | pp. 1–2 |
| SH 0.27 / ex 2025-07-10 — the discrepant comparison | `…/official_notices/cninfo_600011_2025-036_FY2024_equity_distribution_implementation.pdf` | `439ceb651b59383506e46055692a94756fd6a0b8fb136108d5dbe6c33f00e222` | p. 1 |
| SH 0.40 / ex 2026-07-03 | `…/official_notices/cninfo_600011_2026-036_FY2025_equity_distribution_implementation.pdf` | `269ed39f77af653f72c171be12068561b4f5ea0e5a934c90f8a37c0c4b8fdedb` | pp. 1–2 |
| SH 0.20 / ex 2024-07-11, in the 37-row segment | `…/official_notices/cninfo_600011_2024-034_FY2023_equity_distribution_implementation.pdf` | `ffe858d9423e6f75795ead65faad93788910bb24c1cf0eaab5589cca354570a2` | p. 1 |
| G1 technically validated; the U-6 premise is outdated; the recommended next decision | `claude methods/M2B_G1_CORPORATE_ACTIONS_CODEX_ACCEPTANCE.md` | `0558bc6a92b5e986a90ae4f9ff70bb42f222ab3f41d04db8593c2ccf45c7954d` | "Evidence and preservation"; "What is complete and what needs a separate decision" |
| The findings this revision answers | `claude methods/M2B_U6_READINESS_CODEX_REVIEW.md` | `5e3607fa999c021388995077deba2a235ac9e3fe88580e27cb7943afa91f9de0` | U6-R1 … U6-R4 |

**Two documents read for governance, cited for the rules they state and for nothing else.**
`AGENTS.md` (`cb6b114f1a88521873c632d12fea9e67579ab30b1b60864e9e7d5d5a522a85c3`) — degrade to
review-only where data evidence is unclear. `CODEX_CLAUDE_COLLABORATION.md`
(`f17d42e4d56713ade00eb31010494f76fdfecb8c68be2eb9f2ea9f86c6191992`) — §5's status vocabulary and
§7's rule that four data-source states must not substitute for one another. **Neither is cited as
a current runtime or source-acceptance finding**, and no such finding is asserted anywhere in this
document; their hashes appear only as read-time preservation evidence.

Supporting reviews consulted and unchanged: `M2B_P1_BASIS_CONTRACT_CODEX_REVIEW.md` `e9fcab23…`,
`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW.md` `418bba5f…`,
`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md` `f90de3d1…`,
`M2B_P1_HANDOFF_DOCS_CODEX_REVIEW.md` `ba99cba2…`, `M2B_G3_RATIO_CODEX_REVIEW.md` `91388af5…`,
`M2B_G3_RATIO_CODEX_REVIEW_R2.md` `6b9c01fe…`, `M2B_NEXT_STAGE_DECISION_MEMO.md` `536505ea…`.

---

## 8. Recommended decision, alternatives, consequences

### Recommended

**Withhold certification: leave `vendor_basis = unverified` and U-6 deferred as a rule.** Record
the *proposed* reclassification of U-6 from **evidence-blocked** to **evidence-available but
under-determined** — proposed, not adopted, with
`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` left unchanged. **Separately**, put to the user the question
of whether to authorize a bounded retained-artifact study covering M-1, M-2 and M-3.

Nothing else changes: no sufficiency rule, no threshold, no tolerance, no label change, no
eligibility branch, no gate wiring, no capture, no extract.

*Rationale.* The deferral's stated grounds (G-1, G-3) have been overtaken, so the *reason* for
deferring has changed even though the outcome has not. The decisive present obstacle is Q-3: the
reference basis is recorded rather than certified, and every candidate model assumes otherwise.
That is sufficient on its own to withhold certification, without inventing further prerequisites
or demanding exhaustive data. M-1 to M-3 could narrow the mechanism question using bytes already
accepted twice over, which is why they are worth putting to the user — and why they are put as a
*question*, not taken.

*What the authorization boundary actually is.* **Correcting revision 1 (U6-R4):** the candidate
study needs **no newly acquired data**, but it **does require a separately scoped authorization
for the computation and its outputs**. Retained data is not itself authorization to compute over
it. **No M-1/M-2/M-3 work is authorized by the present task, and none is requested by this
document** — this is a recommendation for a future user decision, not an approved operational
request.

### Alternatives

| | Alternative | Consequence |
|---|---|---|
| **A** | **Keep U-6 fully deferred; take no follow-up.** | Honest and fail-closed; `vendor_basis = unverified` stays an accurate recorded state (N-2). It leaves P1 blocked partly by premises now overtaken, and leaves a decision-relevant question unexamined. The proposal's own Option A caution — that this be chosen *deliberately rather than by inaction* — applies with more force than when written |
| **B** | **Adopt a sufficiency rule now on the exact matches.** | **Not defensible.** It would certify the vendor while the reference basis is uncertified (Q-3), rest on untested model shapes (§3.1–3.3), and need a tolerance for E-1 (Q-2). It would also breach §3.3's no-automatic-upgrade commitment and V-13 |
| **C** | **Recommended** — withhold certification, propose the reclassification, and put M-1/M-2/M-3 to the user as a separate authorization | Changes no label, gate or eligibility result. Costs a user decision plus effort if granted. Could narrow the mechanism question; would not certify a basis |
| **D** | **Seek a fresh read-only extract or new capture (M-5) now.** | Premature: both capture authorizations are consumed, G-6 authorization does not exist, and — corrected from revision 1 — more dates from one extract would not by themselves provide out-of-sample confirmation or a second anchoring. Sequencing it after C is preferable, and it is not requested here |

### If C is granted, what must remain true of the follow-on work

It reads retained artifacts only; it writes nothing into any accepted directory; it produces one
document and no output directory, script or dataset; it states its rounding/error assumptions
explicitly rather than tuning them; it defines no threshold, tolerance or cutoff; it changes no
label, gate or eligibility; it reports what remains unidentifiable; and it stops at
`proposed for review`. Should its findings bear on a rule, the rule remains a further, separately
scoped decision — not a consequence of the study.

---

## 9. What this document does not do, and preservation

* It **does not adopt U-6**, does not adopt the proposed reclassification, and does not propose a
  sufficiency rule or define any threshold, tolerance, sample-count cutoff or calibration.
* It **does not** assert a vendor basis, and it **does not** assert that any candidate basis is
  false. The outcome is **fail-closed**: certification is withheld and `vendor_basis` stays
  `unverified`. All eligibility results remain `false` with reason `vendor_basis_unverified`.
* It **does not** exclude `hfq`, exclude any adjustment convention, identify a mechanism, or
  demonstrate an anchor.
* It **does not** claim relative evidentiary weight or independence among the six identified
  comparisons; five exact difference matches and one discrepancy stand as observations.
* It **does not** treat any date or magnitude agreement as causal proof, and does not treat
  `source` / `updated_at` homogeneity as price-basis certification.
* It **does not** treat the index result as excluding stock-specific error, and does not use an
  index observation as evidence about a stock's basis.
* It **does not** assert any current data-source acceptance status, and cites no governance rule as
  such a finding.
* It **does not** dispatch, prepare, request or authorize M-1 … M-5, and **does not** treat the
  existence of retained data as authorization to compute over it. No capture, extract, SQLite open
  or network access is requested.
* It **does not** claim M2 completion, source-capability acceptance, P1 closure, training readiness
  or vendor-basis acceptance. Source capability remains **FAIL**; both capture authorizations
  remain **consumed**.

**Preservation.** This document is the only file written; **nothing else was modified.** Every
artifact in §7 was opened read-only. The accepted G1 delivery (46 files), the accepted G3 r2
delivery (5 files), the basis module and its tests, both `basis_eval_*` outputs, all reviewer
snapshots and review documents, the P1 proposal, and the goal and request documents remain
byte-for-byte unchanged, with the hashes recorded in §7 and in the handoff accompanying this
revision. No test, replay, ratio computation, fitting or calibration was run; no script or output
directory was created. Git was not staged, committed or pushed.

**Stop: `proposed for review`.**
