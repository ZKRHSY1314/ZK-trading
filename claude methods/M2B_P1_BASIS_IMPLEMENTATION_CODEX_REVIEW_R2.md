# M2b P1 basis module — Codex R2 implementation review

Date: 2026-09-09. **Verdict: technically validated within the bounded offline implementation scope. BR-R1, BR-R2, BR-R3 and BR-R4 are closed for the reviewed version.**

本轮技术验收通过。结论绑定下面的代码哈希和输出，不代表 P1 整体关闭、用户采纳新政策、数据源能力通过、三年语料认证或训练就绪，也不授予任何新增操作权限。U-6 仍待证据；所有 eligibility 保持 false；两次采集授权均已消耗。

## Reviewed files and evidence

| Artifact | SHA-256 |
| --- | --- |
| `_m2_smoke/basis_record.py` | `0fda4f7effba73ac04a8f10ce35b686a7a646a741650159f55cd9288b6bd2cc7` |
| `_m2_smoke/test_basis_record.py` | `51add34ec943188fa9bdc7a039cd675d5deee26b711409fd99ad04546f6bad67` |
| New output `basis_records.json` | `c5b1bf3c2f660dcca84c1f3d44fba8252b1580d98fbce300d5412340d32448de` |
| New output `PROVENANCE.json` | `a1b662a2cf67bb331202cec7e086887e59115994abd9828d4bcde7d4aafee514` |

Paths above are relative to `claude methods/`. New output directory: `_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4/`.

The output's deterministic records digest is `f9bef731a8f3e7541f4e266a9b8ad11096727e851a551ce75d657af45b83da9d`. Its producer identity matches the installed module. Fresh generation into an explicitly opted-in temporary directory reproduces the full records, eligibility, view eligibility and digest; the volatile generation metadata is excluded as specified. A second write to that directory is refused without modifying its contents.

Selected source revision remains `revision_20260908T082833Z_r2abc_v2`, deterministic digest `099640a21e5927a057f3d2d1468b5765312bf1b68ff0d056051a18317fc81292`. Its capability FAIL and historical EV6 disagreements are unchanged. The earlier basis output remains a historical artifact, not an output of the newly reviewed module.

## Closure evidence

| Finding | Independent result |
| --- | --- |
| BR-R1: required inputs and consumed-file ledger | Missing, empty, malformed and partial inventories are refused. Removing each of the seven required entries separately is refused. The delivered ledger matches recomputed hashes of all nine selected-revision artifacts, including the reference extract. |
| BR-R2: output boundary | Reviewer directories, mixed-case protected prefixes and arbitrary roots are refused. Temporary roots require explicit opt-in. Normal output is constrained to the canonical root and existing targets are refused. Guard probes create no forbidden directories. |
| BR-R3: access/replay associations | Out-of-range, negative, boolean, duplicate and cross-request attempt positions; wrong counts; mismatched URL; absent, failed, empty and unrelated replay URL evidence all prevent a positive transform claim. |
| BR-R4: mixed record producers | Changes to each of module hash, record schema, derivation rules and evaluator rules yield an incomparable view. Unknown rule versions are explicitly reported. All resulting eligibility values remain false. |

The original reviewer's mixed-module expectation was updated in a **new** driver to accept the explicit `incomparable_record_producers` reason together with `comparable_record_producers=false`. This is the corrected diagnostic contract, not a waived failure. The old driver and its result JSON were preserved. The new driver also selects the new output instead of the historical output. Twelve previous expectations now pass; nine additional groups cover inventory variants, association variants, all identity dimensions, output roots, ledger equality, deterministic reproduction and preservation.

These semantic mutation tests operate on copied in-memory inputs or temporary revision copies. They do not claim to demonstrate arbitrary alteration of retained evidence under intact hashes, nor to solve self-consistent forgery. The documented same-digest substitution limitation remains. This review covers the current retained schema and local offline workflow; it is not a general security certification for every possible filesystem or concurrent actor.

## Executed validation

From `D:\codex-A股交易`:

```powershell
& 'backend/.venv/Scripts/python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_basis_record_codex_r2.py'
```

- Claude suite, run by the independent driver: **41/41**, exit 0.
- Codex independent expectations: **21/21**, no unexpected exceptions or failed expectations.
- Driver exit 0 means execution completed; the acceptance conclusion additionally uses the explicit counts and preservation assertions in its result JSON.
- Detailed results: `_m2_codex_review/basis_record_codex_review_r2_results.json`.
- Nine retained directories were unchanged under Claude's test guard. The independent before/after map covers **104 protected files**, with no differences during execution; a subsequent recheck also matched.
- Against the previous review's protected-file snapshot, only the two authorized implementation/test files differ. Existing producer sources, proposal, retained revisions and original basis output match that earlier snapshot. New files are separately identified above; this comparison does not certify unrelated working-tree files.
- Production database sizes and nanosecond mtimes were unchanged. No SQLite connection was opened; metadata preservation does not assert database-content certification.
- Audit guards blocked socket connect/address resolution/bind, SQLite connect, subprocess launch and `os.system`. One blocked socket.bind occurred during the suite, consistent with the urllib3 import-time IPv6 loopback probe diagnosed in the prior round; it was prevented. No network capture, adapter replay or service operation was performed.
- HEAD remains `73f266d4165df48bacc6112f037537aed5fb7a58`; staging empty. Existing unrelated working-tree modifications remain outside this review.

Codex wrote the new independent driver/result, this R2 report and a current-status pointer in its first-round report. It did not modify Claude implementation, retained outputs, producer files, goal/request documents, data, labels, schema or operational gates.

## Next-stage instructions for Claude

Perform a documentation-only handoff update in `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` and `M2B_REAL_SOURCE_VERIFICATION_REQUEST.md`. Record this bounded technical validation with the exact two producer hashes, new output path and deterministic digest, Claude suite 41/41, and Codex independent expectations 21/21. Link this R2 report. Preserve historical findings and prior outputs; make the current status unambiguous.

State that BR-R1 through BR-R4 are closed for these hashes, while P1 remains open, U-6 deferred, every eligibility false, source capability FAIL, and both capture authorizations consumed. Do not treat technical validation as policy adoption, corpus certification, training readiness or operational authorization.

Do not change implementation or generate another output. No tests, adapter replay, ratios, network/plugin calls, SQLite access, capture, services, tokens, production changes, training, staging, commit or push. Return the documentation diff and preservation hashes, then stop.
