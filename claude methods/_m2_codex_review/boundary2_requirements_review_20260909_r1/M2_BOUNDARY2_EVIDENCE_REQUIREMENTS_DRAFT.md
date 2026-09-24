# Boundary-2 evidence requirements — blocked design draft

> **Status: `proposed for review`. BLOCKED DESIGN DRAFT.** This is a requirements analysis,
> not a request, not a plan and not preparation. **It authorizes nothing, adopts nothing,
> selects no operational route, sets no threshold and defines no PASS criterion.** Boundary
> 2 is **not requested** and remains unauthorized.
>
> **Deliberately non-executable.** It contains **no** command, CLI flag, endpoint, request
> body, schedule, retry rule, credential, configuration, armed plan, run directory or output
> directory — by construction, not by omission. Where an existing procedure is referenced it
> is named by its **check identifiers** only.
>
> **Nothing was executed.** No SQLite of any kind, no dataset, fixture, demo seed or private
> file, no network or plugin acquisition, no provider/service/strategy import or call, no
> test, replay or decoder, no service action, no production/schema/data/strategy/knowledge
> mutation, no pilot, backfill or training, no Git action, no agent or workflow. Direct
> Markdown edits and bounded reads of named existing files only.
>
> Task `M2-BOUNDARY2-REQUIREMENTS-20260909`, from
> `M2_REMAINING_DEPENDENCY_CODEX_REVIEW_R2.md`
> (`9168c10afd803eeeafa3bec5b591a452017737b8c41d6cde98f7a701797c6438`). Revision 1. It makes
> **D13** of `M2_REMAINING_DEPENDENCY_DECISIONS.md` concrete.
>
> **P1 open · U-6 deferred · every eligibility result false · source capability FAIL,
> including the two immutable historical `EV6` failures · both boundary-1b capture
> authorizations consumed. No new capture is requested, and none could erase those
> failures. M2 is not complete.** **Codex owns coordination, email and automation.**

---

## 1. What this draft is, and what it is not

`M2B_REAL_SOURCE_VERIFICATION_REQUEST.md:233` makes a revised M2 request (rev. 3) *"whose
expected keys reflect the C2 and C4/R1 results"* one of four prerequisites of boundary 2,
alongside a capability **PASS**, the G3–G5/G7 corrections implemented and tested, and the
P1 basis-label decision. **This draft is not that rev. 3.** It is the layer beneath it: what
a rev. 3 would have to *state*, and which facts do not yet exist to state.

**It does not narrow the M2 objective.** Goal `:181-185` is unchanged and is the standard
against which any of this is judged.

**Blocking items stay blocking.** Where a fact is unknown or a policy undecided, this draft
says so and stops. **No PASS criterion is invented to complete a template.**

---

## 2. The population and intervals, by reference only

Taken from `M2_PILOT_AUTHORIZATION_REQUEST.md` (rev. 2,
`ebb0e499f5509d0c384cde7fdadf05ded91995cc13b7eb75d7d8c93252a88a05`) as an **existing
manifest reference**. **No dataset, database or symbol file was opened for this draft, and
no availability is inferred.**

| Item | Existing reference |
|---|---|
| Population | 50 stocks + `SH000300` + `SH000001`, pinned to `_m1_closure/pilot_symbols.csv` under manifest sha256 `97e251ae84fc9274…` (`:15`) |
| Research interval | 2023-09-04 … 2026-09-04, **728 sessions** (`:16`) |
| Warm-up interval | 2022-08-24 … 2023-09-01, **250 sessions**, ending **strictly before** the research start (`:17`) |
| Declared eligible volume | 36,193 research + 9,742 warm-up = **45,935 records per view** (`:24`) |
| Pre-published warm-up shortfall | **12** symbols with zero eligible warm-up sessions, listed by name; full 250-session depth attainable for **36 of 50**; *"No download can fix the other 14 — they did not exist"* (`:52-57`) |

**This future population is not the retained sample.** Everything measured so far comes from
**two stocks and one index** (`SH600011`, `BJ920000`, `SH000300`) on **one** capture. The
52-symbol population has **never** been observed by this workstream. **This draft does not
construct a 52-symbol availability matrix**, and any rev. 3 that did so from current
evidence would be fabricating it.

