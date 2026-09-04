from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from app.api import public_opinion_routes
from app.market_regime.service import MarketRegimeService
from app.market_intelligence.models import EventFact
from app.market_intelligence.service import MarketIntelligenceService
from app.public_opinion.service import CodexPublicOpinionService, SECTOR_TAXONOMY
from app.storage.sqlite_store import SQLiteStore


def _reset_global_market_bars(store):
    with store.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS global_market_bars(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                bar_time TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL NOT NULL,
                volume REAL,
                source TEXT NOT NULL,
                available_at TEXT NOT NULL,
                quality_status TEXT NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM global_market_bars")


def test_event_fact_is_auditable_and_available_only_after_retrieval():
    fact = EventFact.from_evidence(
        {
            "event_id": "evt-ai-listing",
            "cluster_id": "cluster-ai-listing",
            "type": "listing",
            "entities": ["MiniMax"],
            "geography": ["HK", "CN"],
            "status": "new",
            "direction": "positive",
            "magnitude": 0.8,
            "published_at": "2026-01-02T09:00:00+08:00",
            "first_seen_at": "2026-01-02T09:05:00+08:00",
            "retrieved_at": "2026-01-02T09:10:00+08:00",
            "available_at": "2026-01-02T09:05:00+08:00",
            "revision": 1,
            "source_tier": "primary_media",
            "evidence_urls": ["https://example.com/minimax-listing"],
            "title": "MiniMax lists in Hong Kong",
            "summary": "The issuer starts trading in Hong Kong.",
        }
    ).to_dict()

    assert set(fact) == {
        "event_id",
        "cluster_id",
        "type",
        "entities",
        "geography",
        "status",
        "direction",
        "magnitude",
        "published_at",
        "first_seen_at",
        "retrieved_at",
        "available_at",
        "revision",
        "source_tier",
        "evidence_urls",
        "raw_hash",
    }
    assert fact["available_at"] == "2026-01-02T01:10:00+00:00"
    assert len(fact["raw_hash"]) == 64
    assert fact["event_id"] == "evt-ai-listing"


def test_cross_market_features_exclude_bars_not_available_at_as_of(test_db):
    _reset_global_market_bars(test_db)
    with test_db.connect() as conn:
        conn.executemany(
            """
            INSERT INTO global_market_bars(
                symbol, asset_class, bar_time, open, high, low, close, volume,
                source, available_at, quality_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "SOX",
                    "equity_index",
                    "2026-01-01T21:00:00+00:00",
                    100,
                    101,
                    99,
                    100,
                    1_000,
                    "fixture",
                    "2026-01-01T21:01:00+00:00",
                    "ready",
                ),
                (
                    "SOX",
                    "equity_index",
                    "2026-01-02T21:00:00+00:00",
                    101,
                    104,
                    100,
                    103,
                    1_100,
                    "fixture",
                    "2026-01-02T21:01:00+00:00",
                    "ready",
                ),
                (
                    "SOX",
                    "equity_index",
                    "2026-01-03T21:00:00+00:00",
                    103,
                    121,
                    102,
                    120,
                    1_500,
                    "fixture",
                    "2026-01-03T21:01:00+00:00",
                    "ready",
                ),
            ],
        )

    result = MarketRegimeService(store=test_db).get_cross_market_features(
        "2026-01-02T23:00:00+00:00"
    )

    assert result["status"] == "ready"
    assert result["as_of"] == "2026-01-02T23:00:00+00:00"
    assert result["features"] == [
        {
            "symbol": "SOX",
            "asset_class": "equity_index",
            "bar_time": "2026-01-02T21:00:00+00:00",
            "available_at": "2026-01-02T21:01:00+00:00",
            "close": 103.0,
            "return_1d": 0.03,
            "return_5d": None,
            "bar_count": 2,
            "source": "fixture",
        }
    ]


def test_cross_market_features_deduplicate_sources_per_market_period(test_db):
    _reset_global_market_bars(test_db)
    with test_db.connect() as conn:
        conn.executemany(
            """
            INSERT INTO global_market_bars(
                symbol, asset_class, bar_time, close, source, available_at, quality_status
            ) VALUES (?, 'commodity', ?, ?, ?, ?, 'ready')
            """,
            [
                ("GOLD", "2026-01-01T21:00:00+00:00", 100, "source-a", "2026-01-01T21:01:00+00:00"),
                ("GOLD", "2026-01-01T21:00:00+00:00", 101, "source-b", "2026-01-01T21:02:00+00:00"),
                ("GOLD", "2026-01-02T21:00:00+00:00", 103, "source-a", "2026-01-02T21:01:00+00:00"),
            ],
        )

    result = MarketRegimeService(store=test_db).get_cross_market_features(
        "2026-01-02T23:00:00+00:00"
    )

    feature = result["features"][0]
    assert feature["bar_count"] == 2
    assert feature["return_1d"] == pytest.approx(103 / 101 - 1)


def test_sector_thesis_counts_one_independent_event_cluster_once(test_db):
    now = "2026-01-02T10:00:00+00:00"
    base = {
        "cluster_id": "cluster-chip-policy",
        "type": "policy",
        "entities": ["semiconductors"],
        "geography": ["CN"],
        "status": "new",
        "direction": "positive",
        "magnitude": 0.6,
        "published_at": now,
        "first_seen_at": now,
        "retrieved_at": now,
        "available_at": now,
        "revision": 1,
        "source_tier": "primary_media",
        "sector_hints": ["semiconductors"],
    }
    single = MarketIntelligenceService(store=test_db).build_snapshot(
        [{**base, "event_id": "evt-chip-a", "evidence_urls": ["https://a.example"]}],
        as_of=now,
    )
    duplicated = MarketIntelligenceService(store=test_db).build_snapshot(
        [
            {**base, "event_id": "evt-chip-a", "evidence_urls": ["https://a.example"]},
            {**base, "event_id": "evt-chip-b", "evidence_urls": ["https://b.example"]},
        ],
        as_of=now,
    )

    assert duplicated["sector_theses"][0]["confidence"] == single["sector_theses"][0]["confidence"]
    assert duplicated["sector_theses"][0]["event_ids"] == ["evt-chip-a"]
    assert (
        "1 independent point-in-time event cluster"
        in duplicated["sector_theses"][0]["rationale"][0]
    )


def test_event_and_cross_market_context_produce_review_only_sector_thesis(test_db):
    _reset_global_market_bars(test_db)
    with test_db.connect() as conn:
        conn.executemany(
            """
            INSERT INTO global_market_bars(
                symbol, asset_class, bar_time, open, high, low, close, volume,
                source, available_at, quality_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "SOX",
                    "equity_index",
                    "2026-01-01T21:00:00+00:00",
                    100,
                    101,
                    99,
                    100,
                    1_000,
                    "fixture",
                    "2026-01-01T21:01:00+00:00",
                    "ready",
                ),
                (
                    "SOX",
                    "equity_index",
                    "2026-01-02T21:00:00+00:00",
                    101,
                    104,
                    100,
                    103,
                    1_100,
                    "fixture",
                    "2026-01-02T21:01:00+00:00",
                    "ready",
                ),
            ],
        )

    snapshot = MarketIntelligenceService(store=test_db).build_snapshot(
        [
            {
                "event_id": "evt-sox-rally",
                "cluster_id": "cluster-us-ai-hardware",
                "type": "cross_market_move",
                "entities": ["Philadelphia Semiconductor Index"],
                "geography": ["US", "CN"],
                "status": "new",
                "direction": "positive",
                "magnitude": 0.7,
                "published_at": "2026-01-02T21:02:00+00:00",
                "first_seen_at": "2026-01-02T21:03:00+00:00",
                "retrieved_at": "2026-01-02T21:04:00+00:00",
                "available_at": "2026-01-02T21:04:00+00:00",
                "revision": 1,
                "source_tier": "primary_media",
                "evidence_urls": ["https://example.com/sox-rally"],
                "title": "US AI hardware and chip shares extend gains",
                "summary": "The SOX index closes higher for a second session.",
                "sector_hints": ["semiconductors"],
            }
        ],
        as_of="2026-01-02T23:00:00+00:00",
    )

    assert snapshot["status"] == "ready"
    assert snapshot["cross_market_context"]["features"][0]["close"] == 103.0
    thesis = snapshot["sector_theses"][0]
    assert thesis["sector"] == "semiconductors"
    assert thesis["direction"] == "positive"
    assert thesis["horizon"] == "1-4w"
    assert thesis["decay"]
    assert thesis["invalidation"]
    assert thesis["industry_chain_edges"]
    assert thesis["confidence"] > 0.5
    assert thesis["event_ids"] == ["evt-sox-rally"]
    assert thesis["review_only"] is True
    assert thesis["auto_trade_allowed"] is False
    assert "buy" not in str(snapshot).lower()
    assert "sell" not in str(snapshot).lower()


