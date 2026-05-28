from app.config import settings
from app.models import (
    SimulationAccountView,
    SimulationFill,
    SimulationOrder,
    SimulationPositionView,
    TradeSide,
)
from app.storage.sqlite_store import SQLiteStore


class SimulatedBroker:
    def __init__(self, account_name: str = "default") -> None:
        self.account_name = account_name
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def execute(self, order: SimulationOrder) -> SimulationFill:
        if order.quantity % settings.min_order_lot != 0:
            raise ValueError(f"A股买卖数量必须是 {settings.min_order_lot} 股的整数倍")
        if order.quantity <= 0:
            raise ValueError("交易数量必须大于0")
        if order.price <= 0:
            raise ValueError("交易价格必须大于0")

        slippage_price = self._apply_slippage(order)
        amount = slippage_price * order.quantity
        fee = max(amount * settings.commission_rate, 5)
        stamp_tax = amount * settings.stamp_tax_rate if order.side == TradeSide.sell else 0

        fill = SimulationFill(
            order=order,
            filled_quantity=order.quantity,
            fill_price=slippage_price,
            fee=fee,
            stamp_tax=stamp_tax,
        )
        self._apply_fill(fill)
        return fill

    def _apply_slippage(self, order: SimulationOrder) -> float:
        direction = 1 if order.side == TradeSide.buy else -1
        return round(order.price * (1 + direction * settings.slippage_rate), 3)

    def account(self) -> SimulationAccountView:
        account = self._ensure_account()
        positions = self.store.fetch_all(
            """
            SELECT symbol, name, quantity, sellable_quantity, avg_cost
            FROM simulation_positions
            WHERE account_id = ?
            ORDER BY symbol
            """,
            (account["id"],),
        )
        return SimulationAccountView(
            account_id=account["id"],
            name=account["name"],
            cash=round(float(account["cash"]), 2),
            initial_cash=float(account["initial_cash"]),
            positions=[SimulationPositionView(**position) for position in positions],
        )

    def settle_next_day(self) -> SimulationAccountView:
        account = self._ensure_account()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE simulation_positions
                SET sellable_quantity = quantity, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ?
                """,
                (account["id"],),
            )
        return self.account()

    def fills(self, limit: int = 50) -> list[dict]:
        account = self._ensure_account()
        return self.store.fetch_all(
            """
            SELECT symbol, side, quantity, fill_price, amount, fee, stamp_tax, created_at
            FROM simulation_fills
            WHERE account_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (account["id"], max(1, min(limit, 200))),
        )

    def _ensure_account(self) -> dict:
        account = self.store.fetch_one(
            "SELECT id, name, cash, initial_cash FROM simulation_accounts WHERE name = ?",
            (self.account_name,),
        )
        if account:
            return account
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO simulation_accounts(name, cash, initial_cash)
                VALUES (?, ?, ?)
                """,
                (self.account_name, settings.default_cash, settings.default_cash),
            )
            account_id = int(cursor.lastrowid)
        return {
            "id": account_id,
            "name": self.account_name,
            "cash": settings.default_cash,
            "initial_cash": settings.default_cash,
        }

    def _apply_fill(self, fill: SimulationFill) -> None:
        account = self._ensure_account()
        order = fill.order
        amount = fill.fill_price * fill.filled_quantity
        total_cost = amount + fill.fee + fill.stamp_tax
        with self.store.connect() as conn:
            if order.side == TradeSide.buy:
                if float(account["cash"]) < total_cost:
                    raise ValueError("模拟账户现金不足")
                self._apply_buy(conn, int(account["id"]), fill, total_cost)
            else:
                self._apply_sell(conn, int(account["id"]), fill, amount)

            conn.execute(
                """
                INSERT INTO simulation_fills(
                    account_id, symbol, side, quantity, fill_price,
                    amount, fee, stamp_tax, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account["id"],
                    order.symbol,
                    order.side.value,
                    fill.filled_quantity,
                    fill.fill_price,
                    amount,
                    fill.fee,
                    fill.stamp_tax,
                    fill.model_dump_json(),
                ),
            )

    def _apply_buy(self, conn, account_id: int, fill: SimulationFill, total_cost: float) -> None:
        order = fill.order
        position = conn.execute(
            """
            SELECT quantity, avg_cost
            FROM simulation_positions
            WHERE account_id = ? AND symbol = ?
            """,
            (account_id, order.symbol),
        ).fetchone()
        if position:
            old_quantity = int(position["quantity"])
            old_cost = float(position["avg_cost"])
            new_quantity = old_quantity + fill.filled_quantity
            new_avg = ((old_quantity * old_cost) + (fill.filled_quantity * fill.fill_price)) / new_quantity
            conn.execute(
                """
                UPDATE simulation_positions
                SET quantity = ?, avg_cost = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND symbol = ?
                """,
                (new_quantity, new_avg, account_id, order.symbol),
            )
        else:
            conn.execute(
                """
                INSERT INTO simulation_positions(
                    account_id, symbol, quantity, sellable_quantity, avg_cost
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (account_id, order.symbol, fill.filled_quantity, 0, fill.fill_price),
            )
        conn.execute(
            """
            UPDATE simulation_accounts
            SET cash = cash - ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (total_cost, account_id),
        )

    def _apply_sell(self, conn, account_id: int, fill: SimulationFill, amount: float) -> None:
        order = fill.order
        position = conn.execute(
            """
            SELECT quantity, sellable_quantity
            FROM simulation_positions
            WHERE account_id = ? AND symbol = ?
            """,
            (account_id, order.symbol),
        ).fetchone()
        if not position:
            raise ValueError("模拟账户没有该股票持仓")
        if int(position["sellable_quantity"]) < fill.filled_quantity:
            raise ValueError("T+1限制：当前可卖数量不足")

        remaining = int(position["quantity"]) - fill.filled_quantity
        if remaining > 0:
            conn.execute(
                """
                UPDATE simulation_positions
                SET quantity = ?, sellable_quantity = sellable_quantity - ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND symbol = ?
                """,
                (remaining, fill.filled_quantity, account_id, order.symbol),
            )
        else:
            conn.execute(
                """
                DELETE FROM simulation_positions
                WHERE account_id = ? AND symbol = ?
                """,
                (account_id, order.symbol),
            )

        conn.execute(
            """
            UPDATE simulation_accounts
            SET cash = cash + ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (amount - fill.fee - fill.stamp_tax, account_id),
        )
