from __future__ import annotations

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
        gates = self._gates(
            exposure_ratio=exposure_ratio,
            largest_position_ratio=largest_position_ratio,
            regime=regime.get("regime", "insufficient_data"),
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
            "gates": gates,
            "posture": posture,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _gates(
        self,
        exposure_ratio: float,
        largest_position_ratio: float,
        regime: str,
    ) -> list[dict]:
        gates = []
        gates.append(
            {
                "name": "total_exposure",
                "status": "blocked" if exposure_ratio >= DEFAULT_LIMITS["max_total_exposure"] else "ok",
                "value": round(exposure_ratio, 4),
                "limit": DEFAULT_LIMITS["max_total_exposure"],
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
            }
        )
        return gates