def test_public_opinion_ingest_derives_event_fact_and_oil_sector_thesis(test_db):
    now = datetime.now(timezone.utc).isoformat()
    result = CodexPublicOpinionService(store=test_db, sources=[]).ingest_evidence(
        [
            {
                "event_id": "evt-hormuz-disruption",
                "cluster_id": "cluster-hormuz-disruption",
                "type": "supply_disruption",
                "entities": ["Strait of Hormuz", "Brent crude"],
                "geography": ["Middle East", "CN"],
                "status": "ongoing",
                "direction": "positive",
                "magnitude": 0.9,
                "published_at": now,
                "published_at_status": "known",
                "first_seen_at": now,
                "retrieved_at": now,
                "available_at": now,
                "revision": 1,
                "source_tier": "primary_media",
                "evidence_urls": ["https://example.com/hormuz"],
                "url": "https://example.com/hormuz",
                "source_name": "Fixture News",
                "source_id": "fixture_news",
                "category": "sector",
                "title": "霍尔木兹航运受阻推动布伦特原油上涨",
                "summary": "供应中断风险推高国际油价。",
                "sector_hints": ["oil_gas"],
                "claims": ["航运受阻", "原油价格上涨"],
            }
        ],
        persist=True,
        requested_by="pytest_market_intelligence",
    )

    assert {
        "semiconductors",
        "oil_gas",
        "gold",
        "crypto",
        "rates_fx",
        "shipping",
    } <= set(SECTOR_TAXONOMY)
    assert result["items"][0]["event_fact"]["event_id"] == "evt-hormuz-disruption"
    assert result["event_facts"][0]["raw_hash"]
    thesis = next(row for row in result["sector_theses"] if row["sector"] == "oil_gas")
    assert thesis["direction"] == "positive"
    assert thesis["invalidation"]
    assert thesis["auto_trade_allowed"] is False
    assert result["forecast_ledger"]["recorded_count"] == (
        5 * result["forecast_ledger"]["sector_count"]
    )
    rows = test_db.fetch_all(
        """
        SELECT scope, subject, horizon_days, probability, features_json
        FROM forecast_decisions
        WHERE decision_id = ? AND subject = 'oil_gas'
        """,
        (result["forecast_ledger"]["decision_id"],),
    )
    assert {row["scope"] for row in rows} == {"sector"}
    assert {row["subject"] for row in rows} == {"oil_gas"}
    assert {row["horizon_days"] for row in rows} == {1, 3, 5, 10, 20}
    for row in rows:
        features = json.loads(row["features_json"])
        assert row["probability"] == pytest.approx(thesis["confidence"])
        assert features["probability_semantics"] == "directional_thesis_success"
        assert features["probability_horizon_days"] == row["horizon_days"]


