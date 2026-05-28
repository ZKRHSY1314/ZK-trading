import json
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from app.config import settings
from app.candidates.lifecycle import CandidateLifecycleService
from app.candidates.scoring import CandidateScoringService
from app.data.akshare_provider import AkshareProvider, MarketDataProvider
from app.data.symbols import normalize_a_share_code, with_exchange_prefix
from app.storage.sqlite_store import SQLiteStore


class AutoDiscoveryScanner:
    """Discover fresh candidates from market-wide spot data.

    The scanner is intentionally observation-only. It prioritizes limit-up and
    strong movers, then leaves risk decisions to the candidate scanner,
    phase matcher, and simulation planner.
    """

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        self.provider = provider or AkshareProvider()
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def scan(self, limit: int = 50, persist: bool = True) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 300))
        try:
            spot, source, fallback_error = self._load_spot()
        except Exception as exc:
            return {
                "status": "failed",
                "source": "akshare.stock_zh_a_spot_em",
                "error": str(exc),
                "discovered_count": 0,
                "items": [],
            }

        items = self._extract_items(spot)
        ranked = sorted(items, key=lambda item: (-item["priority"], item["symbol"]))[:safe_limit]
        for item in ranked:
            item["source"] = source
        result = {
            "status": "completed",
            "source": source,
            "fallback_error": fallback_error,
            "total_scanned": int(len(spot)),
            "discovered_count": len(ranked),
            "limit_up_count": len([item for item in ranked if item["discovery_type"] == "limit_up"]),
            "near_limit_up_count": len(
                [item for item in ranked if item["discovery_type"] == "near_limit_up"]
            ),
            "strong_mover_count": len(
                [item for item in ranked if item["discovery_type"] == "strong_mover"]
            ),
            "items": ranked,
        }
        if persist and ranked:
            result["stored_count"] = self._persist(ranked, result["source"])
            CandidateLifecycleService().record_auto_discovery(ranked, result["source"])
            scored = CandidateScoringService().score_symbols(
                [item["symbol"] for item in ranked],
                source="auto_discovery",
            )
            result["scored_count"] = len(scored)
        return result

    def latest(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT id, symbol, name, trade_date, current_price, pct_change,
                   turnover_rate, volume, amount, priority, discovery_type,
                   source, reasons_json, raw_json, created_at
            FROM auto_discovered_candidates
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 300)),),
        )
        result = []
        for row in rows:
            row["reasons"] = json.loads(row.pop("reasons_json") or "[]")
            row["raw"] = json.loads(row.pop("raw_json") or "{}")
            result.append(row)
        return result

    def latest_by_symbol(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT adc.*
            FROM auto_discovered_candidates adc
            JOIN (
                SELECT symbol, MAX(id) AS latest_id
                FROM auto_discovered_candidates
                WHERE created_at = (
                    SELECT MAX(created_at) FROM auto_discovered_candidates
                )
                GROUP BY symbol
            ) latest ON latest.latest_id = adc.id
            ORDER BY adc.priority DESC, adc.id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        )
        result = []
        for row in rows:
            row["reasons"] = json.loads(row.pop("reasons_json") or "[]")
            row["raw"] = json.loads(row.pop("raw_json") or "{}")
            result.append(row)
        return result

    def _extract_items(self, spot: pd.DataFrame) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if spot.empty:
            return items
        for _, row in spot.iterrows():
            raw = row.to_dict()
            code = self._text(raw, "\u4ee3\u7801")
            if not code:
                continue
            try:
                code = normalize_a_share_code(code)
            except ValueError:
                continue
            if not code.startswith(("0", "3", "6")):
                continue
            name = self._text(raw, "\u540d\u79f0")
            if name and name.upper().startswith("N"):
                continue
            pct_change = self._number(raw, "\u6da8\u8dcc\u5e45")
            if pct_change is None or pct_change < 5 or pct_change > 30:
                continue
            symbol = with_exchange_prefix(code)
            current_price = self._number(raw, "\u6700\u65b0\u4ef7")
            turnover_rate = self._number(raw, "\u6362\u624b\u7387")
            amount = self._number(raw, "\u6210\u4ea4\u989d")
            volume = self._number(raw, "\u6210\u4ea4\u91cf")
            discovery_type = self._discovery_type(code, pct_change)
            reasons = self._reasons(discovery_type, pct_change, turnover_rate, amount)
            priority = self._priority(discovery_type, pct_change, turnover_rate, amount)
            items.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "trade_date": date.today().isoformat(),
                    "current_price": current_price,
                    "pct_change": round(float(pct_change), 4),
                    "turnover_rate": turnover_rate,
                    "volume": volume,
                    "amount": amount,
                    "priority": priority,
                    "discovery_type": discovery_type,
                    "source": "akshare.stock_zh_a_spot_em",
                    "reasons": reasons,
                    "raw": self._json_ready(raw),
                }
            )
        return items

    def _load_spot(self) -> tuple[pd.DataFrame, str, str | None]:
        try:
            return self.provider.get_a_share_spot(), "akshare.stock_zh_a_spot_em", None
        except Exception as exc:
            return self._eastmoney_spot(), "eastmoney.push2_fallback", str(exc)

    def _eastmoney_spot(self) -> pd.DataFrame:
        params = {
            "pn": 1,
            "pz": 5000,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f12,f14,f2,f3,f5,f6,f8",
        }
        url = f"https://push2.eastmoney.com/api/qt/clist/get?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = payload.get("data", {}).get("diff", [])
        mapped = []
        for row in rows:
            mapped.append(
                {
                    "\u4ee3\u7801": row.get("f12"),
                    "\u540d\u79f0": row.get("f14"),
                    "\u6700\u65b0\u4ef7": row.get("f2"),
                    "\u6da8\u8dcc\u5e45": row.get("f3"),
                    "\u6210\u4ea4\u91cf": row.get("f5"),
                    "\u6210\u4ea4\u989d": row.get("f6"),
                    "\u6362\u624b\u7387": row.get("f8"),
                }
            )
        return pd.DataFrame(mapped)

    def _discovery_type(self, code: str, pct_change: float) -> str:
        is_twenty_cm = code.startswith(("300", "301", "688"))
        limit_threshold = 19.5 if is_twenty_cm else 9.8
        near_threshold = 15.0 if is_twenty_cm else 8.5
        if pct_change >= limit_threshold:
            return "limit_up"
        if pct_change >= near_threshold:
            return "near_limit_up"
        return "strong_mover"

    def _priority(
        self,
        discovery_type: str,
        pct_change: float,
        turnover_rate: float | None,
        amount: float | None,
    ) -> float:
        type_score = {"limit_up": 100.0, "near_limit_up": 80.0, "strong_mover": 60.0}[discovery_type]
        turnover_score = min(float(turnover_rate or 0), 30.0) * 0.5
        amount_score = min(float(amount or 0) / 100_000_000, 30.0) * 0.25
        return round(type_score + float(pct_change) + turnover_score + amount_score, 4)

    def _reasons(
        self,
        discovery_type: str,
        pct_change: float,
        turnover_rate: float | None,
        amount: float | None,
    ) -> list[str]:
        label = {
            "limit_up": "limit-up priority scan",
            "near_limit_up": "near limit-up priority scan",
            "strong_mover": "strong mover auto discovery",
        }[discovery_type]
        reasons = [label, f"pct_change={pct_change:.2f}%"]
        if turnover_rate is not None:
            reasons.append(f"turnover_rate={turnover_rate:.2f}%")
        if amount is not None:
            reasons.append(f"amount={amount:.0f}")
        return reasons

    def _persist(self, items: list[dict[str, Any]], source: str) -> int:
        with self.store.connect() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT INTO auto_discovered_candidates(
                        symbol, name, trade_date, current_price, pct_change,
                        turnover_rate, volume, amount, priority, discovery_type,
                        source, reasons_json, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.get("symbol"),
                        item.get("name"),
                        item.get("trade_date"),
                        item.get("current_price"),
                        item.get("pct_change"),
                        item.get("turnover_rate"),
                        item.get("volume"),
                        item.get("amount"),
                        item.get("priority"),
                        item.get("discovery_type"),
                        source,
                        json.dumps(item.get("reasons", []), ensure_ascii=False),
                        json.dumps(item.get("raw", {}), ensure_ascii=False, default=str),
                    ),
                )
        return len(items)

    def _text(self, row: dict[str, Any], key: str) -> str | None:
        value = row.get(key)
        if value is None or pd.isna(value):
            return None
        return str(value).strip()

    def _number(self, row: dict[str, Any], key: str) -> float | None:
        value = row.get(key)
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _json_ready(self, row: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in row.items():
            try:
                if pd.isna(value):
                    result[str(key)] = None
                    continue
            except TypeError:
                pass
            result[str(key)] = value.item() if hasattr(value, "item") else value
        return result
