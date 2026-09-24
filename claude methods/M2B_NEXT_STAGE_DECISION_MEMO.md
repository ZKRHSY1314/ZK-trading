# M2b next-stage decision memo — is a third capture justified?

> **Status: `proposed for review`.** Offline planning only, written from the current code,
> the retained evidence and the existing request. **No HTTP or plugin call, no capture, no
> SQLite open, no production mutation, no service operation, no token access, no
> dataset/strategy/knowledge edit, no pilot, no training, no source expansion, no Git
> staging/commit/push, no live trading.** Local and uncommitted.
>
> **Planning authorizes nothing.** Both boundary-1b authorizations remain **consumed**.
> This memo does not establish source-capability acceptance and does not request a run.
> Date: 2026-09-08. Revision 3 — R1–R3 of `M2B_NEXT_STAGE_MEMO_CODEX_REVIEW.md` closed in
> revision 2; this revision addresses the two remaining items (Annex A alignment, and the
> `EV6` clearing claim). See the resolution table at the end. Sources: `_m2_smoke/evidence_20260908T021722Z/`,
> `evidence_20260908T082833Z/`, `revision_20260908T082833Z_r2abc_v2/`,
> `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md` §§6, 20–25, and the current five producer
> hashes.

## Recommendation, up front

**Defer a third capture.** This is a **marginal-value versus risk judgement**, not a claim
that nothing remains to verify. One genuine end-to-end question **does** remain: the
validated implementation has never produced its own live capture, so it has never been
observed generating capture-time evidence that is self-consistent with what the checks
later read (Section 3). Against that: within the three-symbol, five-request boundary every
check the boundary was designed to produce has now been produced on retained bytes, the
implementation delta in the capture path is one call site, and the open questions in
Section 2 are mostly not reachable by repeating those same five requests. The expected
marginal information is therefore low relative to the cost and the vendor-facing risk of
another live run — **but not zero**, and the judgement is the user's.

**A capture must not be authorized because of the historical `EV6`.** That is a version
gate over two past runs — a matter no future run can undo, since a later capture produces a
separate result and leaves those two exactly as they are. It is equally true that this memo
does **not** rule out a future one-run authorization with a **defined end-to-end acceptance
objective**; Section 5 names the conditions under which one becomes justified.

---

## 1. What is already established

All of the following is measured on retained bytes and reproducible offline. The corrected
implementation was **technically validated by Codex on 2026-09-08** in a bounded offline
scope (`M2B_R2ABC_CLOSURE_CODEX_REVIEW.md`), bound to the five producer hashes
`059d0c43…`, `4b062a55…`, `5bbb6ef0…`, `c6d736b1…`, `23b917c5…`.

**The capture pipeline ran end to end, historically, under the frozen build.** Run
`20260908T082833Z` issued **all five** requests, HTTP 200 each, **5 attempts against a
ceiling of 15**, no retries, `run_status: completed`, armed at 16:27:57 Asia/Shanghai
inside the operator window. Two timing figures, not one: the capture deadline recorded in
the manifest elapsed **6.906 s** of its 900 s budget, and the console's end-of-run figure
for the whole pipeline is **7.5 s**, of which finalization took **0.594 s** against its own
separate 120 s budget.

**Source identity and grammar.** `KLC_K2_<sym>` (stock history), `KLC_KL_<sym>` (index),
`KKE_ShareAmount_<sym>` (auxiliary), each validated as a **complete** name against the
expected exchange and symbol. Decoder branch dispatch confirmed on real bodies: `SH600011`
5,935 rows branch O, `SH000300` 5,987 rows branch D, `BJ920000` 1,393 rows branch O.

**`SH600011` semantics, measured rather than assumed.** Volume unit `share` (`U2`),
currency yuan with an amount ratio ≈ 1.00 over 10 sessions (`U3`), positive volume and
amount on every research row (`U1`), OHLC ordering intact (`D4`), coverage
2001-12-06 → 2026-09-07 complete against the window (`C1`).

