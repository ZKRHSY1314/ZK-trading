# Canonical forecast evidence

Status: `validated` in the cloud against synthetic fixtures only. It has not been run against the production ledger. Counts and IC values reported earlier were dated local observations; nothing in the code, the UI or the tests reproduces them.

## One selector, one read model

Everything that reports forecast statistics joins `forecast_decisions` through the same two pieces in `app/forecasting/canonical.py`:

- `canonical_join()` plus `CANONICAL_SELECTION_PREDICATE`, which admit only confirmed snapshots by default;
- `canonical_snapshot.v3`, which is unchanged. It selects one complete snapshot per (scope, bar vintage). A guard claim decides the snapshot when one exists; shape inference is used only when the vintage has no claim.

Four readers use this:

- labelling (`ForecastFeedback.label_due`);
- evaluation (`ForecastFeedback.evaluate`);
- the ledger's matured read;
- the scoreboard read model (`app/forecasting/evidence.py`).

Calibration consumes the evaluation output and applies the same eligibility function that the scoreboard uses.

## What an evaluation now reports

These fields are per scope and per horizon. The existing fields are kept.

| Field | Meaning |
| --- | --- |
| `fold_unit: decision_date`, `fold_count` | Independent folds are Shanghai **decision dates** with at least one matured sample. Two canonical snapshots decided on the same day (two vintages) count once. Their metrics are averaged within the date first, so each date weighs once. |
| `canonical_snapshot_count`, `repeated_snapshot_date_count` | How many snapshots were read, and how many dates carried more than one. |
| `aggregation: unweighted_mean_across_decision_dates` | Rank IC and precision@k are unweighted means over dates. A date whose IC is undefined (fewer than 2 pairs, or zero variance) is left out, not counted as 0. |
| `confirmed_fold_count`, `inferred_fold_count`, `excluded_inferred_snapshot_count` | Provenance. By default the evaluation uses only confirmed snapshots and states how many inferred snapshots it left out. |
| `due_count`, `matured_due_count`, `pending_count`, `coverage_of_due` | Maturity. A forecast is *due* once its exit session should have closed: next-session entry, h sessions, bar final at 15:15 Shanghai. `coverage_of_due` is `None` when nothing is due yet. An immature horizon is pending, not a data gap. |
| `maturity_basis: weekday_proxy_not_exchange_calendar` | The due test uses weekdays, not an authenticated exchange calendar. Holidays can make it call a forecast due early; it never calls a due forecast pending. |
| `coverage`, `coverage_denominator` | The legacy ratio, matured over all canonical forecasts including immature ones. It is kept for continuity and labelled as such. |
| `insufficient_reasons` | These new reasons are added: `horizon_not_yet_mature`, and `no_confirmed_snapshots` (official mode only). |

The canonical selection itself did not change, so `canonical_snapshot.v3` stays. The fold unit did change. Evaluations stored before this change have no `fold_unit`, and the eligibility check below treats them as "independent dates unknown".

## Runtime availability versus strategy eligibility

**Runtime.** The control plane's `forecast_feedback` step now reports whether labelling and evaluation *ran*. The evaluation result travels separately, as `evidence_status` and `evidence_quality`. An evidence shortfall therefore no longer turns the control-plane run `partial`. Before this change it also:

- marked the worker heartbeat `degraded`;
- shortened its retry interval;
- raised an attention flag on every cycle.

**Strategy evidence.** `strategy_evidence_eligibility()` is governed by `forecast_evidence_policy.v1`. The thresholds are predeclared evidence-sufficiency rules, not tuned trading parameters, and any change needs a new version. A horizon is eligible only if all of these hold:

- the canonical policy is the current one;
- the evidence is official, not exploratory;
- the status is `ready`;
- `fold_unit` is `decision_date` with at least 20 independent dates;
- `coverage_of_due` is at least 0.8;
- the Rank IC is known and positive.

Anything absent fails closed. An unknown IC is never read as "not adverse".

**Calibration.**

- Calibration still records every evaluation and may still recommend challengers on adverse evidence.
- A positive recommendation (`retain_champion_validate_challenger`) now requires eligible evidence. Favourable but thin evidence becomes `continue_monitoring`, with the reasons stated.
- The coverage branch uses `coverage_of_due`, so an immature horizon is no longer reported as a data-coverage problem.

**Stored evaluations.** The scoreboard groups `forecast_evaluations` by canonical policy. A "ready" row with no recorded policy (`legacy_unversioned`), or with another policy, is reported as history (`legacy_ready_count`). It is never treated as current evidence.

## Where to read it

- **API:** `GET /api/forecast/evidence?as_of=<tz-aware ISO>&include_inferred=false`. It is read-only; it never labels or persists anything. `include_inferred=true` produces exploratory evidence, which can never be eligible.
- **UI:** the cockpit's “预测评估证据” card. It shows the policy versions, confirmed, inferred and non-canonical snapshots, open claims, independent decision dates, due/matured/pending counts, due coverage, Rank IC and eligibility with its reasons. Unknown values are shown as unknown, never as 0.
- **Offline, read-only:**
  ```powershell
  backend\.venv\Scripts\python.exe backend\scripts\forecast_evidence_report.py --database trading_local.sqlite3 [--as-of <iso>] [--include-inferred]
  ```
  This opens the database with `mode=ro` and `query_only` and skips schema initialisation. It replaces the pooled `claude methods/verify/measure_*.py` scripts. Those scripts joined every repeated snapshot, ignored scope and the canonical policy, and ranked ties arbitrarily. They stay in the archive unchanged, as history.

## Fixture coverage

`backend/tests/test_forecast_evidence.py` covers:

- same-day snapshots counted as one fold, with per-date IC averaging;
- duplicate re-records, open claims and orphans excluded and counted;
- inferred-only data (official versus exploratory);
- tied predictors and returns under average ranks, and all-tied returns giving an unknown IC;
- partially matured horizons;
- eligibility fail-closed cases;
- stored legacy evaluations;
- calibration gating;
- runtime versus evidence separation in the control plane;
- that the API does not persist;
- the byte-identical database after the offline report.
