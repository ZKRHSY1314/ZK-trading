# P1 — the price-basis labeling and corroboration contract (design proposal)

> **Status: `proposed for review`.** Offline design proposal only, written from the current
> code, G7 and §6 of `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md`, and the retained evidence.
> **This proposal grants no operational authorization**, adopts nothing, implements nothing
> and assigns no basis label. **No capture, HTTP or plugin call, SQLite open, service
> action, token access, production mutation, dataset/strategy/knowledge change, pilot,
> training, source expansion, Git staging/commit/push or live trading.** No code, label,
> threshold, schema or test was changed; nothing was re-run, replayed or recomputed — in
> particular **no wider price ratios were computed** and **no corporate-action data was
> obtained**. Both capture authorizations remain **consumed**. Local and uncommitted.
>
> Date: 2026-09-08. **Revision 6** — A-R2 and A-R3 are closed; this revision closes the
> remaining **A-R1 revision-binding** gap (A.5.2) and clarifies what a recorded attempt
> proves (A.3.1). The reviewed U-1 … U-7 recommendations, the original R1–R3 closures and
> the corrected **B-3** are preserved unchanged. No policy is adopted and **no implementation is authorized**. **P1 remains
> open.** See the resolution table at the end. Companion documents, unchanged by this
> one: `M2B_NEXT_STAGE_DECISION_MEMO.md` (revision 3, technically validated) and §§6, 20–25
> of the request.

---

## 1. What "basis" means here — three different statements, currently collapsed

The label `adjustment_mode` is asked to carry three claims that have different evidence and
different owners. Keeping them apart is most of the work.

**(a) The vendor's price basis.** What Sina actually serves on
`…/hisdata_klc2/klc_kl.js` — whether those closes are as-traded, or already adjusted by
some convention of the vendor's. **The payload declares nothing.** No field in the decoded
rows names a basis; `hk_js_decode`'s branch O emits `date/open/high/low/close/volume/amount`
(plus `prevclose` per record when the record carries a `p` field), and branch D emits no
`amount` and no `prevclose`. Nothing in the retained evidence measures this claim.

**(b) What our adapter does to the series.** Code-derived and settled:
`stock_zh_a_sina.py` produces `hfq` only by fetching `hfq.js` and **multiplying** OHLC by
that factor, `qfq` only by fetching `qfq.js` and **dividing** by it, and `adjust=""`
returns the klc series untouched. This is a property of *our* transformation, not of the
vendor's data.

**(c) The label we store and gate on.** Three independent places treat it differently:

| Where | What it does today |
|---|---|
| `backend/app/data/akshare_provider.py:114-115` | stamps `adjustment_mode = "qfq" if adjust == "qfq" else "unknown"` and `volume_unit = "hand"` — **the label is inferred from the argument we passed**, not from evidence. This is the defect M2a's provenance module exists to close. |
| `_m2_pilot/provenance.py:136-181` (`derive`) | requires **two agreeing legs**: the observed URL path (`derive_adjustment`, `:88-97`) *and* a basis **declared by the response**. With a real Sina payload the second leg is absent, so `:172-174` forces `UNKNOWN` — "no decoded response basis to corroborate the observed path". |
| `_m1_closure/staging_gate.py:303-321` (`basis_gate`, G1b) | reads the **stored** `adjustment_mode` and compares it **as a string** with `--pricing-basis` (default `none`, `:716`); a blank is `UNKNOWN`, a mismatch is `FAIL`, and **mixed bases in one view are `FAIL`**. |

**The consequence, stated exactly.** Under the validated code every real Sina series is
labelled `unknown` **by construction**, so it cannot satisfy `--pricing-basis none` at the
staging gate. Relabelling those rows `none` to get past the gate is precisely what
`provenance.py`'s own header forbids: it "would defeat the very gate that exists to catch
it". **P1 is therefore an undecided labeling and corroboration contract — a design decision
that has not been taken — and not a data defect and not, on the present evidence, a
demonstrated need for new endpoints or a replacement reference.**

---

## 2. Options, and what the existing evidence actually supports

### 2.1 The evidence map

§6 of the request names the candidate P1 evidence. These are the retained results from
`revision_20260908T082833Z_r2abc_v2/`, with what each does **not** support:

| Evidence | Retained result | Supports | Does **not** support |
|---|---|---|---|
| **S1** — planned URL set equals the installed adapter constants | PASS ×3; the recorded sets are the klc history URL plus, for stocks, the auxiliary URL | that the plan addresses the raw endpoints and no factor endpoint | anything about the content served there |
| **B1** — no factor endpoint requested | PASS (run-level), measured `[]` | that **this run** fetched no `qfq.js` / `hfq.js` | that no factor exists upstream, or that the served series is unadjusted |
| **B2** — code-derived from the installed `stock_zh_a_sina.py` (`a3acc946…`) | PASS (run-level): hfq multiplies, qfq divides, `adjust=""` neither | that **our** code applies no transformation on the `adjust=""` path | anything about the vendor's basis — it is a statement about our transformations |
| **R1** — adapter replay with `adjust=""` | PASS ×3 (978 / 978 / 5,987 rows, dates validated) | that the stock replay actually took the untransformed branch | that the replayed series is unadjusted **at source** |
| **I2 / B4** — ratio against the anchored qfq reference | `I2` PASS ×3, ten ratios all `1.0`, `step_date: null`, sources recorded; `B4` ADVISORY ×3, `step_date: null` | identity corroboration: the live series is the same instrument as the cached one | a **flat** ratio is not evidence of vendor-unadjusted prices — see below |
| **B3** — `prevclose` markers | ADVISORY; `SH600011` 24 rows carry `prevclose`, 23 differ from the previous close | a decode-format observation | **excluded: B3 is not P1 evidence**, by §6 and by this proposal |

**Two things neither singly nor jointly prove a vendor basis.** `adjust=""` establishes only
that *we* applied nothing. A **flat** close ratio is what one expects anyway at the cached
`qfq` tail, because that tail is re-anchored at every refresh — so raw and qfq coincide
there whether or not the vendor adjusts. `B4`'s actual claim is the converse and is
conditional: *if* a step appeared, it would be **limited evidence** — not proof, because the
reference mixes fetch times — that the live series is unadjusted relative to the cached qfq
series. With `step_date: null` on all three symbols, the discriminating observation simply
did not occur in the compared segment.

**So the honest reach of the present evidence is (b), not (a):** *no adjustment was applied
by this pipeline, on a pinned code path, over an exactly-matching raw URL set.* Nothing
retained establishes the vendor's own basis.

### 2.2 The options

| | Option | What the label would assert | Cost | Risk |
|---|---|---|---|---|
| **A** | **Status quo** — keep requiring a response-declared basis | nothing new; every real series stays `unknown` | none | boundary 2 stays blocked indefinitely; the block is bookkeeping, not a data finding |
| **B** | **Code-path corroboration → reuse `none`** — replace the declared-basis leg with S1/B1 ∧ B2 ∧ R1 and stamp the existing value `none` | reads as "the data is unadjusted" — a claim about **(a)** | small; `derive` only | **overstates the evidence.** `none` already means a property of the data in `basis_gate` and the manifest; this is the relabelling `provenance.py` warns against |
| **C** | **Separate the two facts** — record *our transformation* and *the vendor's basis* as distinct values, corroborated by S1/B1 ∧ B2 ∧ R1, with the vendor basis explicitly unverified | exactly **(b)**, and says so | larger: new fields must be defined **and** their consumption decided at `basis_gate`, `--pricing-basis`, the manifest's `basis_expected` and the cache vocabulary | schema/migration surface; **and a new string that both sides declare would turn the gate green by string equality alone** — see §2.4 |
| **D** | **Empirical corroboration** — widen `I2`/`B4` to a span containing a corporate action and require a step | evidence bearing on **(a)** | medium; depends on evidence that may not exist (§4) | confounded by the reference's source and fetch-time boundaries; a flat result proves nothing either way |

### 2.3 Recommendation — not adopted, not implemented

**Recommended: C, corroborated by S1/B1 ∧ B2 ∧ R1, with D available later as a
strengthening leg — never as a prerequisite.** The reasoning is one sentence: the evidence
we have establishes what *we* did, so the label should say what *we* did, and the vendor's
basis should be carried as explicitly unverified rather than implied by a value that
already means something stronger.

**C closes only the derivation half of P1.** It removes the response-declared-basis
blocker and lets a *transformation* label be derived from evidence. It does **not** close
the vendor-basis half, and by itself it does **not** decide whether such a series may be
used. Those consumption decisions are set out in §2.4 and several are deliberately left
**unresolved**.

**B is not recommended** even though it is the cheapest: it would put a claim about the
vendor's data behind evidence about our code path, and the value `none` is exactly the one
the staging gate's G1b defect was about. **A is the correct default** if C's cost is judged
too high right now — indefinite `unknown` is honest and fail-closed, and it should be
chosen deliberately rather than by inaction. **D cannot be scheduled** until §4's gaps are
closed, and it can only ever raise or lower confidence in **(a)**; it is not the route to a
storable label on its own.

This section recommends. **It does not adopt, implement, or assign any label, and no
threshold or vocabulary is changed by it.**

### 2.4 Proposed representation, and what it would actually permit

**Proposed fields** (a shape to review, not a schema change):

