# M2a R1-R4 closure: independent acceptance review

Reviewer: Codex. Reviewed 2026-09-06, approximately 23:38 Asia/Taipei.

**Verdict: NOT VALIDATED.** The closure contains real improvements, but seven independent counterexamples remain within the same four previously requested groups. Do not start live sampling, the real 52-symbol collection, training or promotion. Accepted M1 behavior remains accepted; do not reopen M0/M1.

This reviews the new 60-case closure described at the top of `M2A_OFFLINE_PILOT_RUNNER.md`, not the superseded 48-case implementation. The earlier review and probe script remain unchanged.

## Evidence actually run

- Delivered M2a suite: **60 cases, 0 unexpected, exit 0**.
- New independent script: **7 defect observations reproduced**, plus two positive controls and the final unchanged-input check; exit 0. Its exit code means the observations reproduced, **not** that M2a passed acceptance.
- Full positive control: the actual approved **50 stocks + 2 benchmarks**, pinned calendar, complete synthetic eligible research/warm-up grid, fake response transport, current decoder, both disposable staging views, actual unchanged M1 `snapshot`/`validate`, then both public acceptance functions with enforcement enabled and full manifest/calendar hashes supplied. Research exit **0**; warm-up exit **1** with exactly the pinned 14-security depth shortfall; both collection verdicts accepted.
- The response-override defect was reproduced through that same full path, not fabricated gate text. The other parser probes intentionally use adversarial gate text and are identified as such below.

