# M2 — remaining dependencies and the decisions they need

> **Status: `proposed for review`.** Evidence-bound dependency map built from existing files
> only. **This document grants nothing, adopts nothing, and requests no run.** No policy,
> threshold, label, gate or eligibility is changed. No percent-complete and no date appear
> anywhere, by design.
>
> **Nothing was executed.** No SQLite, dataset, fixture or private file; no provider,
> service or strategy import or call; no test, replay or decoder; no network, plugin or
> capture; no new extract; no production/schema/data/strategy/knowledge change; no
> training, pilot or backfill; no Git action; no agent, sweep, scratch script or output
> directory. Direct Markdown edits only.
>
> Task `M2-REMAINING-DEPENDENCIES-20260909`, dispatched by
> `_m2_codex_review/m2_remaining_dependencies_dispatch_20260909.txt`
> (`45f6860c58cc958649e4c8a26c64a4a1eb54336fd7f4d8eba265a98e3882483a`).
> Revision 2 — MD-R1 through MD-R3 of `M2_REMAINING_DEPENDENCY_CODEX_REVIEW.md` addressed in
> one consolidated pass (§8); **reported as addressed pending Codex review, not marked
> closed here.**
>
> **Standing position, unchanged: P1 open · U-6 deferred · every eligibility result false ·
> M2b source capability FAIL, including the two historical `EV6` failures, which are
> immutable and which no future run can erase · both boundary-1b capture authorizations
> consumed. M2 remains incomplete until its own acceptance criteria are met.**
>
> **Codex owns coordination, any stop email and any automation action. This session
> performs none of those.**

---

## 1. The objective, and the distance to it

`THREE_YEAR_RESEARCH_EXECUTION_GOAL.md:173-185`
(`f8b699e531ab4e98e7bccd17bc0c2850355ed0ea75e5038cfecaa216a6266164`) defines M2 as
*"create a validated three-year corpus without silently rewriting evidence"*, with a
prerequisite of **explicit user authorization after M1 review** and five acceptance
criteria: staging-or-copy first (`:181`); before/after manifests, counts, hashes, coverage,
rejected rows and source lineage (`:182`); no `ERROR` pseudo-dates or duplicate
`(symbol, trade_date, adjustment)` rows in the research view (`:183`); corporate-action
adjustment **consistent through the entire interval** (`:184`); and atomic-or-recoverable,
independently checked promotion **only if separately authorized** (`:185`).

**Real work stands behind this, and none of it is a corpus.** M1 and M2a are technically
**validated** and are not reopened here (goal `:1053`, `:1168`): M1 for the data-contract
and staging-acceptance scope, M2a for the **offline** single-process pilot runner on
**synthetic fixtures** (79 cases, exit 0). On top of that: two live boundary-1b captures on
**two stocks and one index**, both ending in capability **FAIL**, with their bytes,
manifests and reference extracts retained; offline check revisions over those bytes; a
technically validated P1 basis *module*; and eight bounded offline audits (G1, G3, U-6
readiness, U-6 retained study, reference-basis lineage, cache write-path, turnover
dependency, amount representation).

**What none of it is:** a backfill over real corpus data, a corpus, or user acceptance —
and the goal's authoritative box (`:1093-1140`) says so in its own terms.

**Attribution preserved.** The adoption of U-1…U-5 and U-7, the deferral of U-6 and the
authorization of the offline basis module are recorded in the goal as a **Claude-reported**
user instruction, **not independently verified by Codex** (`:1155-1170`). That labelling is
carried forward here unchanged and is not upgraded by anything in this document.

---

## 2. Reconciling the historical memo with what has since been settled

`M2B_NEXT_STAGE_DECISION_MEMO.md` (`536505ea…`) is a 2026-09-08 document. Several of its
open items have since been **technically** addressed; others have not, and a technical
resolution is never policy adoption or source acceptance.

