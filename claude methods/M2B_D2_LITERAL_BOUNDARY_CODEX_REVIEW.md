# D2 closure review — literal-program boundary

Date: 2026-09-08. Scope: offline acceptance of Section 18 in
`M2B_REAL_SOURCE_VERIFICATION_REQUEST.md`.

## Overall assessment: Needs revision

**The previous seven F8 counterexamples are closed.** D1 remains validated and
unchanged. However, the new inline-program classifier still has one blocking
correctness boundary: its supposed harmless-print/listing rule does not establish
that the WHOLE program is harmless. Three ordinary compound/expression examples
are incorrectly allowed. A fourth example demonstrates the opposite error: a pure
literal print is falsely classified as launching the API.

Do not reopen the already closed blank-record or relative-worker work. Fix the
bounded inline classification boundary only, then request review. No new live run
is authorized. Source-capability acceptance is still FAIL; this is not progress
into corpus collection or training.

## Commands and actual results

Run from `D:\codex-A股交易`:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/test_m2_smoke.py'
# exit 0: 158 cases, 0 unexpected

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_d1d2.py'
# exit 0: 55 checks, 55 passed, 0 failures

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_d2_literal_boundary.py'
# exit 1: 8 checks, 4 passed, 4 failed acceptance expectations

git diff --check
# exit 0, existing CRLF notices only
```

The new independent driver uses synthetic process records as DATA, never executes
their command text, and calls the real normalizer, classifier, and preflight F8.
Remote HTTP and SQLite opens are guarded. Its eight cases include the following
four failures and four passing controls (basic literal print, literal listing,
direct Python API call, direct PowerShell launcher).

## P1 — The harmless-program exception accepts executable programs

Source: `_m2_smoke/smoke_capture.py:1124`, `:1134-1136`, `:1167-1170`.

`_PY_LITERAL_ONLY` starts with print/repr/str but its greedy `.*` can span multiple
statements. It does not prove literal arguments or a single expression.
`_PS_LISTING_ONLY` only checks the first verb; it does not inspect the complete
program or exclude executable arguments. These examples all currently produce
`F8 PASS`, but must produce FAIL (stack or ambiguous):

```text
python.exe -c "print('starting'); from uvicorn import run; run('app.main:app')"
powershell.exe -Command "Get-Item .; python.exe scripts/control_plane_loop.py"
powershell.exe -Command "Get-Item $(python.exe scripts/control_plane_loop.py)"
```

These are not obfuscated launches or a demand to detect arbitrary malicious code.
They visibly name known stack targets and use ordinary statement sequencing or
argument evaluation, within the contract claimed in Section 18. The first may run
the API inside the same Python process. The two PowerShell records are already
unresolved relevant execution even before a child process becomes visible; F8 must
not call them harmless listings.

Required correction: a harmless exception must cover the whole bounded program
and only demonstrably inert operations/arguments. A program starting with a harmless
operation is not necessarily harmless. If a relevant program cannot be proven a
simple literal print/listing, return ambiguous, not other.

## P2 — A literal string that looks like an invocation is misclassified

Source: `_m2_smoke/smoke_capture.py:1162-1169`.

```text
python.exe -c "print('uvicorn.run(app.main:app)')"
```

Expected F8 PASS; actual F8 FAIL, classification stack. The invocation regex searches
inside a quoted string before any reliable literal-program distinction is made.
The process only prints text. This is a usability/correctness regression, not the
reason live safety remains blocked, but it belongs in the same small fix.

Do not solve the two directions by simply swapping the current regex order: the
existing harmless regex itself is unsafe. A bounded Python AST shape check for a
single allowlisted print/representation call with inert literal arguments is one
option; do not evaluate the program. For PowerShell, conservatively recognize a
complete simple read-only command with literal arguments, refusing relevant compound
commands, substitutions, and unresolved expressions as ambiguous. No general shell
parser, dependency install, or actual process launch is needed.

## P2 — Historical revision was regenerated despite the preservation boundary

Section 18 at lines 1061-1064 explicitly records regeneration of
`_m2_smoke/revision_20260908T021722Z_d1d2/`. Its PROVENANCE now carries the new
capture/test hashes, and checks.json was rewritten. The previous instruction had
explicitly required this revised evidence, as well as the original, to stay unchanged.

This is not alteration of the original run's FAIL: the original raw responses,
manifest, checks, and reference still match the earlier review pins. The revised
deterministic result is also still
`784ffa6621c3e708fa631deaf678b5bbd8dfafbd30c13347e032584b86d6a0af`, capability FAIL.
Nevertheless, an unchanged deterministic result is not unchanged revision provenance.

**Reviewer clarification:** the old `review_m2b_d1d2.py` compares current source hashes
with the producer hashes declared by that historical revision. That assertion is
version-specific and can legitimately fail after new source changes. Running the
driver unchanged was not a requirement to force that historical pin check green.
It must not be satisfied by rewriting the evidence input. The 55/55 result verifies
the currently regenerated input, not preservation of the preceding revision.

For the next handoff:

- Leave all currently retained directories and historical reviewer scripts untouched.
- Put any subsequent re-check in a newly named revision directory, identifying its
  actual producer hashes and parent evidence. No fresh vendor request or DB read is
  needed for an offline re-check.
- Add an honest new note recording which earlier revision fields/files were overwritten.
  Provide a pre-overwrite artifact locator only if it already exists. Otherwise state
  that the previous revision provenance file is not available byte-for-byte. Do not
  fabricate, backdate, or reconstruct it as an original artifact.
- Report expected cross-version hash mismatches separately from functional failures;
  do not edit old evidence or reviewer tests simply to obtain a green count.

## Verified scope and limitations

- D1, smoke_checks.py and smoke_outcomes.py hashes remain unchanged. Both real bodies
  still decode to 5,935 and 5,987 rows through the pinned routine. This proves neither
  full stock semantic acceptance nor three-year corpus readiness.
- The four accepted M2a Python file pins were independently rechecked and match.
  M1/M2a test suites were not rerun this turn; their reported runs belong to Claude.
- The original receipt copies still match their declared sources/hashes. The original
  timing waiver is still a reported conversation, not newly authorized permission.
- The old driver observed 277 processes, F8 PASS, no recognized or unreadable relevant
  matches. This is a present-time observation, not proof of historic or future absence.
- This reviewer made no live capture, production DB open, service operation, Git
  staging/commit/push, or training run. Production DB sizes/mtimes stayed at the previous
  baseline. Metadata checks do not certify historical inactivity or full content.
- Only this new report and its independent driver were added. Existing implementation,
  data, receipts, revisions and earlier reviewer scripts were not edited by this review.

Reviewed source pins:

```text
smoke_capture.py 37942c386bc5659d574db2354b657d9b8a6ea78dbd234323ea9a38ad7f8f6312
test_m2_smoke.py 4103f03b9c5c52192cceb217171a74a4be3614075a3621c4eca9b99aa975a4b3
sina_klc_decoder.py d39e02c8cd736e10c29ae6efc12ce540eeadf790552dcdc14debcf5f18461fee
smoke_checks.py b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c
smoke_outcomes.py 53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e
```

Current regenerated revision anchors (not the pre-overwrite versions):

```text
PROVENANCE.json 9270c1f545b8dd0c59f6586d3a29a8fa5b3060caebb85a07076d4a03018005fd
checks.json 78819944b7c850ce181fbffd2e26ef86ba4aad4fda53c3fa775ab321a424d3a0
```

## Next bounded task

Fix only the whole-program/literal distinction and add regressions for all four
counterexamples. Preserve the previously closed seven and the current capture-refusal
tests. Run the 158-case baseline plus new tests, and the unchanged new independent
driver, with remote HTTP blocked. Apply the provenance handling above without modifying
existing evidence directories. Report actual commands, outcomes, hashes and limitations.
Stop at `ready_for_review`; do not execute a new boundary-1b run or move to the pilot.