**Research and warm-up stay separate**, and the separation is structural, not stylistic:
warm-up ends strictly before research begins; warm-up **integrity** is treated as blocking
while warm-up **depth** is not; and the shortfall above is **pre-published so it cannot be
padded afterwards**. **Shrinking the population or lowering the depth to hide a shortfall is
refused** — that is an existing commitment, restated, not a new rule.

**Eligible-key semantics are listing-aware.** `M1_CLOSURE.md:282`
(`5afb333f…`) records that per-symbol eligibility reuses the accepted **listing-aware
denominator** — `list_date`/`delist_date` are retained, unknown listing stays **UNRESOLVED**
rather than being assumed, and warm-up is a separate gate. A rev. 3's expected keys must be
expressed in those terms, not as a flat session count per symbol.

---

## 3. What C2, C4 and R1 actually change about expected observations

All values below are quoted from the retained
`_m2_smoke/revision_20260908T082833Z_r2abc_v2/checks.json`
(`b6c97eab21254b837f3bd1768eec22c8a54ec925da82beb0f12810156f42d387`). **No new computation
or retrieval was performed.**

### 3.1 C2 — a per-symbol unknown, not a class rule

`C2` is a **FINDING** on `bj920000`: outcome `pre_boundary_history_served`, decided by the
KLC body, with *"the CAUSE (code mapping or otherwise) is **NOT** established by this
observation"*. Measured: `first_date` **2017-03-29**, `last_date` 2026-09-07,
`span_sessions` 501, `span_missing` **empty**, `research_sessions_present` **728**,
`warmup_sessions_present` **250**.

**Implications a rev. 3 would have to carry:**

* For **this one symbol**, the `92xxxx` code **does** serve history predating the
  2024-08-13 boundary, and it covers the declared research and warm-up intervals in full.
  An expected-key statement asserting that pre-boundary rows are unavailable under the new
  code would be **wrong for it**.
* **The result does not generalize.** Exactly one BJ path was contacted. The other BJ
  symbols in the approved population are **unobserved**, so their expected first dates are
  **unknown**, and a rev. 3 must express them as *unknown until observed*, per symbol.
* **The cause is not established**, so no rule may be derived from a presumed mechanism.
* **Unknown must not be padded.** An unobserved symbol's expected keys cannot be filled in
  by analogy with `BJ920000`, and a later missing observation must not be accepted as
  explained merely because this one symbol behaved this way.

### 3.2 C4 — the effective first date, and share dates that are not price keys

`C4` is a **FINDING** on both stocks. `SH600011`: 0 duplicate OHLCVA rows, 0 klc rows before
the first usable share date **2001-12-06**, **4** share dates with no klc row,
`effective_first_date` **2001-12-06**. `BJ920000`: 0 duplicates, first usable share date
**2015-10-27**, **17** share dates with no klc row, `effective_first_date` **2017-03-29**.

**Implications:**

* On the adapter path the usable series begins at **`max(first price date, first
  outstanding-share date)`** — the two cases differ in *which* of the two binds, which is
  why it must be stated as a rule and not as a constant.
* **Share-event dates are not price keys.** The share series is a step function of
  share-count changes; a date appearing only in it does **not** denote a trading session.
  The adapter's outer merge and forward fill will otherwise **fabricate a price row** at
  such a date, removed later only if it duplicates the preceding OHLCVA. A rev. 3's expected
  keys must be **price keys**, derived from the trading calendar, never from the share
  series.
* `duplicate_ohlcva_rows` is **0** for both stocks, so the de-duplication mechanism removed
  nothing here — **on two symbols**. That is not evidence about the other 50.

### 3.3 R1 — stock and index expected counts arise from different mechanisms

`R1` is **PASS** ×3. Both stocks: **978 rows, 2022-08-24 … 2026-09-04** — the declared
window, sliced client-side. The index: **5,987 rows, 2002-01-04 … 2026-09-07**, with the
retained detail stating *"no date arguments; the index adapter returns the full served
series"*, and columns exactly `date, open, high, low, close, volume`.

**Implications:**

* **One expected-key rule cannot cover both instrument classes.** A stock's returned span
  is bounded by the requested window; an index's is whatever the vendor serves. A rev. 3
  must state the two separately and must not express index expectations as a window.
