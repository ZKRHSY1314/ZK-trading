# M2b boundary 1a - closure round 2 review

Date: 2026-09-07 (Asia/Taipei)

## Verdict: NEEDS REVISION; boundary 1b remains unauthorized

There is verified progress. The delivered **104 tests pass**, the write-nothing
`--plan` passes **F1-F8**, and an independent driver confirms the **eight specific
scenarios from the previous review no longer reproduce their original defects**.

However, four related boundary defects remain. Do not reinterpret closure of those eight
scenarios as acceptance of all B1-B5 requirements. Scope stays M2b-1a closure; do not
reopen accepted M1/M2a or start the live smoke, a pilot, or training.

## Reproduction

From `D:\codex-A股交易`:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/test_m2_smoke.py'
# exit 0: 104 cases, 0 unexpected

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/smoke_capture.py' --plan
# exit 0: F1-F8 PASS; reference extraction remains PLANNED, not performed

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_1a_closure.py'
# exit 0: 8 previous scenarios verified closed; 4 remaining defects reproduced

git diff --check
# no whitespace errors; existing CRLF conversion warnings only
```

The new reviewer driver uses synthetic fixtures and the actual capture/check/pipeline
code. All genuine `requests.Session.request` calls are denied, including loopback
proxy traffic. Only task-owned temporary directories are used. A task-owned worker is
paused and released to reproduce R1; it is joined before temporary cleanup. No live
CLI, production database open, or service operation occurs.

Preserve both reviewer scripts. They are historical reproduction evidence, not tests
to edit until green. Add desired-behavior regressions in the implementation's suite.

## Verified closures

| Previous scenario | Independently observed now |
|---|---|
| TLS certificate failure through the real adapter | One call, non-retryable |
| HTTP 403/429 with a failing body | One call per status; stop latched; body not read |
| Correctly paced fast responses | Attempt starts 0, 1.5, 3, 4.5, 6 seconds; T3 PASS |
| HTML in the first two jobs | Only requests 1 and 3 issued; global abort; T3 consistent |
| Explicit capture invalidation | Capability FAIL |
| Reference hash mismatch | Capability FAIL |
| Mutated retained units/timestamps under stale hash | Capability FAIL; deterministic hash changes |
| Exhausted budget before real check entry | Refused before entering replay |

The shared classifier, actual-attempt timing wrapper, reference hash recomputation,
and proxy-aware offline guard are meaningful improvements. No rollback of them is
requested. The remaining findings below concern boundaries still outside those checks.

## R1 - A worker can still write a raw body after capture finalization (P1)

Locations: `smoke_capture.py:1402-1405`, `:1329-1348`, `:1434-1458`;
regression gap: `test_m2_smoke.py:1862-1878`.

`cancelled` guards `_record` and `_flush`, not the raw-body `Path.write_bytes` calls.
The delivered late-write test invokes those two guarded helpers only, sequentially
after a successful capture. It does not let a real in-flight worker wake after abort.

Independent fault injection paused the actual first raw write, expired the clock, and
let capture's supervisor finalize the aborted manifest (`cancelled=True`). The raw file
did not yet exist. Releasing the worker then created that raw file **with cancelled
already true**, while the final manifest stayed byte-identical and contained no record
binding that body. It can therefore race evidence inventory and retention/cleanup.

Required closure:

- Apply a real ownership/cancellation boundary to **all evidence mutations**, not only
  the two manifest helpers. A check-then-write boolean alone still leaves a race window.
- Finalization must not run concurrently with any worker that can publish evidence.
  Design the worker/owner handoff so late worker results cannot mutate the final tree.
- Add an event-controlled test at the real raw write, with abort/finalization between
  arrival and publication, plus a failed-response evidence variant. Verify the entire
  tree and manifest remain consistent, not only the manifest bytes.
- Do not kill unrelated processes or edit accepted M2a to solve this.

## R2 - Finalization's 120-second limit is declared but not enforced (P1)

Locations: `smoke_capture.py:1255-1279`, `:1287-1325`.

The finalization budget is checked once after report writing and **before** cleanup.
The subsequent hashing/move/removal operation is synchronous, receives no deadline,
and is followed by no deadline check. A blocked cleanup is unbounded; an overrun that
eventually returns is still reported as success.

Independent result: the synthetic cleanup consumed 121 seconds on the injected clock
against the declared 120-second budget. The real pipeline returned:

```json
{"phase":"done","capability":"PASS","finalize":{"budget_sec":120.0,
 "elapsed_sec":121.0,"remaining_sec":-1.0,"grace_sec":0.0}}