**`BJ920000` is answered for the first time.** `pre_boundary_history_served` — its history
endpoint serves pre-2024-08-13 data under the `92xxxx` code.

**`SH000300`.** Full served series 5,987 rows, 2002-01-04 → 2026-09-07; coverage complete
(`C3`); the index interface takes no date arguments, which the checks now model separately
from the stock interface.

**The auxiliary series.** 26 entries for `SH600011`, 42 for `BJ920000`, parsed from the
real object-array envelope as data. The field the vendor calls `amount` is **outstanding
shares in 万股** (×10,000 → shares), not traded amount, and is renamed at the boundary so
the distinction cannot be lost. `BJ920000`'s two genuine zeros (2015-03-06, 2015-09-15) are
preserved with their reason and never used as a denominator.

**Adapter replay on the retained bytes.** Both stocks return **978 rows,
2022-08-24 → 2026-09-04**; the index returns **5,987 rows, 2002-01-04 → 2026-09-07**; only
captured URLs were requested; no production database was opened.

**Denominator validity and date validation are corrected and validated.** An explicit zero
now interrupts denominator validity until a later valid observation, matching the installed
`ffill`; `R1` requires an actual date sequence consistent with row count and first/last
metadata, with the declared stock window applied to the stock interface only.

**Where that leaves the check table.** In `revision_20260908T082833Z_r2abc_v2/`: **71
checks — 58 PASS, 2 FAIL, 8 ADVISORY, 3 FINDING, and zero INCONCLUSIVE.** Both FAILs are
`EV6` (Section 3). Per job: `sh600011` FAIL, `sh000300` **PASS**, `bj920000` FAIL;
capability **FAIL**. *This describes the current check set applied to these retained inputs
— it is not proof that every question worth asking is covered by that set.*

**Preservation.** Both captures, all three earlier revisions plus this one, both receipt
sets, the frozen D1/D2 bundle and every reviewer artifact are byte-identical and were
verified so during each round.

---

## 2. What remains substantively unverified

### 2.1 The P1 basis label is an undecided contract — not a demonstrated need for new inputs

**The candidate P1 evidence already exists and already passed.** §6 of the request names it
exactly, and these are the retained results:

| Evidence | Retained result | What it does **not** establish |
|---|---|---|
| `S1` — the planned URL set equals the installed adapter constants | **PASS** ×3; the recorded sets contain the klc history URL and (stocks) the auxiliary URL, and no factor endpoint | that the vendor's klc series is itself unadjusted — only which URLs this plan uses |
| `B1` — no factor endpoint requested | **PASS** (run-level), measured `[]` | that no factor exists upstream; only that this run fetched none |
| `B2` — code-derived from the installed `stock_zh_a_sina.py` (`a3acc946…`): hfq **multiplies** by its factor, qfq **divides** by its factor, `adjust=""` applies neither | **PASS** (run-level) | anything about the vendor's series; it is a property of the *adapter's* transformations |
| `R1` — adapter replay with `adjust=""` | **PASS** ×3 (978 / 978 / 5,987 rows) | that the replayed series is unadjusted at source; only that no adjustment was applied by us |
| `I2` / `B4` — ratio behaviour against the anchored qfq reference | `I2` **PASS** ×3, ten ratios all `1.0`, `step_date: null`, sources recorded; `B4` **ADVISORY** ×3, `step_date: null` | see the correction below — a **flat** ratio does not discriminate |
| `B3` — `prevclose` markers | **ADVISORY**; `SH600011` 24 rows carry `prevclose`, 23 differ from the previous close | **explicitly not P1 evidence** — a decode-format observation |

