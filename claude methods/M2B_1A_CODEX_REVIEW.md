# M2b boundary 1a - Codex acceptance review

Date: 2026-09-07 (Asia/Taipei)

## Decision: NEEDS REVISION - do not execute boundary 1b

The four offline modules exist and the delivered 79-case suite passes. The read-only
`--plan` also passes F1-F8. However, eight independent synthetic integration probes
reproduce five blocking areas below. These are integration defects, not a request to
restart M1/M2a or broaden the design. The accepted M1/M2a boundaries remain accepted.

This review approves neither live requests nor a corpus, training, staging, migration,
service operation, commit, push or promotion. The current stage is **M2b-1a closure**.

## Evidence and reproduction

Run from `D:\codex-A股交易`:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/test_m2_smoke.py'
# exit 0: 79 cases, 0 unexpected

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/smoke_capture.py' --plan
# exit 0: F1-F8 PASS; reference extraction PLANNED, not performed

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_1a.py'
# exit 0: 8 current-defect integration scenarios reproduced

git diff --check
# no whitespace errors; existing CRLF-to-LF warnings only
```

The reviewer probe uses synthetic temporary evidence, fake HTTP responses, real
`SmokeRun -> LiveSinaTransport -> PacedTransport` integration, and `run_checks` itself.
It reuses Claude's synthetic fixture builder, not its acceptance assertions. Genuine
`requests.Session.request` calls are forbidden, including loopback proxy traffic.
The probe never invokes the armed CLI. Synthetic temporary files are cleaned up.

The reviewer probe intentionally asserts **current defect reproduction**. After fixes
it should no longer reproduce those defects. Preserve it; add desired-behavior
regressions to the implementation's own suite rather than editing reviewer evidence.

## B1 - The claimed end-to-end deadline is not on the actual end-to-end path (P1)

Locations: `smoke_capture.py:922`, `:1050`, `:1199`;
`smoke_checks.py:371`, `:601`, `:1017`.

`capture()` supervises `_run_job()`, but that job only downloads and records bodies.
The actual decoding/checking/installed-adapter replay occurs later in `run_checks()`.
It receives no active deadline and calls `replay_fn()` directly. The installed adapter
replay also does not inherit the pure decoder's JS limits. The delivered "stuck decoder"
test calls `supervise()` on an unrelated busy function, never this integration path.

Independent result: a manifest whose budget and grace were already exhausted still
entered the real `run_checks` replay callback and remained blocked until the reviewer
released a synthetic event. No production process was involved.

The armed CLI currently calls capture and prints status only; it does not invoke checks,
write `checks.json`/`REPORT.md`, or perform the documented retention/cleanup sequence.
These functions existing separately does not establish the declared bounded workflow.
The supervisor also abandons a thread; that alone is not evidence of bounded cleanup or
absence of late evidence writes. `_flush` is called per job, not per attempt as its
docstring claims.

Required closure:

- Wire and test one bounded capture/decode/check/report/retention path, including its
  failure path. Define precisely when the deadline starts and the bounded finalization
  allowance. A separate offline replay may use a fresh explicitly bounded budget; an
  initial run must not silently reset its deadline between phases.
- Propagate cancellation/fail-closed state through the real worker and installed replay
  path. Prove no late calls or writes can race finalization/cleanup after an abort.
- Exercise an in-flight trickle, blocked call, retry near expiry and blocked **actual
  check/replay call site**, not just the standalone supervisor helper. Preserve partial
  evidence on failure. Do not terminate unrelated processes or modify accepted M2a.

## B2 - The outcome table does not drive capture or failed-job stopping (P1)

Locations: `smoke_capture.py:1050-1094`; `smoke_checks.py:85-119`, `:393-452`, `:489-510`.

Capture considers every HTTP 200 a successful request. It never decodes/classifies the
payload before issuing the next request, and returns `job_ok=True` for HTML/empty or
malformed payloads. Only the later checker consults the outcome table. Consequently the
capture and checker contradict one another about whether requests should be skipped.

Independent result: synthetic HTML for all three KLC requests produced wire indices
`[1, 2, 3, 4, 5]` and capture status `completed`. T3 then reported requests 2 and 5 were
issued after their jobs' skip triggers. Two failed payload jobs did not stop the BJ job.

Required closure:

- Classify each response before starting dependent requests; use the same table to
  decide request continuation and consecutive failed-job handling.
- Test empty 200, HTML 200 and malformed KLC through the real capture-to-check path.
  Test two such failed jobs and verify the third is never called.
- Teach T3 to distinguish documented job-local skips from run-global abort skips.
  Do not weaken the table or relabel unwanted extra requests as valid.

## B3 - The live adapter loses TLS and vendor-stop semantics (P1)

Locations: `smoke_capture.py:822-846`; `test_m2_smoke.py` transport-mapping cases.

`requests.exceptions.SSLError` inherits `ConnectionError`. The live adapter catches the
broad parent and raises the retryable builtin `ConnectionError`. The delivered mapping
test explicitly expects that behavior, while the report says TLS failures are
non-retryable.

Independent result using the **real requests exception type**: one certificate failure
was attempted three times; all attempt classifications were `transient`.

More seriously, status handling occurs only after full body consumption. If headers
already say 403/429 but the body times out, the known stop status is lost and retried.
Independent result for both 403 and 429: three calls, `retryable=True`, abort latch NULL.
This violates the unconditional stop requirement.

Required closure:

- Preserve non-retryable TLS classification before the broad connection-error mapping.
- Latch a known 403/429 immediately at response headers. A subsequent body error must
  never turn it into a retryable event. Preserve status/headers and bounded partial
  evidence without waiting indefinitely to learn a stop that is already known.
- Retain bounded evidence for failed HTTP attempts too: currently PacedTransport raises
  on non-200 responses before `_run_job` writes any raw body/header record.
- Test these real adapter chains, not just hand-authored manifest states. Keep all
  retries paced and counted; do not bypass the accepted M2a transport policy.

## B4 - T3 measures the time before pacing, not the actual wire attempt (P2)

Locations: `smoke_capture.py:1054-1057`, `:1096-1102`; `smoke_checks.py:521-528`.

`started_mono` is recorded before `get_with_retries()` performs the pacing wait. T3
compares those timestamps as if they were actual HTTP starts. Retry attempts also have
no start timestamp in the emitted attempt manifest.

Independent result:

- Actual fake-wire starts: `0.0, 1.5, 3.0, 4.5, 6.0` seconds - correctly paced.
- Recorded starts: `0.0, 0.0, 1.5, 3.0, 4.5` seconds.
- T3: FAIL, minimum gap 0.000 seconds.

Required closure: record actual attempt-start timestamps immediately before the injected
HTTP call, after pacing, including every retry. Validate pacing from those timestamps.
Prove fast successful responses pass and a genuinely unpaced retry fails. Do not merely
relax the tolerance or remove pacing validation.

## B5 - Evidence hashes and run invalidation are metadata, not acceptance gates (P1)

Locations: `smoke_capture.py:1132-1139`; `smoke_checks.py:236-267`, `:381-389`,
`:919-943`, `:949-1011`, `:1017-1037`.

The checker never consumes `run_valid`/`invalidating_changes` when deciding capability.
It copies the extract's `content_sha256` but does not recompute it or compare it with
the capture manifest's `reference_extract_sha256`. Calendar hash is recorded rather
than enforced against the approved pin. Reference volume-unit fields are not checked
when the fixed volume ratios are interpreted.

Three independent results:

1. An otherwise valid synthetic scene with `run_valid=False` and an explicit production
   DB invalidation still returned capability PASS.
2. The capture reference hash set to 64 zeroes and the extract hash set to 64 `f`s still
   returned PASS.
3. Changing all reference timestamps and all `volume_unit` fields to `unknown`, while
   leaving the stale declared hash, returned PASS and the **identical deterministic
   hash**. The replay comparison therefore did not detect altered retained input.

Required closure:

- Gate acceptance on a valid, complete capture envelope and unchanged protected inputs;
  missing evidence or explicit invalidation must never yield PASS.
- Recompute the frozen reference content hash, bind it to the capture manifest, and
  enforce the approved calendar and recorded dependency/policy pins. Persist and verify
  the actual selection/threshold contract, not an unused descriptive field.
- Qualify basis, source and units before interpreting ratios. Unknown/incompatible
  units or unsupported comparability must produce explicit inconclusive evidence.
- Add corruption and missing-provenance regressions through both initial checks and
  retained-evidence replay. Keep benign replay independent of production DB access.

## Additional handoff hardening (do not expand the project)

- The test connection guard allows all loopback destinations, while the observed
  environment routes external HTTP(S) via `127.0.0.1:7892`. A local proxy tunnel can
  therefore bypass a "non-loopback socket only" restriction. Preserve the JS engine's
  self-pipe, but explicitly deny genuine HTTP requests/proxy traffic in offline tests
  and replay; demonstrate this without contacting the proxy.
- Synchronize the request's opening status and the goal ledger: the request still says
  "no code has been written, no directory created" next to "1a implemented". This is
  documentation polish, not the reason for rejection.
- Treat reference extraction being PLANNED in `--plan` as intentional, not evidence that
  live reference extraction already passed. Live connectivity, vendor format and
  semantics remain unverified until separately authorized boundary 1b.

## Verified scope preservation

The four delivered source hashes were stable from first inspection to final check:

| File | SHA-256 |
|---|---|
| smoke_capture.py | bf953535c7b27194929801f82990e1b9d27d99c4dd40e3269fd62295b3401c6d |
| smoke_checks.py | 295f6b8e9622b54927208b3f3b0269c89eb578d4407201b75dcd1dd5a9391959 |
| sina_klc_decoder.py | 6599285a2cdd5828e4d87698d01cd39012b2724cf5b76ae1ec6861891c6f1858 |
| test_m2_smoke.py | 61290730dcb0bdf99ee9da77f16474cd9124a026e6ace7692c42a149d4b383fb |

Accepted M2a `pilot_runner.py`, `test_m2a.py`, `acceptance.py`, and `transport.py` hashes
match the prior acceptance pins. No accepted code was modified by this review.

Production file metadata matches the existing baseline:

| File | Bytes | mtime_ns |
|---|---:|---:|
| trading_local.sqlite3 | 1346048000 | 1788517646307317700 |
| market_history.sqlite3 | 1234956288 | 1788493486739967200 |
| market_history.sqlite3-wal | 0 | 1788493486748601200 |

These are metadata checks, not newly computed whole-database content hashes. Production
DB contents were not opened by this review. HEAD remains `73f266d`; index empty. No live
smoke output/evidence directory exists. Reviewer-owned additions are only this report
and `_m2_codex_review/review_m2b_1a.py`, local and uncommitted.

## Next handoff to Claude

Close B1-B5 offline, with end-to-end desired-behavior regressions and the small hardening
items above. Preserve M1/M2a and all reviewer artifacts. Update the English request and
progress ledger with exact files, commands, counts and remaining caveats. Stop at
`ready_for_review`; do not execute 1b or request a broader pilot as a substitute for
closing these concrete integration defects.

The evidence-validation workflow influenced this review by separating passing helper
tests from real call-chain behavior and separating offline acceptance from live-source
or three-year-research readiness. No chart, profitability or model claim is evaluated.
