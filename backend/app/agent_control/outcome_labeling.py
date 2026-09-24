import json
from datetime import datetime
from typing import Any

import pandas as pd

from app.config import settings
from app.data.akshare_provider import AkshareProvider
from app.models import AgentLearningOutcome, AgentOutcomeSummary
from app.storage.sqlite_store import SQLiteStore


class OutcomeLabelingService:
    def __init__(
        self,
        store: SQLiteStore | None = None,
        provider: Any | None = None,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()
        self.provider = provider or AkshareProvider()
        self._local_frames: dict[str, pd.DataFrame] = {}
        self._provider_frames: dict[str, pd.DataFrame] = {}

    def label_sample(self, sample_id: int, horizon_days: int) -> dict[str, Any]:
        horizon_days = max(1, min(int(horizon_days), 60))
        sample = self.store.fetch_one(
            "SELECT * FROM agent_learning_samples WHERE id = ?", (sample_id,)
        )
        if not sample:
            raise ValueError(f"Sample {sample_id} not found")

        symbol = sample.get("symbol")
        start_date = self._sample_start_date(sample)

        if not symbol or symbol == "__no_symbol__":
            return self._save_outcome(
                AgentLearningOutcome(
                    sample_id=sample_id,
                    symbol=None,
                    horizon_days=horizon_days,
                    start_date=start_date,
                    end_date=start_date,
                    start_price=None,
                    end_price=None,
                    max_return_pct=None,
                    min_return_pct=None,
                    close_return_pct=None,
                    outcome_label="unsupported_non_market_sample",
                    risk_outcome="unknown",
                    metrics={
                        "data_source": "non_market_sample",
                        "reason": "symbol_required_for_market_outcome",
                        "sample_type": sample.get("sample_type"),
                    },
                )
            )

        required_bars = horizon_days
        bars, data_source = self._load_daily_bars(
            str(symbol),
            start_date=start_date,
            required_bars=required_bars,
        )
        if bars.empty:
            return self._save_outcome(
                AgentLearningOutcome(
                    sample_id=sample_id,
                    symbol=str(symbol),
                    horizon_days=horizon_days,
                    start_date=start_date,
                    end_date=start_date,
                    outcome_label="pending_future_data",
                    risk_outcome="unknown",
                    metrics={
                        "reason": "daily_bars_unavailable",
                        "data_source": data_source,
                    },
                )
            )

        # A signal generated during a session cannot be filled at that same
        # session's close. Outcomes begin at the next tradable session's open.
        future = bars[bars["trade_date"] > start_date].sort_values("trade_date")
        if len(future) < required_bars:
            return self._save_outcome(
                AgentLearningOutcome(
                    sample_id=sample_id,
                    symbol=str(symbol),
                    horizon_days=horizon_days,
                    start_date=start_date,
                    end_date=(str(future.iloc[-1]["trade_date"]) if not future.empty else start_date),
                    outcome_label="pending_future_data",
                    risk_outcome="unknown",
                    metrics={
                        "reason": "insufficient_future_bars",
                        "available_bars": int(len(future)),
                        "required_bars": required_bars,
                        "data_source": data_source,
                    },
                )
            )

        evaluation = future.head(required_bars)
        try:
            evaluation_start_date = str(evaluation.iloc[0]["trade_date"])
            start_price = float(evaluation.iloc[0]["open"])
            end_price = float(evaluation.iloc[-1]["close"])
            max_price = float(evaluation["high"].max())
            min_price = float(evaluation["low"].min())
            close_return_pct = (end_price - start_price) / start_price * 100
            max_return_pct = (max_price - start_price) / start_price * 100
            min_return_pct = (min_price - start_price) / start_price * 100
            end_date = str(evaluation.iloc[-1]["trade_date"])

            if close_return_pct >= 5.0 or max_return_pct >= 10.0:
                outcome_label = "strong_follow_through"
            elif close_return_pct >= 1.0:
                outcome_label = "mild_follow_through"
            elif close_return_pct <= -5.0:
                outcome_label = "failed_signal"
            else:
                outcome_label = "flat_or_noise"

            if min_return_pct <= -10.0:
                risk_outcome = "large_drawdown"
            elif min_return_pct <= -5.0:
                risk_outcome = "normal_drawdown"
            else:
                risk_outcome = "low_drawdown"
        except (KeyError, ValueError, IndexError, ZeroDivisionError):
            evaluation_start_date = start_date
            start_price = None
            end_price = None
            max_return_pct = None
            min_return_pct = None
            close_return_pct = None
            end_date = start_date
            outcome_label = "pending_future_data"
            risk_outcome = "unknown"

        metrics = {
            "data_source": data_source,
            "signal_date": start_date,
            "entry_price_basis": "next_trading_day_open",
            "signal_day_excluded": True,
            "evaluated_session_count": int(len(evaluation)),
        }
        if max_return_pct is not None:
            metrics.update(
                {
                    "max_return": max_return_pct,
                    "min_return": min_return_pct,
                    "close_return": close_return_pct,
                }
            )
        return self._save_outcome(
            AgentLearningOutcome(
                sample_id=sample_id,
                symbol=str(symbol),
                horizon_days=horizon_days,
                start_date=evaluation_start_date,
                end_date=end_date,
                start_price=start_price,
                end_price=end_price,
                max_return_pct=max_return_pct,
                min_return_pct=min_return_pct,
                close_return_pct=close_return_pct,
                outcome_label=outcome_label,
                risk_outcome=risk_outcome,
                metrics=metrics,
            )
        )

    def _sample_start_date(self, sample: dict[str, Any]) -> str:
        features = self._json_object(sample.get("features_json"))
        decision = self._json_object(sample.get("decision_json"))
        snapshot = features.get("snapshot") if isinstance(features.get("snapshot"), dict) else {}
        for value in (
            features.get("signal_date"),
            features.get("trade_date"),
            snapshot.get("trade_date"),
            decision.get("signal_date"),
        ):
            if value:
                return str(value)[:10]
        return str(sample.get("created_at") or datetime.now().isoformat())[:10]

    def _load_daily_bars(
        self,
        symbol: str,
        *,
        start_date: str,
        required_bars: int,
    ) -> tuple[pd.DataFrame, str]:
        local = self._local_daily_bars(symbol)
        if self._future_bar_count(local, start_date) >= required_bars:
            return local, "daily_bar_cache"

        provider = self._provider_daily_bars(symbol)
        if self._future_bar_count(provider, start_date) >= required_bars:
            return provider, "akshare_fallback"
        if not local.empty:
            return local, "daily_bar_cache"
        if not provider.empty:
            return provider, "akshare_fallback"
        return self._empty_frame(), "unavailable"

    def _local_daily_bars(self, symbol: str) -> pd.DataFrame:
        if symbol in self._local_frames:
            return self._local_frames[symbol]
        clean = symbol[2:] if symbol.startswith(("SH", "SZ")) else symbol
        variants = sorted({symbol, symbol.upper(), symbol.lower(), clean})
        placeholders = ",".join("?" for _ in variants)
        rows = self.store.fetch_all(
            f"""
            SELECT trade_date, open, close, high, low
            FROM daily_bar_cache
            WHERE symbol IN ({placeholders})
              AND trade_date != 'ERROR'
              AND quality_status = 'ready'
              AND open IS NOT NULL
              AND close IS NOT NULL
              AND high IS NOT NULL
              AND low IS NOT NULL
            ORDER BY trade_date ASC
            """,
            tuple(variants),
        )
        frame = self._canonical_daily_bars(pd.DataFrame(rows))
        self._local_frames[symbol] = frame
        return frame

    def _provider_daily_bars(self, symbol: str) -> pd.DataFrame:
        if symbol in self._provider_frames:
            return self._provider_frames[symbol]
        clean = symbol[2:] if symbol.startswith(("SH", "SZ")) else symbol
        try:
            raw = self.provider.get_daily_bars(clean)
        except Exception:
            raw = pd.DataFrame()
        frame = self._canonical_daily_bars(raw)
        self._provider_frames[symbol] = frame
        return frame

    def _canonical_daily_bars(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty:
            return self._empty_frame()
        aliases = {
            "trade_date": ("trade_date", "date", "日期"),
            "open": ("open", "开盘"),
            "close": ("close", "收盘"),
            "high": ("high", "最高"),
            "low": ("low", "最低"),
        }
        selected: dict[str, Any] = {}
        for canonical, candidates in aliases.items():
            source = next((name for name in candidates if name in frame.columns), None)
            if source is None:
                return self._empty_frame()
            selected[canonical] = frame[source]
        normalized = pd.DataFrame(selected)
        normalized["trade_date"] = pd.to_datetime(
            normalized["trade_date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        for column in ("open", "close", "high", "low"):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized.dropna(
            subset=["trade_date", "open", "close", "high", "low"],
            inplace=True,
        )
        return normalized.sort_values("trade_date").drop_duplicates("trade_date", keep="last")

    def _future_bar_count(self, frame: pd.DataFrame, start_date: str) -> int:
        if frame.empty:
            return 0
        return int((frame["trade_date"] > start_date).sum())

    def _empty_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=["trade_date", "open", "close", "high", "low"])

    def _json_object(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(raw or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _save_outcome(self, outcome: AgentLearningOutcome) -> dict[str, Any]:
        with self.store.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM agent_learning_outcomes WHERE sample_id = ? AND horizon_days = ?",
                (outcome.sample_id, outcome.horizon_days),
            ).fetchone()
            metrics_json = json.dumps(outcome.metrics, ensure_ascii=False)
            if existing:
                conn.execute(
                    """
                    UPDATE agent_learning_outcomes
                    SET start_date = ?, end_date = ?, start_price = ?, end_price = ?,
                        max_return_pct = ?, min_return_pct = ?, close_return_pct = ?,
                        outcome_label = ?, risk_outcome = ?, metrics_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        outcome.start_date,
                        outcome.end_date,
                        outcome.start_price,
                        outcome.end_price,
                        outcome.max_return_pct,
                        outcome.min_return_pct,
                        outcome.close_return_pct,
                        outcome.outcome_label,
                        outcome.risk_outcome,
                        metrics_json,
                        existing["id"],
                    ),
                )
                outcome.id = existing["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO agent_learning_outcomes (
                        sample_id, symbol, horizon_days, start_date, end_date,
                        start_price, end_price, max_return_pct, min_return_pct, close_return_pct,
                        outcome_label, risk_outcome, metrics_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        outcome.sample_id,
                        outcome.symbol,
                        outcome.horizon_days,
                        outcome.start_date,
                        outcome.end_date,
                        outcome.start_price,
                        outcome.end_price,
                        outcome.max_return_pct,
                        outcome.min_return_pct,
                        outcome.close_return_pct,
                        outcome.outcome_label,
                        outcome.risk_outcome,
                        metrics_json,
                    ),
                )
                outcome.id = cursor.lastrowid
        return outcome.model_dump(mode="json")

    def label_recent(self, limit: int, horizon_days: int) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        horizon_days = max(1, min(int(horizon_days), 60))
        # Cache only within this batch: one local query/provider request per
        # symbol, while a later scheduled run can observe newly arrived bars.
        self._local_frames.clear()
        self._provider_frames.clear()
        samples = self.store.fetch_all(
            """
            SELECT s.id
            FROM agent_learning_samples s
            LEFT JOIN agent_learning_outcomes o
              ON o.sample_id = s.id AND o.horizon_days = ?
            WHERE o.id IS NULL OR o.outcome_label = 'pending_future_data'
            ORDER BY
                CASE
                    WHEN date(
                        COALESCE(
                            CASE WHEN json_valid(s.features_json)
                                THEN json_extract(s.features_json, '$.signal_date')
                            END,
                            substr(s.created_at, 1, 10)
                        ),
                        '+' || ? || ' days'
                    ) <= date('now') THEN 0
                    ELSE 1
                END,
                CASE WHEN o.id IS NULL THEN 0 ELSE 1 END,
                COALESCE(o.updated_at, s.created_at) ASC,
                s.id ASC
            LIMIT ?
            """,
            (horizon_days, horizon_days, limit),
        )
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for sample in samples:
            try:
                results.append(self.label_sample(sample["id"], horizon_days))
            except Exception as exc:
                errors.append({"sample_id": sample["id"], "error": str(exc)})
        return {
            "processed_count": len(samples),
            "outcome_count": len(results),
            "error_count": len(errors),
            "errors": errors,
            "outcomes": results,
        }

    def list_outcomes(self, limit: int) -> list[AgentLearningOutcome]:
        limit = max(1, min(int(limit), 500))
        rows = self.store.fetch_all(
            "SELECT * FROM agent_learning_outcomes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        outcomes = []
        for row in rows:
            data = dict(row)
            data["metrics"] = self._json_object(data.get("metrics_json"))
            outcomes.append(AgentLearningOutcome(**data))
        return outcomes

    def summary(self) -> AgentOutcomeSummary:
        outcomes = self.store.fetch_all("SELECT * FROM agent_learning_outcomes")
        pending_count = sum(
            1 for outcome in outcomes if outcome["outcome_label"] == "pending_future_data"
        )
        by_label: dict[str, int] = {}
        for outcome in outcomes:
            label = str(outcome["outcome_label"])
            by_label[label] = by_label.get(label, 0) + 1

        type_rows = self.store.fetch_all(
            """
            SELECT
                s.sample_type,
                COUNT(o.id) AS outcome_count,
                SUM(CASE WHEN o.outcome_label = 'pending_future_data' THEN 1 ELSE 0 END) AS pending_count,
                AVG(o.close_return_pct) AS avg_close_return_pct,
                AVG(o.max_return_pct) AS avg_max_return_pct,
                AVG(o.min_return_pct) AS avg_min_return_pct
            FROM agent_learning_outcomes o
            JOIN agent_learning_samples s ON s.id = o.sample_id
            GROUP BY s.sample_type
            ORDER BY outcome_count DESC
            """
        )
        by_sample_type = {
            row["sample_type"]: {
                "outcome_count": int(row["outcome_count"] or 0),
                "pending_count": int(row["pending_count"] or 0),
                "avg_close_return_pct": row["avg_close_return_pct"],
                "avg_max_return_pct": row["avg_max_return_pct"],
                "avg_min_return_pct": row["avg_min_return_pct"],
            }
            for row in type_rows
        }
        return AgentOutcomeSummary(
            coverage_count=len(outcomes),
            pending_count=pending_count,
            by_sample_type=by_sample_type,
            by_label=by_label,
        )
