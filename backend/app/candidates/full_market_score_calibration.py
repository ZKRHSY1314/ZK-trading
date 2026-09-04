from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import math
from typing import Any

from app.candidates.full_market_scan import FullMarketFeatureScanner
from app.config import settings
from app.data.market_history import MarketHistoryStore
from app.storage.sqlite_store import SQLiteStore


SCHEMA_VERSION = "full_market_score_calibration.v1"
SCORE_SEMANTICS = "uncalibrated_structure_score"


class FullMarketScoreCalibrationService:
    """Calibrate the full-market structure score with purged time-order evidence."""

    def __init__(
        self,
        *,
        store: SQLiteStore,
        history_store: MarketHistoryStore,
    ) -> None:
        self.store = store
        self.history_store = history_store
        self._scorer = FullMarketFeatureScanner(
            store=store,
            history_store=history_store,
        )

    def run(
        self,
        *,
        horizon_trading_days: int = 20,
        target_return_pct: float = 8.0,
        min_history_bars: int = 60,
        lookback_bars: int = 120,
        validation_fraction: float = 0.2,
        score_bin_width: int = 10,
        sample_stride: int = 10,
        min_train_samples: int = 200,
        min_validation_samples: int = 50,
        min_bin_samples: int = 30,
        as_of_date: str | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        if settings.enable_live_trading:
            return self._blocked_result()
        parameters = self._validated_parameters(
            horizon_trading_days=horizon_trading_days,
            target_return_pct=target_return_pct,
            min_history_bars=min_history_bars,
            lookback_bars=lookback_bars,
            validation_fraction=validation_fraction,
            score_bin_width=score_bin_width,
            sample_stride=sample_stride,
            min_train_samples=min_train_samples,
            min_validation_samples=min_validation_samples,
            min_bin_samples=min_bin_samples,
        )
        cutoff = self._resolve_cutoff(as_of_date)
        samples, sample_audit = self._build_samples(cutoff=cutoff, **parameters)
        split = self._chronological_split(
            samples,
            validation_fraction=parameters["validation_fraction"],
        )
        training = split.pop("training_samples")
        validation = split.pop("validation_samples")
        bins = self._fit_bins(
            training,
            bin_width=parameters["score_bin_width"],
            min_bin_samples=parameters["min_bin_samples"],
        )
        validation_metrics = self._validate(validation, bins=bins)
        sufficient = (
            len(training) >= parameters["min_train_samples"]
            and len(validation) >= parameters["min_validation_samples"]
            and validation_metrics["mapped_sample_count"] >= parameters["min_validation_samples"]
        )
        status = "ready" if sufficient else "insufficient_data"
        if not sufficient:
            bins = [self._suppress_probability(item) for item in bins]
            validation_metrics = {
                **validation_metrics,
                "status": "insufficient_data",
                "brier_score": None,
                "log_loss": None,
                "calibration_error": None,
            }
        result = {
            "status": status,
            "schema_version": SCHEMA_VERSION,
            "score_semantics": SCORE_SEMANTICS,
            "probability_semantics": (
                f"future_{parameters['horizon_trading_days']}d_max_close_return_ge_"
                f"{parameters['target_return_pct']:g}pct"
            ),
            "as_of_date": cutoff,
            "label": {
                "horizon_trading_days": parameters["horizon_trading_days"],
                "target": "future_max_close_return_pct",
                "threshold_pct": parameters["target_return_pct"],
                "comparison": ">=",
            },
            "parameters": parameters,
            "sample_audit": sample_audit,
            "split": split,
            "training": {
                "sample_count": len(training),
                "event_count": sum(int(item["label"]) for item in training),
                "event_rate": self._event_rate(training),
            },
            "validation": {
                "sample_count": len(validation),
                "event_count": sum(int(item["label"]) for item in validation),
                "event_rate": self._event_rate(validation),
                **validation_metrics,
            },
            "bins": bins,
            "sufficiency": {
                "status": status,
                "minimum_train_samples": parameters["min_train_samples"],
                "minimum_validation_samples": parameters["min_validation_samples"],
                "minimum_bin_samples": parameters["min_bin_samples"],
                "confidence_interval_method": ("wilson_score_95pct_nominal_not_cluster_adjusted"),
            },
            "safety": self._safety(),
        }
        if persist:
            run_id, inserted = self._persist(result)
            result["calibration_run_id"] = run_id
            result["persisted"] = inserted
        return result

    def latest(self) -> dict[str, Any]:
        """Return the newest persisted research calibration without recomputing it."""
        if settings.enable_live_trading:
            return self._blocked_result()
        row = self.store.fetch_one(
            """
            SELECT id, result_json, created_at
            FROM full_market_score_calibration_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if row is None:
            return {
                "status": "missing",
                "schema_version": SCHEMA_VERSION,
                "reason": "calibration_missing",
                "calibration_run_id": None,
                "bins": [],
                "safety": self._safety(),
            }
        try:
            result = json.loads(str(row["result_json"] or "{}"))
        except (json.JSONDecodeError, TypeError):
            return {
                "status": "failed",
                "schema_version": SCHEMA_VERSION,
                "reason": "calibration_evidence_invalid",
                "calibration_run_id": int(row["id"]),
                "bins": [],
                "safety": self._safety(),
            }
        if not isinstance(result, dict):
            return {
                "status": "failed",
                "schema_version": SCHEMA_VERSION,
                "reason": "calibration_evidence_invalid",
                "calibration_run_id": int(row["id"]),
                "bins": [],
                "safety": self._safety(),
            }
        return {
            **result,
            "calibration_run_id": int(row["id"]),
            "persisted": True,
            "persisted_at": str(row["created_at"]),
        }

    def map_score(
        self,
        structure_score: float,
        *,
        calibration_run_id: int | None = None,
    ) -> dict[str, Any]:
        score = float(structure_score)
        if not 0.0 <= score <= 100.0:
            raise ValueError("structure_score must be between 0 and 100")
        if settings.enable_live_trading:
            return {
                "status": "blocked",
                "reason": "live_trading_enabled",
                "calibration_run_id": None,
                "structure_score": score,
                "score_semantics": SCORE_SEMANTICS,
                "probability": None,
                "probability_semantics": None,
                "sample_count": 0,
                "confidence_interval_95": None,
                "safety": {
                    **self._safety(),
                    "live_trading_enabled": True,
                },
            }
        if calibration_run_id is None:
            run = self.store.fetch_one(
                """
                SELECT id, status, score_semantics, probability_semantics, result_json
                FROM full_market_score_calibration_runs
                ORDER BY id DESC LIMIT 1
                """
            )
        else:
            run = self.store.fetch_one(
                """
                SELECT id, status, score_semantics, probability_semantics, result_json
                FROM full_market_score_calibration_runs
                WHERE id = ?
                """,
                (int(calibration_run_id),),
            )
        if run is None:
            return self._missing_mapping(score, reason="calibration_missing")
        try:
            result = json.loads(str(run["result_json"] or "{}"))
        except json.JSONDecodeError:
            return self._missing_mapping(
                score,
                reason="calibration_evidence_invalid",
                calibration_run_id=int(run["id"]),
            )
        rows = self.store.fetch_all(
            """
            SELECT bin_index, score_lower_inclusive, score_upper,
                   upper_bound_inclusive, sample_count, success_count,
                   probability, confidence_lower, confidence_upper, status
            FROM full_market_score_calibration_bins
            WHERE calibration_run_id = ?
            ORDER BY bin_index
            """,
            (int(run["id"]),),
        )
        matched = next(
            (
                row
                for row in rows
                if score >= float(row["score_lower_inclusive"])
                and (
                    score < float(row["score_upper"])
                    or (bool(row["upper_bound_inclusive"]) and score <= float(row["score_upper"]))
                )
            ),
            None,
        )
        if (
            str(run["status"]) != "ready"
            or matched is None
            or str(matched["status"]) != "ready"
            or matched["probability"] is None
        ):
            return self._missing_mapping(
                score,
                reason="insufficient_calibration_samples",
                calibration_run_id=int(run["id"]),
                probability_semantics=str(run["probability_semantics"]),
                sample_count=int(matched["sample_count"] or 0) if matched else 0,
            )
        return {
            "status": "ready",
            "calibration_run_id": int(run["id"]),
            "structure_score": score,
            "score_semantics": str(run["score_semantics"]),
            "probability": float(matched["probability"]),
            "probability_semantics": str(run["probability_semantics"]),
            "sample_count": int(matched["sample_count"]),
            "success_count": int(matched["success_count"]),
            "confidence_interval_95": {
                "lower": float(matched["confidence_lower"]),
                "upper": float(matched["confidence_upper"]),
            },
            "label": result["label"],
            "validation": result["validation"],
            "safety": result["safety"],
        }

    def _persist(self, result: dict[str, Any]) -> tuple[int, bool]:
        canonical = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT id
                FROM full_market_score_calibration_runs
                WHERE schema_version = ? AND result_json = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (result["schema_version"], canonical),
            ).fetchone()
            if existing is not None:
                return int(existing["id"]), False
            cursor = connection.execute(
                """
                INSERT INTO full_market_score_calibration_runs(
                    status, schema_version, score_semantics, probability_semantics,
                    as_of_date, horizon_trading_days, target_return_pct,
                    validation_start_date, training_sample_count,
                    validation_sample_count, mapped_validation_sample_count,
                    parameters_json, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["status"],
                    result["schema_version"],
                    result["score_semantics"],
                    result["probability_semantics"],
                    result["as_of_date"],
                    result["label"]["horizon_trading_days"],
                    result["label"]["threshold_pct"],
                    result["split"]["validation_start_date"],
                    result["training"]["sample_count"],
                    result["validation"]["sample_count"],
                    result["validation"]["mapped_sample_count"],
                    json.dumps(result["parameters"], ensure_ascii=False, sort_keys=True),
                    canonical,
                ),
            )
            run_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO full_market_score_calibration_bins(
                    calibration_run_id, bin_index, score_lower_inclusive,
                    score_upper, upper_bound_inclusive, sample_count,
                    success_count, probability, confidence_lower,
                    confidence_upper, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        index,
                        item["score_lower_inclusive"],
                        item["score_upper_inclusive"]
                        if item["score_upper_inclusive"] is not None
                        else item["score_upper_exclusive"],
                        int(item["score_upper_inclusive"] is not None),
                        item["sample_count"],
                        item["success_count"],
                        item["probability"],
                        (
                            item["confidence_interval_95"]["lower"]
                            if item["confidence_interval_95"] is not None
                            else None
                        ),
                        (
                            item["confidence_interval_95"]["upper"]
                            if item["confidence_interval_95"] is not None
                            else None
                        ),
                        item["status"],
                    )
                    for index, item in enumerate(result["bins"])
                ],
            )
        return run_id, True

    @staticmethod
    def _validated_parameters(**values: Any) -> dict[str, Any]:
        horizon = int(values["horizon_trading_days"])
        minimum_history = int(values["min_history_bars"])
        lookback = int(values["lookback_bars"])
        validation_fraction = float(values["validation_fraction"])
        bin_width = int(values["score_bin_width"])
        sample_stride = int(values["sample_stride"])
        if not 1 <= horizon <= 250:
            raise ValueError("horizon_trading_days must be between 1 and 250")
        if minimum_history < 60:
            raise ValueError("min_history_bars must be at least 60")
        if lookback < minimum_history or lookback > 500:
            raise ValueError("lookback_bars must be between min_history_bars and 500")
        if not 0.1 <= validation_fraction <= 0.5:
            raise ValueError("validation_fraction must be between 0.1 and 0.5")
        if bin_width <= 0 or bin_width > 50 or 100 % bin_width:
            raise ValueError("score_bin_width must evenly divide 100")
        if not 1 <= sample_stride <= 60:
            raise ValueError("sample_stride must be between 1 and 60 trading days")
        for name in ("min_train_samples", "min_validation_samples", "min_bin_samples"):
            if int(values[name]) < 1:
                raise ValueError(f"{name} must be positive")
        return {
            "horizon_trading_days": horizon,
            "target_return_pct": float(values["target_return_pct"]),
            "min_history_bars": minimum_history,
            "lookback_bars": lookback,
            "validation_fraction": validation_fraction,
            "score_bin_width": bin_width,
            "sample_stride": sample_stride,
            "min_train_samples": int(values["min_train_samples"]),
            "min_validation_samples": int(values["min_validation_samples"]),
            "min_bin_samples": int(values["min_bin_samples"]),
        }

    def _resolve_cutoff(self, requested: str | None) -> str:
        if requested:
            return date.fromisoformat(str(requested)).isoformat()
        with self.history_store.connect(read_only=True) as connection:
            row = connection.execute(
                """
                SELECT MAX(trade_date) AS trade_date
                FROM daily_bars
                WHERE adjustment_mode = 'qfq' AND quality_status = 'ready'
                """
            ).fetchone()
        if row is None or not row["trade_date"]:
            raise RuntimeError("qfq_history_missing")
        return str(row["trade_date"])

    def _build_samples(
        self,
        *,
        cutoff: str,
        horizon_trading_days: int,
        target_return_pct: float,
        min_history_bars: int,
        lookback_bars: int,
        sample_stride: int,
        **_: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        with self.history_store.connect(read_only=True) as connection:
            snapshot = connection.execute(
                """
                SELECT snapshot.id, snapshot.snapshot_date, snapshot.member_count,
                       COUNT(member.symbol) AS actual_member_count
                FROM universe_snapshots snapshot
                JOIN universe_members member ON member.snapshot_id = snapshot.id
                WHERE snapshot.universe_name = 'a_share_full_market_cache'
                GROUP BY snapshot.id, snapshot.snapshot_date, snapshot.member_count
                HAVING COUNT(member.symbol) = snapshot.member_count
                   AND COUNT(member.symbol) > 0
                ORDER BY date(snapshot.snapshot_date) DESC, snapshot.id DESC
                LIMIT 1
                """
            ).fetchone()
            if snapshot is None:
                return [], {
                    "universe_snapshot_id": None,
                    "universe_snapshot_date": None,
                    "universe_snapshot_member_count": 0,
                    "labeled_sample_count": 0,
                    "discarded": {"official_complete_snapshot_missing": 1},
                    "historical_universe_bias": "current_universe_survivorship_limited",
                    "historical_universe_membership_unbiased": False,
                    "anchor_stride_trading_days": sample_stride,
                    "overlapping_label_windows": (sample_stride < horizon_trading_days),
                    "sample_independence_assumed": False,
                    "adjustment_revision_policy": "latest_qfq_research_series",
                    "historical_adjustment_revision_unbiased": False,
                    "point_in_time_feature_policy": (
                        "each_anchor_uses_only_bars_on_or_before_feature_date"
                    ),
                    "future_label_policy": ("next_n_symbol_trading_bars_after_feature_date"),
                }
            members = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT member.symbol, instrument.name, instrument.exchange
                    FROM universe_members member
                    JOIN instruments instrument ON instrument.symbol = member.symbol
                    WHERE member.snapshot_id = ?
                      AND instrument.asset_type = 'stock'
                    ORDER BY member.symbol
                    """,
                    (int(snapshot["id"]),),
                ).fetchall()
            ]

            samples: list[dict[str, Any]] = []
            discarded = {
                "insufficient_history": 0,
                "pending_future_bars": 0,
            }
            for member in members:
                symbol = str(member["symbol"])
                bars = [
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
                        ORDER BY date(trade_date), trade_date
                        """,
                        (symbol, cutoff),
                    ).fetchall()
                ]
                trade_dates = [str(row["trade_date"]) for row in bars]
                if len(bars) < min_history_bars:
                    discarded["insufficient_history"] += 1
                    continue
                for feature_index in range(
                    min_history_bars - 1,
                    len(bars),
                    sample_stride,
                ):
                    label_end_index = feature_index + horizon_trading_days
                    if label_end_index >= len(bars):
                        discarded["pending_future_bars"] += 1
                        continue
                    window_start = max(0, feature_index + 1 - lookback_bars)
                    score_item = self._scorer.score_bars(
                        member,
                        bars[window_start : feature_index + 1],
                    )
                    feature_close = float(bars[feature_index]["close"])
                    future = bars[feature_index + 1 : label_end_index + 1]
                    max_return_pct = (
                        max(float(row["close"]) for row in future) / feature_close - 1.0
                    ) * 100.0
                    samples.append(
                        {
                            "symbol": symbol,
                            "snapshot_id": int(snapshot["id"]),
                            "snapshot_date": str(snapshot["snapshot_date"]),
                            "feature_date": trade_dates[feature_index],
                            "label_end_date": trade_dates[label_end_index],
                            "score": float(score_item["score"]),
                            "future_max_close_return_pct": max_return_pct,
                            "label": int(max_return_pct >= target_return_pct),
                        }
                    )
        samples.sort(key=lambda item: (item["feature_date"], item["symbol"]))
        return samples, {
            "universe_snapshot_id": int(snapshot["id"]),
            "universe_snapshot_date": str(snapshot["snapshot_date"]),
            "universe_snapshot_member_count": len(members),
            "labeled_sample_count": len(samples),
            "discarded": discarded,
            "historical_universe_bias": "current_universe_survivorship_limited",
            "historical_universe_membership_unbiased": False,
            "anchor_stride_trading_days": sample_stride,
            "overlapping_label_windows": sample_stride < horizon_trading_days,
            "sample_independence_assumed": False,
            "adjustment_revision_policy": "latest_qfq_research_series",
            "historical_adjustment_revision_unbiased": False,
            "point_in_time_feature_policy": (
                "each_anchor_uses_only_bars_on_or_before_feature_date"
            ),
            "future_label_policy": "next_n_symbol_trading_bars_after_feature_date",
        }

    @staticmethod
    def _chronological_split(
        samples: list[dict[str, Any]],
        *,
        validation_fraction: float,
    ) -> dict[str, Any]:
        feature_dates = sorted({str(item["feature_date"]) for item in samples})
        if len(feature_dates) < 2:
            return {
                "policy": "chronological_holdout_with_horizon_purge",
                "validation_start_date": None,
                "training_feature_date_min": None,
                "training_feature_date_max": None,
                "training_label_end_max": None,
                "validation_feature_date_max": None,
                "purged_training_sample_count": 0,
                "training_samples": [],
                "validation_samples": [],
            }
        holdout_dates = max(1, math.ceil(len(feature_dates) * validation_fraction))
        validation_start = feature_dates[-holdout_dates]
        pre_purge_training = [
            item for item in samples if str(item["feature_date"]) < validation_start
        ]
        training = [
            item for item in pre_purge_training if str(item["label_end_date"]) < validation_start
        ]
        validation = [item for item in samples if str(item["feature_date"]) >= validation_start]
        return {
            "policy": "chronological_holdout_with_horizon_purge",
            "validation_start_date": validation_start,
            "training_feature_date_min": FullMarketScoreCalibrationService._date_bound(
                training, "feature_date", min
            ),
            "training_feature_date_max": FullMarketScoreCalibrationService._date_bound(
                training, "feature_date", max
            ),
            "training_label_end_max": FullMarketScoreCalibrationService._date_bound(
                training, "label_end_date", max
            ),
            "validation_feature_date_max": FullMarketScoreCalibrationService._date_bound(
                validation, "feature_date", max
            ),
            "purged_training_sample_count": len(pre_purge_training) - len(training),
            "training_samples": training,
            "validation_samples": validation,
        }

    @staticmethod
    def _date_bound(
        samples: list[dict[str, Any]],
        field: str,
        operation: Any,
    ) -> str | None:
        return operation(str(item[field]) for item in samples) if samples else None

    @classmethod
    def _fit_bins(
        cls,
        training: list[dict[str, Any]],
        *,
        bin_width: int,
        min_bin_samples: int,
    ) -> list[dict[str, Any]]:
        bin_count = 100 // bin_width
        buckets: list[list[dict[str, Any]]] = [[] for _ in range(bin_count)]
        for item in training:
            buckets[cls._bin_index(float(item["score"]), bin_width, bin_count)].append(item)
        result = []
        for index, bucket in enumerate(buckets):
            lower = float(index * bin_width)
            upper = float((index + 1) * bin_width)
            sample_count = len(bucket)
            success_count = sum(int(item["label"]) for item in bucket)
            sufficient = sample_count >= min_bin_samples
            probability = success_count / sample_count if sufficient else None
            interval = cls._wilson_interval(success_count, sample_count) if sufficient else None
            result.append(
                {
                    "score_lower_inclusive": lower,
                    "score_upper_inclusive": upper if index == bin_count - 1 else None,
                    "score_upper_exclusive": None if index == bin_count - 1 else upper,
                    "sample_count": sample_count,
                    "success_count": success_count,
                    "probability": round(probability, 6) if probability is not None else None,
                    "confidence_interval_95": (
                        {"lower": round(interval[0], 6), "upper": round(interval[1], 6)}
                        if interval is not None
                        else None
                    ),
                    "status": "ready" if sufficient else "insufficient_data",
                }
            )
        return result

    @classmethod
    def _validate(
        cls,
        validation: list[dict[str, Any]],
        *,
        bins: list[dict[str, Any]],
    ) -> dict[str, Any]:
        width = int(float(bins[0]["score_upper_exclusive"] or 100.0)) if bins else 100
        pairs: list[tuple[float, int]] = []
        by_bin: dict[int, list[int]] = defaultdict(list)
        for item in validation:
            index = cls._bin_index(float(item["score"]), width, len(bins))
            probability = bins[index]["probability"]
            if probability is None:
                continue
            label = int(item["label"])
            pairs.append((float(probability), label))
            by_bin[index].append(label)
        if not pairs:
            return {
                "status": "insufficient_data",
                "mapped_sample_count": 0,
                "coverage": 0.0,
                "brier_score": None,
                "log_loss": None,
                "calibration_error": None,
            }
        brier = sum((probability - label) ** 2 for probability, label in pairs) / len(pairs)
        epsilon = 1e-12
        log_loss = -sum(
            label * math.log(min(1 - epsilon, max(epsilon, probability)))
            + (1 - label) * math.log(min(1 - epsilon, max(epsilon, 1.0 - probability)))
            for probability, label in pairs
        ) / len(pairs)
        calibration_error = sum(
            len(labels)
            / len(pairs)
            * abs(float(bins[index]["probability"]) - sum(labels) / len(labels))
            for index, labels in by_bin.items()
        )
        return {
            "status": "ready",
            "mapped_sample_count": len(pairs),
            "coverage": round(len(pairs) / len(validation), 6) if validation else 0.0,
            "brier_score": round(brier, 6),
            "log_loss": round(log_loss, 6),
            "calibration_error": round(calibration_error, 6),
        }

    @staticmethod
    def _bin_index(score: float, width: int, bin_count: int) -> int:
        return min(bin_count - 1, max(0, int(min(100.0, max(0.0, score)) // width)))

    @staticmethod
    def _wilson_interval(successes: int, sample_count: int) -> tuple[float, float]:
        z = 1.959963984540054
        probability = successes / sample_count
        denominator = 1.0 + z * z / sample_count
        center = (probability + z * z / (2.0 * sample_count)) / denominator
        margin = (
            z
            * math.sqrt(
                probability * (1.0 - probability) / sample_count
                + z * z / (4.0 * sample_count * sample_count)
            )
            / denominator
        )
        return max(0.0, center - margin), min(1.0, center + margin)

    @staticmethod
    def _event_rate(samples: list[dict[str, Any]]) -> float | None:
        if not samples:
            return None
        return round(sum(int(item["label"]) for item in samples) / len(samples), 6)

    @staticmethod
    def _suppress_probability(item: dict[str, Any]) -> dict[str, Any]:
        return {
            **item,
            "probability": None,
            "confidence_interval_95": None,
            "status": "insufficient_data",
        }

    @classmethod
    def _missing_mapping(
        cls,
        structure_score: float,
        *,
        reason: str,
        calibration_run_id: int | None = None,
        probability_semantics: str | None = None,
        sample_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "status": "insufficient_data",
            "reason": reason,
            "calibration_run_id": calibration_run_id,
            "structure_score": structure_score,
            "score_semantics": SCORE_SEMANTICS,
            "probability": None,
            "probability_semantics": probability_semantics,
            "sample_count": sample_count,
            "confidence_interval_95": None,
            "safety": cls._safety(),
        }

    @staticmethod
    def _safety() -> dict[str, Any]:
        return {
            "research_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "execution_allowed": False,
            "orders_generated": False,
        }

    @classmethod
    def _blocked_result(cls) -> dict[str, Any]:
        return {
            "status": "blocked",
            "schema_version": SCHEMA_VERSION,
            "reason": "live_trading_enabled",
            "bins": [],
            "safety": {
                **cls._safety(),
                "live_trading_enabled": True,
            },
        }
