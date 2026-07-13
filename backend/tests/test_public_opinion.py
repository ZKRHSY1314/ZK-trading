from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.api import public_opinion_routes
from app.public_opinion.service import (
    DEFAULT_SOURCES,
    CodexPublicOpinionService,
    PublicOpinionSource,
)


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
    assert all(item["freshness_status"] == "unknown" for item in result["items"])
    assert result["source_stats"]["unknown_time_count"] == result["item_count"]
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

    monkeypatch.setattr(
        public_opinion_routes,
        "CodexPublicOpinionService",
        FakePublicOpinionService,
    )

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

    latest = client.get("/api/public-opinion/runs/latest")
    assert latest.status_code == 200
    assert latest.json() == {
        "status": "empty",
        "items": [],
        "sector_signals": [],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }

    context = client.get("/api/public-opinion/context/latest?limit=3")
    assert context.status_code == 200
    assert context.json() == {"status": "completed", "top_sectors": [], "limit": 3}

    runs = client.get("/api/public-opinion/runs?limit=4")
    assert runs.status_code == 200
    assert runs.json() == []


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


def test_public_opinion_attempts_all_sources_and_allocates_fairly(test_db, monkeypatch):
    _reset(test_db)
    sources = [
        PublicOpinionSource(
            id=f"source_{index}",
            name=f"Source {index}",
            url=f"https://example.com/{index}.xml",
            category="market",
            parser="rss",
        )
        for index in range(4)
    ]
    service = CodexPublicOpinionService(store=test_db, sources=sources)
    today = datetime.now(timezone.utc).date().isoformat()

    def feed(source):
        index = source.id.rsplit("_", 1)[-1]
        return (
            "<rss><channel><item>"
            f"<title>人工智能算力板块来源{index}最新进展</title>"
            f"<link>https://example.com/news/{index}</link>"
            f"<pubDate>{today}</pubDate>"
            "</item></channel></rss>"
        ).encode("utf-8")

    monkeypatch.setattr(service, "_fetch_source", feed)
    result = service.run(limit=4, persist=False)

    assert result["status"] == "completed"
    assert result["source_stats"]["configured_count"] == 4
    assert result["source_stats"]["attempted_count"] == 4
    assert result["source_stats"]["succeeded_count"] == 4
    assert result["source_stats"]["contributing_count"] == 4
    assert {item["source_id"] for item in result["items"]} == {
        "source_0",
        "source_1",
        "source_2",
        "source_3",
    }


def test_public_opinion_filters_stale_and_navigation_items(test_db, monkeypatch):
    _reset(test_db)
    service = CodexPublicOpinionService(
        store=test_db,
        sources=[
            PublicOpinionSource(
                id="fixture",
                name="Fixture",
                url="https://example.com/rss.xml",
                category="market",
                parser="rss",
            )
        ],
    )
    today = datetime.now(timezone.utc).date().isoformat()
    feed = f"""
    <rss><channel>
      <item><title>人工智能算力板块政策支持</title><link>https://example.com/fresh</link><pubDate>{today}</pubDate></item>
      <item><title>新能源储能历史旧闻回顾</title><link>https://example.com/old</link><pubDate>2020-01-01</pubDate></item>
      <item><title>进入行情中心</title><link>https://example.com/nav</link><pubDate>{today}</pubDate></item>
    </channel></rss>
    """.encode("utf-8")
    monkeypatch.setattr(service, "_fetch_source", lambda source: feed)

    result = service.run(limit=10, persist=False)

    assert [item["url"] for item in result["items"]] == ["https://example.com/fresh"]
    assert result["source_stats"]["stale_filtered_count"] == 1


def test_latest_context_marks_expired_run_stale(test_db, monkeypatch):
    _reset(test_db)
    service = CodexPublicOpinionService(
        store=test_db,
        sources=[
            PublicOpinionSource(
                id="fixture",
                name="Fixture",
                url="https://example.com/rss.xml",
                category="policy",
                parser="rss",
            )
        ],
    )
    today = datetime.now(timezone.utc).date().isoformat()
    feed = (
        "<rss><channel><item><title>政策支持人工智能算力建设</title>"
        "<link>https://example.com/fresh</link>"
        f"<pubDate>{today}</pubDate></item></channel></rss>"
    ).encode("utf-8")
    monkeypatch.setattr(service, "_fetch_source", lambda source: feed)
    result = service.run(limit=5, persist=True)
    stale_at = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    with test_db.connect() as conn:
        conn.execute(
            "UPDATE public_opinion_runs SET completed_at = ? WHERE id = ?",
            (stale_at, result["run_id"]),
        )

    context = service.latest_context(limit=5)

    assert context["status"] == "stale"
    assert context["freshness_status"] == "stale"
    assert context["sector_count"] == 0
    assert context["top_sectors"] == []
    assert context["last_known_top_sectors"]


