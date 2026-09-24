# M2b smoke report

run_id: 20260908T082833Z
run status: completed
abort reason: none

## Verdicts

| scope | verdict |
|---|---|
| job sh600011 | FAIL |
| job sh000300 | INCONCLUSIVE |
| job bj920000 | FAIL |
| capability | **FAIL** |

Reasons: run-level checks failed: ['R1']; sh600011 FAILED; bj920000 FAILED

a capability verdict concerns five captured responses and the decoder, never corpus readiness, feature readiness or training; PASS_WITH_DOCUMENTED_BJ_NON_SERVICE is not an unqualified PASS and authorizes nothing

## Outcome table results

| # | job | transport | payload | request | job | evidence | skipped rest |
|---|---|---|---|---|---|---|---|
| 1 | sh600011 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 2 | sh600011 | ok | undecodable | BAD_DECODE | INCONCLUSIVE_DECODE | inconclusive_decode | True |
| 3 | sh000300 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 4 | bj920000 | ok | decoded | OK | CONTINUE | decoded_payload | False |
| 5 | bj920000 | ok | undecodable | BAD_DECODE | INCONCLUSIVE_DECODE | inconclusive_decode | True |

## Checks

| id | scope | kind | status | detail |
|---|---|---|---|---|
| EV0 | run | required | PASS | capture envelope complete and self-certified as valid |
| EV3 | run | required | PASS | the frozen reference content hash was recomputed and matches both its own declaration and the capture manifest |
| EV4 | run | required | PASS | every approved pin matches |
| EV5 | run | required | PASS | the frozen selection/threshold contract matches the constants these checks apply |
| EV2 | sh600011 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV2 | sh600011 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| S2 | sh600011 | required | FAIL | the pinned routine could not decode this body: entry 0 is not a [date, value] pair |
| EV2 | sh000300 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV2 | bj920000 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| EV2 | bj920000 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| S2 | bj920000 | required | FAIL | the pinned routine could not decode this body: entry 0 is not a [date, value] pair |
| T3 | run | required | PASS | attempts within the ceiling, source key uniform, pacing respected on actual wire starts (retries included), every issued request bound to its attempt records, request count consistent with the outcome |
| T1 | sh600011 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh600011 | required | PASS | payload state 'decoded' |
| T1 | sh600011 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh600011 | required | PASS | payload state 'undecodable' |
| T1 | sh000300 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh000300 | required | PASS | payload state 'decoded' |
| T1 | bj920000 | required | PASS | status 200; served URL equals requested URL |
| T2 | bj920000 | required | PASS | payload state 'decoded' |
| T1 | bj920000 | required | PASS | status 200; served URL equals requested URL |
| T2 | bj920000 | required | PASS | payload state 'undecodable' |
| S1 | sh600011 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | sh000300 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | bj920000 | required | PASS | the planned URL set matches the installed adapter constants |
| B2 | run | required | PASS | code-derived: the hfq branch MULTIPLIES by its factor, the qfq branch DIVIDES by its factor, and the adjust="" branch applies neither |
| B1 | run | required | PASS | no factor endpoint was requested |
| R1 | run | required | FAIL | the adapter replay raised: TypeError: cannot do slice indexing on DatetimeIndex with these indexers [] of type str |
| JOBaux | sh600011 | required | INCONCLUSIVE | history served and decoded; the auxiliary outstanding-share request is ok/undecodable (BAD_DECODE). Missing auxiliary evidence is inconclusive capability evidence - never a history-absence finding and |
| D1 | sh600011 | required | FAIL | js variable 'KLC_K2_sh600011', 5935 rows, decoder branch O (3466) |
| D2 | sh600011 | required | PASS | keys present |
| D3 | sh600011 | required | PASS | all in-window dates are on the pinned calendar |
| D4 | sh600011 | required | PASS | OHLC ordering holds on every traded research row |
| D5 | sh600011 | required | INCONCLUSIVE | no outstanding-share series: the auxiliary request is ok/undecodable (status 200). This is missing AUXILIARY evidence, not history evidence |
| U4 | sh600011 | advisory | ADVISORY | not computable without the outstanding-share series |
| U1 | sh600011 | required | PASS | every research row has positive volume and amount |
| U2 | sh600011 | required | PASS | windowed unit 'share' (one-sided agreement between amount and the price band) |
| B3 | sh600011 | advisory | ADVISORY | 24 rows carry prevclose; 23 differ from the previous close (candidate corporate-action markers, never basis evidence) |
| I2 | sh600011 | required | PASS | close ratio within tolerance on 10 sessions |
| I3 | sh600011 | required | PASS | volume ratio ~ 100 on 10 sessions |
| U3 | sh600011 | required | PASS | amount ratio ~ 1.00 on 10 sessions (yuan, no 10k scaling) |
| B4 | sh600011 | advisory | ADVISORY | the close ratio is flat; a step is evidence that the live series is unadjusted relative to the cached qfq series, not proof (the reference mixes fetch times) |
| C1 | sh600011 | required | PASS | first 2001-12-06 <= 2022-08-24, last 2026-09-07 >= reference tail 2026-09-04, span complete |
| C4 | sh600011 | finding | FINDING | adapter post-processing: 0 duplicate OHLCVA rows, 0 klc rows before the first share date None, 0 share dates with no klc row |
| R1 | sh600011 | required | INCONCLUSIVE | no adapter replay: the auxiliary body was not captured and the installed adapter fetches both URLs |
| D1 | sh000300 | required | PASS | js variable 'KLC_KL_sh000300', 5987 rows, decoder branch D (1479) |
| D2 | sh000300 | required | PASS | keys present |
| D3 | sh000300 | required | PASS | all in-window dates are on the pinned calendar |
| D4 | sh000300 | required | PASS | OHLC ordering holds on every traded research row |
| B3 | sh000300 | advisory | ADVISORY | 0 rows carry prevclose; 0 differ from the previous close (candidate corporate-action markers, never basis evidence) |
| I2 | sh000300 | required | PASS | close ratio within tolerance on 10 sessions |
| I3 | sh000300 | required | PASS | volume ratio ~ 1 on 10 sessions |
| B4 | sh000300 | advisory | ADVISORY | the close ratio is flat; a step is evidence that the live series is unadjusted relative to the cached qfq series, not proof (the reference mixes fetch times) |
| C3 | sh000300 | required | PASS | first 2002-01-04 <= 2022-08-24, last 2026-09-07 >= reference tail 2026-09-02, span complete |
| R1 | sh000300 | required | INCONCLUSIVE | index adapter returned None rows; 0 fabricated dates |
| JOBaux | bj920000 | required | INCONCLUSIVE | history served and decoded; the auxiliary outstanding-share request is ok/undecodable (BAD_DECODE). Missing auxiliary evidence is inconclusive capability evidence - never a history-absence finding and |
| D1 | bj920000 | required | FAIL | js variable 'KLC_K2_bj920000', 1393 rows, decoder branch O (3466) |
| D2 | bj920000 | required | PASS | keys present |
| D3 | bj920000 | required | PASS | all in-window dates are on the pinned calendar |
| D4 | bj920000 | required | PASS | OHLC ordering holds on every traded research row |
| D5 | bj920000 | required | INCONCLUSIVE | no outstanding-share series: the auxiliary request is ok/undecodable (status 200). This is missing AUXILIARY evidence, not history evidence |
| U4 | bj920000 | advisory | ADVISORY | not computable without the outstanding-share series |
| U1 | bj920000 | required | PASS | every research row has positive volume and amount |
| U2 | bj920000 | required | PASS | windowed unit 'share' (one-sided agreement between amount and the price band) |
| B3 | bj920000 | advisory | ADVISORY | 0 rows carry prevclose; 0 differ from the previous close (candidate corporate-action markers, never basis evidence) |
| I2 | bj920000 | required | PASS | close ratio within tolerance on 10 sessions |
| I3 | bj920000 | required | PASS | volume ratio ~ 100 on 10 sessions |
| U3 | bj920000 | required | PASS | amount ratio ~ 1.00 on 10 sessions (yuan, no 10k scaling) |
| B4 | bj920000 | advisory | ADVISORY | the close ratio is flat; a step is evidence that the live series is unadjusted relative to the cached qfq series, not proof (the reference mixes fetch times) |
| C2 | bj920000 | finding | FINDING | BJ outcome 'pre_boundary_history_served' from the decoded KLC history body (auxiliary outstanding-share evidence ABSENT: inconclusive, not an absence finding); the CAUSE (code mapping or otherwise) is |
| C2span | bj920000 | required | PASS | every reference session with volume appears live |
| C4 | bj920000 | finding | FINDING | adapter post-processing: 0 duplicate OHLCVA rows, 0 klc rows before the first share date None, 0 share dates with no klc row |
| R1 | bj920000 | required | INCONCLUSIVE | no adapter replay: the auxiliary body was not captured and the installed adapter fetches both URLs |

