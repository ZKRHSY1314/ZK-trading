import json

from app.candidates.offhour_search import OffhourPotentialSearchService


class FailingDiscovery:
    def scan(self, limit=100, persist=True):
        return {
            "status": "failed",
            "source": "akshare.stock_zh_a_spot_em",
            "total_scanned": 0,
            "stored_count": 0,
            "scored_count": 0,
            "items": [],
            "error": "HTTP Error 502: Bad Gateway",
        }


def test_potential_search_falls_back_to_local_candidate_scores(test_db, monkeypatch):
    with test_db.connect() as conn:
        for table in [
            "potential_search_runs",
            "potential_search_items",
            "candidate_scores",
            "candidate_lifecycle",
            "candidate_lifecycle_events",
            "auto_discovered_candidates",
        ]:
            conn.execute(f"DELETE FROM {table}")
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, rating, state, source,
                reasons_json, components_json, raw_json
            )
            VALUES ('SH600000', 'local-candidate', 90, 'review', 'pending_review',
                    'fixture', '["cached score"]', '{}', '{}')
            """
        )

    monkeypatch.setattr("app.candidates.offhour_search.AutoDiscoveryScanner", FailingDiscovery)

    result = OffhourPotentialSearchService().run(limit=5, persist=True)

    assert result["status"] == "partial"
    assert result["fallback_used"] is True
    assert result["source"] == "local_candidate_evidence_fallback"
    assert result["stored_count"] == 1
    assert result["scored_count"] == 1
    assert result["top_scored_symbols"] == ["SH600000"]
    assert any("discovery_failed" in err for err in result["errors"])
    assert any("discovery_local_fallback_used" in err for err in result["errors"])

    run = test_db.fetch_one("SELECT * FROM potential_search_runs WHERE id = ?", (result["run_id"],))
    summary = json.loads(run["summary_json"])
    assert summary["fallback_used"] is True
    item_count = test_db.fetch_one(
        "SELECT COUNT(*) AS c FROM potential_search_items WHERE run_id = ?",
        (result["run_id"],),
    )["c"]
    lifecycle = test_db.fetch_one("SELECT state FROM candidate_lifecycle WHERE symbol = 'SH600000'")
    assert item_count == 1
    assert lifecycle["state"] == "pending_review"