| Memo item | Status now | Evidence |
|---|---|---|
| §2.1 P1 is an unadopted labelling/corroboration contract | **Partly superseded, and the residue is narrow.** U-1…U-5 and U-7 are recorded as **adopted** and the evidence-side module authorized — **Claude-reported, not independently verified by Codex**. That attribution is a **durable open question about verifiability**, and it is **not** a finding that no adoption occurred. The module was implemented and validated for its hashes, and **U-5's evidence-side route is implemented and accepted, not an open choice**. What remains genuinely undecided is **U-6** and **P1's closure** | `M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md` `f90de3d1…`; goal `:1119-1140`, `:1155-1170` |
| §2.2 "no corporate-action evidence for a discriminating span" | **Materially advanced.** G1 retrieved and retained official implementation notices for both stocks from the issuer/exchange hosts | `M2B_G1_CORPORATE_ACTIONS_CODEX_ACCEPTANCE.md` `0558bc6a…` |
| §2.2 whether the ratio behaves as additive or multiplicative | **A conditional feasibility result, not an explanation.** Under the study's stated **closed half-cent nearest-rounding envelope** and its two **pre-rounding hypotheses**, in every interval with non-zero differences exactly one relation is feasible, and which one **tracks the reference source**. Feasibility is not identification: **source, fetch time, calendar span and price path are confounded** across those intervals, and the study says so | `M2B_U6_RETAINED_STUDY.md` `65fbe917…`; `M2B_U6_RETAINED_STUDY_CODEX_ACCEPTANCE.md` `a6967def…` |
| §2.2 point 3, turnover used / annotated / withheld | **Reframed by evidence.** No retained turnover *rate series* exists, and no `backend/` file reads any smoke output; the wired `turnover_rate` is an unrelated quote field | `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` `50261775…` |
| §2.2 denominator carry-in age | **Confirmed as an observation, not a defect.** Median 1,975 / max 2,516 days for `SH600011`; the zero-interruption rule was never exercised inside the retained research window | same, §3.4 |
| §2.3 `n = 1` temporal stability; BJ generalization | **Unchanged.** One capture, one instant; exactly one BJ path contacted | goal `:1096-1103`; memo §2.3 |
| §2.3 C4 orphan counts, B3 `prevclose` markers | **Unchanged and still unexplained.** C4: 4 (`SH600011`) / 17 (`BJ920000`) share dates with no klc row. B3: of the rows that carry `prevclose`, 24 were counted and 23 differ from the previous close — and B3 is **explicitly not P1 evidence**, is **ADVISORY**, and its retained detail is **truncated** (a sample list, not the complete marker series). **Counts are neither a full series nor a causal explanation** | memo §2.1, §2.3 |
| §3 absence of a same-version live capture | **Unchanged.** The validated build has never produced its own capture | memo §3.2 |
| §3.3 the two historical `EV6` failures | **Immutable.** Not waived; **no run can clear them**, and none is requested for that purpose | memo §3.3; goal `:1108-1111` |
| Where the basis label comes from | **Newly established (code-level).** No reference source's label derives from a response declaration; all trace to request arguments, writer defaults or a source-string migration | `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` `155207ff…` |
| Cache write surface | **Newly mapped.** Includes an unguarded full-table delete (`reset_knowledge`) and a guard-bypassing demo-seed `INSERT OR REPLACE` | `M2B_CACHE_WRITE_PATH_AUDIT.md` `6fa4439d…` |
| Amount representation | **Newly mapped.** The `turnover` alias binds on no inspected frame; three of six inspected paths construct `ready` bars with a null `amount` | `M2B_AMOUNT_REPRESENTATION_AUDIT.md` `cecc8c7a…` |

---

## 3. The dependency table

### 3.0 The prerequisite graph, restored from the request

An earlier revision of this document put staging ahead of the evidence it depends on. The
retained request states the actual gate. `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md:233`,
boundary **2 — 52-symbol pilot**, *"Staging collection of the approved 50 + 2"*:

> *"Later and separate. **Requires a capability PASS, the G3–G5/G7 corrections implemented
> and tested, the P1 basis-label decision taken on the evidence named in Section 6, and a
> revised M2 request (rev. 3) whose expected keys reflect the C2 and C4/R1 results.** Not
> requested."*

and at `:235`: *"A capability FAIL escalates to nothing; it produces findings. A capability
PASS proves only that five specific responses were captured, decoded, replayed through the
adapter and checked as stated."*

**Three consequences govern the rest of this document.**

1. **A downstream authorization cannot substitute for an unmet upstream condition.**
   Authorizing staging would not supply a capability PASS, the live-path corrections, or a
   basis decision. Conversely, **a new capture is neither guaranteed to yield a PASS nor a
   permission to stage** — acquisition grants and staging grants are **not
   interchangeable**, and each needs its own explicit authorization.
2. **The chain is: evidence acquisition objective → policy adoption supported by adequate
   evidence → separately reviewed implementation → qualifying source evidence (capability)
   → pilot/request prerequisites → staged corpus acceptance → optional, separately
   authorized production promotion.** Several items inside it are **independent** and can
   advance in parallel; no rigid ordering is invented between independent items.
3. **Goal `:184` is corpus-wide.** Adjustment consistency *through the entire interval*
   cannot be met by a three-symbol sample however it is authorized.

### 3.1 The table

