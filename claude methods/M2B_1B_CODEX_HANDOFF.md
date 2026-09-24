# M2b-1b: offline correction handoff

Date: 2026-09-08. Codex reviewed run `20260908T021722Z` without additional HTTP
requests or production database opens. The retained FAIL reproduces exactly.
**Diagnostic evidence is verified with caveats; source-capability acceptance is NOT passed.**

Review report: `claude methods/_m2_codex_review/m2b_1b_report/report.html`.
Machine-readable report: the adjacent `artifact.json`.
Independent driver: `claude methods/_m2_codex_review/review_m2b_1b.py`.
Companion notebook: `claude methods/_m2_codex_review/m2b_1b_review.ipynb`.

The notebook code cells executed sequentially with the project Python interpreter;
its lightweight JSON structure was checked. No Jupyter dependencies were installed.
The portable HTML passed canonical and structural verification. The packaged renderer
could not locate a compatible Chromium headless-shell, so browser/source-dialog visual
QA was not performed. This presentation limitation does not change the code findings.

## Next proposed work: bounded offline fixes only

Read this handoff and the report before editing. Use the existing local real bodies as
hash-pinned regression inputs; do not fetch replacements or stage them in Git.

### D1 - bounded trailer support

Location: `claude methods/_m2_smoke/sina_klc_decoder.py:72`, `:113`.

The original strict extractor rejects both retained bodies because their assignments
are followed by non-executable block comments. The pinned routine diagnostically
decodes the assignment-only text into 5,935 and 5,987 ordered, unique-date rows.

Permit the observed comment grammar without allowing arbitrary trailing executable
JavaScript. Preserve strict bytes-to-text, dual-extraction equality, pinned decoder
hashes, limits and malformed-input refusals. Test original bodies, whitespace/comments,
unclosed comments, extra statements/assignments, markup and extraction disagreement.
Do not evaluate raw downloaded JavaScript. Do not infer complete coverage from the
first/last dates or promote the diagnostic decode into a successful original run.

### D2 - fail-closed inventory AND accurate stack recognition

Locations: `smoke_capture.py:950-970`, `:973-978`, `:1177-1202`.

Three independently confirmed counterexamples:

- `process_lister=[]` -> F8 PASS.
- A nonzero inventory subprocess exit with blank stdout -> `default_process_lister=[]`.
- `python.exe -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
  in a nonempty inventory -> F8 PASS. This is the launch form in
  `scripts/run_stack.ps1:338`; the current regex incorrectly requires `backend` after
  `uvicorn`. Fixing decoding alone will not close this hole.

Define explicit producer encoding and validate process-command completion, JSON shape,
nonempty inventory and relevant record completeness. Missing or ambiguous safety
evidence must not mean stopped. Do not use lossy replacement simply to make JSON parse.
Recognize the actual supported API and worker launch forms, while avoiding false
matches on a shell merely quoting their names. Include realistic positive/negative
fixtures, inaccessible relevant command-line cases, malformed/empty output, nonzero
exit, encoding errors and timeouts. Prove failed F8 refuses before HTTP or run-tree
creation. Never stop services to make a preflight pass.

## Correct the evidence wording and preserve provenance

- This capture's inventory size is zero. However, the present-time unmodified lister
  returned 293 processes without Unicode errors during Codex's first probe. The
  explicit-UTF-8 producer returned the same count. The earlier encoding error is
  plausible and reported, but not reproduced now; do not claim every historical F8
  PASS was vacuous without those historical outputs. Codex withdraws reliance on the
  affected F8 evidence, not the unrelated offline test results.
- No current process list proves historical absence of a writer. `run_valid=true`
  and unchanged protected-file metadata do not certify every safety prerequisite.
- The manifest establishes execution around 10:17 Asia/Shanghai, outside the original
  window. The separate user waiver is reported by Claude; its original user message
  was not available to this review. Preserve that authorization reference if available.
  It is not standing permission for another out-of-window run.
- The retained directory lacks the original pipeline summary / process receipt for
  exit code 1 and finalization duration 0.109 seconds. These exact figures are reported,
  not independently replayed. Preserve the original console receipt separately if it
  exists; otherwise label it unavailable. Do not fabricate or backdate one.
- Original evidence, manifest, checks and FAIL remain immutable. Any results from a
  revised decoder belong to a separately named offline revision. The original
  deterministic SHA-256 is
  `02e1b76483cd659b5a16f1df78304392e37effcc706a5c325317eefd42448703`.

## Closure and stop condition

Restrict proposed edits to the smoke implementation, its regression tests and the
English handoff documents. Preserve accepted M1/M2a and historical reviewer scripts.
Run focused regressions and the full affected offline suite with genuine HTTP blocked;
report exact commands, actual results, changed hashes and remaining unknowns. Do not
change thresholds to force semantic checks green. Stop at `ready_for_review` for Codex.

No additional live run is authorized by this handoff. A new one-run authorization is
required after offline review, normally inside the original timing window. The
52-symbol pilot, production writes/promotion, service operations, commits, pushes and
training remain out of scope. Live trading stays disabled.