**Correcting `B4`.** An earlier draft of this memo read `B4` as "a flat close ratio is
evidence that the live series is unadjusted". That is not what `smoke_checks.py:1319` says.
Its actual claim: **the retained ratio is flat**, and *if a step appeared* it would be
**limited evidence** — not proof — that the live series is unadjusted relative to the
cached qfq series, the limit being that the cached reference mixes fetch times. With
`step_date: null` on all three symbols, the discriminating observation simply did not occur
in the compared segment. A flat ratio at the anchored tail is also what one expects
anyway, because the cached qfq tail is re-anchored at every refresh.

**What P1 actually is.** Per G7 of the request: M2a's `provenance.derive` corroborates a
basis **declared by the response**, and the real Sina payload declares none, so every real
series would be `unknown` by construction. Closing P1 needs a **defined corroboration
substitute** — deriving the basis from the adapter code path (`B1`/`B2`) instead of a
response field — plus a code change outside M2a. That is a **labeling and corroboration
contract that has not been adopted or implemented**. It is *not* established that new
endpoints or a replacement reference extract are required to decide it.

**If more evidence is wanted, the specific unsupported proposition is:** *"the live klc
series is unadjusted over a span that contains at least one corporate action."* The only
observation in the current design that would discriminate is a step in
`close_live / close_local` at a known ex-date, and the compared ten-session tail contains
none. How to obtain such a span — for example by widening the comparison window against the
**existing** reference, which needs no new endpoint — is part of the P1 design decision.
**This memo neither decides P1 nor assigns any basis label.**

### 2.2 Denominator carry-in age — an observation, with freshness not independently verified

The retained `SH600011` auxiliary series ends at **2019-10-15**, so every in-window research
row resolves to that observation: carry-in age **median 1,975 days, maximum 2,516 days**
(6.9 years) at the window end. `BJ920000` is much shorter — median 173, maximum 511.

Three things must stay separate:

1. **Known validity interruptions — proven.** `BJ920000` reports zero on 2015-03-06 and
   2015-09-15; both intervals close at the first positive observation, 2015-10-27. These
   are genuine unusable states, preserved with their reason, never used as denominators.
2. **Source freshness and completeness — not independently verified.** This is a
   **change-event** series: the absence of a newer event does **not** by itself show the
   carried value is wrong or that the series is incomplete. Without independent evidence of
   a share-count change, long carry-in is a **reason for uncertainty, not a finding of
   invalidity**. Nor can it be asserted that a future fetch would return the same 26
   entries.
3. **Downstream usage policy — undecided, and not decided here.** Whether turnover is used,
   used with a staleness annotation, or not used is a design decision for the next stage.
   **No expiry threshold, metric change or discard decision is proposed or made in this
   memo.**

**`U4` is ADVISORY.** Its retained measurement is 728 aligned research rows, **0** rows
without an applicable observation, **0** rows exceeding the threshold. That is an advisory
observation about internal consistency — it is **not** a PASS certifying turnover for
downstream use.

### 2.3 Other open items

* **Temporal stability rests on n = 1.** One complete observation exists, at one instant on
  one trading day. Whether the auxiliary object-array shape, `BJ920000`'s pre-boundary
  service and the index's absent `amount` persist is unknown. A second capture on a
  different trading day would supply an observation at a different time; that is **not**
  automatically a proof of statistical independence or of stability.
* **The cause of `BJ920000`'s pre-boundary service is not established** (`C2` FINDING), and
  the result does **not** generalize: exactly one BJ path was contacted, and the other six
  `bj_code_history` symbols remain uncertain with the frozen manifest unchanged. Answering
  them means expanding the symbol set — outside this boundary and requiring separate scope
  review.
* **Two unexplained post-processing asymmetries.** `C4`: **4** share dates for `SH600011`
  (first usable 2001-12-06) and **17** for `BJ920000` (first usable 2015-10-27) have no
  corresponding klc row. `B3`: the `prevclose` mismatches above. Neither is a failure; both
  are unexplained and would matter at pilot scale.
* **No same-version live capture exists** — Section 3.
* **Entirely out of scope and untouched:** corpus, features, labels, strategy, the
  52-symbol pilot, production ingestion, promotion and training.

