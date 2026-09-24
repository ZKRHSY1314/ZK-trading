from __future__ import annotations

from datetime import datetime
import json
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.control_plane.service import ControlPlaneService
from app.data.trading_calendar import trading_session_age
from app.storage.sqlite_store import SQLiteStore


SHANGHAI = ZoneInfo("Asia/Shanghai")


class _Pulse:
    def __init__(self, status: str = "completed") -> None:
        self.status = status

    def latest_context(self, limit: int) -> dict:
        return {"status": "completed", "top_sectors": [{"sector": "ai_compute"}]}

    def run(self, **_: object) -> dict:
        return {
            "status": self.status,
            "run_id": 7,
            "item_count": 12,
            "sector_count": 2,
            "source_count": 4,
            "successful_source_count": 3,
            "sector_signals": [{"sector": "ai_compute", "heat_score": 55}],
            "errors": [],
        }


class _Feedback:
    def snapshot(self) -> dict:
        return {"status": "needs_outcomes", "sample_count": 4, "mature_outcome_count": 0}

    def run(self, **_: object) -> dict:
        return {
            "status": "partial",
            "created_samples": 3,
            "labeled_outcomes": 0,
            "mature_outcome_count": 0,
            "blocked_reasons": ["insufficient_mature_outcomes"],
        }


class _ForecastFeedback:
    def label_due(self, *_: object, **__: object) -> dict:
        return {
            "status": "completed",
            "eligible_count": 0,
            "labelled_count": 0,
            "pending_count": 0,
        }

    def evaluate(self, *_: object, **__: object) -> dict:
        return {
            "status": "ready",
            "as_of": "2026-07-10T02:00:00Z",
            "review_only": True,
            "horizons": [{"horizon_days": 5, "status": "ready", "sample_count": 20}],
            "by_scope": {},
        }


class _Selection:
    def run(self, **_: object) -> dict:
        return {
            "status": "completed",
            "schema_version": "strategy_selection_v2.1",
            "date": "2026-07-10",
            "config_version": "pytest-v1",
            "summary": {"candidate_count": 1},
            "daily_candidate_snapshot": [
                {
                    "symbol": "SZ000001",
                    "name": "fixture",
                    "plan_type": "WATCH_ONLY_PLAN",
                    "final_score": 65,
                    "risk_flags": [],
                }
            ],
            "data_gap_candidates": [],
        }


class _AgentControl:
    def create_task(self, task):
        assert task.task_type == "full_simulation_cycle"
        assert task.payload["limit"] == 20
        assert task.payload["decision_snapshot"]["schema_version"] == "strategy_selection_v2.1"
        assert (
            task.payload["decision_snapshot"]["daily_candidate_snapshot"][0]["symbol"] == "SZ000001"
        )
        return SimpleNamespace(id=99)

    def execute_task(self, task_id: int):
        assert task_id == 99
        return SimpleNamespace(
            id=99,
            model_dump=lambda **_: {
                "id": 99,
                "status": "completed",
                "result": {"status": "partial"},
                "error": None,
            },
        )


@pytest.fixture(autouse=True)
def _clear_decision_day_claims(test_db):
    """Give each test its own claim state.

    test_db is session-scoped, so the one-snapshot-per-vintage claim would
    otherwise leak between tests and the first recording test would silently
    starve every later one.
    """

    with test_db.connect() as conn:
        conn.execute("DELETE FROM forecast_decision_days")
    yield


def _service(
    test_db,
    *,
    hour: int = 10,
    pulse_status: str = "completed",
    market_status: str = "missing",
) -> ControlPlaneService:
    return ControlPlaneService(
        store=test_db,
        public_opinion_factory=lambda: _Pulse(pulse_status),
        feedback_factory=_Feedback,
        forecast_feedback_factory=_ForecastFeedback,
        selection_factory=_Selection,
        agent_control_factory=_AgentControl,
        market_data_factory=lambda _now, _limit: {
            "status": market_status,
            "latest_trade_date": "2026-07-10" if market_status == "fresh" else None,
            "decision_allowed": market_status == "fresh",
        },
        market_data_refresh_factory=lambda _: {"processed": 0, "results": []},
        clock=lambda: datetime(2026, 7, 10, hour, 0, tzinfo=SHANGHAI),
    )


def test_control_plane_status_is_read_only_and_reports_feedback_gap(test_db):
    result = _service(test_db).status()

    assert result["status"] == "attention"
    assert result["market_stage"] == "intraday"
    assert result["recommended_profile"] == "full"
    assert "training_feedback_needs_outcomes" in result["attention_reasons"]
    assert "market_data_missing" in result["attention_reasons"]
    assert result["safety"]["live_trading_enabled"] is False
    assert result["safety"]["real_order_placement"] is False


def test_control_plane_full_run_preserves_partial_business_status(test_db):
    result = _service(test_db, market_status="fresh").run_once(
        profile="full",
        limit=20,
        monitor_limit=3,
        requested_by="pytest",
    )

    assert result["status"] == "partial"
    assert result["task_id"] == 99
    assert [step["step_id"] for step in result["steps"]] == [
        "market_pulse",
        "decision_snapshot",
        "simulation_cycle",
        "forecast_feedback",
        "training_feedback",
    ]
    simulation = next(step for step in result["steps"] if step["step_id"] == "simulation_cycle")
    assert simulation["status"] == "partial"
    assert result["safety"]["broker_access"] is False


