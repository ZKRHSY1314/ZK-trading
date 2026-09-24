# Boundary-1b run 2: independent Codex review

Date: 2026-09-08. Run: `20260908T082833Z`.
Branch: `codex/control-plane-refactor`; HEAD: `73f266d`; index empty.

## Decision

The retained evidence substantiates a completed five-request capture inside the
approved time window. Its original **source-capability verdict remains FAIL** and
reproduces exactly. The failure report is useful with the corrections below; it is
not acceptance of M2, the 52-symbol pilot, a training corpus, or strategy performance.

The run consumed its one-run authorization. This review issues no new live authority.
The next proposed implementation is a bounded **offline** correction and re-evaluation
using the already retained bodies, not another capture or another broad design cycle.

The validate-data and analyze-data-quality workflows were used to distinguish actual
transport execution, reproducible results, sampled semantic evidence, and claims that
exceed the sampled securities.

## Independent evidence

Reproduction:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_run2.py'
```

Result: **59 diagnostic assertions passed, exit 0**. That means the observations and
the failures reproduced, not that the source passed. The first diagnostic draft had
one overly strict amount-ratio assertion at `1e-8`; deviations reached approximately
`1.4e-8`. It was corrected to the already approved +/-1% currency tolerance. No
implementation, data, evidence or acceptance threshold was changed.

- Manifest wire starts: **16:28:34 through 16:28:41 Asia/Shanghai**, after 15:30.
  The author's 16:27:57 clock check is a separately reported pre-arming observation;
  it is not the wire start. Five attempts, each HTTP 200, no retries.
- Independent actual-start gaps: **1.515, 1.500, 1.500, 1.500 seconds**; first-to-fifth
  span **6.015 seconds**. Request URLs match the frozen plan. All five raw byte counts
  and SHA-256 hashes match the manifest.
- The retained plan and capture manifest both record **279** inventoried processes.
  The prose's 280 may refer to an earlier plan; retain that distinction with a receipt
  if available rather than representing it as the final capture inventory.
- Five live-source hashes and five frozen-copy hashes match the accepted D1/D2 pins.
- The deterministic replay is identical:
  `8ffb30b06a70aee4d301f4d7cea53c34e0ea8374dc0587d69b8848cb4f2ed5c2`.
- The original run's manifest/checks/reference, both previous revision anchors and
  all five original receipts still match their earlier accepted hashes.
- All six retained directories were hashed before and after the reviewer probes and
  remained unchanged. Production database sizes/mtimes match the established baseline;
  metadata equality is not a complete historical no-writer proof.

The probes ran with remote-connection and SQLite-open guards. No source requests,
production database opens, service actions, Git staging/commit/push or training occurred
in this review. Only this report and the new reviewer driver were added, locally and
outside the commit allowlist. Unchanged broad suites were not rerun.

## Verified useful progress

| Captured instrument | Decoded rows | First / last date | Pinned window dates present |
|---|---:|---|---:|
| SH600011 | 5,935 | 2001-12-06 / 2026-09-07 | 978 / 978 |
| SH000300 | 5,987 | 2002-01-04 / 2026-09-07 | 978 / 978 |
| BJ920000 | 1,393 | 2017-03-29 / 2026-09-07 | 978 / 978 |

The 978 denominator is the pinned calendar's 250 warm-up sessions plus 728 research
sessions, not a full-market or complete listing-lifetime denominator. Dates were
independently checked for uniqueness/order and membership coverage. The retained
responses end on September 7; this is not a claim of September 8 closing-data freshness.

For both stocks, ten latest usable overlaps with the frozen local reference reproduce
volume ratios approximately 100 and traded-amount ratios approximately 1. These are
sampled unit/currency corroboration, not proof of historical PIT or adjustment validity.

## Required offline corrections

### R2-A: actual auxiliary shape plus zero-value handling

`_m2_smoke/sina_klc_decoder.py:354-393` expects `[date, value]` pairs. Both retained
auxiliary responses are objects with `date` and `amount`: **26 SH600011 entries** and
**42 BJ920000 entries**. The current parser rejection reproduces on each.

There is an additional edge case beyond the author's shape diagnosis: BJ has zero
values on **2015-03-06 and 2015-09-15**. A diagnostic conversion to pairs still fails
at the positive-value gate. Both observations precede the pinned warm-up/research
window; simply allowing object syntax will not complete the correction.

Parse the observed bounded envelope as data, never execute the downloaded wrapper or
its XSS-guard comment. Bind the expected symbol and validate dates, schema and numeric
values. Keep this endpoint's `amount` explicitly separate from traded amount, with
the outstanding-share unit/normalization traceable to the installed adapter.

Specify and test the invalid/zero-observation policy. Preserve raw observations and
report their quality; do not fabricate positive values, silently drop evidence, divide
by zero, or backfill future share counts into earlier dates. A required denominator
that remains unavailable must remain unavailable. Report unusable pre-window rows
separately from validity of the series over the consumed window.

### R2-B: symbol identity, not all digits in a variable name

`_m2_smoke/smoke_checks.py:1017-1025` collects every digit from `KLC_K2_sh600011`,
producing `2600011`; BJ similarly becomes `2920000`. These are reproduced false
failures. Validate the complete supported variable-name structure against the exact
expected exchange and symbol. Do not merely remove all 2s or accept substring matches.
Test correct stock/index names, wrong symbols, wrong exchanges and unknown envelopes.

### R2-C: valid adapter dates and truthful per-job diagnostics

`_m2_smoke/smoke_checks.py:940` passes empty start/end strings. The recorded TypeError
reproduces. In a read-only diagnostic, passing **20220824 / 20260904** allowed the
installed adapters to return **978 rows for each stock**; the index adapter returned
5,987 total rows. Every URL was served from retained bytes. This is cause-isolating
evidence only: no implementation was changed and no corrected capability was awarded.

Use the declared window explicitly, preserve stock/index differences, and make a
failure in one job distinguishable from another job never being evaluated. Assert
actual returned rows/dates, not only absence of an exception. Correct new diagnostic
wording that says an auxiliary body was "not captured" when it was captured but
failed parsing. Share-dependent C4 statistics must not imply measured zero loss when
the share series was unavailable. Do not edit those texts in the sealed report.

## Reporting and evidence boundaries

1. **Do not generalize BJ920000 to all seven BJ selections.** Section 22 at
   `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md:1564-1565` says this settles the mapping note
   and expected keys for seven securities. Only one BJ path was contacted. This run
   establishes pre-boundary history on that path, not the mapping mechanism or data
   coverage of the other six. Preserve their uncertainty and the frozen manifest.
2. **Current handoff must say the authorization is consumed everywhere.** The new
   run-2 heading is correct, but the goal document still contains active statements
   at approximately lines 998-1012 that the second run is unused and needs only a
   re-trigger. Reconcile the current state and archive prior instructions clearly.
   This is an execution-safety correction, not a request for another documentation
   design loop. No third live run is authorized.
3. Keep the original two capture directories, receipts, revisions and frozen accepted
   source bundle immutable. Store any corrected offline evaluation in a **new**
   directory with current producer hashes, original input hashes and a parent link.
   A historical capture-time parser classification may differ from a corrected one;
   label that version difference explicitly. Do not rewrite the manifest, silently
   waive EV6, or change recorded FAIL to PASS.
4. Separate the original live verdict from a new offline re-evaluation. If the
   existing provenance contract cannot certify a corrected capability from these
   retained inputs, report the exact unresolved gate. Do not force a green result or
   launch another capture to sidestep it.

## Proposed next handoff to Claude

Read this report. Implement only R2-A/B/C and their focused offline regressions,
including the BJ zero observations and wrong-symbol cases. Preserve M0/M1/M2a, F8 and
all transport limits. Limit implementation edits to the existing smoke decoder/checks
and their tests; report/ledger corrections and a new separately named offline revision
are the only other deliverables. Keep reviewer scripts untouched.

Use the five retained responses under `evidence_20260908T082833Z/`. Run focused tests,
then the relevant offline smoke suite and a version-aware replay. Report the actual
per-job outcomes, remaining missing evidence and any provenance mismatch without
massaging the stored inputs. Stop at `ready_for_review` for Codex.

No network/plugin calls, fresh capture, production writes, service changes, 52-symbol
pilot, basis-policy switch, training, staging, commit or push. This review proposes
that bounded next task; it does not itself invoke Claude or expand user authorization.
