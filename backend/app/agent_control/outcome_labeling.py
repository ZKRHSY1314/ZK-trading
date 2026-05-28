import json
from datetime import datetime
from typing import Any
import pandas as pd

from app.config import settings
from app.data.akshare_provider import AkshareProvider
from app.models import AgentLearningOutcome, AgentOutcomeSummary
from app.storage.sqlite_store import SQLiteStore


class OutcomeLabelingService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.provider = AkshareProvider()

    def label_sample(self, sample_id: int, horizon_days: int) -> dict[str, Any]:
        self.store.init()
        horizon_days = max(1, min(int(horizon_days), 60))
        sample = self.store.fetch_one("SELECT * FROM agent_learning_samples WHERE id = ?", (sample_id,))
        if not sample:
            raise ValueError(f"Sample {sample_id} not found")

        created_at_str = sample["created_at"]
        symbol = sample["symbol"]
        
        start_date = created_at_str[:10]

        if not symbol or symbol == "__no_symbol__":
            outcome_label = "pending_future_data"
            try:
                created_dt = datetime.fromisoformat(created_at_str.replace("Z", ""))
                days_passed = (datetime.now() - created_dt).days
                if days_passed >= horizon_days:
                    outcome_label = "system_stable"
            except ValueError:
                pass

            outcome = AgentLearningOutcome(
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
                outcome_label=outcome_label,
                risk_outcome="unknown",
            )
            return self._save_outcome(outcome)

        clean_symbol = symbol
        if clean_symbol.startswith("SH") or clean_symbol.startswith("SZ"):
            clean_symbol = clean_symbol[2:]

        try:
            df = self.provider.get_daily_bars(clean_symbol)
        except Exception:
            df = pd.DataFrame()

        if df.empty:
            outcome = AgentLearningOutcome(
                sample_id=sample_id,
                symbol=symbol,
                horizon_days=horizon_days,
                start_date=start_date,
                end_date=start_date,
                outcome_label="pending_future_data",
                risk_outcome="unknown",
                metrics={"reason": "daily_bars_unavailable"},
            )
            return self._save_outcome(outcome)

        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
            future_df = df[df["日期"] >= start_date].sort_values("日期").copy()
        else:
            future_df = pd.DataFrame()

        required_bars = horizon_days + 1
        if len(future_df) < required_bars:
            outcome = AgentLearningOutcome(
                sample_id=sample_id,
                symbol=symbol,
                horizon_days=horizon_days,
                start_date=start_date,
                end_date=str(future_df.iloc[-1]["日期"]) if not future_df.empty and "日期" in future_df.columns else start_date,
                outcome_label="pending_future_data",
                risk_outcome="unknown",
                metrics={
                    "reason": "insufficient_future_bars",
                    "available_bars": int(len(future_df)),
                    "required_bars": required_bars,
                },
            )
            return self._save_outcome(outcome)
        
        eval_df = future_df.head(horizon_days + 1).copy()
        
        try:
            start_price = float(eval_df.iloc[0]["收盘"])
            end_price = float(eval_df.iloc[-1]["收盘"])
            max_price = float(eval_df["最高"].max())
            min_price = float(eval_df["最低"].min())
            
            close_return_pct = (end_price - start_price) / start_price * 100
            max_return_pct = (max_price - start_price) / start_price * 100
            min_return_pct = (min_price - start_price) / start_price * 100
            
            end_date = str(eval_df.iloc[-1]["日期"])
            
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
        except (KeyError, ValueError, IndexError):
            start_price = end_price = max_return_pct = min_return_pct = close_return_pct = None
            end_date = start_date
            outcome_label = "pending_future_data"
            risk_outcome = "unknown"
            
        outcome = AgentLearningOutcome(
            sample_id=sample_id,
            symbol=symbol,
            horizon_days=horizon_days,
            start_date=start_date,
            end_date=end_date,
            start_price=start_price,
            end_price=end_price,
            max_return_pct=max_return_pct,
            min_return_pct=min_return_pct,
            close_return_pct=close_return_pct,
            outcome_label=outcome_label,
            risk_outcome=risk_outcome,
            metrics={"max_return": max_return_pct, "min_return": min_return_pct, "close_return": close_return_pct} if max_return_pct is not None else {}
        )
        return self._save_outcome(outcome)

    def _save_outcome(self, outcome: AgentLearningOutcome) -> dict[str, Any]:
        with self.store.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM agent_learning_outcomes WHERE sample_id = ? AND horizon_days = ?",
                (outcome.sample_id, outcome.horizon_days)
            ).fetchone()
            
            metrics_json = json.dumps(outcome.metrics) if isinstance(outcome.metrics, dict) else '{}'

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
                        outcome.start_date, outcome.end_date, outcome.start_price, outcome.end_price,
                        outcome.max_return_pct, outcome.min_return_pct, outcome.close_return_pct,
                        outcome.outcome_label, outcome.risk_outcome, metrics_json,
                        existing["id"]
                    )
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
                        outcome.sample_id, outcome.symbol, outcome.horizon_days, outcome.start_date, outcome.end_date,
                        outcome.start_price, outcome.end_price, outcome.max_return_pct, outcome.min_return_pct, outcome.close_return_pct,
                        outcome.outcome_label, outcome.risk_outcome, metrics_json
                    )
                )
                outcome.id = cursor.lastrowid
                
        return outcome.model_dump(mode="json")

    def label_recent(self, limit: int, horizon_days: int) -> dict[str, Any]:
        self.store.init()
        limit = max(1, min(int(limit), 500))
        horizon_days = max(1, min(int(horizon_days), 60))
        samples = self.store.fetch_all(
            "SELECT id FROM agent_learning_samples ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        results = []
        errors = []
        for s in samples:
            try:
                res = self.label_sample(s["id"], horizon_days)
                results.append(res)
            except Exception as e:
                errors.append({"sample_id": s["id"], "error": str(e)})
        return {
            "processed_count": len(samples),
            "outcome_count": len(results),
            "error_count": len(errors),
            "errors": errors,
            "outcomes": results,
        }
        
    def list_outcomes(self, limit: int) -> list[AgentLearningOutcome]:
        self.store.init()
        limit = max(1, min(int(limit), 500))
        rows = self.store.fetch_all(
            "SELECT * FROM agent_learning_outcomes ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        outcomes = []
        for r in rows:
            metrics = {}
            if r["metrics_json"]:
                try:
                    metrics = json.loads(r["metrics_json"])
                except json.JSONDecodeError:
                    pass
            d = dict(r)
            d["metrics"] = metrics
            outcomes.append(AgentLearningOutcome(**d))
        return outcomes
        
    def summary(self) -> AgentOutcomeSummary:
        self.store.init()
        outcomes = self.store.fetch_all("SELECT * FROM agent_learning_outcomes")
        
        pending_count = sum(1 for o in outcomes if o["outcome_label"] == "pending_future_data")
        
        by_label: dict[str, int] = {}
        for o in outcomes:
            lbl = str(o["outcome_label"])
            by_label[lbl] = by_label.get(lbl, 0) + 1

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
            by_label=by_label
        )
