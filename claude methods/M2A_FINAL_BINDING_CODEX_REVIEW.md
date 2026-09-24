# M2a 73-case closure: two remaining acceptance-binding defects

Reviewer: Codex. Date: 2026-09-06, approximately 23:52 Asia/Taipei.

**Verdict: NOT YET VALIDATED. R1, R3 and the reviewed R4 counterexamples are closed. R2 is partially closed; only the two concrete binding defects below remain blocking in this review.** Preserve accepted M1 and the working fixes. Do not restart earlier audits or implement live access in this closure.

## Independently executed evidence

- Delivered suite: **73 cases, 0 unexpected, exit 0**.
- `claude methods/_m2_codex_review/review_m2a_binding.py`: five groups of successful closure controls, one successful full-chain control, two reproduced R2 defects and a final unchanged-input check. Exit 0 means the observations reproduced, **not** that the stage passed acceptance.
- Full-chain fixtures use the actual approved 50-stock/two-benchmark manifest, the pinned calendar and **synthetic** eligible research/warm-up bars. Both disposable views are built through fake transport and the actual decoder. The actual unchanged M1 snapshot/validate entry points run, followed by the public acceptance functions with full manifest/calendar hashes and the candidate fingerprint.
- No forged verdict objects, monkeypatched validators, fabricated M1 gate output, enforcement switches or replacement response bodies were used for either remaining defect. Fault injection is used only in the separate R4 publication-failure control.