def test_latest_context_keeps_higher_quality_fresh_run_over_newer_partial(test_db, monkeypatch):
    _reset(test_db)
    sources = [
        PublicOpinionSource(
            id=f"source_{index}",
            name=f"Source {index}",
            url=f"https://source-{index}.example.com/news",
            category="market",
            parser="rss",
        )
        for index in (1, 2)
    ]
    service = CodexPublicOpinionService(store=test_db, sources=sources)
    today = datetime.now(timezone.utc).date().isoformat()

    def feed(source):
        return (
            "<rss><channel><item>"
            f"<title>人工智能算力板块来源{source.id}最新进展</title>"
            f"<link>https://{source.id}.example.com/item</link>"
            f"<pubDate>{today}</pubDate>"
            "</item></channel></rss>"
        ).encode("utf-8")

    monkeypatch.setattr(service, "_fetch_source", feed)
    high_quality = service.run(limit=10, persist=True, requested_by="high_quality")
    assert high_quality["status"] == "completed"

    def partial_feed(source):
        if source.id == "source_2":
            raise RuntimeError("fixture_failure")
        return feed(source)

    monkeypatch.setattr(service, "_fetch_source", partial_feed)
    partial = service.run(limit=10, persist=True, requested_by="newer_partial")
    assert partial["status"] == "partial"

    context = service.latest_context(limit=5)

    assert context["run_id"] == high_quality["run_id"]
    assert context["latest_capture_run_id"] == partial["run_id"]
    assert context["selection_reason"] == "highest_quality_fresh_run"
    assert context["selected_quality_tier"] == 3


def test_ad_hoc_urls_reject_private_network_and_credentials(test_db):
    service = CodexPublicOpinionService(store=test_db, sources=[])

    sources, errors = service._sources_with_ad_hoc_urls(
        [
            "http://127.0.0.1:8000/internal",
            "https://user:secret@example.com/news",
        ]
    )

    assert len(sources) == 4
    assert all(not source.id.startswith("ad_hoc_") for source in sources)
    assert len(errors) == 2
    assert all("unsafe_ad_hoc_url" in item["error"] for item in errors)


def test_ad_hoc_public_url_fetch_is_disabled_to_prevent_dns_rebinding(test_db):
    service = CodexPublicOpinionService(store=test_db, sources=[])

    sources, errors = service._sources_with_ad_hoc_urls(["https://example.com/news"])

    assert len(sources) == len(DEFAULT_SOURCES)
    assert errors == [
        {
            "source_id": "ad_hoc_1",
            "url": "https://example.com/news",
            "error": "ad_hoc_network_fetch_disabled_use_codex_evidence_ingest",
        }
    ]


