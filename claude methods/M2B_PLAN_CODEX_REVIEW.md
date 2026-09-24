# M2b plan review — bounded real-source verification

Reviewer: Codex. Reviewed 2026-09-07, approximately 09:31 Asia/Taipei.

## Overall assessment

**Needs revision before live execution. The plan is a suitable basis for boundary 1a offline implementation, provided the three requirements below are incorporated.** This is a planning review, not an executed smoke-test acceptance. No M2b implementation or real-response evidence exists yet. M1 and M2a remain technically validated.

The three requirements can be resolved together in the offline implementation and its tests; a separate broad audit or repeated documentation-only review is unnecessary. Boundary 1a still requires the user's instruction, and boundary 1b requires separate authorization after code review. This review executes neither boundary.

## Verified strengths and calculation spot-checks

- The selected `SH600011`, `BJ920000` and `SH000300` are present in the unchanged approved manifest, with ordinary-control, BJ-code-history and benchmark roles respectively.
- Installed adapter code confirms two requests per raw stock and one per benchmark: **2 + 2 + 1 = 5** nominal attempts, **15** maximum at three attempts per request. The index path uses `hisdata/klc_kl.js` and the `d=2020_2_4` parameter; the stock path uses `hisdata_klc2`.
- `stock_zh_a_sina.py:196-208` explicitly names request #2/#5 data `outstanding_share`, multiplies it by 10,000 and uses it for turnover. It is not traded amount. The plan correctly separates this from the history payload's `amount` field.
- Keeping real-source decoding separate from the validated synthetic-envelope M2a path is appropriate. The plan does not stamp `none`, run the 50+2 M1 gate on three symbols, promote databases or imply training readiness.
- Default no-network/no-write planning, explicit arming, per-attempt accounting, protected inputs, raw-body capture, offline adapter replay and separate execution approval are appropriate design choices.
- The current handoff now correctly records M2a's accepted review evidence instead of the obsolete 48-test state.

Evidence inspected: `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md` in full; the current goal handoff; installed stock/index adapter code and URL constants; local Requests send/response handling; relevant M2a and cache-provider code. The approved manifest/calendar and M2a runner/test hashes still match the prior acceptance. No live endpoint behavior or current vendor quota was tested.

## Required changes for the offline implementation

### S1 — the proposed 15-minute limit is not a hard deadline

Plan locations: lines 71 and 76; P-A at line 101.

The plan correctly says a read timeout measures gaps between reads, but then calls a deadline checked only before each request a hard runtime limit. A response that keeps sending small chunks within each 30-second gap can keep one request active past 15 minutes. The installed Requests session consumes `r.content` before returning when `stream=False` (`requests/sessions.py:826-827`), so the proposed outer check cannot regain control to stop it. Decoding also needs bounded execution.

Implement an actually enforceable end-to-end deadline covering network body consumption, retry/backoff and decode/replay, with a documented bounded shutdown allowance. A supervised task-owned worker is one possible approach; it must not terminate unrelated applications or services. Alternatively describe a softer limit honestly, but that is not the proposed hard-bounded live-run contract. Include response-size and decoder resource limits as part of the small runner's safety envelope.

Acceptance evidence: fake-clock/worker tests for a continuously trickling response, a blocked in-flight call, retry/backoff near the deadline and a stuck decoder. Show that no request starts after abort and that partial evidence survives.

### S2 — BJ transport/decode failure must not become a positive capability finding

Plan locations: Section 6 verdict definition, T3 at line 152 and C2 at line 189.

C2 maps any non-200, empty body or undecodable response to `not_served_under_92_code`, calls that a decisive finding and permits capability PASS. Those observations do not distinguish unsupported history from a temporary upstream error, transport trouble, an incorrect URL or a decoder defect. Meanwhile T3 requires all five requests to end with HTTP 200, and the failed-job rule skips a stock job's remaining request. These rules give conflicting outcomes for the same BJ failure.

Define one explicit outcome table with transport status, payload/decode status, whether request #5 is skipped, job result and overall result. Preserve 403/429 as unconditional aborts. Exhausted 5xx/timeouts, TLS failures and decoder exceptions must remain failed or inconclusive evidence, not be relabelled supported non-service. If an explicit vendor response establishes non-service at the requested path, report that bounded observation; do not infer its historical-code cause without evidence. A completed investigation with a documented BJ limitation may be reported separately, but must not be an unqualified all-three capability PASS or authorize the 52-symbol pilot.

