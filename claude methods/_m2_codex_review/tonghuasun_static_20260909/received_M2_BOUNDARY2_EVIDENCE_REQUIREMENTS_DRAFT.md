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
> (`9168c10afd803eeeafa3bec5b591a452017737b8c41d6cde98f7a701797c6438`).
> Revision 2 — BQ-R1 through BQ-R4 of `M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_CODEX_REVIEW.md`
> addressed in one consolidated pass (§9); **reported as addressed pending Codex review, not
> marked closed here.** It makes **D13** of `M2_REMAINING_DEPENDENCY_DECISIONS.md` concrete.
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
P1 basis-label decision. **This draft is not that rev. 3** — it carries no operational
parameter and grants nothing. It is the **completed analytical layer** underneath one: what
a rev. 3 would have to *state*, which facts do not yet exist to state, and (§7.1) which
parts remain blocked and why. **No further preparatory document is proposed.**

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
**two stocks and one index** (`SH600011`, `BJ920000`, `SH000300`), which leaves **49 of the
52 instruments unobserved** relative to this sample. The measurements come from the **single
complete** capture `20260908T082833Z` (five of five requests); the earlier capture
`20260908T021722Z` **aborted after two requests** and is not a second observation of the
same kind. **This draft does not construct a 52-symbol availability matrix**, and any rev. 3
that did so from current evidence would be fabricating it.

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

**Four different key sets must not be collapsed**, and the rest of this draft keeps them
apart:

| | Key set | Determined by |
|---|---|---|
| **(a)** | **Raw served keys** | whatever the vendor returns for a request |
| **(b)** | **Adapter output keys** | (a) after the installed adapter's merge, fill, slice and de-duplication |
| **(c)** | **Expected eligible research / warm-up keys** | the **manifest, listing dates and pinned calendar** — `expected_key_map(entries, window)` in `staging_gate.py:205-236`, applied to **stocks and benchmarks alike** as separate sub-populations (`:535-541`) |
| **(d)** | **Accepted staged-view keys** | (b) after the gate has judged it against (c) |

**(c) is a contract, not an observation.** `membership_gate`'s `empty_domain="reject"`
setting for the research interval treats a member with no eligible research session as *"a
manifest error, and it is rejected on the manifest, **independently of what the data
contains**"*; warm-up uses `"allow"` because a security listed after that interval
legitimately has none. **Unknown availability is therefore not an unknown contract.** A
source's first returned date does **not** redefine a listing date, shrink the expected
domain, or justify a missing key — served coverage only determines whether the expected keys
were **supplied**. **No filtering route is designed or implemented here.**

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

* For **this one symbol**, the `92xxxx` code **served** history predating the 2024-08-13
  boundary, and the declared research and warm-up sessions were present in the returned
  series. That is **observed coverage of key set (a) on the sampled interface** — it is
  **not** verified security identity for every historical date, and it does **not**
  establish a listing rule. Expected keys stay with (c).
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
* **Share-only dates must not become price rows — and their calendar status is unknown.**
  `share_dates_without_klc` counts dates present in the share series and absent from the
  price payload (`:1403`). Two things follow, and they are different. First, such a date
  must **not** be promoted to a price observation: the adapter's outer merge and forward
  fill would otherwise **fabricate** a row there, removed later only if it duplicated the
  preceding OHLCVA. Second, **their absence from this payload does not prove they are
  non-trading dates** — a share-only date may be a genuine session whose price observation
  is missing. **The cause of the orphan dates remains unresolved**, and expected keys come
  from (c), the pinned calendar and listing rules, never from the share series.
* **The measurement stage matters, and an earlier draft got it wrong.**
  `duplicate_ohlcva_rows` is counted over the **decoded in-window rows** (`smoke_checks.py:1383-1392`),
  **before and independently of the adapter replay**. A zero therefore says the *payload*
  carried no repeated OHLCVA tuple in the window; it says **nothing** about what the
  adapter's de-duplication did or did not remove. Likewise `effective_first_date` is a
  **computed diagnostic bound** — `max(first price date, first usable share date)` at
  `:1404-1411` — **not** a proof of what the adapter retained. Both are two-symbol
  observations.

### 3.3 R1 — stock and index expected counts arise from different mechanisms

