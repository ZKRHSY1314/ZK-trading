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
> (`45f6860c58cc958649e4c8a26c64a4a1eb54336fd7f4d8eba265a98e3882483a`). Revision 1.
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

**Every accepted result to date is upstream of all five.** The validated work is: an
offline pilot runner on synthetic fixtures (M2a), two live boundary-1b captures on
**two stocks and one index** that both ended in capability **FAIL**, offline check
revisions over their retained bytes, a technically validated P1 basis *module* with **no
`eligible=true` path**, and eight bounded offline audits (G1, G3, U-6 readiness, U-6 retained
study, reference-basis lineage, cache write-path, turnover dependency, amount
representation). **None of these is a staging run, a corpus, or user acceptance**, and the
goal's authoritative box (`:1093-1140`) says so in its own terms.

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
| §2.1 P1 is an unadopted labelling/corroboration contract | **Still open.** The module exists and is validated for its hashes; the contract is not adopted and P1 is not closed | `M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md` `f90de3d1…`; goal `:1119-1140` |
| §2.2 "no corporate-action evidence for a discriminating span" | **Materially advanced.** G1 retrieved and retained official implementation notices for both stocks from the issuer/exchange hosts | `M2B_G1_CORPORATE_ACTIONS_CODEX_ACCEPTANCE.md` `0558bc6a…` |
| §2.2 whether the ratio behaves as additive or multiplicative | **Measured, not explained.** In every interval with non-zero differences exactly one of the two tested relations is feasible, and which one tracks the **reference source** | `M2B_U6_RETAINED_STUDY.md` `65fbe917…`; `M2B_U6_RETAINED_STUDY_CODEX_ACCEPTANCE.md` `a6967def…` |
| §2.2 point 3, turnover used / annotated / withheld | **Reframed by evidence.** No retained turnover *rate series* exists, and no `backend/` file reads any smoke output; the wired `turnover_rate` is an unrelated quote field | `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` `50261775…` |
| §2.2 denominator carry-in age | **Confirmed as an observation, not a defect.** Median 1,975 / max 2,516 days for `SH600011`; the zero-interruption rule was never exercised inside the retained research window | same, §3.4 |
| §2.3 `n = 1` temporal stability; BJ generalization | **Unchanged.** One capture, one instant; exactly one BJ path contacted | goal `:1096-1103`; memo §2.3 |
| §2.3 C4 orphan counts, B3 `prevclose` markers | **Unchanged and still unexplained.** 4 (`SH600011`) / 17 (`BJ920000`) share dates with no klc row; 24 rows carry `prevclose`, 23 differing | memo §2.3 |
| §3 absence of a same-version live capture | **Unchanged.** The validated build has never produced its own capture | memo §3.2 |
| §3.3 the two historical `EV6` failures | **Immutable.** Not waived; **no run can clear them**, and none is requested for that purpose | memo §3.3; goal `:1108-1111` |
| Where the basis label comes from | **Newly established (code-level).** No reference source's label derives from a response declaration; all trace to request arguments, writer defaults or a source-string migration | `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` `155207ff…` |
| Cache write surface | **Newly mapped.** Includes an unguarded full-table delete (`reset_knowledge`) and a guard-bypassing demo-seed `INSERT OR REPLACE` | `M2B_CACHE_WRITE_PATH_AUDIT.md` `6fa4439d…` |
| Amount representation | **Newly mapped.** The `turnover` alias binds on no inspected frame; three of six inspected paths construct `ready` bars with a null `amount` | `M2B_AMOUNT_REPRESENTATION_AUDIT.md` `cecc8c7a…` |

---

## 3. The dependency table

Categories are kept apart deliberately: **E** = missing evidence · **P** = a user policy
choice · **I** = an engineering implementation gap · **O** = operational proof that cannot
exist without an authorized run. Nothing advisory is promoted to a blocker here.

