from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Iterable


_CACHE_LOCK = Lock()
_CACHE_DATES: frozenset[date] = frozenset()
_CACHE_EXPIRES_AT = datetime.min.replace(tzinfo=timezone.utc)
_CACHE_SOURCE = "weekday_fallback"


def trading_session_age(
    latest_date: date,
    target_date: date,
    *,
    exclude_target_session: bool,
    trading_dates: Iterable[date] | None = None,
) -> tuple[int, str]:
    """Count exchange sessions after latest_date through target_date.

    The current session can be excluded before the daily close is expected.
    An injected calendar keeps unit tests deterministic; production uses the
    AKShare/Sina exchange calendar with a six-hour in-process cache.
    """

    if target_date <= latest_date:
        return 0, "injected" if trading_dates is not None else "not_required"
    if trading_dates is not None:
        sessions = frozenset(trading_dates)
        source = "injected"
    else:
        sessions, source = _cached_exchange_dates()
    if sessions and latest_date >= min(sessions) and target_date <= max(sessions):
        count = sum(1 for value in sessions if latest_date < value <= target_date)
        if exclude_target_session and target_date in sessions:
            count = max(0, count - 1)
        return count, source

    count = sum(
        1
        for offset in range(1, (target_date - latest_date).days + 1)
        if (latest_date + timedelta(days=offset)).weekday() < 5
    )
    if exclude_target_session and target_date.weekday() < 5:
        count = max(0, count - 1)
    return count, "weekday_fallback"


def _cached_exchange_dates() -> tuple[frozenset[date], str]:
    global _CACHE_DATES, _CACHE_EXPIRES_AT, _CACHE_SOURCE

    now = datetime.now(timezone.utc)
    with _CACHE_LOCK:
        if now < _CACHE_EXPIRES_AT:
            return _CACHE_DATES, _CACHE_SOURCE
        try:
            import akshare as ak

            frame = ak.tool_trade_date_hist_sina()
            parsed = frozenset(
                value
                for value in (_parse_date(item) for item in frame["trade_date"].tolist())
                if value is not None
            )
            if not parsed:
                raise ValueError("exchange_calendar_empty")
            _CACHE_DATES = parsed
            _CACHE_SOURCE = "akshare.tool_trade_date_hist_sina"
            _CACHE_EXPIRES_AT = now + timedelta(hours=6)
        except Exception:
            _CACHE_DATES = frozenset()
            _CACHE_SOURCE = "weekday_fallback"
            _CACHE_EXPIRES_AT = now + timedelta(minutes=30)
        return _CACHE_DATES, _CACHE_SOURCE


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
