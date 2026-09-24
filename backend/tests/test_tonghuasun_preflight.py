from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from app.data.tonghuasun_preflight import (
    SOURCE,
    expected_latest_session,
    verify_market_data,
)
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


class _Provider:
    """Returns whatever a real adapter would, so the checks face real shapes."""

    def __init__(self, frame=None, error: Exception | None = None) -> None:
        self._frame = frame
        self._error = error

    def get_daily_bars(self, symbol, adjust="qfq", days=5):
        if self._error is not None:
            raise self._error
        return self._frame


def _frame(*, source=SOURCE, adjust="qfq", latest="2026-09-04", **overrides):
    row = {
        "date": latest,
        "open": 10.0,
        "high": 10.8,
        "low": 9.9,
        "close": 10.6,
        "volume": 1234.0,
        "amount": 1_300_000.0,
    }
    row.update(overrides)
    frame = pd.DataFrame([row])
    frame.attrs["source"] = source
    frame.attrs["adjustment_mode"] = adjust
    return frame


def _verify(frame=None, error=None, now=datetime(2026, 9, 4, 17, 0, tzinfo=SHANGHAI)):
    return verify_market_data(provider=_Provider(frame, error), symbol="600519", now=now)


def test_a_real_candle_is_what_makes_the_session_ready():
    result = _verify(_frame())

    assert result.ready is True
    assert result.source == SOURCE
    assert result.latest_trade_date == "2026-09-04"


def test_unauthorized_blocks_and_keeps_the_reason():
    """The 401 that sent a whole full-market refresh to Sina must stop the run.

    A listening port, a 200 from /health and an existing endpoint.json were all
    true that day; none of them touch the market-data path.
    """

    result = _verify(error=RuntimeError("local Tonghuashun API error [unauthorized]"))

    assert result.ready is False
    assert "unauthorized" in result.failure_reason
    assert [c.name for c in result.checks if not c.passed] == ["authentication"]


def test_a_fallback_source_can_never_report_the_session_as_ready():
    """Sina answering is a fallback, not a Tonghuashun session."""

    result = _verify(_frame(source="akshare.stock_zh_a_daily"))

    assert result.ready is False
    assert result.source == "akshare.stock_zh_a_daily"
    assert any(c.name == "source_is_tonghuasun" and not c.passed for c in result.checks)


def test_an_empty_frame_is_a_failure_not_an_absence_of_history():
    """A throttled host answers with an empty frame instead of an error.

    The cache reads that as "no history" and silently charges the request to the
    next source, so preflight has to name it.
    """

    empty = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
    empty.attrs["source"] = SOURCE
    empty.attrs["adjustment_mode"] = "qfq"

    result = _verify(empty)

    assert result.ready is False
    assert "empty" in result.failure_reason


def test_a_candle_dated_ahead_of_the_last_completed_session_is_rejected():
    # 11:00 on a weekday: today's session is still open, so today's bar is not
    # a completed session and must not be accepted as one.
    result = _verify(
        _frame(latest="2026-09-04"), now=datetime(2026, 9, 4, 11, 0, tzinfo=SHANGHAI)
    )

    assert result.ready is False
    assert any(c.name == "latest_trade_date" and not c.passed for c in result.checks)


def test_a_stale_session_warns_rather_than_blocking():
    """Connected but behind is different from not connected; holidays look like this."""

    result = _verify(_frame(latest="2026-08-01"))

    assert result.ready is True
    assert any("stale" in warning for warning in result.warnings)


def test_adjustment_mode_must_match_what_was_asked_for():
    result = _verify(_frame(adjust="hfq"))

    assert result.ready is False
    assert any(c.name == "adjustment_matches_request" and not c.passed for c in result.checks)


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"amount": None}, "amount is null"),
        ({"volume": -1.0}, "volume is negative"),
        ({"close": 0.0}, "close is zero"),
        ({"high": 1.0}, "OHLC are not internally consistent"),
    ],
)
def test_invalid_price_or_size_fields_block_the_session(overrides, expected):
    result = _verify(_frame(**overrides))

    assert result.ready is False
    detail = next(c.detail for c in result.checks if c.name == "ohlc_volume_amount_valid")
    assert expected in detail


def test_expected_session_walks_back_over_the_weekend_and_the_open_session():
    # Saturday -> Friday.
    assert expected_latest_session(datetime(2026, 9, 5, 10, 0, tzinfo=SHANGHAI)) == date(2026, 9, 4)
    # Weekday before 15:15 -> yesterday, matching the cache's own rule.
    assert expected_latest_session(datetime(2026, 9, 4, 11, 0, tzinfo=SHANGHAI)) == date(2026, 9, 3)
    # Weekday after the close -> today.
    assert expected_latest_session(datetime(2026, 9, 4, 17, 0, tzinfo=SHANGHAI)) == date(2026, 9, 4)
    # Monday morning -> the previous Friday, not Sunday.
    assert expected_latest_session(datetime(2026, 9, 7, 9, 0, tzinfo=SHANGHAI)) == date(2026, 9, 4)
