# M2b smoke report

run_id: 20260908T021722Z
run status: aborted
abort reason: 2 consecutive failed jobs; stopping before any further request

## Verdicts

| scope | verdict |
|---|---|
| job sh600011 | INCONCLUSIVE |
| job sh000300 | INCONCLUSIVE |
| job bj920000 | FAIL |
| capability | **FAIL** |

Reasons: sh600011 INCONCLUSIVE; sh000300 INCONCLUSIVE; bj920000 FAILED

a capability verdict concerns five captured responses and the decoder, never corpus readiness, feature readiness or training; PASS_WITH_DOCUMENTED_BJ_NON_SERVICE is not an unqualified PASS and authorizes nothing

## Outcome table results

| # | job | transport | payload | request | job | evidence | skipped rest |
|---|---|---|---|---|---|---|---|
| 1 | sh600011 | ok | undecodable | BAD_DECODE | INCONCLUSIVE_DECODE | inconclusive_decode | True |
| 2 | sh600011 | skipped | not_applicable | SKIPPED | CONTINUE | skipped | False |
| 3 | sh000300 | ok | undecodable | BAD_DECODE | INCONCLUSIVE_DECODE | inconclusive_decode | True |
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
| S2 | sh600011 | required | FAIL | the pinned routine could not decode this body: body is not a single quoted `var NAME = "...";` assignment |
| EV2 | sh000300 | required | PASS | P-B's bytes-to-text reproduces the captured response.text |
| S2 | sh000300 | required | FAIL | the pinned routine could not decode this body: body is not a single quoted `var NAME = "...";` assignment |
| T3 | run | required | PASS | attempts within the ceiling, source key uniform, pacing respected on actual wire starts (retries included), every issued request bound to its attempt records, request count consistent with the outcome |
| T1 | sh600011 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh600011 | required | PASS | payload state 'undecodable' |
| T1 | sh000300 | required | PASS | status 200; served URL equals requested URL |
| T2 | sh000300 | required | PASS | payload state 'undecodable' |
| S1 | sh600011 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | sh000300 | required | PASS | the planned URL set matches the installed adapter constants |
| S1 | bj920000 | required | PASS | the planned URL set matches the installed adapter constants |
| B2 | run | required | PASS | code-derived: the hfq branch MULTIPLIES by its factor, the qfq branch DIVIDES by its factor, and the adjust="" branch applies neither |
| B1 | run | required | PASS | no factor endpoint was requested |
| JOB | sh600011 | required | INCONCLUSIVE | outcome table result INCONCLUSIVE_DECODE (decided by the KLC history request: ok/undecodable); per-symbol checks are not reached |
| JOB | sh000300 | required | INCONCLUSIVE | outcome table result INCONCLUSIVE_DECODE (decided by the KLC history request: ok/undecodable); per-symbol checks are not reached |
| JOB | bj920000 | required | FAIL | outcome table result FAILED (the history request was never issued because the run aborted first; the job cannot PASS); per-symbol checks are not reached |
| C2 | bj920000 | finding | FINDING | BJ outcome 'inconclusive' from the KLC history request; the CAUSE (code mapping or otherwise) is NOT established by this observation |
| R1urls | run | required | PASS | the adapter requested only captured URLs |

## Captured bodies

| # | sha256 |
|---|---|
| 1 | `adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02` |
| 3 | `ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647` |

deterministic checks sha256: `02e1b76483cd659b5a16f1df78304392e37effcc706a5c325317eefd42448703`
reference content sha256 (recomputed): `3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9`

This report makes no statement about corpus coverage, feature readiness, models or strategy.

## Output tree SHA-256

- `REPORT.md` `9595b689c62b0793556e21a94fa3b251e2edccaf72d26b1ec5b28798fadd5255`
- `capture_manifest.json` `09a3442a284dca4d1ea533f43a23a345ab16c3616cc27f4fa00c65e5be65ce6c`
- `checks.json` `87d8b16278b5dff7e22dc8df3da2a3957ecf10ff46cd100a97a1f2e1b07bc104`
- `plan.txt` `7f7c51e3191c0448efd3ce978e4af9098d4725278fc5a4a76d0d75f4cd3d4b29`
- `raw/01_sh600011_klc_kl.js.bin` `adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02`
- `raw/03_sh000300_klc_kl.js.bin` `ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647`
- `reference/reference_extract.json` `ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2`