* **The index frame carries no `amount`.** Amount- and liquidity-derived expectations must
  remain **benchmark-excluded**, consistent with the existing routing.
* `R1` proves the replay **ran and returned those shapes**; it is **not** evidence about
  the values in any column, and not about any symbol outside the three.

---

## 4. Each boundary-2 prerequisite: existing evidence, missing fact, eventual review artifact

| Prerequisite (request `:233`) | Existing evidence | Actual missing fact or design | Eventual review artifact |
|---|---|---|---|
| **Capability PASS** | Two captures, both **FAIL**; `EV2` byte-to-text equivalence on all five bodies; the three-layer outcome/aggregation/verdict contract | A qualifying run has not occurred. **A PASS is not guaranteed by any run**, and `:235` limits what one would prove: five specific responses captured, decoded, replayed and checked | A run report and check table judged under the existing contract, independently reviewed |
| **G3–G5 corrections implemented and tested** | Implemented **in the smoke producers** and covered by their suite: request #2 labelled `outstanding_share_wan` (retained `D5` PASS ×2); expected URLs derived from the installed adapter constants at run time | **Adoption in the code a pilot would actually run.** `_m2_pilot/` is preserved unchanged and still carries the M2a index template and symbol-case handling. **The smoke checker is not a drop-in acquisition or staging replacement**; any alternate route needs its own design, implementation, review and authorization | A reviewed correction, or a reviewed design for the intended pilot path, validated at new hashes |
| **G7 / the P1 basis-label decision** | The P1 proposal designs the **partial, evidence-side** treatment; the basis module implements and records it, validated for its hashes; every record is `unverified` and no `eligible=true` path exists | **No accepted positive vendor-basis rule** (U-6 is evidence-blocked) and **no reviewed pilot integration** on the cited current route. **Reference identity is not basis verification** — the existing `P6`/`H5` and `X1`/`X2` checks compare a stored label with a declaration | An adopted rule, a separately reviewed evidence-validation rule, and a re-reviewed module — **or** a recorded decision to proceed with `unverified` and its consequences |
| **A revised M2 request (rev. 3)** | C2, C4 and R1 as quoted in §3; the pilot request's population, intervals and pre-published shortfall | The document itself. **Drafting it authorizes nothing** and is the one prerequisite with no external dependency | A reviewed rev. 3 whose expected keys match the retained results and state the unknowns as unknown |
| *(underlying)* **Corpus proof** | M1's gate mechanisms, validated on **synthetic fixtures** | **Real corpus evidence through those mechanisms.** A mechanism validated on fixtures is not proof about a corpus | The gate's own results over real data, with before/after manifests |

---

## 5. The three evidence questions, in plain terms

For each: the question, what the existing artifacts **cannot** establish, and **which facts
a future authorized step would have to observe**. No threshold, sufficiency rule, access
plan or endpoint choice appears; unknowns remain blocking.

### 5.1 Whole-interval adjustment consistency (goal `:184`)

**Question.** Is the corporate-action adjustment applied on the same basis at every point of
the declared interval, for every symbol in the population — not merely declared
consistently?

**What existing artifacts cannot establish.** The inherited checks compare a **stored label
against a declaration** per view; they are not an interval-consistency test, and no such
check exists (`M2_REMAINING_DEPENDENCY_DECISIONS.md` §5.1). The retained ratio work is a
**conditional feasibility** result under a stated rounding envelope, on **two** symbols, and
its intervals are confounded in source, fetch time, calendar span and price path — it
identifies no mechanism. G1 established **when** actions occurred for two issuers from
official notices; it did not establish how any vendor applied them.

**Facts a future authorized step would have to observe.** For each symbol: the vendor's
price series across spans that **contain** an independently established action date; the
same series' behaviour **across** that date; and the source and fetch-time provenance of
every row involved, so that a change of basis can be distinguished from a change of source.
**What would count as consistent is undecided and is not defined here.**

### 5.2 Lineage (goal `:182`)

**Question.** For any row in a staged corpus, can its origin be reconstructed — which
source, which request, which code version, and when?

**What existing artifacts cannot establish.** `daily_bar_cache` has **no row-level
provenance**: it stores `source`, `adjustment_mode`, `volume_unit`, `quality_status` and two
timestamps written by different clocks, and the lineage audit found **no reference label
deriving from a response declaration**. The importer records a **coarse run-level** event
with no cache keys and no code pin. History has a referential provenance check (`H4`); the
pricing view's lineage is **thinner**.