```

Required closure:

- Enforce a bounded finalization/retention path with a clear incomplete-finalization
  outcome. No negative remaining budget may become successful completion.
- Test both a returning overrun and a blocked actual retention operation. A post-call
  check detects the former but does not bound the latter.
- Preserve partial evidence on failure, report its location, and keep abandoned workers
  from writing into or cleaning up the retained tree (coordinate with R1).
- Keep the documented total runtime and shutdown/finalization allowances consistent
  with the implemented controls.

## R3 - Five successful requests can validate with zero attempt records (P1)

Locations: `smoke_checks.py:590-658`; capture accounting at
`smoke_capture.py:1362-1432`, `:1452-1487`.

T3 checks only an upper attempt ceiling and whether timestamps are present for each
entry that exists. It never reconciles attempts with issued request records. Removing
the entire attempt array makes the timestamp checks pass vacuously.

Independent result: a valid manifest produced by the actual synthetic capture was
changed only to `attempts=[]`, leaving five recorded successful requests. T3 returned
PASS with `attempts=0`, `issued=5`, `min_gap_sec=null`, and capability remained PASS.
The retained evidence cannot then substantiate any request, pacing or retry claim.

Also, the current `_flush` still follows `get_with_retries` returning/raising: it is not
called after each underlying retry attempt, despite the per-attempt durability claim.

Required closure:

- Bind every issued request to one or more actual attempt records; reconcile identity,
  URL, order, source, terminal outcome and timestamps. Skipped requests must not acquire
  wire attempts, and every retry must be accounted for.
- Reject empty, missing, truncated, duplicated or inconsistent attempt evidence.
- Preserve attempt evidence at the actual attempt boundary, including interrupted retry
  sequences, rather than reconstructing only after a complete retry group returns.
- Cover this through initial checks and retained-evidence replay. Do not relax T3 or
  fabricate substitute attempts from request records.

## R4 - An auxiliary-share 404 is incorrectly promoted to BJ history non-service (P1)

Locations: `smoke_outcomes.py:87-90`, `:157-185`;
`smoke_checks.py:733-760`, `:1084-1154`.

The plan's C2 exception concerns an explicit 404/410 on **request 4, the BJ KLC history
endpoint**. The implementation instead takes the worst job-level outcome, so the same
exception is applied to request 5, the separate outstanding-share endpoint. It then
skips all per-symbol checks, including those on the history body already received.

Independent capture-to-check result:

- Request 4: HTTP 200, history payload decoded successfully.
- Request 5: HTTP 404, outstanding-share endpoint absent.
- C2: `vendor_explicit_absence_at_path` as a BJ history-capability result.
- Capability: `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`.

This does not answer the historical-code question: the historical endpoint did serve
data. It must not be used to infer a BJ history limitation or a manifest population
change, and must not waive the missing auxiliary evidence.

Required closure:

- Make the explicit history-absence exception request-kind/path specific.
- Preserve the observed history result separately; classify missing auxiliary data as
  failed/inconclusive capability evidence, not the qualified history-absence PASS.
- Test request 4 404/410, request 5 404/410 with valid history, and invalid history plus
  auxiliary absence. The latter must not mask a real history-validation failure.

## Scope and safety evidence

Reviewed source hashes match the delivered round-2 report and were stable across review:

| File | SHA-256 |
|---|---|
| smoke_capture.py | 24e1378948efba580f60a18c33149f53b0f36e6acf372b14ce7560500c1e5e44 |
| smoke_checks.py | df8172c1e52ab9a3417e70b9ba52dc5691dec4b51354bbcaa1781749614310c9 |
| smoke_outcomes.py | b9bbdcdbb02e073fa9bd2525af76c31bea8c9a355ba61bd5d3ab240fa40e0049 |
| sina_klc_decoder.py | 6599285a2cdd5828e4d87698d01cd39012b2724cf5b76ae1ec6861891c6f1858 |
| test_m2_smoke.py | 0cbc4e31551c9401fff18df3b8520f61be9adc9c8c4fcb6295f7fcdb7612b7a7 |

Accepted M2a `pilot_runner.py`, `test_m2a.py`, `acceptance.py`, and `transport.py` match
their existing acceptance pins. No accepted implementation was changed in this review.

Production metadata remains:

| File | Bytes | mtime_ns |
|---|---:|---:|
| trading_local.sqlite3 | 1346048000 | 1788517646307317700 |
| market_history.sqlite3 | 1234956288 | 1788493486739967200 |
| market_history.sqlite3-wal | 0 | 1788493486748601200 |

These are metadata comparisons, not a new whole-database content audit. Production DB
contents were not opened by this review. No live smoke output/evidence directories
exist. HEAD `73f266d`; index empty. Reviewer additions are this report and the new
reviewer driver only, local and uncommitted.

## Next action

Claude should close **R1-R4 only**, offline, preserve the accepted stages and reviewer
artifacts, and report actual commands/results with desired-behavior integration tests.
Update the English handoff and ledger, then stop at `ready_for_review`.

The evidence-validation workflow was used to separate verified progress, unresolved
runtime/evidence defects, and still-unverified real-source semantics. This is not a
finding about profitability, model quality, or three-year corpus/training completion.