def test_control_plane_persists_every_ranked_candidate_horizon_in_forecast_ledger(test_db):
    # This models the scheduled path: only a scheduled run writes the official
    # ledger, and run_once now defaults to a manual preview so an unstated
    # caller cannot.
    result = _service(test_db, market_status="fresh").run_once(
        profile="pulse",
        limit=20,
        requested_by="pytest-ledger",
        run_kind="scheduled",
    )

    decision = next(step for step in result["steps"] if step["step_id"] == "decision_snapshot")
    decision_id = decision["details"]["snapshot_id"]
    rows = test_db.fetch_all(
        """
        SELECT decision_id, scope, subject, horizon_days, probability,
               features_json, review_only
        FROM forecast_decisions
        WHERE decision_id = ?
        ORDER BY horizon_days
        """,
        (decision_id,),
    )

    assert [row["horizon_days"] for row in rows] == [1, 3, 5, 10, 20]
    assert {row["subject"] for row in rows} == {"SZ000001"}
    assert {row["scope"] for row in rows} == {"stock"}
    assert all(row["probability"] is None for row in rows)
    assert all(
        json.loads(row["features_json"])["probability_semantics"]
        == "unavailable_uncalibrated_structure_score"
        for row in rows
    )
    assert all(row["review_only"] == 1 for row in rows)
    assert decision["details"]["forecast_ledger"]["recorded_count"] == 5


def test_control_plane_passes_full_timezone_aware_cutoff_to_selection(test_db):
    captured: dict[str, object] = {}
    cutoff = datetime(2026, 7, 10, 10, 17, 23, tzinfo=SHANGHAI)

    class CapturingSelection(_Selection):
        def run(self, **kwargs: object) -> dict:
            captured.update(kwargs)
            return super().run(**kwargs)

    service = ControlPlaneService(
        store=test_db,
        public_opinion_factory=_Pulse,
        feedback_factory=_Feedback,
        forecast_feedback_factory=_ForecastFeedback,
        selection_factory=CapturingSelection,
        agent_control_factory=_AgentControl,
        market_data_factory=lambda _now, _limit: {
            "status": "fresh",
            "latest_trade_date": "2026-07-10",
            "decision_allowed": True,
        },
        clock=lambda: cutoff,
    )

    service.run_once(profile="pulse", limit=20, requested_by="pytest-pit-cutoff")

    assert captured["as_of"] == cutoff
    assert "as_of_date" not in captured


def test_control_plane_full_run_skips_simulation_when_market_data_is_stale(test_db):
    result = _service(test_db, market_status="stale").run_once(profile="full", limit=20)

    simulation = next(step for step in result["steps"] if step["step_id"] == "simulation_cycle")
    assert result["task_id"] is None
    assert simulation["status"] == "partial"
    assert simulation["reason"] == "daily_bar_cache_stale"


def test_control_plane_refreshes_stale_market_data_before_simulation(test_db):
    state = {"status": "stale"}

    def market_data(_now, _limit):
        return {
            "status": state["status"],
            "latest_trade_date": "2026-07-10" if state["status"] == "fresh" else "2026-06-29",
            "decision_allowed": state["status"] == "fresh",
        }

    def refresh(_):
        state["status"] = "fresh"
        return {"processed": 1, "results": [{"status": "success"}]}

    service = ControlPlaneService(
        store=test_db,
        public_opinion_factory=_Pulse,
        feedback_factory=_Feedback,
        forecast_feedback_factory=_ForecastFeedback,
        selection_factory=_Selection,
        agent_control_factory=_AgentControl,
        market_data_factory=market_data,
        market_data_refresh_factory=refresh,
        clock=lambda: datetime(2026, 7, 10, 10, 0, tzinfo=SHANGHAI),
    )

    result = service.run_once(profile="full", limit=20)

    refresh_step = next(
        step for step in result["steps"] if step["step_id"] == "market_data_refresh"
    )
    assert refresh_step["status"] == "completed"
    assert result["market_data"]["status"] == "fresh"
    assert result["task_id"] == 99


def test_control_plane_adaptive_offhour_runs_maintenance(test_db):
    result = _service(test_db, hour=22).run_once(profile="adaptive", limit=20)

    assert result["profile"] == "maintenance"
    assert [step["step_id"] for step in result["steps"]] == [
        "market_pulse",
        "market_data_refresh",
        "decision_snapshot",
        "forecast_feedback",
        "training_feedback",
    ]
    decision = next(step for step in result["steps"] if step["step_id"] == "decision_snapshot")
    assert decision["status"] == "partial"
    assert decision["details"]["reason"] == "daily_bar_cache_missing"


def test_control_plane_insufficient_training_samples_is_partial(test_db):
    class InsufficientFeedback(_Feedback):
        def run(self, **_: object) -> dict:
            return {"status": "insufficient_samples", "blocked_reasons": ["not_mature"]}

    service = ControlPlaneService(
        store=test_db,
        public_opinion_factory=_Pulse,
        feedback_factory=InsufficientFeedback,
        forecast_feedback_factory=_ForecastFeedback,
        selection_factory=_Selection,
        agent_control_factory=_AgentControl,
        clock=lambda: datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI),
    )

    result = service.run_once(profile="training", limit=20)

    assert result["status"] == "partial"
    assert [step["step_id"] for step in result["steps"]] == [
        "forecast_feedback",
        "training_feedback",
    ]
    assert result["steps"][1]["status"] == "partial"


