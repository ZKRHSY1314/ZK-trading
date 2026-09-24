# M2a independent acceptance review

Reviewer: Codex. Scope: the delivered offline pilot runner and its actual behavior.

**Verdict: NOT VALIDATED.** Four bounded correctness/safety groups remain. M1's prior technical acceptance stands; do not restart M0/M1 audits. Neither a live smoke test nor the 52-symbol collection is authorized by this review.

## Evidence actually run

- Delivered `test_m2a.py`: **48 cases, 0 unexpected, exit 0**, independently rerun.
- Independent `claude methods/_m2_codex_review/review_m2a.py`: **13 defect probes reproduced**, followed by unchanged-input assertions. Its final exit code is 0 because it records observed behavior; it is NOT an acceptance pass for M2a.
- The provenance probe used the unchanged actual 50-stock/two-benchmark manifest and pinned calendar, but **all bars and HTTP responses were synthetic**. It invoked the actual unchanged M1 `snapshot`/`validate` command entry point on disposable databases, not fabricated gate text.
- Other parser probes intentionally supplied incomplete or contradictory gate outputs to test fail-closed behavior. They are adversarial inputs, not alleged output from a normal M1 run.

Reproduce from the repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_pilot\test_m2a.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_codex_review\review_m2a.py'
```

## R1 — Blocking: response bodies are disconnected from the stored rows

Location: `_m2_pilot/pilot_runner.py:218`, especially lines 225-226; `provenance.py` adjustment derivation.

The runner requests the expected URLs and records `response.url`, but discards the response body. It then obtains rows from `fetcher(symbol, klass)`, which receives none of those responses. That callback can return unrelated data or initiate unbudgeted network requests. URL equality is not proof that the rows came from the response.

Independent reproduction: every simulated HTTP response was `<html>NOT MARKET DATA</html>`. A separate callback supplied a complete synthetic grid. The runner reported `completed`, `promoted=True`, wrote **45,935 rows per view** with raw-basis metadata, and counted 102 attempts. The actual M1 research gate exited 0; the actual warm-up gate exited 1 only on V3b; both M2a acceptance functions returned `accepted=True`.

This does not invalidate M1: M1 checks its declared data contract, not whether M2a truthfully obtained the input. The missing link is in M2a's ingestion/provenance boundary.

Required closure:

- Decode the captured, successful transport responses in a pure offline decoder. Do not fetch a second dataset through an independent callback.
- Bind parsed data to normalized security identity, source path, response identity/hash, basis evidence, and ingest-run metadata. Apply the basis check to benchmarks as well as stocks.
- Reject HTML, malformed data, missing/contradictory identity and basis evidence, and unexpected rows; preserve unknown evidence. Treat a response copy into two stores as lineage consistency, not independent source corroboration.
- Add an actual fake-transport -> decoder -> staging -> unchanged M1 gate -> M2a acceptance integration test. Inject bad response bodies into that exact path and prove no successful raw-data job/publication.
- Do not write `fetched_at='offline-fixture'` as eventual live provenance or leave all ingest runs as a generic `pilot` record. Synthetic fixtures must remain clearly separate from a future live run.

## R2 — Blocking: acceptance can pass absent or weakened gates

Location: `_m2_pilot/acceptance.py:86`, `:177`, `:188`, `:220`.

Reproduced with the current public defaults:

| Input | Actual result |
|---|---|
| Research output contains only P4=PASS; other mandatory gates absent | accepted=True |
| Research P4=UNKNOWN is marked advisory | accepted=True |
| Warm-up has the integrity gates, but V3b is absent | accepted=True |
| V3b=UNKNOWN, with the pinned shortfall | accepted=True |
| V3b=FAIL is advisory, with the pinned shortfall | accepted=True |

The shortfall set is more complete than M1's three-row sample, but it does not replace the required gate contract. Optional `expected_ids=()` and caller-provided required/advisory flags leave the acceptance boundary open. The runner also never invokes either acceptance function before its own `completed/promoted` result.

Required closure:

- Require the exact mode-specific gate inventory and requiredness internally, rejecting missing/duplicate/malformed gates, conflicting verdicts, and absent baseline/calendar/representation/unit gates. Do not rely on callers to remember an optional list.
- For this pinned warm-up plan, require V3b to exist, be required, and have status **FAIL**, with the complete expected shortfall and counts. UNKNOWN is not a known IPO depth limitation.
- Bind acceptance to the actual run's frozen inputs and both consumed views. Reject changed manifests/calendars; do not accept an arbitrary reduced population merely because it contains the same 14 short securities.
- Distinguish collection completion, acceptance, and publication. A failed gate or incomplete job set must never be presented as accepted publication.

## R3 — Blocking: declared stop/retry guarantees are incomplete

Location: `_m2_pilot/pilot_runner.py:199`; `_m2_pilot/transport.py:85`, `:135`, `:170`.

Reproduced:

- All **52 jobs** returned 404. The run made 52 attempts, did not stop after 20 consecutive failed jobs, and returned `completed`, `promoted=True`.
- A transport-raised `RunAborted` was caught as a generic exception and retried **3 times**; the final error was `TransportError` and the sticky abort reason remained unset.
- `ValueError` from the transport was also retried 3 times, contrary to the stated limited retry classification.
- An infinite connect timeout was accepted by the constructor despite the finite-timeout claim.

Required closure:

- Implement the 20-consecutive-job-failure stop and reset-on-success behavior. Failures/rejections and incomplete collection must have honest rollup states.
- Preserve RunAborted as a sticky, non-retryable whole-run stop. Retry only explicitly classified transient I/O failures and allowed HTTP statuses.
- Validate finite positive configuration, bounded attempt counts, and the actual request budget. Clarify per-job versus per-request retry semantics.
- Wire hidden-retry checks into the eventual transport construction path; a helper tested in isolation is not proof of enforcement. No live implementation/call is required for this closure: prove the boundary with injected sessions/transports.

## R4 — Blocking: two-file publication is not failure-safe

Location: `_m2_pilot/pilot_runner.py:88`, `:184`, `:214`.

The guard accepts trading and history resolving to the same destination. It also accepts one destination equal to the other destination's `.partial` file. The two `os.replace` calls are sequential, with no pair-level recovery.

Independent failure injection: pre-existing synthetic trading/history candidates were placed in a disposable directory. The first replacement succeeded and the second raised OSError. The result was **new trading + old history**, with `h.sqlite3.partial` left behind. There was no controlled recovery result.

Required closure:

- Validate pairwise distinct final and temporary roles, including aliases, before any mutation. Never unlink another role or an unowned/pre-existing partial as routine initialization.
- Prefer a fresh run-specific output directory and fail closed on reuse, or implement tested recovery preserving the prior pair. If publication uses a pointer/manifest, only expose the pair after both writes and acceptance succeed.
- Test failures during initialization, either database write, validation, and publication, not just HTTP 429. Preserve protected inputs and previous candidates.

## Safety and review limits

The independent probe blocked socket connections. All database writes were disposable synthetic fixtures; the approved manifest and all reviewed M1/M2 Python files plus the calendar retained their hashes. Production main/WAL sizes and nanosecond mtimes stayed at the prior baseline:

- trading_local.sqlite3: 1,346,048,000 bytes; 1788517646307317700.
- market_history.sqlite3: 1,234,956,288 bytes; 1788493486739967200.
- market_history.sqlite3-wal: 0 bytes; 1788493486748601200.

These are metadata checks, not fresh full-content production hashes. The first reviewer-probe run hit a reviewer-owned SQLite-handle cleanup error after printing the pipeline result; the handle was explicitly closed and the complete probe was rerun successfully. This was not attributed to Claude's implementation. That first run left a synthetic-only temporary folder at `C:\Users\Administrator\AppData\Local\Temp\m2review_pipeline_y4pia2bg`; the environment blocked the subsequent cleanup command, so no alternate deletion method was attempted. The final probe run cleaned up its own temporary fixtures normally.

No live source capability was tested. No full backend or broad M1 suite was rerun in this review. HEAD remains 73f266d and the Git index is empty. Reviewer artifacts remain local and excluded from Git.

## Next handoff

Close only R1-R4 offline in `_m2_pilot/` and the English M2a handoff/progress documents. Preserve accepted M1 behavior and existing unrelated edits. Keep the delivered tests, but correct assertions that currently encode misleading success (for example all failed jobs reporting completed). Add regressions for the actual counterexamples above and use the genuine integrated path.

Stop again at ready_for_review. Do not present the user's next choice as live smoke versus full pilot yet; neither is ready for authorization on this implementation. No network/plugin calls, downloads, real staging collection, production/runtime changes, services, Git operations, training, or promotion are implied.