def test_negative_sector_thesis_probability_means_probability_of_directional_success(test_db):
    now = datetime.now(timezone.utc).isoformat()
    result = CodexPublicOpinionService(store=test_db, sources=[]).ingest_evidence(
        [
            {
                "event_id": "evt-oil-demand-shock",
                "cluster_id": "cluster-oil-demand-shock",
                "type": "demand_contraction",
                "entities": ["Brent crude"],
                "geography": ["Global", "CN"],
                "status": "ongoing",
                "direction": "negative",
                "magnitude": 0.8,
                "published_at": now,
                "published_at_status": "known",
                "first_seen_at": now,
                "retrieved_at": now,
                "available_at": now,
                "revision": 1,
                "source_tier": "primary_media",
                "evidence_urls": ["https://example.com/oil-demand"],
                "url": "https://example.com/oil-demand",
                "source_name": "Fixture News",
                "source_id": "fixture_news_negative",
                "category": "sector",
                "title": "Demand contraction weighs on crude oil",
                "summary": "A demand shock is negative for oil producers.",
                "sector_hints": ["oil_gas"],
                "claims": ["demand contraction", "oil price pressure"],
            }
        ],
        persist=True,
        requested_by="pytest_market_intelligence_negative",
    )

    thesis = next(row for row in result["sector_theses"] if row["sector"] == "oil_gas")
    assert thesis["direction"] == "negative"
    row = test_db.fetch_one(
        """
        SELECT probability, features_json
        FROM forecast_decisions
        WHERE decision_id = ? AND subject = 'oil_gas' AND horizon_days = 5
        """,
        (result["forecast_ledger"]["decision_id"],),
    )
    features = json.loads(row["features_json"])
    assert row["probability"] == pytest.approx(thesis["confidence"])
    assert features["direction"] == "negative"
    assert features["probability_semantics"] == "directional_thesis_success"
    assert features["probability_horizon_days"] == 5