`R1` is **PASS** ×3. Both stocks: **978 rows, 2022-08-24 … 2026-09-04** — the declared
window, sliced client-side. The index: **5,987 rows, 2002-01-04 … 2026-09-07**, with the
retained detail stating *"no date arguments; the index adapter returns the full served
series"*, and columns exactly `date, open, high, low, close, volume`.

**Implications:**

* **The window exemption is a property of the `R1` *interface* check, not of the pilot.**
  `smoke_checks.py:432-447` states it exactly: *"`window=None` is the index interface, which
  takes no date arguments and returns the full served series; that is a **different
  contract, not a laxer one**, so the window is not imposed on it … it is **not a
  requirement that any security return a particular row count**."* An earlier draft
  over-read this as meaning a rev. 3 must not express index expectations as a window. **That
  was wrong.** The pilot's benchmarks are judged against key set (c) like every other
  member, over the **same declared research and warm-up intervals**.
* **Extra served history must be accounted for without becoming research observations.**
  Receiving 5,987 index rows does not make 5,987 rows eligible; the rows outside the
  declared intervals belong to (a)/(b) and must be visible as such, not silently discarded
  and not silently counted.
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
| **G7 / the P1 basis-label decision** | The P1 proposal designs the **partial, evidence-side** treatment; the basis module implements and records it, validated for its hashes; every record is `unverified` and no `eligible=true` path exists | **No accepted positive vendor-basis rule** (U-6 is evidence-blocked) and **no reviewed pilot integration** on the cited current route. **Reference identity is not basis verification** — the existing `P6`/`H5` and `X1`/`X2` checks compare a stored label with a declaration | An adopted rule, a separately reviewed evidence-validation rule, and a re-reviewed module. **There is no `unverified` fallback for this prerequisite** — see the note below |
| **A revised M2 request (rev. 3)** | C2, C4 and R1 as quoted in §3; the pilot request's population, intervals and pre-published shortfall | The document itself. **Drafting it authorizes nothing** and is the one prerequisite with no external dependency | A reviewed rev. 3 whose expected keys match the retained results and state the unknowns as unknown |
| *(underlying)* **Corpus proof** | M1's gate mechanisms, validated on **synthetic fixtures** | **Real corpus evidence through those mechanisms.** A mechanism validated on fixtures is not proof about a corpus | The gate's own results over real data, with before/after manifests |

**Why `unverified` is not a way through.** An earlier draft offered "a recorded decision to
proceed with `unverified`" as an alternative discharge of the P1 prerequisite. **That is
withdrawn**: it would silently reopen U-1 and U-2. The proposal's U-1 recommendation
(`M2B_P1_BASIS_CONTRACT_PROPOSAL.md:454-458`) is explicit —
*"`(adapter_transform = none, vendor_basis = unverified)` **does not qualify** a series for
any boundary-2 use that depends on the price basis … The pair may still be **stored and
reported as an audit fact**, and it does not block uses that make no basis claim —
identity, coverage, calendar and unit work."* The pilot request's consumed views are
raw/unadjusted and their `none` semantics are unchanged, and **no later permission has
reversed them**. The adoption record remains **Claude-reported and not independently
verified**, which is a verifiability question — not a licence to re-decide U-1.

So `unverified` is an **audit holding state**, not a pass. **P1 and U-6 stay blocked by the
actual evidence and policy gaps**, no waiver is suggested, and the objective is not relaxed.
Independent **non-basis** analysis (identity, coverage, calendar, unit) may continue inside
its own authorized scope, and **does not complete M2**.

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
against a declaration** per view; they are not an interval-consistency test, and **no such
check was found in the inspected current code** — the inheritance trace maps the cited gate
and runner only and did **not** establish repository-wide absence
(`M2_REMAINING_DEPENDENCY_DECISIONS.md` §5.1). The retained ratio work is a
**conditional feasibility** result under a stated rounding envelope, on **two** symbols, and
its intervals are confounded in source, fetch time, calendar span and price path — it
identifies no mechanism. G1 established **when** actions occurred for two issuers from
official notices; it did not establish how any vendor applied them.

**Facts a future authorized step would have to observe.** Per symbol, the source and
fetch-time provenance of every row in the interval, so that a change of basis can be
distinguished from a change of source; and, **where an action falls inside the interval**,
the price series on both sides of that independently established date.

