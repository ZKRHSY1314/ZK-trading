import json
from datetime import datetime

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


class MarketRegimeService:
    def __init__(self):
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

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
