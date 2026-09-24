# M2b P1 basis module — Codex independent implementation review

> Historical first-round findings. On 2026-09-09 the corrected implementation closed BR-R1 through BR-R4 in a bounded offline review: Claude suite 41/41; independent expectations 21/21. See [the R2 review](M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md) for the current reviewed hashes and limitations. The original findings below remain the record of the earlier implementation.

Date: 2026-09-09. Verdict: **changes required; bounded implementation acceptance withheld**.

本轮复核实际交付的离线模块，不以此前方案验收代替实现验收。Claude 原测试全部通过，但独立边界检查发现四组需要修复的问题。没有发现 `eligible=true` 分支；这并不能弥补证据校验和输出保护缺口。P1 未关闭，source capability 仍为 FAIL，两次采集授权均已消耗。

## Reviewed identity and scope

- HEAD: `73f266d4165df48bacc6112f037537aed5fb7a58`; staging empty at inspection.
- `claude methods/_m2_smoke/basis_record.py`: SHA-256 `debddb673a9e419b9ab7cd0a9c9718b5778d2937378749fdcf4ed3b663a60a33`.
- `claude methods/_m2_smoke/test_basis_record.py`: SHA-256 `9effcf1b5e981277688d6e9bb342c83f2e6922cc5e5de1c2953497d6913f51c4`.
- Reviewed output: `_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2/`; its stored deterministic digest `c6cc36c64a590bb6433b6708cb9ad2f6dd7a6a4471f69102b84de509a0459c3f` recomputes correctly.
- Retained selected revision: `revision_20260908T082833Z_r2abc_v2`, deterministic digest `099640a21e5927a057f3d2d1468b5765312bf1b68ff0d056051a18317fc81292`, capability FAIL.
- Existing producer files, evidence, proposal, implementation and Claude output were read-only. Synthetic mutations occurred only in temporary copies. Output-guard probes did not create their proposed directories.

## Findings

### BR-R1 — P1: required input verification can be omitted; consumed-file ledger incomplete

Location: `basis_record.py:235-251`, `:388`, `:662-691`.

`verify()` checks `input_hashes` only when it is a nonempty dictionary. Removing that field from a temporary copy of the current v3 PROVENANCE still succeeds with zero declared inputs verified, and the two stock transforms still derive as `none`. A second probe retains only the manifest entry and edits the copied reference extract: verification still succeeds with one declared input verified. Neither probe edits the checks deterministic block or its digest anchors. This is a missing-field bypass, not the acknowledged limit concerning fully self-consistent forgeries.

The unmodified retained input verifies all declared hashes, but its reference extract is absent from returned `consumed_artifacts` and from the output's consumed-file ledger, even though the verifier read and hashed it. Recording only the three initial JSON inputs plus a separate raw-body ledger does not satisfy the complete consumed-file contract.

Required correction: define and enforce the required input inventory for each supported complete schema, including applicable raw/reference inputs; reject missing, partial, malformed or unsafe entries before output. Record recomputed hashes for every artifact actually read, with an unambiguous mapping to any separately recorded producer hashes. Preserve rejection of incomplete legacy schemas and both deterministic anchors.

### BR-R2 — P1: output guard does not enforce the approved root and is case-sensitive on Windows

Location: `basis_record.py:627-651`.

The guard accepts a fresh `basis_eval_*` path beneath `_m2_codex_review`. It also accepts a path beneath `EVIDENCE_codex_guard_probe_never_created`, because protected-prefix comparisons are case-sensitive. Both are guard-only probes: no file or directory was written there. The writer exposes `out_root` and uses this guard, so the omission affects the write boundary, rather than merely the CLI description.

Required correction: constrain normal output to the approved canonical root and a fresh output directory; reject reviewer/evidence/revision/receipt/frozen locations using Windows-appropriate path comparisons. If tests require a scratch root, make that allowance explicit and bounded. Preserve no-overwrite behavior and check resolved containment before creating directories.

### BR-R3 — P2: access/replay cross-checks do not support the claimed positive transform derivation