**An action-free interval is a different evidence case, not a gap.** A symbol with no
corporate action in the interval is **not** required to have one, its absence is **not**
evidence of missing data, and an action-free interval is **not** automatic basis
verification either — it simply offers no discriminating observation. **What would count as
consistent is undecided and is not defined here, and no threshold or sufficiency criterion
is invented.**

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
batch upsert — so the conditional guard is not a global protection. **No isolation mechanism for a staging target was found in the inspected
code** — which is a statement about what was read, not a repository-wide absence — and none
of this observes what any database contains.

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

**Missing policy, or evidence no run supplies.** U-6 sufficiency; the positive
vendor-basis corroboration; the durable attribution record for the recorded U-1…U-5/U-7
adoption; and a whole-interval consistency **criterion**, which is a definition rather than
a measurement.

**Missing but empirically observable.** Per-symbol availability for the **49** unobserved
instruments is an **observation**, not a policy gap: an authorized step could supply it.

**Optional, and not an adopted requirement.** The **cause** behind C2 is a vendor-mechanism
explanation. What the gate needs is evidence of correct historical **identity and coverage**;
explaining the vendor's internals is **not by itself an adopted gate**, and this draft does
not promote it to a blocker.

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
| **1** | How the P1 basis-label prerequisite is discharged | **Evidence that does not exist.** U-6 is evidence-blocked, and per §4 there is **no `unverified` fallback** for a basis-dependent pilot use |
| **2** | Which code a pilot would run — the pilot path corrected, or a new design | A reviewed design. `_m2_pilot/` is preserved and may not be edited without its own authorization; **the smoke checker is not a replacement**, and any alternate route is subject to its **own** design, implementation, review and authorization |
| **3** | Whether a further capture is authorized, and for what defined objective | A defined end-to-end objective must exist first. **No run is guaranteed to yield a PASS**, and none can erase the historical `EV6` |
| **4** | The staging isolation and lineage design | §5.2 and §5.3's questions answered as designs, before any run |
| **5** | Whether a staged corpus backfill is authorized | **All** of boundary 2's prerequisites, plus decision 4. **A staging grant supplies none of them**, and acquisition and staging remain distinct grants |

**Nothing above is chosen here, and no sequence is asserted between items that do not depend
on each other.**

### 7.1 What remains genuinely blocked in a later operational request

This document completes the analytical layer it was commissioned for. **It does not ask for
the same analysis to be commissioned again**, and it proposes no further document whose
purpose would be to restate it. What a later operational request would still have to
contain, and cannot yet, is named here so the blockage is explicit rather than deferred:

* **Per-symbol expected keys for the 49 unobserved instruments** — expressible today only as
  the (c) contract from manifest, listing dates and calendar; the served coverage against it
  is unobserved.
* **The basis statement for the consumed views** — blocked on decision 1, with no
  `unverified` route.
* **The identity of the executing code** — blocked on decision 2.
* **Every operational parameter** — request shaping, pacing, ordering, retry behaviour,
  target location, retention and rollback. **These are deliberately absent here**: they are
  route and authorization decisions, and writing them would be operational preparation,
  which this task excludes.

**None of these is requested, and naming them adopts nothing.**

---

## 8. Consulted pins, limits, preservation

| File | sha256 | Used for |
|---|---|---|
| `M2_REMAINING_DEPENDENCY_CODEX_REVIEW_R2.md` | `9168c10afd803eeeafa3bec5b591a452017737b8c41d6cde98f7a701797c6438` | the assignment |
| `M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_CODEX_REVIEW.md` | `3d844477399412de066bb63ad88dd5f3cdc7000b8d583ca30dda895b5f4ccea8` | the review this revision answers |
| `_m2_smoke/smoke_checks.py` | `4b062a55fae6f9bd348a7ffdf20073debababffafc71568e2aaaf8181c832bbe` | §3.2, §3.3 (`:432-447`, `:1383-1392`, `:1403`, `:1404-1411`) |
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
| `M2_REMAINING_DEPENDENCY_DECISIONS.md` | `8f0b8228ac3634167039c27eff24eca4833fafac33d7b24f652286710584e849` | §4, §5.1 |

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

---

## 9. Revision record

