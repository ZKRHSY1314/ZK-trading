from datetime import date, datetime, time
import logging
from typing import Any

from app.config import settings
from app.data.snapshot_builder import MarketDataError, MarketSnapshotBuilder
from app.data.symbols import normalize_a_share_code
from app.models import PriceReadinessReport
from app.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class PriceReadinessService:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()
        self.builder = MarketSnapshotBuilder()

    def run_readiness_check(self, limit: int = 100) -> dict[str, Any]:
        """
        Inspects top candidate scores and checks price readiness.
        """
        limit = max(1, min(int(limit), 500))
        candidates = self.store.fetch_all(
            """
            SELECT symbol, MAX(name) AS name, MAX(total_score) AS best_score
            FROM candidate_scores
            GROUP BY symbol
            ORDER BY best_score DESC
            LIMIT ?
            """,
            (limit,)
        )
        
        results = []
        for row in candidates:
            symbol = row["symbol"]
            name = row["name"]
            report = self._check_symbol(symbol, name)
            self._save_report(report)
            results.append(report.model_dump())
            
        summary = self.get_summary()
        return {
            "processed": len(results),
            "summary": summary,
            "reports": results
        }

    def _check_symbol(self, symbol: str, name: str | None) -> PriceReadinessReport:
        now_str = datetime.now().isoformat()
        code = normalize_a_share_code(symbol)
        
        history_points = 0
        error_msg = None
        
        try:
            # Check history size using local cache directly
            try:
                row = self.store.fetch_one(
                    "SELECT COUNT(*) as cnt FROM daily_bar_cache WHERE symbol = ? AND trade_date != 'ERROR'",
                    (symbol,)
                )
                if row:
                    history_points = row["cnt"]
            except Exception as e:
                logger.warning(f"Failed to check history cache for {code}: {e}")
                
            snapshot = self.builder.build(symbol, name)
            
            coverage_status = "ready"
            if snapshot.price is None:
                coverage_status = "missing_price"
            elif history_points < 5:
                coverage_status = "insufficient_history"
                
            source = snapshot.metadata.get("source", "unknown")
            latest_price_at = self._snapshot_price_time(snapshot.trade_date, snapshot.metadata)
            if "fallback" in source.lower():
                # If we fallback, it might be stale or low quality
                if coverage_status == "ready":
                    coverage_status = "stale_price"
            if latest_price_at is None and coverage_status == "ready":
                coverage_status = "stale_price"
            elif latest_price_at and self._is_stale(latest_price_at) and coverage_status == "ready":
                coverage_status = "stale_price"
                    
            return PriceReadinessReport(
                symbol=symbol,
                name=name,
                source=source,
                latest_price=snapshot.price,
                latest_price_at=latest_price_at,
                coverage_status=coverage_status,
                history_points=history_points,
                error_message=None,
                metrics_json=snapshot.metadata,
                created_at=now_str,
                updated_at=now_str
            )
        except MarketDataError as e:
            return PriceReadinessReport(
                symbol=symbol,
                name=name,
                source="error",
                latest_price=None,
                latest_price_at=None,
                coverage_status="error",
                history_points=history_points,
                error_message=str(e),
                metrics_json={},
                created_at=now_str,
                updated_at=now_str
            )
        except Exception as e:
            return PriceReadinessReport(
                symbol=symbol,
                name=name,
                source="error",
                latest_price=None,
                latest_price_at=None,
                coverage_status="error",
                history_points=history_points,
                error_message=f"Unexpected error: {str(e)}",
                metrics_json={},
                created_at=now_str,
                updated_at=now_str
            )

    def _save_report(self, report: PriceReadinessReport) -> None:
        import json
        sql = """
            INSERT INTO price_readiness_reports 
            (symbol, name, source, latest_price, latest_price_at, coverage_status, history_points, error_message, metrics_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                source = excluded.source,
                latest_price = excluded.latest_price,
                latest_price_at = excluded.latest_price_at,
                coverage_status = excluded.coverage_status,
                history_points = excluded.history_points,
                error_message = excluded.error_message,
                metrics_json = excluded.metrics_json,
                updated_at = excluded.updated_at
        """
        with self.store.connect() as conn:
            conn.execute(sql, (
                report.symbol,
                report.name,
                report.source,
                report.latest_price,
                report.latest_price_at,
                report.coverage_status,
                report.history_points,
                report.error_message,
                json.dumps(report.metrics_json),
                report.updated_at
            ))

    def get_latest_reports(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            "SELECT * FROM price_readiness_reports ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        for row in rows:
            import json
            if isinstance(row.get("metrics_json"), str):
                row["metrics_json"] = json.loads(row["metrics_json"])
        return rows

    def get_summary(self) -> dict[str, int]:
        rows = self.store.fetch_all(
            "SELECT coverage_status, COUNT(*) as cnt FROM price_readiness_reports GROUP BY coverage_status"
        )
        return {row["coverage_status"]: row["cnt"] for row in rows}

    def _snapshot_price_time(
        self,
        trade_date: date | None,
        metadata: dict[str, Any],
    ) -> str | None:
        quote_time = metadata.get("quote_time")
        if isinstance(quote_time, str) and len(quote_time) >= 14:
            try:
                return datetime.strptime(quote_time[:14], "%Y%m%d%H%M%S").isoformat(
                    timespec="seconds"
                )
            except ValueError:
                pass
        if trade_date is not None:
            return datetime.combine(trade_date, time()).isoformat(timespec="seconds")
        return None

    def _is_stale(self, latest_price_at: str) -> bool:
        try:
            price_time = datetime.fromisoformat(latest_price_at)
        except ValueError:
            return True
        return (datetime.now() - price_time).days > 10