Location: `basis_record.py:416-440`, `:452-503`.

The access routine treats nonempty `attempt_positions` as a boolean, then selects attempts by `request_index`; it does not validate the actual positions or the attempt URL against the request. In direct synthetic derivation probes, an out-of-range position and a mismatched attempt URL each still produce stock transform `none` without a reason. Removing `R1urls` while keeping per-job R1 PASS has the same result: replay URLs are copied into the record but do not constrain derivation.

These three probes exercise the public derivation function with copied in-memory inputs. They do **not** demonstrate that an arbitrary edit to retained inputs defeats otherwise intact file hashes. They demonstrate that the specified semantic cross-checks are absent from derivation, independently of digest integrity.

Required correction: cross-check request indexes, attempt positions/counts and URL associations; distinguish attempted/responded/skipped evidence; require the applicable evaluated replay URL evidence before a positive transform claim. Missing or inconsistent evidence must yield an explicit refusal/unknown result, while preserving the index-specific rules and vendor-basis unverified state.

### BR-R4 — P2: view evaluation ignores mixed record-producer identities

Location: `basis_record.py:168`, `:607-619`.

`records_comparable()` knows about the new module/rules identity, but `evaluate_view()` compares only vendor basis and upstream pins. Two otherwise identical records with different `record_producer.module_sha256` produce only `vendor_basis_unverified`, with no mixed/incomparable-view reason. Eligibility remains false; this is a provenance and diagnostic contract failure, not a demonstrated eligibility bypass.

Required correction: enforce comparability in view evaluation across module hash, record schema, derivation rules and evaluator rules, as well as upstream identity. Reject unknown versions explicitly. Keep historical records unchanged and every eligibility result false.

## Independent validation and preservation

Command, from repository root:

```powershell
& 'backend/.venv/Scripts/python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_basis_record_codex.py'
```

- Claude suite: **27/27 passed**.
- Codex supplemental expectations: **3/12 passed, 9 failed**, grouped into the four findings above. These are 12 additional expectations, not a replacement count for Claude's suite.
- Driver exit 0 means the review completed and saved its findings; it does not mean acceptance passed.
- Passed supplemental checks: retained stock volume units; all tested vendor-basis assertions ineligible; stored output digest recomputation.
- The review's 101 protected-file hashes were unchanged before/after the suite and probes. Database file sizes and nanosecond mtimes were unchanged; these metadata checks do not constitute database-content certification.
- A process audit hook prohibited socket connection/address resolution/bind, SQLite open, subprocess launch and `os.system`. It blocked one `socket.bind` during the suite. A separate guarded diagnostic traced the same event to urllib3's import-time `_has_ipv6("::1")` probe. The bind was prevented; no HTTP request, capture, adapter replay, SQLite open or service operation was performed by this review.
- Evidence: `_m2_codex_review/basis_record_codex_review_results.json` contains suite output, individual probe results, protected-file hash maps and database metadata.
- Codex wrote only its independent review driver, result JSON and this report. No implementation fix, policy adoption, gate integration, staging, commit or push was performed.

## Next-stage instructions for Claude

Address BR-R1 through BR-R4 in `basis_record.py` and `test_basis_record.py`. Enforce the complete schema-specific input inventory and consumed-file ledger; constrain canonical output roots with Windows-safe comparisons; validate access/replay evidence associations before positive transform derivation; and apply full record-producer comparability in view evaluation. Add focused regressions for each reproduced boundary and preserve the unconditional `eligible=false` contract.

Run only offline synthetic tests and retained-artifact validation. Preserve the existing basis output as a historical artifact and produce one fresh bounded output directory for the corrected version. Do not modify Codex review artifacts, producer sources, retained revisions, evidence, proposal or operational gates. Do not access the network, SQLite, services, tokens or live data; do not replay the adapter, capture, train, stage, commit or push. Report exact commands, counts, hashes and preservation evidence at `ready_for_review`. Do not claim P1 closure, source-capability acceptance or training readiness.
