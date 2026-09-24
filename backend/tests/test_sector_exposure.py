import sqlite3

import pytest

from app.market_intelligence import SectorExposureResolver, SectorMembership
from app.market_intelligence.exposure import membership_hash
from app.storage.sqlite_store import SQLiteStore


def test_sector_membership_is_point_in_time_and_revision_safe(tmp_path):
    store = SQLiteStore(tmp_path / "sector-exposure.sqlite3")
    resolver = SectorExposureResolver(store)
    first = SectorMembership(
        symbol="SH600001",
        sector="semiconductors",
        effective_from="2026-01-01",
        effective_to="2026-06-30",
        source="fixture",
        available_at="2026-01-02T09:00:00+08:00",
        confidence=0.9,
    )
    second = SectorMembership(
        symbol="SH600001",
        sector="ai_compute",
        effective_from="2026-07-01",
        effective_to=None,
        source="fixture",
        available_at="2026-07-01T09:00:00+08:00",
        confidence=0.8,
    )

    assert resolver.record(first)["review_only"] is True
    assert resolver.record(first)["sector"] == "semiconductors"
    resolver.record(second)

    assert resolver.sectors_for("SH600001", as_of="2026-01-01") == []
    assert [item["sector"] for item in resolver.sectors_for("SH600001", as_of="2026-06-01")] == [
        "semiconductors"
    ]
    assert [item["sector"] for item in resolver.sectors_for("SH600001", as_of="2026-07-02")] == [
        "ai_compute"
    ]


def test_sector_membership_rejects_rewriting_same_identity(tmp_path):
    resolver = SectorExposureResolver(SQLiteStore(tmp_path / "immutable.sqlite3"))
    resolver.record(
        SectorMembership(
            symbol="SZ000001",
            sector="oil_gas",
            effective_from="2026-01-01",
            effective_to=None,
            source="fixture",
            available_at="2026-01-01T09:00:00+08:00",
            confidence=0.7,
        )
    )

    with pytest.raises(ValueError, match="immutable"):
        resolver.record(
            SectorMembership(
                symbol="SZ000001",
                sector="oil_gas",
                effective_from="2026-01-01",
                effective_to=None,
                source="fixture",
                available_at="2026-01-01T09:00:00+08:00",
                confidence=0.9,
            )
        )


def test_latest_snapshot_as_of_removes_and_readds_members(tmp_path):
    store = SQLiteStore(tmp_path / "snapshot-asof.sqlite3")
    resolver = SectorExposureResolver(store)

    def record(symbols: list[str], observed_at: str, effective_date: str) -> None:
        resolver.record_snapshot(
            source="fixture-board",
            sector="semiconductors",
            symbols=symbols,
            member_hash=membership_hash(symbols),
            observed_at=observed_at,
            effective_date=effective_date,
            confidence=0.9,
        )

    record(["SH600001", "SZ000002"], "2026-07-12T04:00:00Z", "2026-07-12")
    record(["SH600001"], "2026-07-13T04:00:00Z", "2026-07-13")
    record(["SH600001", "SZ000002"], "2026-07-14T04:00:00Z", "2026-07-14")

    before_removal = resolver.symbols_for("semiconductors", as_of="2026-07-13T03:59:59Z")
    at_removal = resolver.symbols_for("semiconductors", as_of="2026-07-13T04:00:00Z")
    after_readd = resolver.symbols_for("semiconductors", as_of="2026-07-14T04:00:00Z")

    assert [row["symbol"] for row in before_removal] == ["SH600001", "SZ000002"]
    assert [row["symbol"] for row in at_removal] == ["SH600001"]
    assert [row["symbol"] for row in after_readd] == ["SH600001", "SZ000002"]
    assert (
        resolver.sectors_for("SZ000002", as_of="2026-07-13T03:59:59Z")[0]["membership_mode"]
        == "snapshot"
    )
    assert resolver.sectors_for("SZ000002", as_of="2026-07-13T04:00:00Z") == []
    assert (
        resolver.sectors_for_many(["SZ000002"], as_of="2026-07-14T04:00:00Z")["SZ000002"][0][
            "snapshot_id"
        ]
        == after_readd[0]["snapshot_id"]
    )


