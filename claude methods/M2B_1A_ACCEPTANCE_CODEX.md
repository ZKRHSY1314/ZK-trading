# M2b boundary 1a - independent technical acceptance

Date: 2026-09-08 (Asia/Taipei)

## Verdict: VALIDATED for the offline scope

The four blocking findings R1-R4 in `M2B_1A_CLOSURE_CODEX_REVIEW.md` are closed
on the reviewed revision. No remaining blocker was found for this bounded offline
stage. This is Codex's technical validation, not user authorization for live work
or a declaration that the entire M2 milestone is complete.

Overall evidence assessment: **Share with caveats**. The implementation and synthetic
failure handling are verified; real vendor response semantics remain unverified.
Boundary 1b is still unauthorized and was not executed in this review.

## Reviewed sources and reproducible checks

- Claude's request: `claude methods/M2B_REAL_SOURCE_VERIFICATION_REQUEST.md`, Section 14.
- Current implementation and delivered tests: `claude methods/_m2_smoke/`.
- Prior blocking report: `claude methods/M2B_1A_CLOSURE_CODEX_REVIEW.md`.
- New independent probes: `claude methods/_m2_codex_review/review_m2b_1a_round3.py`.

From `D:\codex-A股交易`:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/test_m2_smoke.py'
# exit 0: 132 cases, 0 unexpected

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_1a_round3.py'
# exit 0: baseline and independent R1-R4 closure probes PASS

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/smoke_capture.py' --plan
# exit 0: F1-F8 PASS; reference extraction PLANNED, not performed

