"""Auditable market cap and PB inputs for the rule layer.

The rule layer needs ``market_cap_billion`` and ``pb``. Neither exists in
``daily_bar_cache``, and ``stock_profiles`` is empty, so both the backtest and
the live selection path have been running with those gates permanently dark:
the backtest fails the market-cap gate on every bar, and live scoring skips it.

This module supplies both from a single source so the two paths agree.

Accuracy contract — read before trusting a number from here:

* A snapshot records ``total_share`` and ``book_value_per_share`` *as observed
  at ``available_at``*. Values for an earlier ``trade_date`` are reconstructed as
  ``close * total_share`` and ``close / book_value_per_share``.
* Share counts and book value change over time (placements, buybacks, unlocks,
  earnings). The further back the date, the larger the error, and companies that
  delisted are absent entirely. Every derived value is therefore stamped
  ``method="projected_from_snapshot"`` and must never be presented as an
  observed point-in-time fact.
* For A+H listings the vendor's total market cap prices H shares at the A-share
  price, which overstates it.

Historical consumers must pass their decision cutoff to ``resolve``. A snapshot
whose ``available_at`` is later than that cutoff is excluded, so a snapshot
ingested today can no longer leak into an old backtest. This is deliberately a
coarse band-filter input (the rule asks for 50–200亿), not a valuation model.
Replace it with真 point-in-time 股本结构 when that source is reachable; the
resolver interface stays the same.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

import requests

from app.data.symbols import normalize_a_share_code

logger = logging.getLogger(__name__)

TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
BATCH_SIZE = 60
SOURCE = "tencent_qt_snapshot"
METHOD = "projected_from_snapshot"
SHANGHAI = ZoneInfo("Asia/Shanghai")

# Field offsets in the tencent quote payload, verified across 主板 / 创业板 /
# 科创板 / 北交所 / ST on 2026-09-01.
_IDX_NAME = 1
_IDX_PRICE = 3
_IDX_FLOAT_CAP = 44
_IDX_TOTAL_CAP = 45
_IDX_PB = 46
_MIN_FIELDS = 47


@dataclass(frozen=True)
class FundamentalSnapshot:
    symbol: str
    name: str
    as_of: str
    price: float
    market_cap_billion: float | None
    float_cap_billion: float | None
    pb: float | None
    total_share_billion: float | None
    book_value_per_share: float | None
    source: str = SOURCE
    available_at: str | None = None


def tencent_code(symbol: str) -> str:
    code = normalize_a_share_code(symbol)
    if code.startswith(("43", "83", "87", "88", "92")):
        return f"bj{code}"
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _positive(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def parse_quote_line(
    line: str,
    as_of: str,
    *,
    available_at: str | None = None,
) -> FundamentalSnapshot | None:
    if '="' not in line:
        return None
    key, _, body = line.partition('="')
    fields = body.rstrip('";').split("~")
    if len(fields) < _MIN_FIELDS:
        return None
    code = key.strip().replace("v_", "")[2:]
    price = _positive(fields[_IDX_PRICE])
    if price is None:
        return None
    total_cap = _positive(fields[_IDX_TOTAL_CAP])
    pb = _positive(fields[_IDX_PB])
    return FundamentalSnapshot(
        symbol=code,
        name=fields[_IDX_NAME],
        as_of=as_of,
        price=price,
        market_cap_billion=total_cap,
        float_cap_billion=_positive(fields[_IDX_FLOAT_CAP]),
        pb=pb,
        # 亿股; market cap is quoted in 亿元 and price in 元.
        total_share_billion=total_cap / price if total_cap else None,
        book_value_per_share=price / pb if pb else None,
        available_at=available_at,
    )


class TencentFundamentalProvider:
    """Batched read-only quote fetch. No credentials, no order path."""

    def __init__(self, timeout: float = 10.0, session: requests.Session | None = None):
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch(self, symbols: list[str]) -> list[FundamentalSnapshot]:
        out: list[FundamentalSnapshot] = []
        for start in range(0, len(symbols), BATCH_SIZE):
            batch = symbols[start : start + BATCH_SIZE]
            try:
                codes = ",".join(tencent_code(item) for item in batch)
            except ValueError:
                codes = ",".join(
                    tencent_code(item) for item in batch if _safe_code(item)
                )
            if not codes:
                continue
            try:
                response = self.session.get(
                    f"{TENCENT_QUOTE_URL}{codes}", timeout=self.timeout
                )
                response.encoding = "gbk"
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - per-batch isolation
                logger.warning("fundamental batch failed at offset %s: %s", start, exc)
                continue
            # Availability begins only after the response has actually arrived.
            batch_available_at = datetime.now(timezone.utc)
            batch_as_of = batch_available_at.astimezone(SHANGHAI).date().isoformat()
            for line in response.text.strip().splitlines():
                snapshot = parse_quote_line(
                    line,
                    batch_as_of,
                    available_at=batch_available_at.isoformat(),
                )
                if snapshot is not None:
                    out.append(snapshot)
        return out


def _safe_code(symbol: str) -> bool:
    try:
        normalize_a_share_code(symbol)
    except ValueError:
        return False
    return True


class FundamentalsStore:
    """Append-only snapshot store keyed by (symbol, as_of, source)."""

    def __init__(self, store):
        self.store = store

    def upsert(self, snapshots: list[FundamentalSnapshot]) -> int:
        if not snapshots:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                item.symbol,
                item.as_of,
                item.name,
                item.price,
                item.market_cap_billion,
                item.float_cap_billion,
                item.pb,
                item.total_share_billion,
                item.book_value_per_share,
                item.source,
                item.available_at or now,
                now,
            )
            for item in snapshots
        ]
        with self.store.connect() as conn:
            conn.executemany(
                """
                INSERT INTO symbol_fundamental_snapshot (
                    symbol, as_of, name, price, market_cap_billion, float_cap_billion,
                    pb, total_share_billion, book_value_per_share, source,
                    available_at, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol, as_of, source) DO NOTHING
                """,
                rows,
            )
        return len(rows)

    def rows(self, as_of: str | datetime | None = None) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT symbol, as_of, total_share_billion, book_value_per_share,
                   market_cap_billion, pb, source, available_at
            FROM symbol_fundamental_snapshot
            ORDER BY symbol ASC, as_of ASC, available_at ASC
            """,
        )
        if as_of is None:
            return rows
        trade_date, cutoff = _decision_cutoff(as_of)
        return [
            row
            for row in rows
            if str(row.get("as_of") or "") <= trade_date
            and _available_at(row.get("available_at")) <= cutoff
        ]

    def latest_by_symbol(
        self, as_of: str | datetime | None = None
    ) -> dict[str, dict[str, Any]]:
        rows = self.rows(as_of)
        # Later rows win, so the map ends up holding the newest snapshot that
        # was available at the requested cutoff.
        return {row["symbol"]: row for row in rows}