| Field | Proposed values | Meaning |
|---|---|---|
| `adapter_transform` | `none` \| `qfq` \| `hfq` \| `unknown` | what **our** pipeline applied. `none` = no transformation applied by us; `unknown` = the fail-closed value |
| `vendor_basis` | `unverified` \| `unadjusted` \| `adjusted` \| `inconsistent` | the **vendor's** convention. `unverified` = not established (today's universal state for Sina klc); `inconsistent` = evidence disagrees across the span |
| `basis_evidence_ref` | `{run_id, adapter_source_sha256, routine_sha256, observed_urls, adjust_argument}` | the binding that makes the pair re-checkable (§3.2) |
| `adjustment_mode` | **unchanged** — `qfq` \| `none` \| `unknown` | the existing **gate-facing** field. The pair does not replace it; how the pair maps onto it is the policy question below |

**The anti-requirement, stated first.** `basis_gate` compares strings. If a new value were
written into both the store and `--pricing-basis`, the gate would go green **by string
equality with no new evidence about prices**. So: **a value whose meaning is "unverified"
must never be accepted by a gate as a certification of price basis.** Renaming does not
verify. Any adoption of C must decide the gate's *semantics*, not merely extend its
vocabulary.

**Consumer decision table** — what `(adapter_transform, vendor_basis)` permits:

| Transform fact | Vendor basis | Evidence validity (pins) | Audit storage | Closes P1? | Satisfies `--pricing-basis none`? | Boundary-2 eligibility |
|---|---|---|---|---|---|---|
| `none` | `unverified` | current | **Yes** — store both fields plus `basis_evidence_ref` | **Derivation half only.** The vendor-basis half stays open | **No** under the present meaning of `none`; maps to `adjustment_mode = unknown` → gate `FAIL`/`UNKNOWN` | **Undecided — U-1.** Not established by this pair alone |
| `none` | `unadjusted` | current | Yes | Would close both halves | Only if the project decides the pair maps to stored `none` — **U-2** | Would be eligible under U-1's stricter reading |
| `none` | `adjusted` | current | Yes | Closes it negatively — the series is not a raw basis | No | Not eligible on a raw-basis requirement |
| `none` | `inconsistent` | current | Yes | No | No | Not eligible; the span is not one basis |
| `qfq` / `hfq` | any | current | Yes | n/a — existing behaviour | `qfq` matches only a `qfq` declaration | existing rules |
| `unknown` | any | current | Yes (as a failure record) | No | No | No |
| any | any | **stale** (a pin no longer matches the installed code) | Yes | No | No — treated as `unknown` (§3.2) | No |

**Mixed states, by dimension.** Uniformity is not homogeneity:

* **Mixed `adapter_transform` in one view** → the existing `basis_gate` rule stands: **FAIL**.
* **Uniform `adapter_transform = none`, mixed `vendor_basis`** → the view is not one basis;
  whether that is FAIL or a recorded caveat is **U-3**.
* **Uniform `vendor_basis = unverified`** → this proves nothing about the vendor. Every row
  carrying the same "we did not establish it" is **uniformity of ignorance, not uniformity
  of convention**: the vendor may have changed convention anywhere inside the span and the
  label would look identical. A uniform `unverified` view must therefore never be read as
  basis-homogeneous.
* **Mixed `basis_evidence_ref` pins across a view** → the rows were derived under different
  code; whether such a view may be gated at all is **U-4**.

**Unresolved policy decisions — explicitly open, and not decided here:**

* **U-1** Does boundary 2 require a *verified* vendor basis, or does it accept
  `(none, unverified)` with a recorded caveat and a documented risk?
* **U-2** Does `--pricing-basis none` keep its present meaning (a property of the prices),
  get split into a transform gate plus a basis gate, or be redefined? Until this is
  decided, `(none, unverified)` **does not** satisfy it.
* **U-3** Is a view with mixed `vendor_basis` a FAIL or a caveat?
* **U-4** May a view mixing evidence pins be gated, or must pins be uniform?
* **U-5** Storage route: new columns on `daily_bar_cache`, a parallel audit table, or
  evidence-side only — each with a different migration review.
* **U-6** What evidence would be **sufficient** to assert `vendor_basis = unadjusted`
  (§3.3). This proposal deliberately does not define sufficiency.
* **U-7** Whether the index's `vendor_basis` carries the same meaning as a stock's, given
  that corporate-action adjustment does not arise for an index level in the same form.

**Until U-1 and U-2 are decided, adopting C changes what we can *record*, not what we may
*use*.** Saying "P1 is closed" on the strength of C alone would be wrong.

---

## 3. What the contract would have to specify

Proposed content for a future decision. **Nothing here is in force.**

### 3.1 Decision rules, with stock and index stated separately

* **D-1a (stock, transformation).** `adapter_transform = none` only when **all** hold: the
  observed URL set equals the expected raw set exactly (`derive_adjustment`, S1); the
  transport log contains **no** factor endpoint anywhere in the run (B1); the installed
  `stock_zh_a_sina.py` matches its pinned hash **and** all three code properties are
  readable from it (B2); and the series was produced on the **`adjust=""`** branch (R1).
* **D-1b (index, transformation).** The index interface takes **no `adjust` argument** and
  has no factor endpoints, so the `adjust=""` and B2 conditions are **not applicable** —
  they are neither waived nor silently assumed. `adapter_transform = none` for a benchmark
  requires: the observed URL set equals the expected index URL exactly (S1), the installed
  index adapter matches its pinned hash, and the recorded `adjust` argument is **absent**.
  An implementer must not reuse D-1a's conditions for an index or invent an exemption.
* **D-2 (vendor basis).** `vendor_basis` starts at `unverified` and is **never** raised by
  D-1a/D-1b, by `adjust=""`, by a flat ratio, or by uniformity across rows. Raising it
  requires the necessary conditions of §3.3 **and** an explicit sufficiency rule that this
  proposal does not define (**U-6**).
* **D-3 (identity is not basis).** `I2`/`I3` corroborate that the live and cached series are
  the same instrument and unit. They are identity evidence and must not be read as basis
  evidence.
* **D-4 (a response declaration is one leg, not a verdict).** If a future payload ever
  declares a basis, that declaration is **necessary-only** corroboration: it may support a
  `vendor_basis` assertion **together with** independent evidence, and **never upgrades the
  field on its own**. A declaration that contradicts other evidence forces `inconsistent`.
  This supersedes nothing in D-2; the two are consistent — D-2 forbids automatic upgrades,
  D-4 says a declaration is not an exception to that.