def test_control_plane_source_failure_is_not_reported_completed(test_db):
    result = _service(test_db, pulse_status="partial").run_once(profile="pulse", limit=20)

    assert result["status"] == "partial"
    assert result["steps"][0]["status"] == "partial"


def test_control_plane_unknown_business_status_fails_closed_to_partial(test_db):
    result = _service(test_db, pulse_status="unexpected_vendor_state").run_once(
        profile="pulse",
        limit=20,
    )

    assert result["status"] == "partial"
    assert result["steps"][0]["status"] == "partial"


def test_forecast_feedback_compaction_reports_stock_and_sector_without_fold_payloads():
    compact = ControlPlaneService._compact_forecast_feedback(
        {
            "labels": {
                "eligible_count": 1,
                "labelled_count": 1,
                "pending_count": 0,
                "by_scope": {
                    "stock": {"eligible_count": 1, "labelled_count": 1},
                    "sector": {"eligible_count": 2, "labelled_count": 1, "pending_count": 1},
                },
            },
            "evaluation": {
                "status": "ready",
                "horizons": [],
                "by_scope": {
                    "stock": {"status": "insufficient_data", "horizons": []},
                    "sector": {
                        "status": "ready",
                        "horizons": [
                            {
                                "horizon_days": 5,
                                "status": "ready",
                                "sample_count": 25,
                                "fold_count": 4,
                                "coverage": 0.9,
                                "precision_at_k": 0.6,
                                "by_decision": [{"decision_id": "large-fold-payload"}],
                            }
                        ],
                    },
                },
            },
            "calibration": {"proposal_count": 1, "proposal_ids": [7]},
        }
    )

    assert compact["by_scope"]["sector"]["labelled_count"] == 1
    assert compact["by_scope"]["sector"]["horizons"][0]["precision_at_k"] == 0.6
    assert "by_decision" not in compact["by_scope"]["sector"]["horizons"][0]
    assert compact["calibration_proposal_ids"] == [7]


def test_control_plane_requires_broad_latest_bar_coverage(tmp_path):
    store = SQLiteStore(tmp_path / "market.sqlite3")
    store.init()
    with store.connect() as conn:
        for symbol, trade_date in (("SH600001", "2026-07-10"), ("SZ000001", "2026-07-09")):
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, source, quality_status
                ) VALUES (?, ?, 10, 10.2, 9.8, 10.1, 'pytest', 'ready')
                """,
                (symbol, trade_date),
            )
    service = ControlPlaneService(
        store=store,
        clock=lambda: datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI),
    )

    snapshot = service._market_data_snapshot(datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI))

    assert snapshot["status"] == "incomplete"
    assert snapshot["latest_coverage_ratio"] == 0.5
    assert snapshot["decision_allowed"] is False


def test_control_plane_coverage_uses_selection_universe_not_cache_history(tmp_path):
    store = SQLiteStore(tmp_path / "selection-universe.sqlite3")
    store.init()
    with store.connect() as conn:
        for symbol in ("SH600010", "SH600011", "SH600012"):
            conn.execute(
                """
                INSERT INTO stock_profiles(
                    symbol, name, current_price, dataset_name, source_file, raw_json
                ) VALUES (?, ?, 10, 'production', 'import.csv', '{}')
                """,
                (symbol, symbol),
            )
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, source, quality_status
            ) VALUES ('SH600010', '2026-07-10', 10, 10.2, 9.8, 10.1, 'pytest', 'ready')
            """
        )
    service = ControlPlaneService(store=store)

    snapshot = service._market_data_snapshot(
        datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI),
        limit=5,
    )

    assert snapshot["universe_source"] == "selection_v2"
    assert snapshot["total_symbol_count"] == 3
    assert snapshot["latest_symbol_count"] == 1
    assert snapshot["latest_coverage_ratio"] == 0.3333
    assert snapshot["status"] == "incomplete"


