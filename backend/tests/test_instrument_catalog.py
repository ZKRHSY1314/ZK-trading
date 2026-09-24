from __future__ import annotations

import json
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from app.config import settings
from app.data.instrument_catalog import InstrumentCatalogRefreshService
from app.data.market_history import MarketHistoryStore


SHANGHAI = ZoneInfo("Asia/Shanghai")


class PartialCatalogProvider:
    def get_sh_main_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"证券代码": ["600000"], "证券简称": ["浦发银行"]})

    def get_sh_star_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"证券代码": ["688001"], "证券简称": ["华兴源创"]})

    def get_sz_a_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"A股代码": ["000001"], "A股简称": ["平安银行"]})

    def get_bj_code_name(self) -> pd.DataFrame:
        raise TimeoutError("north exchange directory timed out")


class CompleteCatalogProvider:
    def get_sh_main_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "证券代码": ["600000"],
                "证券简称": ["浦发银行"],
                "上市日期": ["1999-11-10"],
            }
        )

    def get_sh_star_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "证券代码": ["688001"],
                "证券简称": ["华兴源创"],
                "上市日期": ["2019-07-22"],
            }
        )

    def get_sz_a_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "A股代码": ["000001"],
                "A股简称": ["平安银行"],
                "A股上市日期": ["1991-04-03"],
            }
        )

    def get_bj_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "证券代码": ["920000"],
                "证券简称": ["北交测试"],
                "上市日期": ["2026-07-15"],
            }
        )


class ChangedCatalogProvider(CompleteCatalogProvider):
    def get_sh_main_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "证券代码": ["600000"],
                "证券简称": ["浦发银行新简称"],
                "上市日期": ["1999-11-10"],
            }
        )

    def get_bj_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "证券代码": ["920001"],
                "证券简称": ["北交新股"],
                "上市日期": ["2026-07-16"],
            }
        )


class EightMemberCatalogProvider:
    def get_sh_main_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"证券代码": ["600000", "600001"], "证券简称": ["沪主一", "沪主二"]}
        )

    def get_sh_star_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"证券代码": ["688001", "688002"], "证券简称": ["科创一", "科创二"]}
        )

    def get_sz_a_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"A股代码": ["000001", "000002"], "A股简称": ["深市一", "深市二"]}
        )

    def get_bj_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"证券代码": ["920000", "920001"], "证券简称": ["北交一", "北交二"]}
        )


class ProviderMustNotBeCalled:
    def __getattr__(self, name: str):
        raise AssertionError(f"provider must not be called: {name}")


class CatalogWithMissingName(CompleteCatalogProvider):
    def get_bj_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"证券代码": ["920000"], "证券简称": [float("nan")]})


class SzPrimaryFailureWithCombinedFallback(CompleteCatalogProvider):
    def get_sz_a_code_name(self) -> pd.DataFrame:
        raise ConnectionError("szse ssl eof")

    def get_a_share_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "code": ["sh600000", "sh688001", "sz000001", "sz300001"],
                "name": ["沪市重复", "科创重复", "平安银行", "特锐德"],
            }
        )


class SegmentSkewCatalogProvider:
    def get_sh_main_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "证券代码": ["600000", "600001", "600002", "600003"],
                "证券简称": ["沪主一", "沪主二", "沪主三", "沪主四"],
            }
        )

    def get_sh_star_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "证券代码": ["688001", "688002", "688003", "688004"],
                "证券简称": ["科创一", "科创二", "科创三", "科创四"],
            }
        )

    def get_sz_a_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "A股代码": ["000001", "000002", "000003", "000004"],
                "A股简称": ["深市一", "深市二", "深市三", "深市四"],
            }
        )

    def get_bj_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"证券代码": ["920000", "920001"], "证券简称": ["北交一", "北交二"]}
        )


class TruncatedBjCatalogProvider(SegmentSkewCatalogProvider):
    def get_bj_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"证券代码": ["920000"], "证券简称": ["北交一"]})


def test_incomplete_external_catalog_never_mutates_database_or_manifest(tmp_path) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"
    manifest_path.write_text(
        json.dumps({"sentinel": "last-known-good"}),
        encoding="utf-8",
    )

    result = InstrumentCatalogRefreshService(
        provider=PartialCatalogProvider(),
        database_path=database_path,
        minimum_member_count=1,
    ).run(
        apply=True,
        manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 9, 0, tzinfo=SHANGHAI),
    )

    assert result["status"] == "partial"
    assert result["writes_enabled"] is False
    assert result["discovery_complete"] is False
    assert result["member_count"] == 3
    assert not database_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
        "sentinel": "last-known-good"
    }


