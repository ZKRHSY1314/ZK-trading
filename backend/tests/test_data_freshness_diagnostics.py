import json

from app.diagnostics.data_freshness import DataFreshnessDiagnosticsService


def _insert_bar(conn, symbol: str, trade_date: str, close: float) -> None:
    conn.execute(
        """
        INSERT INTO daily_bar_cache(
            symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
        )
        VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000, 'fixture', 'ready')
        """,
        (symbol, trade_date, close, close + 0.2, close - 0.2, close),
    )


def test_data_freshness_preflight_is_read_only_and_identifies_stale_candidates(test_db):
    with test_db.connect() as conn:
        for table in ["daily_bar_cache", "candidate_scores", "potential_search_runs"]:
            conn.execute(f"DELETE FROM {table}")
        _insert_bar(conn, "SH600000", "2026-06-20", 10.0)
        _insert_bar(conn, "SH600000", "2026-06-21", 10.1)
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, source, reasons_json, components_json, raw_json
            )
            VALUES ('SH600000', 'fixture', 90, 'fixture', '[]', '{}', '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, source, reasons_json, components_json, raw_json
            )
            VALUES ('SZ002081', 'missing', 80, 'fixture', '[]', '{}', '{}')
            """
        )

    summary = DataFreshnessDiagnosticsService(store=test_db).daily_bar_refresh_preflight(
        max_lag_days=1,
        candidate_limit=10,
    )

    assert summary["status"] == "refresh_recommended"
    assert summary["preflight_writes_database"] is False
    assert summary["refresh_would_write_database"] is True
    assert summary["requires_explicit_cache_mutation"] is True
    assert summary["safe_to_refresh_review_cache"] is True
    assert summary["stale_candidate_count"] == 1
    assert summary["missing_candidate_count"] == 1
    assert summary["sample_stale_candidates"][0]["symbol"] == "SH600000"
    assert summary["sample_missing_candidates"][0]["symbol"] == "SZ002081"


def test_discovery_recovery_keeps_external_failure_separate_from_downstream_evidence(test_db):
    with test_db.connect() as conn:
        for table in ["candidate_scores", "candidate_lifecycle", "auto_discovered_candidates", "potential_search_runs"]:
            conn.execute(f"DELETE FROM {table}")
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, source, reasons_json, components_json, raw_json
            )
            VALUES ('SH600000', 'fixture', 90, 'fixture', '[]', '{}', '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO potential_search_runs(
                status, source, total_scanned, stored_count, scored_count, errors_json, summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "partial",
                "akshare.stock_zh_a_spot_em",
                0,
                0,
                1,
                json.dumps(["discovery_failed: Remote end closed connection without response"]),
                "{}",
            ),
        )

    summary = DataFreshnessDiagnosticsService(store=test_db).discovery_recovery()

    assert summary["status"] == "external_source_failed"
    assert summary["external_error_count"] == 1
    assert summary["candidate_scores_available"] == 1
    assert summary["downstream_candidate_evidence_available"] is True
    assert summary["preflight_writes_database"] is False
    assert summary["recommended_api"] == "POST /api/candidates/potential-search/run?limit=100&persist=false"