---

## 3. Three states that must not be conflated, and the historical `EV6`

### 3.1 What `EV2` covers, and only that

`EV2` (`smoke_checks.py:828`) compares `sha256_text(bytes_to_text(retained_bytes,
recorded_encoding))` with the `text_sha256` the capture recorded. It establishes exactly
one thing: **the retained bytes convert to the same text the capture saw.** It says nothing
about whether the updated **capture → classifier → manifest → checks** path has executed in
a real capture.

### 3.2 The three states

| | Status |
|---|---|
| **Historical live execution** | Done, under the **frozen** build `0ed93f05…` et al.: transport, pacing, attempt accounting, the outcome table, the evidence store, finalization, retention and replay all ran on a complete five-request run. |
| **Current offline validation** | Done: the validated build passes on the retained bytes, technically validated by Codex in that bounded offline scope. |
| **Same-version live capture** | **Absent.** The validated implementation has never produced its own capture evidence. In `smoke_capture.py` the delta is a single call site — the classification call now passes `expected_symbol` and `instrument_class` — but the classifier, outcome mapping and checks it invokes have all changed. |

The third row is a **real end-to-end question**, not milestone bookkeeping: whether this
implementation, run live, records classifications self-consistent with what its own checks
read. `EV2` does not answer it, and neither does "zero INCONCLUSIVE", which describes the
current check set on these retained inputs only.

### 3.3 The historical `EV6` disagreement

`EV6` is emitted **only when the capture-recorded classification differs from the current
one** — it is a FAIL-only check, so a capture that agrees produces no `EV6` entry at all.
In run `20260908T082833Z` the frozen build recorded requests **2** and **5** (the
`sh600011` and `bj920000` auxiliary bodies) as `undecodable`; the validated build reads the
same bytes as `decoded`. Run `20260908T021722Z` is in the same position: its two issued
requests were recorded `ok / undecodable` under the pre-D1 decoder.

It is not tampering or byte drift — `EV2` passes on all five bodies and every input hash
matches. It is a **code-version disagreement**, which is what `EV6` exists to surface. It is
**historical and immutable**: no offline work can clear it, **and no future run can clear it
either** — a later capture yields a separate result and leaves these two untouched. It
**has not been waived**, neither capture's FAIL has been rewritten, and neither the
superseded revision nor the old reviewer has been edited to turn green. Consequently **any
capability verdict computed from either retained capture is capped at FAIL by design** —
and that fact alone is not a reason to capture.

---

## 4. Weighing it

**For deferring.** Within the boundary, every check it was designed to produce has been
produced: zero INCONCLUSIVE, and every required check except `EV6` passes for all three
symbols. The open items in §2.1–2.3 are mostly unreachable by repeating these five
requests — P1 is a design decision, the share-series freshness question cannot be resolved
by re-fetching an endpoint that reports change events, the BJ cause and the other six
symbols are out of boundary. The capture-path delta is one call site, and `EV2` shows the
bytes-to-text step was already exact. A live run carries vendor-facing risk and consumes a
scarce authorization.

**Against deferring.** The same-version live capture is genuinely absent (§3.2), and both
prior runs failed on exactly that class of defect — capture-time parsing — each invisible
until live bytes arrived. A capability verdict under the validated implementation can only
ever come from a live run, so M2b cannot be completed without one eventually.

**Balance.** Low expected marginal information now, non-zero residual risk, and a scarce
authorization argue for deferring **until the run has a defined end-to-end acceptance
objective** rather than being spent to close a version gate. That objective is most cheaply
obtained together with the boundary-2 design (Section 5, T1), so one run then answers a new
question *and* produces same-version evidence.

**Recommended next work — all offline, all within existing scope, none of it authorized by
this memo:**

1. Decide the **P1 labeling/corroboration contract** on its merits (§2.1), including
   whether the discriminating span can be obtained from the existing reference. This is the
   actual blocker for boundary 2.
