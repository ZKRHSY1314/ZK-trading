from __future__ import annotations

from typing import Protocol

import pandas as pd


class ReferenceDataProvider(Protocol):
    """External read-only data required by the reference ingest seam."""

    def get_industry_boards(self) -> pd.DataFrame: ...

    def get_industry_members(self, symbol: str) -> pd.DataFrame: ...

    def get_concept_boards(self) -> pd.DataFrame: ...

    def get_concept_members(self, symbol: str) -> pd.DataFrame: ...

    def get_sina_industry_boards(self) -> pd.DataFrame: ...

    def get_sina_industry_members(self, symbol: str) -> pd.DataFrame: ...

    def get_share_buybacks(self) -> pd.DataFrame: ...

    def get_us_daily(self, symbol: str) -> pd.DataFrame: ...

    def get_sox_daily(self) -> pd.DataFrame: ...

    def get_foreign_futures_daily(self, symbol: str) -> pd.DataFrame: ...

    def get_crypto_spot(self) -> pd.DataFrame: ...


class AkshareReferenceProvider:
    """AKShare 1.18.x adapter for Eastmoney reference datasets."""

    def get_industry_boards(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_board_industry_name_em()

    def get_industry_members(self, symbol: str) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_board_industry_cons_em(symbol=symbol)

    def get_concept_boards(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_board_concept_name_em()

    def get_concept_members(self, symbol: str) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_board_concept_cons_em(symbol=symbol)

    def get_sina_industry_boards(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_sector_spot(indicator="新浪行业")

    def get_sina_industry_members(self, symbol: str) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_sector_detail(sector=symbol)

    def get_share_buybacks(self) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_repurchase_em()

    def get_us_daily(self, symbol: str) -> pd.DataFrame:
        import akshare as ak

        return ak.stock_us_daily(symbol=symbol, adjust="qfq")

    def get_sox_daily(self) -> pd.DataFrame:
        import akshare as ak

        return ak.macro_global_sox_index()

    def get_foreign_futures_daily(self, symbol: str) -> pd.DataFrame:
        import akshare as ak

        return ak.futures_foreign_hist(symbol=symbol)

    def get_crypto_spot(self) -> pd.DataFrame:
        import akshare as ak

        return ak.crypto_js_spot()


__all__ = ["AkshareReferenceProvider", "ReferenceDataProvider"]
