from __future__ import annotations

from datetime import date, timedelta
import json

from app.candidates.selection_v2 import StrategySelectionV2Service
from app.forecasting import ForecastDecision, ForecastLedger
from app.market_intelligence import SectorExposureResolver, SectorMembership


def _reset(store) -> None:
    with store.connect() as conn:
        for table in [
            "stock_profiles",
            "candidate_lifecycle",
            "candidate_lifecycle_events",
            "auto_discovered_candidates",
            "potential_search_items",
            "potential_search_runs",
            "candidate_scores",
            "daily_bar_cache",
            "realtime_market_events",
            "public_opinion_runs",
            "public_opinion_items",
            "public_opinion_sector_signals",
        ]:
            conn.execute(f"DELETE FROM {table}")


def _insert_profile(
    store,
    symbol: str,
    name: str,
    price: float | None,
    *,
    pct_change: float | None = None,
    pb: float | None = None,
    market_cap_billion: float | None = None,
    score: float = 60,
    rating: str = "训练关注",
    risk_level: str | None = None,
    operation_cost_line: float | None = None,
    sell_target: float | None = None,
    limit_up_count: int | None = None,
) -> None:
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO stock_profiles(
                symbol, name, current_price, pct_change, operation_cost_line,
                sell_target, risk_level, pb, limit_up_count, score, rating,
                dataset_name, source_file, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                name,
                price,
                pct_change,
                operation_cost_line,
                sell_target,
                risk_level,
                pb,
                limit_up_count,
                score,
                rating,
                "unit_test",
                "test_strategy_selection_v2.py",
                json.dumps({"market_cap_billion": market_cap_billion}, ensure_ascii=False),
            ),
        )


def _insert_bars(
    store,
    symbol: str,
    closes: list[float],
    *,
    base_volume: float = 1_000_000,
    last_volume_ratio: float = 1.4,
    amount: float = 80_000_000,
    upper_shadow_last: bool = False,
) -> None:
    start = date(2025, 1, 1)
    with store.connect() as conn:
        for index, close in enumerate(closes):
            prev = closes[index - 1] if index else close
            open_ = prev
            high = max(open_, close) * 1.01
            low = min(open_, close) * 0.99
            if upper_shadow_last and index == len(closes) - 1:
                open_ = close * 0.995
                high = close * 1.13
                low = close * 0.99
            volume = base_volume
            if index == len(closes) - 1:
                volume = base_volume * last_volume_ratio
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, volume, amount,
                    source, quality_status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    (start + timedelta(days=index)).isoformat(),
                    open_,
                    high,
                    low,
                    close,
                    volume,
                    amount,
                    "unit_test",
                    "ready",
                    "2026-06-30T15:00:00",
                ),
            )


def _item(result: dict, symbol: str) -> dict:
    for candidate in result["daily_candidate_snapshot"]:
        if candidate["symbol"] == symbol:
            return candidate
    raise AssertionError(f"missing candidate {symbol}")


