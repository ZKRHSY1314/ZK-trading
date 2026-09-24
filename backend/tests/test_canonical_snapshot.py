from __future__ import annotations

import json

import pytest

from app.forecasting import ForecastDecision, ForecastLedger
from app.forecasting.canonical import (
    CANONICAL_POLICY_VERSION,
    SELECTION_CONFIRMED,
    SELECTION_INFERRED,
    canonical_snapshots,
)
from app.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "canonical.sqlite3")
    store.init()
    return store


def _record(store, decision_id, subjects, cutoff, *, horizons=(1, 3, 5, 10, 20),
            data_version="vintage-2026-07-10"):
    ledger = ForecastLedger(store)
    for rank, subject in enumerate(subjects, start=1):
        for horizon in horizons:
            ledger.record_forecast(
                ForecastDecision(
                    decision_id=decision_id,
                    scope="stock",
                    subject=subject,
                    decision_cutoff=cutoff,
                    available_at=cutoff,
                    horizon_days=horizon,
                    rank=rank,
                    score=100.0 - rank,
                    probability=None,
                    model_version="selection-v3",
                    prompt_version="event-thesis-v1",
                    data_version=data_version,
                    features={},
                    evidence=[],
                    reasons=["fixture"],
                    status="pending_outcome",
                )
            )


def _claim(store, decision_id, *, recorded_count, candidate_count=3,
           run_kind="scheduled", data_version="vintage-2026-07-10"):
    with store.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) "
            "VALUES ('stock', ?, ?, '2026-07-10T09:00:00+08:00', ?, ?, ?)",
            (data_version, decision_id, candidate_count, recorded_count, run_kind),
        )


