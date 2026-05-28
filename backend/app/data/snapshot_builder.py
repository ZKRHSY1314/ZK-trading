from datetime import date
from time import sleep
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd

from app.config import settings
from app.data.akshare_provider import AkshareProvider, MarketDataProvider
from app.data.symbols import normalize_a_share_code, with_exchange_prefix
from app.knowledge.repository import KnowledgeRepository
from app.models import MarketSnapshot
from app.storage.sqlite_store import SQLiteStore


class MarketDataError(RuntimeError):
    pass


class MarketSnapshotBuilder:
    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        self.provider = provider or AkshareProvider()
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.repository = KnowledgeRepository(self.store)

    def build(self, symbol: str, name: str | None = None) -> MarketSnapshot:
        code = normalize_a_share_code(symbol)
        prefixed = with_exchange_prefix(code)
        keywords = self.repository.keywords_for_stock(prefixed, name)
        profile = self.repository.best_stock_profile(keywords)

        try:
            hist = self._load_daily_bars(code)
        except MarketDataError as exc:
            quote = self._load_quote_fallback(code)
            if quote:
                return self._fallback_from_quote(prefixed, symbol, name, profile, quote, str(exc))
            if profile:
                return self._fallback_from_profile(prefixed, symbol, name, profile, str(exc))
            raise

        if hist.empty:
            quote = self._load_quote_fallback(code)
            if quote:
                return self._fallback_from_quote(
                    prefixed, symbol, name, profile, quote, "AKShare日线为空"
                )
            if profile:
                return self._fallback_from_profile(prefixed, symbol, name, profile, "AKShare日线为空")
            raise MarketDataError(f"未获取到 {code} 的日线行情")

        hist = hist.sort_values("日期")
        latest = hist.iloc[-1]
        previous = hist.iloc[-2] if len(hist) >= 2 else None

        close = self._float(latest.get("收盘"))
        current_name = name or (profile or {}).get("name")
        volume_ratio = self._volume_ratio(hist)

        return MarketSnapshot(
            symbol=prefixed,
            name=current_name,
            trade_date=self._date(latest.get("日期")),
            price=close,
            pct_change=self._float(latest.get("涨跌幅")),
            high=self._float(latest.get("最高")),
            low=self._float(latest.get("最低")),
            open=self._float(latest.get("开盘")),
            close=close,
            volume=self._float(latest.get("成交量")),
            amount=self._float(latest.get("成交额")),
            pb=self._float((profile or {}).get("pb")),
            historical_high=self._float(hist["最高"].max()),
            metadata={
                "source": "akshare.stock_zh_a_hist",
                "data_quality": "daily_bar",
                "raw_symbol": symbol,
                "code": code,
                "prefixed_symbol": prefixed,
                "previous_close": self._float(previous.get("收盘")) if previous is not None else None,
                "volume_ratio": volume_ratio,
                "five_day_pct": self._five_day_pct(hist),
                "profile_operation_cost_line": (profile or {}).get("operation_cost_line"),
                "profile_sell_target": (profile or {}).get("sell_target"),
                "profile_risk_level": (profile or {}).get("risk_level"),
                "profile_rating": (profile or {}).get("rating"),
            },
        )

    def _load_daily_bars(self, code: str) -> pd.DataFrame:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return self.provider.get_daily_bars(code)
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    sleep(1.5)
        raise MarketDataError(f"AKShare日线接口失败: {last_exc}") from last_exc

    def _fallback_from_profile(
        self,
        prefixed: str,
        raw_symbol: str,
        name: str | None,
        profile: dict[str, Any],
        reason: str,
    ) -> MarketSnapshot:
        current_price = self._float(profile.get("current_price"))
        if current_price is None:
            raise MarketDataError(f"行情接口失败，且本地档案缺少现价: {reason}")

        recent_high = self._float(profile.get("recent_high"))
        historical_high = recent_high or current_price

        return MarketSnapshot(
            symbol=prefixed,
            name=name or profile.get("name"),
            trade_date=None,
            price=current_price,
            pct_change=self._profile_pct(profile.get("pct_change")),
            high=recent_high,
            low=None,
            open=None,
            close=current_price,
            volume=None,
            amount=None,
            pb=self._float(profile.get("pb")),
            historical_high=historical_high,
            metadata={
                "source": "local_stock_profile",
                "data_quality": "fallback_profile",
                "fallback_reason": reason,
                "raw_symbol": raw_symbol,
                "prefixed_symbol": prefixed,
                "volume_ratio": None,
                "five_day_pct": self._profile_pct(profile.get("five_day_pct")),
                "profile_operation_cost_line": profile.get("operation_cost_line"),
                "profile_sell_target": profile.get("sell_target"),
                "profile_risk_level": profile.get("risk_level"),
                "profile_rating": profile.get("rating"),
            },
        )

    def _fallback_from_quote(
        self,
        prefixed: str,
        raw_symbol: str,
        name: str | None,
        profile: dict[str, Any] | None,
        quote: dict[str, Any],
        reason: str,
    ) -> MarketSnapshot:
        price = self._float(quote.get("price"))
        if price is None:
            raise MarketDataError(f"报价兜底缺少现价: {reason}")

        profile = profile or {}
        recent_high = self._float(profile.get("recent_high")) or self._float(quote.get("high"))
        historical_high = recent_high or price
        return MarketSnapshot(
            symbol=prefixed,
            name=name or profile.get("name") or quote.get("name"),
            trade_date=self._date(quote.get("trade_date")),
            price=price,
            pct_change=self._float(quote.get("pct_change")),
            high=self._float(quote.get("high")),
            low=self._float(quote.get("low")),
            open=self._float(quote.get("open")),
            close=price,
            volume=self._float(quote.get("volume")),
            amount=self._float(quote.get("amount")),
            pb=self._float(profile.get("pb")),
            historical_high=historical_high,
            metadata={
                "source": "tencent_quote_fallback",
                "data_quality": "realtime_quote_fallback",
                "fallback_reason": reason,
                "raw_symbol": raw_symbol,
                "prefixed_symbol": prefixed,
                "quote_time": quote.get("quote_time"),
                "previous_close": self._float(quote.get("previous_close")),
                "volume_ratio": None,
                "five_day_pct": self._profile_pct(profile.get("five_day_pct")),
                "profile_operation_cost_line": profile.get("operation_cost_line"),
                "profile_sell_target": profile.get("sell_target"),
                "profile_risk_level": profile.get("risk_level"),
                "profile_rating": profile.get("rating"),
            },
        )

    def _load_quote_fallback(self, code: str) -> dict[str, Any] | None:
        prefix = "sh" if code.startswith("6") else "sz"
        url = f"https://qt.gtimg.cn/q={prefix}{code}"
        try:
            with urlopen(url, timeout=8) as response:
                body = response.read().decode("gbk", errors="ignore")
        except (OSError, URLError):
            return None

        if '="' not in body:
            return None
        payload = body.split('="', 1)[1].split('";', 1)[0]
        fields = payload.split("~")
        if len(fields) < 40:
            return None

        quote_time = fields[30] if len(fields) > 30 else None
        return {
            "name": fields[1].replace(" ", ""),
            "code": fields[2],
            "price": fields[3],
            "previous_close": fields[4],
            "open": fields[5],
            "quote_time": quote_time,
            "trade_date": quote_time[:8] if quote_time and len(quote_time) >= 8 else None,
            "pct_change": fields[32] if len(fields) > 32 else None,
            "high": fields[33] if len(fields) > 33 else None,
            "low": fields[34] if len(fields) > 34 else None,
            "volume": fields[36] if len(fields) > 36 else None,
            "amount": fields[37] if len(fields) > 37 else None,
        }

    def _volume_ratio(self, hist: pd.DataFrame) -> float | None:
        if len(hist) < 6:
            return None
        latest_volume = self._float(hist.iloc[-1].get("成交量"))
        previous_mean = hist.iloc[-6:-1]["成交量"].astype(float).mean()
        if not latest_volume or not previous_mean:
            return None
        return round(latest_volume / previous_mean, 4)

    def _five_day_pct(self, hist: pd.DataFrame) -> float | None:
        if len(hist) < 6:
            return None
        latest_close = self._float(hist.iloc[-1].get("收盘"))
        base_close = self._float(hist.iloc[-6].get("收盘"))
        if not latest_close or not base_close:
            return None
        return round((latest_close - base_close) / base_close * 100, 4)

    def _float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        return float(value)

    def _profile_pct(self, value: Any) -> float | None:
        result = self._float(value)
        if result is None:
            return None
        if abs(result) < 1:
            return round(result * 100, 4)
        return result

    def _date(self, value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        return pd.to_datetime(value).date()