2. Decide the **downstream policy for turnover** given §2.2 — used, annotated, or not used
   — without changing any metric definition here.
3. Draft the **revised M2 / boundary-2 request** and let it state which endpoints and
   fields it needs. If it needs something never captured, a capture becomes justified on
   its own merits and the same-version evidence follows as a by-product.

---

## 5. Named conditions that would justify a capture

A capture becomes justified when **any one** of these holds. None holds today.

| # | Condition | The question it answers |
|---|---|---|
| T1 | The boundary-2 request is drafted and needs an endpoint or field this boundary never captured, or a defined end-to-end acceptance objective for the validated implementation is set | What does that endpoint serve / does the current implementation produce self-consistent capture evidence? |
| T2 | Cross-day observation is deliberately adopted as an objective, on a **different trading day** — accepting that this yields an additional observation, not a stability proof | Do the payload shapes, `BJ920000`'s pre-boundary service and the index's absent `amount` recur? |
| T3 | The capture or classification path changes again in a way `EV2`'s bytes-to-text equivalence cannot cover | Does the capture record what the checks will read? |
| T4 | The vendor is observed or reported to have changed a payload format or endpoint | Does the pinned grammar still hold? |

**Clearing the historical `EV6` is not a condition — and is not something any run can
do.** The two retained captures keep their `EV6` failures permanently. A run authorized
under T1–T4 produces a **new, separate** result: if that run's recorded classifications
match what its checks read, its own result simply contains no `EV6` entry — which is not a
pass, and says nothing about its other checks, which may still fail. Historical evidence is
added to, never rewritten.

---

## Annex A — the unchanged terms, if the user decides otherwise

**This annex is not a request and not a recommendation.** It restates the terms already
reviewed, and summarises the **existing** outcome and aggregation contract rather than
creating rules. Nothing is armed.

**Authorization.** A fresh explicit **one-run** user authorization is required, naming the
three symbols, the five requests, local-only retention, and **read-only** access to
`trading_local.sqlite3` for the frozen reference extract. Both prior authorizations are
consumed and neither extends. **New endpoints or additional symbols are not covered by this
annex and require separate scope review.**

**Boundary and limits, unchanged.** `SH600011`, `SH000300`, `BJ920000`; five requests;
global attempt ceiling `CEILING = 15`; pacing `MIN_INTERVAL = 1.5 s`; concurrency 1; finite
timeouts; sticky 403/429 abort; 15-minute wall-clock cap; operator window **before 09:15 or
after 15:30** Asia/Shanghai, verified by hand — `--plan` reads no clock, so a green
pre-flight does not establish timing compliance. A clean run consumes **at least ~6 s** of
the 900 s budget.

**Bounded retries are not a second run.** `transport.MAX_ATTEMPTS_PER_JOB = 3` bounds
attempts **per request**, so a two-request stock job may consume up to 6 of the global 15;
403/429 abort the run and are never retried; a TLS failure is never retried; a 3xx is
refused rather than followed. All of that happens **inside one authorized run**. **A failed
or aborted run does not license another capture** — a further run needs a new explicit
one-run authorization.

**Evidence requirements.** Exactly the §21 report structure: run identity and honesty header
with both clocks; verbatim F1–F8 including the process-inventory counts; the per-request
wire record; the outcome table; the check table split by evidential weight with absent
checks listed as absent; the four questions answered or not; per-job and capability
verdicts; the offline replay hash and `db_guard` confirmation; preservation anchors; and
limitations.

**Three layers, and they must not be collapsed.** The code decides in this order:
`smoke_outcomes.OUTCOME_TABLE` (one **request**) → `smoke_outcomes.aggregate_job` (one
**job**, by request kind) → `smoke_checks.summarize` (per-job verdicts, then **one**
capability verdict). This annex summarises that existing contract; it creates no rule.

**Layer 1 — the request outcome**, keyed by `(transport_state, payload_state)` and read by
both capture and the checks:

