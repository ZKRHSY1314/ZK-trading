import pytest

from app.market_intelligence import SectorExposureResolver, SectorMembership
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
    assert [
        item["sector"]
        for item in resolver.sectors_for("SH600001", as_of="2026-06-01")
    ] == ["semiconductors"]
    assert [
        item["sector"]
        for item in resolver.sectors_for("SH600001", as_of="2026-07-02")
    ] == ["ai_compute"]


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