Reproduce from the repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_pilot\test_m2a.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_codex_review\review_m2a_binding.py'
```

## Closed controls — keep these fixes

- R1: the `responses` override is rejected before a request or staging creation. Actual HTML responses produce zero successful jobs.
- R2 portions: `enforce=False` no longer exists; truncated manifest hashes, missing calendar pins and conflicting RESULT lines are refused. The delivered suite also passes same-population symbol substitution, wrong-run finalization and changed-candidate cases.
- R3: two calls after an inner abort produce only one underlying attempt; the original reason is retained.
- R4: the actual run-specific pointer temporary path hardlinked to a protected disposable sentinel is refused at construction. An unowned temporary is preserved, not reused or deleted. Actual `os.replace` failure leaves the previous pointer unchanged and removes the exclusively owned temporary.
- Healthy full-chain control: 52 jobs succeed; research exits 0; warm-up exits 1 only with the expected 14-security depth shortfall; both verdicts accept and finalization publishes the synthetic candidate.

## R2.1 / P1 — a caller-supplied fingerprint does not bind gate execution

Locations: `_m2_pilot/acceptance.py:232`, especially `:249`; public entry points `:275` and `:298`; `_m2_pilot/pilot_runner.py:429`.

`bind_inputs()` checks that a candidate fingerprint was supplied, then copies it directly into the verdict. It does not establish that the supplied M1 output was produced by validating that candidate. `finalize()` compares that copied string with the files' fingerprint, so it trusts a binding that the acceptance layer never verified.

Reproduction:

1. Build valid candidate A and run the real M1 research and warm-up gates. Save their untouched output.
2. Build candidate B through the normal collector, omitting one eligible research-day bar for SH688001 from both source envelopes. B completes 52 jobs but contains **45,934**, not 45,935, rows per view.
3. Run B's actual M1 gates. Research exits **1**, fails gates **M1 and M3**, and both public acceptance verdicts reject B.
4. Call the same public acceptance functions with **A's original report text** and **B's genuine collection fingerprint**, with correct full manifest/calendar pins. Both return accepted.
5. Finalize B with B's own collection and these publicly issued verdicts. It returns **published=True**.

Thus the normal wrong-run check is useful but insufficient: the report can be rebound before finalization. This is an accidental stale-report/candidate mix-up the boundary is intended to catch, not a claim that Python must defend against arbitrary hostile code in its own process.

Required closure: make the official candidate-validation path own the actual M1 invocations and receipt creation. It should select these exact view paths and frozen inputs, fingerprint before and after validation, and refuse changes. Keep raw-text parsing as a lower-level helper, not a way to mint publishable validation merely by supplying an unrelated fingerprint. A small orchestration wrapper around the unchanged M1 gate is sufficient; no signatures, service or new infrastructure are requested.

## R2.2 / P1 — a research verdict can stand in for warm-up acceptance

Location: `_m2_pilot/pilot_runner.py:429` through `:438`.

Both finalization slots only require `accepted=True` and a matching candidate fingerprint. Neither verifies which validation mode produced the verdict. Consequently `finalize(collection, research_verdict, research_verdict)` can publish without successful warm-up collection acceptance.

Reproduction:

1. Build candidate C with complete research data but remove one SH688001 warm-up day from both response envelopes.
2. C's real research gate exits **0** and its public research verdict accepts.
3. Its real warm-up path rejects: **W1_pricing=FAIL**. This is an integrity gap, not the approved IPO depth exception.
4. Pass C's genuine research verdict in both finalization slots. Finalization returns **published=True**, despite the demonstrated warm-up failure.

Required closure: receipts must carry a validated mode/contract identity, and finalization must require one research receipt and one warm-up-collection receipt for the same run, frozen inputs and candidate. Do not infer the receipt mode from the argument name or permit two copies of the research receipt. Retain the distinction between accepted warm-up collection integrity and feature readiness.

## Bounded next step

Change only the validation/finalization binding path, its focused tests, and the English M2a handoff/progress documents. Preserve all working R1/R3/R4 fixes and M1 behavior. Do not modify Codex reviewer artifacts.

Required regressions:

1. Good A report plus bad B candidate cannot create publishable acceptance; B's own required failures remain blocking.
2. A research receipt cannot satisfy warm-up collection acceptance, including when actual warm-up integrity fails.
3. Healthy approved 50+2 synthetic research/warm-up collection still publishes through the official validation path.
4. Existing wrong-run and post-validation mutation rejection stays green; a candidate changing during the gate invocation is rejected by the same binding mechanism.

Return exact commands, results and changed files, then stop at `ready_for_review`. No broader M0/M1 audit, live decoder work, network/plugin calls, downloads, real staging collection, production/runtime changes, services, Git staging/commit/push, training or promotion.

## Safety and version evidence

Socket connections were blocked in the independent probe. All database writes and publications were disposable synthetic fixtures, cleaned up successfully. Reviewed M1/M2 code, manifest and calendar hashes stayed unchanged. Production main/WAL size and nanosecond mtime checks remained at the previous baseline:

| File at repository root | Bytes | mtime_ns |
|---|---:|---:|
| trading_local.sqlite3 | 1,346,048,000 | 1788517646307317700 |
| market_history.sqlite3 | 1,234,956,288 | 1788493486739967200 |
| market_history.sqlite3-wal | 0 | 1788493486748601200 |

These are production metadata checks, not new full-content hashes. HEAD remains `73f266d`, index empty; no real `staging/pilot_20260906` exists. `git diff --check` exited 0 with line-ending warnings, not whitespace errors. No Claude implementation files were changed in this review; only this English reviewer report and its probe script were added locally and remain excluded from Git.

Reviewed SHA-256:

```text
pilot_runner.py  4a524fc5943c4546b382aea9839fff4d675983007f2b37883922d769e96948ef
acceptance.py    efa46c13f9706a53113dc0d47930f97f19a26d8796c92e300220bdfa99e33e07
transport.py     f57bbc6c7237ae56bbb28a49df8c2d42bc48b4187def8d66486a9afbd905cfb7
test_m2a.py      cc6a66e202a5ade5adeff3c459d26ca2bf7c62e05f345ea239889dab5ecbcc4d
```

The deliberate live-decoder limitation remains outside this closure. No live-source readiness, completed research corpus or training completion is implied by these offline results.
