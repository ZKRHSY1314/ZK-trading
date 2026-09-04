from datetime import datetime, timezone

from app.config import settings
from app.models import (
    SimulationAccountView,
    SimulationFill,
    SimulationOrder,
    SimulationPositionView,
    TradeSide,
)
from app.simulation.market_data import SimulationMarketDataService
from app.storage.sqlite_store import SQLiteStore


class SimulatedBroker:
    def __init__(self, account_name: str = "default") -> None:
        self.account_name = account_name
        self.store = SQLiteStore(settings.database_path)

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
        market_data = SimulationMarketDataService(store=self.store)
        screen_snapshot = market_data.screen_position_snapshot()
        position_views: list[SimulationPositionView] = []
        valuation_warnings: list[str] = []
        market_values: list[float] = []
        unrealized_values: list[float] = []
        today_values: list[float] = []
        valuation_times: list[str] = []
        freshness_values: list[str] = []

        for position in positions:
            mark = market_data.mark_snapshot(str(position["symbol"]))
            quantity = int(position["quantity"])
            avg_cost = float(position["avg_cost"])
            market_value = round(quantity * mark.price, 2) if mark.price is not None else None
            unrealized_pnl = (
                round(quantity * (mark.price - avg_cost), 2) if mark.price is not None else None
            )
            today_pnl = (
                round(quantity * (mark.price - mark.previous_close), 2)
                if mark.price is not None and mark.previous_close is not None
                else None
            )
            if market_value is None:
                valuation_warnings.append(f"missing_mark_price:{position['symbol']}")
            else:
                market_values.append(market_value)
                unrealized_values.append(float(unrealized_pnl or 0.0))
            if today_pnl is None:
                valuation_warnings.append(f"missing_previous_close:{position['symbol']}")
            else:
                today_values.append(today_pnl)
            if mark.as_of:
                valuation_times.append(mark.as_of)
            freshness_values.append(mark.freshness)
            position_views.append(
                SimulationPositionView(
                    **position,
                    mark_price=mark.price,
                    previous_close=mark.previous_close,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    today_pnl=today_pnl,
                    mark_source=mark.source,
                    mark_as_of=mark.as_of,
                    freshness=mark.freshness,
                )
            )

        position_count = len(position_views)
        priced_count = len(market_values)
        cash = round(float(account["cash"]), 2)
        if position_count == 0:
            market_value_total: float | None = 0.0
            unrealized_total: float | None = 0.0
            today_total: float | None = 0.0
            total_assets: float | None = cash
            position_ratio: float | None = 0.0
            valuation_status = "complete"
            freshness = "not_applicable"
        elif priced_count == position_count:
            market_value_total = round(sum(market_values), 2)
            unrealized_total = round(sum(unrealized_values), 2)
            total_assets = round(cash + market_value_total, 2)
            position_ratio = round(market_value_total / total_assets * 100, 2) if total_assets > 0 else 0.0
            today_total = round(sum(today_values), 2) if len(today_values) == position_count else None
            valuation_status = "complete" if today_total is not None else "partial"
            freshness = self._aggregate_freshness(freshness_values)
        else:
            market_value_total = None
            unrealized_total = None
            today_total = None
            total_assets = None
            position_ratio = None
            valuation_status = "unavailable" if priced_count == 0 else "partial"
            freshness = self._aggregate_freshness(freshness_values)

        return SimulationAccountView(
            account_id=account["id"],
            name=account["name"],
            cash=cash,
            initial_cash=float(account["initial_cash"]),
            positions=position_views,
            total_assets=total_assets,
            market_value=market_value_total,
            unrealized_pnl=unrealized_total,
            today_pnl=today_total,
            today_pnl_scope="open_positions_mark_to_previous_close",
            position_ratio=position_ratio,
            valuation_status=valuation_status,
            valuation_as_of=self._oldest_valuation_time(valuation_times),
            freshness=freshness,
            valuation_warnings=valuation_warnings,
            screen_snapshot_status=screen_snapshot.status,
            screen_snapshot_reason=screen_snapshot.reason,
            screen_snapshot_scope=screen_snapshot.scope,
            screen_snapshot_as_of=screen_snapshot.as_of,
            screen_positions=screen_snapshot.positions,
            simulation_only=True,
            live_trading_enabled=False,
        )

    @staticmethod
    def _aggregate_freshness(values: list[str]) -> str:
        unique = {value for value in values if value}
        if not unique:
            return "unavailable"
        if len(unique) == 1:
            return next(iter(unique))
        return "mixed"

    @staticmethod
    def _oldest_valuation_time(values: list[str]) -> str | None:
        if not values:
            return None

        def sort_key(value: str) -> datetime:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return datetime.max.replace(tzinfo=timezone.utc)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

        return min(values, key=sort_key)

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
            synced = self._sync_empty_account_cash(account)
            if synced:
                return synced
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

    def _sync_empty_account_cash(self, account: dict) -> dict | None:
        current_initial = float(account["initial_cash"])
        current_cash = float(account["cash"])
        if current_initial == float(settings.default_cash) or current_cash != current_initial:
            return None
        position_count = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM simulation_positions WHERE account_id = ?",
            (account["id"],),
        )
        fill_count = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM simulation_fills WHERE account_id = ?",
            (account["id"],),
        )
        if int((position_count or {}).get("cnt") or 0) or int((fill_count or {}).get("cnt") or 0):
            return None
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE simulation_accounts
                SET cash = ?, initial_cash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (settings.default_cash, settings.default_cash, account["id"]),
            )
        updated = dict(account)
        updated["cash"] = settings.default_cash
        updated["initial_cash"] = settings.default_cash
        return updated

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
