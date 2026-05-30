from typing import Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    def get_a_share_spot(self) -> pd.DataFrame:
        ...

    def get_minute_bars(self, symbol: str, period: str = "1") -> pd.DataFrame:
        ...

    def get_daily_bars(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame:
        ...


class AkshareProvider:
    def get_a_share_spot(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_zh_a_spot_em()

    def get_minute_bars(self, symbol: str, period: str = "1") -> pd.DataFrame:
        import akshare as ak

        return ak.stock_zh_a_hist_min_em(symbol=symbol, period=period, adjust="")

    def get_daily_bars(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame:
        import akshare as ak

        return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust=adjust)
