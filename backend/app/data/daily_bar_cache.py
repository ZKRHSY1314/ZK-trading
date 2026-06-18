import json
import logging
import re
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from app.config import settings
from app.data.snapshot_builder import MarketDataError, MarketSnapshotBuilder
from app.data.symbols import normalize_a_share_code
from app.models import DailyBarCache
from app.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

class DailyBarCacheService:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()
        self.builder = MarketSnapshotBuilder()

    def refresh_bars(self, limit: int = 50, days: int = 120) -> dict[str, Any]:
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
        
        results = []
        for row in candidates:
            symbol = row["symbol"]
            code = normalize_a_share_code(symbol)
            attempts = []
            
            try:
                raw_bars = self.builder.provider.get_daily_bars(code)
                bars = self._normalize_bars(raw_bars, days, "akshare.stock_zh_a_hist")
                attempts.append({"source": "akshare.stock_zh_a_hist", "status": "success"})
            except Exception as e1:
                attempts.append({"source": "akshare.stock_zh_a_hist", "status": "failed", "error": str(e1)})
                try:
                    raw_bars = self._load_sina_daily_bars(code)
                    bars = self._normalize_bars(raw_bars, days, "sina.cn.kline_daily_fallback")
                    attempts.append({"source": "sina.cn.kline_daily_fallback", "status": "success"})
                except Exception as e2:
                    attempts.append({"source": "sina.cn.kline_daily_fallback", "status": "failed", "error": str(e2)})
                    
                    # Fallback to local cache if possible
                    existing_bars = self.get_bars(symbol, limit=days)
                    if existing_bars:
                        attempts.append({"source": "local_cache", "status": "success"})
                        results.append({
                            "symbol": symbol,
                            "status": "success",
                            "bars_saved": 0,
                            "source": existing_bars[0]["source"] + "_cached",
                            "attempts": attempts
                        })
                        # Remove error row if any exists
                        with self.store.connect() as conn:
                            conn.execute(
                                "DELETE FROM daily_bar_cache WHERE symbol = ? AND trade_date = 'ERROR'",
                                (symbol,)
                            )
                        continue
                    
                    error_msg = f"AKShare failed: {str(e1)}; Sina failed: {str(e2)}"
                    self._save_error_bar(symbol, error_msg)
                    results.append({"symbol": symbol, "status": "error", "error": error_msg, "attempts": attempts})
                    continue

            # Drop invalid bars
            valid_bars = [b for b in bars if b.trade_date and b.close is not None]
            
            if not valid_bars:
                error_msg = "No history returned or valid bars found"
                attempts.append({"source": "validation", "status": "failed", "error": error_msg})
                self._save_error_bar(symbol, error_msg)
                results.append({"symbol": symbol, "status": "error", "error": "No history returned", "attempts": attempts})
                continue
            
            saved_count = 0
            for bar in valid_bars:
                bar.symbol = symbol
                self._upsert_bar(bar)
                saved_count += 1
                
            results.append({"symbol": symbol, "status": "success", "bars_saved": saved_count, "source": valid_bars[0].source, "attempts": attempts})
                
        summary = self.get_summary()
        return {
            "processed": len(results),
            "summary": summary,
            "results": results
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
                        with self.store.connect() as conn:
                            conn.execute(
                                "DELETE FROM daily_bar_cache WHERE symbol = ? AND trade_date = 'ERROR'",
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

            saved_count = 0
            for bar in valid_bars:
                bar.symbol = symbol
                self._upsert_bar(bar)
                saved_count += 1

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
            (symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount,
                source = excluded.source,
                quality_status = excluded.quality_status,
                updated_at = excluded.updated_at
        """
        with self.store.connect() as conn:
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
                bar.quality_status,
                now_str
            ))

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
                   COUNT(CASE WHEN trade_date != 'ERROR' THEN 1 END) as cached_bar_count,
                   MIN(CASE WHEN trade_date != 'ERROR' THEN trade_date END) as first_trade_date,
                   MAX(CASE WHEN trade_date != 'ERROR' THEN trade_date END) as last_trade_date,
                   MAX(CASE WHEN trade_date != 'ERROR' THEN source END) as source,
                   CASE
                       WHEN COUNT(CASE WHEN trade_date != 'ERROR' THEN 1 END) > 0 THEN 'ready'
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
                           WHEN COUNT(CASE WHEN trade_date != 'ERROR' THEN 1 END) > 0 THEN 'ready'
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
        frame = frame.dropna(subset=["_trade_date"]).sort_values("_trade_date").tail(days)
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

    def _normalize_bars(self, raw_bars: Any, days: int, source: str) -> list[DailyBarCache]:
        if raw_bars is None:
            return []
        if isinstance(raw_bars, pd.DataFrame):
            if raw_bars.empty:
                return []
            frame = raw_bars.sort_values("日期").tail(days)
            return [
                DailyBarCache(
                    symbol="",
                    trade_date=self._date_str(row.get("日期")),
                    open=self._float(row.get("开盘")),
                    high=self._float(row.get("最高")),
                    low=self._float(row.get("最低")),
                    close=self._float(row.get("收盘")),
                    volume=self._float(row.get("成交量")),
                    amount=self._float(row.get("成交额")),
                    source=source,
                    quality_status="ready",
                )
                for _, row in frame.iterrows()
            ]
        bars = raw_bars[-days:] if len(raw_bars) > days else raw_bars
        normalized: list[DailyBarCache] = []
        for bar in bars:
            normalized.append(
                DailyBarCache(
                    symbol="",
                    trade_date=bar.trade_date.isoformat() if hasattr(bar.trade_date, 'isoformat') else str(bar.trade_date)[:10],
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    amount=bar.amount,
                    source=source,
                    quality_status="ready",
                )
            )
        return normalized

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
