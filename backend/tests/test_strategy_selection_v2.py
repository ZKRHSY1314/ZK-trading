from __future__ import annotations

from datetime import date, timedelta
import json

from app.candidates.selection_v2 import StrategySelectionV2Service


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
                    [{"title": "政策支持AI芯片算力建设", "score": 32}],
                    ensure_ascii=False,
                ),
            ),
        )

    result = StrategySelectionV2Service(store=test_db).run(mode="balanced", limit=20)
    item = _item(result, "SZ301099")

    assert result["public_opinion_context"]["top_sectors"][0]["sector"] == "ai_compute"
    assert item["features"]["public_opinion_tailwind"]["matched"] is True
    assert item["features"]["public_opinion_tailwind"]["sector"] == "ai_compute"
    assert "PUBLIC_OPINION_SECTOR_TAILWIND" in item["raw_signals"]
    assert item["score_components"]["market_sector"] > 3
    assert item["allow_live_order"] is False