## Captured bodies

| # | sha256 |
|---|---|
| 1 | `adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02` |
| 2 | `9112ebac1d613c42b7eb0a16ddc81f6717c92c5f4c5ba6b81aef9cd8070ccb86` |
| 3 | `ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647` |
| 4 | `100d3b527b963ebdca39dda23db2cbbd6b2e1e6880299121c334dae4f9c4b7a8` |
| 5 | `2ab669b3ec2d245e074ca969c0dd38538c921d9b6956c2b6dca29ae9c5c5871c` |

deterministic checks sha256: `8ffb30b06a70aee4d301f4d7cea53c34e0ea8374dc0587d69b8848cb4f2ed5c2`
reference content sha256 (recomputed): `3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9`

This report makes no statement about corpus coverage, feature readiness, models or strategy.

## Output tree SHA-256

- `REPORT.md` `f5934456605d88371c24da8dfe08bd48df4b4857afec4d1248192fc54d83146e`
- `capture_manifest.json` `771486f8ada3c641eec8036ac9313f5dcad2e402f112fcca656f2a1c620ea355`
- `checks.json` `f7c9444b90c0c86ed3f1c5f7f0783ba785425672759440c30448466a8bdbc932`
- `plan.txt` `62b9553d4087c6be218ddd3efe7d8b9beb7c0429b53f76b35b179c15e50426e4`
- `raw/01_sh600011_klc_kl.js.bin` `adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02`
- `raw/02_sh600011_getAmountBySymbol.bin` `9112ebac1d613c42b7eb0a16ddc81f6717c92c5f4c5ba6b81aef9cd8070ccb86`
- `raw/03_sh000300_klc_kl.js.bin` `ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647`
- `raw/04_bj920000_klc_kl.js.bin` `100d3b527b963ebdca39dda23db2cbbd6b2e1e6880299121c334dae4f9c4b7a8`
- `raw/05_bj920000_getAmountBySymbol.bin` `2ab669b3ec2d245e074ca969c0dd38538c921d9b6956c2b6dca29ae9c5c5871c`
- `reference/reference_extract.json` `ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2`
