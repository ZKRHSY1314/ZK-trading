# M3-02 working-version boundary feedback

This is feedback within the active M3-02 task, not a second dispatch or a final rejection. Preserve the accepted label policy/module, current write scope, earlier evidence and all unsuccessful attempts. Incorporate the corrections before the final bounded real run and stable manifest. Do not restart the task or edit Codex-owned files.

Codex preserved and tested reader SHA-256 `01e2f1ca93b96fa8f2871dffd74ecd11d03a500c99b3052ae9e6327977e13683` (61,621 bytes). The source and mocked test/harness are in `codex/reader_working_preview_input_01/`. Reproduction: `backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/codex/run_reader_boundary_review.py" "claude methods/_m3_20260910/codex/test_independent_reader_boundary.py" <new Codex output directory>` (Codex already ran it; do not write to Codex scope yourself).

Actual result: **4 methods, 1 pass / 3 failures**, no API errors. Receipts: `codex/reader_working_boundary_tests_01/execution.json` and `stderr.txt`. All database openers were mocked; the audit hook allowed zero real SQLite connections, network or subprocesses. No unauthorized file was created or read. Nested connection post-hash ownership now passes, so that earlier working concern is already resolved.

## Confirmed outstanding requirements

1. **Fixed real input/date boundary is not enforced at entry.** `dataclasses.replace(FROZEN_M2, price_max_date='2026-09-04')` reaches `ReadOnlyStore` in `reconcile`; replacing the trading SourceSpec with a caller-owned path/hash reaches `verify_source` in `run_development`. The current path comparison inside verify_source compares a resolved path with itself, not with the task's fixed source allowlist. Default values and caller-provided matching hashes do not enforce this task boundary. Validate the complete real configuration (including exact source paths/hashes/sizes, metadata/policy pins, development dates, maximum price date and benchmark role) before source I/O. The direct reconcile/store APIs must not provide a bypass. Keep synthetic fixtures explicitly confined to the authorized new scratch scope, reject real/production files in synthetic mode, and do not allow changing a synthetic boolean to relabel real data. Retain an admissible synthetic read-to-label path.

2. **Construction performs file I/O.** `ReadOnlyStore.__init__` immediately calls verify_source. The task and module contract require import and construction to have no I/O side effects. Store pure configuration in the constructor; perform verification only on the explicit read/enter path, immediately before connecting, then verify again on exit. Cover construction with an I/O-intercepting test as well as the positive explicit read.

## Related static checks to close in the same delivery

- `run_development` currently accepts an arbitrary output directory after only checking nonexistence. Enforce the permitted new output scope before reading inputs or writing anything; retain refusal to overwrite. Test rejected output paths without touching them.
- `ReadLog` currently retains SQL text without parameters. Preserve bound date/symbol parameters (and connection identity) in the audit receipt so the actual development-only queries are independently inspectable. Reading `PRAGMA query_only` back is stronger evidence than a hardcoded true field.

These checks implement the existing task's boundaries; they do not authorize extra files, captures, held-out analysis, production access, policy changes or a new stage. Pin this feedback and the referenced independent source/receipts in the final manifest. Include positive and negative tests and a real execution receipt that identifies every actual connection. Then complete the same M3-02 task, mark ready_for_review and stop.
