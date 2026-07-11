from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
import json
import math
from typing import Any

from app.forecasting.ledger import (
    FORECAST_HORIZONS,
    ForecastDecision,
    ForecastLedger,
    ForecastOutcome,
)
from app.storage.sqlite_store import SQLiteStore


_CHINA_TZ = timezone(timedelta(hours=8))
_BENCHMARK_PRIORITY = ("SH000300", "SH000001")


def _datetime(value: str | datetime) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None:
        raise ValueError("forecast feedback timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 8)


class ForecastFeedback:
    """Mature stock forecasts and evaluate immutable decision snapshots."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.store.init()
        self.ledger = ForecastLedger(store)

    def label_due(
        self,
        as_of: str | datetime,
        *,
        limit: int = 1000,
    ) -> dict[str, Any]:
        cutoff = _datetime(as_of)
        rows = self.store.fetch_all(
            """
            SELECT d.*
            FROM forecast_decisions d
            LEFT JOIN forecast_outcomes o
              ON o.decision_id = d.decision_id
             AND o.scope = d.scope
             AND o.subject = d.subject
             AND o.horizon_days = d.horizon_days
            WHERE d.scope = 'stock'
              AND d.review_only = 1
              AND o.id IS NULL
              AND d.decision_cutoff <= ?
              AND d.available_at <= ?
            ORDER BY d.decision_cutoff, d.decision_id, d.rank IS NULL, d.rank, d.subject
            LIMIT ?
            """,
            (
                cutoff.isoformat().replace("+00:00", "Z"),
                cutoff.isoformat().replace("+00:00", "Z"),
                max(1, min(int(limit), 10_000)),
            ),
        )
        labelled: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        for row in rows:
            forecast = self._forecast(row)
            outcome, reason = self._label(forecast, cutoff)
            if outcome is None:
                pending.append(
                    {
                        "decision_id": forecast.decision_id,
                        "subject": forecast.subject,
                        "horizon_days": forecast.horizon_days,
                        "reason": reason,
                    }
                )
                continue
            persisted = self.ledger.record_outcome(outcome)
            labelled.append(
                {
                    "decision_id": persisted.decision_id,
                    "subject": persisted.subject,
                    "horizon_days": persisted.horizon_days,
                    "observed_at": persisted.observed_at,
                }
            )
        return {
            "status": "completed",
            "schema_version": "forecast_feedback_labels.v1",
            "as_of": cutoff.isoformat().replace("+00:00", "Z"),
            "eligible_count": len(rows),
            "labelled_count": len(labelled),
            "pending_count": len(pending),
            "labelled": labelled,
            "pending": pending,
            "horizon_days": sorted(FORECAST_HORIZONS),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def evaluate(
        self,
        as_of: str | datetime,
        *,
        k: int = 5,
        min_samples: int = 20,
        min_folds: int = 3,
    ) -> dict[str, Any]:
        cutoff = _datetime(as_of)
        safe_k = max(1, min(int(k), 100))
        safe_min_samples = max(1, int(min_samples))
        safe_min_folds = max(1, int(min_folds))
        horizons = [
            self._evaluate_horizon(
                cutoff,
                horizon,
                k=safe_k,
                min_samples=safe_min_samples,
                min_folds=safe_min_folds,
            )
            for horizon in sorted(FORECAST_HORIZONS)
        ]
        return {
            "status": "ready"
            if any(row["status"] == "ready" for row in horizons)
            else "insufficient_data",
            "schema_version": "forecast_feedback_evaluation.v1",
            "as_of": cutoff.isoformat().replace("+00:00", "Z"),
            "horizon_days": sorted(FORECAST_HORIZONS),
            "k": safe_k,
            "target": "benchmark_neutral_return>0",
            "horizons": horizons,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _label(
        self,
        forecast: ForecastDecision,
        as_of: datetime,
    ) -> tuple[ForecastOutcome | None, str | None]:
        decision_date = _datetime(forecast.decision_cutoff).astimezone(_CHINA_TZ).date().isoformat()
        as_of_date = as_of.astimezone(_CHINA_TZ).date().isoformat()
        stock_rows = self._bars_after(
            forecast.subject,
            decision_date=decision_date,
            as_of_date=as_of_date,
            limit=forecast.horizon_days,
        )
        if len(stock_rows) < forecast.horizon_days:
            return None, "stock_horizon_not_matured"
        entry = stock_rows[0]
        exit_row = stock_rows[forecast.horizon_days - 1]
        observed_at = datetime.combine(
            datetime.fromisoformat(str(exit_row["trade_date"])).date(),
            time(hour=15),
            tzinfo=_CHINA_TZ,
        ).astimezone(timezone.utc)
        if observed_at > as_of:
            return None, "stock_horizon_not_matured"

        benchmark = None
        benchmark_symbol = None
        for symbol in _BENCHMARK_PRIORITY:
            window = self._aligned_window(
                symbol,
                entry_date=str(entry["trade_date"]),
                exit_date=str(exit_row["trade_date"]),
            )
            if window is not None:
                benchmark_symbol = symbol
                benchmark = window
                break
        if benchmark is None or benchmark_symbol is None:
            return None, "benchmark_window_missing"

        continuous_return = self._return(float(entry["open"]), float(exit_row["close"]))
        benchmark_return = self._return(benchmark["entry_price"], benchmark["exit_price"])
        sector_symbol = self._sector_benchmark_symbol(forecast.features)
        sector_window = (
            self._aligned_window(
                sector_symbol,
                entry_date=str(entry["trade_date"]),
                exit_date=str(exit_row["trade_date"]),
            )
            if sector_symbol
            else None
        )
        if sector_window is None:
            sector_return = benchmark_return
            sector_return_source = "benchmark_proxy"
            sector_return_is_proxy = True
            sector_evidence: dict[str, Any] = {
                "sector_return_semantics": "benchmark_proxy_not_observed_industry_return",
                "sector_proxy_symbol": benchmark_symbol,
                "sector_proxy_reason": (
                    "industry_benchmark_window_unavailable"
                    if sector_symbol
                    else "industry_benchmark_not_provided"
                ),
            }
        else:
            sector_return = self._return(sector_window["entry_price"], sector_window["exit_price"])
            sector_return_source = "industry_benchmark"
            sector_return_is_proxy = False
            sector_evidence = {
                "sector_return_semantics": "observed_industry_benchmark_return",
                "sector_benchmark_symbol": sector_symbol,
                "sector_entry": sector_window["entry"],
                "sector_exit": sector_window["exit"],
            }

        evidence = {
            "label_policy": "next_session_open_to_hth_session_close",
            "decision_cutoff": forecast.decision_cutoff,
            "horizon_days": forecast.horizon_days,
            "entry": {
                "trade_date": str(entry["trade_date"]),
                "price_field": "open",
                "price": float(entry["open"]),
            },
            "exit": {
                "trade_date": str(exit_row["trade_date"]),
                "price_field": "close",
                "price": float(exit_row["close"]),
            },
            "stock_source": str(entry["source"]),
            "benchmark_symbol": benchmark_symbol,
            "benchmark_entry": benchmark["entry"],
            "benchmark_exit": benchmark["exit"],
            "benchmark_return_source": "market_index",
            "sector_return_source": sector_return_source,
            "sector_return_is_proxy": sector_return_is_proxy,
            **sector_evidence,
        }
        outcome = ForecastOutcome(
            decision_id=forecast.decision_id,
            scope="stock",
            subject=forecast.subject,
            horizon_days=forecast.horizon_days,
            observed_at=observed_at,
            continuous_return=continuous_return,
            benchmark_return=benchmark_return,
            sector_return=sector_return,
            data_version=(
                f"daily_bar_cache:{exit_row['trade_date']}:{entry['source']}:{benchmark['source']}"
            ),
            evidence=evidence,
            review_only=True,
        )
        return outcome, None

    def _bars_after(
        self,
        symbol: str,
        *,
        decision_date: str,
        as_of_date: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        return self.store.fetch_all(
            """
            SELECT symbol, trade_date, open, close, source
            FROM daily_bar_cache
            WHERE upper(symbol) = upper(?)
              AND trade_date > ?
              AND trade_date <= ?
              AND quality_status = 'ready'
              AND open IS NOT NULL AND open > 0
              AND close IS NOT NULL AND close > 0
            ORDER BY trade_date ASC
            LIMIT ?
            """,
            (symbol, decision_date, as_of_date, int(limit)),
        )

    def _aligned_window(
        self,
        symbol: str,
        *,
        entry_date: str,
        exit_date: str,
    ) -> dict[str, Any] | None:
        rows = self.store.fetch_all(
            """
            SELECT symbol, trade_date, open, close, source
            FROM daily_bar_cache
            WHERE upper(symbol) = upper(?)
              AND trade_date IN (?, ?)
              AND quality_status = 'ready'
              AND open IS NOT NULL AND open > 0
              AND close IS NOT NULL AND close > 0
            ORDER BY trade_date ASC
            """,
            (symbol, entry_date, exit_date),
        )
        by_date = {str(row["trade_date"]): row for row in rows}
        if entry_date not in by_date or exit_date not in by_date:
            return None
        entry = by_date[entry_date]
        exit_row = by_date[exit_date]
        return {
            "entry_price": float(entry["open"]),
            "exit_price": float(exit_row["close"]),
            "entry": {
                "trade_date": entry_date,
                "price_field": "open",
                "price": float(entry["open"]),
            },
            "exit": {
                "trade_date": exit_date,
                "price_field": "close",
                "price": float(exit_row["close"]),
            },
            "source": str(exit_row["source"]),
        }

    def _evaluate_horizon(
        self,
        as_of: datetime,
        horizon_days: int,
        *,
        k: int,
        min_samples: int,
        min_folds: int,
    ) -> dict[str, Any]:
        cutoff = as_of.isoformat().replace("+00:00", "Z")
        rows = self.store.fetch_all(
            """
            SELECT
                d.decision_id, d.subject, d.rank, d.score, d.probability,
                o.id AS outcome_id,
                o.continuous_return,
                o.benchmark_neutral_return,
                o.observed_at
            FROM forecast_decisions d
            LEFT JOIN forecast_outcomes o
              ON o.decision_id = d.decision_id
             AND o.scope = d.scope
             AND o.subject = d.subject
             AND o.horizon_days = d.horizon_days
             AND o.observed_at <= ?
            WHERE d.scope = 'stock'
              AND d.review_only = 1
              AND d.horizon_days = ?
              AND d.decision_cutoff <= ?
              AND d.available_at <= ?
            ORDER BY d.decision_id, d.rank IS NULL, d.rank, d.subject
            """,
            (cutoff, horizon_days, cutoff, cutoff),
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["decision_id"])].append(row)

        by_decision: list[dict[str, Any]] = []
        all_matured: list[dict[str, Any]] = []
        for decision_id, fold_rows in sorted(grouped.items()):
            matured = [row for row in fold_rows if row.get("outcome_id") is not None]
            all_matured.extend(matured)
            top = fold_rows[:k]
            precision = None
            if len(top) == k and all(row.get("outcome_id") is not None for row in top):
                precision = sum(1 for row in top if float(row["benchmark_neutral_return"]) > 0) / k
            predictor_actual = [
                (self._rank_predictor(row), float(row["benchmark_neutral_return"]))
                for row in matured
                if self._rank_predictor(row) is not None
            ]
            rank_ic = (
                self._spearman(
                    [pair[0] for pair in predictor_actual],
                    [pair[1] for pair in predictor_actual],
                )
                if len(predictor_actual) >= 2
                else None
            )
            probability_rows = [row for row in matured if row.get("probability") is not None]
            brier = self._brier(probability_rows)
            by_decision.append(
                {
                    "decision_id": decision_id,
                    "forecast_count": len(fold_rows),
                    "sample_count": len(matured),
                    "coverage": _round(len(matured) / len(fold_rows)) if fold_rows else 0.0,
                    "precision_at_k": _round(precision),
                    "spearman_rank_ic": _round(rank_ic),
                    "brier_score": _round(brier),
                    "probability_sample_count": len(probability_rows),
                }
            )

        precision_values = [
            float(row["precision_at_k"]) for row in by_decision if row["precision_at_k"] is not None
        ]
        rank_ic_values = [
            float(row["spearman_rank_ic"])
            for row in by_decision
            if row["spearman_rank_ic"] is not None
        ]
        probability_rows = [row for row in all_matured if row.get("probability") is not None]
        sample_count = len(all_matured)
        forecast_count = len(rows)
        fold_count = sum(1 for row in by_decision if row["sample_count"] > 0)
        insufficient_reasons = []
        if sample_count < min_samples:
            insufficient_reasons.append(f"sample_count_below_{min_samples}")
        if fold_count < min_folds:
            insufficient_reasons.append(f"fold_count_below_{min_folds}")
        return {
            "status": "insufficient_data" if insufficient_reasons else "ready",
            "horizon_days": horizon_days,
            "target": "benchmark_neutral_return>0",
            "aggregation": "unweighted_mean_across_decision_id_folds",
            "rank_predictor": "negative_rank_then_score",
            "k": k,
            "forecast_count": forecast_count,
            "sample_count": sample_count,
            "fold_count": fold_count,
            "coverage": _round(sample_count / forecast_count) if forecast_count else 0.0,
            "precision_at_k": _round(
                sum(precision_values) / len(precision_values) if precision_values else None
            ),
            "precision_fold_count": len(precision_values),
            "spearman_rank_ic": _round(
                sum(rank_ic_values) / len(rank_ic_values) if rank_ic_values else None
            ),
            "rank_ic_fold_count": len(rank_ic_values),
            "brier_score": _round(self._brier(probability_rows)),
            "probability_sample_count": len(probability_rows),
            "by_decision": by_decision,
            "insufficient_reasons": insufficient_reasons,
            "review_only": True,
        }

    @staticmethod
    def _forecast(row: dict[str, Any]) -> ForecastDecision:
        return ForecastDecision(
            decision_id=row["decision_id"],
            scope=row["scope"],
            subject=row["subject"],
            decision_cutoff=row["decision_cutoff"],
            available_at=row["available_at"],
            horizon_days=int(row["horizon_days"]),
            rank=row["rank"],
            score=row["score"],
            probability=row["probability"],
            model_version=row["model_version"],
            prompt_version=row["prompt_version"],
            data_version=row["data_version"],
            features=json.loads(row["features_json"]),
            evidence=json.loads(row["evidence_json"]),
            reasons=json.loads(row["reasons_json"]),
            status=row["status"],
            review_only=bool(row["review_only"]),
        )

    @staticmethod
    def _return(entry_price: float, exit_price: float) -> float:
        if entry_price <= 0 or exit_price <= 0:
            raise ValueError("outcome prices must be positive")
        return round(exit_price / entry_price - 1.0, 10)

    @staticmethod
    def _sector_benchmark_symbol(features: dict[str, Any]) -> str | None:
        for key in ("sector_benchmark_symbol", "industry_benchmark_symbol"):
            value = str(features.get(key) or "").strip().upper()
            if value:
                return value
        return None

    @staticmethod
    def _rank_predictor(row: dict[str, Any]) -> float | None:
        if row.get("rank") is not None:
            return -float(row["rank"])
        if row.get("score") is not None:
            return float(row["score"])
        return None

    @staticmethod
    def _brier(rows: list[dict[str, Any]]) -> float | None:
        if not rows:
            return None
        return sum(
            (
                float(row["probability"])
                - (1.0 if float(row["benchmark_neutral_return"]) > 0 else 0.0)
            )
            ** 2
            for row in rows
        ) / len(rows)

    @classmethod
    def _spearman(cls, left: list[float], right: list[float]) -> float | None:
        if len(left) != len(right) or len(left) < 2:
            return None
        return cls._pearson(cls._ranks(left), cls._ranks(right))

    @staticmethod
    def _ranks(values: list[float]) -> list[float]:
        result = [0.0] * len(values)
        ordered = sorted(range(len(values)), key=lambda index: values[index])
        start = 0
        while start < len(ordered):
            end = start + 1
            while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
                end += 1
            average_rank = (start + 1 + end) / 2.0
            for position in range(start, end):
                result[ordered[position]] = average_rank
            start = end
        return result

    @staticmethod
    def _pearson(left: list[float], right: list[float]) -> float | None:
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = sum(
            (left_value - left_mean) * (right_value - right_mean)
            for left_value, right_value in zip(left, right, strict=True)
        )
        left_variance = sum((value - left_mean) ** 2 for value in left)
        right_variance = sum((value - right_mean) ** 2 for value in right)
        denominator = math.sqrt(left_variance * right_variance)
        if denominator == 0:
            return None
        return numerator / denominator