* **D-5 (exclusions).** `B3` is not P1 evidence in any form.
* **D-6 (no retroactive relabelling).** Rows already stored `unknown` are not rewritten by
  adopting this contract; whether they may later be **re-derived** is **U-4**/**U-5**.
* **D-7 (mixed views).** `basis_gate`'s rule — mixed bases in one view are FAIL — is
  preserved unchanged; any new value must be enumerated there rather than passing as a
  blank, and §2.4's mixed-state rows apply per dimension.

### 3.2 Evidence and version binding

A label is valid only for the exact code and inputs that produced it, and must carry:

* the adapter source path and **sha256** — `stock_zh_a_sina.py`, `a3acc946…` as recorded by
  B2 for stocks; the index adapter's equivalent for benchmarks;
* the pinned vendor routine hash (`hk_js_decode`, `39a599c9…`);
* the URL constants the plan derived, and the observed URL set actually requested;
* the `adjust` argument used, or its recorded absence for an index;
* the producing `run_id` and its evidence hash.

**If any pin changes, the label does not transfer.** It must be re-derived under the new
pins; a stored label whose pins no longer match the installed code is treated as `unknown`
at consumption time, whatever the stored string says. This is the discipline `EV4` already
applies to approved pins and `EV6` to capture-time classifications.

### 3.3 Necessary versus sufficient evidence for a vendor-basis assertion

**Necessary — all of these must hold before any assertion is even considered:**

1. a valid `adapter_transform` label under D-1a/D-1b, with current pins;
2. a comparison span homogeneous in **both** `source` **and** `updated_at` (§4);
3. an **independently established** corporate action inside that span, from a source
   outside this evidence set;
4. a reference whose own basis is known (the cache records `qfq` for stocks, `none` for the
   index);
5. an observed ratio behaviour consistent in **direction and magnitude** with that action.

**Sufficient — not defined here, deliberately.** No single observation suffices: **a ratio
step alone does not**, and **a response declaration alone does not**. Absent an agreed
sufficiency rule (**U-6**), `vendor_basis` stays `unverified` even when every necessary
condition is met. A contract that cannot yet say what would be enough must not permit an
automatic upgrade in the meantime.

### 3.4 Fail-closed outcomes, by field

Each condition yields the outcome shown **for that field**; no single shared `unknown`:

| # | Condition | `adapter_transform` | `vendor_basis` | `volume_unit` | Gate outcome |
|---|---|---|---|---|---|
| F-1 | missing/extra URL, redirect target, retry to another path | `unknown` | `unverified` | unchanged | not gateable |
| F-2 | any factor endpoint observed in the run | `unknown` | `unverified` | unchanged | not gateable |
| F-3 | adapter source hash absent or different from the pin | `unknown` | `unverified` | unchanged | not gateable |
| F-4 | a B2 property unreadable from the installed source (**stock only**) | `unknown` | `unverified` | unchanged | not gateable |
| F-5 | an `adjust` argument other than `""` on a series claiming `none` (**stock only**) | `unknown` | `unverified` | unchanged | not gateable |
| F-6 | required columns missing (existing `derive` behaviour, `:151-153`) | `unknown` | `unverified` | `unknown` | not gateable |
| F-7 | the two transformation legs disagree | `unknown` | `unverified` | unchanged | not gateable |
| F-8 | pins no longer match the installed code | stored value **ignored**, read as `unknown` | `unverified` | unchanged | not gateable |
| F-9 | contradictory vendor-basis evidence | unchanged | `inconsistent` | unchanged | not gateable on a single basis |

**Not fail-closed cases — normal states, listed so they are not confused with failures:**

* **N-1 (index unit).** A benchmark carries no `amount` series, so `volume_unit` is
  `unknown` **by construction** and the benchmark is excluded from unit gates. This is a
  property of the instrument, not a failure, and it does not affect `adapter_transform`.
* **N-2 (no discriminating observation).** With no such observation available,
  `vendor_basis` stays `unverified` and the **transformation label is retained** — the
  absence of vendor-basis evidence never invalidates the transformation fact.

### 3.5 A focused future validation matrix

To be built **only if** a contract is adopted; offline, synthetic fixtures, no capture.
Outcomes are given per field.

| # | Scenario | Expected |
|---|---|---|
| V-1 | **stock**: exact raw URL set, adapter hash matches, `adjust=""` | `adapter_transform=none`, `vendor_basis=unverified`; gate per U-1/U-2 |
| V-2 | a factor endpoint appears anywhere in the transport log | `adapter_transform=unknown` (F-2) |
| V-3 | adapter source hash differs from the pin | `adapter_transform=unknown` (F-3) |
| V-4 | one URL missing / one extra | `adapter_transform=unknown` (F-1) |
| V-5 | `adjust="qfq"` passed | existing `qfq` behaviour, unchanged |
| V-6 | required columns missing | `adapter_transform=unknown`, `volume_unit=unknown` (F-6) |
| V-7 | **index**: exact index URL, index adapter hash matches, no `adjust` argument recorded | `adapter_transform=none` via **D-1b**; `volume_unit=unknown` by N-1; `vendor_basis=unverified` (see U-7) |
| V-8 | **index**: D-1a's stock conditions applied to an index | contract violation — the implementation must use D-1b, not exempt the index |
| V-9 | two `adapter_transform` values stored in one view | `basis_gate` FAIL, unchanged |
| V-10 | uniform `adapter_transform=none`, mixed `vendor_basis` | per **U-3** — not silently collapsed |
| V-11 | uniform `vendor_basis=unverified` across a view | **not** treated as basis-homogeneous |
| V-12 | stored label whose pins no longer match the installed code | read as `unknown` (F-8) |
| V-13 | ratio step over a span homogeneous in source **and** `updated_at`, with an independently established action | necessary conditions met; **no automatic upgrade** — stays `unverified` pending U-6 |
| V-14 | ratio flat over such a span | no change either way; explicitly not evidence of unadjusted |
| V-15 | a future payload declares a basis, with no independent support | **no upgrade** (D-4) |
| V-16 | a declaration contradicting other evidence | `vendor_basis=inconsistent` (F-9) |
| V-17 | `B3` markers present or absent | no effect on any field |

### 3.6 Code locations a future implementation would touch

Identified, **not changed**:

| Location | Role |
|---|---|
| `_m2_pilot/provenance.py:136-181` (`derive`), `:88-97` (`derive_adjustment`), `:60-77` (`Provenance` / `require_basis`), `:37-38` (`UNKNOWN` / `RAW`) | where the declared-basis leg lives and where a code-path leg would replace it |
| `backend/app/data/akshare_provider.py:114-115` | the argument-derived stamp; any contract must not re-create it |
| `_m1_closure/staging_gate.py:303-321` (`basis_gate`), `:530`, `:568-578`, `:716` | the consumer: stored-vs-declared **string** comparison, mixed-basis FAIL, `--pricing-basis` default |
| `_m2_smoke/smoke_checks.py` — B1, B2 (run-level), I2/I3, B4 (advisory) | the evidence producers; a contract would consume them, not redefine them |
| `_m2_smoke/smoke_capture.py` — `REFERENCE_RULES` (`basis_expected = {'stock': 'qfq', 'benchmark': 'none'}`) | what the reference side is expected to be |
| storage vocabulary: `daily_bar_cache.adjustment_mode` (`qfq` / `none` / `unknown`) | any new field or value is a data-vocabulary change requiring its own migration review (**U-5**) |

M2a and M1 are **validated** and are named here only as consumers. Nothing in this proposal
reopens them.

---

## 4. What the retained reference extracts actually contain

Inspected offline: `evidence_20260908T021722Z/reference/reference_extract.json` and
`evidence_20260908T082833Z/reference/reference_extract.json`. **Both are byte-identical**
(`content_sha256` `3a599027…`). The extract was taken read-only under
`file:…?mode=ro` + `PRAGMA query_only=1` from `daily_bar_cache`, filtered
**`quality_status = 'ready'`**, the three symbols, and `trade_date between 2022-08-24 and
2026-09-04`. **No database was opened for this proposal**, and no ratios were computed.

| Symbol | Rows | Earliest … latest **in the extract** | Stored basis |
|---|---|---|---|
| `SH600011` | 538 | **2024-06-21** … 2026-09-04 | `qfq` |
| `SH000300` | 538 | **2024-06-19** … 2026-09-02 | `none` |
| `BJ920000` | 501 | **2024-08-13** … 2026-09-04 | `qfq` |

**What the absence of earlier rows does and does not show.** The extract contains no row
before each symbol's own earliest date above. Because the SQL filtered on
`quality_status = 'ready'` as well as symbol and date, that shows only: **at that extraction
time, under those filters, no earlier `ready` row for that symbol was returned.** It does
**not** show that the cache holds no earlier data — rows in another `quality_status`, or
otherwise outside the filter, would not appear — and it does **not** show that a different
reference source is required. Establishing what the cache actually holds would need a fresh
read-only extract, which is neither performed nor requested here.

**A wider comparison is possible against the existing extract — but it is bounded and
confounded.** `I2`/`B4` compare only the ten most recent common sessions
(`thresholds.identity_sessions = 10`), while the extract holds **538** rows for `SH600011`.
That is a real, unused margin, available offline. Two distinct homogeneity questions apply,
and they give different answers.

**Same `source` only:**

| Symbol | Source span | Rows |
|---|---|---|
| `SH600011` | `akshare.stock_zh_a_hist` 2024-06-21 … 2024-08-12 | 37 |
| | `akshare.stock_zh_a_daily` 2024-08-13 … **2026-07-24** | **471** |
| | `tonghuasun.local.quotes.candle` 2026-07-27 … 2026-09-04 | 30 |
| `BJ920000` | `tonghuasun.local.quotes.candle` 2024-08-13 … 2026-07-23 | 470 |
| | `akshare.stock_zh_a_daily` 2026-07-24 only | 1 |
| | `tonghuasun.local.quotes.candle` 2026-07-27 … 2026-09-04 | 30 |
| `SH000300` | `akshare.stock_zh_index_daily` throughout | 538 |

**Same `source` *and* `updated_at`** — contiguous segments, which is the stricter and more
relevant grouping:

| Symbol | Segment | Rows |
|---|---|---|
| `SH600011` | `stock_zh_a_hist` / `2026-07-15T14:16:19`, 2024-06-21 … 2024-08-12 | 37 |
| | `stock_zh_a_daily` / `2026-09-03T17:21:19`, 2024-08-13 … **2026-07-23** | **470** |
| | `stock_zh_a_daily` / `2026-09-04T15:09:56`, **2026-07-24 only** | **1** |
| | `tonghuasun…candle` / `2026-09-04T18:06:09`, 2026-07-27 … 2026-09-04 | 30 |
| `BJ920000` | `tonghuasun…candle` / `2026-09-03T19:39:41`, 2024-08-13 … 2026-07-23 | **470** |
| | `stock_zh_a_daily` / `2026-09-04T15:02:08`, **2026-07-24 only** | 1 |
| | `tonghuasun…candle` / `2026-09-04T18:06:31`, 2026-07-27 … 2026-09-04 | 30 |
| `SH000300` | `stock_zh_index_daily` / `2026-07-12T10:38:21`, 2024-06-19 … 2024-06-20 | 2 |
| | `stock_zh_index_daily` / `2026-07-15T15:18:22`, 2024-06-21 | 1 |
| | `stock_zh_index_daily` / `2026-07-15T19:38:23`, 2024-06-24 … 2026-06-09 | **475** |
| | `stock_zh_index_daily` / `2026-09-03T11:41:45`, 2026-06-10 … 2026-09-02 | 60 |

**So `SH600011`'s 471-row same-source span is not fetch-time homogeneous**: it splits into
**470 rows (2024-08-13 … 2026-07-23, updated `2026-09-03T17:21:19`)** plus **one row dated
2026-07-24 updated `2026-09-04T15:09:56`**. **2026-07-24 is therefore an `updated_at`
boundary for `SH600011` as well**, not only the date of `BJ920000`'s differently-sourced
row. That `BJ920000` row is a **record from a different source with a different
`updated_at`**; the stored fields say nothing about how it was produced, and no claim that
it was interpolated is made or supported.

**The largest span sharing both `source` and `updated_at` is 470 rows
(2024-08-13 … 2026-07-23) for each stock**, and 475 rows (2024-06-24 … 2026-06-09) for the
index. Grouping this way removes exactly **two recorded metadata differences**. It does
**not** establish that a segment is homogeneous in price convention, nor that any corporate
action occurs inside it. `SH000300` cannot discriminate anything about stock adjustment in
any case — both sides are basis `none`.

**Whether any corporate action falls inside these spans is not established, and this
proposal does not assume one.** The only pointer in the retained record is `B3`'s marker
list, which is (i) **not P1 evidence**, and (ii) **truncated**: `measured` keeps only
`mismatch_dates[:10]`, all between 2002-06-20 and 2011-06-23, so the retained evidence
cannot say whether any of the 24 markers lies inside the available overlap.

### Evidence gaps, precisely

| # | Gap | Closable without new data? |
|---|---|---|
| G-1 | No corporate-action date is established inside any available span | **No** — needs an independent corporate-action source, out of scope here |
| G-2 | `B3`'s marker list is retained only to the first ten entries (2002–2011) | Partly — recomputable offline from retained bytes, but still not P1 evidence |
| G-3 | The ratio series over the wider overlap has never been computed; only the 10-session tail exists | **Yes** — a bounded offline computation over retained artifacts. **Not performed in this round or the previous one.** |
| G-4 | 2024-08-13, **2026-07-24** and 2026-07-27 are `source` and/or `updated_at` boundaries for the stocks; a step at or near them is confounded | Partly — restricting to a segment homogeneous in both keys (≤ 470 rows) avoids these two recorded differences, at the cost of span, and proves nothing further about convention |
| G-5 | The extract returns no `ready` row before 2024-06-21 (`SH600011`), 2024-06-19 (`SH000300`) or 2024-08-13 (`BJ920000`), so no comparison is possible there **from this extract** | **No, from retained material.** Whether the cache holds earlier data at all is **not determined** — a fresh read-only extract would be needed, and none is requested |
| G-6 | A fresh or wider extract would need a read-only `trading_local.sqlite3` open | **No** — not authorized now, and not requested here |

**What this changes about the earlier recommendation.** The decision memo suggested the
discriminating span "may be obtainable from the existing reference". This inspection
qualifies that: an unused margin genuinely exists — up to **470 rows** per stock sharing
both `source` and `updated_at` — but whether it contains a discriminating event is
**unknown**, G-1 is not closable offline, and G-5 is a limit of *this extract*, not an
established property of the cache. The memo is not amended by this proposal; this is the
finding a P1 decision should be taken against.

---

## 5. Decision-ready recommendations for U-1 … U-7

Each item below gives **one** recommended choice, its rationale, the consumers it touches,
and what would have to exist before it could be implemented. **These are recommendations
for a decision, not decisions.** Nothing here is adopted, and **P1 stays open**.

Defaults throughout are deliberately conservative: preserve the present meaning of price
basis, refuse to let an unverified or inconsistent vendor basis qualify for raw-basis use,
preserve every mixed-basis failure, never let mixed or stale producer pins certify a view,
prefer an evidence-side representation over a production migration, keep index semantics
separate from stock corporate-action evidence, and invent no thresholds.

### 5.0 Two kinds of question

| Item | Kind | Decidable now? |
|---|---|---|
| U-1, U-2, U-3, U-4, U-5 | **Policy** — a choice about risk, semantics or engineering route | **Yes**, on the evidence already in hand |
| U-6 | **Evidence-blocked** — no available observation can settle it | **No.** See §4's G-1, G-3, G-5 |
| U-7 | **Policy** semantics, wrapping an **evidence-blocked** sub-question | The semantics: yes. Any index basis *assertion*: no |

One principle runs through U-3, U-4 and U-6 and is stated once here: **record once, evaluate
at use.** A stored label is a **historical audit fact** about what a particular code version
derived from particular inputs; it is never rewritten, deleted or back-dated. **Current
eligibility is a separate question**, recomputed at the moment of consumption against the
installed pins, and it defaults to *not eligible*. Preserving the fact and refusing the use
are not in conflict.

### U-1 — Does boundary 2 require a *verified* vendor basis?

**Recommended: yes.** `(adapter_transform = none, vendor_basis = unverified)` **does not
qualify** a series for any boundary-2 use that depends on the price basis. An `inconsistent`
vendor basis likewise does not qualify. The pair may still be **stored and reported as an
audit fact**, and it does not block uses that make no basis claim — identity, coverage,
calendar and unit work.

*Rationale.* The evidence establishes what **we** did, not what the vendor serves. A pilot
consuming these prices as "raw" would be asserting a property nothing has measured. This is
not a claim that the vendor adjusts — `unverified` is a statement about our knowledge — and
the decision is reversible the moment U-6 is answered.

*Affected consumers.* The boundary-2 request (to be drafted), the manifest's
`basis_expected`, `staging_gate.basis_gate` (unchanged by this recommendation), and any
feature or label that consumes prices as a basis-bearing quantity.

*Implementation prerequisites.* None technical — it is a decision to record. If adopted,
the boundary-2 request must state the requirement explicitly, so that it is not re-litigated
implicitly later by a view that happens to pass a string comparison.

### U-2 — What happens to `--pricing-basis none`?

**Recommended: keep its present meaning, unchanged.** `none` continues to mean a property
of the prices. Do **not** redefine it, do **not** add an "unverified" value to the gate's
vocabulary, and do **not** split it into a transform gate plus a basis gate in this round.
The transformation fact is recorded **beside** the gate, never inside it.

*Rationale.* `basis_gate` compares strings, so extending its vocabulary is the one change
that could turn it green with no new evidence about prices — the anti-requirement in §2.4.
Preserving the meaning preserves G1b's protection. A later split remains possible, but it
should **follow** U-6 rather than precede it: a gate that distinguishes transform from basis
is only useful once a basis can actually be asserted.

*Affected consumers.* `_m1_closure/staging_gate.py:303-321`, `:530`, `:568-578`, `:716`; the
M1 staging test suite; any runbook or script passing `--pricing-basis`.

*Implementation prerequisites.* None — this is a decision **not** to change code. A future
split would need its own review and updated M1 tests, and M1 is validated: reopening it
requires separate authorization.

### U-3 — A view with mixed `vendor_basis`

**Recommended: FAIL**, mirroring the existing mixed-`adjustment_mode` rule rather than
introducing a softer path. A view that mixes bases cannot be described by one declared
basis.

*Note on the uniform case.* A view uniformly `unverified` is **not** a mixed-basis failure —
it is uniform. It is also **not eligible** under U-1, because uniformity of an unverified
label is uniformity of ignorance, not of convention (§2.4). The two rules are independent
and both apply.

*Rationale.* `basis_gate` already rejects mixed stored bases for exactly this reason. One
consistent rule is also easier to reason about than a caveat that a downstream reader must
notice and act on.

*Affected consumers.* `basis_gate`; the eligibility evaluator proposed in §5.8; boundary-2
view construction.

*Implementation prerequisites.* `vendor_basis` must be recorded per row before such a check
can be computed at all — that is the evidence-side scope of U-5. Until then the rule is
declaratory.

### U-4 — Mixed or stale evidence pins

**Recommended: require uniform, current pins for eligibility; never certify on mixed or
stale pins.** A row whose `basis_evidence_ref` no longer matches the installed code keeps
its stored value as a historical fact and is read as `unknown` for any current decision
(F-8). A view mixing pins is **not eligible**, whatever its stored strings say.
Re-derivation produces a **new** record; it never amends an old one.

*Rationale.* A label is only as good as the code that produced it — the discipline `EV4`
applies to approved pins and `EV6` to capture-time classifications. Recording the fact
preserves the audit trail; evaluating eligibility at use prevents a stale fact from silently
certifying today's view. This is the "record once, evaluate at use" principle above, and it
is what lets D-6 forbid retroactive relabelling without freezing the project.

*Affected consumers.* The eligibility evaluator; `basis_gate` if the mapping is ever wired;
any boundary-2 view spanning more than one producer version.

*Implementation prerequisites.* `basis_evidence_ref` recorded per row (U-5); a pin
comparison helper; and a written rule that re-derivation appends rather than edits.

### U-5 — Where the representation lives

**Recommended: evidence-side only, for the initial design.** Compute and record
`adapter_transform`, `vendor_basis` and `basis_evidence_ref` in the smoke's **own offline
evidence** — the checker's output and the revision-side provenance. **No `daily_bar_cache`
columns, no production migration, no gate wiring** in this phase.

*Rationale.* It is reversible, touches no production data, needs no migration review, and
produces exactly the artifact a later decision would need in order to be taken on evidence
rather than on argument. A production representation should **follow** the policy decisions,
not lead them.

*Affected consumers.* `_m2_smoke/smoke_checks.py` as the producer, and the revision
directories' provenance records. **Nothing under `backend/` or `_m1_closure/`.**

*Implementation prerequisites.* Agreement that the record is **evidence, not a label with
authority**, and the derivation rules of §3.1 and the per-field outcomes of §3.4 fixed
first. A phase-2 production representation is explicitly **out of scope** and would need its
own migration review (blocker B-4).

### U-6 — What would be *sufficient* to assert `vendor_basis = unadjusted`

**Recommended: keep deferred. Define no sufficiency rule, and invent no threshold,
tolerance, session count or step-magnitude test.**

*Rationale.* This is **evidence-blocked, not policy-blocked.** §4 records why: **G-1** no
corporate action is established inside any available span; **G-3** the wider ratio series has
never been computed; **G-5** no comparison is possible before each symbol's earliest date in
the extract. A rule written now would be calibrated against evidence nobody has seen, and it
would read as a contract while being an assumption. Meanwhile §3.3's necessary conditions
stand and there is **no automatic upgrade** — neither from a ratio step nor from a response
declaration.

*Affected consumers.* Everything downstream of a vendor-basis assertion: U-1's eligibility,
boundary 2, and any raw-basis feature.

*Prerequisites to reopen it* — each a separate decision or authorization, **none requested
here**: an independently sourced corporate-action date inside a span homogeneous in both
`source` and `updated_at`; the bounded offline ratio computation over that span using
retained artifacts; and, if that span proves unusable, a fresh read-only extract.

*Meanwhile.* `vendor_basis` stays `unverified`, which is an honest recorded state and not a
failure (N-2).

### U-7 — Does the index's `vendor_basis` mean what a stock's means?

**Recommended: no — treat the index separately, in both directions.** Record
`adapter_transform` for a benchmark under **D-1b**, and keep `vendor_basis` a **separate
question with its own, currently undefined, meaning**: do not assert it, do not infer it
from the stock rule, and **never** use an index observation as evidence about a stock's
basis or a stock observation as evidence about an index.

*Rationale.* An index level is not adjusted for corporate actions the way a stock price is,
and §4 records that the cached index reference is basis `none` on both sides — so the ratio
test has no discriminating power there at all. Reusing the stock semantics would create a
field whose meaning nobody has defined.

*Affected consumers.* D-1b and V-7/V-8; the manifest's `basis_expected`
(`benchmark: none`); any benchmark-consuming feature.

*Implementation prerequisites.* A short written definition of what a benchmark's basis field
**means**, before any value other than `unverified` is recorded. That definition is deferred
alongside U-6.

### 5.8 Minimal proposed implementation scope

If — and only if — U-1 … U-5 and U-7 are decided as recommended, the smallest coherent
implementation is:

1. **Fix the rules as text**: §3.1 (D-1a stock / D-1b index), §3.2 binding, §3.4 per-field
   fail-closed outcomes. No code yet.
2. **An evidence-side record only**: `adapter_transform`, `vendor_basis` (which is
   `unverified` for every series today) and `basis_evidence_ref`, computed from the S1, B1,
   B2 and R1 evidence the offline checker **already produces**, written into its own output.
   No new vocabulary in any gate, no new threshold.
3. **An eligibility evaluator**: given such a record plus the installed pins, return
   *eligible* / *not eligible, with the reason* — defaulting to **not eligible**, and
   applying U-1, U-3 and U-4.
4. **Offline synthetic tests** for the §3.5 matrix, including the index rows V-7/V-8 and the
   no-upgrade rows V-13/V-15/V-16.

**Explicitly out of scope:** any `daily_bar_cache` column or migration; any change to
`basis_gate`, `--pricing-basis`, `provenance.derive` or `akshare_provider`; relabelling any
stored row; any vendor-basis assertion; any threshold, tolerance or session count.

### 5.9 Explicit blockers

| # | Blocker | Consequence |
|---|---|---|
| B-1 | U-6's evidence gaps G-1 / G-3 / G-5 | no `vendor_basis = unadjusted` assertion is possible; sufficiency stays undefined |
| B-2 | **M2b source capability remains FAIL**, and no same-version live capture exists | nothing reaches boundary 2 regardless of how P1 is decided |
| B-3 | A fresh or wider read-only extract needs authorization (G-6) | **It blocks only fresh extraction — not every investigation.** Three lines of work are separately scoped and must not be merged: **(i) external corporate-action evidence**, which lies outside this project's data entirely and is what U-6's necessary condition 3 requires; **(ii) an offline ratio computation over *retained* artifacts** (G-3), which needs **no** new extraction or authorization beyond a decision to spend the effort; **(iii) a fresh read-only extract** (G-5/G-6), needed only if the retained extract's span proves unusable, and which does require authorization. **None of the three is performed, prepared or requested here.** |
| B-4 | Any production-side representation needs a migration review | U-5 phase 2 cannot be folded into the initial scope |
| B-5 | The historical `EV6` failures stand and are cleared by nothing | the two retained captures can never yield a capability PASS |
| B-6 | U-1 and U-2 are decisions for the user/reviewer, not for this document | until they are recorded, **no gate may consume the new fields** |
| B-7 | M1 and M2a are validated | touching `staging_gate` or `provenance` reopens validated scope and needs separate authorization |

**All of §5 is proposed, not adopted. P1 remains open.**

---

## Appendix A. Implementation specification (proposed)

Compact spec for the §5.8 scope, written so a future implementer needs no further
interpretation. **Nothing here is implemented, adopted or authorized**, and it stops
short of writing any code.

### A.1 Exact input artifacts

All read-only, all already retained. No database, network or new extraction.

| Path | Supplies |
|---|---|
| `evidence_<run_id>/capture_manifest.json` | `run_id`; `environment` (capture-time third-party pins); one record per request (`index`, `job`, `symbol`, `kind`, `requested_url`, `served_url`, `status`, `outcome`, `payload_state`, `encoding`, `body_sha256`, `text_sha256`, `raw_file`); `attempts`; `deadline`; `reference_extract_sha256` |
| `evidence_<run_id>/raw/*.bin` | the response bodies (referenced by hash; not re-decoded by this scope) |
| `evidence_<run_id>/reference/reference_extract.json` | `rules` (`basis_expected`, `filters`, `thresholds`, `corroboration_span_rule`), `rows`, `content_sha256` |
| `<revision>/checks.json` | `deterministic.checks` (S1, B1, B2, I2/I3, R1, R1urls …), `deterministic.adapter_basis_facts`, `deterministic.decoded_summary`, `deterministic.verdicts`, `deterministic_sha256`; and the **volatile** `run_meta` (`run_id`, `checked_at_utc`) |
| `<revision>/PROVENANCE.json` | `producer_implementation` (5 hashes), `input_hashes` (7 entries), `parent_evidence`, `supersedes_revision`, `revised_offline_result` |

### A.2 What is actually recorded — and what is not

Four identifier classes, never to be conflated:

| Class | Where it lives | Example |
|---|---|---|
| **Producer pins** — *our* code that derived the record | `PROVENANCE.producer_implementation` (5 entries) | `smoke_checks.py` `4b062a55…` |
| **Run IDs** — which capture, which offline evaluation | `capture_manifest.run_id`, `checks.json.run_meta.run_id`, and the revision directory name | `20260908T082833Z`; `revision_20260908T082833Z_r2abc_v2` |
| **Input hashes** — the bytes evaluated | `PROVENANCE.input_hashes` (7); per request `body_sha256` / `text_sha256` | `raw/02_sh600011_getAmountBySymbol.bin` |
| **Third-party pins** — the vendor routine and adapter environment | `capture_manifest.environment` | `akshare_version` `1.18.64`; `hk_js_decode_sha256` `39a599c9…` |

**Capture-time (historical, in the manifest):** `akshare_version`; the three URL templates
`stock_hist` / `stock_amount` / `index_hist`; `index_params` (`d = 2020_2_4`);
`hk_js_decode_sha256` (**full** 64-hex in the manifest — `EV4`'s `measured` shows only the
first 16, so the manifest is the source for the full value); plus `git`, `tls` and
`process_inventory_size`.

**Check-time observations, NOT capture-time pins.**
`deterministic.adapter_basis_facts.source_sha256` = `a3acc946…` for `stock_zh_a_sina.py` is
read from the **installed file when the checks ran** (`run_meta.checked_at_utc`, e.g.
`2026-09-08T09:22:59Z`), not when the capture happened. A record must carry it as
`observed_at: <checked_at_utc>` under the producer pins that observed it. **It must never
be written into a capture-time pin field or back-dated**, and the capture manifest must
never be edited to add it.

**Not recorded anywhere today — do not fabricate:**

* **The index adapter's source hash.** `index_stock_zh` appears nowhere in `checks.json`;
  `adapter_basis_facts` covers only the stock adapter. **Consequence:** under D-1b an index
  record derived from the retained captures cannot reach `adapter_transform = none` — it is
  `unknown` for want of a recorded pin. A future derivation may compute the index hash as a
  **new check-time observation** going forward; it can never be supplied retrospectively.
* **The replay's `adjust` argument — no structured field exists.** `adjust=""` appears in
  `checks.json` only inside **narrative text**: `B2.detail` ("the `adjust=\"\"` branch
  applies neither") and `B4`'s prose. (An earlier draft said it occurred only in `B4`'s
  prose; that was inaccurate — `B2.detail` carries it too. The substantive point is
  unchanged and does not rest on a full-text search.) There is **no structured
  invocation-argument field** anywhere: the value is an invocation fact of the checker's own
  source, **inferable from the producer pin `smoke_checks.py 4b062a55…`**, and a record may
  state it only as "implied by producer pin X", never as an observed field.
* Any per-row provenance: the artifacts carry per-**series** facts only.

### A.3 Field mappings

| Proposed field | Derived from | Stock | Index |
|---|---|---|---|
| `adapter_transform` | `S1` (per symbol) ∧ `B1` (run) ∧ `B2` (run) ∧ `R1` (per symbol) | all four required (**D-1a**) | `S1` + a recorded index-adapter pin + absence of an `adjust` argument (**D-1b**); `B2` and `adjust=""` are **not applicable**, not waived |
| `vendor_basis` | no input maps to any value other than `unverified` | `unverified` | `unverified`, with U-7's separate meaning |
| `basis_evidence_ref.producer_pins` | `PROVENANCE.producer_implementation` | same | same |
| `basis_evidence_ref.run_ids` | `capture_manifest.run_id` + revision directory name | same | same |
| `basis_evidence_ref.input_hashes` | `PROVENANCE.input_hashes`, plus that symbol's `body_sha256` | 2 bodies | 1 body |
| `basis_evidence_ref.capture_pins` | `capture_manifest.environment` | same | same |
| `basis_evidence_ref.observed_at_check_time` | `adapter_basis_facts` + `run_meta.checked_at_utc` | stock adapter hash | **absent today** (see A.2) |
| `url_evidence.planned` | `S1.measured` per symbol — see A.3.1 | 2 URLs | 1 URL |
| `url_evidence.evidenced_access` | attempt-backed only — see A.3.1 | per request | per request |
| `url_evidence.replay_requested` | `R1urls.measured` (offline replay) — see A.3.1 | run-wide | run-wide |
| `series_coverage` | `R1.measured` (`rows`, `first_date`, `last_date`, `dates_returned`) and `decoded_summary[<index>]` (`js_variable`, `branch`, `row_count`) | 978 rows, window-bounded | 5,987 rows, no date arguments |

#### A.3.1 Three URL classes, never merged into one `observed_urls`

An earlier draft folded planned and replay URLs into a single `observed_urls` field. That
would let a consumer read evidence from the wrong stage. They are three distinct facts:

| Class | Exact source | What it means | What it does **not** mean |
|---|---|---|---|
| **planned / expected** | `S1.measured` — built in `smoke_checks.py:970-980` from the `requested_url` of **every** manifest request record, compared with `cap.expected_requests(...)` | the plan addressed exactly the expected adapter URLs | **not** that any request was issued. A **skipped** record still carries a `requested_url` |
| **evidenced access** | a request record with `attempt_count > 0` and non-empty `attempt_positions`, cross-referenced to entries in `manifest.attempts` (`request_index`, `attempt_no`, `status`, `error`, `transport_outcome`), plus `served_url` | an attempt against this URL was **initiated and recorded**, that many times | **not** that the endpoint was reachable, and **not** that any HTTP response arrived — see below |
| **offline replay requested** | `R1urls.measured` — `replay["_requested_urls"]` (`smoke_checks.py:1460-1465`) | the installed adapter, replayed offline against retained bodies, asked for these URLs | **not** a live capture log. Its PASS only excludes **uncaptured** URLs; it asserts no completeness, and a replay may cover a subset of jobs |

**The retained evidence shows why this matters.** In run `20260908T021722Z` **all five**
records carry a `requested_url`, but only requests **1** and **3** have `attempt_count: 1`
with attempt entries; requests **2** (`job_local`), **4** and **5** (`run_global`) were
**skipped and never issued**. A single merged field would have recorded five "observed"
URLs for a run that reached two. The complete five-request run
`20260908T082833Z` happens to make all three classes coincide; that coincidence must not be
used to define the general mapping.

**What a recorded attempt does and does not prove.** An entry in `manifest.attempts` is
evidence that the transport **started and recorded an attempt**. It is **not** evidence that
the endpoint was reachable, nor that an HTTP response was received: an attempt with
`status: null` and an `error` — a timeout, a TLS failure, a connection error — is a fully
recorded attempt with **no response at all**. Response receipt is evidenced only by a
**non-null `status`** on that attempt, and even a `200` says nothing about whether the body
is usable; that is `payload_state`'s question. A record must therefore distinguish
*attempted*, *responded* and *usable*, and never collapse them.

**Completeness rules.**

* A skipped request is recorded as **planned, not accessed**, with its `skip_scope`
  (`job_local` / `run_global`); it is never counted as evidenced access.
* A positive `adapter_transform` derivation requires an attempt carrying a **recorded
  response status**, not merely the existence of an attempt entry.
* Evidenced access is per **request**, derived from attempts — never inferred from `S1`.
* Replay coverage is recorded as the **set of jobs actually replayed**; a job absent from
  the replay is `replay_not_evaluated`, not a failure and not a success.
* A positive `adapter_transform` derivation (D-1a/D-1b) requires the symbol's history
  request to be **evidenced as accessed** *and* its replay to have been evaluated — **not
  merely `S1` PASS and `R1urls` PASS**, neither of which establishes issuance or
  completeness.

### A.4 Granularity, coverage, and missing evidence

**Granularity.** One record per **(capture `run_id`, revision id, job)** — three records per
revision, keyed by the job name (`sh600011`, `sh000300`, `bj920000`). **Never per row.**
`decoded_summary` is keyed by request index (`"1"`, `"3"`, `"4"` — history bodies only), so
the mapping index → job comes from the manifest's request records.

**Coverage.** Symbols: exactly the three jobs; a record is emitted for a job **only** if its
history request exists in the manifest. Dates: the series' own `first_date` … `last_date`
from `R1`; the declared window `2022-08-24 … 2026-09-04` applies to the **stock** replay
only and is not imposed on the index (§3.1 D-1b).

**Missing evidence — outcomes per field, never inferred:**

| Missing input | `adapter_transform` | `vendor_basis` | Note |
|---|---|---|---|
| `S1` absent or mismatched for the symbol | `unknown` (F-1) | `unverified` | |
| `B1` shows any factor endpoint | `unknown` (F-2) | `unverified` | |
| `B2` absent / a property unreadable (**stock**) | `unknown` (F-4) | `unverified` | |
| `B2` absent for an **index** | **not a failure** | `unverified` | D-1b: B2 is not applicable (N-1 pattern) |
| no recorded index-adapter pin (**today's state**) | `unknown` | `unverified` | A.2 — cannot be supplied retrospectively |
| `R1` not evaluated for the symbol | `unknown` | `unverified` | absence of a replay is not a transform fact |
| `capture_manifest.environment` pin missing | `unknown` (F-3 pattern) | `unverified` | never substitute a current value |
| producer pins absent from `PROVENANCE.json` | record **not emitted** | — | an unattributable record is worse than none |

### A.5 The new module's own version, mandatory pre-write verification, and output

#### A.5.1 Two version namespaces, kept apart

The five `_m2_smoke` hashes describe the **upstream** code that produced `checks.json`.
They say nothing about the module that derives these new records and runs the evaluator, so
a change to *its* rules would leave every pin identical while the meaning of the output
changed. The output therefore records both:

| Field | Content |
|---|---|
| `upstream_producer_pins` | the five hashes from the consumed `PROVENANCE.producer_implementation`, **recomputed** from the installed files at derivation time and reported as matched / mismatched |
| `record_producer.module_sha256` | `basis_record.py`'s own sha256 |
| `record_producer.record_schema_version` | e.g. `m2b.basis_record.v1` — the output's shape |
| `record_producer.derivation_rules_version` | which numbered rule set (§3.1 D-1a/D-1b, §3.4) produced the fields |
| `record_producer.evaluator_rules_version` | which §A.6 rule set produced the eligibility answer |
| `consumed_artifacts` | the **recomputed** sha256 of every file actually read: `<revision>/checks.json`, `<revision>/PROVENANCE.json`, `evidence_<run_id>/capture_manifest.json`, and each referenced raw body |
| `source_identity` | `capture_run_id`, `revision_name`, `parent_evidence`, and the consumed `deterministic_sha256` |

Records carrying different `derivation_rules_version` or `evaluator_rules_version` are
**not comparable** and must never be merged into one view.

#### A.5.2 Mandatory verification before any write, in order

Copying a self-reported hash is not verification. All of the following run first; **any
failure stops the write**:

1. **Presence** — every file in A.1 that the record depends on exists and is readable.
2. **Input hashes** — recompute the sha256 of each consumed file and of each referenced raw
   body, and compare with `PROVENANCE.input_hashes` and the manifest's `body_sha256`.
3. **Structure** — required keys and declared schema strings present and of the expected
   type (`m2b.capture_manifest.v3`; `checks.json` carrying `deterministic` and
   `deterministic_sha256`; `PROVENANCE.schema`).
4. **Deterministic-block integrity, against two anchors.** Recompute
   `canonical_sha256(checks.deterministic)` and require it to equal **both**
   `checks.json.deterministic_sha256` **and** the selected revision's own result anchor in
   `PROVENANCE.json` (A.5.2a). Matching only the digest a file carries about itself is
   self-consistency, not verification: a `deterministic` block edited and then re-digested
   would satisfy the first comparison alone.
5. **Revision binding, before any run-level identity check.**
   **(a)** `PROVENANCE.schema` must be one of the supported schemas in the table below, and
   its declared result anchor must be present. An **unknown schema, or a missing anchor,
   is rejected** — the module must **never** fall back to capture-run identity, which
   cannot distinguish two revisions of the same capture.
   **(b)** `PROVENANCE.revision` must equal the **selected** revision directory's name. A
   `checks.json` lifted from another revision is refused here even when it is internally
   valid.
   **(c)** An `evidence_<run_id>/` capture directory carries **no `PROVENANCE.json`** and
   therefore has no revision identity; it cannot be selected as a revision input, and its
   absence of an anchor is never treated as "anchor not applicable".
6. **Cross-file identity, as a supplement and never a substitute** —
   `checks.json.run_meta.run_id` equals `capture_manifest.run_id` equals the `run_id`
   embedded in the revision's parent-evidence reference and in the revision name; where the
   schema records `input_hashes`, they match the parent evidence's files; every job
   referenced exists both in `cap.JOBS` and in the manifest.
7. **Upstream pins** — recompute the five upstream hashes from the installed files; a
   mismatch does **not** block recording history but marks the result `pins_stale` and
   forbids any authoritative claim.
8. **Output path** — the target directory must not exist.

##### A.5.2a Supported schemas and their anchors

Declared explicitly, because the retained revisions do not share one shape:

| `PROVENANCE.schema` | Result anchor | Identity keys present | Note |
|---|---|---|---|
| `m2b.offline_revision.v1` | `revised_deterministic_sha256` | `revision`, `original_evidence`, `implementation_that_produced_this_revision` | **no** `input_hashes`, **no** `producer_implementation` |
| `m2b.offline_revision.v2` | `revised_deterministic_sha256` | `revision`, `parent_evidence`, `producer_implementation` | **no** `input_hashes` |
| `m2b.offline_revision.v3` | `revised_offline_result.deterministic_sha256` | `revision`, `parent_evidence`, `producer_implementation`, `input_hashes` | the current shape |

Anything else — an unrecognized schema string, a supported schema whose anchor key is
absent, or a directory with no `PROVENANCE.json` — is **rejected outright**.

**Consequence for v1 and v2, stated rather than worked around.** Neither records
`input_hashes`, and v1 records no `producer_implementation`, so step 2 has no per-file
manifest to verify against and step 7 has no upstream pins to recompute. Records derived
from those revisions therefore **cannot be fully verified**, and the fail-closed outcome is
that no trusted record is produced from them — not a partially trusted one.

**Why capture-run identity is not enough — from the retained set.**
`revision_20260908T021722Z_d1d2` and `revision_20260908T021722Z_d2_literal` are two
revisions of the **same** capture, and their `checks.json` files carry the **same**
`deterministic_sha256` `784ffa66…`, which is also the value in both of their result anchors.
Swapping one's `checks.json` for the other's would satisfy every digest and run-id test.
Only step 5(b) — `PROVENANCE.revision` equal to the selected directory — catches it.

**Fail-closed outcomes.** On any failure the module writes **no record**. It may write a
single clearly-marked `UNUSABLE.json` naming the failed step, the files involved and the
observed-versus-expected hashes — a diagnostic, never a fact. **A `PASS` from the consumed
`checks.json` is never copied through**, and a partially verified input never yields a
partially trusted record. An internally consistent forged input set — every file altered
*and* its recorded hashes altered to match — is **not** detectable by these steps; that
limit is stated rather than papered over.

#### A.5.3 Output paths and deterministic serialization

**Independent paths only.** One new directory per evaluation:
`claude methods/_m2_smoke/basis_eval_<revision_name>/`, containing `basis_records.json` and
`PROVENANCE.json`. The writer **refuses if the target exists** and **never writes into**
`evidence_*`, `revision_*`, `receipts_*`, `frozen_impl_*` or any reviewer directory. Every
existing capture and revision stays byte-identical; a re-derivation creates a **new**
directory (U-4's append-only rule).

**Deterministic serialization.** `json.dumps(obj, indent=2, ensure_ascii=False,
sort_keys=True)` plus a trailing newline; the hashed block covers `records` only and is
digested with the existing `cap.canonical_sha256`, mirroring the established
`deterministic` / `run_meta` split. Volatile values — generation time, absolute filesystem
paths, host details — live in a `meta` block **excluded** from the hash. Note that
`adapter_basis_facts.source` is an **absolute path containing non-ASCII directory names**;
the hashed block stores a normalized repo-relative form, with the raw string kept in `meta`.

### A.6 The evaluator's scope

**Basis-dependent eligibility only.** Given a record plus the currently installed pins, it
returns `{eligible: bool, reasons: [...]}`.

**In this initial module there is no `eligible: true` branch at all.** It returns
`eligible: false` for every input, with a reason code. This is deliberate and is the direct
consequence of U-6 being undefined: **any** true branch would be reachable by editing a
label, and there is no adopted rule against which a `vendor_basis` claim could be validated.
Constraining the *producer* to emit only `unverified` is not enough — the evaluator is
separately callable and must not trust its input's labels.

**Unsupported assertions are rejected even when everything else is genuine.** A record that
says `vendor_basis = unadjusted` while carrying **real, current** evidence references and
**matching** pins is refused: none of the referenced evidence — S1, B1, B2, R1, I2/B4 — ever
established the vendor's basis, so a valid reference does not make the assertion supported.
Retaining a true reference and flipping `unverified` to `unadjusted` is exactly the
pseudo-upgrade this rule exists to stop.

**Reason codes** (distinguishing *why*, without changing any capability verdict or operating
authority): `vendor_basis_unverified` — the ordinary current state; `unsupported_vendor_basis_assertion`
— a claim no adopted rule supports; `unknown_rules_version` — the record's
`derivation_rules_version` or `evaluator_rules_version` is unrecognized, so it is refused
rather than evaluated under today's rules; `evidence_mismatch` — verification per A.5.2
failed; `pins_stale`; `mixed_view` — mixed `vendor_basis` or mixed pins (U-3, U-4).

**A future positive path is out of scope and must not be pre-wired.** It requires U-6 to be
adopted **and** a separately reviewed evidence-validation rule; no hook, flag or
configuration that could enable one may be added in this version.

**It grants no operational authority.** It does not replace, override or modify the
capability verdict, any per-job verdict, `EV6`, `basis_gate`, `--pricing-basis` or any
existing gate; it writes nothing production-side; and a `false` from it is not a data
finding about the vendor. It answers exactly one question — *may this series be used for a
purpose that depends on the price basis?* — and today the answer is always no.

### A.7 Proposed file write scope

| Action | Path | Note |
|---|---|---|
| **create** | `claude methods/_m2_smoke/basis_record.py` | derivation (A.3/A.4) + the A.6 evaluator; reads retained artifacts only |
| **create** | `claude methods/_m2_smoke/test_basis_record.py` | the A.8 matrix, offline synthetic fixtures |
| **create** | `claude methods/_m2_smoke/basis_eval_<revision_name>/` | `basis_records.json`, `PROVENANCE.json` |
| **modify** | **nothing** | zero existing files change |

The new module's own hash and rules versions are recorded inside every output (A.5.1), so
its version is never inferred from the five upstream pins. Keeping this a separate module
rather than folding it into `smoke_checks.py` is deliberate:
editing a producer file would change the producer pins, invalidate the current revision's
provenance and force a fresh revision — for a record that grants no authority. New files do
not alter the five pins `059d0c43…`, `4b062a55…`, `5bbb6ef0…`, `c6d736b1…`, `23b917c5…`.

### A.8 Small future synthetic validation matrix

For the record and evaluator only — §3.5 validates the derivation rules and is unchanged.

| # | Scenario | Expected |
|---|---|---|
| A-1 | complete stock inputs (S1 ∧ B1 ∧ B2 ∧ R1) | `adapter_transform=none`, `vendor_basis=unverified`, evaluator `eligible: false` |
| A-2 | index inputs, no `B2`, no recorded index-adapter pin | `adapter_transform=unknown`; **absence of `B2` is not itself a failure** |
| A-3 | `B2` present, one property unreadable | `adapter_transform=unknown` (F-4) |
| A-4 | producer pins absent from `PROVENANCE.json` | no record emitted |
| A-5 | stored record whose pins differ from the installed code | `eligible: false`, reason "stale pins"; the stored record is **not** rewritten |
| A-6 | a set mixing producer pins | `eligible: false`, reason "mixed pins" |
| A-7 | a record hand-edited to `vendor_basis=unadjusted` with no supporting evidence reference | rejected as unsupported; **no threshold is consulted** |
| A-8 | serialize the same records twice | byte-identical output and identical hash; `meta` excluded |
| A-9 | target directory already exists | write refused; nothing overwritten |
| A-10 | attempt to write inside `evidence_*` / `revision_*` | refused by path guard |
| A-11 | a raw body's bytes differ from the recorded `body_sha256` (input drift) | verification step 2 fails; **no record written**, `UNUSABLE.json` only |
| A-12 | one field inside `checks.json` edited, its file hash updated | step 4 fails on the recomputed `deterministic_sha256`; no record |
| A-13 | `checks.json` from revision X paired with revision Y's manifest | step 5 fails on cross-file identity; no record |
| A-14 | a consumed input file missing entirely | step 1 fails; no record |
| A-15 | `basis_record.py` changed but every upstream pin identical | `record_producer.module_sha256` and the rules versions differ; records are marked **not comparable** and are not merged |
| A-16 | a record with an unrecognized `derivation_rules_version` | evaluator returns `eligible: false`, reason `unknown_rules_version` — never evaluated under current rules |
| A-17 | a record claiming `vendor_basis=unadjusted` with **genuine** evidence references and **current** pins | `eligible: false`, reason `unsupported_vendor_basis_assertion` |
| A-18 | a job's history request is **skipped but listed** with a `requested_url` | recorded as planned, **not** as evidenced access; `adapter_transform=unknown` |
| A-19 | the replay covered a subset of jobs | absent jobs marked `replay_not_evaluated`; no positive transform derivation for them |
| A-20 | an **internally valid `checks.json` from another revision of the same capture** — self-consistent digest, matching `run_id`, and (as with `…_d1d2` vs `…_d2_literal`) possibly the identical `deterministic_sha256` | step 5(b) fails: `PROVENANCE.revision` does not equal the selected revision. **Rejected before any record is written**; run-id agreement must not rescue it |
| A-21 | `deterministic` content edited **and its own `deterministic_sha256` recomputed**, while the selected revision's `PROVENANCE` result anchor still holds the original digest | step 4 fails on the **second** anchor. Rejected before writing. (If the anchor were edited to match as well, this is the self-consistent-forgery limit stated in A.5.2) |
| A-22 | `PROVENANCE.schema` unrecognized, or a supported schema with its anchor key missing, or a directory with no `PROVENANCE.json` | rejected outright; **no fallback to capture-run identity** |
| A-23 | an attempt recorded with `status: null` and a transport `error` | counted as **attempted, not responded**; no positive transform derivation from it |

**Appendix A is a specification, not an implementation.** Building it requires U-1 … U-5 and
U-7 to be decided as recommended, and it still leaves U-6 deferred and every §5.9 blocker in
place.

---

## 6. Revision record

| # | Finding (`M2B_P1_BASIS_CONTRACT_CODEX_REVIEW.md`) | Resolution in revision 2 |
|---|---|---|
| **R1** | Option C defined how a label is produced but not what it permits; a matching new string would pass `basis_gate` by equality alone; mixed states undefined | New **§2.4**: concrete fields (`adapter_transform`, `vendor_basis`, `basis_evidence_ref`, with `adjustment_mode` unchanged as the gate-facing field), the **anti-requirement** that a string whose meaning is "unverified" must never be read as a certification, and a **consumer decision table** covering audit storage, P1 closure, `--pricing-basis none` and boundary-2 eligibility for each state. Mixed states are handled per dimension, and **uniform `unverified` is named as uniformity of ignorance, not of convention**. Seven policy decisions **U-1…U-7** are left explicitly open, and §2.3 now says C closes only the **derivation half** of P1. |
| **R2** | D-1 vs V-7 conflicted on the index; nine "unknown" branches conflated fields; D-2/D-4/V-10 left upgrade rules ambiguous | D-1 split into **D-1a (stock)** and **D-1b (index)** — the index takes no `adjust` argument and B2 does not apply, stated as *not applicable* rather than exempt. §3.4 replaced with a **per-field** table (`adapter_transform` / `vendor_basis` / `volume_unit` / gate) plus **N-1, N-2** for the normal states that are not failures — index unit `unknown` by construction, and the transformation label retained when no vendor-basis evidence exists. New **§3.3** separates **necessary** conditions from **sufficiency**, which is deliberately **not defined** (U-6): neither a ratio step nor a response declaration upgrades `vendor_basis`, and D-4 makes a declaration a necessary-only leg. The matrix gains V-7/V-8, V-13/V-15/V-16 accordingly. |
| **A-R1 (binding)** | Revision 6 (this round): revision identity was not bound, so a valid `checks.json` from another revision of the same capture could pass | **A.5.2 step 4** now requires the recomputed digest to equal **both** `checks.json.deterministic_sha256` **and** the selected revision's `PROVENANCE` result anchor — self-consistency is not verification. **New step 5** binds revision identity *before* any run-level check: the schema must be supported with its anchor present, `PROVENANCE.revision` must equal the **selected** directory's name, and an `evidence_*` capture directory — which has no `PROVENANCE.json` — cannot be selected; run-id agreement is a **supplement, never a substitute**, and there is **no fallback to capture-run identity**. **A.5.2a** declares the supported schemas and anchors (`v1`/`v2` → `revised_deterministic_sha256`; `v3` → `revised_offline_result.deterministic_sha256`), rejects anything else outright, and states the consequence that `v1`/`v2` — lacking `input_hashes`, and `v1` also `producer_implementation` — cannot yield a fully verified record at all. The retained set supplies the worked example: `…_d1d2` and `…_d2_literal` share the capture **and** the digest `784ffa66…`, so only the revision binding separates them. New cases **A-20 … A-22**. **A.3.1** additionally clarifies that a recorded attempt proves only that an attempt was initiated and recorded — **not** endpoint reachability and **not** receipt of an HTTP response, which needs a non-null `status`; a positive derivation now requires an attempt with a recorded response status (case **A-23**). |
| **A-R1** | Revision 5: the record inherited only upstream pins, and input verification was unspecified | **A.5.1** splits `upstream_producer_pins` from the new module's own `record_producer` — `module_sha256`, `record_schema_version`, `derivation_rules_version`, `evaluator_rules_version` — plus `consumed_artifacts` (**recomputed** hashes of every file read) and `source_identity`; records with different rules versions are **not comparable**. **A.5.2** makes seven verification steps mandatory before any write — presence, recomputed input hashes, structure, **recomputed `deterministic_sha256`** (which catches a single edited field), cross-file identity (`run_id` across manifest/checks/PROVENANCE/revision name), upstream-pin recomputation, and a non-existent target — each **fail-closed**: no record, only an `UNUSABLE.json` diagnostic, and **never a copied PASS**. The undetectable case (a fully self-consistent forgery) is stated. New cases A-11 … A-16. |
| **A-R2** | Planned, evidenced and replay URLs were merged into one `observed_urls`; and the `adjust` claim was inaccurate | **A.3.1** defines three separate classes with their exact sources: **planned/expected** from `S1` (`smoke_checks.py:970-980`, built from every record's `requested_url` — **skipped records included**, so it proves no issuance); **evidenced access** from `attempt_count`/`attempt_positions` and `manifest.attempts`; **offline replay requested** from `R1urls` (`:1460-1465`, whose PASS only excludes uncaptured URLs and asserts no completeness). The retained run `20260908T021722Z` is cited as the worked example — five `requested_url`s, two actually issued, three skipped. Completeness rules cover skipped requests and replay subsets, and a positive transform derivation now requires **evidenced access plus an evaluated replay**, not `S1`/`R1urls` PASS. The `adjust` sentence is corrected: it also appears in `B2.detail`; the substantive point — **no structured invocation-argument field exists** — no longer rests on a full-text search. New cases A-18, A-19. |
| **A-R3** | The evaluator exposed a label-driven `eligible: true` path while U-6 is undefined | **A.6** now has **no `eligible: true` branch at all**: every input returns `false` with a reason code, because any true branch would be reachable by editing a label and the evaluator is separately callable, so producer-side constraints cannot substitute for input validation. A record claiming `unadjusted` with **genuine references and current pins** is explicitly **rejected** (`unsupported_vendor_basis_assertion`), and an unrecognized rules version is refused rather than evaluated under today's rules (`unknown_rules_version`). Reason codes distinguish unverified / unsupported / unknown-version / evidence-mismatch / stale pins / mixed view **without touching any capability verdict or operating authority**. Any future positive path requires U-6 adopted **and** a separately reviewed evidence-validation rule, with **no hook pre-wired**. New cases A-16, A-17. |
| **App. A** | Revision 4: an implementation-specification appendix was requested, and **B-3** overstated what a fresh extract blocks | **B-3 corrected**: fresh extraction is authorization-gated, but it is not a prerequisite for every investigation — external corporate-action evidence, an offline ratio over **retained** artifacts, and a fresh read-only extract are now scoped separately, and **none is performed**. New **Appendix A** specifies the exact input artifacts (A.1); the four identifier classes and, precisely, **what is not recorded** (A.2) — the index adapter's source hash appears nowhere, `adjust=""` is inferable from a producer pin rather than recorded, and `adapter_basis_facts.source_sha256` is a **check-time observation that must never be presented as a capture-time pin**; field mappings with stock/index differences (A.3); per-job record granularity, symbol/date coverage and per-field missing-evidence outcomes (A.4); independent output paths under `basis_eval_<revision>/` with deterministic `sort_keys` serialization and a hash-excluded `meta` block (A.5); the evaluator as **basis-dependent eligibility only**, which on today's records can return only `eligible: false` and grants no operational authority (A.6); an exact write scope creating two files plus output directories and **modifying nothing** (A.7); and a ten-row synthetic matrix (A.8). Recommendations and R1–R3 closures are preserved; nothing is implemented or adopted. |
| **§5** | Revision 3: a decision-ready recommendation was requested for each open policy item | New **§5** gives one recommended choice per **U-1 … U-7**, each with rationale, affected consumers and implementation prerequisites, plus **§5.0** separating the five policy questions from **U-6** (evidence-blocked) and U-7's evidence-blocked sub-question, the **record once, evaluate at use** principle, a **minimal implementation scope** (§5.8, evidence-side only) and **seven explicit blockers** (§5.9). Recommendations are conservative by design: the meaning of `--pricing-basis none` is preserved, an unverified or inconsistent vendor basis does not qualify for raw-basis use, mixed-basis failures and mixed/stale-pin refusals are preserved, no threshold is invented, and index semantics are kept separate. **Nothing is adopted and P1 remains open.** R1–R3 were not reopened. |
| **R3** | Reference conclusions over-reached: the filtered extract cannot prove the cache lacks earlier data; per-symbol dates were merged; source homogeneity was conflated with source-plus-`updated_at`; an interpolation claim was unsupported | §4 rewritten. Earliest dates given **per symbol** (2024-06-21 / 2024-06-19 / 2024-08-13), with an explicit statement that the `quality_status = 'ready'` filter means absence in the extract shows only what that extraction returned — **not** that the cache lacks earlier data, and **not** that another source is required; **G-5** rewritten to match. Two separate tables now distinguish **same-`source`** spans from **same-`source`-and-`updated_at`** segments: `SH600011`'s 471-row source span splits into **470 rows (2024-08-13 … 2026-07-23)** plus **one row on 2026-07-24** with a different `updated_at`, so **2026-07-24 is a confounder for `SH600011` too** (added to G-4). The largest both-key segment is **470 rows** per stock (475 for the index), and grouping this way is stated to remove only two recorded metadata differences. The **"interpolated-source row" claim is removed**. |

---

## 7. What this proposal does not do

It does not adopt or implement Option C or any other option, assign or change any label,
value, threshold, schema, dataset, strategy or knowledge entry, decide turnover policy,
reopen the decision memo or any validated milestone, or request, prepare or arm a capture.
Nothing was executed: no test, replay, ratio computation, corporate-action lookup, database
open, network call or `run_id`. All existing files, evidence, revisions, receipts, frozen
bundles and reviewer artifacts are preserved unchanged. Both capture authorizations remain
consumed, and **M2b source capability remains FAIL and is not accepted**.

**Stop: `proposed for review`.**
