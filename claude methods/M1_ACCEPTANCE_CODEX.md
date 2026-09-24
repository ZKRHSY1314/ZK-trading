# M1 technical acceptance — 2026-09-06

Reviewer: Codex

Verdict: **VALIDATED for the M1 data-contract and staging-acceptance scope.** The bounded K1/K2 closure is complete. No blocking defect remains among the finite closure criteria reviewed in this round. This does not certify the current market dataset, strict point-in-time research, training readiness, strategy performance, or every possible future input/configuration.

User acceptance and M2 execution authorization remain separate. No downloads are authorized by this document.

## Independently verified results

| Check | Actual result |
|---|---|
| Supplied staging end-to-end suite | 67 checks, 0 unexpected; exit 0 |
| Primitive quality checks | 46 cases, 0 unexpected; exit 0 |
| Temporal proofs, called directly | 13/13 true; exit 0 |
| Prior independent subprocess probes | 11/11 expected outcomes |
| Actual unchanged 50 stocks + 2 benchmarks, independently constructed expected keys | 36,193 records/view; clean control exits 0 |
| Original BJ920002/2024-05-29 pre-listing addition in both views | Exit 1; both membership gates identify the ineligible key |
| Known-empty research eligibility, correctly empty data | Exit 1 on the explicit manifest policy; absent_symbols=0 and correctly_empty=1 |
| Known-empty research eligibility, one injected record in both views | Exit 1; ineligible security/session identified; insertion cannot turn failure into success |
| IPO with legitimate zero eligible warm-up observations | Research and warm-up coverage gates PASS; only required observation-depth gate V3b fails |
| Ineligible IPO warm-up observation added to both views | W1_pricing and W1_history both FAIL |
| Required history warm-up missing or divergent | Overall validation FAILS |
| History explicitly not consumed for warm-up | Pricing-only result is scoped and history is explicitly NOT CONSUMED |

Both fully-outside research cases were independently reproduced using disposable listing metadata: listing after the research window and delisting before it. These synthetic contracts make no assertion about a real security's actual listing history and do not modify the approved manifest.

## Accepted design

`expected_key_map()` retains known-empty sets. Observed keys are compared against those sets instead of bypassing validation. Missing-series reporting applies only to securities that owe eligible records.

Research uses an explicit `empty_domain=reject` batch policy, while warm-up uses `empty_domain=allow`. Under either policy, an observed ineligible key fails. Genuinely unknown eligibility remains UNKNOWN, not known-empty or PASS.

Feature observation depth is distinct from eligible coverage. V3b is not a standalone readiness verdict: all required membership, representation, reconciliation and depth gates must pass together. This limitation is now documented by Claude.

The reviewed G1/G2 fixes, G3 protections, M0 baseline, accepted census, and selected pilot population stand. Do not restart those audits merely to increase a test count.

## Reproduction

From `D:\codex-A股交易`:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_closure\test_staging_gate_e2e.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_closure\test_acceptance_gates.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_codex_review\empty_domain_acceptance.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 -c "import sys; sys.path.insert(0, r'claude methods/_m1_closure'); import temporal_contract as t; rows=t.proofs(); print(rows); assert len(rows)==13 and all(r[1] for r in rows)"
```

The final independent harness asserts all 11 prior probe outcomes and adds separate assertions on the actual IPO warm-up gate statuses. Its final output is `bounded_acceptance: PASS`. The companion notebook is `_m1_codex_review/M1_empty_domain_acceptance.ipynb`; inspect the referenced Python scripts for fixture construction and exact assertions. No backend-wide suite was rerun in this bounded artifact-only acceptance.

## Data and safety

Production main/WAL sizes and nanosecond modification times matched the prior baseline and stayed unchanged during the probes:

- trading_local.sqlite3: 1,346,048,000 bytes; mtime_ns 1788517646307317700.
- market_history.sqlite3: 1,234,956,288 bytes; mtime_ns 1788493486739967200.
- market_history.sqlite3-wal: 0 bytes; mtime_ns 1788493486748601200.

These are metadata checks, not fresh full production-content hashes. Protected fixture archives/baselines, the calendar, approved manifest and reviewed code retained their checked hashes. All fault writes were confined to disposable synthetic fixtures and cleaned up. No production migration, runtime implementation, network/plugin call, download, service start, staging, commit or push was performed by this review. Live trading remains outside the authorized scope.

## What remains before the three-year research goal

M1 proves the contract and tested rejection behavior, not that the existing corpus passes those gates. M2 pilot downloads have not started. Approximately three years of validated data, reviewed labels/cases, execution-model validation and chronological out-of-sample research are still ahead.

Known limitations remain explicit: incomplete local history and warm-up, unresolved unit evidence and historical universe/ST/suspension/delisting/BJ mapping, no locally established strict-PIT evidence, and identity-only cross-view reconciliation. Identical fixture values are not independent real-source corroboration. The 746 legacy evaluations and A2 remain a separate prerequisite before official evaluation consumption.

## Next handoff

Record M1 as technically `validated`, not user-accepted and not training-ready. The next decision is user authorization for the existing bounded 50-stock/two-benchmark staging pilot. Preserve the research interval 2023-09-04 through 2026-09-04 and do not change the selected population to hide failures.

The pilot authorization must explicitly pin the optional pre-window warm-up collection interval/depth, consumed views, declared price representation/transformation, source/request limits and staging destination. Advisory data-collection acceptance must never be presented as feature readiness, particularly for new listings. Unknown evidence remains unresolved and is not waived to make the pilot pass.

Until explicit authorization, make no network/plugin calls or dataset writes. Full-market rebuilding, production promotion, training, services, Git operations and changes to strategy/knowledge materials are not implied. Keep all local reviewer/Claude artifacts and datasets out of Git.
