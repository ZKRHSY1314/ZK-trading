from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.market_regime.service import MarketRegimeService
from app.simulation.broker import SimulatedBroker


DEFAULT_LIMITS = {
    "max_total_exposure": 0.60,
    "max_single_position": 0.20,
    "max_new_positions_per_day": 3,
    "max_daily_loss": 0.03,
    "max_drawdown_stop": 0.10,
    "consecutive_loss_cooldown": 3,
}


class PortfolioRiskService:
    def __init__(self):
        self.broker = SimulatedBroker()

    def state(self) -> dict:
        account = self.broker.account()
        positions_value = sum(position.quantity * position.avg_cost for position in account.positions)
        equity = account.cash + positions_value
        exposure_ratio = positions_value / equity if equity > 0 else 0
        largest_position_ratio = (
            max((position.quantity * position.avg_cost for position in account.positions), default=0) / equity
            if equity > 0
            else 0
        )
        regime = MarketRegimeService().get_latest_regime()
        activity = self._activity_state(equity)
        gates = self._gates(
            exposure_ratio=exposure_ratio,
            largest_position_ratio=largest_position_ratio,
            regime=regime.get("regime", "insufficient_data"),
            activity=activity,
        )
        posture = "stop_new_entries" if any(gate["status"] == "blocked" for gate in gates) else "normal"
        if posture == "normal" and any(gate["status"] == "reduced" for gate in gates):
            posture = "reduce"
        return {
            "equity": round(equity, 2),
            "cash": account.cash,
            "positions_value": round(positions_value, 2),
            "position_count": len(account.positions),
            "exposure_ratio": round(exposure_ratio, 4),
            "largest_position_ratio": round(largest_position_ratio, 4),
            "limits": DEFAULT_LIMITS,
            "market_regime": regime,
            "activity": activity,
            "gates": gates,
            "posture": posture,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _gates(
        self,
        exposure_ratio: float,
        largest_position_ratio: float,
        regime: str,
        activity: dict,
    ) -> list[dict]:
        gates = []
        gates.append(
            {
                "name": "total_exposure",
                "status": "blocked" if exposure_ratio >= DEFAULT_LIMITS["max_total_exposure"] else "ok",
                "value": round(exposure_ratio, 4),
                "limit": DEFAULT_LIMITS["max_total_exposure"],
                "reason": "模拟总仓位超过上限时停止新开仓。",
            }
        )
        gates.append(
            {
                "name": "single_position",
                "status": "blocked"
                if largest_position_ratio >= DEFAULT_LIMITS["max_single_position"]
                else "ok",
                "value": round(largest_position_ratio, 4),
                "limit": DEFAULT_LIMITS["max_single_position"],
                "reason": "单票模拟仓位超过上限时停止加仓。",
            }
        )
        if regime == "extreme_risk":
            status = "blocked"
        elif regime == "weak":
            status = "reduced"
        else:
            status = "ok"
        gates.append(
            {
                "name": "market_regime",
                "status": status,
                "value": regime,
                "limit": "no new entries in extreme_risk; half size in weak",
                "reason": "大盘环境弱势时降低仓位，极端风险时停止新开仓。",
            }
        )
        gates.append(
            {
                "name": "max_daily_loss",
                "status": "blocked"
                if activity["daily_loss_ratio"] >= DEFAULT_LIMITS["max_daily_loss"]
                else "ok",
                "value": activity["daily_loss_ratio"],
                "limit": DEFAULT_LIMITS["max_daily_loss"],
                "reason": "当日模拟账户损失超过阈值时停止新开仓。",
            }
        )
        gates.append(
            {
                "name": "max_drawdown_stop",
                "status": "blocked"
                if activity["drawdown_ratio"] >= DEFAULT_LIMITS["max_drawdown_stop"]
                else "ok",
                "value": activity["drawdown_ratio"],
                "limit": DEFAULT_LIMITS["max_drawdown_stop"],
                "reason": "当前模拟权益较初始资金回撤过大时停止新开仓。",
            }
        )
        gates.append(
            {
                "name": "consecutive_loss_cooldown",
                "status": "blocked"
                if activity["consecutive_loss_count"] >= DEFAULT_LIMITS["consecutive_loss_cooldown"]
                else "ok",
                "value": activity["consecutive_loss_count"],
                "limit": DEFAULT_LIMITS["consecutive_loss_cooldown"],
                "reason": "连续亏损达到阈值时进入冷却观察。",
            }
        )
        gates.append(
            {
                "name": "max_new_positions_per_day",
                "status": "blocked"
                if activity["new_positions_today"] >= DEFAULT_LIMITS["max_new_positions_per_day"]
                else "ok",
                "value": activity["new_positions_today"],
                "limit": DEFAULT_LIMITS["max_new_positions_per_day"],
                "reason": "限制单日新增模拟开仓次数。",
            }
        )
        return gates

    def _activity_state(self, equity: float) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        account = self.broker._ensure_account()
        rows = self.broker.store.fetch_all(
            """
            SELECT side, amount, fee, stamp_tax, created_at
            FROM simulation_fills
            WHERE account_id = ?
            ORDER BY id DESC
            LIMIT 100
            """,
            (account["id"],),
        )
        buys_today = [
            row
            for row in rows
            if row["side"] == "buy" and str(row["created_at"] or "").startswith(today)
        ]
        costs_today = sum(float(row["fee"] or 0) + float(row["stamp_tax"] or 0) for row in rows)
        daily_loss_ratio = costs_today / equity if equity > 0 else 0.0
        drawdown_ratio = (
            max(0.0, float(account["initial_cash"]) - equity) / float(account["initial_cash"])
            if float(account["initial_cash"]) > 0
            else 0.0
        )
        return {
            "new_positions_today": len(buys_today),
            "daily_loss_ratio": round(daily_loss_ratio, 4),
            "drawdown_ratio": round(drawdown_ratio, 4),
            "consecutive_loss_count": 0,
            "note": "Simulation broker has no realized lot P/L yet; consecutive loss cooldown is conservative placeholder.",
        }
