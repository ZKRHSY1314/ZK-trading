# M2b D1/D2 offline technical acceptance

Date: 2026-09-08. Reviewer: Codex. Branch: `codex/control-plane-refactor`.
HEAD: `73f266d`; index empty; pre-existing dirty work preserved.

## Decision

**Status: validated, within the bounded offline D1/D2 correction scope.**
The seven earlier F8 counterexamples and the subsequent four literal-boundary
counterexamples are closed. No blocking defect was found in the reviewed closure.
User acceptance is separate from this technical verdict.

This closes the current offline correction loop; no further classifier redesign is
requested. The next stage is preparation for one newly authorized boundary-1b smoke
capture, not the 52-symbol pilot or training. **M2b source capability remains FAIL**
because the only real capture aborted and its missing requests were never issued.
This document does not authorize another live run or production database operation.

## Independent verification executed

The validate-data workflow was used to separate source/code evidence, author test
claims, version-specific provenance, and the distinct live-source acceptance decision.

Run from `D:\codex-A股交易` with the existing project interpreter:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_smoke/test_m2_smoke.py'
# exit 0: 165 cases, 0 unexpected

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_d2_literal_boundary.py'
# exit 0: 8 checks, 8 passed (including all four previous failures)

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_d2_final.py'
# exit 0: 32 checks, 32 passed

& '.\backend\.venv\Scripts\python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_d1d2.py'
# exit 1: 54/55; exactly one EXPECTED cross-version producer-pin mismatch

