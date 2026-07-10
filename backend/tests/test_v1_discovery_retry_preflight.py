import importlib.util
import json
from pathlib import Path


def _load_preflight_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "v1_discovery_retry_preflight.py"
    spec = importlib.util.spec_from_file_location("v1_discovery_retry_preflight", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _seed_context(test_db) -> None:
    with test_db.connect() as conn:
        for table in [
            "potential_search_runs",
            "potential_search_items",
            "auto_discovered_candidates",
            "candidate_lifecycle",
            "candidate_lifecycle_events",
            "candidate_scores",
        ]:
            conn.execute(f"DELETE FROM {table}")
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
                10,
                json.dumps(["discovery_failed: Remote end closed connection without response"]),
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, source, reasons_json, components_json, raw_json
            )
            VALUES ('SH600000', 'fixture', 90, 'fixture', '[]', '{}', '{}')
            """
        )


def test_discovery_retry_preflight_success_is_no_write(test_db):
    module = _load_preflight_module()
    _seed_context(test_db)
    calls = {}

    class FakeService:
        def run(self, limit, persist):
            calls["limit"] = limit
            calls["persist"] = persist
            return {
                "run_id": None,
                "status": "completed",
                "source": "fixture",
                "total_scanned": 100,
                "stored_count": 3,
                "scored_count": 1,
                "top_scored_symbols": ["SH600000"],
                "errors": [],
            }

    summary = module.build_preflight(
        limit=50,
        store=test_db,
        service_factory=lambda: FakeService(),
    )

    assert calls == {"limit": 50, "persist": False}
    assert summary["retry_status"] == "retry_succeeded_persist_false"
    assert summary["database_mutated"] is False
    assert summary["latest_run_before"]["status"] == "partial"
    assert summary["latest_run_after"]["status"] == "partial"
    assert summary["next_action"] == "persist_discovery_run_can_replace_partial_status"
    assert summary["downstream_candidate_evidence_available"] is True


def test_discovery_retry_preflight_external_failure_stays_no_write(test_db):
    module = _load_preflight_module()
    _seed_context(test_db)

    class FakeService:
        def run(self, limit, persist):
            return {
                "run_id": None,
                "status": "partial",
                "source": "akshare.stock_zh_a_spot_em",
                "total_scanned": 0,
                "stored_count": 0,
                "scored_count": 1,
                "top_scored_symbols": [],
                "errors": ["discovery_failed: Remote end closed connection without response"],
            }

    summary = module.build_preflight(
        store=test_db,
        service_factory=lambda: FakeService(),
    )

    assert summary["retry_status"] == "external_source_still_failing"
    assert summary["database_mutated"] is False
    assert summary["writes_database"] is False
    assert summary["result"]["errors"] == ["discovery_failed: Remote end closed connection without response"]
    assert summary["next_action"] == "continue_with_downstream_candidates_and_retry_later"


def test_discovery_retry_preflight_persists_only_after_clean_preflight(test_db):
    module = _load_preflight_module()
    _seed_context(test_db)
    calls = []

    class FakeService:
        def run(self, limit, persist):
            calls.append(persist)
            if persist:
                with test_db.connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO potential_search_runs(
                            status, source, total_scanned, stored_count, scored_count,
                            errors_json, summary_json
                        )
                        VALUES ('completed', 'fixture', 100, 3, 1, '[]', '{}')
                        """
                    )
                return {
                    "run_id": 2,
                    "status": "completed",
                    "source": "fixture",
                    "total_scanned": 100,
                    "stored_count": 3,
                    "scored_count": 1,
                    "top_scored_symbols": ["SH600000"],
                    "errors": [],
                }
            return {
                "run_id": None,
                "status": "completed",
                "source": "fixture",
                "total_scanned": 100,
                "stored_count": 3,
                "scored_count": 1,
                "top_scored_symbols": ["SH600000"],
                "errors": [],
            }

    summary = module.build_preflight(
        store=test_db,
        service_factory=lambda: FakeService(),
        persist_review_run=True,
    )

    assert calls == [False, True]
    assert summary["persist_requested"] is True
    assert summary["writes_database"] is True
    assert summary["no_write_database_mutated"] is False
    assert summary["persist_database_mutated"] is True
    assert summary["persist_status"] == "persisted_review_run"
    assert summary["latest_run_after"]["status"] == "completed"
    assert summary["next_action"] == "refresh_v1_stability_expect_discovery_attention_clear"
