"""One canonical decision snapshot per (scope, bar vintage).

Why this exists
---------------
Before the one-snapshot-per-vintage guard, a 15-minute control loop re-recorded
the same daily candidates every cycle. The ledger holds 20,082 decision rows
across only 155 decision ids, and single days carry 10-24x the same decisions.
Pooling those rows weights every statistic - win rate, Rank IC, the scoreboard -
by how long the loop happened to be up rather than by distinct decisions, and it
inflates the FOLD count, which is what makes a Rank IC look stable.

Why a whole snapshot, never rows
--------------------------------
A snapshot is a ranked list decided at one instant. Selecting survivors per
subject would assemble a list out of rows from several snapshots: a ranking that
was never decided, whose ranks disagree with each other. This module selects one
complete ``decision_id`` and callers consume that entire snapshot.

Eligibility, in order
---------------------
The guard record decides, and it decides exclusively:

1. **A claim exists and is finalized** (``recorded_count > 0``).
   Only that ``decision_id`` may be canonical, and only if it also matches the
   claim: ``subject_count == candidate_count``, ``row_count == recorded_count``,
   the full required horizon set, and a rectangular shape. Selection kind is
   ``confirmed``.

2. **A claim exists but is not finalized** (``recorded_count = 0``).
   The vintage has NO canonical snapshot. This is the case that motivated the
   rule: a writer can lose its lease, resume, and finish a *complete* snapshot
   whose finalize then fails. Those rows are orphans. Falling back to "earliest
   complete" would let that orphan win whenever the successor had not finished,
   so there is no fallback while a claim is open.

3. **No claim at all** (legacy rows written before the guard existed).
   Only then is shape used to infer a snapshot: rectangular, and covering as
   many subjects and horizons as the best snapshot of that vintage. The required
   horizon COUNT is deliberately not hardcoded here - a legacy vintage may have
   been written with a different grid, and there is no claim to say otherwise.
   Selection kind is ``inferred`` - weaker evidence, and labelled as such,
   because if every snapshot of a vintage was truncated by one upstream failure
   the largest is still incomplete while looking complete beside its siblings.
   Only the guarded path can rule that out, because only it has an independent
   statement of the intended size.

Only scheduled runs ever create a claim - manual, replay and challenger runs are
previews that never write - so in practice the run_kind filter below guards
against exactly two things: a legacy_unknown row migrated from before the column
existed, and any future writer that gains claim access without also earning
official status.

Nothing here deletes or rewrites rows. Duplicates and orphans stay on disk as
the audit trail of what the system actually did, and are excluded on read.
"""

from __future__ import annotations

CANONICAL_POLICY_VERSION = "canonical_snapshot.v3"

# The stock decision pipeline writes every horizon in FORECAST_HORIZONS for every
# candidate, so a guard-confirmed stock snapshot missing any of them is
# incomplete no matter how self-consistent its claim looks.
#
# Sourced from FORECAST_HORIZONS rather than restated, so a grid change cannot
# leave this selection behind. CANONICAL_POLICY_VERSION must be bumped in the
# same commit as any grid change, so stored evaluations stay attributable to the
# grid that produced them; a silent change would silently redefine "complete".
#
# Resolved lazily: ledger imports this module, so importing it back at module
# scope would be circular.


def required_stock_horizons() -> tuple[int, ...]:
    from app.forecasting.ledger import FORECAST_HORIZONS

    return tuple(sorted(FORECAST_HORIZONS))

SELECTION_CONFIRMED = "confirmed"
SELECTION_INFERRED = "inferred"

