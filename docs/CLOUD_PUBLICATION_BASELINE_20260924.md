# Cloud publication baseline — 2026-09-24

This is a source handoff, not a claim that production, research qualification or CI is complete.

- Repository: `ZKRHSY1314/ZK-trading`.
- Publication branch: `codex/control-plane-refactor`; pre-publication HEAD: `73f266d4165df48bacc6112f037537aed5fb7a58`.
- Implementation assignment: [CLAUDE_CLOUD_HANDOFF_20260924.md](CLAUDE_CLOUD_HANDOFF_20260924.md).
- No changes are merged to `main` by this publication. Claude must start from the publication branch.

## Included and excluded

Included: all pending application source changes, tests, startup scripts, project instructions, formal review documents, and source/review files from the historical `claude methods` archive. The archive is provided for traceability, not as an instruction to execute every script or bulk-read every report.

Excluded: production/frozen SQLite databases, market captures and raw/generated datasets, JSON receipts and replay exports, CSV/JSONL files, binaries, downloaded PDFs, archives, logs, virtual environments, caches, credentials and Visual Studio state. Omitted files remain on the local computer; this publication does not delete them. Archived documents retain references to those local-only files. Missing evidence must remain missing in cloud acceptance.

`.gitignore` now shares source/review extensions under `claude methods` while excluding generated artifacts there. `.gitattributes` disables newline conversion for byte-pinned research modules/tests and archived source/reviews. This is necessary: the frozen SHA-256 values cover original CRLF bytes. Converting them to LF would create new bytes without a research change or a valid new freeze.

## Actual local checks before publication

The test process used a unique temporary SQLite path and `ENABLE_LIVE_TRADING=false`, not the production database.

| Check | Result |
| --- | --- |
| Full backend `python -B -m pytest -q` | **1,055 passed, 2 failed; 70 subtests passed**, 209.35 seconds. One existing Starlette TestClient deprecation warning |
| Ruff 0.16.6, application/tests plus new diagnostic/session scripts | **33 findings**: 19 E741, 12 E702, 1 E703, 1 F841 |
| Prior diagnostic increment | 70 focused tests passed on September 13; this is historical evidence, not another September 24 run |
| Credential-pattern inspection of publication candidates | One literal matched; verified as the existing `SYNTHETIC-SECRET` test fixture. No actual credential identified by these checks; pattern scanning is not an absolute guarantee |

The two pytest failures are:

1. `tests/test_m4_portfolio.py::TestPolicyAndIsolation::test_module_is_stdlib_only_without_side_effects`
2. `tests/test_m4_risk.py::TestImmutabilityAndDeterminism::test_module_is_stdlib_only_and_frozen_modules_are_the_pinned_bytes`

Both assert the absence of `app` in `sys.modules` while the ordinary pytest host imports `app` from `conftest.py`. Preserve the assertion in a genuinely isolated process instead of skipping it. Do not describe this full test run as passing.

Ruff findings are confined to the three `backend/app/research/m4_*.py` files and `test_m4_portfolio.py` / `test_m4_risk.py`. The publication does not silently rewrite frozen files or alter hashes to hide those findings. The next cloud increment must resolve the CI contract with explicit provenance preservation.

No frontend code changed in this publication; frontend tests/build were not rerun locally for this handoff. Claude should execute them in the cloud baseline and report actual results. Windows-only integration checks require Windows; Linux skips are not equivalent evidence.

The application/source whitespace check passes when the historical `claude methods` archive is excluded. The whole-archive check reports existing trailing whitespace, including Markdown hard line breaks and old helper-script formatting. Those archival bytes are preserved rather than silently edited during publication; this is separate from the Ruff and pytest failures above.

## Byte pins that must survive checkout

| File | SHA-256 of local frozen bytes |
| --- | --- |
| `backend/app/research/m3_labels.py` | `e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393` |
| `backend/app/research/m3_frozen_reader.py` | `288594cf0acf977c5ede3f5dec6584134a879889793c4c3542d01b1d7f7ae5af` |
| `backend/app/research/m4_execution.py` | `83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7` |
| `backend/app/research/m4_portfolio.py` | `2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360` |
| `backend/app/research/m4_risk.py` | `faec444ee98ed6ee8c20da217a6cb29ced53d7de2ceae1e2198b1cbc73b665f2` |

Do not equate these source pins with availability of the omitted data/manifests, independent reproduction of historical qualification, or training eligibility.
