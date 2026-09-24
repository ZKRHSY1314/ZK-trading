# M1 key-domain and warm-up review — Codex, 2026-09-06

## Verdict

The specific counterexamples from the previous G1a/G1b/G2a/G2b review are now repaired. Preserve those fixes and the accepted G3 protections.

**M1 is still not fully validated as an executable M2 handoff:** the expected-key contract still misses unexpected dates for a known security (K1). The warm-up readiness claim also needs an explicit consumer/view boundary and matching checks (K2). These are bounded closure items, not a restart of the data audit. No download is authorized.

This review used the data-quality workflow to check the declared grain: security/session/basis in each consumed view, distinguishing research-window coverage from feature warm-up. The primary handoff remains English Markdown, with a companion notebook and executable evidence.

## Independently verified progress

Commands run from the repository root with the project interpreter, -B -X utf8:
- temporal_contract.py: 13/13.
- test_acceptance_gates.py: 46/46.
- test_staging_gate_e2e.py: 36 checks, 0 unexpected.

All three commands exited 0.

The independent fixture plan was computed directly from the actual CSV and pinned calendar, without calling the gate's eligibility implementation. It contains the same 50 stocks plus SH000300 and SH000001 and 36,193 eligible research records in each view. The real command accepts this clean fixture.

Independently reproduced fixed behaviors:
- A deleted history key fails M3/X2.
- A substituted history stock fails M3/X2.
- Actual qfq history declared as none fails H5.
- A changed high with unchanged close fails X2.
- Required 250-session warm-up with no explicit start derives an interval and fails V3b when data is absent.
- Required warm-up with neither start nor depth returns input error 2.

The listed fixes are accepted for these behaviors. Do not rework them.

## K1 [P1] — Unexpected dates for a known security are not compared to eligibility

Location: _m1_closure/staging_gate.py:205-254, particularly :231; identity_gate at :280.

membership_gate computes want - seen but never seen - want. Its unexpected check detects extra symbols only. identity_gate detects differences between the two views, not deviations that both views share from the manifest's eligible domain.

Independent real-CLI probe:
- The actual manifest lists BJ920002 on 2024-05-30.
- Add a 2024-05-29 record for that security to BOTH disposable views, leaving all valid records present.
- Both views now contain 36,194 records.
- The command returns exit 0 / SUCCEEDED.

This is outside the current declared listing-interval contract. It is not a claim that all pre-exchange-listing observations are intrinsically fake; genuine predecessor/venue history would need its own evidenced, explicitly approved mapping. Agreement between two copies does not establish eligibility.

Required closure:
- Compare observed and expected keys in both directions within each declared interval, including extra dates for known symbols.
- Report missing keys, unexpected keys and unexpected symbols separately.
- Do not silently admit pre-listing or post-delisting rows because the same row exists in both views.
- Keep legitimate declared warm-up separate from unexpected research keys. Do not solve this by rejecting every row outside the research interval.
- Unknown eligibility remains unresolved; do not invent listing/history mappings.

Acceptance:
- Existing clean 50+2 control continues to pass.
- A same-key pre-listing addition in BOTH views fails and identifies the security/session.
- A synthetic declared post-delisting addition fails too.
- Legitimate declared, eligible warm-up does not become an unexpected research record.
- Existing missing-key/substitution cases remain failures.

## K2 [P2] — Warm-up readiness is pricing-only, while the handoff does not pin that consumer boundary

Locations: _m1_closure/staging_gate.py:529-530 (identity limited to research window), :542-556 (readiness counts daily_bar_cache only).

I isolated this using a disposable diagnostic subset of two pre-window-listed stocks plus the two benchmarks. This does NOT change the approved pilot population.

- Complete 250-session pre-window warm-up in both views: exit 0.
- Delete ALL pre-window history rows while preserving pricing warm-up: still exit 0, V3b reports ready.
- Restore history then change one warm-up high from 11 to 12: still exit 0, identity reports no mismatch because it compares only the research window.

Observed fact: the command proves pricing warm-up count, not research-history warm-up completeness or cross-view warm-up identity. This becomes an erroneous readiness claim if features consume the history view. If features intentionally consume pricing only, that restriction must be explicit in the contract and result.

Required closure:
- Pin which view(s) provide feature warm-up for the approved pilot/research path.
- If both views are required, apply eligibility, missing/extra-key and declared identity checks to warm-up in both views; missing or divergent required history warm-up must block.
- If only pricing is the intended feature source, explicitly scope the readiness result to pricing and disallow downstream interpretation as history/both-view readiness. History warm-up is then declared not consumed, not silently certified.
- Count eligible, valid observations, not arbitrary dates present before listing.
- Preserve the distinction between complete eligible price coverage and enough observations for a feature. New listings can satisfy one and not the other.
- Advisory pilot collection remains possible only when explicitly authorized and must not claim research/feature readiness.

Acceptance: a genuinely clean eligible warm-up control passes; absent or divergent warm-up in a required view fails; a declared unconsumed view is reported as such; new-listing insufficiency and interval non-overlap remain explicit.

## Test preservation note

The current end-to-end count is still 36, but the suite is not the same 36 cases as before. Several earlier CLI cases (history malformed date/price/duplicate/FK, missing/unsupported transformations, unknown eligibility) were replaced by the latest cases. Primitive tests still cover some functions, but not their CLI wiring.

Retain or restore these already-requested regression scenarios in the current CLI suite; do not treat an unchanged count as proof they were preserved. No broader backend audit is requested.

## Next instruction and boundaries

Close K1 and explicitly resolve K2. Preserve the now-verified G1/G2 behaviors, G3, M0, the accepted census, and the selected 50+2 population. No broad audit or multi-agent workflow.

Writes remain local closure artifacts and English handoff/progress documents under claude methods/. Preserve runtime code, production data, existing datasets, strategies, methodology/knowledge materials and unrelated edits. No network/plugin calls, downloads, migrations, services, staging, commits or pushes.

Report exact commands, actual results, the declared warm-up consumer contract, and remaining limitations; stop at ready_for_review. M2 pilot authorization is still a separate user decision after acceptance. Full-market rebuilding, training-readiness claims and production promotion are not implied.

## Reproduction and safety

Executable: _m1_codex_review/key_contract_review.py
Captured observations: _m1_codex_review/key_contract_results.jsonl
Supplied-suite outputs: _m1_codex_review/key_contract_suite_results.json
Companion: _m1_codex_review/M1_key_contract_review.ipynb

Run from the repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_codex_review\key_contract_review.py'
```

The diagnostic exits 0 when collection and fixed-behavior assertions succeed; the captured false passes remain findings, not acceptance. All fault injections used newly created temporary synthetic databases and were cleaned up. Protected fixture inputs and baseline remained hash-identical. Production main/WAL size and mtime were unchanged, and reviewed artifact hashes stayed unchanged during the probes. HEAD remains 73f266d; no runtime code or production data was changed by this review.