def test_strategy_selection_v2_soft_scores_and_plan_buckets(test_db):
    _reset(test_db)

    _insert_profile(test_db, "SZ300001", "高位强势", 31, pct_change=4.0, pb=4.2, market_cap_billion=120)
    _insert_bars(test_db, "SZ300001", [10 + i * 0.1 for i in range(210)] + [31], last_volume_ratio=1.5)

    _insert_profile(test_db, "SZ300002", "高位出货", 30.5, pct_change=1.0, pb=4.8, market_cap_billion=90)
    _insert_bars(
        test_db,
        "SZ300002",
        [10 + i * 0.09 for i in range(210)] + [30.5],
        last_volume_ratio=4.5,
        upper_shadow_last=True,
    )

    _insert_profile(test_db, "SZ300003", "低位弱势", 10, pct_change=-1.5, pb=2.6, market_cap_billion=80)
    _insert_bars(test_db, "SZ300003", [24 - i * 0.06 for i in range(211)], last_volume_ratio=0.6)

    _insert_profile(test_db, "SZ300004", "高PB强势", 12, pct_change=10.1, pb=8.5, market_cap_billion=70, limit_up_count=1)
    _insert_bars(test_db, "SZ300004", [18 - i * 0.04 for i in range(210)] + [12], last_volume_ratio=1.8)

    _insert_profile(test_db, "SH600005", "大盘核心", 22, pct_change=4.8, pb=3.1, market_cap_billion=1500)
    _insert_bars(test_db, "SH600005", [14 + i * 0.04 for i in range(210)] + [22], last_volume_ratio=1.2)

    _insert_profile(test_db, "SZ300006", "A杀修复", 22, pct_change=9.8, pb=3.0, market_cap_billion=80)
    _insert_bars(test_db, "SZ300006", [52 - i * 0.15 for i in range(200)] + [20, 21, 22], last_volume_ratio=1.6)

    _insert_profile(
        test_db,
        "SZ300007",
        "成本线附近",
        13.1,
        pct_change=1.2,
        pb=3.8,
        market_cap_billion=90,
        operation_cost_line=13,
        sell_target=26,
    )
    _insert_bars(test_db, "SZ300007", [12.6 + (i % 4) * 0.05 for i in range(211)], last_volume_ratio=1.0)

    _insert_profile(test_db, "SZ300008", "*ST风险", 5, pct_change=1.0, pb=1.2, market_cap_billion=20)
    _insert_bars(test_db, "SZ300008", [5 + i * 0.01 for i in range(60)], last_volume_ratio=1.0)

    _insert_profile(test_db, "SZ300009", "数据缺失", 9, pct_change=3.0, pb=3.0, market_cap_billion=50)

    result = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=50)

    high_strong = _item(result, "SZ300001")
    assert high_strong["plan_type"] in {"WAIT_PULLBACK_PLAN", "WATCH_ONLY_PLAN", "WAIT_BREAKOUT_PLAN"}
    assert high_strong["plan_type"] != "REJECT_HARD"

    distribution = _item(result, "SZ300002")
    assert "HIGH_DISTRIBUTION" in distribution["risk_flags"]
    assert "STRUCTURE_DISTRIBUTION_VETO" in distribution["risk_flags"]
    assert distribution["features"]["structure_signal"]["distribution_veto"] is True
    assert (
        distribution["features"]["structure_signal"]["distribution_probability"]
        > distribution["features"]["structure_signal"]["pre_markup_probability"]
    )
    assert distribution["plan_type"] != "SIM_BUY_PLAN"

    weak_low = _item(result, "SZ300003")
    assert weak_low["plan_type"] != "SIM_BUY_PLAN"

    high_pb = _item(result, "SZ300004")
    assert "PB_HIGH" in high_pb["risk_flags"]
    assert high_pb["plan_type"] in {"WAIT_PULLBACK_PLAN", "WAIT_BREAKOUT_PLAN", "WATCH_ONLY_PLAN"}
    assert high_pb["plan_type"] != "REJECT_HARD"

    large_cap = _item(result, "SH600005")
    assert "STRATEGY_005" in large_cap["strategy_candidates"]
    assert large_cap["plan_type"] in {"SECTOR_BAROMETER", "WAIT_PULLBACK_PLAN", "WATCH_ONLY_PLAN"}
    assert large_cap["plan_type"] != "REJECT_HARD"

    a_kill = _item(result, "SZ300006")
    assert "A_KILL_REPAIR" in a_kill["risk_flags"]
    assert a_kill["plan_type"] != "SIM_BUY_PLAN"

    cost_line = _item(result, "SZ300007")
    assert cost_line["features"]["structure_signal"]["review_only"] is True
    assert (
        cost_line["features"]["structure_signal"]["pre_markup_probability"]
        > cost_line["features"]["structure_signal"]["distribution_probability"]
    )
    assert "STRATEGY_004" in cost_line["strategy_candidates"]
    assert cost_line["plan_type"] == "WAIT_BREAKOUT_PLAN"

    st_risk = _item(result, "SZ300008")
    assert st_risk["plan_type"] == "REJECT_HARD"
    assert "HF001_ST" in st_risk["hard_blocks"]

    data_weak = _item(result, "SZ300009")
    assert "DATA_WEAK" in data_weak["risk_flags"]
    assert data_weak["plan_type"] != "SIM_BUY_PLAN"

    assert result["summary"]["candidate_count"] == 9
    assert result["filter_diagnostics"]["after_hard_filter_count"] >= 1
    assert result["safety"]["simulate_only"] is True
    assert result["safety"]["allow_live_order"] is False
    for candidate in result["daily_candidate_snapshot"]:
        assert candidate["simulate_only"] is True
        assert candidate["allow_live_order"] is False
        assert candidate["execution_allowed"] is False


