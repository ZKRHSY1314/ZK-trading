import json
from datetime import datetime
import pandas as pd
from collections import defaultdict
from typing import Any

from app.config import settings
from app.models import MarketSnapshot, CandidateTier, TradeSide
from app.rules.engine import RuleEngine
from app.rules.loader import load_rule_config
from app.storage.sqlite_store import SQLiteStore
from app.backtest.metrics import BacktestMetrics
from app.data.symbols import normalize_a_share_code, with_exchange_prefix
from app.data.price_limits import infer_board_type, limit_up_threshold

class BacktestEngine:
    def __init__(self, config: dict | None = None):
        self.config = config or load_rule_config()
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.rule_engine = RuleEngine(self.config)
        self.fee_rate = settings.commission_rate
        self.stamp_tax = settings.stamp_tax_rate
        self.slippage = settings.slippage_rate
        self.lot_size = settings.min_order_lot

    def run(self, start_date: str, end_date: str, symbols: list[str], initial_cash: float, max_positions: int, per_symbol_cap: float) -> dict[str, Any]:
        cash = initial_cash
        positions = {} # symbol -> {quantity, avg_cost, days_held, sellable_quantity}
        trades = []
        daily_equity = []

        with self.store.connect() as conn:
            params: list[Any] = []
            if symbols:
                placeholders = ",".join("?" for _ in symbols)
                where_clause = f"symbol IN ({placeholders}) AND quality_status = 'ready'"
                params.extend(symbols)
            else:
                where_clause = "quality_status = 'ready'"

            sql = f"""
                SELECT symbol, trade_date, open, high, low, close, volume, amount, quality_status
                FROM daily_bar_cache
                WHERE {where_clause}
                ORDER BY trade_date ASC
            """
            all_rows = conn.execute(sql, tuple(params)).fetchall()

        # Group by symbol to build dataframes
        symbol_data = defaultdict(list)
        for r in all_rows:
            symbol_data[r['symbol']].append(dict(r))

        dfs = {}
        for sym, records in symbol_data.items():
            df = pd.DataFrame(records)
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df.set_index('trade_date', inplace=True)
            dfs[sym] = df

        # Get all unique trade dates in range
        all_dates = sorted(list(set(r['trade_date'] for r in all_rows if start_date <= r['trade_date'] <= end_date)))

        skipped_count = 0
        rejected_count = 0
        blocked_by_regime_count = 0

        from app.market_regime.service import MarketRegimeService
        regime_service = MarketRegimeService()

        for current_date in all_dates:
            regime_data = regime_service.get_latest_regime(current_date)
            regime = regime_data.get("regime", "neutral")
            curr_dt = pd.to_datetime(current_date)
            # T+1 rollover
            for sym, pos in positions.items():
                pos['sellable_quantity'] = pos['quantity']
                pos['days_held'] += 1

            # 1. Process exits (Stop Loss, Take Profit, Max Days)
            symbols_to_remove = []
            for sym, pos in positions.items():
                if sym not in dfs:
                    continue
                df = dfs[sym]
                if curr_dt not in df.index:
                    continue
                bar = df.loc[curr_dt]

                sell_price = None
                sell_reason = ""

                # Check simple stop loss / take profit
                cost = pos['avg_cost']
                if bar['low'] <= cost * 0.92:
                    sell_price = bar['open'] if bar['open'] <= cost * 0.92 else cost * 0.92
                    sell_reason = "stop_loss"
                elif bar['high'] >= cost * 1.15:
                    sell_price = bar['open'] if bar['open'] >= cost * 1.15 else cost * 1.15
                    sell_reason = "take_profit"
                elif pos['days_held'] >= 5:
                    sell_price = bar['open']
                    sell_reason = "max_holding_days"

                # Cannot sell if low >= limit up (limit up open and stick, though rare for exits)
                # Cannot sell if high <= limit down (limit down open and stick)
                code = normalize_a_share_code(sym)
                board = infer_board_type(code, "")
                limit_up_pct = limit_up_threshold(board)
                prev_bar = df.loc[:curr_dt].iloc[-2] if len(df.loc[:curr_dt]) > 1 else None
                if prev_bar is not None:
                    limit_down_price = prev_bar['close'] * (1 - limit_up_pct / 100)
                    if bar['high'] <= limit_down_price * 1.01: # Limit down, cannot sell
                        sell_price = None

                if sell_price and pos['sellable_quantity'] > 0:
                    qty = pos['sellable_quantity']
                    price = sell_price * (1 - self.slippage)
                    amount = price * qty
                    fee = max(amount * self.fee_rate, 5)
                    tax = amount * self.stamp_tax
                    cash += (amount - fee - tax)
                    trades.append({
                        "symbol": sym, "side": "sell", "quantity": qty, "price": price,
                        "fee": fee, "stamp_tax": tax, "trade_date": current_date, "reason": sell_reason
                    })
                    symbols_to_remove.append(sym)

            for sym in symbols_to_remove:
                del positions[sym]

            # 2. Process entries
            candidates = []
            for sym, df in dfs.items():
                if curr_dt not in df.index:
                    continue
                hist = df.loc[:curr_dt]
                if len(hist) < 2:
                    continue
                bar = hist.iloc[-1]
                prev_bar = hist.iloc[-2]

                if pd.isna(bar['close']) or pd.isna(bar['open']):
                    skipped_count += 1
                    continue

                code = normalize_a_share_code(sym)
                board = infer_board_type(code, "")
                limit_up_pct = limit_up_threshold(board)

                # Calculate features
                high_250 = hist['high'].tail(250).max()
                high_500 = hist['high'].tail(500).max()
                pct_change = (bar['close'] - prev_bar['close']) / prev_bar['close'] * 100
                five_day_pct = (bar['close'] - hist.iloc[-6]['close']) / hist.iloc[-6]['close'] * 100 if len(hist) >= 6 else 0
                vol_ratio = bar['volume'] / hist['volume'].iloc[-6:-1].mean() if len(hist) >= 6 and hist['volume'].iloc[-6:-1].mean() > 0 else 1.0

                snapshot = MarketSnapshot(
                    symbol=sym,
                    trade_date=current_date,
                    price=float(bar['close']),
                    pct_change=float(pct_change),
                    high=float(bar['high']),
                    low=float(bar['low']),
                    open=float(bar['open']),
                    close=float(bar['close']),
                    volume=float(bar['volume']),
                    amount=float(bar['amount']),
                    historical_high=float(high_250),
                    metadata={
                        "data_quality": "daily_bar",
                        "board_type": board,
                        "limit_up_threshold": limit_up_pct,
                        "high_250": float(high_250),
                        "high_500": float(high_500),
                        "volume_ratio": float(vol_ratio),
                        "five_day_pct": float(five_day_pct),
                        "previous_close": float(prev_bar['close'])
                    }
                )

                decision = self.rule_engine.evaluate(snapshot)
                if decision.blocked:
                    rejected_count += 1
                elif decision.tier == CandidateTier.strong:
                    candidates.append((sym, decision.score, snapshot))

            candidates.sort(key=lambda x: x[1], reverse=True)

            if regime == "extreme_risk":
                blocked_by_regime_count += len(candidates)
                candidates = []

            for sym, score, snapshot in candidates:
                if len(positions) >= max_positions:
                    break
                if sym in positions:
                    continue

                # Check limit up open and stick (can't buy)
                limit_up_price = snapshot.metadata['previous_close'] * (1 + snapshot.metadata['limit_up_threshold'] / 100)
                if snapshot.low >= limit_up_price * 0.99:
                    continue # Cannot buy

                # Size position
                alloc_cap = per_symbol_cap * (0.5 if regime == "weak" else 1.0)
                max_alloc = (cash + sum(p['quantity'] * dfs[s].loc[curr_dt]['close'] for s, p in positions.items() if s in dfs and curr_dt in dfs[s].index)) * alloc_cap
                alloc = min(cash, max_alloc)
                buy_price = snapshot.close * (1 + self.slippage)
                qty = int(alloc / buy_price) // self.lot_size * self.lot_size

                if qty >= self.lot_size:
                    amount = buy_price * qty
                    fee = max(amount * self.fee_rate, 5)
                    total_cost = amount + fee
                    if cash >= total_cost:
                        cash -= total_cost
                        positions[sym] = {
                            'quantity': qty,
                            'sellable_quantity': 0,
                            'avg_cost': buy_price,
                            'days_held': 0
                        }
                        trades.append({
                            "symbol": sym, "side": "buy", "quantity": qty, "price": buy_price,
                            "fee": fee, "stamp_tax": 0.0, "trade_date": current_date, "reason": "strong_signal"
                        })

            # Record daily equity
            pos_value = 0
            for sym, pos in positions.items():
                if sym in dfs and curr_dt in dfs[sym].index:
                    pos_value += pos['quantity'] * dfs[sym].loc[curr_dt]['close']
                else:
                    pos_value += pos['quantity'] * pos['avg_cost']

            daily_equity.append({
                "trade_date": current_date,
                "cash": cash,
                "positions_value": pos_value,
                "total_equity": cash + pos_value
            })

        # Calculate metrics
        final_equity = daily_equity[-1]['total_equity'] if daily_equity else initial_cash
        total_return = (final_equity - initial_cash) / initial_cash

        max_drawdown = 0
        peak = initial_cash
        for eq in daily_equity:
            if eq['total_equity'] > peak:
                peak = eq['total_equity']
            dd = (peak - eq['total_equity']) / peak
            if dd > max_drawdown:
                max_drawdown = dd

        winning_trades = len([t for t in trades if t['side'] == 'sell' and t['price'] > sum(b['price'] for b in trades if b['side'] == 'buy' and b['symbol'] == t['symbol']) / max(1, len([b for b in trades if b['side'] == 'buy' and b['symbol'] == t['symbol']]))])
        sell_trades = len([t for t in trades if t['side'] == 'sell'])
        win_rate = winning_trades / sell_trades if sell_trades > 0 else 0

        gross_profit = sum(t['price']*t['quantity'] for t in trades if t['side'] == 'sell')
        gross_loss = sum(b['price']*b['quantity'] for b in trades if b['side'] == 'buy')
        pl_ratio = gross_profit / gross_loss if gross_loss > 0 else 0
        buy_dates: dict[str, list[str]] = defaultdict(list)
        holding_days: list[int] = []
        for trade in trades:
            if trade["side"] == "buy":
                buy_dates[trade["symbol"]].append(trade["trade_date"])
            elif trade["side"] == "sell" and buy_dates[trade["symbol"]]:
                start = pd.to_datetime(buy_dates[trade["symbol"]].pop(0))
                end = pd.to_datetime(trade["trade_date"])
                holding_days.append(max(0, int((end - start).days)))
        avg_holding_days = sum(holding_days) / len(holding_days) if holding_days else 0
        exposure_days = len([eq for eq in daily_equity if eq["positions_value"] > 0])
        exposure_ratio = exposure_days / len(daily_equity) if daily_equity else 0

        metrics_dict = {
            "total_return": total_return,
            "annualized_return": (1 + total_return) ** (252 / len(daily_equity)) - 1 if daily_equity else 0,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_loss_ratio": pl_ratio,
            "trade_count": len(trades) // 2,
            "average_holding_days": avg_holding_days,
            "exposure_ratio": exposure_ratio,
            "skipped_due_to_data_count": skipped_count,
            "rejected_by_risk_count": rejected_count,
            "blocked_by_regime_count": blocked_by_regime_count,
        }
        status = "completed" if daily_equity else "insufficient_data"

        # Persist
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO historical_backtest_runs(
                    config_json, data_source, start_date, end_date, status,
                    initial_cash, final_cash, metrics_json, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    json.dumps(self.config), "daily_bar_cache", start_date, end_date, status,
                    initial_cash, final_equity, json.dumps(metrics_dict), datetime.now().isoformat()
                )
            )
            run_id = cursor.lastrowid

            for t in trades:
                conn.execute(
                    """
                    INSERT INTO historical_backtest_trades(
                        run_id, symbol, side, quantity, price, fee, stamp_tax, trade_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, t['symbol'], t['side'], t['quantity'], t['price'], t['fee'], t['stamp_tax'], t['trade_date'])
                )

            for eq in daily_equity:
                conn.execute(
                    """
                    INSERT INTO historical_backtest_daily_equity(
                        run_id, trade_date, cash, positions_value, total_equity
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, eq['trade_date'], eq['cash'], eq['positions_value'], eq['total_equity'])
                )

        return {
            "run_id": run_id,
            "status": status,
            "metrics": metrics_dict,
            "trades": len(trades),
            "days": len(daily_equity)
        }
