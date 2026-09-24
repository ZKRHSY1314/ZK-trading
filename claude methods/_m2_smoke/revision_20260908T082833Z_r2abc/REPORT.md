# M2b smoke report

run_id: 20260908T082833Z
run status: completed
abort reason: none

## Verdicts

| scope | verdict |
|---|---|
| job sh600011 | FAIL |
| job sh000300 | PASS |
| job bj920000 | FAIL |
| capability | **FAIL** |

Reasons: sh600011 FAILED; bj920000 FAILED

a capability verdict concerns five captured responses and the decoder, never corpus readiness, feature readiness or training; PASS_WITH_DOCUMENTED_BJ_NON_SERVICE is not an unqualified PASS and authorizes nothing

## Outcome table results

| # | job | transport | payload | request | job | evidence | skipped rest |
|---|---|---|---|---|---|---|---|
| 1 | sh600011 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 2 | sh600011 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 3 | sh000300 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 4 | bj920000 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 5 | bj920000 | ok | decoded | OK | CONTINUE | decoded_payload | False |

## Checks

| id | scope | kind | status | detail |
|---|---|---|---|---|
| EV0 | run | required | PASS | capture envelope complete and self-certified as valid |
| EV3 | run | required | PASS | the frozen reference content hash was recomputed and matches both its own declaration and the capture manifest |
| EV4 | run | required | PASS | every approved pin matches |
| EV5 | run | required | PASS | the frozen selection/threshold contract matches the constants these checks apply |
| EV2 | sh600011 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV2 | sh600011 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV6 | sh600011 | required | FAIL | capture classified this body as 'undecodable'; the retained bytes classify as 'decoded' |
| EV2 | sh000300 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV2 | bj920000 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV2 | bj920000 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV6 | bj920000 | required | FAIL | capture classified this body as 'undecodable'; the retained bytes classify as 'decoded' |
| T3 | run | required | PASS | attempts within the ceiling, source key uniform, pacing respected on actual wire starts (retries included), every issued request bound to its attempt records, request count consistent with the outcome |
| T1 | sh600011 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh600011 | required | PASS | payload state 'decoded' |
| T1 | sh600011 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh600011 | required | PASS | payload state 'decoded' |
| T1 | sh000300 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh000300 | required | PASS | payload state 'decoded' |
| T1 | bj920000 | required | PASS | status 200; served URL equals requested URL |
| T2 | bj920000 | required | PASS | payload state 'decoded' |
| T1 | bj920000 | required | PASS | status 200; served URL equals requested URL |
| T2 | bj920000 | required | PASS | payload state 'decoded' |
| S1 | sh600011 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | sh000300 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | bj920000 | required | PASS | the planned URL set matches the installed adapter constants |
| B2 | run | required | PASS | code-derived: the hfq branch MULTIPLIES by its factor, the qfq branch DIVIDES by its factor, and the adjust="" branch applies neither |
| B1 | run | required | PASS | no factor endpoint was requested |
| D1 | sh600011 | required | PASS | variable name 'KLC_K2_sh600011' matches the expected exchange and symbol; 5935 rows, decoder branch O (3466) |
| D2 | sh600011 | required | PASS | keys present |
| D3 | sh600011 | required | PASS | all in-window dates are on the pinned calendar |
| D4 | sh600011 | required | PASS | OHLC ordering holds on every traded research row |
| D5 | sh600011 | required | PASS | 26 [date, outstanding_share_wan] entries; never labelled amount |
| U4 | sh600011 | advisory | ADVISORY | as-of turnover check on 728 research rows (0 had no applicable share observation); 0 exceed 100%. Denominator age: median 1975 days, max 2516 days - a value carried forward this long is weak evidence, |
| U1 | sh600011 | required | PASS | every research row has positive volume and amount |
| U2 | sh600011 | required | PASS | windowed unit 'share' (one-sided agreement between amount and the price band) |
| B3 | sh600011 | advisory | ADVISORY | 24 rows carry prevclose; 23 differ from the previous close (candidate corporate-action markers, never basis evidence) |
| I2 | sh600011 | required | PASS | close ratio within tolerance on 10 sessions |
| I3 | sh600011 | required | PASS | volume ratio ~ 100 on 10 sessions |
| U3 | sh600011 | required | PASS | amount ratio ~ 1.00 on 10 sessions (yuan, no 10k scaling) |
| B4 | sh600011 | advisory | ADVISORY | the close ratio is flat; a step is evidence that the live series is unadjusted relative to the cached qfq series, not proof (the reference mixes fetch times) |
| C1 | sh600011 | required | PASS | first 2001-12-06 <= 2022-08-24, last 2026-09-07 >= reference tail 2026-09-04, span complete |
| C4 | sh600011 | finding | FINDING | adapter post-processing: 0 duplicate OHLCVA rows, 0 klc rows before the first usable share date 2001-12-06, 4 share dates with no klc row |
| R1 | sh600011 | required | PASS | adapter returned 978 rows 2022-08-24..2026-09-04 over the declared window 20220824..20260904 |
| D1 | sh000300 | required | PASS | variable name 'KLC_KL_sh000300' matches the expected exchange and symbol; 5987 rows, decoder branch D (1479) |
| D2 | sh000300 | required | PASS | keys present |
| D3 | sh000300 | required | PASS | all in-window dates are on the pinned calendar |
| D4 | sh000300 | required | PASS | OHLC ordering holds on every traded research row |
| B3 | sh000300 | advisory | ADVISORY | 0 rows carry prevclose; 0 differ from the previous close (candidate corporate-action markers, never basis evidence) |
| I2 | sh000300 | required | PASS | close ratio within tolerance on 10 sessions |
| I3 | sh000300 | required | PASS | volume ratio ~ 1 on 10 sessions |
| B4 | sh000300 | advisory | ADVISORY | the close ratio is flat; a step is evidence that the live series is unadjusted relative to the cached qfq series, not proof (the reference mixes fetch times) |
| C3 | sh000300 | required | PASS | first 2002-01-04 <= 2022-08-24, last 2026-09-07 >= reference tail 2026-09-02, span complete |
| R1 | sh000300 | required | PASS | index adapter returned 5987 rows 2002-01-04..2026-09-07 (no date arguments; the index adapter returns the full served series) |
| D1 | bj920000 | required | PASS | variable name 'KLC_K2_bj920000' matches the expected exchange and symbol; 1393 rows, decoder branch O (3466) |
| D2 | bj920000 | required | PASS | keys present |
| D3 | bj920000 | required | PASS | all in-window dates are on the pinned calendar |
| D4 | bj920000 | required | PASS | OHLC ordering holds on every traded research row |
| D5 | bj920000 | required | PASS | 42 [date, outstanding_share_wan] entries; never labelled amount |
| U4 | bj920000 | advisory | ADVISORY | as-of turnover check on 728 research rows (0 had no applicable share observation); 0 exceed 100%. Denominator age: median 173 days, max 511 days - a value carried forward this long is weak evidence, n |
| U1 | bj920000 | required | PASS | every research row has positive volume and amount |
| U2 | bj920000 | required | PASS | windowed unit 'share' (one-sided agreement between amount and the price band) |
| B3 | bj920000 | advisory | ADVISORY | 0 rows carry prevclose; 0 differ from the previous close (candidate corporate-action markers, never basis evidence) |
| I2 | bj920000 | required | PASS | close ratio within tolerance on 10 sessions |
| I3 | bj920000 | required | PASS | volume ratio ~ 100 on 10 sessions |
| U3 | bj920000 | required | PASS | amount ratio ~ 1.00 on 10 sessions (yuan, no 10k scaling) |
| B4 | bj920000 | advisory | ADVISORY | the close ratio is flat; a step is evidence that the live series is unadjusted relative to the cached qfq series, not proof (the reference mixes fetch times) |
| C2 | bj920000 | finding | FINDING | BJ outcome 'pre_boundary_history_served' from the decoded KLC history body; the CAUSE (code mapping or otherwise) is NOT established by this observation |
| C2span | bj920000 | required | PASS | every reference session with volume appears live |
| C4 | bj920000 | finding | FINDING | adapter post-processing: 0 duplicate OHLCVA rows, 0 klc rows before the first usable share date 2015-10-27, 17 share dates with no klc row |
| R1 | bj920000 | required | PASS | adapter returned 978 rows 2022-08-24..2026-09-04 over the declared window 20220824..20260904 |
| R1urls | run | required | PASS | the adapter requested only captured URLs |

## Captured bodies

| # | sha256 |
|---|---|
| 1 | `adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02` |
| 2 | `9112ebac1d613c42b7eb0a16ddc81f6717c92c5f4c5ba6b81aef9cd8070ccb86` |
| 3 | `ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647` |
| 4 | `100d3b527b963ebdca39dda23db2cbbd6b2e1e6880299121c334dae4f9c4b7a8` |
| 5 | `2ab669b3ec2d245e074ca969c0dd38538c921d9b6956c2b6dca29ae9c5c5871c` |

deterministic checks sha256: `c23f44bcea71e89d5ee0c0b6bfedf4532dcae3daed71deb5f51b93fe91ff3743`
reference content sha256 (recomputed): `3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9`

This report makes no statement about corpus coverage, feature readiness, models or strategy.