| transport / payload | request result | row job result | evidence class | skips the rest | aborts the run |
|---|---|---|---|---|---|
| `ok / decoded` | `OK` | `CONTINUE` | `decoded_payload` | no | no |
| `ok / markup`, `ok / empty` | `BAD_PAYLOAD` | `INCONCLUSIVE_PAYLOAD` | `inconclusive_payload` | yes | no |
| `ok / undecodable`, `ok / no_rows` | `BAD_DECODE` | `INCONCLUSIVE_DECODE` | `inconclusive_decode` | yes | no |
| `vendor_not_found` (404/410 only) | `VENDOR_ABSENT` | `NOT_SERVED_AT_PATH` | `vendor_explicit_absence_at_path` | yes | no |
| `vendor_stop` (403/429) | `STOP` | `FAILED` | `run_aborted_vendor_stop` | yes | **yes** |
| `exhausted_retryable`, `non_retryable_status`, `redirect`, `tls_failure`, `transport_error` | `FAILED` | `FAILED` | `inconclusive_transport` | yes | no |
| `aborted` | `ABORTED` | `FAILED` | `run_aborted` | yes | **yes** |
| `skipped` | `SKIPPED` | `CONTINUE` | `skipped` | no | no |

Those eight are the **only** evidence classes. There is **no `inconclusive_auxiliary`
evidence class**: `INCONCLUSIVE_AUXILIARY` is a *job* result produced by `aggregate_job`
and is never a property of a request. (`JOB_INCONCLUSIVE_TRANSPORT` exists in the
vocabulary but no row uses it — transport failures carry evidence class
`inconclusive_transport` with row job result `FAILED`.)

**Layer 2 — `aggregate_job`, by request kind.** The same request outcome means different
things depending on which request produced it:

| Situation | Job result |
|---|---|
| no history request recorded for the job | `FAILED` |
| the **history** row's job result is not `CONTINUE` — transport failure, TLS, refused redirect, vendor stop, run abort, markup/empty, undecodable/no rows, or 404/410 | that row's job result **stands**: `FAILED`, `INCONCLUSIVE_PAYLOAD`, `INCONCLUSIVE_DECODE` or `NOT_SERVED_AT_PATH` |
| the **history** request was not issued — whether skipped run-globally after an abort, or skipped with no trigger | **`FAILED`** in both cases, with different recorded notes; the job cannot PASS either way |
| history decoded and the instrument has no auxiliary request (the index) | `CONTINUE` |
| history decoded and the auxiliary request decoded | `CONTINUE` |
| history decoded, but the **auxiliary** request **aborts the run** (vendor stop or run abort) | **`FAILED`** — never softened into auxiliary evidence |
| history decoded, auxiliary **skipped run-globally** because the run aborted first | `INCONCLUSIVE_AUXILIARY` |
| history decoded, auxiliary **skipped with no trigger** | **`FAILED`** — an unexplained skip is a contradiction |
| history decoded, **ordinary auxiliary failure**: transport failure, explicit 404/410, markup/empty/undecodable/no rows | `INCONCLUSIVE_AUXILIARY` |

So a transport failure on the **history** request fails the job, while the same failure on
the **auxiliary** request, after history decoded, is `INCONCLUSIVE_AUXILIARY`: the history
checks still run on the received body, so an invalid history is still found, and the missing
auxiliary evidence can never become a PASS or an absence finding. Only the **KLC history**
request's explicit 404/410 can ever yield `NOT_SERVED_AT_PATH`.

**Layer 3 — `summarize`.** Per job:

* `CONTINUE` or `INCONCLUSIVE_AUXILIARY` → the job's **required** checks are consulted, in
  this precedence: any required **FAIL** → **FAIL**; else `INCONCLUSIVE_AUXILIARY` or any
  required INCONCLUSIVE → **INCONCLUSIVE**; else **PASS**.
