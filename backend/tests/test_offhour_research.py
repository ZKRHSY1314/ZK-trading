import json
from pathlib import Path

import pytest

from app.research import offhour
from app.research.offhour import OffhourResearchLoopService


class FakePotentialSearch:
    def __init__(self, symbols=None):
        self.symbols = symbols or ["SH600000"]

    def run(self, limit=100, persist=True):
        return {
            "run_id": 7,
            "status": "completed",
            "total_scanned": len(self.symbols),
            "stored_count": len(self.symbols),
            "scored_count": len(self.symbols),
            "top_scored_symbols": self.symbols,
            "top_scored_items": [
                {"symbol": symbol, "name": f"Fixture {idx}", "potential_score": 80 - idx}
                for idx, symbol in enumerate(self.symbols)
            ],
            "errors": [],
        }


@pytest.fixture
def clean_store(test_db):
    with test_db.connect() as conn:
        for table in [
            "offhour_research_runs",
            "historical_backtest_trades",
            "historical_backtest_closed_trades",
            "historical_backtest_daily_equity",
            "historical_backtest_runs",
            "daily_bar_cache",
        ]:
            conn.execute(f"DELETE FROM {table}")
    return test_db


def write_dataset2_source(tmp_path: Path, mode="simulation_and_training_only", allow_live_order=False) -> Path:
    source_dir = (
        tmp_path
        / "\u6570\u636e\u96c62"
        / "a_share_trading_training_pack_v2"
        / "a_share_trading_training_pack_v2"
    )
    strategies_dir = source_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    strategy_set = {
        "mode": mode,
        "rules": [
            {
                "pattern_id": "TEST_BIG_YANG_001",
                "name": "big yang high volume",
                "category": "fixture_volume_price",
                "timeframe": "daily",
                "conditions": {
                    "software_tags": [
                        "single_candle",
                        "big_yang",
                        "high_volume",
                        "price_volume_rise",
                    ]
                },
                "outputs": {
                    "expected_bias": "bullish",
                    "action_label": "SIM_BUY_CANDIDATE",
                    "risk_level": "medium",
                    "confidence": "medium",
                    "allow_live_order": allow_live_order,
                },
            }
        ],
    }
    risk_controls = {
        "version": "fixture",
        "action_label_map": {"SIM_BUY_CANDIDATE": "simulation only"},
    }
    (strategies_dir / "strategy_set.json").write_text(
        json.dumps(strategy_set, ensure_ascii=False),
        encoding="utf-8",
    )
    (strategies_dir / "risk_controls.json").write_text(
        json.dumps(risk_controls, ensure_ascii=False),
        encoding="utf-8",
    )
    return source_dir


def insert_bar(store, symbol, trade_date, open_, high, low, close, volume=1000, amount=1000000):
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, trade_date, open_, high, low, close, volume, amount, "fixture", "ready"),
        )


def seed_signal_history(store):
    bars = [
        ("2026-05-01", 10.0, 10.1, 9.9, 10.0, 1000, 10_000_000),
        ("2026-05-02", 10.0, 10.2, 9.9, 10.1, 1000, 10_100_000),
        ("2026-05-03", 10.0, 11.2, 9.9, 11.0, 4000, 220_000_000),
        ("2026-05-04", 11.0, 11.8, 10.8, 11.6, 2500, 180_000_000),
        ("2026-05-05", 11.5, 12.0, 11.3, 11.8, 2300, 170_000_000),
    ]
    for date, open_, high, low, close, volume, amount in bars:
        insert_bar(store, "SH600000", date, open_, high, low, close, volume=volume, amount=amount)
        insert_bar(store, "SH000300", date, 100, 101, 99, 100 + len(date), volume=10000, amount=300_000_000)


def test_offhour_research_reads_dataset2_chinese_path_and_writes_candidate_artifact(
    clean_store, tmp_path, monkeypatch
):
    source_dir = write_dataset2_source(tmp_path)
    seed_signal_history(clean_store)
    monkeypatch.setattr(offhour, "OffhourPotentialSearchService", lambda: FakePotentialSearch())

    service = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    result = service.run(limit=10, strategy_limit=5, history_days=60, write_artifact=True)

    assert result["status"] == "completed"
    assert result["dataset2_source"]["rule_count"] == 1
    assert result["strategy_replay"]["signal_count"] >= 1
    assert result["sandbox"]["evaluated_count"] >= 1
    assert result["model_candidate"]["artifact_written"] is True
    assert Path(result["model_candidate"]["artifact_path"]).exists()
    assert result["live_trading_enabled"] is False

    latest = service.latest_run()
    assert latest is not None
    assert latest["run_id"] == result["run_id"]


def test_offhour_research_blocks_unsafe_dataset2_strategy_source(clean_store, tmp_path, monkeypatch):
    source_dir = write_dataset2_source(tmp_path, mode="simulation_and_training_only", allow_live_order=True)
    monkeypatch.setattr(offhour, "OffhourPotentialSearchService", lambda: FakePotentialSearch())

    result = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    ).run(limit=10)

    assert result["status"] == "blocked"
    assert any("unsafe strategy outputs" in reason for reason in result["blocked_reasons"])
    assert result["model_candidate"]["artifact_written"] is False


def test_offhour_research_does_not_fabricate_signals_without_daily_history(
    clean_store, tmp_path, monkeypatch
):
    source_dir = write_dataset2_source(tmp_path)
    monkeypatch.setattr(offhour, "OffhourPotentialSearchService", lambda: FakePotentialSearch(["SH600001"]))

    result = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    ).run(limit=10, strategy_limit=5, history_days=60, write_artifact=True)

    assert result["status"] == "blocked"
    assert result["daily_bar_coverage"]["status"] == "insufficient_history_data"
    assert result["strategy_replay"]["signal_count"] == 0
    assert result["model_candidate"]["artifact_written"] is False


def test_offhour_research_api_smoke(client, monkeypatch):
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "run",
        lambda self, **kwargs: {
            "run_id": 99,
            "status": "completed",
            "strategy_replay": {"signal_count": 1},
            "sandbox": {"evaluated_count": 1},
            "model_candidate": {"artifact_written": False, "status": "skipped"},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    )
    response = client.get("/api/research/offhour/capabilities")
    assert response.status_code == 200
    assert response.json()["simulation_only"] is True

    response = client.post("/api/research/offhour/run", json={"limit": 10, "strategy_limit": 5})
    assert response.status_code == 200
    assert response.json()["run_id"] == 99

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["live_trading_enabled"] is False
