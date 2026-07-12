import json
from datetime import datetime
import sqlite3
from typing import Any

from app.config import settings
from app.market_intelligence.models import iso_utc, parse_utc
from app.storage.sqlite_store import SQLiteStore


GLOBAL_MARKET_BARS_REQUIREMENT = {
    "table": "global_market_bars",
    "required_columns": [
        "symbol",
        "asset_class",
        "bar_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
        "available_at",
        "quality_status",
    ],
    "point_in_time_rule": "bar_time <= as_of AND available_at <= as_of",
    "recommended_unique_key": ["symbol", "bar_time", "source"],
}


class MarketRegimeService:
    def __init__(self, store: SQLiteStore | None = None):
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()

    def get_cross_market_features(self, as_of: str) -> dict[str, Any]:
        """Return only global bars that were available at the requested cutoff."""

        parsed_as_of = parse_utc(as_of, field="as_of")
        assert parsed_as_of is not None
        cutoff = iso_utc(parsed_as_of) or str(as_of)
        with self.store.connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (GLOBAL_MARKET_BARS_REQUIREMENT["table"],),
            ).fetchone()
            if not exists:
                return self._missing_cross_market(cutoff, "global_market_bars_missing")
            try:
                rows = conn.execute(
                    """
                    WITH source_ranked AS (
                        SELECT symbol, asset_class, bar_time, close, source, available_at,
                               ROW_NUMBER() OVER (
                                   PARTITION BY symbol, bar_time
                                   ORDER BY datetime(available_at) DESC, source ASC
                               ) AS source_rank
                        FROM global_market_bars
                        WHERE quality_status = 'ready'
                          AND datetime(bar_time) <= datetime(?)
                          AND datetime(available_at) <= datetime(?)
                    ), period_ranked AS (
                        SELECT symbol, asset_class, bar_time, close, source, available_at,
                               ROW_NUMBER() OVER (
                                   PARTITION BY symbol
                                   ORDER BY datetime(bar_time) DESC
                               ) AS period_rank
                        FROM source_ranked
                        WHERE source_rank = 1
                    )
                    SELECT symbol, asset_class, bar_time, close, source, available_at
                    FROM period_ranked
                    WHERE period_rank <= 6
                    ORDER BY symbol ASC, datetime(bar_time) DESC
                    """,
                    (cutoff, cutoff),
                ).fetchall()
            except sqlite3.OperationalError:
                return self._missing_cross_market(cutoff, "global_market_bars_schema_invalid")

        grouped: dict[str, list[Any]] = {}
        for row in rows:
            grouped.setdefault(str(row["symbol"]), []).append(row)
        features: list[dict[str, Any]] = []
        for symbol, symbol_rows in grouped.items():
            latest = symbol_rows[0]
            latest_close = float(latest["close"])
            return_1d = self._period_return(latest_close, symbol_rows, 1)
            return_5d = self._period_return(latest_close, symbol_rows, 5)
            features.append(
                {
                    "symbol": symbol,
                    "asset_class": str(latest["asset_class"]),
                    "bar_time": str(latest["bar_time"]),
                    "available_at": str(latest["available_at"]),
                    "close": latest_close,
                    "return_1d": return_1d,
                    "return_5d": return_5d,
                    "bar_count": len(symbol_rows),
                    "source": str(latest["source"]),
                }
            )
        return {
            "status": "ready" if features else "insufficient_data",
            "as_of": cutoff,
            "features": features,
            "reason": None if features else "no_global_market_bars_at_as_of",
            "required_table": GLOBAL_MARKET_BARS_REQUIREMENT,
            "point_in_time": True,
        }

    @staticmethod
    def _period_return(latest_close: float, rows: list[Any], periods: int) -> float | None:
        if len(rows) <= periods:
            return None
        baseline = float(rows[periods]["close"])
        if baseline == 0:
            return None
        return round(latest_close / baseline - 1.0, 6)

    @staticmethod
    def _missing_cross_market(as_of: str, reason: str) -> dict[str, Any]:
        return {
            "status": "insufficient_data",
            "as_of": as_of,
            "features": [],
            "reason": reason,
            "required_table": GLOBAL_MARKET_BARS_REQUIREMENT,
            "point_in_time": True,
        }

    def get_latest_regime(self, as_of_date: str | None = None) -> dict:
        date_filter = "AND trade_date <= ?" if as_of_date else ""
        params = (as_of_date,) if as_of_date else ()
        with self.store.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM daily_bar_cache
                WHERE lower(symbol) IN ('sh000001', 'sh000300')
                  AND quality_status = 'ready'
                  {date_filter}
                ORDER BY trade_date DESC
                LIMIT 40
                """,
                params,
            ).fetchall()

        if not rows:
            return self._insufficient("missing index history", as_of_date)

        first_symbol = rows[0]["symbol"].lower()
        symbol_rows = [row for row in rows if row["symbol"].lower() == first_symbol]
        if len(symbol_rows) < 5:
            return self._insufficient("not enough index bars", as_of_date)

        latest = symbol_rows[0]
        close = float(latest["close"])
        ma20_window = symbol_rows[: min(20, len(symbol_rows))]
        ma20 = sum(float(row["close"]) for row in ma20_window) / len(ma20_window)
        ma5 = sum(float(row["close"]) for row in symbol_rows[:5]) / 5

        reasons: list[str] = []
        if close > ma20 and ma5 >= ma20:
            regime = "strong"
            reasons.append("index above MA20 with short-term strength")
        elif close < ma20 * 0.95:
            regime = "extreme_risk"
            reasons.append("index is more than 5 percent below MA20")
        elif close < ma20:
            regime = "weak"
            reasons.append("index below MA20")
        else:
            regime = "neutral"
            reasons.append("index near MA20")

        return {
            "regime": regime,
            "confidence": 0.8,
            "reasons": reasons,
            "data_quality": "daily_bar_cache",
            "metrics": {
                "symbol": first_symbol,
                "close": close,
                "ma5": ma5,
                "ma20": ma20,
                "bar_count": len(symbol_rows),
            },
            "as_of_date": as_of_date,
            "updated_at": datetime.now().isoformat(),
        }

    def refresh(self, as_of_date: str | None = None) -> dict:
        regime = self.get_latest_regime(as_of_date)
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO market_regime_snapshots(
                    as_of_date, regime, confidence, data_quality, reasons_json, metrics_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    regime.get("as_of_date") or as_of_date,
                    regime["regime"],
                    regime["confidence"],
                    regime["data_quality"],
                    json.dumps(regime.get("reasons", []), ensure_ascii=False),
                    json.dumps(regime.get("metrics", {}), ensure_ascii=False),
                ),
            )
            regime["id"] = int(cursor.lastrowid)
        return regime

    def latest_saved(self) -> dict | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM market_regime_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return None
        item = dict(row)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
        return item

    def _insufficient(self, reason: str, as_of_date: str | None = None) -> dict:
        return {
            "regime": "insufficient_data",
            "confidence": 0.0,
            "reasons": [reason],
            "data_quality": "insufficient",
            "metrics": {},
            "as_of_date": as_of_date,
            "updated_at": datetime.now().isoformat(),
        }
