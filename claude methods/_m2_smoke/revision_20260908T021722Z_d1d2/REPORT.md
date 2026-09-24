# M2b smoke report

run_id: 20260908T021722Z
run status: aborted
abort reason: 2 consecutive failed jobs; stopping before any further request

## Verdicts

| scope | verdict |
|---|---|
| job sh600011 | FAIL |
| job sh000300 | FAIL |
| job bj920000 | FAIL |
| capability | **FAIL** |

Reasons: run-level checks failed: ['T3']; sh600011 FAILED; sh000300 FAILED; bj920000 FAILED

a capability verdict concerns five captured responses and the decoder, never corpus readiness, feature readiness or training; PASS_WITH_DOCUMENTED_BJ_NON_SERVICE is not an unqualified PASS and authorizes nothing

## Outcome table results

| # | job | transport | payload | request | job | evidence | skipped rest |
|---|---|---|---|---|---|---|---|
| 1 | sh600011 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 2 | sh600011 | skipped | not_applicable | SKIPPED | FAILED | skipped | False |
| 3 | sh000300 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 4 | bj920000 | skipped | not_applicable | SKIPPED | FAILED | skipped | False |
| 5 | bj920000 | skipped | not_applicable | SKIPPED | FAILED | skipped | False |

## Checks

| id | scope | kind | status | detail |
|---|---|---|---|---|
| EV0 | run | required | PASS | capture envelope complete and self-certified as valid |
| EV3 | run | required | PASS | the frozen reference content hash was recomputed and matches both its own declaration and the capture manifest |
| EV4 | run | required | PASS | every approved pin matches |
| EV5 | run | required | PASS | the frozen selection/threshold contract matches the constants these checks apply |
| EV2 | sh600011 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV6 | sh600011 | required | FAIL | capture classified this body as 'undecodable'; the retained bytes classify as 'decoded' |
| EV2 | sh000300 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV6 | sh000300 | required | FAIL | capture classified this body as 'undecodable'; the retained bytes classify as 'decoded' |
| T3 | run | required | FAIL | request 2 was skipped with no earlier skip trigger in job sh600011 |
| T1 | sh600011 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh600011 | required | PASS | payload state 'decoded' |
| T1 | sh000300 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh000300 | required | PASS | payload state 'decoded' |
| S1 | sh600011 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | sh000300 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | bj920000 | required | PASS | the planned URL set matches the installed adapter constants |
| B2 | run | required | PASS | code-derived: the hfq branch MULTIPLIES by its factor, the qfq branch DIVIDES by its factor, and the adjust="" branch applies neither |
| B1 | run | required | PASS | no factor endpoint was requested |
| JOB | sh600011 | required | FAIL | outcome table result FAILED (the auxiliary request was skipped although the history request decoded; no outcome triggered that skip); per-symbol checks are not reached |
| D1 | sh000300 | required | PASS | js variable 'KLC_KL_sh000300', 5987 rows, decoder branch D (1479) |
| D2 | sh000300 | required | PASS | keys present |
| D3 | sh000300 | required | PASS | all in-window dates are on the pinned calendar |
| D4 | sh000300 | required | PASS | OHLC ordering holds on every traded research row |
| B3 | sh000300 | advisory | ADVISORY | 0 rows carry prevclose; 0 differ from the previous close (candidate corporate-action markers, never basis evidence) |
| I2 | sh000300 | required | PASS | close ratio within tolerance on 10 sessions |
| I3 | sh000300 | required | PASS | volume ratio ~ 1 on 10 sessions |
| B4 | sh000300 | advisory | ADVISORY | the close ratio is flat; a step is evidence that the live series is unadjusted relative to the cached qfq series, not proof (the reference mixes fetch times) |
| C3 | sh000300 | required | PASS | first 2002-01-04 <= 2022-08-24, last 2026-09-07 >= reference tail 2026-09-02, span complete |
| R1 | sh000300 | required | PASS | index adapter returned 5987 rows; 0 fabricated dates |
| JOB | bj920000 | required | FAIL | outcome table result FAILED (the history request was never issued because the run aborted first; the job cannot PASS); per-symbol checks are not reached |
| C2 | bj920000 | finding | FINDING | BJ outcome 'inconclusive' from the KLC history request; the CAUSE (code mapping or otherwise) is NOT established by this observation |
| R1urls | run | required | PASS | the adapter requested only captured URLs |

## Captured bodies

| # | sha256 |
|---|---|
| 1 | `adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02` |
| 3 | `ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647` |

deterministic checks sha256: `784ffa6621c3e708fa631deaf678b5bbd8dfafbd30c13347e032584b86d6a0af`
reference content sha256 (recomputed): `3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9`

This report makes no statement about corpus coverage, feature readiness, models or strategy.