def test_strategy_selection_v2_strict_zero_still_outputs_diagnostics(test_db):
    _reset(test_db)
    _insert_profile(test_db, "SZ301001", "弱势观察", 10, pct_change=-2.0, pb=3.0, market_cap_billion=60)
    _insert_bars(test_db, "SZ301001", [18 - i * 0.04 for i in range(80)], last_volume_ratio=0.7)

    result = StrategySelectionV2Service(store=test_db).run(mode="strict", limit=20)

    assert result["summary"]["strict_buy_plan_count"] == 0
    assert result["daily_candidate_snapshot"]
    assert result["filter_diagnostics"]["top_blocking_reasons"]
    assert result["safety"]["simulate_only"] is True
    assert result["safety"]["allow_live_order"] is False


def test_strategy_selection_v2_api_smoke(client, test_db):
    _reset(test_db)
    _insert_profile(test_db, "SZ301002", "接口候选", 11, pct_change=8.0, pb=4.0, market_cap_billion=80)
    _insert_bars(test_db, "SZ301002", [14 - i * 0.02 for i in range(90)] + [11], last_volume_ratio=1.5)

    response = client.get("/api/candidates/selection-v2/summary?mode=balanced&limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["summary"]["candidate_count"] == 1
    assert payload["safety"]["simulate_only"] is True
    assert payload["safety"]["allow_live_order"] is False
    assert payload["daily_candidate_snapshot"][0]["allow_live_order"] is False


def test_strategy_selection_v2_uses_potential_items_and_filters_unit_test_only_profiles(test_db):
    _reset(test_db)
    _insert_profile(test_db, "SZ300007", "unit-test-only", 13.1, score=99)
    _insert_bars(test_db, "SZ300007", [12.6 + (i % 4) * 0.05 for i in range(211)], last_volume_ratio=1.0)
    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO potential_search_items(
                run_id, symbol, name, current_price, pct_change, turnover_rate,
                amount, lifecycle_state, potential_score, reasons_json,
                components_json, source, raw_json
            )
            VALUES (1, 'SH600000', 'real-candidate', 10.5, 6.2, 3.1,
                    120000000, 'pending_review', 88, '[]', '{}', 'fixture', '{}')
            """
        )

    result = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=20)
    symbols = {item["symbol"] for item in result["daily_candidate_snapshot"]}

    assert "SH600000" in symbols
    assert "SZ300007" not in symbols
    assert result["summary"]["candidate_count"] == 1
    assert result["safety"]["allow_live_order"] is False


def test_strategy_selection_v2_quarantines_candidates_without_market_basis(test_db):
    _reset(test_db)
    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO potential_search_items(
                run_id, symbol, name, current_price, pct_change, turnover_rate,
                amount, lifecycle_state, potential_score, reasons_json,
                components_json, source, raw_json
            )
            VALUES (1, 'SZ301010', 'active-candidate', 18, 3.0, 2.2,
                    90000000, 'pending_review', 82, '[]', '{}', 'pytest', '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, discovery_score, volume_score,
                phase_score, lifecycle_score, focus_score, risk_penalty,
                rating, state, source, reasons_json, components_json, raw_json
            )
            VALUES (
                'SH600111', 'no-market-basis', 95, 12, 12,
                15, 12, 8, 2, 'review', 'pending_review',
                'pytest_gap', '["cached score only"]', '{}', '{}'
            )
            """
        )
    result = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=20)
    active_symbols = {item["symbol"] for item in result["daily_candidate_snapshot"]}
    gap_symbols = {item["symbol"] for item in result["data_gap_candidates"]}

    assert "SZ301010" in active_symbols
    assert "SH600111" not in active_symbols
    assert "SH600111" in gap_symbols
    assert result["summary"]["candidate_count"] == 1
    assert result["summary"]["data_gap_count"] == 1
    assert result["filter_diagnostics"]["active_candidate_count"] == 1
    assert result["filter_diagnostics"]["data_gap_count"] == 1
    assert result["data_gap_candidates"][0]["allow_live_order"] is False