git diff --check
# exit 0; existing CRLF conversion warnings only
```

The independent driver reuses synthetic fixtures, not Claude's test-case functions.
It exercises actual capture, checks, retention and replay paths. Real HTTP is denied,
including the loopback proxy; database opens are denied. Writable fixtures are confined
to one task-owned temporary directory; deliberately paused workers are released and
joined before its removal. No generated market dataset or production database is opened.

The first run of the new reviewer driver failed because its own assertion filtered
`BJ920000` instead of the check schema's lowercase `bj920000`. Correcting that reviewer
selector required no implementation change. The complete rerun passed. Historical
reviewer scripts were not edited or repurposed as current passing tests.

## Closure evidence

| Finding | Independent observed result | Relevant implementation |
| --- | --- | --- |
| R1: late raw-body writes | Paused the actual staged `Path.write_bytes`, expired capture, then released the worker after the seal. Both successful-response and failed-response variants left the entire sealed evidence tree byte-identical; only request 1 was issued; no orphan body appeared. | `smoke_capture.py:380`, `:399`, `:1600`, `:2033` |
| R2: unbounded/misreported finalization | A returning 121-second cleanup against 120 seconds reports `overrun`, remaining -1, exit 1. Separately blocked staged-check writes and the actual retention rename report `abandoned`; after release, tree contents remain identical, no subsequent steps run, and retention never duplicates the tree. | `smoke_capture.py:518`, `:534`, `:1677`, `:1805`, `:1872` |
| R3: missing or inconsistent attempt evidence | Empty/truncated attempts, wrong status, binding, source or URL all produce T3 FAIL and capability FAIL. The empty-attempt corruption also fails retained replay. Two 503s followed by 200 yield seven total attempts; the previous classified attempt is already on disk before the next retry's response. | `smoke_capture.py:1244`, `:1484`, `:2108`; `smoke_checks.py:479` |
| R4: auxiliary absence mistaken for history absence | Request 4 HTTP 404/410 yields the documented BJ-qualified finding. Request 5 HTTP 404/410 yields INCONCLUSIVE while retaining served-history checks. Request 5 HTTP 403/429 yields FAIL. | `smoke_outcomes.py:115`; shared aggregation and required-check rollup in `smoke_checks.py` |

The delivered 132-case suite additionally covers the pre-seal refusal window, forced
unsealed capture, failed publication rollback, duplicate requests, aborted retry tails,
cross-volume retention refusal, raw-body removal, and malformed auxiliary payloads.
These are distinct from proof on actual vendor data; the test count is not a readiness metric.

## Revision identity

The current five source hashes match Claude's Section 14 report and stayed unchanged
through this review:

| File under `_m2_smoke/` | SHA-256 |
| --- | --- |
| `smoke_capture.py` | `b17f8d0d624c53ed189562566021f11c2e4a9f1bcad0add8713fc66dbc060156` |
| `smoke_checks.py` | `b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c` |
| `smoke_outcomes.py` | `53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e` |
| `sina_klc_decoder.py` | `6599285a2cdd5828e4d87698d01cd39012b2724cf5b76ae1ec6861891c6f1858` |
| `test_m2_smoke.py` | `5cb4cc3e1075b09054132398491657595ce72bd91694469ba4e1d275b57a3064` |

Accepted M1 manifest/calendar and the four pinned M2a source/test files match their
accepted hashes. Their older suites were not redundantly rerun in this review.
Both older reviewer drivers match the prior reported hashes.

## Production and repository boundary

Metadata-only checks, without opening the databases:

| File | Bytes | mtime_ns |
| --- | ---: | ---: |
| `trading_local.sqlite3` | 1346048000 | 1788517646307317700 |
| `market_history.sqlite3` | 1234956288 | 1788493486739967200 |
| `market_history.sqlite3-wal` | 0 | 1788493486748601200 |

These match the prior baseline. This is a metadata comparison, not a fresh row-count audit.
HEAD remains `73f266d`, branch `codex/control-plane-refactor`, index empty. The workspace
remains dirty with unrelated user/Claude changes preserved. `tmp/` is absent; no smoke
`evidence_*` or `.pending` directory exists in the smoke output area. No live request,
plugin call, service start/stop, credential access, production write, training, staging,
commit or push was performed. This review adds only this report and the new reviewer driver.

## Required caveats and non-blocking documentation follow-up

1. This validates the offline engineering path only. No real Sina body has yet proved
   decoder behavior, identity, units, adjustment basis, session coverage or adapter losses.
   The three-year corpus and model-training goal are not completed by this acceptance.
2. Cancellation is not thread termination. A worker already inside one guarded filesystem
   operation may finish that operation; a forced-unsealed capture is explicitly partial
   and not retained. The tests validate those reported degraded outcomes, not universal
   immunity to an indefinitely stuck operating system or disk.
3. The timing restriction remains an **operator condition**, not a checked clock gate in
   F1-F8. Immediately before a future authorized run, explicitly verify and record
   Asia/Shanghai time: before 09:15 or after 15:30. A green `--plan` alone does not prove
   timing-window compliance. Do not start services or stop unrelated processes to pass F8.
4. Section 3 of the request still says the stock qfq path multiplies by its factor;
   the reviewed B2 implementation and later correction establish qfq division (hfq
   multiplication). Correct this stale narrative when updating the handoff; do not
   modify accepted code or reinterpret raw data's basis to match it.

The validation workflow was used to separate tested claims, unverified live-data claims
and authorization conditions. No chart or rendered-report QA applies to this code-stage review.

## Next action: obtain the user's bounded 1b authorization

No further generic offline redesign is requested. Freeze the reviewed hashes, link this
review in the progress ledger, and keep 1b proposed until the user explicitly authorizes
one smoke run and the local evidence-retention choice.

Recommended choice: retain the captured raw bodies and the minimal frozen reference
extract **locally only**, under the reviewed evidence directory, to permit independent
offline replay. No Git staging, external upload or production promotion is authorized.

If separately authorized, execute the existing boundary 1b once, outside the stated
timing window exclusion and only with a fresh passing preflight. Scope is SH600011,
SH000300 and BJ920000 in the fixed five-request order, at most 15 attempts including
per-request retries, concurrency 1, spacing at least 1.5 seconds, unchanged TLS checks
and abort rules. Do not substitute endpoints or expand symbols after a failure.

Capture the process exit code and pipeline summary as well as the retained manifest,
checks, report, hashes and frozen reference. Report actual request count, duration,
failures, coverage and unresolved semantics; repeat the deterministic checks offline
from retained evidence and stop at `ready_for_review` for Codex. Do not advance to the
52-symbol pilot, full-market rebuilding, basis labeling, production writes or training.