* `NOT_SERVED_AT_PATH` → carried through as `NOT_SERVED_AT_PATH`.
* `FAILED` → **FAIL**.
* `INCONCLUSIVE_PAYLOAD` / `INCONCLUSIVE_DECODE`, or any other job result → **INCONCLUSIVE**.

**Required-check FAIL precedence applies only in the first branch.** For a `FAILED`,
`NOT_SERVED_AT_PATH` or payload/decode-inconclusive job the aggregated job result decides
and the required checks are not re-consulted.

Then the single capability verdict, in order:

1. any **run-level** check FAIL → **FAIL**; otherwise any run-level check INCONCLUSIVE →
   **INCONCLUSIVE**.
2. each job in `JOBS` order — `sh600011`, `sh000300`, `bj920000` — a per-job **FAIL** sets
   **FAIL**; a per-job INCONCLUSIVE sets INCONCLUSIVE only while the verdict is not already
   FAIL; `NOT_SERVED_AT_PATH` from any job **other than `bj920000`** sets **FAIL**.
3. **the BJ exception:** `NOT_SERVED_AT_PATH` from `bj920000` raises the verdict to
   `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` **only if the verdict is exactly PASS at that
   point**. It requires an explicit **404/410 on `bj920000`'s KLC history request** — a
   404 on its auxiliary endpoint gives `INCONCLUSIVE_AUXILIARY` instead. `bj920000` is
   evaluated **last**, so any earlier FAIL or INCONCLUSIVE has already been recorded and
   the exception does not apply; a later FAIL would overwrite it. It can mask nothing, its
   **cause is not established**, and it authorizes nothing.
4. `run_status != "completed"`: a vendor-stop abort → **FAIL**; otherwise, if not already
   FAIL → **INCONCLUSIVE**, which also downgrades
   `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`.

**Overall FAIL precedence holds throughout:** once the verdict is FAIL nothing raises it,
and the code's own verdict note records that even
`PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` "is not an unqualified PASS and authorizes nothing".

**Success / failure criteria for any future run are exactly the above**, not a separate
scheme: PASS requires no run-level FAIL or INCONCLUSIVE **and** all three jobs at per-job
PASS. **A FAIL is an acceptable outcome that produces findings, not an escalation.** No
verdict authorizes the 52-symbol pilot, production ingestion or training.

**`EV6` in a new run.** `EV6` is raised only where a capture-recorded classification differs
from the current one. So **within that new run's own result**, matching classifications
simply produce no `EV6` entry — which is not a pass, and says nothing about its other
checks, which may still fail and would then decide the verdict by the layers above. The two
retained captures' `EV6` failures are untouched by any of this.

**Preservation rules.** A fresh UTC `run_id` (never reusing `20260908T021722Z` or
`20260908T082833Z`); new `evidence_<run_id>/`; any offline re-check in a **new** separately
versioned revision directory with producer and input hashes; the current five producer
hashes frozen into a new bundle and verified before arming, so what runs is what was
validated; every existing evidence, revision, receipt, frozen and reviewer artifact
byte-identical, verified before and after; nothing staged, committed, pushed or uploaded;
no service started or stopped, no endpoint substituted, no symbol added, no production
write.

---

## Revision record

### Revision 3 — the two remaining items