**Facts a future authorized step would have to observe.** A recorded association between
each written row and the request that produced it, the producer version, and the
observation time — sufficient that a later reader can answer "where did this come from"
without inference. **Whether that is achieved by new columns, a parallel record or an
external log is a design choice this draft does not make.**

### 5.3 Safe, isolated staging (goal `:181`, `:185`)

**Question.** Can a backfill run without any possibility of removing or overwriting existing
evidence, and can its result be discarded or promoted as a unit?

**What existing artifacts cannot establish.** The cache write-path audit found an
**unqualified full-table delete** over a 71-table list that includes `daily_bar_cache`, a
**guard-bypassing** demo-seed replace, and **three unconditional deletes** that precede the
batch upsert — so the conditional guard is not a global protection. **No isolation mechanism
for a staging target has been identified**, and none of this observes what any database
contains.

**Facts a future authorized step would have to observe.** That the staging target is
distinct from production for the whole run; that no path reachable during the run can delete
or replace production rows; and that the run's result can be discarded entirely, or promoted
as a unit, with the outcome independently checkable. **Recording the risk is not a
substitute**: goal `:181` requires staging-or-copy first.

---

## 6. Inherited, missing, and later — kept apart

**Inherited (mechanism exists, validated on fixtures; needs real evidence, not new code).**
Calendar and archive integrity; membership and eligible-key completeness in both views;
date validity; OHLC positivity; duplicate business keys; declared cross-view transformation
and identity reconciliation; the stock volume-unit check with its benchmark exclusion and
its verified/quarantined accounting; warm-up separation, non-consumption and coverage.

**Missing policy or evidence (no run supplies these).** U-6 sufficiency; the positive
vendor-basis corroboration; the durable attribution record for the recorded U-1…U-5/U-7
adoption; the cause behind C2; per-symbol availability for 51 unobserved instruments; a
whole-interval consistency criterion.

**Later implementation or operational authorization (separate grants).** The pilot-path
correction or design; row-level lineage; the staging isolation design; the backfill itself;
and — separately again — promotion.

**Off the critical path.** The turnover policy: no wired consumer of the retained measure
exists, so **withheld is the current state and costs nothing**. It enters this graph only if
a real consumer is introduced. The null-`amount` semantics belong to the staging design, not
to boundary 2's prerequisites.

---

## 7. The smallest set of genuinely necessary decisions, and what each needs first

**Granting a permission does not satisfy its technical prerequisites**, and none of the
following is requested here.

| # | Decision | Evidence prerequisite before it can be acted on |
|---|---|---|
| **1** | Whether rev. 3 is drafted, and by whom | **None.** It is a document; it authorizes nothing and has no external dependency. It is the only item on this list that is not blocked |
| **2** | How the P1 basis-label prerequisite is discharged — a positive rule, or a recorded decision to proceed with `unverified` and its consequences | U-6 is **evidence-blocked**; a positive rule needs evidence that does not exist. The alternative needs no new evidence but is a **policy** choice with stated consequences |
| **3** | Which code a pilot would run, and whether the pilot path is corrected or newly designed | A reviewed design. `_m2_pilot/` is preserved and may not be edited without its own authorization; the smoke checker is not a replacement |
| **4** | Whether a further capture is authorized, and for what defined objective | A defined end-to-end objective must exist first. **No run is guaranteed to yield a PASS**, and none can erase the historical `EV6` |
| **5** | The staging isolation and lineage design | §5.2 and §5.3's questions answered as designs, before any run |
| **6** | Whether a staged corpus backfill is authorized | **All** of boundary 2's prerequisites, plus decision 5. **A staging grant supplies none of them**, and acquisition and staging remain distinct grants |

**Nothing above is chosen here, and no sequence is asserted between items that do not depend
on each other.** Decisions 1 and 2's fallback branch are independent of everything else.

---

## 8. Consulted pins, limits, preservation

