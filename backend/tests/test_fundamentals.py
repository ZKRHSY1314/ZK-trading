import pytest

from app.data.fundamentals import (
    METHOD,
    FundamentalResolver,
    FundamentalsStore,
    FundamentalSnapshot,
    parse_quote_line,
    tencent_code,
)


def quote_line(code: str, name: str, price: str, float_cap: str, total_cap: str, pb: str) -> str:
    fields = [""] * 88
    fields[0] = "1"
    fields[1] = name
    fields[2] = code[2:]
    fields[3] = price
    fields[44] = float_cap
    fields[45] = total_cap
    fields[46] = pb
    return f'v_{code}="' + "~".join(fields) + '";'


@pytest.fixture
def store(test_db):
    with test_db.connect() as conn:
        conn.execute("DELETE FROM symbol_fundamental_snapshot")
    return test_db


def test_tencent_code_maps_each_board():
    assert tencent_code("SH600000") == "sh600000"
    assert tencent_code("SH688981") == "sh688981"
    assert tencent_code("SZ000001") == "sz000001"
    assert tencent_code("SZ300750") == "sz300750"
    assert tencent_code("BJ430047") == "bj430047"


def test_parse_quote_line_derives_share_count_and_book_value():
    line = quote_line("sh600000", "浦发银行", "9.16", "3050.81", "3050.81", "0.40")
    snapshot = parse_quote_line(line, "2026-09-01")

    assert snapshot is not None
    assert snapshot.symbol == "600000"
    assert snapshot.market_cap_billion == pytest.approx(3050.81)
    assert snapshot.pb == pytest.approx(0.40)
    # 总市值 / 现价 = 总股本(亿股)
    assert snapshot.total_share_billion == pytest.approx(333.06, abs=0.01)
    # 现价 / 市净率 = 每股净资产
    assert snapshot.book_value_per_share == pytest.approx(22.9, abs=0.01)


def test_parse_quote_line_rejects_suspended_and_short_payloads():
    assert parse_quote_line(quote_line("sh600000", "X", "0.00", "1", "1", "1"), "2026-09-01") is None
    assert parse_quote_line('v_sh600000="1~X~600000~9.16";', "2026-09-01") is None
    assert parse_quote_line("", "2026-09-01") is None


def test_parse_quote_line_leaves_missing_valuation_none():
    snapshot = parse_quote_line(
        quote_line("sz000001", "平安银行", "11.72", "2274.35", "0.00", "0.00"),
        "2026-09-01",
    )
    assert snapshot is not None
    assert snapshot.market_cap_billion is None
    assert snapshot.pb is None
    assert snapshot.total_share_billion is None
    assert snapshot.book_value_per_share is None


def test_resolver_projects_snapshot_onto_a_historical_close(store):
    written = FundamentalsStore(store).upsert(
        [
            FundamentalSnapshot(
                symbol="600000",
                name="浦发银行",
                as_of="2026-09-01",
                price=10.0,
                market_cap_billion=1000.0,
                float_cap_billion=1000.0,
                pb=2.0,
                total_share_billion=100.0,
                book_value_per_share=5.0,
            )
        ]
    )
    assert written == 1

    resolver = FundamentalResolver(store)
    resolved = resolver.resolve("SH600000", close=8.0)

    # 100亿股 × 8元 = 800亿; 8元 / 5元每股净资产 = 1.6
    assert resolved.market_cap_billion == pytest.approx(800.0)
    assert resolved.pb == pytest.approx(1.6)
    assert resolved.method == METHOD
    assert resolved.snapshot_as_of == "2026-09-01"


def test_resolver_returns_empty_for_unknown_symbol_or_bad_close(store):
    resolver = FundamentalResolver(store)
    assert resolver.resolve("SH600000", close=8.0).market_cap_billion is None
    assert resolver.resolve("not-a-code", close=8.0).market_cap_billion is None


def test_upsert_is_idempotent_per_symbol_and_day(store):
    snapshot = FundamentalSnapshot(
        symbol="600000",
        name="浦发银行",
        as_of="2026-09-01",
        price=10.0,
        market_cap_billion=1000.0,
        float_cap_billion=1000.0,
        pb=2.0,
        total_share_billion=100.0,
        book_value_per_share=5.0,
    )
    fundamentals = FundamentalsStore(store)
    fundamentals.upsert([snapshot])
    fundamentals.upsert([snapshot])

    rows = store.fetch_all("SELECT COUNT(*) AS n FROM symbol_fundamental_snapshot")
    assert rows[0]["n"] == 1


def test_upsert_does_not_rewrite_original_availability(store):
    first = FundamentalSnapshot(
        symbol="600000",
        name="first",
        as_of="2026-09-01",
        price=10.0,
        market_cap_billion=1000.0,
        float_cap_billion=1000.0,
        pb=2.0,
        total_share_billion=100.0,
        book_value_per_share=5.0,
        available_at="2026-09-01T06:00:00+00:00",
    )
    replacement = FundamentalSnapshot(
        **{
            **first.__dict__,
            "name": "replacement",
            "available_at": "2026-09-02T06:00:00+00:00",
        }
    )
    fundamentals = FundamentalsStore(store)
    fundamentals.upsert([first])
    fundamentals.upsert([replacement])

    row = store.fetch_one(
        "SELECT name, available_at FROM symbol_fundamental_snapshot WHERE symbol = ?",
        ("600000",),
    )
    assert row["name"] == "first"
    assert row["available_at"] == "2026-09-01T06:00:00+00:00"


def test_resolver_excludes_snapshot_not_visible_at_decision_cutoff(store):
    FundamentalsStore(store).upsert(
        [
            FundamentalSnapshot(
                symbol="600000",
                name="future",
                as_of="2020-01-01",
                price=10.0,
                market_cap_billion=1000.0,
                float_cap_billion=1000.0,
                pb=2.0,
                total_share_billion=100.0,
                book_value_per_share=5.0,
                # Backfilled after the historical decision date.
                available_at="2020-01-02T00:00:00+00:00",
            )
        ]
    )

    resolved = FundamentalResolver(store).resolve(
        "SH600000",
        close=8.0,
        as_of="2020-01-01",
    )

    assert resolved.market_cap_billion is None
    assert resolved.pb is None


def test_resolver_uses_latest_snapshot_visible_at_exact_cutoff(store):
    FundamentalsStore(store).upsert(
        [
            FundamentalSnapshot(
                symbol="600000",
                name="visible",
                as_of="2020-01-01",
                price=10.0,
                market_cap_billion=1000.0,
                float_cap_billion=1000.0,
                pb=2.0,
                total_share_billion=100.0,
                book_value_per_share=5.0,
                available_at="2020-01-01T06:00:00+00:00",
            )
        ]
    )

    resolver = FundamentalResolver(store)
    before = resolver.resolve(
        "SH600000", close=8.0, as_of="2020-01-01T13:59:59+08:00"
    )
    after = resolver.resolve(
        "SH600000", close=8.0, as_of="2020-01-01T14:00:01+08:00"
    )

    assert before.market_cap_billion is None
    assert after.market_cap_billion == pytest.approx(800.0)
    assert after.snapshot_available_at == "2020-01-01T06:00:00+00:00"