def test_strategy_selection_v2_uses_public_opinion_sector_tailwind(test_db):
    _reset(test_db)
    _insert_profile(
        test_db,
        "SZ301099",
        "AI芯片设备",
        18,
        pct_change=5.2,
        pb=4.0,
        market_cap_billion=90,
    )
    _insert_bars(test_db, "SZ301099", [12 + i * 0.02 for i in range(210)] + [18], last_volume_ratio=1.6)

    with test_db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO public_opinion_runs(
                status, source_count, item_count, sector_count,
                summary_json, review_only, simulation_only, live_trading_enabled
            )
            VALUES ('completed', 1, 2, 1, '{}', 1, 1, 0)
            """
        )
        run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO public_opinion_sector_signals(
                run_id, sector, heat_score, item_count, positive_count,
                policy_count, market_count, risk_count, keywords_json,
                evidence_json, suggested_action
            )
            VALUES (?, 'ai_compute', 60, 2, 2, 1, 1, 0, ?, ?, 'sector_watch_review_only')
            """,
            (
                run_id,
                json.dumps(["AI", "芯片"], ensure_ascii=False),
                json.dumps(
                    [
                        {
                            "title": "政策支持AI芯片算力建设",
                            "score": 32,
                            "source_id": "csrc_policy",
                            "source_tier": "official",
                            "tags": ["policy", "positive"],
                            "freshness_status": "fresh",
                        }
                    ],
                    ensure_ascii=False,
                ),
            ),
        )

    result = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=20)
    item = _item(result, "SZ301099")

    assert result["public_opinion_context"]["top_sectors"][0]["sector"] == "ai_compute"
    assert item["features"]["public_opinion_tailwind"]["matched"] is True
    assert item["features"]["public_opinion_tailwind"]["sector"] == "ai_compute"
    assert item["features"]["public_opinion_tailwind"]["official_policy_count"] == 1
    assert "PUBLIC_OPINION_SECTOR_TAILWIND" in item["raw_signals"]
    assert item["score_components"]["market_sector"] > 3
    assert item["allow_live_order"] is False


def test_strategy_selection_v2_does_not_give_global_news_bonus_without_candidate_match(test_db):
    _reset(test_db)
    _insert_profile(
        test_db,
        "SZ301100",
        "食品零售",
        18,
        pct_change=5.2,
        pb=4.0,
        market_cap_billion=90,
    )
    _insert_bars(test_db, "SZ301100", [12 + i * 0.02 for i in range(210)] + [18], last_volume_ratio=1.6)

    baseline = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=20)
    baseline_item = _item(baseline, "SZ301100")

    with test_db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO public_opinion_runs(
                status, source_count, item_count, sector_count,
                summary_json, review_only, simulation_only, live_trading_enabled
            )
            VALUES ('completed', 2, 2, 1, '{}', 1, 1, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO public_opinion_sector_signals(
                run_id, sector, heat_score, item_count, positive_count,
                policy_count, market_count, risk_count, keywords_json,
                evidence_json, suggested_action
            )
            VALUES (?, 'ai_compute', 72, 2, 2, 1, 1, 0, ?, '[]', 'sector_watch_review_only')
            """,
            (cursor.lastrowid, json.dumps(["AI", "芯片"], ensure_ascii=False)),
        )

    with_news = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=20)
    news_item = _item(with_news, "SZ301100")

    assert news_item["features"]["public_opinion_tailwind"]["matched"] is False
    assert news_item["features"]["public_opinion_tailwind"]["score_effect"] == "none_without_candidate_sector_match"
    assert news_item["score_components"]["market_sector"] == baseline_item["score_components"]["market_sector"]


def test_strategy_selection_v2_ascii_keyword_requires_token_boundary(test_db):
    service = StrategySelectionV2Service(store=test_db)

    assert service._candidate_keyword_match("ai 芯片设备", "AI") is True
    assert service._candidate_keyword_match("external_discovery_failed_review_only", "AI") is False


def test_strategy_selection_v2_blocks_stale_production_bars(test_db):
    _reset(test_db)
    _insert_profile(test_db, "SH600099", "生产候选", 12.0, pct_change=2.0)
    _insert_bars(test_db, "SH600099", [10.0 + index * 0.01 for index in range(30)])
    with test_db.connect() as conn:
        conn.execute(
            """
            UPDATE stock_profiles
            SET dataset_name = 'production', source_file = 'market_import.csv',
                raw_json = '{"as_of_date":"2026-07-10"}'
            WHERE symbol = 'SH600099'
            """
        )

    result = StrategySelectionV2Service(store=test_db).run(
        mode="balanced",
        limit=20,
        as_of_date="2026-07-10",
    )
    item = _item(result, "SH600099")

    assert "HF007_STALE_MARKET_DATA" in item["hard_blocks"]
    assert item["plan_type"] == "REJECT_HARD"


def test_strategy_selection_v2_ignores_stale_realtime_and_profile_prices(test_db):
    _reset(test_db)
    closes = [10.0 + index * 0.1 for index in range(30)]
    _insert_profile(test_db, "SZ300099", "价格时效测试", 88.0, pct_change=9.0)
    _insert_bars(test_db, "SZ300099", closes)
    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO realtime_market_events(
                symbol, name, price, source, provider_status, event_ts, received_ts,
                quality_status, payload_json, dedupe_key
            ) VALUES (
                'SZ300099', '价格时效测试', 99, 'pytest', 'ok',
                '2020-01-01T10:00:00+08:00', '2020-01-01T10:00:01+08:00',
                'realtime_ok', '{}', 'stale-price-fixture'
            )
            """
        )

    result = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=20)
    item = _item(result, "SZ300099")

    assert item["features"]["price"] == closes[-1]
    assert item["features"]["price_source"] == "daily_bar_cache"
    assert item["features"]["realtime_freshness"]["status"] == "stale_date"


