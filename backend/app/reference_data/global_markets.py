from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from app.reference_data.provider import ReferenceDataProvider
from app.storage.sqlite_store import SQLiteStore


SHANGHAI = ZoneInfo("Asia/Shanghai")
NEW_YORK = ZoneInfo("America/New_York")
MINIMUM_DAILY_BARS = 6


@dataclass(frozen=True)
class GlobalMarketBar:
    symbol: str
    asset_class: str
    bar_time: str
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: float | None
    source: str
    available_at: str
    quality_status: str


class GlobalMarketIngestor:
    """Normalize read-only cross-market references into point-in-time bars."""

    def __init__(
        self,
        *,
        store: SQLiteStore,
        provider: ReferenceDataProvider,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.clock = clock

    def run(
        self,
        *,
        apply: bool,
        now: datetime,
        days: int = 30,
        include_sox: bool = True,
        symbol_limit: int | None = None,
    ) -> dict[str, Any]:
        if days < MINIMUM_DAILY_BARS:
            raise ValueError(f"global_days must be at least {MINIMUM_DAILY_BARS}")
        if days > 3660:
            raise ValueError("global_days cannot exceed 3660")
        if symbol_limit is not None and symbol_limit < 1:
            raise ValueError("global_symbol_limit must be positive")

        specs = [
            {
                "symbol": "SMH",
                "asset_class": "equity_etf",
                "source": "akshare.stock_us_daily[qfq]",
                "method": "get_us_daily",
                "argument": "SMH",
                "normalizer": "daily",
                "session": "us_equity",
            },
            {
                "symbol": "NVDA",
                "asset_class": "equity",
                "source": "akshare.stock_us_daily[qfq]",
                "method": "get_us_daily",
                "argument": "NVDA",
                "normalizer": "daily",
                "session": "us_equity",
            },
            {
                "symbol": "CL",
                "asset_class": "commodity_future",
                "source": "akshare.futures_foreign_hist[continuous_unadjusted]",
                "method": "get_foreign_futures_daily",
                "argument": "CL",
                "normalizer": "daily",
                "session": "global_future",
            },
            {
                "symbol": "GC",
                "asset_class": "commodity_future",
                "source": "akshare.futures_foreign_hist[continuous_unadjusted]",
                "method": "get_foreign_futures_daily",
                "argument": "GC",
                "normalizer": "daily",
                "session": "global_future",
            },
            {
                "symbol": "BTC",
                "asset_class": "crypto_future",
                "source": "akshare.futures_foreign_hist[continuous_unadjusted]",
                "method": "get_foreign_futures_daily",
                "argument": "BTC",
                "normalizer": "daily",
                "session": "global_future",
            },
        ]
        if include_sox:
            specs.append(
                {
                    "symbol": "SOX",
                    "asset_class": "equity_index",
                    "source": "akshare.macro_global_sox_index",
                    "method": "get_sox_daily",
                    "argument": None,
                    "normalizer": "sox",
                    "session": "us_equity",
                }
            )
        if symbol_limit is not None:
            specs = specs[:symbol_limit]

        results: list[dict[str, Any]] = []
        all_bars: list[GlobalMarketBar] = []
        errors: list[dict[str, Any]] = []
        callable_sources = 0
        for spec in specs:
            method = getattr(self.provider, str(spec["method"]), None)
            if not callable(method):
                results.append(
                    {
                        "symbol": spec["symbol"],
                        "source": spec["source"],
                        "status": "unsupported",
                        "reason": f"provider capability missing: {spec['method']}",
                        "bars_received": 0,
                        "bars_selected": 0,
                        "freshness": self._freshness(None, now),
                    }
                )
                continue
            callable_sources += 1
            try:
                argument = spec["argument"]
                frame = method(argument) if argument is not None else method()
                retrieved_at = self._retrieved_at(not_before=now)
                if not isinstance(frame, pd.DataFrame):
                    raise TypeError(
                        f"{spec['source']} returned {type(frame).__name__}, expected DataFrame"
                    )
                bars = self._normalize(
                    frame=frame,
                    spec=spec,
                    now=retrieved_at,
                    days=days,
                )
                source_result = self._source_result(
                    spec=spec,
                    frame=frame,
                    bars=bars,
                    now=retrieved_at,
                )
                results.append(source_result)
                all_bars.extend(bars)
            except Exception as exc:
                error = {
                    "stage": "global_market_bars",
                    "symbol": spec["symbol"],
                    "source": spec["source"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                errors.append(error)
                results.append(
                    {
                        "symbol": spec["symbol"],
                        "source": spec["source"],
                        "status": "error",
                        "bars_received": 0,
                        "bars_selected": 0,
                        "freshness": self._freshness(None, now),
                        "error": error,
                    }
                )

        disposition = self._classify_records(all_bars)
        written = 0
        write_error: dict[str, Any] | None = None
        if apply:
            pending_writes = [bar for bar, state in disposition if state != "unchanged"]
            try:
                written = self._insert_immutable_many(pending_writes)
            except sqlite3.Error as exc:
                write_error = {
                    "stage": "global_market_bars_write",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "records_attempted": len(pending_writes),
                    "transaction_rolled_back": True,
                }
                errors.append(write_error)

        state_counts = {
            state: sum(item_state == state for _, item_state in disposition)
            for state in ("new", "revised", "unchanged")
        }
        for result in results:
            symbol_states = [
                state for bar, state in disposition if bar.symbol == result["symbol"]
            ]
            result["records_new"] = symbol_states.count("new")
            result["records_revised"] = symbol_states.count("revised")
            result["records_unchanged"] = symbol_states.count("unchanged")
            result["records_written"] = (
                result["records_new"] + result["records_revised"]
                if apply and write_error is None
                else 0
            )

        fetched = sum(result["status"] not in {"error", "unsupported", "empty"} for result in results)
        ready = sum(result["status"] == "ready" for result in results)
        degraded = sum(
            result["status"]
            in {
                "degraded_provisional",
                "degraded_spot",
                "degraded_stale",
                "insufficient_data",
            }
            for result in results
        )
        failed = sum(result["status"] == "error" for result in results)
        unsupported = sum(result["status"] == "unsupported" for result in results)
        if write_error is not None:
            status = "error"
        elif callable_sources == 0:
            status = "unsupported"
        elif fetched == 0:
            status = "error" if failed else "empty"
        elif failed or degraded or unsupported:
            status = "partial"
        else:
            status = "completed" if apply else "planned"
        freshness_counts: dict[str, int] = {}
        for result in results:
            freshness_status = str(result["freshness"]["status"])
            freshness_counts[freshness_status] = freshness_counts.get(freshness_status, 0) + 1
        return {
            "status": status,
            "minimum_daily_bars": MINIMUM_DAILY_BARS,
            "requested_days": days,
            "include_sox": include_sox,
            "requested_source_count": len(specs),
            "fetched_source_count": fetched,
            "ready_source_count": ready,
            "degraded_source_count": degraded,
            "failed_source_count": failed,
            "unsupported_source_count": unsupported,
            "source_coverage_pct": self._pct(fetched, len(specs)),
            "ready_source_coverage_pct": self._pct(ready, len(specs)),
            "bar_records_planned": len(disposition),
            "bar_records_new": state_counts["new"],
            "bar_records_revised": state_counts["revised"],
            "bar_records_unchanged": state_counts["unchanged"],
            "bar_records_written": written,
            "freshness": dict(sorted(freshness_counts.items())),
            "sources": results,
            "errors": errors,
        }

    def _normalize(
        self,
        *,
        frame: pd.DataFrame,
        spec: dict[str, Any],
        now: datetime,
        days: int,
    ) -> list[GlobalMarketBar]:
        if frame.empty:
            raise ValueError("source frame is empty")
        if spec["normalizer"] == "crypto_spot":
            return self._normalize_crypto_spot(frame=frame, spec=spec, now=now)

        date_column = self._column(frame, ("date", "\u65e5\u671f"))
        close_candidates = (
            ("close", "\u6536\u76d8")
            if spec["normalizer"] == "daily"
            else ("latest_value", "close", "\u6700\u65b0\u503c")
        )
        close_column = self._column(frame, close_candidates)
        open_column = self._column(frame, ("open", "\u5f00\u76d8"), required=False)
        high_column = self._column(frame, ("high", "\u6700\u9ad8"), required=False)
        low_column = self._column(frame, ("low", "\u6700\u4f4e"), required=False)
        volume_column = self._column(frame, ("volume", "\u6210\u4ea4\u91cf"), required=False)
        normalized: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            bar_date = self._date_value(row.get(date_column))
            close = self._number(row.get(close_column))
            if bar_date is None or close is None or close <= 0:
                continue
            open_value = self._number(row.get(open_column)) if open_column else None
            high = self._number(row.get(high_column)) if high_column else None
            low = self._number(row.get(low_column)) if low_column else None
            volume = self._number(row.get(volume_column)) if volume_column else None
            if spec["normalizer"] == "daily" and any(
                value is None or value <= 0 for value in (open_value, high, low)
            ):
                continue
            if spec["normalizer"] == "daily" and not (
                low <= min(open_value, close) <= max(open_value, close) <= high
            ):
                continue
            normalized.append(
                {
                    "date": bar_date,
                    "open": open_value,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
        by_date = {item["date"]: item for item in normalized}
        selected = [by_date[key] for key in sorted(by_date)][-days:]
        if not selected:
            raise ValueError("source contains no valid numeric daily bars")
        freshness = self._freshness(selected[-1]["date"], now)
        if len(selected) < MINIMUM_DAILY_BARS:
            quality = "insufficient_history"
        elif freshness["status"] == "stale":
            quality = "stale"
        else:
            quality = "ready"
        available_at = self._iso_utc(now)
        return [
            GlobalMarketBar(
                symbol=str(spec["symbol"]),
                asset_class=str(spec["asset_class"]),
                bar_time=self._iso_utc(
                    datetime.combine(item["date"], time.min, tzinfo=timezone.utc)
                ),
                open=item["open"],
                high=item["high"],
                low=item["low"],
                close=item["close"],
                volume=item["volume"],
                source=str(spec["source"]),
                available_at=available_at,
                quality_status=(
                    quality
                    if self._daily_bar_is_final(
                        bar_date=item["date"],
                        session=str(spec.get("session") or ""),
                        now=now,
                    )
                    else "provisional"
                ),
            )
            for item in selected
        ]

    def _normalize_crypto_spot(
        self,
        *,
        frame: pd.DataFrame,
        spec: dict[str, Any],
        now: datetime,
    ) -> list[GlobalMarketBar]:
        pair_column = self._column(frame, ("pair", "symbol", "\u4ea4\u6613\u54c1\u79cd"))
        close_column = self._column(frame, ("last", "close", "\u6700\u8fd1\u62a5\u4ef7"))
        updated_column = self._column(frame, ("updated_at", "date", "\u66f4\u65b0\u65f6\u95f4"))
        market_column = self._column(frame, ("market", "\u5e02\u573a"), required=False)
        high_column = self._column(frame, ("high_24h", "24\u5c0f\u65f6\u6700\u9ad8"), required=False)
        low_column = self._column(frame, ("low_24h", "24\u5c0f\u65f6\u6700\u4f4e"), required=False)
        volume_column = self._column(
            frame,
            ("volume_24h", "24\u5c0f\u65f6\u6210\u4ea4\u91cf"),
            required=False,
        )
        candidates: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            if self._text(row.get(pair_column)).upper().replace("/", "") != "BTCUSD":
                continue
            updated = self._datetime_value(row.get(updated_column))
            close = self._number(row.get(close_column))
            if updated is None or close is None or close <= 0:
                continue
            candidates.append(
                {
                    "updated": updated,
                    "close": close,
                    "high": self._number(row.get(high_column)) if high_column else None,
                    "low": self._number(row.get(low_column)) if low_column else None,
                    "volume": self._number(row.get(volume_column)) if volume_column else None,
                    "market": self._text(row.get(market_column)) if market_column else "",
                }
            )
        if not candidates:
            raise ValueError("crypto spot frame contains no valid BTCUSD quote")
        candidates.sort(
            key=lambda item: (
                item["updated"],
                "bitstamp" in item["market"].casefold(),
                item["market"],
            ),
            reverse=True,
        )
        selected = candidates[0]
        freshness = self._freshness(selected["updated"].date(), now)
        quality = "stale_spot" if freshness["status"] == "stale" else "degraded_spot"
        return [
            GlobalMarketBar(
                symbol=str(spec["symbol"]),
                asset_class=str(spec["asset_class"]),
                bar_time=self._iso_utc(selected["updated"]),
                open=None,
                high=selected["high"],
                low=selected["low"],
                close=selected["close"],
                volume=selected["volume"],
                source=str(spec["source"]),
                available_at=self._iso_utc(now),
                quality_status=quality,
            )
        ]

    def _source_result(
        self,
        *,
        spec: dict[str, Any],
        frame: pd.DataFrame,
        bars: list[GlobalMarketBar],
        now: datetime,
    ) -> dict[str, Any]:
        latest = max(datetime.fromisoformat(bar.bar_time.replace("Z", "+00:00")) for bar in bars)
        freshness = self._freshness(latest.date(), now)
        qualities = sorted({bar.quality_status for bar in bars})
        latest_quality = bars[-1].quality_status
        if latest_quality == "provisional":
            status = "degraded_provisional"
        elif spec["normalizer"] == "crypto_spot":
            status = "degraded_spot"
        elif len(bars) < MINIMUM_DAILY_BARS:
            status = "insufficient_data"
        elif freshness["status"] == "stale":
            status = "degraded_stale"
        else:
            status = "ready"
        return {
            "symbol": spec["symbol"],
            "asset_class": spec["asset_class"],
            "source": spec["source"],
            "status": status,
            "bars_received": len(frame),
            "bars_selected": len(bars),
            "latest_bar_time": self._iso_utc(latest),
            "quality_statuses": qualities,
            "freshness": freshness,
            "price_adjustment": (
                "qfq"
                if spec["source"] == "akshare.stock_us_daily[qfq]"
                else "continuous_contract_unadjusted"
                if spec.get("session") == "global_future"
                else "not_applicable"
            ),
        }

    def _classify_records(
        self,
        bars: list[GlobalMarketBar],
    ) -> list[tuple[GlobalMarketBar, str]]:
        if not bars:
            return []
        symbols = sorted({bar.symbol for bar in bars})
        placeholders = ",".join("?" for _ in symbols)
        rows = self.store.fetch_all(
            f"""
            SELECT rowid AS ingest_rowid, symbol, bar_time, asset_class,
                   open, high, low, close, volume, source, available_at,
                   quality_status, julianday(available_at) AS available_jd
            FROM global_market_bars
            WHERE symbol IN ({placeholders})
            ORDER BY available_jd DESC, ingest_rowid DESC
            """,
            tuple(symbols),
        )
        latest: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in rows:
            key = (
                str(row["symbol"]),
                str(row["bar_time"]),
                self._source_family(str(row["source"])),
            )
            latest.setdefault(key, row)

        result: list[tuple[GlobalMarketBar, str]] = []
        for bar in bars:
            existing = latest.get((bar.symbol, bar.bar_time, bar.source))
            if existing is None:
                state = "new"
            elif self._same_payload(existing, bar):
                state = "unchanged"
            else:
                bar = self._revision_bar(bar)
                state = "revised"
            result.append((bar, state))
        return result

    def _insert_immutable_many(self, bars: list[GlobalMarketBar]) -> int:
        if not bars:
            return 0
        with self.store.connect() as conn:
            conn.executemany(
                """
                INSERT INTO global_market_bars(
                    symbol, asset_class, bar_time, open, high, low, close,
                    volume, source, available_at, quality_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        bar.symbol,
                        bar.asset_class,
                        bar.bar_time,
                        bar.open,
                        bar.high,
                        bar.low,
                        bar.close,
                        bar.volume,
                        bar.source,
                        bar.available_at,
                        bar.quality_status,
                    )
                    for bar in bars
                ],
            )
        return len(bars)

    @staticmethod
    def _source_family(source: str) -> str:
        return source.split("#revision-", 1)[0]

    @staticmethod
    def _revision_bar(bar: GlobalMarketBar) -> GlobalMarketBar:
        payload = json.dumps(
            {
                "symbol": bar.symbol,
                "asset_class": bar.asset_class,
                "bar_time": bar.bar_time,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "available_at": bar.available_at,
                "quality_status": bar.quality_status,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
        return replace(bar, source=f"{bar.source}#revision-{payload_hash}")

    @staticmethod
    def _same_payload(existing: dict[str, Any], bar: GlobalMarketBar) -> bool:
        return (
            existing["asset_class"] == bar.asset_class
            and GlobalMarketIngestor._same_number(existing["open"], bar.open)
            and GlobalMarketIngestor._same_number(existing["high"], bar.high)
            and GlobalMarketIngestor._same_number(existing["low"], bar.low)
            and GlobalMarketIngestor._same_number(existing["close"], bar.close)
            and GlobalMarketIngestor._same_number(existing["volume"], bar.volume)
            and existing["quality_status"] == bar.quality_status
        )

    @staticmethod
    def _same_number(left: Any, right: Any) -> bool:
        if left is None or right is None:
            return left is None and right is None
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)

    @staticmethod
    def _column(
        frame: pd.DataFrame,
        candidates: tuple[str, ...],
        *,
        required: bool = True,
    ) -> str | None:
        column = next((candidate for candidate in candidates if candidate in frame.columns), None)
        if column is None and required:
            raise ValueError(
                f"required column missing; expected one of {list(candidates)}, "
                f"received {list(frame.columns)}"
            )
        return column

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        return str(value).strip()

    @staticmethod
    def _date_value(value: Any) -> date | None:
        if value is None:
            return None
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()

    @staticmethod
    def _datetime_value(value: Any) -> datetime | None:
        if value is None:
            return None
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        result = parsed.to_pydatetime()
        if result.tzinfo is None:
            result = result.replace(tzinfo=SHANGHAI)
        return result.astimezone(timezone.utc)

    @staticmethod
    def _freshness(latest: date | None, now: datetime) -> dict[str, Any]:
        if latest is None:
            return {"latest_date": None, "age_days": None, "status": "unknown"}
        age_days = max((now.astimezone(SHANGHAI).date() - latest).days, 0)
        if age_days <= 4:
            status = "fresh"
        elif age_days <= 10:
            status = "recent"
        else:
            status = "stale"
        return {"latest_date": latest.isoformat(), "age_days": age_days, "status": status}

    def _retrieved_at(self, *, not_before: datetime) -> datetime:
        if self.clock is None:
            return not_before
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("global market clock must return a timezone-aware datetime")
        observed = value.astimezone(timezone.utc)
        started = not_before.astimezone(timezone.utc)
        return max(observed, started)

    @staticmethod
    def _daily_bar_is_final(*, bar_date: date, session: str, now: datetime) -> bool:
        if session == "us_equity":
            close_at = datetime.combine(bar_date, time(hour=16, minute=15), tzinfo=NEW_YORK)
            return now.astimezone(timezone.utc) >= close_at.astimezone(timezone.utc)
        if session == "global_future":
            return now.astimezone(SHANGHAI).date() > bar_date
        return True

    @staticmethod
    def _iso_utc(value: datetime) -> str:
        if value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _pct(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator * 100.0, 2)


__all__ = ["GlobalMarketBar", "GlobalMarketIngestor", "MINIMUM_DAILY_BARS"]
