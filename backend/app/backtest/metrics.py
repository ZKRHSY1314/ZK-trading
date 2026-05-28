from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    max_drawdown: float
    win_rate: float
    profit_loss_ratio: float
    trade_count: int


def is_strictly_better(before: BacktestMetrics, after: BacktestMetrics) -> bool:
    return (
        after.total_return > before.total_return
        and after.max_drawdown <= before.max_drawdown
        and after.win_rate >= before.win_rate
        and after.profit_loss_ratio >= before.profit_loss_ratio
        and after.trade_count >= 20
    )