def test_control_plane_requires_current_session_bar_after_close(tmp_path):
    store = SQLiteStore(tmp_path / "close-freshness.sqlite3")
    store.init()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, source, quality_status
            ) VALUES ('SH600020', '2026-07-09', 10, 10.2, 9.8, 10.1, 'pytest', 'ready')
            """
        )
    service = ControlPlaneService(store=store)

    intraday = service._market_data_snapshot(
        datetime(2026, 7, 10, 10, 0, tzinfo=SHANGHAI),
        limit=5,
    )
    after_close = service._market_data_snapshot(
        datetime(2026, 7, 10, 16, 0, tzinfo=SHANGHAI),
        limit=5,
    )

    assert intraday["status"] == "fresh"
    assert after_close["status"] == "stale"


def test_trading_session_age_respects_exchange_holiday_gap():
    sessions = {
        datetime(2026, 1, 30, tzinfo=SHANGHAI).date(),
        datetime(2026, 2, 5, tzinfo=SHANGHAI).date(),
    }

    intraday_age, source = trading_session_age(
        datetime(2026, 1, 30, tzinfo=SHANGHAI).date(),
        datetime(2026, 2, 5, tzinfo=SHANGHAI).date(),
        exclude_target_session=True,
        trading_dates=sessions,
    )
    after_close_age, _ = trading_session_age(
        datetime(2026, 1, 30, tzinfo=SHANGHAI).date(),
        datetime(2026, 2, 5, tzinfo=SHANGHAI).date(),
        exclude_target_session=False,
        trading_dates=sessions,
    )

    assert source == "injected"
    assert intraday_age == 0
    assert after_close_age == 1


def test_control_plane_status_route_is_mounted(client):
    response = client.get("/api/control-plane/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "control_plane_status.v1"
    assert payload["safety"]["live_trading_enabled"] is False
    assert payload["safety"]["real_order_placement"] is False


def _decision_rows(store, data_version: str = "2026-07-10") -> int:
    with store.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM forecast_decisions WHERE data_version = ?",
                (data_version,),
            ).fetchone()[0]
        )


def test_only_one_decision_snapshot_is_recorded_per_bar_vintage(test_db):
    """A repeated cycle on the same bar vintage must not re-record the day.

    The loop runs every 15 minutes and the candidate set only changes when the
    bars do, so without this each cycle re-froze the same decisions: 8 snapshots
    and 1,200 rows for 30 subjects were observed in one morning, and July days
    carry 10-24x. Every pooled statistic downstream would then be weighted by
    loop uptime rather than by distinct decisions.
    """

    service = _service(test_db, market_status="fresh")

    before = _decision_rows(test_db)
    first = service._run_decision_snapshot(
        limit=5, now=datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI), run_kind="scheduled"
    )
    assert first["forecast_ledger"]["status"] == "recorded"
    recorded = first["forecast_ledger"]["recorded_count"]
    assert recorded > 0
    assert _decision_rows(test_db) == before + recorded

    second = service._run_decision_snapshot(
        limit=5, now=datetime(2026, 7, 10, 17, 15, tzinfo=SHANGHAI), run_kind="scheduled"
    )
    ledger = second["forecast_ledger"]
    assert ledger["status"] == "already_recorded"
    assert ledger["recorded_count"] == 0
    # The reason names the vintage, so an operator can tell "already done today"
    # apart from "produced nothing".
    assert ledger["reason"] == "decision_day_already_recorded:2026-07-10"
    assert ledger["existing_decision_id"] == first["snapshot_id"]
    # No new rows: the whole point.
    assert _decision_rows(test_db) == before + recorded


def test_a_claim_that_never_wrote_its_rows_is_taken_over(test_db):
    """A crash between claiming and writing must not lock the day out forever.

    The claim is taken before the inserts so a racing cycle loses immediately,
    which leaves a window where a dead process owns a vintage with zero rows.
    Age is what makes it abandoned rather than merely in flight.
    """

    service = _service(test_db, market_status="fresh")
    with test_db.connect() as conn:
        conn.execute(
            "INSERT INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) "
            # Hours old, so it is unambiguously a corpse rather than a writer
            # that is merely mid-flight.
            "VALUES ('stock', '2026-07-10', 'decision-crashed', "
            "'2026-07-10T09:00:00+08:00', 5, 0, 'scheduled')"
        )

    result = service._run_decision_snapshot(
        limit=5, now=datetime(2026, 7, 10, 17, 30, tzinfo=SHANGHAI), run_kind="scheduled"
    )

    assert result["forecast_ledger"]["status"] == "recorded"
    assert result["snapshot_id"] != "decision-crashed"
    with test_db.connect() as conn:
        row = conn.execute(
            "SELECT decision_id, recorded_count FROM forecast_decision_days "
            "WHERE scope = 'stock' AND data_version = '2026-07-10'"
        ).fetchone()
    assert row["decision_id"] == result["snapshot_id"]
    assert int(row["recorded_count"]) == result["forecast_ledger"]["recorded_count"]


def test_stale_market_data_never_claims_a_vintage(test_db):
    """A cycle that cannot see fresh bars must leave the day available.

    Claiming on a degraded run would freeze the vintage against the real
    snapshot that follows once the bars land.
    """

    service = _service(test_db, market_status="missing")

    result = service._run_decision_snapshot(limit=5, now=datetime(2026, 7, 10, 11, 0, tzinfo=SHANGHAI))

    assert result["status"] == "partial"
    with test_db.connect() as conn:
        claims = int(
            conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0]
        )
    assert claims == 0
def test_two_concurrent_claims_cannot_both_win_the_same_vintage(tmp_path):
    """The primary key is the guard, so real threads have to prove it.

    A read-then-write check in application code lets two callers both pass, and
    concurrent callers are ordinary: a scheduled loop and a manual run-once
    overlap. Each thread gets its own store, as separate processes would.
    """

    import threading

    from app.storage.sqlite_store import SQLiteStore

    db_path = tmp_path / "claims.sqlite3"
    SQLiteStore(db_path).init()

    start = threading.Barrier(6)
    outcomes: list[object] = []
    lock = threading.Lock()

    def claim(index: int) -> None:
        service = ControlPlaneService(
            store=SQLiteStore(db_path),
            public_opinion_factory=lambda: _Pulse("completed"),
            feedback_factory=_Feedback,
            forecast_feedback_factory=_ForecastFeedback,
            selection_factory=_Selection,
            agent_control_factory=_AgentControl,
            market_data_factory=lambda _now, _limit: {"status": "fresh"},
            market_data_refresh_factory=lambda _: {"processed": 0, "results": []},
            clock=lambda: datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI),
        )
        start.wait()
        result = service._claim_decision_day(
            scope="stock",
            run_kind="scheduled",
            data_version="2026-07-10",
            decision_id=f"decision-{index}",
            candidate_count=3,
            claimed_at="2026-07-10T17:00:00+08:00",
        )
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=claim, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    winners = [item for item in outcomes if item is None]
    assert len(winners) == 1, f"expected exactly one winner, got {len(winners)}"
    assert len(outcomes) == 6
    with SQLiteStore(db_path).connect() as conn:
        assert int(conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0]) == 1


def test_an_empty_claim_that_is_still_recent_is_left_alone(test_db):
    """An in-flight writer is observably empty; reclaiming it duplicates the day.

    Rows are written after the claim commits, so recorded_count stays 0 for the
    whole time a healthy writer is working. Only age distinguishes that from a
    process that died.
    """

    service = _service(test_db, market_status="fresh")
    with test_db.connect() as conn:
        conn.execute(
            "INSERT INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) "
            "VALUES ('stock', '2026-07-10', 'decision-in-flight', "
            "'2026-07-10T16:59:30+08:00', 5, 0, 'scheduled')"
        )

    held = service._claim_decision_day(
        scope="stock",
        run_kind="scheduled",
        data_version="2026-07-10",
        decision_id="decision-intruder",
        candidate_count=5,
        claimed_at="2026-07-10T17:00:00+08:00",
    )

    assert held is not None
    assert held["decision_id"] == "decision-in-flight"
    with test_db.connect() as conn:
        row = conn.execute(
            "SELECT decision_id FROM forecast_decision_days WHERE data_version = '2026-07-10'"
        ).fetchone()
    assert row["decision_id"] == "decision-in-flight"


def test_an_empty_claim_older_than_the_stale_window_is_reclaimed(test_db):
    service = _service(test_db, market_status="fresh")
    with test_db.connect() as conn:
        conn.execute(
            "INSERT INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) "
            "VALUES ('stock', '2026-07-10', 'decision-dead', "
            "'2026-07-10T09:00:00+08:00', 5, 0, 'scheduled')"
        )

    held = service._claim_decision_day(
        scope="stock",
        run_kind="scheduled",
        data_version="2026-07-10",
        decision_id="decision-fresh",
        candidate_count=5,
        claimed_at="2026-07-10T17:00:00+08:00",
    )

    assert held is None
    with test_db.connect() as conn:
        row = conn.execute(
            "SELECT decision_id FROM forecast_decision_days WHERE data_version = '2026-07-10'"
        ).fetchone()
    assert row["decision_id"] == "decision-fresh"


def test_a_stale_writer_that_resumes_after_takeover_is_rejected(test_db):
    """Writer A stalls, Writer B takes the vintage, A wakes up and must lose.

    The lease alone cannot prevent this: it stops an *immediate* takeover, but a
    writer that pauses past the lease loses the vintage and would otherwise
    resume inserting rows and finalize over the successor's claim - two
    snapshots for one vintage, which is the outcome the guard exists to stop.
    Ownership is fenced by decision_id, carried in the finalizing UPDATE itself.
    """

    service = _service(test_db, market_status="fresh")

    # Writer A claims the vintage, then stalls (nothing finalized yet).
    assert (
        service._claim_decision_day(
            scope="stock",
            run_kind="scheduled",
            data_version="2026-07-10",
            decision_id="decision-A",
            candidate_count=5,
            claimed_at="2026-07-10T09:00:00+08:00",
        )
        is None
    )

    # Writer B arrives long after the lease expired and takes over.
    assert (
        service._claim_decision_day(
            scope="stock",
            run_kind="scheduled",
            data_version="2026-07-10",
            decision_id="decision-B",
            candidate_count=5,
            claimed_at="2026-07-10T17:00:00+08:00",
        )
        is None
    )
    assert service._owns_decision_day(
        scope="stock", data_version="2026-07-10", decision_id="decision-B"
    )

    # Writer A wakes up. It no longer owns the vintage, and it must not be able
    # to publish - not even though it holds a claim it once won.
    assert not service._owns_decision_day(
        scope="stock", data_version="2026-07-10", decision_id="decision-A"
    )
    assert (
        service._finalize_decision_day(
            scope="stock",
            data_version="2026-07-10",
            decision_id="decision-A",
            recorded_count=150,
        )
        is False
    )

    # B's ownership survives A's attempt untouched.
    with test_db.connect() as conn:
        row = conn.execute(
            "SELECT decision_id, recorded_count FROM forecast_decision_days "
            "WHERE scope = 'stock' AND data_version = '2026-07-10'"
        ).fetchone()
    assert row["decision_id"] == "decision-B"
    assert int(row["recorded_count"]) == 0

    # And B can still publish normally.
    assert (
        service._finalize_decision_day(
            scope="stock",
            data_version="2026-07-10",
            decision_id="decision-B",
            recorded_count=150,
        )
        is True
    )


def test_a_vintage_already_finalized_by_a_successor_reports_already_recorded(test_db):
    """A finalized successor is reached at the claim, before any writing starts.

    This is the idempotent-repeat path, not the ownership-loss path: the run
    never begins writing, so it reports already_recorded. The genuine
    ownership-loss races are exercised below.
    """

    service = _service(test_db, market_status="fresh")
    now = datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI)

    # A successor already owns the vintage and has published.
    with test_db.connect() as conn:
        conn.execute(
            "INSERT INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) "
            "VALUES ('stock', '2026-07-10', 'decision-successor', "
            "'2026-07-10T16:59:00+08:00', 5, 150, 'scheduled')"
        )

    result = service._run_decision_snapshot(limit=5, now=now, run_kind="scheduled")

    ledger = result["forecast_ledger"]
    assert ledger["status"] == "already_recorded"
    assert ledger["recorded_count"] == 0
    assert ledger["existing_decision_id"] == "decision-successor"


def test_a_manual_run_is_a_preview_and_never_writes_the_official_ledger(test_db):
    """run_kind travels from the caller to the claim, and manual writes nothing.

    A field on the request model would be cosmetic if the service still shared
    one claim key: the claim is keyed on (scope, data_version), so a manual run
    that took it would leave the scheduled run with "already_recorded" and no way
    to replace it - costing that day its official snapshot permanently.
    """

    service = _service(test_db, market_status="fresh")
    with test_db.connect() as conn:
        # test_db is session-scoped, so measure what THIS run adds.
        before = int(conn.execute("SELECT COUNT(*) FROM forecast_decisions").fetchone()[0])

    result = service.run_once(profile="full", limit=5, run_kind="manual")

    decision = next(
        step for step in result["steps"] if step["step_id"] == "decision_snapshot"
    )
    ledger = decision["details"]["forecast_ledger"]
    assert ledger["status"] == "preview_not_recorded"
    assert ledger["recorded_count"] == 0
    assert ledger["run_kind"] == "manual"
    # Nothing claimed, nothing written.
    with test_db.connect() as conn:
        assert int(conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0]) == 0
        after = int(conn.execute("SELECT COUNT(*) FROM forecast_decisions").fetchone()[0])
    assert after == before


def test_a_manual_run_cannot_block_the_scheduled_snapshot_for_that_day(test_db):
    """The scheduled run must still get its day after a manual one ran first."""

    service = _service(test_db, market_status="fresh")

    service.run_once(profile="full", limit=5, run_kind="manual")
    scheduled = service._run_decision_snapshot(
        limit=5, now=datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI), run_kind="scheduled"
    )

    assert scheduled["forecast_ledger"]["status"] == "recorded"
    assert scheduled["forecast_ledger"]["recorded_count"] > 0
    with test_db.connect() as conn:
        row = conn.execute(
            "SELECT decision_id, run_kind FROM forecast_decision_days"
        ).fetchone()
    assert row["run_kind"] == "scheduled"
    assert row["decision_id"] == scheduled["snapshot_id"]


def test_the_api_model_carries_run_kind_into_the_service(test_db):
    """End to end: request field -> run_once -> claim table."""

    from app.control_plane.router import ControlPlaneRunInput

    # An unspecified caller is not the scheduler, so the model defaults to a
    # preview. Only the worker asks for "scheduled" explicitly.
    assert ControlPlaneRunInput().run_kind == "manual"
    payload = ControlPlaneRunInput().model_dump()
    assert payload["run_kind"] == "manual"

    service = _service(test_db, market_status="fresh")
    result = service.run_once(**{**payload, "profile": "full", "limit": 5})

    decision = next(
        step for step in result["steps"] if step["step_id"] == "decision_snapshot"
    )
    assert decision["details"]["forecast_ledger"]["status"] == "preview_not_recorded"


def test_the_http_endpoint_defaults_to_manual_preview(client, test_db):
    """Over real HTTP, an unspecified caller must not take the official claim.

    The cockpit's run button posts no run_kind. With a "scheduled" default a
    human clicking Run consumed that day's claim - a primary key - so the real
    scheduled run afterwards could only get "already_recorded" and the day lost
    its official snapshot permanently.
    """

    with test_db.connect() as conn:
        before_claims = int(
            conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0]
        )
        before_rows = int(
            conn.execute("SELECT COUNT(*) FROM forecast_decisions").fetchone()[0]
        )

    response = client.post("/api/control-plane/run-once", json={"profile": "full", "limit": 5})

    assert response.status_code == 200
    decision = next(
        (
            step
            for step in response.json().get("steps", [])
            if step.get("step_id") == "decision_snapshot"
        ),
        None,
    )
    # The decision step may stop earlier than the preview gate when this test
    # database has no bars; either way the official ledger must be untouched,
    # which is what the counts below prove.
    if decision is not None:
        ledger = (decision.get("details") or {}).get("forecast_ledger")
        if ledger is not None:
            assert ledger["status"] == "preview_not_recorded"
            assert ledger["run_kind"] == "manual"

    with test_db.connect() as conn:
        assert (
            int(conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0])
            == before_claims
        )
        assert (
            int(conn.execute("SELECT COUNT(*) FROM forecast_decisions").fetchone()[0])
            == before_rows
        )


def test_the_scheduled_worker_asks_for_the_official_claim() -> None:
    """The one caller that may write the official ledger says so explicitly."""

    from scripts import control_plane_loop

    sent: dict = {}

    def _request(method, url, payload=None, *, timeout=30):
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        sent.update(payload or {})
        return {"status": "completed"}

    control_plane_loop.request_json = _request
    try:
        control_plane_loop.run_slot("http://127.0.0.1:8000", "full", 30)
    finally:
        import importlib

        importlib.reload(control_plane_loop)

    assert sent["run_kind"] == "scheduled"
    assert sent["requested_by"] == "control_plane_worker"


def test_an_omitted_run_kind_cannot_create_an_official_claim(test_db):
    """Fail closed at the core, not only at the HTTP edge.

    A caller that forgets to state provenance must not mint the day's official
    snapshot. run_once defaults to a preview, and the one function that can
    create a claim refuses anything but an explicit scheduled run.
    """

    service = _service(test_db, market_status="fresh")

    # Omitted at the service entry point: preview, nothing claimed.
    result = service.run_once(profile="full", limit=5)
    decision = next(
        step for step in result["steps"] if step["step_id"] == "decision_snapshot"
    )
    assert decision["details"]["forecast_ledger"]["status"] == "preview_not_recorded"
    with test_db.connect() as conn:
        assert int(conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0]) == 0

    # Omitted at the claim itself: refused outright rather than defaulted.
    with pytest.raises(ValueError, match="only 'scheduled' runs may claim"):
        service._claim_decision_day(
            scope="stock",
            data_version="2026-07-10",
            decision_id="decision-unstated",
            candidate_count=5,
            claimed_at="2026-07-10T17:00:00+08:00",
        )
    with pytest.raises(ValueError, match="only 'scheduled' runs may claim"):
        service._claim_decision_day(
            scope="stock",
            data_version="2026-07-10",
            decision_id="decision-manual",
            candidate_count=5,
            claimed_at="2026-07-10T17:00:00+08:00",
            run_kind="manual",
        )
    with test_db.connect() as conn:
        assert int(conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0]) == 0


def test_http_forwards_manual_by_default_and_scheduled_when_asked(client, monkeypatch):
    """The routing contract itself, independent of whether bars exist.

    Asserting only that no rows were written is weak: a request that fails early
    for want of market data writes nothing either. A spy captures the exact
    argument the router forwards.
    """

    from app.control_plane import router as router_module

    forwarded: list[dict] = []

    class _SpyService:
        def run_once(self, **kwargs):
            forwarded.append(kwargs)
            return {"status": "completed", "steps": []}

    monkeypatch.setattr(router_module, "ControlPlaneService", lambda: _SpyService())

    assert client.post("/api/control-plane/run-once", json={"limit": 5}).status_code == 200
    assert forwarded[-1]["run_kind"] == "manual"

    # An empty body must behave the same as an omitted field.
    assert client.post("/api/control-plane/run-once").status_code == 200
    assert forwarded[-1]["run_kind"] == "manual"

    # And the scheduler's explicit request is forwarded unchanged.
    assert (
        client.post(
            "/api/control-plane/run-once", json={"limit": 5, "run_kind": "scheduled"}
        ).status_code
        == 200
    )
    assert forwarded[-1]["run_kind"] == "scheduled"


def test_a_direct_snapshot_call_without_run_kind_writes_nothing(test_db):
    """The internal method must fail closed too, not just the public entry.

    _run_decision_snapshot is reachable from inside the service and from tests,
    so a "scheduled" default here would let an unstated caller mint the day's
    official snapshot even though every outer layer defaults to preview.
    """

    service = _service(test_db, market_status="fresh")
    with test_db.connect() as conn:
        before_rows = int(
            conn.execute("SELECT COUNT(*) FROM forecast_decisions").fetchone()[0]
        )

    result = service._run_decision_snapshot(
        limit=5, now=datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI)
    )

    assert result["forecast_ledger"]["status"] == "preview_not_recorded"
    assert result["forecast_ledger"]["run_kind"] == "manual"
    assert result["forecast_ledger"]["recorded_count"] == 0
    with test_db.connect() as conn:
        assert int(conn.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0]) == 0
        assert (
            int(conn.execute("SELECT COUNT(*) FROM forecast_decisions").fetchone()[0])
            == before_rows
        )


class _ManyCandidates:
    """A selection wide enough that the periodic ownership recheck can fire.

    The recheck runs every OWNERSHIP_RECHECK_EVERY candidates, so a one-candidate
    fixture can never reach it.
    """

    def __init__(self, count: int = 15) -> None:
        self._count = count

    def run(self, **_: object) -> dict:
        return {
            "status": "completed",
            "schema_version": "strategy_selection_v2.1",
            "date": "2026-07-10",
            "config_version": "pytest-v1",
            "summary": {"candidate_count": self._count},
            "daily_candidate_snapshot": [
                {
                    "symbol": f"SZ{index:06d}",
                    "name": "fixture",
                    "plan_type": "WATCH_ONLY_PLAN",
                    "final_score": 65,
                    "risk_flags": [],
                }
                for index in range(1, self._count + 1)
            ],
            "data_gap_candidates": [],
        }


def _service_with_selection(test_db, selection):
    return ControlPlaneService(
        store=test_db,
        public_opinion_factory=lambda: _Pulse("completed"),
        feedback_factory=_Feedback,
        forecast_feedback_factory=_ForecastFeedback,
        selection_factory=lambda: selection,
        agent_control_factory=_AgentControl,
        market_data_factory=lambda _now, _limit: {
            "status": "fresh",
            "latest_trade_date": "2026-07-10",
            "decision_allowed": True,
        },
        market_data_refresh_factory=lambda _: {"processed": 0, "results": []},
        clock=lambda: datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI),
    )


def _steal_claim_after(test_db, monkeypatch, *, after_writes: int, thief: str):
    """Let another writer take the vintage partway through this run's writing.

    Simulates writer B winning the vintage - after A's lease expired - while A is
    still inserting rows. The takeover is a real UPDATE of the claim row, which
    is exactly what B's own claim would have done.
    """

    from app.control_plane import service as service_module

    state = {"writes": 0}
    real_ledger = service_module.ForecastLedger

    class _StealingLedger(real_ledger):
        def record_forecast(self, forecast):
            result = super().record_forecast(forecast)
            state["writes"] += 1
            if state["writes"] == after_writes:
                with test_db.connect() as conn:
                    conn.execute(
                        "UPDATE forecast_decision_days SET decision_id = ? "
                        "WHERE scope = 'stock' AND data_version = '2026-07-10'",
                        (thief,),
                    )
            return result

    monkeypatch.setattr(service_module, "ForecastLedger", _StealingLedger)
    return state


def test_a_writer_that_loses_the_vintage_mid_write_stops_and_reports_ownership_lost(
    test_db, monkeypatch
):
    """Writer B takes the vintage while A is still inserting rows.

    A must notice at its next periodic recheck, stop writing, and report
    ownership_lost with the rows it had already written - not finalize on top of
    B's claim, which would put two snapshots on one vintage.
    """

    service = _service_with_selection(test_db, _ManyCandidates(15))
    # Ten candidates x five horizons: the takeover lands just before the
    # recheck at candidate 11.
    _steal_claim_after(test_db, monkeypatch, after_writes=50, thief="decision-B")

    result = service._run_decision_snapshot(
        limit=20, now=datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI), run_kind="scheduled"
    )

    ledger = result["forecast_ledger"]
    assert ledger["status"] == "ownership_lost"
    assert ledger["reason"] == "decision_day_reclaimed_by_another_writer:2026-07-10"
    assert ledger["recorded_count"] == 0
    # It stopped at the recheck rather than writing all 15 candidates.
    assert ledger["orphaned_row_count"] == 50
    assert ledger["candidate_count"] == 15

    # B still owns the vintage, and A did not publish over it.
    with test_db.connect() as conn:
        row = conn.execute(
            "SELECT decision_id, recorded_count FROM forecast_decision_days "
            "WHERE scope = 'stock' AND data_version = '2026-07-10'"
        ).fetchone()
    assert row["decision_id"] == "decision-B"
    assert int(row["recorded_count"]) == 0


def test_a_writer_that_loses_the_vintage_before_finalize_reports_ownership_lost(
    test_db, monkeypatch
):
    """The same race, but the takeover lands after the last row is written.

    No periodic recheck fires for a small snapshot, so the fenced UPDATE in
    _finalize_decision_day is the only thing standing between A and publishing
    over B's claim.
    """

    service = _service_with_selection(test_db, _Selection())
    # One candidate x five horizons: steal on the final write.
    _steal_claim_after(test_db, monkeypatch, after_writes=5, thief="decision-B")

    result = service._run_decision_snapshot(
        limit=5, now=datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI), run_kind="scheduled"
    )

    ledger = result["forecast_ledger"]
    assert ledger["status"] == "ownership_lost"
    assert ledger["recorded_count"] == 0
    assert ledger["orphaned_row_count"] == 5

    with test_db.connect() as conn:
        row = conn.execute(
            "SELECT decision_id, recorded_count FROM forecast_decision_days "
            "WHERE scope = 'stock' AND data_version = '2026-07-10'"
        ).fetchone()
    assert row["decision_id"] == "decision-B"
    assert int(row["recorded_count"]) == 0


def test_a_lost_vintage_is_visible_in_the_decision_step_not_only_the_ledger(
    test_db, monkeypatch
):
    """The operator reads the step status, not the nested ledger payload.

    The selection reports "completed" whenever it produced a list, so taking the
    step status from it alone made a run that published nothing look identical
    to one that published. The step must be the worse of the two.
    """

    service = _service_with_selection(test_db, _Selection())
    _steal_claim_after(test_db, monkeypatch, after_writes=5, thief="decision-B")

    payload = service._run_decision_step(
        limit=5, now=datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI), run_kind="scheduled"
    )

    assert payload["result"]["forecast_ledger"]["status"] == "ownership_lost"
    assert payload["step"]["status"] == "partial"
    # And the whole cycle degrades with it.
    assert ControlPlaneService._rollup_status([payload["step"]]) == "partial"


def test_an_idempotent_repeat_does_not_degrade_the_cycle(test_db):
    """The guard working as designed must not read as a degraded run.

    Roughly 95 of 96 daily cycles hit an already-claimed vintage. Reporting that
    as partial trains an operator to ignore the one cycle that matters.
    """

    service = _service_with_selection(test_db, _Selection())
    now = datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI)

    first = service._run_decision_step(limit=5, now=now, run_kind="scheduled")
    assert first["result"]["forecast_ledger"]["status"] == "recorded"
    assert first["step"]["status"] == "completed"

    second = service._run_decision_step(limit=5, now=now, run_kind="scheduled")
    assert second["result"]["forecast_ledger"]["status"] == "already_recorded"
    assert second["step"]["status"] == "completed"
    assert ControlPlaneService._rollup_status([second["step"]]) == "completed"


def test_a_preview_run_is_a_clean_completion_not_a_partial(test_db):
    """A manual run was asked not to write, and did not. That is success."""

    service = _service_with_selection(test_db, _Selection())

    payload = service._run_decision_step(
        limit=5, now=datetime(2026, 7, 10, 17, 0, tzinfo=SHANGHAI), run_kind="manual"
    )

    ledger = payload["result"]["forecast_ledger"]
    assert ledger["status"] == "preview_not_recorded"
    assert ledger["recorded_count"] == 0
    assert payload["step"]["status"] == "completed"

    # Nothing was claimed, so the scheduled run can still take the vintage.
    with test_db.connect() as conn:
        claims = conn.execute(
            "SELECT COUNT(*) FROM forecast_decision_days WHERE data_version = '2026-07-10'"
        ).fetchone()[0]
    assert claims == 0
