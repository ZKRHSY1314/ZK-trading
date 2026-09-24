# G-3 bounded offline technical validation — 2026-09-09

**Verdict: technically validated for the five hashes below. G3-R1, G3-R2 and G3-R2b are closed in this bounded offline analysis.** This is not user acceptance, P1 closure, vendor-basis certification, source-capability acceptance, three-year corpus certification, training readiness, or authorization for any further operation.

Claude's sole implementation session `Fable 5.1 project advice (fork)` handed off the corrected five files and was observed Idle. HEAD is `73f266d`, with no staged files. Goal/request remain `f8b699e5…` / `c39726d0…`; their authoritative limitations remain operative.

## Validated files

Directory: `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/`.

| File | SHA-256 |
|---|---|
| g3_ratio_analysis.py | 998d915b250c0d3e74a575ce170813fc4d1d47c819db1ed7ed453d6f4cc05604 |
| test_g3_ratio_analysis.py | a71feee09600af459ae3e44ee7413a96f7e2b08c077a7d73d04878818b57a72e |
| results.json | 538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd |
| REPORT.md | 8f7bf13637f0d418237a0f969a71ea25930380c3f8f10601aa611e69995edabd |
| PROVENANCE.json | 1a262d74110e30ef33e32d291038fc6c78a8c70204ccdad581017e9330575456 |

## Evidence and test results

Command: `backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_codex_review/review_g3_ratio_codex_r2b.py"`.

**Claude suite 29/29, exit 0; independent expectations 60/60.** Results are in `_m2_codex_review/g3_ratio_codex_review_r2b_results.json`. The new reviewer preserves the earlier reviewer file, adapts its endpoint-field assertions to the explicitly renamed `endpoint_*` fields, and adds interval-boundary and preservation checks. Its snapshot check is bound to the immutable earlier result map, not to the mutable coordination state.

Verified:

- All retained results and the Markdown report reproduce from retained artifacts; input/code/output hashes recompute and provenance agrees.
- Independent joins reproduce 538 / 501 / 538 ratio points and 537 / 500 / 537 consecutive-usable-date changes for SH600011 / BJ920000 / SH000300.
- Twenty public-path probes preserve the corrected invalid-price behavior on both sides. Full-span and segment usable totals agree.
- Source and fetch-time round trips through an invalid middle row or a vendor-absent middle date retain both crossed boundary dates. Endpoint flags remain false when the endpoints agree; interval flags and report tables correctly remain true. Vendor-only dates contribute no fabricated metadata.
- Every retained ratio, price difference, segment statistic and consecutive-date numerical value is unchanged from the `54088a1d…` reviewer snapshot. Changes are confined to boundary reporting and its evidence/tests/documentation within the authorized five files.
- The original five-file G3 delivery, earlier smoke/evidence/basis files, and the five-file reviewer snapshot remain unchanged. All smoke files match this review's before/after maps.

No adapter replay, external network, SQLite connection, service action, capture, production data change, staging, commit or push was performed. The independent driver runs with remote-network/database guards and an audit hook; no prohibited operation was observed. Local loopback used by the existing offline decoder engine remains permitted.

## Remaining M2 blockers and scheduling decision

G-3's previously uncomputed wider retained ratio series is now available and technically validated as exploratory measurement. This does **not** establish the vendor's basis or explain the stock differences as corporate actions. G-1 still lacks independent corporate-action evidence; G-5 remains the lack of earlier overlap in the retained extract, not proof that the production cache lacks earlier rows. A fresh extract (G-6) and external corporate-action queries are outside the current authorization. U-6 sufficiency and downstream turnover policy are not decided by this review. Historical EV6 failures remain unchanged; both capture authorizations are consumed.

No additional implementation task is dispatched. Under the user's automation rules, pause the recurring heartbeat at this evidence/policy boundary and notify the user. The recommended next decision is whether to authorize a bounded, read-only lookup of official corporate-action records for the two stocks over the retained 470-session comparison spans; no lookup, SQLite access or new capture is authorized or prepared by that recommendation. Any later operational request needs its own explicit scope and review. M2 remains incomplete.

## Next-stage instruction for Claude

Hold. Codex technically validated the current five-file G3 delivery, with your suite at 29/29 and independent checks at 60/60. Preserve these files and all previous artifacts. Do not create an acknowledgment file, revise goal/request documents, rerun tests or begin another task. P1 remains open, U-6 deferred, every eligibility false, source capability FAIL, and both capture authorizations consumed. Wait for a separately scoped user decision on the remaining evidence/policy work; no network, SQLite, capture, services, production changes, training, staging, commit or push is authorized.