Acceptance evidence: offline cases for BJ 404/explicit non-service, exhausted 503, timeout, 403/429, empty/HTML payload, malformed encoded payload, valid post-boundary-only history and valid pre-boundary history. Each must have a single deterministic outcome consistent with request-count checks.

### S3 — freeze the reference inputs needed for reproducible checks

Plan locations: F2 at line 109, I2/I3/U3 and C1-C3, output retention in Section 5, reproduction promise at line 204.

Checks depend on local cache rows read at F2, but retention specifies raw remote bodies plus a summary of the local reference. Replaying later against a refreshed production cache can change identity/unit/coverage results even when all captured response hashes are identical. A summary of the tail is insufficient to reconstruct every ratio and membership comparison.

Add a minimal read-only reference extract to the proposed temporary/evidence artifacts: only the selected market-data rows/fields actually consumed, their source, basis, unit and timestamps, plus the query/selection rules, calendar, thresholds and hashes. Disclose this addition in the boundary-1b retention request. Replay must consume these frozen inputs without opening production. Compare deterministic check content; exclude run timestamps and other intentionally variable metadata from byte-equality claims.

Also qualify the reference rather than assuming all mixed-source cached `qfq` tail rows equal raw prices. Insufficient overlap, zero denominators or unestablished adjustment/unit comparability must produce explicit inconclusive/reference-quality reasons. Do not repair these by changing production data or treating the cache as unquestionable ground truth.

Acceptance evidence: capture a synthetic reference, alter the mock current cache, then prove replay output remains unchanged and no production database is opened during replay.

## Minor clarifications — not separate blockers

- P-B returns decoded records; P-C should compare the **bytes-to-text decoding step** with captured `response.text`, not compare the decoder's record output with a string.
- The installed qfq branch divides OHLC by its factor (`stock_zh_a_sina.py:293-296`); the plan's general wording that qfq multiplies is inaccurate. Keep basis evidence tied to the actual raw branch and do not infer a label from `prevclose`.
- U4's outstanding-share comparison should be date-aligned, rather than comparing an unspecified share observation with maximum volume across the whole window. It remains advisory.
- Logs should redact authorization/cookie/proxy credential fields even if the current expected request environment is credential-free. Do not copy arbitrary future request headers verbatim into evidence.

## Recommended next handoff

Implement only boundary 1a once the user authorizes it: P-A..P-D under `claude methods/_m2_smoke/`, with socket-blocked tests and the three requirements above. Update the English request/ledger alongside code. Preserve validated M1/M2a and reviewer artifacts. No additional agent-review campaign or broad data audit is needed.

Return exact files, commands, test results and the write-nothing `--plan` output. Stop at `ready_for_review`. The live smoke, evidence-retention choice and the later 52-symbol pilot remain separate user decisions. No network/plugin calls, downloads, production/runtime changes, service operations, commits/pushes, training or promotion are implied.

## Review scope and safety

This review followed the data-validation distinction between supported claims, assumptions and unrun checks. There are no quantitative charts requiring visual QA. Local cache row-count/ratio claims were not independently queried in this pass; their future reference-quality checks remain necessary. No live payload, TLS connection, quota or executable M2b test result is claimed.

Only local documents/code/manifests and file metadata were read. No production database was opened. Production sizes remain 1,346,048,000 bytes for `trading_local.sqlite3`, 1,234,956,288 for `market_history.sqlite3`, and zero for its WAL; their visible UTC mtimes remain at the earlier baseline. M2a runner SHA-256 remains `943a8c3f5f34a0739115771ac952dd3576ae1ccf4df2b1bf7089de00c90b97cb`; its test file remains `5ec054560fbc92fcd9a30cccbf37dffbf20327389e53922eb8ce3efd52bc4ac1`. HEAD is `73f266d`, index empty. `_m2_smoke/`, `tmp/` and `staging/` were absent when checked.

The only addition made by this review is this local English report, excluded from Git. No M2a suite was rerun: its reviewed source hashes are unchanged, and this request concerns a new plan rather than executable M2b code.