Categories are kept apart deliberately: **E** = missing evidence · **P** = a user policy
choice · **I** = an engineering implementation gap · **O** = operational proof that cannot
exist without an authorized run. Nothing advisory is promoted to a blocker here.

| # | Unresolved proposition or deliverable | Evidence already available | Still missing | What would settle it | Blocks | Authorization needed |
|---|---|---|---|---|---|---|
| **D1** | An **authorized real-corpus** staging/copy backfill exists, with before/after manifests, coverage, rejected rows and lineage (goal `:181-182`) | M1's gate implementation (`_m1_closure/`, §5.1) validated on **synthetic fixtures**; the frozen manifest `97e251ae…` and calendar `f1f1ce33…` **do** exist; the M2a offline pilot runner is validated on fixtures; the cache write-path map | **O** — no backfill over **real corpus data** has been authorized or run, so no before/after manifest pair exists **for such a run**. This is not a claim that no manifest of any kind exists | An authorized staging run producing those artifacts, **after** the §3.0 prerequisites | **The full corpus** | Explicit user authorization for a staging backfill, scoped and separate from any promotion — **and it does not substitute for D2/D3/D12** |
| **D2** | The validated build produces self-consistent capture evidence | Two historical captures, both FAIL; `EV2` bytes-to-text passes on all five bodies | **O** — no same-version live capture | One authorized run with a **defined end-to-end acceptance objective** (memo §5, T1–T4) | **Source capability** | A new explicit one-run authorization. **Not requested here**, and **never** to clear `EV6` |
| **D3** | The **P1 basis-label decision** required by boundary 2 is taken | The necessary-condition set (`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §3.3); G1 actions; the conditional ratio result; U-1…U-5/U-7 recorded adopted (Claude-reported) and the evidence-side route **implemented and accepted** | **E** — U-6 sufficiency, and any index basis *assertion*, are **evidence-blocked**: *"no available observation can settle it"* (`:443-444`). Plus the durable **attribution** question (§1) | Evidence that does not currently exist, for U-6; independent confirmation of the adoption record, for attribution | **Boundary 2 explicitly** (request `:233`) — and therefore, indirectly, **the staged corpus**. Not source capability | A decision to *seek* particular evidence is **separate** from authorization to *acquire* it. Neither is requested here |
| **D4** | A record can ever evaluate `eligible = true` | `basis_record.py` `0fda4f7e…`, validated for its hashes; 41/41 exit 0 | **I** — under the **currently proposed route**, `evaluate()` returns a hard-coded `False` (§5.2) and exposes no branch | An adopted sufficiency rule **and** a separately reviewed evidence-validation rule **and** an implementation change. **No claim is made that any future design must reuse this evaluator** | Any positive eligibility path **on this route** | Policy (U-6) **plus** a separate implementation authorization. Adopting U-6 alone would change nothing on this route |
| **D5** | Adjustment is consistent through the **entire** interval (goal `:184`) | G1 official actions for two stocks; G3 ratio analysis; the U-6 study's **conditional** per-interval feasibility | **E** at corpus scale — evidence covers 2 stocks + 1 index on one capture, and the gate's existing basis checks (P6/H5, X1/X2, §5.1) are **per-view declaration** tests, not an interval-consistency test | Corpus-wide evidence through an interval-consistency criterion that does not yet exist as a check | **The full corpus**, and D1's acceptance | **Two distinct grants**: authorization to *acquire* the data, and authorization to *stage* it. **Neither implies the other** |
| **D6** | Denominator definition and freshness | The retained auxiliary series; ages; the zero-interruption rule | **E** — the vendor declares neither the definition (total / free-float / A-share) nor freshness | Vendor documentation or an independent reference; **not** obtainable by re-fetching a change-event endpoint | **Only an optional future consumer** | None required to leave it open |
| **D7** | Turnover used / annotated / withheld | The full consumer map; no wired consumer of the retained measure | **P** — a policy choice, with nothing currently depending on it | A user decision | **Nothing.** Choosing "withheld" closes none of P1, U-6, capability or M2 | None. Any *implementation* would need its own scope review |
| **D8** | Null-`amount` bars stored `ready` | Three of six inspected paths construct that shape; M1's `chk_units` quarantines the stock case; benchmarks are excluded by design | **P** on the semantics, **I** on where the flag is computed (`daily_bar_cache.py:195`/`:204-205`, propagated at `:213-214`) | A policy decision on the semantics, then a scoped implementation | **Corpus quality fields** — a D1 acceptance concern, not capability | Policy decision, then separate production authorization |
| **D9** | Temporal stability; BJ generalization beyond one symbol | One complete observation, one instant, one BJ path | **E** — a second observation on a different trading day; the other six `bj_code_history` symbols | A run under memo T2, understanding that it yields **an additional observation, not a stability proof**; more symbols need separate scope review | **Source capability** confidence, and D5's breadth | A new one-run authorization; symbol expansion is **outside** the existing boundary |
| **D10** | C4 orphan share-dates; B3 `prevclose` mismatches | The retained counts | **E** — no explanation | Vendor behaviour evidence or a wider sample | **Nothing today.** Advisory; *"would matter at pilot scale"* | None |
| **D11** | Corpus-safety of the write surface before any backfill | The cache write-path audit: `reset_knowledge` full-table delete over 71 tables, the demo-seed `INSERT OR REPLACE`, the batch guard and its pre-`executemany` deletes | **I** — no isolation or constraint for those paths exists for a staging run | A design that **constrains or isolates** them, reviewed before D1 runs. **Recording the risk is not a substitute for meeting the safety criterion**; goal `:181` requires staging-or-copy first precisely so this cannot be waived | **D1's acceptance** | Design decision, then a separately authorized implementation |
| **D12** | The **G3–G5/G7 live-path corrections** are *implemented and tested* in the code a pilot would actually run (request `:233`) | **G3** — the smoke labels request #2 `outstanding_share_wan`, never `amount`; retained `D5` PASS ×2. **G4/G5** — the smoke derives expected URLs from the installed adapter constants at run time, so the template and symbol-case defects do not apply to it. All three are covered by `test_m2_smoke.py` (182 cases, exit 0) | **I**, and precisely located: the corrections live in `_m2_smoke/`, while `_m2_pilot/` is **preserved unchanged** by standing instruction — `provenance.py:44` still carries the M2a `INDEX_HIST = …/hisdata_klc2/klc_kl.js` template (G4) and `derive` (`:136-141`) still requires a **response-declared** basis (G7). **G7 is not designed anywhere** | Either a reviewed correction of the pilot path, or an explicit decision that the pilot runs the smoke-derived path instead. **G7 additionally needs the P1 corroboration substitute (D3)** | **Boundary 2** | A scoped implementation authorization — **and it must not reopen the preserved `_m2_pilot/` artefacts without one** |
| **D13** | A revised M2 request (rev. 3) whose expected keys reflect the C2 and C4/R1 results (request `:233`) | The retained C2 finding (BJ pre-boundary service, cause not established), C4 orphan counts, R1 replay results | **I/P** — no rev. 3 exists | Drafting it, which the memo also names as the step that would make any further capture justifiable on its own merits | **Boundary 2** | None to draft; it is a document. **Drafting it authorizes nothing** |

**Index and stock roles stay separate throughout.** The index has no auxiliary
outstanding-share request, no amount requirement, no unit gate (`chk_units` excludes
benchmarks by construction) and no liquidity claim; U-7 exists precisely because an index
`vendor_basis` may not mean what a stock's means. **Research and warm-up spans stay
separate too**: the retained research window is `2023-09-04…2026-09-04` (728 sessions)
inside a declared window opening `2022-08-24`, and warm-up rows are not research evidence.

---

## 4. What the retained bytes cannot settle

* **Causation for the ratio behaviour.** The U-6 study established that which relation is
  feasible **tracks the reference source**. Tracking is not mechanism: the retained bytes
  cannot distinguish a vendor convention from an adapter transformation from a coincidence
  of the sampled spans.
* **Vendor semantics from local names.** A column name, a code comment, a writer default or
  a caller-added `amount_unit="yuan"` label is not a vendor declaration. The lineage audit
  established that **no** retained reference label derives from a response declaration.
* **Freshness of a change-event series.** Long carry-in proves neither an incorrect share
  count nor incompleteness, and re-fetching the same endpoint cannot resolve it.
* **Database contents, from the recent static audits.** The eight offline audits listed in
  §1 — and this turn — are **static reads only**: write *eligibility*, an *attempted* write
  and *durable contents* are three different things, and those audits evidence only the
  first, having opened no database. **That is a statement about them, not about the
  workstream's history:** the two authorized captures did read production rows read-only to
  build the frozen reference extracts, and M1's gate was validated against a database of
  synthetic fixtures. Neither is erased by the sentence above.
* **The historical `EV6` failures.** They are a code-version disagreement, permanently
  recorded. A future run produces a separate result; matching classifications there merely
  emit no `EV6` entry, which is not a pass.

---

## 5. Two traces completed here, and what is genuinely left

### 5.1 W-1 — what the M1 gate already computes toward the M2 acceptance criteria

Completed inside this correction from the named accepted files: `_m1_closure/staging_gate.py`
(`7152d773…`) and the delegated checks it imports at `:63-65` from `acceptance_runner.py`
(`59b67c18…`). **M1 and M2a are validated and are not reopened**; this only maps what
exists to the goal's criteria, to show what a future run would **inherit** rather than
build.

| Goal criterion | Existing gate checks | Inherited, or still missing |
|---|---|---|
| `:182` manifests, counts, hashes | **C0** pinned calendar vs frozen baseline (`:493`); **A_*** archive present / readable / **unchanged (file + whole-db content)** (`:502-514`); **B0** frozen baseline unmodified by validation (`:667`) | **Mechanism inherited.** What is missing is a **before/after pair for a real backfill**, which only an authorized run produces |
| `:182` coverage | **V3** warm-up coverage (`:659`); **V3b** per-security feature readiness (`:648`); **M1/M2/M3** membership + eligible-key completeness for stocks, benchmarks and history (`:535-541`) | **Mechanism inherited**, including the listing-aware eligible-session denominator |
| `:182` rejected rows | the verified / **quarantined** accounting inside the delegated checks (e.g. `chk_units`, `acceptance_runner.py:188-208`) | **Mechanism inherited**; a corpus-scale rejection report is not |
| `:182` source lineage | **H4** history ingest-run provenance referentially valid (`:553`) | **Partly inherited.** `daily_bar_cache` itself carries no row-level provenance (cache write-path audit), so lineage for the pricing view is thinner than for history |
| `:183` no `ERROR` pseudo-dates | **P1/H1** dates are real sessions (`:521`, `:548`) | **Inherited** |
| `:183` no duplicate `(symbol, trade_date, adjustment)` | **P5/H3** duplicate business keys (`:527`, `:550`); **P6/H5** stored basis matches the declaration (`:529`, `:555`); **X1/X2** declared cross-view transformation and identity reconciliation (`:560-579`) | **Inherited** |
| `:184` adjustment consistent through the **entire** interval | — | **Missing.** P6/H5 and X1/X2 test a **declaration match per view**, not consistency across the interval. **This is a real check gap, not only missing data** |
| `:181` staging-or-copy first; `:185` recoverable promotion | — | **Not gate logic at all.** Operational, and unauthorized |

**Decision impact, and it changes D1's shape.** Most of `:182-183` **already has an
implementation** validated on synthetic fixtures, so D1 is **less an implementation gap
than an evidence-and-authorization gap**. The genuine engineering gaps are narrower and
now named: the **`:184` interval-consistency criterion**, the pricing view's thinner
lineage, and the staging/promotion mechanics.

### 5.2 One trace that changes the eligibility picture

`_m2_smoke/basis_record.py` (`0fda4f7e…`) `evaluate()` at `:730-762`:

```python
    return {
        "eligible": False,          # a literal, not derived from `reasons`
        "reasons": sorted(set(reasons)),
        "note": "U-6 is deferred, so this module exposes no eligible=true path. A future "
                "positive path requires an adopted sufficiency rule AND a separately "
                "reviewed evidence-validation rule; none is pre-wired here.",
```

**Consequence, and it is decision-relevant.** The `False` is **unconditional**: a record
accumulating **zero** reasons still returns `eligible: False`. Moreover every
`vendor_basis` other than `unverified` is *refused* as
`unsupported_vendor_basis_assertion` (`:741-750`), and `evaluate_view` (`:772-798`) can only
ever return `False` because it aggregates `evaluate`. **So adopting U-6 would not by itself
produce a positive eligibility path** — D4 is an **engineering gap sitting behind a policy
gap**, not one question. That distinction was not explicit in the map before this trace and
is why the trace was completed rather than deferred.

### 5.3 Remaining offline candidates — a bounded statement

**No further materially useful offline candidate was identified in the inspected scope.**
Two items considered and dropped: re-reading the P1 proposal's §3.6 code-location list
would restate work already accepted and would not resize a decision, since U-5's
evidence-side route is **implemented and accepted**, not an open choice; and re-reading the
retained auxiliary bodies would confirm a field spelling and a count that are already
recorded, answering no open question. Also excluded: re-running validated suites,
re-auditing accepted findings, further sweeps, and any repeat model fit over the same price
windows.

**Bound.** This is an assessment of candidates **in the inspected scope**, not a claim that
the repository is exhausted. On this evidence the next dependencies are **external**:
**D3's evidence-blocked U-6 question**, **D12/D13's scoped implementation and request
work**, **D2's one-run objective**, and **D1's staging authorization** — in that character,
not more offline analysis.

---

## 6. Genuinely unresolved decisions, with their prerequisite conditions

Each is an item **not already decided**. Adopted-and-implemented items (U-1…U-5, U-7 and
the evidence-side route) are **not** re-asked here. **No option is chosen**, no threshold
set, no blanket permission sought, and no capture command, configuration or run directory
prepared. **Deciding to seek evidence is separate from authorizing its acquisition, and a
design choice is separate from permission to implement it.**

| # | Unresolved decision | Alternatives | Prerequisite condition | Acceptance evidence at that boundary |
|---|---|---|---|---|
| **1** | **U-6 sufficiency, and whether an eligibility path is built at all** (D3, D4) | (a) commission a search for evidence that could support a sufficiency rule; (b) adopt a rule on stated grounds and separately authorize an evaluator change; (c) leave `unverified` fail-closed | U-6 is **evidence-blocked** (`:443`); and on the current route, adopting a rule alone changes nothing because no branch exists (§5.2) | An adopted rule, a **separately reviewed** evidence-validation rule, and a re-reviewed module at new hashes |
| **2** | **How the P1 adoption attribution is resolved** (§1, D3) | (a) the user confirms the U-1…U-5/U-7 adoption in a durable artefact; (b) it stays **Claude-reported, not independently verified** | Nothing technical blocks (a); it is a record-keeping decision. **(b) is the status quo and is not a finding that no adoption occurred** | A user-authored record Codex can verify, or continued explicit labelling |
| **3** | **Whether the G3–G5/G7 corrections are carried into the code a pilot would run** (D12) | (a) a scoped, reviewed correction of the pilot path; (b) an explicit decision that the pilot runs the smoke-derived path; (c) neither | Boundary 2 requires them *implemented and tested* (`:233`); `_m2_pilot/` is **preserved unchanged** and may not be edited without its own authorization; **G7 additionally needs decision 1** | The corrected path validated at new hashes, with the preservation of `_m2_pilot/` either kept or explicitly released |
| **4** | **Whether a revised M2 request (rev. 3) is drafted** (D13) | (a) draft it, reflecting C2 and C4/R1; (b) do not | **None** — drafting is a document, authorizes nothing, and the memo names it as the step that would let any later capture be judged on its own merits | A reviewed rev. 3 whose expected keys match the retained results |
| **5** | **Whether a further capture is authorized, and for what objective** (D2, D9) | (a) one run with a **defined end-to-end acceptance objective** (T1) or on a different trading day (T2); (b) none | A defined objective must exist **first**. **A capability PASS is not guaranteed by any run, and is not itself permission to stage.** **No run can erase either historical `EV6`**, and none is requested for that purpose | The run's own outcome and check tables under the existing three-layer contract; a FAIL is an acceptable, informative outcome |
| **6** | **Corpus-safety design for the write surface** (D11) | (a) constrain the destructive paths; (b) isolate the staging target from them | **Both are designs**; goal `:181` requires staging-or-copy first, so this criterion is **not waivable by recording the risk** | A written design, then a re-audit of the write paths against it |
| **7** | **Whether a staged corpus backfill is authorized** (D1, D5) | (a) authorize a scoped staging/copy backfill; (b) hold; (c) redefine M2's scope | **All of boundary 2's prerequisites** (`:233`) — capability PASS, decisions 1/3/4 — **plus** decision 6. **A staging grant supplies none of them**, and acquisition and staging are separate grants | Before/after manifests, counts, hashes, coverage, rejected rows, lineage; no `ERROR` or duplicate keys in the research view; and an interval-consistency result for `:184`, whose check does not yet exist (§5.1) |
| **8** | **Null-`amount` semantics** (D8) | (a) make a stock bar with no usable amount distinguishable; (b) leave it `ready` | (a) touches production ingestion and can change guard outcomes | A stated intent for the `:465-477` clause and the `:502-521` deletes, validated against that intent |
| **9** | **Turnover policy** (D7) | used / annotated / **withheld** | **None.** Withheld is the current state and nothing depends on the choice | None required to leave it as-is |

**On sequence.** Decisions **2, 4 and 6** are independent of the others and of each other,
and can advance in any order. Decision **1** gates the G7 half of **3**. Decisions **1, 3,
4** and a capability PASS are, per the request, prerequisites of **7**; **5** is one route
toward that PASS but is neither guaranteed to produce it nor a substitute for the rest.
**8** belongs to **7**'s design. **9 needs no action.** **This is a dependency statement,
not a schedule, and no ordering is asserted between items that do not depend on each
other.**

**Codex, not this document, decides whether to continue an identified offline task or to
notify the user and pause.**

---

## 7. Consulted pins and preservation

| File | sha256 | Used for |
|---|---|---|
| `_m2_codex_review/m2_remaining_dependencies_dispatch_20260909.txt` | `45f6860c58cc958649e4c8a26c64a4a1eb54336fd7f4d8eba265a98e3882483a` | the assignment |
| `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` | `f8b699e531ab4e98e7bccd17bc0c2850355ed0ea75e5038cfecaa216a6266164` | §1 (`:173-185`, `:1093-1170`) |
| `M2B_NEXT_STAGE_DECISION_MEMO.md` | `536505ea4a29e506dadf3c510eab67dc8d52a84706f2288c85690af64aea0d4a` | §2, §3 (T1–T4) |
| `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md` | `c39726d06aafc4d630c05fe93141e8b99012221571da0eea28789d5fa9033057` | scoped terms |
| `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` | `71e0dc52b8cf93281b1c09f501a62695915ef070a740dc378df2f1637a66007c` | D3, §6 (`:426-450`, §3.3, §3.6) |
| `_m2_smoke/basis_record.py` | `0fda4f7effba73ac04a8f10ce35b686a7a646a741650159f55cd9288b6bd2cc7` | §5.2 (`:727-798`) |
| `M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md` | `f90de3d1ac0aa61ff6ee7dba899ee49141ad39f0809e58b391c969a784f9c6f2` | D4 |
| `M2B_G1_CORPORATE_ACTIONS_CODEX_ACCEPTANCE.md` | `0558bc6a92b5e986a90ae4f9ff70bb42f222ab3f41d04db8593c2ccf45c7954d` | §2 |
| `M2B_G3_RATIO_ACCEPTANCE_CODEX.md` | `bb1b295999a5d3791481a35d354daa47ddab23cd7882087bd0f3fb1338ca2110` | §2 |
| `M2B_U6_READINESS_ASSESSMENT.md` | `de130cf0bb5d02cd6a66a383eaa93188c7dbb2110337eb7e623a120b1ce368d2` | §2, §4 |
| `M2B_U6_READINESS_CODEX_ACCEPTANCE.md` | `8a1d8595bcc1bf1abae092f6e8a9c528a66bd83d945215e62b5844d34dab5d3a` | §2 |
| `M2B_U6_RETAINED_STUDY.md` | `65fbe917be7816f725461ff3d6ed7f3f2f2bce2e3f27019ae8efabf2dde5cb41` | §2, §4 |
| `M2B_U6_RETAINED_STUDY_CODEX_ACCEPTANCE.md` | `a6967defd5bf04f9a7c6bea3344105f2c4e8ee0b768295608c1f0ad8a63f109f` | §2 |
| `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` | `155207ffcee956a5a582bb993ef315a56345c7a854637c007f178ec0bf3ded92` | §2, §4 |
| `M2B_CACHE_WRITE_PATH_AUDIT.md` | `6fa4439d9c8c19331357018729ccbae9a06e13708de2831f5fca3af596cecd73` | D11 |
| `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` | `50261775464ba24cf5cedfd3bdc4ce002421f7bcf238ba96cc5d9637c3b3a1ec` | §2, D6, D7 |
| `M2B_AMOUNT_REPRESENTATION_AUDIT.md` | `cecc8c7a7f22f3e3d05a1cabffbb765b4fa6cc29973a85bd11e118f976e953a2` | §2, D8 |
| `_m1_closure/staging_gate.py` | `7152d773ea9ca9778c0f038cf9caaf7be36119c7d0cc059de80821d53ff35b7f` | §5.1 (W-1 inheritance trace) |
| `_m1_closure/acceptance_runner.py` | `59b67c18ed714f9e074d20d8ac8d9d68e0258ed259cd07c0ec60a36e45c5e9ad` | §5.1 (W-1 inheritance trace) |
| `M2_REMAINING_DEPENDENCY_CODEX_REVIEW.md` | `685e9bae2332d059cb14aad8b1cb1971f5b787512f92728391b1d9adb3812389` | the review this revision answers |
| `_m2_pilot/provenance.py` | `21197f57e7d594045d2842003b538a7d5cd82da5a5dfc426bdffea855eb17f63` | D12 (`:44` `INDEX_HIST`, `:136-141` `derive`) |
| `_m2_smoke/revision_20260908T082833Z_r2abc_v2/checks.json` | `b6c97eab21254b837f3bd1768eec22c8a54ec925da82beb0f12810156f42d387` | §2, §3 window facts |

**Limits.** This map reconciles the documents and code named above at those bytes. It is
**not** a claim that every project file was consulted; §5.3 states the bound. Nothing here
observes runtime behaviour or database contents.

**Preservation.** No existing file was modified, moved, renamed or deleted; the only write
is this document. Every accepted audit, acceptance report and Codex review listed above is
unchanged, as are the retained captures, revisions and producers. Verification accompanies
the handoff.

---

## 8. Revision record

**Revision 2 — `M2_REMAINING_DEPENDENCY_CODEX_REVIEW.md`
(`685e9bae2332d059cb14aad8b1cb1971f5b787512f92728391b1d9adb3812389`), MD-R1 to MD-R3, one
consolidated pass.** The reviewed revision-1 bytes were
`3895c339c0dd7db14897d1e9ac310c630264a7f2877925a5f775b07aff02fcec`. **Reported as addressed
pending review, not marked closed here.**

| # | Finding | Correction made |
|---|---|---|
| **MD-R1** | The critical path contradicted the request's boundary-2 prerequisites: D3 said basis evidence did not block the corpus, and §6 put staging before capture, implying a downstream authorization could substitute for unmet upstream conditions | New **§3.0** quotes the actual gate (`M2B_REAL_SOURCE_VERIFICATION_REQUEST.md:233`) — capability **PASS**, G3–G5/G7 implemented and tested, the P1 basis decision, and a rev. 3 request — plus `:235` on what a PASS does and does not prove. Three governing consequences are stated: a downstream grant supplies no upstream condition; **acquisition and staging grants are not interchangeable**, and a capture is not guaranteed to yield a PASS; and goal `:184` is corpus-wide. **D3** is restated as gating **boundary 2 and therefore the staged corpus**; **D5** now names **two distinct grants**; **D1** records that a staging grant does not substitute for D2/D3/D12. New **D12** tracks the G3–G5/G7 corrections and their **evidenced status** — implemented and tested in `_m2_smoke/`, while `_m2_pilot/` remains preserved and still carries the G4 template (`provenance.py:44`) and the G7 response-declared basis (`:136-141`), with **G7 not designed anywhere**. New **D13** covers the rev. 3 request. **D11** no longer offers "accept as-is with the risk recorded" as an alternative — the safety criterion is not waivable that way. **D4** is bounded to *the currently proposed route*, with no claim that a future design must reuse this evaluator. §6 states explicitly which items are **independent**, so no rigid ordering is invented |
| **MD-R2** | §2 declared the contract unadopted and §6 re-asked for all of U-1…U-5/U-7, reopening bounded decisions; W-1's inference was project-wide; W-2/W-3 repeated accepted work | §2's P1 row now preserves the attribution consistently: U-1…U-5/U-7 are **recorded adopted** and the evidence-side route **implemented and accepted** — Claude-reported and not independently verified is a **durable verifiability question, not a finding that no adoption occurred** — leaving **U-6** and P1 closure as the genuine residue. §6 no longer re-asks the adopted items; the attribution itself is decision **2**. §1 records that **M1 and M2a are validated and not reopened** (goal `:1053`, `:1168`), so no project-wide implementation gap is inferred. **W-1 is completed inside this document as §5.1**, an inheritance map from `staging_gate.py`/`acceptance_runner.py` to the goal's criteria: most of `:182-183` **already has an implementation**, and the genuine gaps narrow to the **`:184` interval-consistency check**, the pricing view's thinner lineage, and the staging/promotion mechanics. **W-2 and W-3 are dropped**, with the reason given, and §5.3 is a bounded statement that no further materially useful offline candidate was identified in the inspected scope |
| **MD-R3** | Historical scope was overstated: "no staging run … no manifests exist"; "every audit … no database has been opened"; the ratio result was stated unconditionally; B3 was summarised without its limits | **D1** is qualified to an **authorized real-corpus** backfill, and records that the frozen manifest `97e251ae…`, the calendar `f1f1ce33…` and the fixture-validated gate and pilot runner **do** exist. **§4** now scopes the static claim to the eight recent audits and this turn, and states that the authorized captures did read production rows read-only for the frozen reference extracts and that M1's gate was validated against a fixture database. **§2's ratio row** restores the **closed half-cent nearest-rounding envelope**, the two **pre-rounding hypotheses**, and the **source/fetch-time/span/price-path confounding**. **§2's B3 row** restores that B3 is **explicitly not P1 evidence**, is **ADVISORY**, and that its retained detail is **truncated** — counts are neither a complete marker series nor a causal explanation |

No new study, computation, retrieval, scratch script, output directory, agent or workflow
was used; the corrections rest on the named accepted source and review files pinned in §7.

**Stop: `proposed for review`.**