def test_proxy_synthetic_dns_is_allowed_only_for_trusted_static_sources(test_db, monkeypatch):
    service = CodexPublicOpinionService(store=test_db, sources=[])

    monkeypatch.setattr(
        "app.public_opinion.service.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 0, "", ("198.18.0.42", 443))],
    )

    service._validate_public_url(
        DEFAULT_SOURCES[0].url,
        resolve_dns=True,
        allow_proxy_synthetic_dns=True,
    )
    with pytest.raises(ValueError, match="private_or_non_global"):
        service._validate_public_url(
            "https://example.com/news",
            resolve_dns=True,
        )

    monkeypatch.setattr(
        "app.public_opinion.service.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 0, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(ValueError, match="private_or_non_global"):
        service._validate_public_url(
            DEFAULT_SOURCES[0].url,
            resolve_dns=True,
            allow_proxy_synthetic_dns=True,
        )


def test_codex_evidence_ingest_requires_auditable_fields_and_marks_freshness(test_db):
    _reset(test_db)
    service = CodexPublicOpinionService(store=test_db, sources=[])
    now = datetime.now(timezone.utc)

    result = service.ingest_evidence(
        [
            {
                "url": "https://www.csrc.gov.cn/csrc/policy/ai-compute",
                "retrieved_at": now.isoformat(),
                "published_at_status": "known",
                "published_at": now.isoformat(),
                "title": "政策加快人工智能算力基础设施建设",
                "summary": "官方文件提出支持数据中心和芯片基础设施建设。",
                "source_id": "official_fixture",
                "source_name": "Official Fixture",
                "source_tier": "official",
                "category": "policy",
                "sector_hints": ["算力"],
            }
        ],
        persist=True,
        requested_by="pytest_codex",
    )

    assert result["status"] == "completed"
    assert result["schema_version"] == "codex_public_opinion_evidence_ingest.v1"
    assert result["items"][0]["freshness_status"] == "fresh"
    assert result["items"][0]["published_at_status"] == "known"
    assert result["source_stats"]["ingest_mode"] == "codex_structured_evidence"
    assert result["sector_signals"][0]["sector"] == "ai_compute"
    assert result["sector_signals"][0]["official_policy_count"] == 1
    assert result["review_only"] is True
    assert result["simulation_only"] is True
    assert result["live_trading_enabled"] is False


def test_codex_evidence_ingest_api_contract(client):
    now = datetime.now(timezone.utc).isoformat()
    response = client.post(
        "/api/public-opinion/evidence/ingest",
        json={
            "persist": False,
            "requested_by": "pytest_api",
            "evidence": [
                {
                    "url": "https://example.com/market/robotics",
                    "retrieved_at": now,
                    "published_at_status": "known",
                    "published_at": now,
                    "title": "机器人板块获得最新产业政策支持",
                    "summary": "结构化证据包含来源、时间和可复核链接。",
                    "source_name": "Fixture News",
                    "source_id": "fixture_news",
                    "category": "policy",
                    "sector_hints": ["机器人"],
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "codex_public_opinion_evidence_ingest.v1"
    assert payload["item_count"] == 1
    assert payload["review_only"] is True
    assert payload["simulation_only"] is True
    assert payload["live_trading_enabled"] is False


def test_codex_evidence_rejects_unverified_official_domain(test_db):
    service = CodexPublicOpinionService(store=test_db, sources=[])
    now = datetime.now(timezone.utc)

    result = service.ingest_evidence(
        [
            {
                "url": "https://example.com/policy/ai-compute",
                "retrieved_at": now.isoformat(),
                "published_at_status": "known",
                "published_at": now.isoformat(),
                "title": "自称官方的人工智能算力政策消息",
                "summary": "该来源域名不属于受信任的官方域名。",
                "source_id": "spoofed_official",
                "source_name": "Spoofed Official",
                "source_tier": "official",
                "category": "policy",
                "sector_hints": ["算力"],
            }
        ],
        persist=False,
        requested_by="pytest_codex",
    )

    assert result["status"] == "partial"
    assert result["item_count"] == 0
    assert "official_source_domain_unverified" in result["errors"][0]["error"]


def test_ascii_sector_keyword_does_not_match_inside_unrelated_word(test_db):
    service = CodexPublicOpinionService(store=test_db, sources=[])

    assert service._keyword_hits("AI 芯片", ["AI"]) == ["AI"]
    assert service._keyword_hits("external_discovery_failed_review_only", ["AI"]) == []


def test_sector_confidence_counts_publishers_not_claimed_source_ids(test_db):
    service = CodexPublicOpinionService(store=test_db, sources=[])
    items = []
    for source_id, path in (("sina_one", "one"), ("sina_two", "two")):
        items.append(
            service._score_item(
                {
                    "source_id": source_id,
                    "source_name": "Sina",
                    "source_tier": "market_media",
                    "category": "market",
                    "title": "人工智能芯片板块走强",
                    "summary": "市场资金关注算力方向。",
                    "url": f"https://finance.sina.com.cn/{path}",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "freshness_status": "fresh",
                }
            )
        )

    signal = service._sector_signals(items)[0]

    assert signal["independent_source_count"] == 1


def test_single_negative_policy_signal_is_risk_review_only(test_db):
    service = CodexPublicOpinionService(store=test_db, sources=[])

    action = service._suggested_action(
        {"risk_count": 1, "positive_count": 0, "policy_count": 1, "item_count": 1},
        heat_score=20,
    )

    assert action == "risk_review_only"


def test_unknown_time_positive_does_not_become_fresh_tailwind(test_db):
    service = CodexPublicOpinionService(store=test_db, sources=[])
    positive_unknown = service._score_item(
        {
            "source_id": "old_policy",
            "source_name": "Policy",
            "source_tier": "official",
            "category": "policy",
            "title": "政策支持人工智能算力建设",
            "summary": "支持芯片产业。",
            "url": "https://www.csrc.gov.cn/old",
            "freshness_status": "unknown",
        }
    )
    fresh_neutral = service._score_item(
        {
            "source_id": "fresh_market",
            "source_name": "Market",
            "source_tier": "market_media",
            "category": "market",
            "title": "人工智能芯片板块交易信息",
            "summary": "板块成交信息汇总。",
            "url": "https://finance.sina.com.cn/fresh",
            "freshness_status": "fresh",
        }
    )

    signal = service._sector_signals([positive_unknown, fresh_neutral])[0]

    assert signal["positive_count"] >= 1
    assert signal["fresh_positive_count"] == 0
    assert signal["fresh_official_policy_count"] == 0
    assert signal["fresh_official_positive_policy_count"] == 0
    assert signal["fresh_positive_source_count"] == 0