@lru_cache(maxsize=4096)
def _decision_cutoff(value: str | datetime) -> tuple[str, datetime]:
    """Return the Shanghai trade date and exact UTC visibility cutoff.

    A date-only backtest cutoff means the A-share close (15:00 Shanghai), not
    UTC midnight. Timestamp callers retain their exact decision time.
    """

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        if len(text) == 10:
            local_date = datetime.fromisoformat(text).date()
            parsed = datetime.combine(local_date, time(15, 0), tzinfo=SHANGHAI)
        else:
            parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    local = parsed.astimezone(SHANGHAI)
    return local.date().isoformat(), parsed.astimezone(timezone.utc)


@lru_cache(maxsize=32768)
def _available_at(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        # Invalid provenance must fail closed for point-in-time reads.
        return datetime.max.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ResolvedFundamentals:
    market_cap_billion: float | None
    pb: float | None
    method: str | None
    snapshot_as_of: str | None
    snapshot_available_at: str | None
    snapshot_source: str | None


_EMPTY = ResolvedFundamentals(None, None, None, None, None, None)


class FundamentalResolver:
    """Reconstructs market cap / PB for a historical close.

    See the module docstring: these are projections from a current snapshot, not
    observed point-in-time facts. ``method`` is carried through so any consumer
    can label or exclude them.
    """

    def __init__(self, store, as_of: str | datetime | None = None):
        self._by_code: dict[str, list[dict[str, Any]]] = {}
        for row in FundamentalsStore(store).rows(as_of):
            try:
                code = normalize_a_share_code(row["symbol"])
            except ValueError:
                continue
            self._by_code.setdefault(code, []).append(row)

    def __len__(self) -> int:
        return len(self._by_code)

    def visible_symbol_count(self, as_of: str | datetime) -> int:
        return sum(self._visible_row(rows, as_of) is not None for rows in self._by_code.values())

    def resolve(
        self,
        symbol: str,
        close: float,
        *,
        as_of: str | datetime | None = None,
    ) -> ResolvedFundamentals:
        try:
            code = normalize_a_share_code(symbol)
        except ValueError:
            return _EMPTY
        rows = self._by_code.get(code) or []
        row = rows[-1] if as_of is None and rows else self._visible_row(rows, as_of)
        if row is None or not close or close <= 0:
            return _EMPTY
        share = row.get("total_share_billion")
        bvps = row.get("book_value_per_share")
        return ResolvedFundamentals(
            market_cap_billion=round(close * share, 4) if share else None,
            pb=round(close / bvps, 4) if bvps else None,
            method=METHOD,
            snapshot_as_of=row.get("as_of"),
            snapshot_available_at=row.get("available_at"),
            snapshot_source=row.get("source"),
        )

    @staticmethod
    def _visible_row(
        rows: list[dict[str, Any]],
        as_of: str | datetime | None,
    ) -> dict[str, Any] | None:
        if as_of is None:
            return rows[-1] if rows else None
        trade_date, cutoff = _decision_cutoff(as_of)
        for row in reversed(rows):
            if (
                str(row.get("as_of") or "") <= trade_date
                and _available_at(row.get("available_at")) <= cutoff
            ):
                return row
        return None