def test_snapshot_cutoff_preserves_microsecond_precision(tmp_path):
    store = SQLiteStore(tmp_path / "snapshot-microseconds.sqlite3")
    resolver = SectorExposureResolver(store)
    first_symbols = ["SH600001"]
    future_symbols = ["SZ000002"]
    first = resolver.record_snapshot(
        source="fixture-board",
        sector="semiconductors",
        symbols=first_symbols,
        member_hash=membership_hash(first_symbols),
        observed_at="2026-07-12T04:00:00.000001Z",
        effective_date="2026-07-12",
        confidence=0.9,
    )
    resolver.record_snapshot(
        source="fixture-board",
        sector="semiconductors",
        symbols=future_symbols,
        member_hash=membership_hash(future_symbols),
        observed_at="2026-07-12T04:00:00.000002Z",
        effective_date="2026-07-12",
        confidence=0.9,
    )

    rows = resolver.symbols_for(
        "semiconductors",
        as_of="2026-07-12T04:00:00.000001Z",
    )
    latest = resolver.latest_snapshot(
        source="fixture-board",
        sector="semiconductors",
        as_of="2026-07-12T04:00:00.000001Z",
    )

    assert [row["symbol"] for row in rows] == first_symbols
    assert latest is not None
    assert latest["id"] == first["id"]


def test_snapshot_supersedes_same_source_legacy_rows_but_keeps_other_sources(tmp_path):
    store = SQLiteStore(tmp_path / "snapshot-legacy-union.sqlite3")
    resolver = SectorExposureResolver(store)
    for symbol, source in (("SH600001", "fixture-board"), ("SZ000002", "other-source")):
        resolver.record(
            SectorMembership(
                symbol=symbol,
                sector="semiconductors",
                effective_from="2026-01-01",
                effective_to=None,
                source=source,
                available_at="2026-01-01T01:00:00+08:00",
                confidence=0.7,
            )
        )
    resolver.record_snapshot(
        source="fixture-board",
        sector="semiconductors",
        symbols=["SZ000003"],
        member_hash=membership_hash(["SZ000003"]),
        observed_at="2026-07-12T04:00:00Z",
        effective_date="2026-07-12",
        confidence=0.9,
    )

    rows = resolver.symbols_for("semiconductors", as_of="2026-07-12T04:00:00Z")

    assert [(row["symbol"], row["membership_mode"]) for row in rows] == [
        ("SZ000003", "snapshot"),
        ("SZ000002", "legacy_interval"),
    ]


def test_snapshot_batch_rolls_back_if_any_snapshot_conflicts(tmp_path):
    store = SQLiteStore(tmp_path / "snapshot-atomic.sqlite3")
    resolver = SectorExposureResolver(store)
    common = {
        "source": "fixture-board",
        "sector": "semiconductors",
        "observed_at": "2026-07-12T04:00:00Z",
        "effective_date": "2026-07-12",
        "confidence": 0.9,
    }
    first_symbols = ["SH600001"]
    second_symbols = ["SZ000002"]

    with pytest.raises(sqlite3.IntegrityError):
        resolver.record_snapshots(
            [
                {
                    **common,
                    "symbols": first_symbols,
                    "member_hash": membership_hash(first_symbols),
                },
                {
                    **common,
                    "symbols": second_symbols,
                    "member_hash": membership_hash(second_symbols),
                },
            ]
        )

    assert (
        store.fetch_one("SELECT COUNT(*) AS count FROM sector_membership_snapshots")["count"] == 0
    )
    assert (
        store.fetch_one("SELECT COUNT(*) AS count FROM sector_membership_snapshot_members")["count"]
        == 0
    )
