# Amount representation audit — Codex review, 2026-09-09

**Verdict: corrections required.** Completed Claude handoff and idle sole session observed.
Reviewed `M2B_AMOUNT_REPRESENTATION_AUDIT.md` SHA-256
`dbd902254b7098796471fed6ad5a518143bb661e627e7bcb76c6d06b4bfccf82`.
Snapshot: `_m2_codex_review/amount_representation_review_20260909_r1/`.

Preserve the useful findings: alias priority versus positional selection; ambiguity
reporting; the inspected returned schemas do not let a turnover-rate alias bind; the
successful Tencent qfq branch can construct ready candidate bars with amount None; and
source_comparison flags non-finite amount. These are static conditional findings, not
observations of executed ingestion or identical live response bytes.

## AR-R1 — separate stocks from benchmark routing and locate the real write guard

Section 7 treats all F3/F5/F6 null-amount rows as quarantined by chk_units. The delegate
explicitly excludes benchmark symbols (`acceptance_runner.py:163-184`); staging supplies
that benchmark list. The stock null-amount case is quarantined, but F5/F6 benchmark rows
are not subjected to that stock liquidity check. Do not infer that benchmark amounts
must exist or that their absence is an ingestion defect.

The table calls lines 414-418 the _upsert_bars guard; those are from the single-row helper.
The actual batch conflict guard is `daily_bar_cache.py:465-477`, reached by the real stock
and benchmark writers. Correct the citation and bound the claim to an existing conflicting
row at that statement. Preceding deletes at lines 502-521 and first inserts are separate;
do not imply a global guarantee that stored good rows cannot be removed or replaced.
Refer to the already accepted cache write-path audit, without reopening it.
Also correct the benchmark normalizer citation: lines 917-930, not the stock builder at
998-1010. Write eligibility, attempted insert/update, and durable database contents are
distinct; no database contents were observed here.

## AR-R2 — include caller-added unit labels and the requested M2 evidence boundary

The producer-to-comparison trace skips metadata changes. At
`compare_market_sources.py:50`, the Eastmoney probe explicitly stamps volume_unit=hand and
amount_unit=yuan; line 63 stamps the Sina amount_unit=yuan. Lines 70-73 serialize selected
attributes and rows, and lines 188-191/201-204 rebuild frames before normalization.
These are local caller assertions, not new vendor proof, and they do not alter the
production cache writer. Report them rather than leaving the impression that no unit
label reaches comparison. The cached_sample branch at lines 209-213 is another inspected
input to comparison; either bound the matrix to direct provider probes or briefly name
that branch and its limits. Same loader/code does not establish identical live bytes
across separate invocations; keep Case C a same-input reasoning example with a reachable
source shape, not an observed cross-run byte comparison.

Complete the originally requested U1/U2/U3 distinction using the existing checker and
retained v2 JSON. U2 calls prov.derive_unit at `smoke_checks.py:1231-1240`; U3 compares
amount ratios on selected retained live/reference pairs at lines 1299-1316. Report the
actual finite evidence scope and limits; do not elevate local labels to independently
verified currency or let retained Sina checks certify Tencent/cache/index paths. Pin any
additional source actually relied on. This is a short static trace, no replay/decoder or
new calculation is needed. Include the existing Tencent delegated newfqkline return
(`daily_bar_cache.py:638/655,779-827`) within F3, or explicitly bound F3 to the branch read;
the delegate also constructs amount=None, but that should be read rather than assumed.

## AR-R3 — the proposed fix does not follow the actual quality-status flow

Section 9 proposes treating all-null amount like absent amount, but both already become
None/ready in the inspected builders. That equivalence alone changes nothing.
Additionally, `_refresh_stock_symbol` overwrites every normalized bar's quality_status
at `daily_bar_cache.py:213-214`; merely marking a bar inside the normalizer is not enough.
Trace this propagation and keep any possible change explicitly conditional on a future
policy and production authorization. Distinguish stock amount requirements from index
exclusion. A flag change can affect the existing SQL guard, so "flags only while guard
behavior remains unchanged" is not an established compatibility result. State a coherent
future validation requirement for the chosen semantics rather than promising unaffected
upsert outcomes without analyzing them.

Dropping an inert required parameter or aligning alias tuples are not narrower fixes
for missing amount; separate those unrelated cleanups or omit them. No cleanup is needed
for this task. Keep the proposal minimal and unimplemented; do not adopt a new rule or
quality label to make the document appear resolved.

## Verification and next instruction

17 document-table source/artifact pins match; 91 protected files unchanged; 46 G1 files
unchanged with identical path set. Additional smoke checker pin is in verification JSON.
Static source and retained JSON review only; no tests, runtime imports, SQLite, network,
provider/replay/decoder, services, production/data mutation or Git write. HEAD 73f266d;
staging empty. P1 open, U-6 deferred, every eligibility false, capability FAIL including
historical EV6; both capture authorizations consumed. Technical corrections do not close M2.

Task AMOUNT-CORRECTION-20260909. Resolve AR-R1 through AR-R3 together in ONE concise
revision of ONLY `claude methods/M2B_AMOUNT_REPRESENTATION_AUDIT.md`. Preserve correct
alias findings and all accepted artifacts. Direct text edits and the indicated short
source/retained-JSON reads only; no agents, broad sweeps, scratch scripts/output directories,
new studies, datasets/fixtures, SQLite, tests/imports/runtime, network/capture/replay/decoder,
services, production/schema/data/strategy/knowledge changes, policy/gate/label/eligibility/
threshold changes, training/pilot/backfill or Git actions. Existing continuous offline
authorization suffices. Deliver the stable sole-document hash, actual source pins and
preservation evidence at proposed for review, with findings addressed pending Codex review.
