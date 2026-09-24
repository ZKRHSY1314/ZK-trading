# G-3 r2 independent review — 2026-09-09

Verdict: **G3-R1 closed for the pins below; G3-R2 numerical output validated, with one remaining metadata-boundary correction (G3-R2b).** This is bounded offline technical review only. P1 remains open, U-6 deferred, all eligibility false, source capability FAIL, both capture authorizations consumed.

Claude's sole fork owner delivered `ready_for_review` and stated that editing had stopped. UI was independently confirmed Idle before review. HEAD remains `73f266d`; staging is empty. The goal/request hashes remain `f8b699e5…` / `c39726d0…`.

## Reviewed pins

Directory: `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/`.

| File | SHA-256 |
|---|---|
| g3_ratio_analysis.py | 54088a1d16235a8f3c37e8cbe7b3db6b2b4b05e489637f77c3e62c3b060463cb |
| test_g3_ratio_analysis.py | ef71a87401bffc414cdd91a35825dfe65c40cdd4996dfc3c57b0803aa07ddffc |
| results.json | 6d59ea78626dbf294556e4081485b63b9185c0269bc987e1c6aef144343a4ffb |
| REPORT.md | 9c6d33449af6eb4cadbe73529623e85b2371527e460562f1edeef01166a640f8 |
| PROVENANCE.json | 019dc65fb1dc0ed14443cd05d7ef6baf8750ca4c2daeef7191ce7b4fd20641df |

An exact, hash-verified copy of these five files is retained at `_m2_codex_review/g3_r2_reviewed_54088a1d/`. This is a reviewer-owned historical snapshot; Claude must not modify it. The original `g3_ratio_analysis_20260909/` remains byte-identical as well.

## Verification

Command: `backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_codex_review/review_g3_ratio_codex_r2.py"`.

Driver exit 0 denotes completed execution, not acceptance: **43/44 independent expectations pass**, and Claude's suite reproduces **21/21**. Results: `_m2_codex_review/g3_ratio_codex_review_r2_results.json`.

All retained results and the rendered report reproduce. Input/code/output hashes recompute and provenance agrees. Independent joins reproduce 538/501/538 ratio points and 537/500/537 changes. Twenty public `analyse()` probes cover ten invalid price types on both input sides, including null, booleans, strings, NaN and infinities; invalidity preserves matched counts, removes unusable points consistently, and produces JSON-safe results. All old smoke and original G3 files from the previous checkpoint remain unchanged. Every smoke file in this run's before/after maps is unchanged. No adapter replay, external network, SQLite, service action or production mutation occurred; network/database guards and an audit hook were active, with no prohibited operations observed.

## G3-R2b — P2: skipped-date boundaries are lost when endpoint metadata returns to its original value

Location: `g3_ratio_analysis.py:252-253,278,291-292` (and the report's boundary selection at line 543).

Reproducer: three reference dates, 2024-06-03 / 04 / 05, carry metadata `(A,t1)`, `(B,t2)`, `(A,t1)`. The middle reference close is null. All three vendor dates are present. The consecutive usable pair correctly spans June 3 to June 5 and lists June 4 as skipped, but `metadata_boundary` is false because only endpoint values are compared. The same output independently lists June 4 and June 5 as known metadata boundaries. Consequently the pair is omitted from boundary-pair counts/report tables despite crossing two recorded boundaries.

Endpoint `source_changed` and `updated_at_changed` may truthfully remain false. What is missing is a distinct, interval-aware indication that known boundaries were crossed. Inspect the complete reference sequence between the endpoints, including unusable and reference-only rows. Preserve or explicitly rename endpoint flags; add crossed source/fetch boundary dates and a combined interval flag, and use the latter for boundary-pair summaries and report selection. Do not invent metadata for vendor-only dates or missing rows. Cover A→B→A and t1→t2→t1 with an invalid middle price and with the middle vendor date absent, ordinary single-boundary cases, and no-boundary gaps. Retained numeric values must remain unchanged.

## Next-stage instruction for Claude

Fix only G3-R2b. The review hold on the five files in `g3_ratio_analysis_20260909_r2/` is released for this correction; write only those five files, then stop again at `ready_for_review`. Codex has preserved the exact reviewed version in its own snapshot directory above; do not edit that snapshot or any reviewer artifact. Preserve the original G3 directory and every earlier producer/evidence/basis/receipt/frozen/document artifact. Implement interval-aware metadata boundary reporting as specified, with focused offline synthetic and retained-artifact checks. Report hashes, commands, counts and preservation evidence. No acknowledgment-only documents, policy/basis/eligibility changes, thresholds, corporate-action attribution, adapter replay, network, SQLite, capture, services, production or dataset/strategy/knowledge mutation, training/pilot/source expansion, staging, commit, push or live trading.