def test_exactly_one_snapshot_is_canonical_per_scope_and_vintage(store):
    _record(store, "decision-0900", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00")
    _record(store, "decision-0915", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:15:00+08:00")

    picked = canonical_snapshots(store)

    assert len(picked) == 1
    assert picked[0]["decision_id"] == "decision-0900"
    assert picked[0]["policy_version"] == CANONICAL_POLICY_VERSION


def test_an_incomplete_early_snapshot_loses_to_a_complete_later_one(store):
    """Earliest alone is a heuristic; completeness has to be checked first.

    A run that died part way leaves a genuine, earliest-cutoff snapshot covering
    only some of the day's candidates. Taking it because it came first would
    silently shrink the day's decision to whatever the crash happened to write.
    """

    _record(store, "decision-0900-truncated", ["SH600000"], "2026-07-10T09:00:00+08:00")
    _record(store, "decision-0915-complete", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:15:00+08:00")

    picked = canonical_snapshots(store)

    assert [p["decision_id"] for p in picked] == ["decision-0915-complete"]


def test_a_snapshot_missing_a_horizon_is_not_complete(store):
    """Rectangularity matters: every subject needs the full horizon grid."""

    _record(store, "decision-0900-partial", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00", horizons=(1, 3))
    _record(store, "decision-0915-full", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:15:00+08:00")

    picked = canonical_snapshots(store)

    assert [p["decision_id"] for p in picked] == ["decision-0915-full"]


def test_a_guard_confirmed_snapshot_wins_over_an_earlier_unconfirmed_one(store):
    """A published claim is evidence of successful generation, not an inference.

    forecast_decision_days is only updated once a writer finished while still
    owning the vintage, so it outranks a bare timestamp.
    """

    _record(store, "decision-0900-manual", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00")
    _record(store, "decision-0915-guarded", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:15:00+08:00")
    _claim(store, "decision-0915-guarded", recorded_count=15, candidate_count=3)

    picked = canonical_snapshots(store)

    assert [p["decision_id"] for p in picked] == ["decision-0915-guarded"]


def test_snapshots_with_different_candidate_sets_are_never_merged(store):
    """The market moves between cycles, so candidate sets differ. Never blend them."""

    _record(store, "decision-0900", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00")
    _record(store, "decision-0915", ["SH600000", "SH600003", "SH600004"],
            "2026-07-10T09:15:00+08:00")

    picked = canonical_snapshots(store)
    assert [p["decision_id"] for p in picked] == ["decision-0900"]

    matured_subjects = {
        row["subject"]
        for row in ForecastLedger(store).store.fetch_all(
            "SELECT DISTINCT subject FROM forecast_decisions WHERE decision_id = ?",
            ("decision-0900",),
        )
    }
    # Subjects unique to the later snapshot must not appear alongside these.
    assert matured_subjects == {"SH600000", "SH600001", "SH600002"}


def test_each_vintage_gets_its_own_canonical_snapshot(store):
    _record(store, "decision-d1", ["SH600000", "SH600001"], "2026-07-10T09:00:00+08:00",
            data_version="vintage-2026-07-10")
    _record(store, "decision-d2", ["SH600000", "SH600001"], "2026-07-13T09:00:00+08:00",
            data_version="vintage-2026-07-13")

    picked = {p["data_version"]: p["decision_id"] for p in canonical_snapshots(store)}

    assert picked == {
        "vintage-2026-07-10": "decision-d1",
        "vintage-2026-07-13": "decision-d2",
    }


def test_selection_is_deterministic_across_repeated_reads(store):
    """Replay must be stable, including when cutoffs tie."""

    _record(store, "decision-bbb", ["SH600000", "SH600001"], "2026-07-10T09:00:00+08:00")
    _record(store, "decision-aaa", ["SH600000", "SH600001"], "2026-07-10T09:00:00+08:00")

    runs = [canonical_snapshots(store) for _ in range(5)]

    assert all(run == runs[0] for run in runs)
    # The tie breaks on decision_id ascending, not on insertion order.
    assert runs[0][0]["decision_id"] == "decision-aaa"


def test_matured_reads_consume_only_the_canonical_snapshot(store):
    """The ledger must honour the shared policy, not its own partitioning."""

    from app.forecasting import ForecastOutcome

    ledger = ForecastLedger(store)
    _record(store, "decision-0900-truncated", ["SH600000"], "2026-07-10T09:00:00+08:00")
    _record(store, "decision-0915-complete", ["SH600000", "SH600001"],
            "2026-07-10T09:15:00+08:00")
    for decision_id, subjects in (
        ("decision-0900-truncated", ["SH600000"]),
        ("decision-0915-complete", ["SH600000", "SH600001"]),
    ):
        for subject in subjects:
            ledger.record_outcome(
                ForecastOutcome(
                    decision_id=decision_id,
                    scope="stock",
                    subject=subject,
                    horizon_days=5,
                    observed_at="2026-08-10T15:00:00+08:00",
                    continuous_return=0.05,
                    benchmark_return=0.01,
                    sector_return=0.02,
                    data_version="outcome-eod-5",
                    evidence={"price_source": "fixture"},
                )
            )

    matured = ledger.matured("2026-08-11T00:00:00+08:00", scope="stock", include_inferred=True)

    # The truncated early snapshot is excluded even though it is earliest.
    assert {row.forecast.decision_id for row in matured} == {"decision-0915-complete"}
    assert len(matured) == 2
    # Raw reads still see everything: nothing was deleted.
    raw = ledger.matured("2026-08-11T00:00:00+08:00", scope="stock", deduplicate=False)
    assert len(raw) == 3


def test_an_orphaned_snapshot_never_becomes_canonical_even_when_the_successor_fails(store):
    """The scenario the guard alone does not cover.

    Writer A stalls past its lease. Writer B reclaims the vintage. A resumes and
    finishes a COMPLETE snapshot, but its finalize correctly fails because it no
    longer owns the claim. B then fails before finalizing anything.

    No guard-confirmed snapshot exists. An "earliest complete snapshot" fallback
    would hand the vintage to A's orphan - rows that the system itself refused to
    publish. While a claim is open there is no fallback at all.
    """

    # A's orphaned but structurally complete snapshot.
    _record(store, "decision-A-orphan", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00")
    # B holds the vintage and never finished.
    _claim(store, "decision-B", recorded_count=0)

    assert canonical_snapshots(store) == []


def test_a_vintage_with_an_unfinished_claim_has_no_canonical_snapshot(store):
    """recorded_count = 0 means "not published yet", not "fall back to shape"."""

    _record(store, "decision-inflight", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00")
    _claim(store, "decision-inflight", recorded_count=0)

    assert canonical_snapshots(store) == []

    # Once the writer publishes, the same rows become canonical.
    _claim(store, "decision-inflight", recorded_count=15)
    picked = canonical_snapshots(store)
    assert [p["decision_id"] for p in picked] == ["decision-inflight"]
    assert picked[0]["selection_kind"] == SELECTION_CONFIRMED


def test_a_guarded_snapshot_must_match_the_claim_not_merely_its_siblings(store):
    """Completeness is checked against the claim, not against the other snapshots.

    If one upstream failure truncated every snapshot of a vintage, the largest
    would still look complete beside its siblings. The claim records how many
    candidates were meant to be written, so it can catch that.
    """

    # The claim says 3 candidates x 5 horizons = 15 rows, but only 2 landed.
    _record(store, "decision-truncated", ["SH600000", "SH600001"],
            "2026-07-10T09:00:00+08:00")
    _claim(store, "decision-truncated", recorded_count=15, candidate_count=3)

    assert canonical_snapshots(store) == []


def test_a_manual_run_does_not_become_the_official_daily_snapshot(store):
    """An ad-hoc invocation must not silently become the decision of record."""

    _record(store, "decision-manual", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00")
    _claim(store, "decision-manual", recorded_count=15, run_kind="manual")

    assert canonical_snapshots(store) == []


def test_legacy_vintages_without_any_guard_record_are_labelled_inferred(store):
    """Rows written before the guard existed are weaker evidence, and say so."""

    _record(store, "decision-legacy", ["SH600000", "SH600001", "SH600002"],
            "2026-07-10T09:00:00+08:00")

    picked = canonical_snapshots(store)

    assert [p["decision_id"] for p in picked] == ["decision-legacy"]
    assert picked[0]["selection_kind"] == SELECTION_INFERRED
    assert picked[0]["policy_version"] == CANONICAL_POLICY_VERSION


def test_matured_defaults_to_confirmed_only_and_carries_provenance(store):
    """The default read is official evidence; weaker rows must be asked for.

    An `inferred` snapshot was chosen by shape alone. Returning it by default
    would let a downstream consumer treat it as equal to a guard-confirmed one,
    and the production ledger is 1 confirmed against 29 inferred.
    """

    from app.forecasting import ForecastOutcome

    ledger = ForecastLedger(store)
    _record(store, "decision-guarded", ["SH600000"], "2026-07-10T09:00:00+08:00",
            data_version="vintage-guarded")
    _record(store, "decision-legacy", ["SH600001"], "2026-07-13T09:00:00+08:00",
            data_version="vintage-legacy")
    _claim(store, "decision-guarded", recorded_count=5, candidate_count=1,
           data_version="vintage-guarded")
    for decision_id, subject in (("decision-guarded", "SH600000"),
                                 ("decision-legacy", "SH600001")):
        ledger.record_outcome(
            ForecastOutcome(
                decision_id=decision_id, scope="stock", subject=subject, horizon_days=5,
                observed_at="2026-08-10T15:00:00+08:00", continuous_return=0.05,
                benchmark_return=0.01, sector_return=0.02,
                data_version="outcome-eod-5", evidence={"price_source": "fixture"},
            )
        )

    official = ledger.matured("2026-08-11T00:00:00+08:00", scope="stock")
    assert [row.forecast.decision_id for row in official] == ["decision-guarded"]
    assert official[0].selection_kind == SELECTION_CONFIRMED

    exploratory = ledger.matured(
        "2026-08-11T00:00:00+08:00", scope="stock", include_inferred=True
    )
    kinds = {row.forecast.decision_id: row.selection_kind for row in exploratory}
    assert kinds == {
        "decision-guarded": SELECTION_CONFIRMED,
        "decision-legacy": SELECTION_INFERRED,
    }

    # The raw audit path still shows everything and claims no provenance.
    raw = ledger.matured("2026-08-11T00:00:00+08:00", scope="stock", deduplicate=False)
    assert len(raw) == 2
    assert all(row.selection_kind is None for row in raw)


def test_an_orphaned_snapshot_is_never_returned_as_official_evidence(store):
    """Open claim -> no canonical snapshot -> nothing official, even exploratory."""

    from app.forecasting import ForecastOutcome

    ledger = ForecastLedger(store)
    _record(store, "decision-A-orphan", ["SH600000"], "2026-07-10T09:00:00+08:00")
    _claim(store, "decision-B", recorded_count=0, candidate_count=1)
    ledger.record_outcome(
        ForecastOutcome(
            decision_id="decision-A-orphan", scope="stock", subject="SH600000",
            horizon_days=5, observed_at="2026-08-10T15:00:00+08:00",
            continuous_return=0.05, benchmark_return=0.01, sector_return=0.02,
            data_version="outcome-eod-5", evidence={"price_source": "fixture"},
        )
    )

    assert ledger.matured("2026-08-11T00:00:00+08:00", scope="stock") == []
    # Not even the exploratory path resurrects it: the vintage has no canonical
    # snapshot at all while a claim is open.
    assert ledger.matured(
        "2026-08-11T00:00:00+08:00", scope="stock", include_inferred=True
    ) == []
    # But the row is still on disk for audit.
    assert len(
        ledger.matured("2026-08-11T00:00:00+08:00", scope="stock", deduplicate=False)
    ) == 1


def test_a_scheduled_claim_matching_a_two_horizon_stock_snapshot_is_not_confirmed(store):
    """recorded_count agreeing with itself is not proof of a complete grid.

    A stock run truncated to horizons (1, 3) writes two rows for its one
    candidate and records recorded_count=2, so subject_count == candidate_count,
    row_count == recorded_count and the snapshot is rectangular - every
    self-consistency check passes. Only the grid itself catches it, because
    recorded_count says what was written, never what was intended.
    """

    _record(store, "decision-truncated-grid", ["SH600000"],
            "2026-07-10T09:00:00+08:00", horizons=(1, 3))
    _claim(store, "decision-truncated-grid", recorded_count=2, candidate_count=1)

    assert canonical_snapshots(store) == []


def test_a_full_five_horizon_stock_snapshot_is_still_confirmed(store):
    """The complete grid must keep passing, so the rule is not merely strict."""

    _record(store, "decision-full-grid", ["SH600000"], "2026-07-10T09:00:00+08:00")
    _claim(store, "decision-full-grid", recorded_count=5, candidate_count=1)

    picked = canonical_snapshots(store)

    assert [p["decision_id"] for p in picked] == ["decision-full-grid"]
    assert picked[0]["selection_kind"] == SELECTION_CONFIRMED


def test_a_legacy_sector_snapshot_is_not_held_to_the_stock_grid(store):
    """Sector theses were never written on FORECAST_HORIZONS."""

    ledger = ForecastLedger(store)
    for horizon in (1, 3):
        ledger.record_forecast(
            ForecastDecision(
                decision_id="sector-legacy", scope="sector", subject="ai_compute",
                decision_cutoff="2026-07-10T09:00:00+08:00",
                available_at="2026-07-10T09:00:00+08:00", horizon_days=horizon,
                rank=1, score=90.0, probability=None, model_version="sector-v1",
                prompt_version="thesis-v1", data_version="sector-vintage",
                features={}, evidence=[], reasons=["fixture"], status="pending_outcome",
            )
        )

    picked = {p["decision_id"]: p["selection_kind"] for p in canonical_snapshots(store)}

    assert picked == {"sector-legacy": SELECTION_INFERRED}


def test_outcome_provenance_survives_persistence_and_reload(store):
    """An exploratory label must stay identifiable after it is written.

    Reporting selection_kind in the response is not enough: once a row is on
    disk it looks like any other matured outcome, and re-deriving provenance
    from the canonical query later is unreliable because a vintage's
    classification changes as claims land. So it is written into the evidence.
    """

    from app.forecasting import ForecastOutcome
    from app.forecasting.canonical import CANONICAL_POLICY_VERSION

    ledger = ForecastLedger(store)
    _record(store, "decision-confirmed", ["SH600000"], "2026-07-10T09:00:00+08:00",
            data_version="vintage-confirmed")
    _claim(store, "decision-confirmed", recorded_count=5, candidate_count=1,
           data_version="vintage-confirmed")
    _record(store, "decision-legacy", ["SH600001"], "2026-07-10T09:00:00+08:00",
            data_version="vintage-legacy")

    for decision_id, subject, kind in (
        ("decision-confirmed", "SH600000", SELECTION_CONFIRMED),
        ("decision-legacy", "SH600001", SELECTION_INFERRED),
    ):
        ledger.record_outcome(
            ForecastOutcome(
                decision_id=decision_id, scope="stock", subject=subject, horizon_days=5,
                observed_at="2026-08-10T15:00:00+08:00", continuous_return=0.05,
                benchmark_return=0.01, sector_return=0.02, data_version="outcome-eod-5",
                evidence={
                    "price_source": "fixture",
                    "canonical_selection_kind": kind,
                    "canonical_policy_version": CANONICAL_POLICY_VERSION,
                },
            )
        )

    # Reloaded from disk, not from the object that was written.
    reloaded = {
        row["decision_id"]: json.loads(row["evidence_json"] or "{}")
        for row in store.fetch_all(
            "SELECT decision_id, evidence_json FROM forecast_outcomes"
        )
    }
    assert reloaded["decision-confirmed"]["canonical_selection_kind"] == SELECTION_CONFIRMED
    assert reloaded["decision-legacy"]["canonical_selection_kind"] == SELECTION_INFERRED
    assert (
        reloaded["decision-legacy"]["canonical_policy_version"] == CANONICAL_POLICY_VERSION
    )

    # And the official read still refuses the inferred one on its own merits.
    official = ledger.matured("2026-08-11T00:00:00+08:00", scope="stock")
    assert [row.forecast.decision_id for row in official] == ["decision-confirmed"]
    assert official[0].selection_kind == SELECTION_CONFIRMED


def test_label_due_reports_confirmed_and_inferred_counts_and_quality(store):
    """The response must say what evidence it just wrote."""

    from datetime import datetime, timezone

    from app.forecasting.feedback import ForecastFeedback

    _record(store, "decision-legacy", ["SH600001"], "2026-07-10T09:00:00+08:00",
            data_version="vintage-legacy")

    result = ForecastFeedback(store).label_due(
        datetime(2027, 1, 1, tzinfo=timezone.utc), include_inferred=True
    )

    assert "confirmed_labelled_count" in result
    assert "inferred_labelled_count" in result
    assert result["canonical_policy_version"] == CANONICAL_POLICY_VERSION
    # Anything written from an inferred snapshot taints the aggregate.
    if result["inferred_labelled_count"]:
        assert result["evidence_quality"] == "exploratory"
        for item in result["labelled"]:
            assert item["selection_kind"] in {SELECTION_CONFIRMED, SELECTION_INFERRED}
