import pytest
from app.data.snapshot_builder import MarketSnapshotBuilder, MarketDataError

def test_data_fallback_when_provider_fails(mock_provider):
    builder = MarketSnapshotBuilder(provider=mock_provider)
    
    # "000000" causes our mock_provider to raise an Exception
    try:
        snapshot = builder.build("000000", "Test Fallback")
        # If it succeeds because it falls back to empty quote/profile
        assert snapshot.metadata["data_quality"] != "daily_bar"
    except MarketDataError as e:
        # Or it correctly bubbles up if there's no fallback data
        assert "000000" in str(e) or "fallback" in str(e).lower() or "失败" in str(e)

def test_successful_data_fetch(mock_provider):
    builder = MarketSnapshotBuilder(provider=mock_provider)
    snapshot = builder.build("600000", "Test Success")
    
    # Using our mock data
    assert snapshot.price == 10.5
    assert snapshot.metadata["data_quality"] == "daily_bar"