Commands from the repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_pilot\test_m2a.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_codex_review\review_m2a_closure.py'
```

## What is now working

The suite verifies rejection of HTML on the normal decoder path, malformed identity/basis/schema, absent or weakened required gates with enforcement enabled, and absent/UNKNOWN/advisory V3b. The 20-consecutive-failure stop, finite-timeout validation, non-retryable programming errors, first-call propagation of `RunAborted`, distinct database destinations and fresh run directories now work. Collection no longer publishes automatically. A single pointer replaces the old two-database replacement sequence.

These gains should be preserved. They do not close alternate entry points that bypass the new checks.

## R1 / P1: the response-body bypass still exists

Locations: `_m2_pilot/pilot_runner.py:208` and `:302`.

The removed `fetcher` callback has effectively been replaced by the public `responses` mapping. `_one()` prefers `responses[response.url]` over `response.text`. A successful HTTP status and matching URL do not prove the replacement body came from that response.

Reproduction: every fake HTTP response contained only `<html>NOT MARKET DATA</html>`. A separately supplied mapping contained valid synthetic envelopes. The runner completed **52 jobs / 102 attempts**, wrote **45,935 rows per view**, and both actual M1-driven acceptance paths accepted it with enforcement and exact pins enabled. Every stored body hash matched the replacement envelope, not the actual HTML response.

This remains a provenance failure, not a claim that synthetic bars are actual market observations or that M1 should detect forged ingestion provenance.

Closure: remove the body override from the runner. Put test bodies exclusively inside the injected fake transport's response object. Use one captured response object/body as the source of decoding, hashing and lineage. Add the HTML-plus-replacement regression to the public runner path.

## R2 / P1: enforcement and exact-run binding remain optional

Locations: `_m2_pilot/acceptance.py:107`, `:225`, `:255`, `:280`; `_m2_pilot/pilot_runner.py:367`.

Four reproduced observations:

1. `accept_research(partial_text, 0, enforce=False)` still accepts a report containing only **P4=PASS**. The report says callers cannot remove the internal inventory; the public flag does exactly that. The delivered happy-path integration test itself uses `enforce=False` and a reduced population.
2. Replacing `SH688001` with `SH600998` in a disposable copy of the manifest preserves 50+2 counts and is accepted by the public default binding path. No expected manifest hash or calendar is mandatory. This parser probe deliberately supplied a full synthetic all-pass report; it tests binding, not normal M1 behavior. Hash prefix comparison also is not exact full-hash equality.
3. A contradictory `RESULT: FAILED ... P4` followed by an all-pass gate report and `RESULT: SUCCEEDED` is accepted, even with exact pins supplied. The parser takes the last verdict instead of rejecting multiple verdicts.
4. A genuine complete, accepted run A's collection and acceptance Boolean can be handed to another runner B that has never collected anything. B publishes successfully; `CURRENT.json` points to **two nonexistent databases**. No run identity, candidate content or acceptance-result binding is checked at publication.

Closure: public acceptance must enforce its complete contract without a bypass switch. Require full frozen manifest/calendar hashes, approved population and the actual run/candidate identity; reject missing or mismatched bindings and multiple/conflicting verdicts. If low-level unit-test helpers need reduced fixtures, separate them from the public acceptance boundary. Publication must consume/verify results for these exact completed candidate views, not a caller-supplied Boolean. Reject wrong-run, missing-file and post-validation changed-candidate cases. A runner-owned validation/finalization path is a reasonable small implementation; no new infrastructure is required.

The cross-run publication case also demonstrates the remaining R4 exposure. Do not count it twice as two independent probes.

## R3 / P2: an inner abort is non-retried but not sticky

Location: `_m2_pilot/transport.py:159`.

The first transport-raised `RunAborted` is correctly propagated after one attempt. However, its handler never sets `aborted_reason`. Calling the same transport again succeeds with status **200**, increasing attempts to **2**, while `aborted_reason` remains NULL.

The delivered test named "STICKY" only tests the first call. The current runner does break its active loop, so this is narrower than the old three-retry defect; it is still the previously required whole-run sticky-stop contract, not an unrelated new feature request.

Closure: latch the original reason before propagating the abort. Test a second call on the same object and require no underlying request and no increase in attempts. Preserve working 403/429 and attempt-ceiling behavior.

## R4 / P1: pointer temporary roles bypass protected-path checks

Locations: `_m2_pilot/pilot_runner.py:112`, `:383` through `:397`.

The guard checks database final/partial roles but not the actual publication roles `CURRENT.json` and `CURRENT.json.tmp`. The fixed temporary filename is opened with `write_text`, which follows existing hardlinks/symlinks.

Reproduction used only a disposable sentinel, never a production file. Before constructing the runner, `CURRENT.json.tmp` was hardlinked to a sentinel outside staging, and that sentinel was explicitly included in `protected`. Construction passed. After a genuinely complete and accepted 52-symbol synthetic collection, publication returned success and **overwrote the protected sentinel** with pointer JSON.

Closure: include every actual publication role in path/protection checks; refuse unsafe existing aliases and use an exclusively created, owned temporary file rather than following/reusing a fixed pre-existing one. Recheck relevant roles at publication. Preserve the previous pointer and pair on write/replace failure. Add actual pointer-write/replace fault injection and protected-alias tests, together with R2's wrong-run/stale-candidate tests. Do not delete or overwrite an unowned temporary path as cleanup.

The delivered "failed publication of run 2" test simulates an HTTP failure before publication; it does not inject a failure into pointer writing/replacement.

## Scope, safety and remaining live limitation

All network connections were denied in the independent script. All database writes, pointer publications and hardlink targets were synthetic disposable fixtures. Temporary fixtures were closed and cleaned up successfully. All reviewed M1/M2 Python files, the approved manifest and calendar retained their SHA-256 hashes. Production main/WAL sizes and nanosecond mtimes remained:

| File at repository root | Bytes | mtime_ns |
|---|---:|---:|
| trading_local.sqlite3 | 1,346,048,000 | 1788517646307317700 |
| market_history.sqlite3 | 1,234,956,288 | 1788493486739967200 |
| market_history.sqlite3-wal | 0 | 1788493486748601200 |

These production checks are metadata checks, not new full-content production hashes. HEAD remains `73f266d`; index empty. No implementation, production data or runtime changes were made. `git diff --check` exited 0 with line-ending warnings, no whitespace errors; no real `staging/pilot_20260906` exists. The only new local artifacts are this reviewer report and its independent probe script; both remain excluded from Git.

The real Sina JS decoder is explicitly unsupported and live transport refuses execution. That is an honestly declared offline limitation, **not an additional defect required to be implemented in this closure**. Passing M2a will not prove live connectivity, source semantics, a three-year research corpus, feature readiness or training completion. No broad backend/M1 re-audit was run or is requested here.

Reviewed fingerprints (SHA-256):

```text
manifest      97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe
calendar      f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656
pilot_runner  74d98af9008138b491601cdf69d02bae8bb1469ab63350b10375f0177abf51ea
acceptance    a697e0f3355dd67636fbea3597faabd106f19ad2bbd1627b5fb50ef54021a161
transport     cd57174739e5d70ac39b58e5eddf942ff0d2fb39f227dd391773eb1bf89126fd
```

## Next instruction to Claude

Close only the remaining R1-R4 counterexamples in this review. Preserve the working fixes and accepted M1 behavior. Keep changes within `_m2_pilot/` and the English M2a handoff/progress documents; do not edit Codex's historical or new reviewer artifacts. Add regressions on the public path, including a complete 50+2 synthetic research/warm-up chain with enforcement on and no caller bypasses. Correct the handoff's claims about body binding, mandatory pins, sticky aborts and integrated-test coverage to match actual execution.

Report exact commands, results and changed files, then stop at `ready_for_review`. Do not call external services/plugins, download data, collect real staging data, alter production/runtime state, start services, stage/commit/push, train or promote anything. Do not reopen M0/M1 or implement the live decoder in this closure.
