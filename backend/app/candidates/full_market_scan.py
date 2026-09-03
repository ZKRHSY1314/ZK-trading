from __future__ import annotations

from datetime import date
import hashlib
import json
import statistics
import time
from typing import Any

from app.config import settings
from app.data.market_history import MarketHistoryStore
from app.storage.sqlite_store import SQLiteStore


SOURCE = "full_market_consolidation_v1"
FEATURE_VERSION = "consolidation_features.v1"


class FullMarketFeatureScanner:
    """Score the official qfq universe and persist review-only candidate evidence."""

    def __init__(
        self,
        *,
        store: SQLiteStore | None = None,
        history_store: MarketHistoryStore | None = None,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        if store is None:
            self.store.init()
        self.history_store = history_store or MarketHistoryStore()

    def run(
        self,
        *,
        limit: int = 300,
        min_bars: int = 60,
        lookback: int = 120,
        max_stale_days: int = 5,
        as_of_date: str | None = None,
        persist: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        if settings.enable_live_trading:
            return self._blocked_result()
        safe_limit = max(1, min(int(limit), 500))
        safe_min_bars = max(40, min(int(min_bars), 250))
        safe_lookback = max(safe_min_bars, min(int(lookback), 500))
        started = time.monotonic()

        snapshot, members = self._official_universe(as_of_date=as_of_date)
        cutoff = str(as_of_date or snapshot["snapshot_date"])
        cutoff_date = date.fromisoformat(cutoff)
        scored: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        qfq_ready_count = 0
        computed_count = 0
        reused_count = 0
        existing_states = self._existing_states()

        with self.history_store.connect(read_only=True) as connection:
            for member in members:
                aggregate = connection.execute(
                    """
                    SELECT MAX(trade_date) AS latest_trade_date,
                           MAX(updated_at) AS latest_updated_at,
                           COUNT(*) AS bar_count,
                           (
                               SELECT latest.row_hash
                               FROM daily_bars AS latest
                               WHERE latest.symbol = ?
                                 AND latest.adjustment_mode = 'qfq'
                                 AND latest.quality_status = 'ready'
                                 AND date(latest.trade_date) <= date(?)
                               ORDER BY latest.trade_date DESC
                               LIMIT 1
                           ) AS latest_row_hash
                    FROM daily_bars AS aggregate_bar
                    WHERE aggregate_bar.symbol = ?
                      AND adjustment_mode = 'qfq'
                      AND quality_status = 'ready'
                      AND date(trade_date) <= date(?)
                    """,
                    (member["symbol"], cutoff, member["symbol"], cutoff),
                ).fetchone()
                bar_count = int(aggregate["bar_count"] or 0)
                if bar_count <= 0:
                    gaps.append({**member, "reason": "qfq_history_missing"})
                    continue
                qfq_ready_count += 1
                latest_date = date.fromisoformat(str(aggregate["latest_trade_date"]))
                stale_days = max(0, (cutoff_date - latest_date).days)
                if stale_days > max(0, int(max_stale_days)):
                    gaps.append(
                        {
                            **member,
                            "reason": "qfq_history_stale",
                            "latest_trade_date": latest_date.isoformat(),
                            "stale_days": stale_days,
                        }
                    )
                    continue
                if bar_count < safe_min_bars:
                    gaps.append(
                        {
                            **member,
                            "reason": "insufficient_bars",
                            "bar_count": bar_count,
                            "minimum_bars": safe_min_bars,
                        }
                    )
                    continue
                input_revision = self._input_revision(
                    member=member,
                    snapshot_id=int(snapshot["id"]),
                    cutoff=cutoff,
                    latest_trade_date=str(aggregate["latest_trade_date"]),
                    latest_updated_at=str(aggregate["latest_updated_at"] or ""),
                    latest_row_hash=str(aggregate["latest_row_hash"] or ""),
                    bar_count=bar_count,
                    lookback=safe_lookback,
                    min_bars=safe_min_bars,
                )
                previous = existing_states.get(str(member["symbol"]))
                if (
                    not force
                    and previous is not None
                    and previous.get("input_revision") == input_revision
                ):
                    scored.append(self._state_item(previous))
                    reused_count += 1
                    continue
                rows = [
                    dict(row)
                    for row in connection.execute(
                        """
                        SELECT trade_date, open, high, low, close, volume, amount,
                               provider, available_at, quality_status
                        FROM daily_bars
                        WHERE symbol = ?
                          AND adjustment_mode = 'qfq'
                          AND quality_status = 'ready'
                          AND date(trade_date) <= date(?)
                        ORDER BY trade_date DESC
                        LIMIT ?
                        """,
                        (member["symbol"], cutoff, safe_lookback),
                    ).fetchall()
                ]
                rows.reverse()
                item = self.score_bars(member, rows)
                item["input_revision"] = input_revision
                item["bars_count"] = bar_count
                scored.append(item)
                computed_count += 1

        scored.sort(key=lambda item: (-item["score"], item["symbol"]))
        selected = [item for item in scored if item["tier"] != "rejected"][:safe_limit]
        selected = self._attach_calibration(selected)
        counts = {
            "strong": sum(item["tier"] == "strong" for item in scored),
            "watch": sum(item["tier"] == "watch" for item in scored),
            "rejected": sum(item["tier"] == "rejected" for item in scored),
        }
        duration_seconds = round(time.monotonic() - started, 3)
        result: dict[str, Any] = {
            "status": "completed",
            "schema_version": "full_market_feature_scan.v1",
            "feature_version": FEATURE_VERSION,
            "probability_semantics": "uncalibrated_structure_score",
            "source": SOURCE,
            "as_of_date": cutoff,
            "universe_snapshot_id": int(snapshot["id"]),
            "universe_count": len(members),
            "qfq_ready_count": qfq_ready_count,
            "eligible_count": len(scored),
            "excluded_count": len(gaps),
            "selected_count": len(selected),
            "tier_counts": counts,
            "duration_seconds": duration_seconds,
            "incremental": {
                "computed_count": computed_count,
                "reused_count": reused_count,
            },
            "parameters": {
                "limit": safe_limit,
                "min_bars": safe_min_bars,
                "lookback": safe_lookback,
                "max_stale_days": max(0, int(max_stale_days)),
                "force": bool(force),
            },
            "items": selected,
            "data_gaps": gaps,
            "safety": self._safety(),
        }
        if persist:
            result.update(self._persist(result=result, scored=scored, selected=selected))
        return result

    def latest(self, *, limit: int = 300, tier: str | None = None) -> dict[str, Any]:
        run_row = self.store.fetch_one(
            """
            SELECT id, status, source, feature_version, as_of_date, summary_json,
                   created_at, completed_at
            FROM full_market_feature_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if run_row is None:
            return {
                "status": "missing",
                "run": None,
                "candidate_count": 0,
                "candidates": [],
                "safety": self._safety(),
            }
        try:
            run_summary = json.loads(str(run_row.pop("summary_json") or "{}"))
        except json.JSONDecodeError:
            run_summary = {}
        run = {**run_summary, **run_row}
        where = "WHERE is_candidate = 1"
        params: list[Any] = []
        if tier:
            where += " AND tier = ?"
            params.append(str(tier))
        params.append(max(1, min(int(limit), 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT symbol, name, exchange, trade_date, current_price, pct_change,
                   volume, amount, score, tier, discovery_type, reasons_json,
                   features_json, updated_at
            FROM full_market_feature_state
            {where}
            ORDER BY score DESC, symbol
            LIMIT ?
            """,
            tuple(params),
        )
        candidates = []
        for row in rows:
            try:
                row["reasons"] = json.loads(str(row.pop("reasons_json") or "[]"))
            except json.JSONDecodeError:
                row["reasons"] = []
            try:
                row["features"] = json.loads(str(row.pop("features_json") or "{}"))
            except json.JSONDecodeError:
                row["features"] = {}
            candidates.append(row)
        candidates = self._attach_calibration(candidates)
        return {
            "status": str(run_row.get("status") or "completed"),
            "run": run,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "safety": self._safety(),
        }

    def _attach_calibration(
        self,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        # Local import avoids a module cycle: the calibration service deliberately
        # reuses this scanner's public score_bars() implementation.
        from app.candidates.full_market_score_calibration import (
            FullMarketScoreCalibrationService,
        )

        calibration = FullMarketScoreCalibrationService(
            store=self.store,
            history_store=self.history_store,
        )
        enriched: list[dict[str, Any]] = []
        for item in items:
            score = float(item["score"])
            enriched.append(
                {
                    **item,
                    "score_semantics": "uncalibrated_structure_score",
                    "probability_semantics": "limited_historical_calibration",
                    "calibration": calibration.map_score(score),
                }
            )
        return enriched

    def _official_universe(
        self,
        *,
        as_of_date: str | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if not self.history_store.database_path.exists():
            raise FileNotFoundError(
                f"market history database not found: {self.history_store.database_path}"
            )
        with self.history_store.connect(read_only=True) as connection:
            if as_of_date:
                row = connection.execute(
                    """
                    SELECT id, snapshot_date, member_count, provider
                    FROM universe_snapshots
                    WHERE universe_name = 'a_share_full_market_cache'
                      AND date(snapshot_date) <= date(?)
                    ORDER BY date(snapshot_date) DESC, id DESC
                    LIMIT 1
                    """,
                    (as_of_date,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT id, snapshot_date, member_count, provider
                    FROM universe_snapshots
                    WHERE universe_name = 'a_share_full_market_cache'
                    ORDER BY date(snapshot_date) DESC, id DESC
                    LIMIT 1
                    """
                ).fetchone()
            if row is None:
                raise RuntimeError("official_full_market_universe_missing")
            snapshot = dict(row)
            members = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT member.symbol, instrument.name, instrument.exchange
                    FROM universe_members member
                    JOIN instruments instrument ON instrument.symbol = member.symbol
                    WHERE member.snapshot_id = ?
                      AND instrument.asset_type = 'stock'
                      AND instrument.status = 'active'
                    ORDER BY member.symbol
                    """,
                    (snapshot["id"],),
                ).fetchall()
            ]
        return snapshot, members

    def _existing_states(self) -> dict[str, dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT symbol, name, exchange, trade_date, current_price, pct_change,
                   volume, amount, score, tier, discovery_type, reasons_json,
                   features_json, input_revision, bars_count
            FROM full_market_feature_state
            WHERE feature_version = ?
            """,
            (FEATURE_VERSION,),
        )
        return {str(row["symbol"]): row for row in rows}

    @staticmethod
    def _state_item(row: dict[str, Any]) -> dict[str, Any]:
        try:
            reasons = json.loads(str(row.get("reasons_json") or "[]"))
        except json.JSONDecodeError:
            reasons = []
        try:
            features = json.loads(str(row.get("features_json") or "{}"))
        except json.JSONDecodeError:
            features = {}
        return {
            "symbol": str(row["symbol"]),
            "name": row.get("name"),
            "exchange": row.get("exchange"),
            "trade_date": str(row["trade_date"]),
            "current_price": float(row["current_price"]),
            "pct_change": float(row.get("pct_change") or 0),
            "volume": float(row.get("volume") or 0),
            "amount": float(row.get("amount") or 0),
            "score": float(row["score"]),
            "tier": str(row["tier"]),
            "discovery_type": str(row["discovery_type"]),
            "reasons": reasons,
            "features": features,
            "input_revision": str(row["input_revision"]),
            "bars_count": int(row["bars_count"]),
        }

    @staticmethod
    def _input_revision(
        *,
        member: dict[str, Any],
        snapshot_id: int,
        cutoff: str,
        latest_trade_date: str,
        latest_updated_at: str,
        latest_row_hash: str,
        bar_count: int,
        lookback: int,
        min_bars: int,
    ) -> str:
        payload = "|".join(
            (
                str(member["symbol"]),
                str(member.get("name") or ""),
                str(member.get("exchange") or ""),
                str(snapshot_id),
                cutoff,
                latest_trade_date,
                latest_updated_at,
                latest_row_hash,
                str(bar_count),
                FEATURE_VERSION,
                str(lookback),
                str(min_bars),
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def score_bars(
        self,
        member: dict[str, Any],
        bars: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply the versioned full-market structure score to point-in-time bars."""
        closes = [float(row["close"]) for row in bars]
        highs = [float(row["high"]) for row in bars]
        lows = [float(row["low"]) for row in bars]
        volumes = [float(row.get("volume") or 0) for row in bars]
        latest = bars[-1]
        close = closes[-1]
        returns = [
            (closes[index] / closes[index - 1] - 1.0) * 100
            for index in range(1, len(closes))
            if closes[index - 1] > 0
        ]

        range_20 = self._range_pct(highs[-20:], lows[-20:])
        range_60 = self._range_pct(highs[-60:], lows[-60:])
        volatility_20 = statistics.pstdev(returns[-20:]) if len(returns) >= 2 else 0.0
        true_ranges = []
        for index in range(max(1, len(bars) - 14), len(bars)):
            previous_close = closes[index - 1]
            true_ranges.append(
                max(
                    highs[index] - lows[index],
                    abs(highs[index] - previous_close),
                    abs(lows[index] - previous_close),
                )
            )
        atr_14_pct = (sum(true_ranges) / len(true_ranges) / close * 100) if true_ranges else 0.0
        average_volume_5 = self._mean(volumes[-5:])
        average_volume_20 = self._mean(volumes[-20:])
        volume_ratio_5_20 = (
            average_volume_5 / average_volume_20 if average_volume_20 > 0 else None
        )
        ma_20 = self._mean(closes[-20:])
        ma_60 = self._mean(closes[-60:])
        prior_high_60 = max(highs[-60:-1] or highs[-60:])
        breakout_gap_60 = max(0.0, (prior_high_60 / close - 1.0) * 100)
        return_20 = (close / closes[-21] - 1.0) * 100 if len(closes) >= 21 else 0.0
        low_60 = min(lows[-60:])
        high_60 = max(highs[-60:])
        close_position_60 = (
            (close - low_60) / (high_60 - low_60) * 100
            if high_60 > low_60
            else 50.0
        )

        score = 0.0
        score += self._scaled_inverse(range_20, best=3.0, worst=20.0, weight=30.0)
        score += self._scaled_inverse(volatility_20, best=0.5, worst=5.0, weight=20.0)
        score += self._scaled_inverse(atr_14_pct, best=1.0, worst=6.0, weight=15.0)
        score += self._scaled_inverse(breakout_gap_60, best=1.0, worst=15.0, weight=15.0)
        if close >= ma_20:
            score += 8.0
        if ma_20 >= ma_60 * 0.98:
            score += 7.0
        if volume_ratio_5_20 is not None:
            if 0.45 <= volume_ratio_5_20 <= 0.95:
                score += 5.0
            elif volume_ratio_5_20 <= 1.15:
                score += 3.0
        score = round(min(100.0, max(0.0, score)), 4)
        if score >= 70:
            tier = "strong"
            discovery_type = "consolidation_ready"
        elif score >= 50:
            tier = "watch"
            discovery_type = "consolidation_watch"
        else:
            tier = "rejected"
            discovery_type = "structure_not_ready"

        features = {
            "bar_count": len(bars),
            "range_20_pct": round(range_20, 4),
            "range_60_pct": round(range_60, 4),
            "volatility_20_pct": round(volatility_20, 4),
            "atr_14_pct": round(atr_14_pct, 4),
            "volume_ratio_5_20": (
                round(volume_ratio_5_20, 4) if volume_ratio_5_20 is not None else None
            ),
            "breakout_gap_60_pct": round(breakout_gap_60, 4),
            "ma_20": round(ma_20, 4),
            "ma_60": round(ma_60, 4),
            "ma_20_gap_pct": round((close / ma_20 - 1.0) * 100, 4),
            "ma_60_gap_pct": round((close / ma_60 - 1.0) * 100, 4),
            "return_20_pct": round(return_20, 4),
            "close_position_60_pct": round(close_position_60, 4),
        }
        reasons = [
            f"20日振幅 {range_20:.2f}%",
            f"20日波动率 {volatility_20:.2f}%",
            f"距60日压力位 {breakout_gap_60:.2f}%",
        ]
        if volume_ratio_5_20 is not None:
            reasons.append(f"5/20日量比 {volume_ratio_5_20:.2f}")
        return {
            "symbol": str(member["symbol"]),
            "name": member.get("name"),
            "exchange": member.get("exchange"),
            "trade_date": str(latest["trade_date"]),
            "current_price": round(close, 4),
            "pct_change": round(returns[-1] if returns else 0.0, 4),
            "volume": float(latest.get("volume") or 0),
            "amount": float(latest.get("amount") or 0),
            "score": score,
            "tier": tier,
            "discovery_type": discovery_type,
            "reasons": reasons,
            "features": features,
        }

    def _persist(
        self,
        *,
        result: dict[str, Any],
        scored: list[dict[str, Any]],
        selected: list[dict[str, Any]],
    ) -> dict[str, Any]:
        summary = {
            key: result[key]
            for key in (
                "schema_version",
                "feature_version",
                "as_of_date",
                "universe_snapshot_id",
                "universe_count",
                "qfq_ready_count",
                "eligible_count",
                "excluded_count",
                "selected_count",
                "tier_counts",
                "duration_seconds",
                "incremental",
                "parameters",
                "safety",
            )
        }
        with self.store.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO full_market_feature_runs(
                    status, source, feature_version, as_of_date,
                    universe_snapshot_id, universe_count, qfq_ready_count,
                    eligible_count, excluded_count, selected_count,
                    strong_count, watch_count, rejected_count, computed_count,
                    reused_count, error_count, duration_seconds, parameters_json,
                    summary_json, completed_at
                )
                VALUES (
                    'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    SOURCE,
                    FEATURE_VERSION,
                    result["as_of_date"],
                    result["universe_snapshot_id"],
                    result["universe_count"],
                    result["qfq_ready_count"],
                    result["eligible_count"],
                    result["excluded_count"],
                    result["selected_count"],
                    result["tier_counts"]["strong"],
                    result["tier_counts"]["watch"],
                    result["tier_counts"]["rejected"],
                    result["incremental"]["computed_count"],
                    result["incremental"]["reused_count"],
                    0,
                    result["duration_seconds"],
                    json.dumps(result["parameters"], ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("full_market_feature_run_persist_failed")
            scan_id = int(cursor.lastrowid)
            connection.execute(
                "DELETE FROM full_market_feature_state WHERE source = ?",
                (SOURCE,),
            )
            selected_symbols = {item["symbol"] for item in selected}
            for item in scored:
                connection.execute(
                    """
                    INSERT INTO full_market_feature_state(
                        symbol, name, exchange, trade_date, as_of_date,
                        current_price, pct_change, volume, amount, score, tier,
                        discovery_type, source, feature_version, input_revision,
                        bars_count, is_candidate, reasons_json, features_json,
                        scan_run_id, updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        item["symbol"],
                        item.get("name"),
                        item.get("exchange"),
                        item["trade_date"],
                        result["as_of_date"],
                        item["current_price"],
                        item["pct_change"],
                        item["volume"],
                        item["amount"],
                        item["score"],
                        item["tier"],
                        item["discovery_type"],
                        SOURCE,
                        FEATURE_VERSION,
                        item["input_revision"],
                        item["bars_count"],
                        int(item["symbol"] in selected_symbols),
                        json.dumps(item["reasons"], ensure_ascii=False),
                        json.dumps(item["features"], ensure_ascii=False),
                        scan_id,
                    ),
                )
            connection.execute(
                "DELETE FROM auto_discovered_candidates WHERE source = ?",
                (SOURCE,),
            )
        return {
            "scan_id": scan_id,
            "stored_feature_count": len(scored),
            "stored_candidate_count": len(selected),
        }

    @staticmethod
    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _range_pct(highs: list[float], lows: list[float]) -> float:
        low = min(lows)
        return (max(highs) / low - 1.0) * 100 if low > 0 else 0.0

    @staticmethod
    def _scaled_inverse(value: float, *, best: float, worst: float, weight: float) -> float:
        if value <= best:
            return weight
        if value >= worst:
            return 0.0
        return weight * (worst - value) / (worst - best)

    @staticmethod
    def _safety() -> dict[str, bool]:
        return {
            "research_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "execution_allowed": False,
        }

    def _blocked_result(self) -> dict[str, Any]:
        return {
            "status": "blocked",
            "reason": "live_trading_enabled",
            "source": SOURCE,
            "items": [],
            "safety": {
                **self._safety(),
                "live_trading_enabled": True,
            },
        }
