from dataclasses import dataclass, field


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_cost: float
    sellable_quantity: int = 0


@dataclass
class SimulatedAccount:
    cash: float = 100_000
    positions: dict[str, Position] = field(default_factory=dict)

    def position_of(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)
