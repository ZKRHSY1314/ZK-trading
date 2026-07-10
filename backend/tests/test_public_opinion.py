from __future__ import annotations

from app.api import routes
from app.public_opinion.service import CodexPublicOpinionService, PublicOpinionSource


def _reset(store) -> None:
    with store.connect() as conn:
        for table in [
            "public_opinion_items",
            "public_opinion_sector_signals",
            "public_opinion_runs",
        ]:
            conn.execute(f"DELETE FROM {table}")


def test_public_opinion_capture_scores_and_persists_sector_signals(test_db, monkeypatch):
    _reset(test_db)
    service = CodexPublicOpinionService(
        store=test_db,
        sources=[
            PublicOpinionSource(
                id="fixture_rss",
                name="Fixture RSS",
                url="https://example.test/rss.xml",
                category="policy",
                parser="rss",
            )
        ],
    )
    feed = """
    <rss><channel>
      <item>
        <title>国务院政策支持AI芯片算力数据中心建设</title>
        <link>https://example.test/a</link>
        <description>人工智能和半导体板块迎来政策支持</description>
      </item>
      <item>
        <title>低空经济无人机产业方案发布</title>
        <link>https://example.test/b</link>
      </item>
      <item>
        <title>某板块监管风险提示</title>
        <link>https://example.test/c</link>
      </item>
    </channel></rss>
    """.encode("utf-8")
    monkeypatch.setattr(service, "_fetch_source", lambda source: feed)

    result = service.run(limit=10, persist=True, requested_by="test")

    assert result["status"] == "completed"
    assert result["review_only"] is True
    assert result["simulation_only"] is True
    assert result["live_trading_enabled"] is False
    assert result["run_id"] is not None
    assert result["sector_signals"]
    sectors = {item["sector"]: item for item in result["sector_signals"]}
    assert "ai_compute" in sectors
    assert sectors["ai_compute"]["heat_score"] > 0
    assert sectors["ai_compute"]["suggested_action"] in {
        "sector_watch_review_only",
        "continue_monitoring_review_only",
        "single_item_watch_review_only",
    }

    persisted = test_db.fetch_one(
        "SELECT item_count, sector_count, review_only, simulation_only, live_trading_enabled "
        "FROM public_opinion_runs WHERE id = ?",
        (result["run_id"],),
    )
    assert persisted["item_count"] == result["item_count"]
    assert persisted["sector_count"] == result["sector_count"]
    assert persisted["review_only"] == 1
    assert persisted["simulation_only"] == 1
    assert persisted["live_trading_enabled"] == 0

    context = service.latest_context(limit=3)
    assert context["top_sectors"][0]["sector"] in sectors


def test_public_opinion_api_smoke(client, monkeypatch):
    class FakePublicOpinionService:
        def capabilities(self):
            return {"status": "ok", "safety": {"allow_live_order": False}}

        def run(self, *, limit, persist, requested_by, source_urls):
            return {
                "status": "completed",
                "limit": limit,
                "persist": persist,
                "requested_by": requested_by,
                "source_urls": source_urls,
                "item_count": 1,
                "sector_count": 1,
                "sector_signals": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }

        def latest_context(self, limit=8):
            return {"status": "completed", "top_sectors": [], "limit": limit}

        def latest_run(self):
            return None

        def list_runs(self, limit=20):
            return []

    monkeypatch.setattr(routes, "CodexPublicOpinionService", FakePublicOpinionService)

    capabilities = client.get("/api/public-opinion/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["safety"]["allow_live_order"] is False

    response = client.post(
        "/api/public-opinion/run",
        json={
            "limit": 5,
            "persist": True,
            "requested_by": "pytest",
            "source_urls": ["https://example.test/news"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["review_only"] is True
    assert payload["simulation_only"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["source_urls"] == ["https://example.test/news"]


def test_public_opinion_run_blocks_when_live_trading_enabled(test_db, monkeypatch):
    _reset(test_db)
    from app.config import settings

    old_value = settings.enable_live_trading
    settings.enable_live_trading = True
    try:
        service = CodexPublicOpinionService(
            store=test_db,
            sources=[
                PublicOpinionSource(
                    id="fixture",
                    name="Fixture",
                    url="https://example.test",
                    category="market",
                )
            ],
        )
        monkeypatch.setattr(service, "_fetch_source", lambda source: b"")
        result = service.run(limit=10, persist=True)
    finally:
        settings.enable_live_trading = old_value

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    row = test_db.fetch_one(
        "SELECT status, live_trading_enabled FROM public_opinion_runs WHERE id = ?",
        (result["run_id"],),
    )
    assert row["status"] == "blocked"
    assert row["live_trading_enabled"] == 1