def test_complete_catalog_persists_versioned_snapshot_and_compatible_manifest(tmp_path) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"
    observed_at = datetime(2026, 7, 16, 9, 5, tzinfo=SHANGHAI)

    result = InstrumentCatalogRefreshService(
        provider=CompleteCatalogProvider(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(apply=True, manifest_path=manifest_path, now=observed_at)

    assert result["status"] == "completed"
    assert result["discovery_complete"] is True
    assert result["writes_enabled"] is True
    assert result["member_count"] == 4
    assert result["changes"] == {
        "added": 4,
        "renamed": 0,
        "reactivated": 0,
        "inactivated": 0,
    }
    with MarketHistoryStore(database_path).connect(read_only=True) as connection:
        instruments = connection.execute(
            "SELECT symbol, name, exchange, board, list_date, status "
            "FROM instruments ORDER BY symbol"
        ).fetchall()
        snapshots = connection.execute(
            "SELECT id, member_count, source_hash FROM universe_snapshots"
        ).fetchall()
        member_count = connection.execute(
            "SELECT COUNT(*) FROM universe_members WHERE snapshot_id = ?",
            (result["snapshot_id"],),
        ).fetchone()[0]

    assert [dict(row) for row in instruments] == [
        {
            "symbol": "BJ920000",
            "name": "北交测试",
            "exchange": "BJ",
            "board": "beijing",
            "list_date": "2026-07-15",
            "status": "active",
        },
        {
            "symbol": "SH600000",
            "name": "浦发银行",
            "exchange": "SH",
            "board": "sh_main",
            "list_date": "1999-11-10",
            "status": "active",
        },
        {
            "symbol": "SH688001",
            "name": "华兴源创",
            "exchange": "SH",
            "board": "star",
            "list_date": "2019-07-22",
            "status": "active",
        },
        {
            "symbol": "SZ000001",
            "name": "平安银行",
            "exchange": "SZ",
            "board": "sz_main",
            "list_date": "1991-04-03",
            "status": "active",
        },
    ]
    assert len(snapshots) == 1
    assert snapshots[0]["member_count"] == member_count == 4

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    symbols = ["BJ920000", "SH600000", "SH688001", "SZ000001"]
    legacy_hash = hashlib.sha256("\n".join(symbols).encode("utf-8")).hexdigest()
    assert manifest["schema_version"] == 2
    assert manifest["manifest_kind"] == "a_share_instrument_catalog"
    assert manifest["universe_symbols"] == symbols
    assert manifest["universe_hash"] == legacy_hash
    assert manifest["universe_count"] == 4
    assert manifest["discovery_complete"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["members"][1] == {
        "symbol": "SH600000",
        "name": "浦发银行",
        "exchange": "SH",
        "board": "sh_main",
        "list_date": "1999-11-10",
        "status": "active",
    }


def test_catalog_changes_preserve_old_snapshots_and_bars_while_updating_current_state(
    tmp_path,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"
    first = InstrumentCatalogRefreshService(
        provider=CompleteCatalogProvider(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(
        apply=True,
        manifest_path=manifest_path,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )
    store = MarketHistoryStore(database_path)
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_bars(
                symbol, trade_date, adjustment_mode, open, high, low, close,
                provider, fetched_at, row_hash
            ) VALUES ('BJ920000', '2026-07-15', 'qfq', 10, 11, 9, 10.5,
                      'pytest', '2026-07-15T16:00:00+08:00', 'old-bar')
            """
        )

    second = InstrumentCatalogRefreshService(
        provider=ChangedCatalogProvider(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(
        apply=True,
        manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 16, 0, tzinfo=SHANGHAI),
    )

    assert second["changes"] == {
        "added": 1,
        "renamed": 1,
        "reactivated": 0,
        "inactivated": 1,
    }
    with store.connect(read_only=True) as connection:
        current = {
            str(row["symbol"]): dict(row)
            for row in connection.execute(
                "SELECT symbol, name, status, delist_date FROM instruments"
            ).fetchall()
        }
        old_members = connection.execute(
            "SELECT symbol, member_metadata_json FROM universe_members "
            "WHERE snapshot_id = ? ORDER BY symbol",
            (first["snapshot_id"],),
        ).fetchall()
        new_symbols = [
            str(row["symbol"])
            for row in connection.execute(
                "SELECT symbol FROM universe_members WHERE snapshot_id = ? ORDER BY symbol",
                (second["snapshot_id"],),
            ).fetchall()
        ]
        old_bar_count = connection.execute(
            "SELECT COUNT(*) FROM daily_bars WHERE symbol = 'BJ920000'"
        ).fetchone()[0]

    assert current["SH600000"]["name"] == "浦发银行新简称"
    assert current["BJ920001"]["status"] == "active"
    assert current["BJ920000"] == {
        "symbol": "BJ920000",
        "name": "北交测试",
        "status": "inactive",
        "delist_date": None,
    }
    assert old_bar_count == 1
    assert json.loads(old_members[1]["member_metadata_json"])["name"] == "浦发银行"
    assert "BJ920000" in [str(row["symbol"]) for row in old_members]
    assert "BJ920000" not in new_symbols
    assert "BJ920001" in new_symbols


def test_suspiciously_truncated_successful_catalog_does_not_replace_last_good_snapshot(
    tmp_path,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"
    InstrumentCatalogRefreshService(
        provider=EightMemberCatalogProvider(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(
        apply=True,
        manifest_path=manifest_path,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )
    previous_manifest = manifest_path.read_bytes()

    result = InstrumentCatalogRefreshService(
        provider=CompleteCatalogProvider(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(
        apply=True,
        manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 16, 0, tzinfo=SHANGHAI),
    )

    assert result["status"] == "partial"
    assert result["reason"] == "suspicious_member_count_drop"
    assert result["baseline_member_count"] == 8
    assert result["member_count"] == 4
    assert result["writes_enabled"] is False
    assert manifest_path.read_bytes() == previous_manifest
    with MarketHistoryStore(database_path).connect(read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM universe_snapshots").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM instruments WHERE status = 'active'"
        ).fetchone()[0] == 8


def test_apply_is_blocked_before_discovery_when_live_trading_is_enabled(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"
    monkeypatch.setattr(settings, "enable_live_trading", True)

    result = InstrumentCatalogRefreshService(
        provider=ProviderMustNotBeCalled(),
        database_path=database_path,
        minimum_member_count=1,
    ).run(apply=True, manifest_path=manifest_path)

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    assert result["writes_enabled"] is False
    assert result["safety"]["live_trading_enabled"] is True
    assert not database_path.exists()
    assert not manifest_path.exists()


def test_missing_instrument_name_makes_the_catalog_incomplete(tmp_path) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"

    result = InstrumentCatalogRefreshService(
        provider=CatalogWithMissingName(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(apply=True, manifest_path=manifest_path)

    assert result["status"] == "partial"
    assert result["discovery_complete"] is False
    assert result["writes_enabled"] is False
    assert any(
        attempt["segment"] == "bj" and attempt["status"] == "error"
        for attempt in result["attempts"]
    )
    assert not database_path.exists()
    assert not manifest_path.exists()


def test_combined_code_name_fallback_only_fills_failed_segment_with_provenance(
    tmp_path,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"

    result = InstrumentCatalogRefreshService(
        provider=SzPrimaryFailureWithCombinedFallback(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(apply=True, manifest_path=manifest_path)

    assert result["status"] == "completed"
    assert result["discovery_status"] == "complete_external_with_combined_fallback"
    assert result["member_count"] == 5
    assert any(
        attempt["segment"] == "sz_a"
        and attempt["source"] == "akshare.stock_info_sz_name_code.a"
        and attempt["status"] == "error"
        for attempt in result["attempts"]
    )
    assert any(
        attempt == {
            "segment": "sz_a",
            "source": "akshare.stock_info_a_code_name",
            "status": "success_fallback",
            "count": 2,
        }
        for attempt in result["attempts"]
    )
    with MarketHistoryStore(database_path).connect(read_only=True) as connection:
        rows = connection.execute(
            "SELECT symbol, name, exchange FROM instruments ORDER BY symbol"
        ).fetchall()
    assert [dict(row) for row in rows if row["exchange"] == "SZ"] == [
        {"symbol": "SZ000001", "name": "平安银行", "exchange": "SZ"},
        {"symbol": "SZ300001", "name": "特锐德", "exchange": "SZ"},
    ]
    assert "沪市重复" not in [str(row["name"]) for row in rows]


def test_segment_level_drop_is_rejected_even_when_total_retained_ratio_looks_safe(
    tmp_path,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    manifest_path = tmp_path / "current_a_share_universe.json"
    InstrumentCatalogRefreshService(
        provider=SegmentSkewCatalogProvider(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(apply=True, manifest_path=manifest_path)
    previous_manifest = manifest_path.read_bytes()

    result = InstrumentCatalogRefreshService(
        provider=TruncatedBjCatalogProvider(),
        database_path=database_path,
        minimum_member_count=4,
    ).run(apply=True, manifest_path=manifest_path)

    assert result["status"] == "partial"
    assert result["reason"] == "suspicious_segment_count_drop"
    assert result["segment"] == "bj"
    assert result["baseline_member_count"] == 14
    assert result["member_count"] == 13
    assert result["retained_ratio"] > 0.9
    assert result["segment_baseline_count"] == 2
    assert result["segment_member_count"] == 1
    assert result["segment_retained_ratio"] == 0.5
    assert result["writes_enabled"] is False
    assert manifest_path.read_bytes() == previous_manifest
    with MarketHistoryStore(database_path).connect(read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM universe_snapshots").fetchone()[0] == 1