_CANONICAL_CTE_TEMPLATE = """
canonical_snapshot_shape AS (
    SELECT
        scope,
        data_version,
        decision_id,
        MIN(decision_cutoff) AS snapshot_cutoff,
        COUNT(DISTINCT subject) AS subject_count,
        COUNT(DISTINCT horizon_days) AS horizon_count,
        COUNT(DISTINCT CASE WHEN horizon_days IN ({required_horizon_list})
                            THEN horizon_days END) AS required_horizon_count,
        COUNT(*) AS row_count
    FROM forecast_decisions
    GROUP BY scope, data_version, decision_id
),
canonical_vintage_shape AS (
    SELECT
        scope,
        data_version,
        MAX(subject_count) AS max_subject_count,
        MAX(horizon_count) AS max_horizon_count
    FROM canonical_snapshot_shape
    GROUP BY scope, data_version
),
-- Which vintages are governed by a guard record at all. A vintage that has one
-- is decided solely by it; shape may not override or rescue it.
canonical_guarded_vintage AS (
    SELECT scope, data_version FROM forecast_decision_days
),
canonical_confirmed AS (
    SELECT
        s.scope,
        s.data_version,
        s.decision_id,
        s.snapshot_cutoff,
        '{confirmed}' AS selection_kind
    FROM canonical_snapshot_shape s
    JOIN forecast_decision_days c
      ON c.scope = s.scope
     AND c.data_version = s.data_version
     AND c.decision_id = s.decision_id
    WHERE c.recorded_count > 0
      AND c.run_kind = 'scheduled'
      AND s.subject_count = c.candidate_count
      AND s.row_count = c.recorded_count
      AND s.row_count = s.subject_count * s.horizon_count
      -- Fail closed on the stock grid. recorded_count only says how many rows a
      -- run wrote, so a run truncated to horizons (1, 3) records recorded_count=2
      -- and agrees with itself perfectly. Only the grid itself can catch that.
      AND (
            s.scope <> 'stock'
         OR s.required_horizon_count = {required_horizon_count}
      )
),
canonical_inferred AS (
    SELECT
        s.scope,
        s.data_version,
        s.decision_id,
        s.snapshot_cutoff,
        '{inferred}' AS selection_kind
    FROM canonical_snapshot_shape s
    JOIN canonical_vintage_shape v
      ON v.scope = s.scope AND v.data_version = s.data_version
    LEFT JOIN canonical_guarded_vintage g
      ON g.scope = s.scope AND g.data_version = s.data_version
    WHERE g.scope IS NULL
      AND s.subject_count = v.max_subject_count
      AND s.horizon_count = v.max_horizon_count
      AND s.row_count = s.subject_count * s.horizon_count
),
canonical_eligible AS (
    SELECT * FROM canonical_confirmed
    UNION ALL
    SELECT * FROM canonical_inferred
),
canonical_ranked AS (
    SELECT
        scope,
        data_version,
        decision_id,
        selection_kind,
        ROW_NUMBER() OVER (
            PARTITION BY scope, data_version
            ORDER BY snapshot_cutoff ASC, decision_id ASC
        ) AS canonical_rank
    FROM canonical_eligible
),
canonical AS (
    SELECT scope, data_version, decision_id, selection_kind
    FROM canonical_ranked
    WHERE canonical_rank = 1
)
"""


def canonical_snapshot_cte() -> str:
    """The CTE body defining `canonical`, without the leading WITH keyword.

    Compose it as ``f"WITH {canonical_snapshot_cte()} SELECT ..."``. Every read
    path that reports statistics must use this rather than its own partitioning,
    so the ledger, feedback, calibration and the scoreboard cannot drift apart on
    what "one decision" means.
    """

    horizons = required_stock_horizons()
    return _CANONICAL_CTE_TEMPLATE.format(
        required_horizon_list=", ".join(str(value) for value in horizons),
        required_horizon_count=len(horizons),
        confirmed=SELECTION_CONFIRMED,
        inferred=SELECTION_INFERRED,
    ).strip()


def canonical_join(alias: str = "d") -> str:
    """The join that restricts `alias` to canonical snapshot rows."""

    return (
        f"JOIN canonical cs\n"
        f"  ON cs.decision_id = {alias}.decision_id\n"
        f" AND cs.scope = {alias}.scope\n"
        f" AND cs.data_version = {alias}.data_version"
    )


def canonical_snapshots(store) -> list[dict]:
    """Resolve the canonical snapshot per (scope, data_version).

    Exposed for diagnostics, for the future scoreboard, and for tests that need
    to assert which snapshot the policy chose and on what evidence.
    """

    rows = store.fetch_all(
        f"WITH {canonical_snapshot_cte()} "
        "SELECT scope, data_version, decision_id, selection_kind FROM canonical "
        "ORDER BY scope, data_version"
    )
    return [
        {
            "scope": row["scope"],
            "data_version": row["data_version"],
            "decision_id": row["decision_id"],
            "selection_kind": row["selection_kind"],
            "policy_version": CANONICAL_POLICY_VERSION,
        }
        for row in rows
    ]
