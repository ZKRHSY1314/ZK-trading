# M2b D1/D2 independent review — 2026-09-08

## Verdict

**D1: validated for the bounded decoder correction. D2: changes requested.**
The revision is not ready for another boundary-1b live capture. M2b source-capability
acceptance remains FAIL. This review does not authorize a new capture, the 52-symbol
pilot, database changes, services, commits/pushes, or training. Live trading stays disabled.

This is a source-backed validation review using the validate-data workflow: observed
behaviour and independent counterexamples take precedence over a green author suite.
No Claude implementation file or historical evidence was edited by the reviewer.

## Executed verification

Run from `D:\codex-A股交易` with the existing project interpreter:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/test_m2_smoke.py'
# exit 0: 146 cases, 0 unexpected

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_d1d2.py'
# exit 1: 55 checks, 48 passed, 7 failed acceptance expectations

git diff --check
# exit 0; existing CRLF-to-LF notices, no whitespace errors
```

The independent driver uses synthetic process records only. None of its example
launch commands is executed. Remote connections and all SQLite opens are guarded.
It reads retained evidence and the five explicitly identified original console files.
Its real process query is read-only and reports counts, not unrelated command lines.

M1/M2a test results quoted by Claude were not rerun in this review; do not attribute
those test runs to Codex. The focused changed M2b suite was rerun.

## Verified improvements

- D1 decodes the two hash-pinned original bodies with the pinned installed routine:
  sh600011 produces 5,935 ordered unique-date rows (branch O), and sh000300 produces
  5,987 (branch D). Both end on 2026-09-07. This is decode evidence, not complete
  three-year corpus or stock semantic acceptance.
- Malformed/unclosed/oversized trailers, extra executable statements, and too many
  comments are rejected. Raw downloaded JavaScript is not evaluated.
- Empty inventories, nonzero inventory exits, blank stdout, strict UTF-8 failures,
  timeouts, and the actual `run_stack.ps1` API launch form now fail closed.
- The revised offline replay matches its stored deterministic hash exactly:
  `784ffa6621c3e708fa631deaf678b5bbd8dfafbd30c13347e032584b86d6a0af`.
  Its capability remains FAIL, correctly. Old capture classifications and skip
  decisions are not rewritten to fit the revised decoder.
- Both raw bodies, the original manifest, checks and frozen reference match the
  previous Codex review's pins. The separate revision copies the raw bodies,
  manifest and reference byte for byte. Both evidence trees stayed unchanged.
- All five receipt copies match their declared hashes AND their still-accessible
  original source files; copied mtimes also match the declared original mtimes.
  This now supports original exit code 1, finalization time 0.109 seconds, and the
  two inventory-reader UnicodeDecodeError tracebacks. The timing-waiver text is
  still Claude's account of a conversation, not the original user instruction.

## Blocking D2 findings

All seven counterexamples below go through the real `preflight()` F8 check. Each
should return FAIL (a recognized stack process or unresolved relevant process),
but returns PASS. Group them into the following three bounded corrections.

### P1 — Incomplete relevant records are still accepted

Locations: `_m2_smoke/smoke_capture.py:1022-1033`, `:1116-1126`.

`cmdline_available` is computed using `command is not None`. An empty string or
whitespace is therefore labelled available. A missing Name plus null CommandLine
is also accepted and classified as an unrelated image.

Reproduced normalized records, each combined with an unrelated System record:

```python
{'ProcessId': 999991, 'Name': 'python.exe', 'CommandLine': ''}
{'ProcessId': 999991, 'Name': 'python.exe', 'CommandLine': '  '}
{'ProcessId': 999991, 'CommandLine': None}
```

Normalize blank relevant command lines as unavailable, and validate the identity
and field types needed to rule out relevant processes. If identity is insufficient,
fail rather than infer unrelated. Preserve the legitimate System/null-command case.

### P1 — Relative worker paths are missed

Locations: `_m2_smoke/smoke_capture.py:1084`, `:1163-1167`.

The matcher demands `backend/scripts/` inside the command line. Starting the same
existing scripts from the backend working directory omits that prefix:

```text
python.exe -X utf8 scripts\control_plane_loop.py --profile full
python.exe -X utf8 scripts\market_history_refresh_loop.py
```

Neither is evidence that the machine is stopped. Recognize the project's known
worker entrypoints in supported relative as well as absolute forms, with interpreter
identity checks. This does not require a general command-line parser or new services.

### P1 — Inline execution is treated as mere discussion

Locations: `_m2_smoke/smoke_capture.py:1078-1096`, `:1126`.

Discarding everything after `-c` / `-Command` removes actual launches as well as
innocent quoted text. These two synthetic commands are incorrectly accepted:

```text
python.exe -c "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=8000)"
powershell.exe -NoProfile -Command "& 'D:\codex-A股交易\scripts\run_stack.ps1'"
```

The first can run the API inside that same Python process; a separate child need
not appear to rescue detection. Distinguish bounded recognizable invocation from
literal print/listing forms, or classify unresolved relevant launches as ambiguous.
Do not evaluate command text, add an expansive shell parser, or treat every inline
program as safely unrelated. Keep the passing `print(...)` and `Get-Item` negative
fixtures. Correct the comment claiming that inline code is necessarily only talking
about a launch.

## Non-blocking evidence/documentation notes

- Current inventory returned 283 processes, F8 PASS, no recognized or unreadable
  relevant matches. This is not certification of historical absence, and the
  counterexamples mean F8 is not yet a sufficient safety gate even now.
- `PROVENANCE.json` records old source hashes but names no retrievable frozen source
  artifact. A hash identifies content; it does not preserve or reconstruct it.
  In a new note, provide an existing artifact locator if available; otherwise label
  old-code replay currently unverified. Do not reconstruct/backdate an old source
  snapshot or alter sealed evidence. The original replay was verified by Codex in
  the earlier review; that historical observation remains valid.
- The test module's opening docstring still says there are no real samples, despite
  its new L-block using two. Correct this wording when updating the tests.

## Safety and review baseline

Branch `codex/control-plane-refactor`, HEAD `73f266d`, index empty. Existing dirty
changes remain untouched. This review adds only this English report and its separate
independent driver; neither is to be staged or committed under the user's exclusions.

Production file metadata remained unchanged; no production DB was opened by the
independent driver. Size/mtime checks are not a full-content proof of historical
inactivity:

| File | Bytes | mtime_ns |
|---|---:|---:|
| trading_local.sqlite3 | 1346048000 | 1788517646307317700 |
| market_history.sqlite3 | 1234956288 | 1788493486739967200 |
| market_history.sqlite3-wal | 0 | 1788493486748601200 |

Reviewed implementation hashes:

```text
sina_klc_decoder.py d39e02c8cd736e10c29ae6efc12ce540eeadf790552dcdc14debcf5f18461fee
smoke_capture.py fadcaf3cc4a3dcbe7e77afa8c6336d6a35aa5c57b2a5d036960d4e3009639b88
test_m2_smoke.py 748b5131882e54db5fb45ca2eb549e3a6c4156e51d52ced9fba70d4722517dd2
smoke_checks.py b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c
smoke_outcomes.py 53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e
```

## Next handoff to Claude

Fix only the three D2 gaps above in the smoke process gate and its regression tests.
Keep D1, accepted M1/M2a, original receipts/evidence, revised evidence and reviewer
scripts unchanged. Add normalized-record-to-F8 and capture-refusal regressions:
missing/ambiguous relevant process evidence must fail before any HTTP or run-tree
creation. Use synthetic process records and frozen reference fixtures; never launch
the example writers or stop services to make a test pass.

Run the affected offline suite with remote HTTP blocked and the independent driver
unchanged. Report exact results, changed hashes and remaining limitations. Address
the two small documentation notes without enlarging the implementation scope.
Stop at `ready_for_review`. Do not execute another boundary-1b run; a fresh one-run
user authorization is required after this safety review closes. No production writes,
52-symbol pilot, service operations, Git staging/commit/push, or training.