def test_codex_schema_and_api_preserve_structured_event_fact(client, monkeypatch):
    schema_path = Path(__file__).resolve().parents[1] / "configs" / "codex_market_pulse.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    item_schema = schema["properties"]["evidence"]["items"]
    event_fields = {
        "event_id",
        "cluster_id",
        "type",
        "entities",
        "geography",
        "status",
        "direction",
        "magnitude",
        "published_at",
        "first_seen_at",
        "retrieved_at",
        "available_at",
        "revision",
        "source_tier",
        "evidence_urls",
        "raw_hash",
    }
    assert event_fields <= set(item_schema["required"])

    captured = {}

    class FakeService:
        def __init__(self, store=None):
            self.store = store

        def ingest_evidence(self, evidence, *, persist, requested_by):
            captured["evidence"] = evidence
            return {
                "status": "completed",
                "event_facts": evidence,
                "review_only": True,
                "live_trading_enabled": False,
            }

    monkeypatch.setattr(public_opinion_routes, "CodexPublicOpinionService", FakeService)
    response = client.post(
        "/api/public-opinion/evidence/ingest",
        json={
            "persist": False,
            "requested_by": "pytest_event_contract",
            "evidence": [
                {
                    "event_id": "evt-1",
                    "cluster_id": "cluster-1",
                    "type": "listing",
                    "entities": ["MiniMax"],
                    "geography": ["HK", "CN"],
                    "status": "new",
                    "direction": "positive",
                    "magnitude": 0.8,
                    "published_at": "2026-01-02T09:00:00+08:00",
                    "published_at_status": "known",
                    "first_seen_at": "2026-01-02T09:05:00+08:00",
                    "retrieved_at": "2026-01-02T09:10:00+08:00",
                    "available_at": "2026-01-02T09:10:00+08:00",
                    "revision": 1,
                    "source_tier": "primary_media",
                    "evidence_urls": ["https://example.com/listing"],
                    "raw_hash": "a" * 64,
                    "url": "https://example.com/listing",
                    "title": "MiniMax Hong Kong listing event",
                    "summary": "The company starts trading in Hong Kong.",
                    "source_name": "Fixture",
                    "source_id": "fixture",
                    "category": "sector",
                    "sector_hints": ["ai_compute"],
                    "claims": ["listing date announced"],
                }
            ],
        },
    )

    assert response.status_code == 200
    passed = captured["evidence"][0]
    assert passed["event_id"] == "evt-1"
    assert passed["type"] == "listing"
    assert passed["entities"] == ["MiniMax"]
    assert passed["raw_hash"] == "a" * 64


def test_empty_global_market_table_degrades_with_explicit_data_contract(tmp_path):
    store = SQLiteStore(tmp_path / "market-intelligence.sqlite3")
    result = MarketRegimeService(store=store).get_cross_market_features("2026-01-02T23:00:00+00:00")

    assert result["status"] == "insufficient_data"
    assert result["reason"] == "no_global_market_bars_at_as_of"
    assert result["features"] == []
    assert result["required_table"]["table"] == "global_market_bars"
    assert {"symbol", "bar_time", "close", "available_at", "quality_status"} <= set(
        result["required_table"]["required_columns"]
    )


def test_sector_thesis_never_uses_event_retrieved_after_cutoff(tmp_path):
    store = SQLiteStore(tmp_path / "future-event.sqlite3")
    snapshot = MarketIntelligenceService(store=store).build_snapshot(
        [
            {
                "event_id": "evt-future-policy",
                "cluster_id": "cluster-future-policy",
                "type": "policy",
                "entities": ["Semiconductor industry"],
                "geography": ["CN"],
                "status": "new",
                "direction": "positive",
                "magnitude": 0.9,
                "published_at": "2026-01-03T01:00:00+00:00",
                "first_seen_at": "2026-01-03T01:01:00+00:00",
                "retrieved_at": "2026-01-03T01:02:00+00:00",
                "available_at": "2026-01-03T01:02:00+00:00",
                "revision": 1,
                "source_tier": "official",
                "evidence_urls": ["https://example.com/future-policy"],
                "title": "Semiconductor policy",
                "summary": "A policy published after the evaluation cutoff.",
                "sector_hints": ["semiconductors"],
            }
        ],
        as_of="2026-01-02T23:00:00+00:00",
    )

    assert snapshot["status"] == "insufficient_data"
    assert snapshot["event_facts"] == []
    assert snapshot["sector_theses"] == []
    assert snapshot["rejected"] == [{"index": "0", "reason": "not_available_at_as_of"}]