def test_strategy_selection_v2_global_rank_keeps_high_score_from_later_source(test_db):
    _reset(test_db)
    with test_db.connect() as conn:
        for index in range(10):
            conn.execute(
                """
                INSERT INTO candidate_lifecycle(symbol, name, state, score, source, raw_json)
                VALUES (?, ?, 'pending_review', 1, 'lifecycle', '{}')
                """,
                (f"SH6001{index:02d}", f"low-{index}"),
            )
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, rating, state, source,
                reasons_json, components_json, raw_json
            ) VALUES (
                'SZ300888', 'high-score', 99, 'focus', 'pending_review',
                'candidate_score', '[]', '{}', '{}'
            )
            """
        )

    universe = StrategySelectionV2Service(store=test_db).candidate_universe(limit=5)

    assert "SZ300888" in universe


def test_strategy_selection_v2_as_of_date_excludes_all_future_evidence(test_db):
    _reset(test_db)
    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, source, reasons_json,
                components_json, raw_json, created_at
            ) VALUES (
                'SH600888', 'past-ai-candidate', 20, 'pytest', '[]', '{}', '{}',
                '2026-01-02T09:00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, source, reasons_json,
                components_json, raw_json, created_at
            ) VALUES (
                'SH600888', 'future-overwrite', 99, 'pytest', '[]', '{}', '{}',
                '2026-01-03T09:00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, source, reasons_json,
                components_json, raw_json, created_at
            ) VALUES (
                'SZ300999', 'future-only-candidate', 100, 'pytest', '[]', '{}', '{}',
                '2026-01-03T09:00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO stock_profiles(
                symbol, name, current_price, score, rating,
                dataset_name, source_file, raw_json
            ) VALUES (
                'SZ300777', 'undated-profile', 42, 100, 'future-unknown',
                'production', 'undated.csv', '{}'
            )
            """
        )
        for trade_date, close in (
            ('2026-01-01', 10.0),
            ('2026-01-02', 11.0),
            ('2026-01-03', 99.0),
        ):
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, volume, amount,
                    source, quality_status
                ) VALUES ('SH600888', ?, ?, ?, ?, ?, 1000, 1000000, 'pytest', 'ready')
                """,
                (trade_date, close, close * 1.01, close * 0.99, close),
            )
        for event_ts, price, dedupe_key in (
            ('2026-01-02T10:00:00+08:00', 12.0, 'as-of-past'),
            ('2026-01-03T10:00:00+08:00', 100.0, 'as-of-future'),
        ):
            conn.execute(
                """
                INSERT INTO realtime_market_events(
                    symbol, name, price, source, provider_status, event_ts,
                    received_ts, quality_status, payload_json, dedupe_key
                ) VALUES (
                    'SH600888', 'past-ai-candidate', ?, 'pytest', 'ok', ?, ?,
                    'realtime_ok', '{}', ?
                )
                """,
                (price, event_ts, event_ts, dedupe_key),
            )

        past_run_id = int(
            conn.execute(
                """
                INSERT INTO public_opinion_runs(
                    status, item_count, sector_count, summary_json,
                    review_only, simulation_only, live_trading_enabled,
                    created_at, completed_at
                ) VALUES (
                    'completed', 1, 1, '{}', 1, 1, 0,
                    '2026-01-02T11:00:00', '2026-01-02T11:01:00'
                )
                """
            ).lastrowid
        )
        conn.execute(
            """
            INSERT INTO public_opinion_sector_signals(
                run_id, sector, heat_score, item_count, positive_count,
                keywords_json, evidence_json, suggested_action, created_at
            ) VALUES (?, 'ai_compute', 40, 1, 1, '["AI"]', '[]',
                      'sector_watch_review_only', '2026-01-02T11:01:00')
            """,
            (past_run_id,),
        )
        future_run_id = int(
            conn.execute(
                """
                INSERT INTO public_opinion_runs(
                    status, item_count, sector_count, summary_json,
                    review_only, simulation_only, live_trading_enabled,
                    created_at, completed_at
                ) VALUES (
                    'completed', 1, 1, '{}', 1, 1, 0,
                    '2026-01-03T11:00:00', '2026-01-03T11:01:00'
                )
                """
            ).lastrowid
        )
        conn.execute(
            """
            INSERT INTO public_opinion_sector_signals(
                run_id, sector, heat_score, item_count, positive_count,
                keywords_json, evidence_json, suggested_action, created_at
            ) VALUES (?, 'defense', 99, 1, 1, '["defense"]', '[]',
                      'sector_watch_review_only', '2026-01-03T11:01:00')
            """,
            (future_run_id,),
        )

    result = StrategySelectionV2Service(store=test_db).run(
        mode="balanced",
        limit=20,
        as_of_date="2026-01-02",
    )

    symbols = {
        item["symbol"]
        for item in result["daily_candidate_snapshot"] + result["data_gap_candidates"]
    }
    item = _item(result, "SH600888")
    assert symbols == {"SH600888"}
    assert item["name"] == "past-ai-candidate"
    assert item["features"]["bars_count"] == 2
    assert item["features"]["price"] == 12.0
    assert item["features"]["latest_realtime"]["event_ts"].startswith("2026-01-02")
    assert result["public_opinion_context"]["run_id"] == past_run_id
    assert result["public_opinion_context"]["top_sectors"][0]["sector"] == "ai_compute"


def test_sector_forecast_matches_candidate_through_point_in_time_membership(test_db):
    _reset(test_db)
    SectorExposureResolver(test_db).record(
        SectorMembership(
            symbol="SH600321",
            sector="semiconductors",
            effective_from="2026-01-01",
            effective_to=None,
            source="pytest",
            available_at="2026-01-02T08:00:00+08:00",
            confidence=0.95,
        )
    )
    ForecastLedger(test_db).record_forecast(
        ForecastDecision(
            decision_id="sector-thesis-pit",
            scope="sector",
            subject="semiconductors",
            decision_cutoff="2026-01-02T09:00:00+08:00",
            available_at="2026-01-02T09:00:00+08:00",
            horizon_days=5,
            rank=1,
            score=82.0,
            probability=0.82,
            model_version="market_intelligence_snapshot.v1",
            prompt_version="codex_market_pulse.v2",
            data_version="2026-01-02",
            features={
                "sector": "semiconductors",
                "direction": "positive",
                "confidence": 0.82,
                "horizon": "1-4w",
            },
            evidence=[],
            reasons=["cross-market confirmation"],
            status="pending_outcome",
        )
    )
    service = StrategySelectionV2Service(store=test_db)

    context = service._public_opinion_context(as_of_date="2026-01-03")
    tailwind = service._candidate_public_opinion_tailwind(
        {"symbol": "SH600321", "name": "fixture-company"},
        context,
        as_of_date="2026-01-03",
    )

    assert context["sector_forecasts"][0]["sector"] == "semiconductors"
    assert tailwind["matched"] is True
    assert tailwind["sector_forecast"] is True
    assert tailwind["matched_via"] == "sector_membership_history"
    assert tailwind["sector"] == "semiconductors"
