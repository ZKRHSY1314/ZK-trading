from typing import Protocol

import pandas as pd

# daily_bar_cache stores volume in 手; Sina reports 股.
SHARES_PER_HAND = 100.0


class MarketDataProvider(Protocol):
    def get_sh_main_code_name(self) -> pd.DataFrame: ...

    def get_sh_star_code_name(self) -> pd.DataFrame: ...

    def get_sz_a_code_name(self) -> pd.DataFrame: ...

    def get_bj_code_name(self) -> pd.DataFrame: ...

    def get_a_share_spot(self) -> pd.DataFrame: ...

    def get_a_share_code_name(self) -> pd.DataFrame: ...

    def get_minute_bars(self, symbol: str, period: str = "1") -> pd.DataFrame: ...

    def get_daily_bars(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame: ...

    def get_daily_bars_sina(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame: ...


class AkshareProvider:
    def get_sh_main_code_name(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_info_sh_name_code(symbol="主板A股")

    def get_sh_star_code_name(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_info_sh_name_code(symbol="科创板")

    def get_sz_a_code_name(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_info_sz_name_code(symbol="A股列表")

    def get_bj_code_name(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_info_bj_name_code()

    def get_a_share_spot(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_zh_a_spot_em()

    def get_a_share_code_name(self) -> pd.DataFrame:
        """Return the independent Sina-backed A-share code/name universe."""
        import akshare as ak

        return ak.stock_info_a_code_name()

    def get_minute_bars(self, symbol: str, period: str = "1") -> pd.DataFrame:
        import akshare as ak

        return ak.stock_zh_a_hist_min_em(symbol=symbol, period=period, adjust="")

    def get_daily_bars(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame:
        import akshare as ak

        return ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            adjust=adjust,
            timeout=12,
        )

    def get_daily_bars_sina(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame:
        """Sina-backed daily bars, which report 成交额 that the Tencent feed omits.

        ``stock_zh_a_hist`` reaches eastmoney (push2his); when that host is
        unreachable the chain falls back to Tencent, whose qfq kline carries no
        ``amount`` at all. This source is the only reachable one that does, so
        it exists to keep the execution model on reported liquidity instead of
        the volume x price proxy.

        Sina reports volume in 股 while ``daily_bar_cache`` stores 手 - the unit
        every downstream consumer assumes - so volume is converted here and the
        frame is tagged ``volume_unit="hand"``. The ``turnover`` column is a
        turnover *rate*, not an amount; it is dropped so the bar normalizer
        cannot mistake it for one.
        """

        import akshare as ak

        from app.data.symbols import normalize_a_share_code

        code = normalize_a_share_code(symbol)
        # Beijing carries 43/83/87/88 *and* the newer 92 block; 92xxxx would
        # otherwise be misread as Shanghai because it starts with a 9.
        if code.startswith(("4", "8", "92")):
            prefix = "bj"
        elif code.startswith(("6", "9")):
            prefix = "sh"
        else:
            prefix = "sz"

        frame = ak.stock_zh_a_daily(symbol=f"{prefix}{code}", adjust=adjust)
        if frame is None or frame.empty:
            raise RuntimeError("No history returned or valid bars found")

        frame = frame.drop(columns=["turnover", "outstanding_share"], errors="ignore").copy()
        if "volume" in frame.columns:
            frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce") / SHARES_PER_HAND
        frame.attrs["source"] = "akshare.stock_zh_a_daily"
        frame.attrs["adjustment_mode"] = "qfq" if adjust == "qfq" else "unknown"
        frame.attrs["volume_unit"] = "hand"
        return frame