**Revision 2 — `M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_CODEX_REVIEW.md`
(`3d844477399412de066bb63ad88dd5f3cdc7000b8d583ca30dda895b5f4ccea8`), BQ-R1 to BQ-R4, one
consolidated pass.** The reviewed revision-1 bytes were
`7f1cbe9c82089ec3f9176b4a4c2ac2a4ba0d713ed1f5b404a122c6db295d647f`. **Reported as addressed
pending review, not marked closed here.**

| # | Finding | Correction made |
|---|---|---|
| **BQ-R1** | §3.3 treated the `R1` index window exemption as a property of the pilot, and unknown availability was allowed to read as an unknown contract | §2 adds the **four key sets** — (a) raw served, (b) adapter output, (c) expected eligible research/warm-up from **manifest, listing dates and pinned calendar**, (d) accepted staged-view — with `staging_gate.py:205-236` quoted: research uses `empty_domain="reject"`, *"a manifest error … **independently of what the data contains**"*, warm-up uses `"allow"`, and `membership_gate` runs over **stocks and benchmarks alike** (`:535-541`). §3.3 now quotes `smoke_checks.py:432-447` — the window is not imposed on the **index interface** because it *"is a different contract, not a laxer one"* and *"not a requirement that any security return a particular row count"* — and states plainly that the earlier reading was wrong: **the pilot's benchmarks are judged against (c) over the same declared intervals**, and 5,987 served rows do not become 5,987 eligible ones. §3.1 restates C2's coverage as **observed coverage of (a) on the sampled interface**, not verified identity for all historical dates and not a listing rule; **a first returned date redefines no listing date and justifies no missing key**. No filtering route is designed |
| **BQ-R2** | §4's G7 row and §7's decision 2 offered proceeding with `unverified` as an alternative discharge of the P1 prerequisite, silently reopening U-1/U-2 | The fallback is **removed** from both. §4 gains a note quoting the proposal's U-1 recommendation (`:454-458`): the pair *"**does not qualify** a series for any boundary-2 use that depends on the price basis"*, while remaining storable *"as an audit fact"* and not blocking identity, coverage, calendar and unit work. `unverified` is stated to be an **audit holding state, not a pass**; P1/U-6 stay blocked on the actual evidence and policy gaps; no waiver is suggested and the objective is not relaxed; non-basis analysis continues in its own scope and **does not complete M2** |
| **BQ-R3** | Measured diagnostics were read as adapter effects; share-only dates were called non-trading dates; the unobserved-instrument count was wrong; §6 mis-sorted availability and the C2 cause | §3.2 now names the **measurement stage**: `duplicate_ohlcva_rows` is counted over decoded in-window rows at `smoke_checks.py:1383-1392`, **before and independently of the replay**, so a zero says nothing about what the adapter removed; `effective_first_date` is a **computed diagnostic bound** (`:1404-1411`), not proof of what the adapter retained. Share-only dates (`:1403`) must not be promoted to price rows, **and their market-calendar status is not established** — a share-only date may be a genuine session with a missing price observation; the **orphan cause stays unresolved**. §2 corrects the arithmetic to **49** unobserved instruments (52 − 3) and distinguishes the **aborted** two-request capture from the **single complete** five-request one. §6 splits its middle category: per-symbol availability for the 49 is **empirically observable**, not a policy gap; and the **cause** of C2 is recorded as an **optional explanation**, not an adopted gate — identity and coverage are what the gate needs |
| **BQ-R4** | §7 asked again whether and by whom rev. 3 should be drafted, reopening an already-authorized task | Decision 1 is **removed**. §1 states that this is the **completed analytical layer** and that **no further preparatory document is proposed**. New **§7.1** names what a later operational request would still have to contain and cannot yet — per-symbol expected keys for the 49, the basis statement, the executing code's identity, and **every operational parameter**, which is deliberately absent as route-and-authorization work this task excludes. §5.1's *"no such check exists"* and §5.3's *"no isolation mechanism"* are qualified to **the inspected current code**, not repository-wide absence. §5.1 also records that **an action-free interval is a different evidence case** — not proof of missing data and not automatic basis verification — and that no threshold or sufficiency criterion is invented |

No new document, script, directory, study, test, import, runtime call, database access or
Git action was used for this revision; the corrections rest on the named files pinned in §8.

**Stop: `proposed for review`.**