| # | Finding | Resolution |
|---|---|---|
| 1 | Annex A did not match `OUTCOME_TABLE` / `aggregate_job` / `summarize`; it invented an `inconclusive_auxiliary` **evidence class**, collapsed request outcomes into job results, and inherited an incomplete transport shorthand | Annex A rewritten as **three explicit layers**. Layer 1 reproduces the request-level table with its eight — and only eight — evidence classes, noting that `INCONCLUSIVE_AUXILIARY` is a job result and never a request property, and that `JOB_INCONCLUSIVE_TRANSPORT` is defined but unused. Layer 2 gives `aggregate_job` by request kind, distinguishing a **history** transport failure (`FAILED`) from the same failure on the **auxiliary** request after history decoded (`INCONCLUSIVE_AUXILIARY`), an auxiliary request that **aborts the run** (`FAILED`), a **run-global** auxiliary skip (`INCONCLUSIVE_AUXILIARY`), an **unexplained** auxiliary skip (`FAILED`), and both history-skip cases (`FAILED`). Layer 3 states the per-job mapping with **required-check FAIL precedence confined to the `CONTINUE` / `INCONCLUSIVE_AUXILIARY` branch**, then the capability order with **overall FAIL precedence**, the BJ exception reachable only from an exact PASS with `bj920000` evaluated last, and the `run_status != completed` downgrade. No rule invented; no code changed. |
| 2 | The memo said a future run would clear the historical `EV6` | Removed everywhere. The recommendation, §3.3, §5 and Annex A now state that the two retained captures' `EV6` failures are **permanent and cleared by nothing**; a separately authorized run produces a **new, separate** result in which matching classifications merely emit no `EV6` entry — not a pass — while its other checks may still fail. Historical evidence is added to, never rewritten. |

### Revision 2 — R1–R4 of `M2B_NEXT_STAGE_MEMO_CODEX_REVIEW.md` (R1–R3 closed)

| # | Finding | Resolution in revision 2 |
|---|---|---|
| R1 | `B4` misquoted; existing candidate P1 evidence omitted; "undecided" escalated to "undecidable in this boundary" | §2.1 rewritten: `B4` restated (retained ratio **flat**, `step_date: null`; a step *would be* limited evidence, not proof), the full `S1`/`B1`, `B2`, `R1`, `I2`/`B4` candidate set tabulated with retained statuses and what each cannot establish, `B3` marked explicitly not P1 evidence, P1 framed as an **unadopted labeling/corroboration contract** per G7, and the one unsupported proposition named. New endpoints / a replacement reference are **not** claimed necessary. P1 is not implemented and no basis label is assigned. |
| R2 | Carry-in age presented as proof the share count is stale at the source; `U4` implied to certify turnover | §2.2 rewritten: age reported as an observation with **freshness and completeness not independently verified**; the three concerns separated (known validity interruptions / source-freshness uncertainty / downstream policy); the claim that a re-fetch would return the same 26 entries removed; `U4` stated as **ADVISORY** with its 728 / 0 / 0 measurement. No metric change, no expiry rule, no discard decision. |
| R3 | `EV2` treated as proof for the whole new capture path; "no substantive end-to-end question" contradicted the memo's own §2.6 | Recommendation rewritten as an explicit **marginal-value/risk** judgement that names the remaining end-to-end question; new §3 limits `EV2` to bytes-to-text equivalence and tabulates the three states (historical live execution / current offline validation / **absent** same-version capture); "zero INCONCLUSIVE" qualified; a different trading day described as an additional observation, not a stability proof; T1 widened so a defined end-to-end acceptance objective is a legitimate basis for a future one-run authorization, while capture-to-clear-`EV6` stays excluded. |
| R4 | Annex verdict rules disagreed with the code; the BJ exception was under-specified; retries and a new run were conflated | Partially resolved in revision 2 — `MAX_ATTEMPTS_PER_JOB = 3` per **request** under `CEILING = 15` distinguished from an unauthorized additional run, `EV6` corrected to a FAIL-only check, and new endpoints/symbols routed to separate scope review, all of which stand. The verdict tables themselves were still misaligned and are **superseded by revision 3, item 1** above. |

---

## What this memo did and did not do

Written from the current sources, the retained evidence and the existing request. **No
implementation file, evidence directory, revision, receipt set, frozen bundle or reviewer
artifact was modified.** Nothing was executed: no suite was re-run, no adapter replayed, no
capture prepared or armed, no database opened, no network reached, no `run_id` minted.
Both boundary-1b authorizations remain consumed. **M2b source capability remains FAIL and
is not accepted.**

**Stop: `proposed for review`.**