| # | Unresolved proposition or deliverable | Evidence already available | Still missing | What would settle it | Blocks | Authorization needed |
|---|---|---|---|---|---|---|
| **D1** | A staging/copy backfill exists, with before/after manifests, coverage, rejected rows and lineage (goal `:181-182`) | M1's gate implementation (`_m1_closure/`); the cache write-path map | **O** — no staging run has occurred; no manifests exist | An authorized staging run producing those artifacts | **The full corpus.** Nothing else | Explicit user authorization for a staging backfill, scoped and separate from any promotion |
| **D2** | The validated build produces self-consistent capture evidence | Two historical captures, both FAIL; `EV2` bytes-to-text passes on all five bodies | **O** — no same-version live capture | One authorized run with a **defined end-to-end acceptance objective** (memo §5, T1–T4) | **Source capability** | A new explicit one-run authorization. **Not requested here**, and **never** to clear `EV6` |
| **D3** | Vendor basis is decided rather than `unverified` | The full necessary-condition set (`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §3.3); G1 actions; G3/U-6 ratio behaviour | **P** for U-1…U-5 and U-7's semantics — *decidable on evidence in hand* (`:442`); **E** for U-6 and any index basis assertion — *"no available observation can settle it"* (`:443-444`) | A user decision on U-1…U-5/U-7; for U-6, evidence that does not currently exist | **Basis-dependent boundary-2 use.** Not source capability, not the corpus | Policy decision only. No acquisition permission is implied by deciding to seek evidence |
| **D4** | A record can ever evaluate `eligible = true` | `basis_record.py` `0fda4f7e…`, validated for its hashes; 41/41 exit 0 | **I** — see §5.1: `evaluate()` returns a **hard-coded** `False`; there is no branch to enable | An adopted sufficiency rule **and** a separately reviewed evidence-validation rule **and** an implementation change | Any positive eligibility path | Policy (U-6) **plus** a separate implementation authorization. Adopting U-6 alone would change nothing |
| **D5** | Adjustment is consistent through the entire interval (goal `:184`) | G1 official actions for two stocks; G3 ratio analysis; the U-6 study's per-interval feasibility | **E** at corpus scale — evidence covers 2 stocks + 1 index, one capture | Coverage evidence across the actual symbol set and interval, from an authorized run | **The full corpus.** Also gates D1's acceptance | The same authorization as D1 |
| **D6** | Denominator definition and freshness | The retained auxiliary series; ages; the zero-interruption rule | **E** — the vendor declares neither the definition (total / free-float / A-share) nor freshness | Vendor documentation or an independent reference; **not** obtainable by re-fetching a change-event endpoint | **Only an optional future consumer** | None required to leave it open |
| **D7** | Turnover used / annotated / withheld | The full consumer map; no wired consumer of the retained measure | **P** — a policy choice, with nothing currently depending on it | A user decision | **Nothing.** Choosing "withheld" closes none of P1, U-6, capability or M2 | None. Any *implementation* would need its own scope review |
| **D8** | Null-`amount` bars stored `ready` | Three of six inspected paths construct that shape; M1's `chk_units` quarantines the stock case; benchmarks are excluded by design | **P** on the semantics, **I** on where the flag is computed (`daily_bar_cache.py:195`/`:204-205`, propagated at `:213-214`) | A policy decision on the semantics, then a scoped implementation | **Corpus quality fields** — a D1 acceptance concern, not capability | Policy decision, then separate production authorization |
| **D9** | Temporal stability; BJ generalization beyond one symbol | One complete observation, one instant, one BJ path | **E** — a second observation on a different trading day; the other six `bj_code_history` symbols | A run under memo T2, understanding that it yields **an additional observation, not a stability proof**; more symbols need separate scope review | **Source capability** confidence, and D5's breadth | A new one-run authorization; symbol expansion is **outside** the existing boundary |
| **D10** | C4 orphan share-dates; B3 `prevclose` mismatches | The retained counts | **E** — no explanation | Vendor behaviour evidence or a wider sample | **Nothing today.** Advisory; *"would matter at pilot scale"* | None |
| **D11** | Corpus-safety of the write surface before any backfill | The cache write-path audit: `reset_knowledge` full-table delete over 71 tables, the demo-seed `INSERT OR REPLACE`, the batch guard and its pre-`executemany` deletes | **I/P** — whether those paths are acceptable during a staging backfill has not been decided | A design decision recorded before D1 runs | **D1's safety**, not its permission | Decided as part of the D1 design; implementation separately authorized |

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
* **Database contents.** Every audit in this workstream is static. Write *eligibility*, an
  *attempted* write and *durable contents* are three different things; only the first has
  been evidenced, and no database has been opened.
* **The historical `EV6` failures.** They are a code-version disagreement, permanently
  recorded. A future run produces a separate result; matching classifications there merely
  emit no `EV6` entry, which is not a pass.

---

## 5. Useful work possible **now**, from named existing files

### 5.1 One trace completed in this task, because it changes the map

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

### 5.2 Candidates that would change a decision

| Candidate | File(s) | Question a short static read answers | Decision impact |
|---|---|---|---|
| **W-1** | `_m1_closure/staging_gate.py` (`7152d773…`) and the **five** further check functions it imports at `:63-65` from `acceptance_runner.py` (`59b67c18…`) — only `chk_units` has been read | What acceptance evidence the M1 gate already computes (dates, symbols, prices, duplicates, provenance) | Tells D1 whether the goal's `:182-183` acceptance evidence has an existing implementation to inherit, or is an implementation gap. **Directly sizes D1** |
| **W-2** | `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §3.6, *"Code locations a future implementation would touch"* (`71e0dc52…`) | The engineering surface behind each U-5 storage route | **Sizes the U-5 alternative** so the D3 policy choice is made with its cost visible |
| **W-3** | The retained auxiliary bodies `raw/02_…bin`, `raw/05_…bin` | The vendor's own field spelling and entry count, read from the bytes rather than through `checks.json` summaries | Minor; sharpens D6's statement of what the vendor does and does not declare |

### 5.3 Work that would **not** advance anything

Re-running validated suites; re-auditing accepted findings; another alias or token sweep;
any further model fit over the same price windows; restating known limits in new prose.
**None of these is proposed.**

### 5.4 Bound

This is an assessment of candidates **identified in the inspected scope**. It is **not** a
claim that every file on disk has been examined. If W-1 and W-2 are completed and nothing
further emerges, the next dependency is external and unambiguous: **D1's staging
authorization**, or **D3's policy decision**, or **D2's one-run objective** — not more
offline analysis.

---

## 6. Consolidated user decisions, in priority order

Each is stated as alternatives with implications. **No option is chosen here**, no
threshold is set, no blanket permission is sought, and no capture command, configuration or
run directory is prepared. **Deciding to seek evidence is separate from authorizing its
acquisition; a production design choice is separate from permission to implement it.**

| Priority | Decision | Alternatives | Implication | Acceptance evidence at that boundary |
|---|---|---|---|---|
| **1** | **U-1 … U-5, U-7 semantics** (D3) | (a) decide now on evidence in hand — the proposal calls these decidable at `:442`; (b) defer with P1 open | (a) unblocks a boundary-2 basis contract and makes the U-5 storage route costable; (b) leaves every basis-dependent use blocked | A recorded decision per item, plus a contract revision reviewed against it. **No code change implied by deciding** |
| **2** | **Whether M2 proceeds by staging backfill at all** (D1) | (a) authorize a scoped staging/copy backfill; (b) hold; (c) redefine M2's scope | (a) is the **only** route to the goal's `:181-185`; (b) leaves M2 permanently incomplete by its own criteria; (c) is a goal change, not a technical step | Before/after manifests, counts, hashes, coverage, rejected rows, lineage — and no `ERROR` or duplicate keys in the research view |
| **3** | **Whether a third capture is authorized, and for what objective** (D2, D9) | (a) authorize one run with a **defined end-to-end acceptance objective** (T1) or a different trading day (T2); (b) do not | (a) yields same-version evidence as a by-product; (b) leaves source capability unresolvable. **Neither erases `EV6`**, and no run is requested here | The run's own outcome table and check table under the existing three-layer contract; a FAIL is an acceptable, informative outcome |
| **4** | **U-6, and whether an eligibility path is built at all** (D4) | (a) adopt a sufficiency rule **and** separately authorize the evaluator change; (b) adopt nothing and keep `unverified` fail-closed | U-6 is **evidence-blocked** (`:443`); and per §5.1 adopting it alone changes no behaviour, because no branch exists | An adopted rule, a reviewed evidence-validation rule, and a re-reviewed module at new hashes |
| **5** | **Corpus-safety design before any backfill** (D11) | (a) constrain or isolate the destructive write paths for the staging run; (b) accept them as-is with the risk recorded | Affects whether a backfill can silently remove or replace stored rows | A written design plus a re-audit of the write paths against it |
| **6** | **Null-`amount` semantics** (D8) | (a) make a stock bar with no usable amount distinguishable; (b) leave it `ready` | (a) touches production ingestion and can change guard outcomes; (b) preserves today's behaviour and today's silence | A stated intent for the `:465-477` clause and the `:502-521` deletes, validated against that intent |
| **7** | **Turnover policy** (D7) | used / annotated / **withheld** | **Withheld is the current state and costs nothing.** Nothing depends on this choice today | None required to leave it as-is |

**Proposed sequence, not a schedule and not a request:** decide 1 → complete W-1/W-2 to
size 2 and 5 → decide 2 → decide 5 and 6 as part of 2's design → treat 3 on its own merits
if and when a defined objective exists → 4 only if a basis-dependent consumer is actually
wanted. **7 needs no action.**

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
| `_m2_smoke/basis_record.py` | `0fda4f7effba73ac04a8f10ce35b686a7a646a741650159f55cd9288b6bd2cc7` | §5.1 (`:727-798`) |
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
| `_m1_closure/staging_gate.py` | `7152d773ea9ca9778c0f038cf9caaf7be36119c7d0cc059de80821d53ff35b7f` | W-1 |
| `_m1_closure/acceptance_runner.py` | `59b67c18ed714f9e074d20d8ac8d9d68e0258ed259cd07c0ec60a36e45c5e9ad` | W-1 |
| `_m2_smoke/revision_20260908T082833Z_r2abc_v2/checks.json` | `b6c97eab21254b837f3bd1768eec22c8a54ec925da82beb0f12810156f42d387` | §2, §3 window facts |

**Limits.** This map reconciles the documents and code named above at those bytes. It is
**not** a claim that every project file was consulted; §5.4 states the bound. Nothing here
observes runtime behaviour or database contents.

**Preservation.** No existing file was modified, moved, renamed or deleted; the only write
is this document. Every accepted audit, acceptance report and Codex review listed above is
unchanged, as are the retained captures, revisions and producers. Verification accompanies
the handoff.

**Stop: `proposed for review`.**