| File | sha256 | Used for |
|---|---|---|
| `M2_REMAINING_DEPENDENCY_CODEX_REVIEW_R2.md` | `9168c10afd803eeeafa3bec5b591a452017737b8c41d6cde98f7a701797c6438` | the assignment |
| `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md` | `c39726d06aafc4d630c05fe93141e8b99012221571da0eea28789d5fa9033057` | §1, §4 (`:233`, `:235`, §6, §9) |
| `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` | `f8b699e531ab4e98e7bccd17bc0c2850355ed0ea75e5038cfecaa216a6266164` | `:181-185` |
| `M2B_NEXT_STAGE_DECISION_MEMO.md` | `536505ea4a29e506dadf3c510eab67dc8d52a84706f2288c85690af64aea0d4a` | boundary-2 discussion |
| `M2_PILOT_AUTHORIZATION_REQUEST.md` | `ebb0e499f5509d0c384cde7fdadf05ded91995cc13b7eb75d7d8c93252a88a05` | §2 |
| `M1_CLOSURE.md` | `5afb333fc9d76532e61de53a58febc5ff0a0ced2f32eb66c57d28608fe8e4f7e` | §2 (listing-aware semantics) |
| `_m2_smoke/revision_20260908T082833Z_r2abc_v2/checks.json` | `b6c97eab21254b837f3bd1768eec22c8a54ec925da82beb0f12810156f42d387` | §3 (C2, C4, R1) |
| `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` | `71e0dc52b8cf93281b1c09f501a62695915ef070a740dc378df2f1637a66007c` | §4 (G7 row) |
| `_m2_smoke/basis_record.py` | `0fda4f7effba73ac04a8f10ce35b686a7a646a741650159f55cd9288b6bd2cc7` | §4 (the partial record) |
| `_m1_closure/staging_gate.py` | `7152d773ea9ca9778c0f038cf9caaf7be36119c7d0cc059de80821d53ff35b7f` | §6 (inherited mechanisms) |
| `_m1_closure/acceptance_runner.py` | `59b67c18ed714f9e074d20d8ac8d9d68e0258ed259cd07c0ec60a36e45c5e9ad` | §6 |
| `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` | `155207ffcee956a5a582bb993ef315a56345c7a854637c007f178ec0bf3ded92` | §5.2 |
| `M2B_CACHE_WRITE_PATH_AUDIT.md` | `6fa4439d9c8c19331357018729ccbae9a06e13708de2831f5fca3af596cecd73` | §5.3 |
| `M2B_U6_RETAINED_STUDY.md` | `65fbe917be7816f725461ff3d6ed7f3f2f2bce2e3f27019ae8efabf2dde5cb41` | §5.1 |
| `M2B_G1_CORPORATE_ACTIONS_CODEX_ACCEPTANCE.md` | `0558bc6a92b5e986a90ae4f9ff70bb42f222ab3f41d04db8593c2ccf45c7954d` | §5.1 |
| `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` | `50261775464ba24cf5cedfd3bdc4ce002421f7bcf238ba96cc5d9637c3b3a1ec` | §6 |
| `M2B_AMOUNT_REPRESENTATION_AUDIT.md` | `cecc8c7a7f22f3e3d05a1cabffbb765b4fa6cc29973a85bd11e118f976e953a2` | §6 |
| `M2_REMAINING_DEPENDENCY_DECISIONS.md` | `2b4546cd51ffd9dab3855c6fd3d33e411ecf8acca31dcb07cd251e2328a3bf21` | §4, §5.1 |

**Limits.**

1. **Reference only.** The population, intervals and shortfall in §2 are quoted from an
   existing document. **No dataset, symbol file or database was opened**, and **no
   availability was inferred** for any symbol.
2. **Two stocks and one index.** Every measured value in §3 comes from that sample on one
   capture. **Nothing here is evidence about the other 51 instruments.**
3. **Non-executable by construction.** Existing procedures are referenced by check
   identifier; no operational parameter of any kind appears.
4. **Not exhaustive.** This draft names the requirements visible from the files pinned
   above. It is not a claim that every requirement has been identified, and a reviewed
   rev. 3 may find more.
5. **Blocking stays blocking.** Every unknown fact and undecided policy above is left
   unresolved rather than closed with an invented criterion.

**Preservation.** No existing file was modified, moved, renamed or deleted by the creation
of this document. The historical request, goal, proposal and memo, the accepted code and
reports, and every Codex review are unchanged.

**Stop: `proposed for review`.**