git diff --check
# exit 0, existing CRLF notices only
```

The old driver's remaining mismatch compares current source with the producer of
the earlier `..._d1d2` revision. The exact expected difference is confined to
smoke_capture.py and test_m2_smoke.py. It is not a functional failure, and was not
made green by editing old evidence or the driver. Do not sum these suites into a
count of unique independent scenarios; they intentionally overlap.

The new 32-check driver verifies the new revision's actual producer pins, retained
inputs, exact offline replay, prior revision anchors, additional AST/literal/bounds
cases, and the real capture-entry refusal for all three executable counterexamples.
Those entries receive synthetic process records and an already frozen reference;
they refuse with F8 before HTTP or capture output directories are created. None of
the command-line examples is executed. Remote HTTP and SQLite opens are guarded.

## Why the code now satisfies this closure

- `smoke_capture.py:1131`: Python inertness is checked over the entire AST, not a
  print-like prefix. Imports, assignments, nested executable arguments, interpolation,
  comprehensions and unresolved expressions are not accepted as literal printing.
  The 4,096-character and 400-node limits are retained; parsing does not run the code.
- `smoke_capture.py:1204`: PowerShell's safe exception requires a complete simple
  read-only command and rejects sequencing, pipes, variables, substitutions,
  redirection and other compound syntax. This is deliberately conservative.
- `smoke_capture.py:1240`: the whole-program inertness check precedes invocation
  substring matching, so literal launch-looking text is not mistaken for execution.
  Relevant programs outside the proven simple forms are blocked as stack/ambiguous.
- The earlier blank/unidentifiable-record and absolute/relative known-worker fixes
  remain covered by the full suite and prior independent driver.
- D1 is unchanged. Both retained real bodies still decode through the pinned routine
  to 5,935 and 5,987 rows. This is bounded decoder evidence, not corpus readiness.

## Evidence preservation and replay

The new re-check is separately named:
`claude methods/_m2_smoke/revision_20260908T021722Z_d2_literal/`.
Its producer_implementation fields match the current five reviewed files. Raw bodies,
capture manifest and frozen reference are byte-identical to the sealed original.

The independently recomputed deterministic block matches its stored result:

```text
784ffa6621c3e708fa631deaf678b5bbd8dfafbd30c13347e032584b86d6a0af
capability: FAIL
```

The prior revision's two anchors still match the preceding review:

```text
..._d1d2/PROVENANCE.json 9270c1f545b8dd0c59f6586d3a29a8fa5b3060caebb85a07076d4a03018005fd
..._d1d2/checks.json 78819944b7c850ce181fbffd2e26ef86ba4aad4fda53c3fa775ab321a424d3a0
```

The earlier overwrite is now explicitly documented in the NEW provenance file,
including the unavailable pre-overwrite artifact. It has not been represented as
recovered or backdated. That historic loss is not undone by this acceptance. The
original raw responses/manifest/checks/reference and receipt copies still match their
earlier pins. All four retained directories were hash-inventoried before and after
the final driver and stayed unchanged.

## Frozen implementation pins

```text
smoke_capture.py 0ed93f05a8d8ab87da7dc57fa4c9c874806cc04d57b7ed93e53617cedc27daa2
test_m2_smoke.py d14a4f9822b8b249afe2366fc82eea80f1e9ed78de6e208c4b13c569e669df37
sina_klc_decoder.py d39e02c8cd736e10c29ae6efc12ce540eeadf790552dcdc14debcf5f18461fee
smoke_checks.py b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c
smoke_outcomes.py 53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e
```

New revision anchors:

```text
PROVENANCE.json 6d1cdc3e134a123f7ef2ca63447b00e4bc590aaa8497d83ada1cf0a88c940500
checks.json 2ef03476dabe6a4876e4104b2fabfc71dbcd553017a3dffc5c95435ebad8880a
```

A hash identifies content; it is not a retrievable source archive. If preparing the
next run, preserve a local non-Git copy of these reviewed source files with matching
hashes before any subsequent edits. Do not bundle credentials, unrelated private
files, datasets or production databases.

## Required caveats and scope boundaries

1. F8 is a point-in-time check of known visible launch forms, not a sandbox, global
   writer lock, or universal proof that the host is idle. The reviewed shapes include
   the project's normal API/worker/frontend/launcher forms. Bash, encoded/obfuscated
   or unrecognized launch forms and code without recognizable target markers are not
   certified by this review. In particular, code with no target marker can return
   other without an inertness proof; Section 19's wording about all unproven programs
   must be read narrowly as **unproven relevant programs**.
2. A fresh inventory and operator assurance that project writers remain stopped are
   necessary for a future smoke. Never stop services automatically to make F8 pass.
3. The next run still needs fresh, one-run user authorization. The earlier consumed
   authorization and reported timing waiver are not standing permission. Respect the
   original before-09:15/after-15:30 Asia/Shanghai operator window and record the clock
   immediately before arming; a green F8 does not verify that window.
4. Current source-capability evidence remains FAIL. BJ920000 was never contacted;
   the stock's auxiliary request and associated semantic checks remain missing.
   Do not infer full coverage, usable strategy evidence, or completed training.
5. The four accepted M2a code pins were rechecked and match. M1/M2a suites were not
   rerun this turn; their quoted runs belong to Claude, not this review.
6. This reviewer performed no live HTTP capture, production DB open, service action,
   Git staging/commit/push, or training. The independent drivers used a no-SQLite guard;
   production file sizes/mtimes remain at the established baseline below. Metadata
   equality is not a historical no-writer or full-content proof.

| File | Bytes | mtime_ns |
|---|---:|---:|
| trading_local.sqlite3 | 1346048000 | 1788517646307317700 |
| market_history.sqlite3 | 1234956288 | 1788493486739967200 |
| market_history.sqlite3-wal | 0 | 1788493486748601200 |

Only this English acceptance report and the new version-aware reviewer driver were
added by this turn. Earlier reviewer scripts, implementation and evidence were not
edited. The reviewer artifacts remain outside Git under the user's exclusions.

## Next instruction for Claude — preparation only

Read this acceptance. Record D1/D2 as technically validated, not M2b source capability
as passed. Freeze the reviewed implementation locally and prepare a concise new
boundary-1b one-run authorization request using the existing five-request plan,
15-attempt ceiling, pacing, TLS, timeout and abort rules unchanged. State exact
symbols/endpoints, output paths, timing condition, fresh preflight requirements,
read-only reference scope and missing questions the run should answer.

Preserve every prior evidence/revision directory and the original FAIL. New run
artifacts must use a fresh run_id and directory. Do not request another broad design
cycle or expand collection. Stop for fresh user authorization before arming. No live
HTTP, production database operation, service action, 52-symbol pilot, Git staging,
commit/push, or training is authorized by this preparation handoff.
