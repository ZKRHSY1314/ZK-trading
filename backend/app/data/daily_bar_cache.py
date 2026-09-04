import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from app.config import settings
from app.data.snapshot_builder import MarketSnapshotBuilder
from app.data.symbols import normalize_a_share_code
from app.data.tonghuasun_provider import TonghuasunMarketDataProvider
from app.models import DailyBarCache
from app.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

class DailyBarCacheService:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        if store is None:
            self.store.init()
        self.builder = MarketSnapshotBuilder()
        self.tonghuasun_provider = TonghuasunMarketDataProvider(
            product_home=settings.tonghuasun_product_home or None,
            timeout=settings.tonghuasun_request_timeout_seconds,
            min_request_interval=settings.tonghuasun_min_request_interval_seconds,
        )
        self._write_lock = Lock()

    def refresh_bars(
        self,
        limit: int = 50,
        days: int = 120,
        source_policy: str | None = None,
    ) -> dict[str, Any]:
        """
        Refresh daily bars for top candidate symbols.
        """
        limit = max(1, min(int(limit), 200))
        days = max(1, min(int(days), 500))
        
        candidates = self.store.fetch_all(
            """
            SELECT symbol, MAX(name) AS name, MAX(total_score) AS best_score
            FROM candidate_scores
            GROUP BY symbol
            ORDER BY best_score DESC
            LIMIT ?
            """,
            (limit,)
        )
        
        return self.refresh_symbols(
            [str(row["symbol"]) for row in candidates],
            days=days,
            source_policy=source_policy or settings.daily_bar_source_policy,
        )

    def refresh_symbols(
        self,
        symbols: list[str] | tuple[str, ...],
        days: int = 120,
        source_policy: str | None = None,
        max_workers: int = 5,
    ) -> dict[str, Any]:
        """
        Refresh daily bars for an explicit symbol list.
        Useful when diagnostics find stale symbols outside the top candidate-score slice.
        """
        days = max(1, min(int(days), 500))
        # None means "use the configured source", the same way refresh_bars
        # resolves it. A literal default here silently overrode the setting.
        source_policy = str(
            source_policy or settings.daily_bar_source_policy
        ).strip().lower()
        if source_policy not in {
            "tonghuasun_first",
            "tonghuasun_only",
            "akshare_first",
            "sina_first",
            "sina_only",
            "tencent_first",
            "akshare_only",
            "tencent_only",
        }:
            raise ValueError(f"unsupported daily-bar source policy: {source_policy}")
        max_workers = max(1, min(int(max_workers), 20))
        cleaned_symbols: list[str] = []
        seen: set[str] = set()
        for item in symbols:
            symbol = str(item or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            cleaned_symbols.append(symbol)
            if len(cleaned_symbols) >= 200:
                break

        worker_count = min(max_workers, len(cleaned_symbols))
        if worker_count:
            with ThreadPoolExecutor(
                max_workers=worker_count,
                thread_name_prefix="daily-bar-refresh",
            ) as pool:
                results = list(
                    pool.map(
                        lambda symbol: self._refresh_stock_symbol(
                            symbol,
                            days=days,
                            source_policy=source_policy,
                        ),
                        cleaned_symbols,
                    )
                )
        else:
            results = []
        return {
            "processed": len(results),
            "max_workers": max_workers,
            "summary": self.get_summary(),
            "results": results,
        }

    def _refresh_stock_symbol(
        self,
        symbol: str,
        *,
        days: int,
        source_policy: str | None = None,
    ) -> dict[str, Any]:
        source_policy = str(source_policy or settings.daily_bar_source_policy).strip().lower()
        code = normalize_a_share_code(symbol)
        attempts: list[dict[str, Any]] = []
        source_loaders = {
            "tonghuasun.local.quotes.candle": lambda: (
                self.tonghuasun_provider.get_daily_bars(
                    symbol,
                    adjust="qfq",
                    days=days,
                )
            ),
            "akshare.stock_zh_a_hist": lambda: self.builder.provider.get_daily_bars(code),
            "akshare.stock_zh_a_daily": lambda: (
                self.builder.provider.get_daily_bars_sina(code, adjust="qfq")
            ),
            "tencent.fqkline.qfq": lambda: self._load_tencent_qfq_daily_bars(
                symbol,
                days=days,
            ),
        }
        # Only the tonghuasun and Sina sources report 成交额; Tencent qfq never
        # does, so a chain that falls through to Tencent silently trades
        # reported liquidity for the execution-model proxy. Sina is kept out of
        # the pre-existing chains on purpose: it is reachable where eastmoney is
        # not, so slipping it into the default "akshare_first" would change what
        # every caller fetches. Reach it by asking for it.
        source_order = {
            # 2026-09-03: Sina sits ahead of Tencent here because a fallback to
            # Tencent silently drops 成交额. Verified over 2,260 overlapping days
            # on 40 symbols: the local host and Sina agree exactly on SH/SZ
            # (median relative difference 0), and where they diverge - Beijing
            # 92xxxx only, 7 rows - Tencent as an independent third source backs
            # the local host, so Sina stays a fallback rather than a peer.
            "tonghuasun_first": (
                "tonghuasun.local.quotes.candle",
                "akshare.stock_zh_a_daily",
                "tencent.fqkline.qfq",
                "akshare.stock_zh_a_hist",
            ),
            "tonghuasun_only": ("tonghuasun.local.quotes.candle",),
            "akshare_first": ("akshare.stock_zh_a_hist", "tencent.fqkline.qfq"),
            "sina_first": (
                "akshare.stock_zh_a_daily",
                "tencent.fqkline.qfq",
                "akshare.stock_zh_a_hist",
            ),
            "sina_only": ("akshare.stock_zh_a_daily",),
            "tencent_first": ("tencent.fqkline.qfq", "akshare.stock_zh_a_hist"),
            "akshare_only": ("akshare.stock_zh_a_hist",),
            "tencent_only": ("tencent.fqkline.qfq",),
        }[source_policy]
        valid_bars: list[DailyBarCache] = []
        raw_fallback_bars: list[DailyBarCache] = []
        errors: list[str] = []
        for source in source_order:
            try:
                raw_bars = source_loaders[source]()
                adjustment_mode = "qfq"
                quality_status = "ready"
                effective_source = source
                volume_unit = "hand"
                if isinstance(raw_bars, pd.DataFrame):
                    adjustment_mode = str(
                        raw_bars.attrs.get("adjustment_mode") or adjustment_mode
                    ).lower()
                    effective_source = str(raw_bars.attrs.get("source") or source)
                    volume_unit = str(raw_bars.attrs.get("volume_unit") or volume_unit)
                    if adjustment_mode != "qfq":
                        quality_status = "review_only_unadjusted"
                normalized = self._normalize_bars(
                    raw_bars,
                    days,
                    effective_source,
                    adjustment_mode=adjustment_mode,
                    volume_unit=volume_unit,
                )
                for bar in normalized:
                    bar.quality_status = quality_status
                candidate_bars = [
                    bar for bar in normalized if bar.trade_date and bar.close is not None
                ]
                if not candidate_bars:
                    raise RuntimeError("No history returned or valid bars found")
            except Exception as exc:
                errors.append(f"{source} failed: {exc}")
                attempts.append({"source": source, "status": "failed", "error": str(exc)})
                continue
            if candidate_bars[0].adjustment_mode != "qfq":
                raw_fallback_bars = candidate_bars
                attempts.append(
                    {
                        "source": source,
                        "status": "raw_only_deferred",
                        "adjustment_mode": candidate_bars[0].adjustment_mode,
                    }
                )
                continue
            valid_bars = candidate_bars
            attempts.append({"source": source, "status": "success"})
            break

        if not valid_bars and raw_fallback_bars:
            valid_bars = raw_fallback_bars

        if not valid_bars:
            attempts.append(
                {
                    "source": "sina.cn.kline_daily_fallback",
                    "status": "skipped_unsafe_unknown_adjustment",
                }
            )
            existing_bars = self.get_bars(symbol, limit=days)
            if existing_bars:
                attempts.append({"source": "local_cache", "status": "degraded_cached"})
                with self._write_lock:
                    with self.store.connect() as conn:
                        conn.execute("PRAGMA busy_timeout = 30000")
                        conn.execute(
                            "DELETE FROM daily_bar_cache "
                            "WHERE symbol = ? AND trade_date = 'ERROR'",
                            (symbol,),
                        )
                return {
                    "symbol": symbol,
                    "status": "degraded_cached",
                    "bars_saved": 0,
                    "source": existing_bars[0]["source"] + "_cached",
                    "latest_trade_date": existing_bars[0].get("trade_date"),
                    "error": "remote_refresh_failed_existing_cache_preserved",
                    "attempts": attempts,
                }

            error_msg = "; ".join(errors) or "No history returned or valid bars found"
            self._save_error_bar(symbol, error_msg)
            return {
                "symbol": symbol,
                "status": "error",
                "error": error_msg,
                "attempts": attempts,
            }

        saved_count = self._upsert_bars(symbol, valid_bars)

        return {
            "symbol": symbol,
            "status": (
                "success"
                if valid_bars[0].adjustment_mode == "qfq"
                else "isolated_non_qfq"
            ),
            "bars_saved": saved_count,
            "source": valid_bars[0].source,
            "latest_trade_date": max(bar.trade_date for bar in valid_bars),
            "adjustment_mode": valid_bars[0].adjustment_mode,
            "volume_unit": valid_bars[0].volume_unit,
            "attempts": attempts,
        }

    def refresh_benchmark_bars(
        self,
        symbols: list[str] | tuple[str, ...] | None = None,
        days: int = 500,
    ) -> dict[str, Any]:
        """
        Refresh benchmark index bars used by backtest and off-hour regime checks.
        This is deliberately separate from candidate stock history refresh.
        """
        days = max(1, min(int(days), 1000))
        requested = symbols or ("SH000300", "SH000001")
        normalized_symbols = [self._normalize_benchmark_symbol(symbol) for symbol in requested]

        results: list[dict[str, Any]] = []
        for symbol in normalized_symbols:
            attempts: list[dict[str, Any]] = []
            try:
                raw_bars = self._load_akshare_index_daily_bars(symbol)
                bars = self._normalize_index_bars(raw_bars, days, "akshare.stock_zh_index_daily")
                attempts.append({"source": "akshare.stock_zh_index_daily", "status": "success"})
            except Exception as e1:
                attempts.append({"source": "akshare.stock_zh_index_daily", "status": "failed", "error": str(e1)})
                try:
                    raw_bars = self._load_sina_index_daily_bars(symbol)
                    bars = self._normalize_index_bars(raw_bars, days, "sina.cn.index_kline_daily_fallback")
                    attempts.append({"source": "sina.cn.index_kline_daily_fallback", "status": "success"})
                except Exception as e2:
                    attempts.append(
                        {
                            "source": "sina.cn.index_kline_daily_fallback",
                            "status": "failed",
                            "error": str(e2),
                        }
                    )
                    existing_bars = self.get_bars(symbol, limit=days)
                    if existing_bars:
                        attempts.append({"source": "local_cache", "status": "success"})
                        results.append(
                            {
                                "symbol": symbol,
                                "status": "success",
                                "bars_saved": 0,
                                "source": f"{existing_bars[0]['source']}_cached",
                                "attempts": attempts,
                            }
                        )
                        with self._write_lock:
                            with self.store.connect() as conn:
                                conn.execute("PRAGMA busy_timeout = 30000")
                                conn.execute(
                                    "DELETE FROM daily_bar_cache "
                                    "WHERE symbol = ? AND trade_date = 'ERROR'",
                                    (symbol,),
                                )
                        continue

                    error_msg = f"AKShare index failed: {str(e1)}; Sina index failed: {str(e2)}"
                    self._save_error_bar(symbol, error_msg)
                    results.append({"symbol": symbol, "status": "error", "error": error_msg, "attempts": attempts})
                    continue

            valid_bars = [bar for bar in bars if bar.trade_date and bar.close is not None]
            if not valid_bars:
                error_msg = "No benchmark history returned or valid bars found"
                attempts.append({"source": "validation", "status": "failed", "error": error_msg})
                self._save_error_bar(symbol, error_msg)
                results.append({"symbol": symbol, "status": "error", "error": error_msg, "attempts": attempts})
                continue

            for bar in valid_bars:
                bar.symbol = symbol
            saved_count = self._upsert_bars(symbol, valid_bars)

            results.append(
                {
                    "symbol": symbol,
                    "status": "success",
                    "bars_saved": saved_count,
                    "source": valid_bars[0].source,
                    "attempts": attempts,
                }
            )

        success_count = len([item for item in results if item.get("status") == "success"])
        return {
            "status": "completed" if success_count else "error",
            "processed": len(results),
            "ready_count": success_count,
            "summary": self.get_summary(),
            "results": results,
        }

    def _upsert_bar(self, bar: DailyBarCache) -> None:
        now_str = datetime.now().isoformat(timespec="seconds")
        sql = """
            INSERT INTO daily_bar_cache
            (symbol, trade_date, open, high, low, close, volume, amount, source,
             adjustment_mode, volume_unit, quality_status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount,
                source = excluded.source,
                adjustment_mode = excluded.adjustment_mode,
                volume_unit = excluded.volume_unit,
                quality_status = excluded.quality_status,
                updated_at = excluded.updated_at
            WHERE NOT (
                daily_bar_cache.quality_status = 'ready'
                AND daily_bar_cache.adjustment_mode = 'qfq'
                AND (
                    excluded.quality_status != 'ready'
                    OR excluded.adjustment_mode != 'qfq'
                )
            )
              AND NOT (
                  daily_bar_cache.quality_status = 'ready'
                  AND daily_bar_cache.amount IS NOT NULL
                  AND excluded.amount IS NULL
              )
        """
        with self._write_lock:
            with self.store.connect() as conn:
                conn.execute("PRAGMA busy_timeout = 30000")
                if bar.trade_date != "ERROR":
                    conn.execute(
                        "DELETE FROM daily_bar_cache WHERE symbol = ? AND trade_date = 'ERROR'",
                        (bar.symbol,),
                    )
                conn.execute(sql, (
                    bar.symbol,
                    bar.trade_date,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                    bar.amount,
                    bar.source,
                    bar.adjustment_mode,
                    bar.volume_unit,
                    bar.quality_status,
                    now_str
                ))

    def _upsert_bars(self, symbol: str, bars: list[DailyBarCache]) -> int:
        if not bars:
            return 0
        now_str = datetime.now().isoformat(timespec="seconds")
        sql = """
            INSERT INTO daily_bar_cache
            (symbol, trade_date, open, high, low, close, volume, amount, source,
             adjustment_mode, volume_unit, quality_status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount,
                source = excluded.source,
                adjustment_mode = excluded.adjustment_mode,
                volume_unit = excluded.volume_unit,
                quality_status = excluded.quality_status,
                updated_at = excluded.updated_at
            WHERE NOT (
                daily_bar_cache.quality_status = 'ready'
                AND daily_bar_cache.adjustment_mode = 'qfq'
                AND (
                    excluded.quality_status != 'ready'
                    OR excluded.adjustment_mode != 'qfq'
                )
            )
              AND NOT (
                  daily_bar_cache.quality_status = 'ready'
                  AND daily_bar_cache.amount IS NOT NULL
                  AND excluded.amount IS NULL
              )
        """
        rows = []
        for bar in bars:
            bar.symbol = symbol
            rows.append(
                (
                    symbol,
                    bar.trade_date,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                    bar.amount,
                    bar.source,
                    bar.adjustment_mode,
                    bar.volume_unit,
                    bar.quality_status,
                    now_str,
                )
            )
        with self._write_lock:
            with self.store.connect() as conn:
                conn.execute("PRAGMA busy_timeout = 30000")
                conn.execute(
                    "DELETE FROM daily_bar_cache WHERE symbol = ? AND trade_date = 'ERROR'",
                    (symbol,),
                )
                incomplete_session = self._incomplete_session_date()
                if incomplete_session:
                    conn.execute(
                        "DELETE FROM daily_bar_cache WHERE symbol = ? AND trade_date >= ?",
                        (symbol, incomplete_session),
                    )
                if all(bar.adjustment_mode == "qfq" for bar in bars):
                    conn.execute(
                        """
                        DELETE FROM daily_bar_cache
                        WHERE symbol = ?
                          AND source = 'sina.cn.kline_daily_fallback'
                          AND adjustment_mode = 'unknown'
                        """,
                        (symbol,),
                    )
                conn.executemany(sql, rows)
        return len(rows)

    def _save_error_bar(self, symbol: str, error_message: str) -> None:
        """
        Save a placeholder row indicating an error fetching history for this symbol.
        We use a distinct trade_date like 'ERROR' to store the error state if needed,
        but a better approach is to store it with trade_date='1970-01-01' or similar,
        or just rely on the latest entry.
        For simplicity, we insert a placeholder record with trade_date = 'ERROR' to track status.
        """
        error_bar = DailyBarCache(
            symbol=symbol,
            trade_date="ERROR",
            source="error",
            quality_status="error"
        )
        self._upsert_bar(error_bar)

    def get_coverage(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get a summary of cached history by symbol.
        """
        limit = max(1, min(int(limit), 1000))
        sql = """
            SELECT symbol,
                   COUNT(CASE WHEN trade_date != 'ERROR' AND quality_status = 'ready' THEN 1 END)
                       as cached_bar_count,
                   MIN(CASE WHEN trade_date != 'ERROR' AND quality_status = 'ready'
                       THEN trade_date END) as first_trade_date,
                   MAX(CASE WHEN trade_date != 'ERROR' AND quality_status = 'ready'
                       THEN trade_date END) as last_trade_date,
                   MAX(CASE WHEN trade_date != 'ERROR' AND quality_status = 'ready'
                       THEN source END) as source,
                   CASE
                       WHEN COUNT(CASE WHEN trade_date != 'ERROR' AND quality_status = 'ready'
                           THEN 1 END) > 0 THEN 'ready'
                       WHEN COUNT(CASE WHEN quality_status = 'review_only_unknown_adjustment'
                           THEN 1 END) > 0 THEN 'review_only_unknown_adjustment'
                       WHEN COUNT(CASE WHEN trade_date = 'ERROR' THEN 1 END) > 0 THEN 'error'
                       ELSE 'partial'
                   END as quality_status
            FROM daily_bar_cache
            GROUP BY symbol
            ORDER BY cached_bar_count DESC, symbol ASC
            LIMIT ?
        """
        rows = self.store.fetch_all(sql, (limit,))
        return rows

    def get_bars(self, symbol: str, limit: int = 120) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        sql = """
            SELECT * FROM daily_bar_cache 
            WHERE symbol = ? AND trade_date != 'ERROR' 
            ORDER BY trade_date DESC 
            LIMIT ?
        """
        rows = self.store.fetch_all(sql, (symbol, limit))
        return rows

    def get_summary(self) -> dict[str, int]:
        rows = self.store.fetch_all(
            """
            SELECT quality_status AS status_type, COUNT(*) AS cnt
            FROM (
                SELECT symbol,
                       CASE
                           WHEN COUNT(CASE WHEN trade_date != 'ERROR' AND quality_status = 'ready'
                               THEN 1 END) > 0 THEN 'ready'
                           WHEN COUNT(CASE WHEN quality_status = 'review_only_unknown_adjustment'
                               THEN 1 END) > 0 THEN 'review_only_unknown_adjustment'
                           WHEN COUNT(CASE WHEN trade_date = 'ERROR' THEN 1 END) > 0 THEN 'error'
                           ELSE 'partial'
                       END AS quality_status
                FROM daily_bar_cache
                GROUP BY symbol
            )
            GROUP BY quality_status
            """
        )
        return {row["status_type"]: row["cnt"] for row in rows}

    def _load_tencent_qfq_daily_bars(
        self,
        symbol: str,
        *,
        days: int = 120,
    ) -> pd.DataFrame:
        """Load a forward-adjusted stock series without mixing raw and qfq prices."""

        code = normalize_a_share_code(symbol)
        normalized = str(symbol or "").strip().upper()
        if normalized.startswith("BJ") or code.startswith(("43", "82", "83", "87", "88", "92")):
            prefix = "bj"
        else:
            prefix = "sh" if code.startswith("6") else "sz"
        api_symbol = f"{prefix}{code}"
        request_count = max(120, min(int(days), 500))
        url = (
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
            f"param={api_symbol},day,,,{request_count},qfq"
        )
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(
                    response.read().decode("utf-8", errors="strict")
                )
            if payload.get("code") != 0:
                raise RuntimeError(
                    "Tencent qfq API failed: "
                    f"{payload.get('msg') or payload.get('code')}"
                )
        except Exception as primary_error:
            try:
                return self._load_tencent_newfqkline_qfq_daily_bars(
                    api_symbol,
                    request_count=request_count,
                )
            except Exception as fallback_error:
                raise RuntimeError(
                    "Tencent qfq endpoints failed: "
                    f"fqkline={primary_error}; newfqkline={fallback_error}"
                ) from fallback_error
        symbol_payload = (payload.get("data") or {}).get(api_symbol) or {}
        rows = symbol_payload.get("qfqday")
        adjustment_mode = "qfq"
        if not isinstance(rows, list):
            # ``day`` is raw history. It may be numerically equal to qfq when
            # no corporate action occurred, but provenance must remain explicit.
            raw_rows = symbol_payload.get("day")
            try:
                return self._load_tencent_newfqkline_qfq_daily_bars(
                    api_symbol,
                    request_count=request_count,
                )
            except Exception:
                rows = raw_rows
                adjustment_mode = "none"
        if not isinstance(rows, list):
            raise RuntimeError("Tencent qfq response is missing qfqday/day")

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            normalized_rows.append(
                {
                    "date": row[0],
                    "open": row[1],
                    "close": row[2],
                    "high": row[3],
                    "low": row[4],
                    "volume": row[5],
                    "amount": None,
                }
            )
        frame = pd.DataFrame(normalized_rows)
        frame.attrs["adjustment_mode"] = adjustment_mode
        if adjustment_mode == "none":
            frame.attrs["source"] = "tencent.fqkline.raw"
            try:
                factor_evidence = self._load_sina_unit_qfq_factor_evidence(
                    api_symbol,
                    raw_rows=rows,
                )
            except Exception as exc:
                frame.attrs["factor_verification_status"] = "rejected"
                frame.attrs["factor_verification_error"] = str(exc)
            else:
                frame.attrs["adjustment_mode"] = "qfq"
                frame.attrs["source"] = (
                    "tencent.fqkline.raw+sina.qfq_factor.unit_verified"
                )
                frame.attrs["factor_verification_status"] = "verified"
                frame.attrs["factor_evidence"] = factor_evidence
        return frame

    def _load_sina_unit_qfq_factor_evidence(
        self,
        api_symbol: str,
        *,
        raw_rows: list[Any],
    ) -> dict[str, Any]:
        """Prove that raw prices equal qfq when the complete factor series is unitary."""

        raw_dates = sorted(
            datetime.fromisoformat(str(row[0])[:10]).date()
            for row in raw_rows
            if isinstance(row, list) and row and row[0]
        )
        if not raw_dates:
            raise RuntimeError("Tencent raw series has no valid dates for factor verification")

        cache_buster = int(datetime.now().timestamp() * 1_000)
        url = (
            "https://finance.sina.com.cn/realstock/company/"
            f"{api_symbol}/qfq.js?_={cache_buster}"
        )
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="strict")
        match = re.search(
            rf"\bvar\s+{re.escape(api_symbol)}qfq\s*=\s*(\{{.*?\}})\s*/\*",
            body,
            re.S,
        )
        if match is None:
            raise RuntimeError("Sina qfq factor response is not recognized JSONP")
        payload = json.loads(match.group(1))
        factor_rows = payload.get("data")
        if not isinstance(factor_rows, list) or len(factor_rows) < 2:
            raise RuntimeError("Sina qfq factor history is missing or incomplete")
        if payload.get("total") != len(factor_rows):
            raise RuntimeError("Sina qfq factor total does not match returned history")

        factors: list[tuple[Any, float]] = []
        for row in factor_rows:
            if not isinstance(row, dict) or row.get("d") is None or row.get("f") is None:
                raise RuntimeError("Sina qfq factor row is incomplete")
            try:
                effective_date = datetime.fromisoformat(str(row["d"])[:10]).date()
                factor = float(row["f"])
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Sina qfq factor row is invalid") from exc
            if not math.isfinite(factor) or factor <= 0:
                raise RuntimeError("Sina qfq factor must be finite and positive")
            factors.append((effective_date, factor))

        factor_dates = [item[0] for item in factors]
        if len(set(factor_dates)) != len(factor_dates):
            raise RuntimeError("Sina qfq factor dates are duplicated")
        if min(factor_dates) > raw_dates[0]:
            raise RuntimeError("Sina qfq factor history does not cover the raw horizon")
        if max(factor_dates) > raw_dates[-1]:
            raise RuntimeError("Sina qfq factor history is newer than the raw horizon")
        if any(not math.isclose(factor, 1.0, rel_tol=0.0, abs_tol=1e-12) for _, factor in factors):
            raise RuntimeError("Sina qfq factor history is not unitary")

        return {
            "provider": "sina.qfq_factor",
            "factor_row_count": len(factors),
            "coverage_start": min(factor_dates).isoformat(),
            "coverage_end": max(factor_dates).isoformat(),
            "raw_start": raw_dates[0].isoformat(),
            "raw_end": raw_dates[-1].isoformat(),
            "factor": 1.0,
        }

    def _load_tencent_newfqkline_qfq_daily_bars(
        self,
        api_symbol: str,
        *,
        request_count: int,
    ) -> pd.DataFrame:
        query = urlencode(
            {
                "_var": "kline_dayqfq",
                "param": f"{api_symbol},day,,,{request_count},qfq",
                "r": "0.8205512681390605",
            }
        )
        url = (
            "https://web.ifzq.gtimg.cn/appstock/app/newfqkline/get?"
            f"{query}"
        )
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="strict")
        separator = body.find("=")
        if separator < 0:
            raise RuntimeError("Tencent newfqkline qfq response is not JSONP")
        payload = json.loads(body[separator + 1 :])
        if payload.get("code") != 0:
            raise RuntimeError(
                "Tencent newfqkline qfq API failed: "
                f"{payload.get('msg') or payload.get('code')}"
            )
        rows = ((payload.get("data") or {}).get(api_symbol) or {}).get("qfqday")
        if not isinstance(rows, list):
            raise RuntimeError("Tencent newfqkline response is missing qfqday")
        normalized_rows = [
            {
                "date": row[0],
                "open": row[1],
                "close": row[2],
                "high": row[3],
                "low": row[4],
                "volume": row[5],
                "amount": None,
            }
            for row in rows
            if isinstance(row, list) and len(row) >= 6
        ]
        frame = pd.DataFrame(normalized_rows)
        frame.attrs["adjustment_mode"] = "qfq"
        frame.attrs["source"] = "tencent.newfqkline.qfq"
        return frame

    def _load_sina_daily_bars(self, code: str) -> pd.DataFrame:
        prefix = "sh" if code.startswith("6") else "sz"
        url = (
            "https://quotes.sina.cn/cn/api/jsonp.php/var%20_phaseReplay=/"
            "CN_MarketDataService.getKLineData?"
            f"symbol={prefix}{code}&scale=240&ma=no&datalen=1200"
        )
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
        match = re.search(r"var\s+_phaseReplay=\((.*)\);?", body, re.S)
        if not match:
            raise RuntimeError("Sina JSONP 响应无法解析")
        rows = json.loads(match.group(1))
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        result = pd.DataFrame(
            {
                "日期": frame["day"],
                "开盘": pd.to_numeric(frame["open"], errors="coerce"),
                "收盘": pd.to_numeric(frame["close"], errors="coerce"),
                "最高": pd.to_numeric(frame["high"], errors="coerce"),
                "最低": pd.to_numeric(frame["low"], errors="coerce"),
                "成交量": pd.to_numeric(frame["volume"], errors="coerce"),
                "成交额": None,
            }
        )
        return result

    def _load_akshare_index_daily_bars(self, symbol: str) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_zh_index_daily(symbol=self._benchmark_symbol_to_api_symbol(symbol))

    def _load_sina_index_daily_bars(self, symbol: str) -> pd.DataFrame:
        api_symbol = self._benchmark_symbol_to_api_symbol(symbol)
        url = (
            "https://quotes.sina.cn/cn/api/jsonp.php/var%20_benchmarkReplay=/"
            "CN_MarketDataService.getKLineData?"
            f"symbol={api_symbol}&scale=240&ma=no&datalen=1200"
        )
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
        match = re.search(r"var\s+_benchmarkReplay=\((.*)\);?", body, re.S)
        if not match:
            raise RuntimeError("Sina index JSONP response could not be parsed")
        rows = json.loads(match.group(1))
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        return pd.DataFrame(
            {
                "date": frame["day"],
                "open": pd.to_numeric(frame["open"], errors="coerce"),
                "high": pd.to_numeric(frame["high"], errors="coerce"),
                "low": pd.to_numeric(frame["low"], errors="coerce"),
                "close": pd.to_numeric(frame["close"], errors="coerce"),
                "volume": pd.to_numeric(frame["volume"], errors="coerce"),
            }
        )

    def _normalize_index_bars(self, raw_bars: Any, days: int, source: str) -> list[DailyBarCache]:
        if raw_bars is None or not isinstance(raw_bars, pd.DataFrame) or raw_bars.empty:
            return []
        date_col = self._first_existing_column(raw_bars, ("date", "trade_date"))
        open_col = self._first_existing_column(raw_bars, ("open",))
        high_col = self._first_existing_column(raw_bars, ("high",))
        low_col = self._first_existing_column(raw_bars, ("low",))
        close_col = self._first_existing_column(raw_bars, ("close",))
        volume_col = self._first_existing_column(raw_bars, ("volume",))
        amount_col = self._first_existing_column(raw_bars, ("amount", "turnover"), required=False)
        required = [date_col, open_col, high_col, low_col, close_col, volume_col]
        if any(column is None for column in required):
            raise RuntimeError(f"Unsupported benchmark bar columns: {list(raw_bars.columns)}")

        frame = raw_bars.copy()
        frame["_trade_date"] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame.dropna(subset=["_trade_date"]).sort_values("_trade_date")
        incomplete_session = self._incomplete_session_date()
        if incomplete_session:
            cutoff_date = datetime.fromisoformat(incomplete_session).date()
            frame = frame[frame["_trade_date"].dt.date < cutoff_date]
        frame = frame.tail(days)
        normalized: list[DailyBarCache] = []
        for _, row in frame.iterrows():
            normalized.append(
                DailyBarCache(
                    symbol="",
                    trade_date=row["_trade_date"].date().isoformat(),
                    open=self._float(row.get(open_col)),
                    high=self._float(row.get(high_col)),
                    low=self._float(row.get(low_col)),
                    close=self._float(row.get(close_col)),
                    volume=self._float(row.get(volume_col)),
                    amount=self._float(row.get(amount_col)) if amount_col else None,
                    source=source,
                    adjustment_mode="none",
                    volume_unit="unknown",
                    quality_status="ready",
                )
            )
        return normalized

    def _first_existing_column(
        self,
        frame: pd.DataFrame,
        candidates: tuple[str, ...],
        required: bool = True,
    ) -> str | None:
        for candidate in candidates:
            if candidate in frame.columns:
                return candidate
        if required:
            return None
        return None

    def _normalize_benchmark_symbol(self, symbol: str) -> str:
        raw = str(symbol or "").strip().upper()
        digits = re.sub(r"\D", "", raw)[-6:]
        if len(digits) != 6:
            raise ValueError(f"Unsupported benchmark symbol: {symbol}")
        if raw.startswith("SZ") or digits.startswith("399"):
            return f"SZ{digits}"
        return f"SH{digits}"

    def _benchmark_symbol_to_api_symbol(self, symbol: str) -> str:
        normalized = self._normalize_benchmark_symbol(symbol)
        return normalized.lower()

    def _normalize_bars(
        self,
        raw_bars: Any,
        days: int,
        source: str,
        *,
        adjustment_mode: str = "unknown",
        volume_unit: str = "unknown",
    ) -> list[DailyBarCache]:
        if raw_bars is None:
            return []
        if isinstance(raw_bars, pd.DataFrame):
            if raw_bars.empty:
                return []
            date_col = self._first_existing_column(raw_bars, ("date", "trade_date", "日期"))
            open_col = self._first_existing_column(raw_bars, ("open", "开盘"))
            high_col = self._first_existing_column(raw_bars, ("high", "最高"))
            low_col = self._first_existing_column(raw_bars, ("low", "最低"))
            close_col = self._first_existing_column(raw_bars, ("close", "收盘"))
            volume_col = self._first_existing_column(raw_bars, ("volume", "成交量"))
            amount_col = self._first_existing_column(
                raw_bars,
                ("amount", "turnover", "成交额"),
                required=False,
            )
            required = [date_col, open_col, high_col, low_col, close_col, volume_col]
            if any(column is None for column in required):
                raise RuntimeError(f"Unsupported daily bar columns: {list(raw_bars.columns)}")
            frame = raw_bars.copy()
            frame["_trade_date"] = pd.to_datetime(frame[date_col], errors="coerce")
            frame = frame.dropna(subset=["_trade_date"]).sort_values("_trade_date")
            incomplete_session = self._incomplete_session_date()
            if incomplete_session:
                cutoff_date = datetime.fromisoformat(incomplete_session).date()
                frame = frame[frame["_trade_date"].dt.date < cutoff_date]
            frame = frame.tail(days)
            return [
                DailyBarCache(
                    symbol="",
                    trade_date=row["_trade_date"].date().isoformat(),
                    open=self._float(row.get(open_col)),
                    high=self._float(row.get(high_col)),
                    low=self._float(row.get(low_col)),
                    close=self._float(row.get(close_col)),
                    volume=self._float(row.get(volume_col)),
                    amount=self._float(row.get(amount_col)) if amount_col else None,
                    source=source,
                    adjustment_mode=adjustment_mode,
                    volume_unit=volume_unit,
                    quality_status="ready",
                )
                for _, row in frame.iterrows()
            ]
        bars = raw_bars[-days:] if len(raw_bars) > days else raw_bars
        normalized: list[DailyBarCache] = []
        incomplete_session = self._incomplete_session_date()
        for bar in bars:
            trade_date = (
                bar.trade_date.isoformat()
                if hasattr(bar.trade_date, "isoformat")
                else str(bar.trade_date)[:10]
            )
            if incomplete_session and trade_date >= incomplete_session:
                continue
            normalized.append(
                DailyBarCache(
                    symbol="",
                    trade_date=trade_date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    amount=bar.amount,
                    source=source,
                    adjustment_mode=adjustment_mode,
                    volume_unit=volume_unit,
                    quality_status="ready",
                )
            )
        return normalized

    def _incomplete_session_date(self) -> str | None:
        now = datetime.now().astimezone()
        if now.weekday() < 5 and (now.hour, now.minute) < (15, 15):
            return now.date().isoformat()
        return None

    def _float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        return float(value)

    def _date_str(self, value: Any) -> str:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return str(value)[:10]
        return parsed.date().isoformat()
