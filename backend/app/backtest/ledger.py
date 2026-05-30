from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class PositionLot:
    symbol: str
    quantity: int
    entry_price: float
    entry_date: str
    entry_fee: float


@dataclass(frozen=True)
class ClosedTrade:
    symbol: str
    quantity: int
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    realized_pnl: float
    realized_pnl_pct: float
    holding_days: int
    fees: float
    stamp_tax: float
    slippage_cost: float
    exit_reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class FIFOLedger:
    def __init__(self) -> None:
        self.lots: dict[str, list[PositionLot]] = {}

    def buy(self, symbol: str, quantity: int, entry_price: float, entry_date: str, fee: float) -> None:
        self.lots.setdefault(symbol, []).append(
            PositionLot(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                entry_date=entry_date,
                entry_fee=fee,
            )
        )

    def sell(
        self,
        symbol: str,
        quantity: int,
        exit_price: float,
        exit_date: str,
        fee: float,
        stamp_tax: float,
        exit_reason: str,
        slippage_cost: float = 0.0,
    ) -> list[ClosedTrade]:
        remaining = quantity
        closed: list[ClosedTrade] = []
        lots = self.lots.get(symbol, [])
        while remaining > 0 and lots:
            lot = lots[0]
            matched = min(remaining, lot.quantity)
            entry_fee_alloc = lot.entry_fee * matched / lot.quantity if lot.quantity else 0.0
            exit_fee_alloc = fee * matched / quantity if quantity else 0.0
            tax_alloc = stamp_tax * matched / quantity if quantity else 0.0
            slippage_alloc = slippage_cost * matched / quantity if quantity else 0.0
            entry_value = lot.entry_price * matched
            realized = (exit_price - lot.entry_price) * matched - entry_fee_alloc - exit_fee_alloc - tax_alloc
            realized_pct = realized / entry_value if entry_value > 0 else 0.0
            holding_days = max(
                0,
                int((datetime.fromisoformat(exit_date) - datetime.fromisoformat(lot.entry_date)).days),
            )
            closed.append(
                ClosedTrade(
                    symbol=symbol,
                    quantity=matched,
                    entry_date=lot.entry_date,
                    exit_date=exit_date,
                    entry_price=lot.entry_price,
                    exit_price=exit_price,
                    realized_pnl=round(realized, 6),
                    realized_pnl_pct=round(realized_pct, 6),
                    holding_days=holding_days,
                    fees=round(entry_fee_alloc + exit_fee_alloc, 6),
                    stamp_tax=round(tax_alloc, 6),
                    slippage_cost=round(slippage_alloc, 6),
                    exit_reason=exit_reason,
                )
            )
            lot.quantity -= matched
            lot.entry_fee -= entry_fee_alloc
            remaining -= matched
            if lot.quantity <= 0:
                lots.pop(0)
        if not lots and symbol in self.lots:
            self.lots.pop(symbol)
        return closed

    def quantity(self, symbol: str) -> int:
        return sum(lot.quantity for lot in self.lots.get(symbol, []))

    def average_cost(self, symbol: str) -> float:
        lots = self.lots.get(symbol, [])
        quantity = sum(lot.quantity for lot in lots)
        if quantity <= 0:
            return 0.0
        return sum(lot.quantity * lot.entry_price for lot in lots) / quantity

    def open_position_count(self) -> int:
        return len([symbol for symbol in self.lots if self.quantity(symbol) > 0])
