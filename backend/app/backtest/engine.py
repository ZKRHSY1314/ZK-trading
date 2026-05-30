from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd

from app.backtest.execution import BacktestExecutionModel, ExecutionDecision
from app.backtest.ledger import ClosedTrade, FIFOLedger
from app.config import settings
from app.data.price_limits import infer_board_type, limit_up_threshold
from app.data.symbols import normalize_a_share_code
from app.market_regime.service import MarketRegimeService
from app.models import CandidateTier, MarketSnapshot
from app.rules.engine import RuleEngine
from app.rules.loader import load_rule_config
from app.storage.sqlite_store import SQLiteStore


class BacktestEngine:
    def __init__(self, config: dict | None = None):
        self.config = config or load_rule_config()
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.rule_engine = RuleEngine(self.config)
        self.execution = BacktestExecutionModel()
        self.fee_rate = settings.commission_rate
        self.stamp_tax = settings.stamp_tax_rate
        self.slippage = settings.slippage_rate
        self.lot_size = settings.min_order_lot

    def run(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str],
        initial_cash: float,
        max_positions: int,
        per_symbol_cap: float,
        benchmark_symbol: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        benchmark_symbol = benchmark_symbol or settings.backtest_default_benchmark_symbol
        cash = initial_cash
        ledger = FIFOLedger()
        sellable: dict[str, int] = {}
        trades: list[dict[str, Any]] = []
        closed_trades: list[ClosedTrade] = []
        daily_equity: list[dict[str, Any]] = []
        warnings: list[str] = []

        dfs = self._load_symbol_frames(symbols)
        all_dates = self._trade_dates(dfs, start_date, end_date)

        skipped_count = 0
        rejected_count = 0
        blocked_by_regime_count = 0
        regime_service = MarketRegimeService()

        for current_date in all_dates:
            curr_dt = pd.to_datetime(current_date)
            for sym in list(ledger.lots):
                sellable[sym] = ledger.quantity(sym)

            regime_data = regime_service.get_latest_regime(current_date)
            regime = regime_data.get("regime", "neutral")

            for sym in list(ledger.lots):
                if sym not in dfs or curr_dt not in dfs[sym].index:
                    continue
                bar = dict(dfs[sym].loc[curr_dt])
                avg_cost = ledger.average_cost(sym)
                sell_price = None
                sell_reason = ""
                if float(bar["low"]) <= avg_cost * 0.92:
                    sell_price = float(bar["open"]) if float(bar["open"]) <= avg_cost * 0.92 else avg_cost * 0.92
                    sell_reason = "stop_loss"
                elif float(bar["high"]) >= avg_cost * 1.15:
                    sell_price = float(bar["open"]) if float(bar["open"]) >= avg_cost * 1.15 else avg_cost * 1.15
                    sell_reason = "take_profit"
                elif self._oldest_holding_days(ledger, sym, current_date) >= 5:
                    sell_price = float(bar["open"])
                    sell_reason = "max_holding_days"

                if sell_price is None:
                    continue

                previous_close = self._previous_close(dfs[sym], curr_dt)
                decision = self.execution.decide(
                    side="sell",
                    requested_quantity=sellable.get(sym, 0),
                    price=round(sell_price * (1 - self.slippage), 4),
                    bar=bar,
                    previous_close=previous_close,
                    limit_pct=self._limit_pct(sym),
                )
                self._append_trade(trades, sym, current_date, sell_reason, decision)
                if decision.fill_status == "rejected":
                    warnings.append(f"{current_date} {sym} exit blocked: {decision.reject_reason}")
                    continue

                proceeds = decision.price * decision.filled_quantity - decision.fee - decision.stamp_tax
                cash += proceeds
                matched = ledger.sell(
                    symbol=sym,
                    quantity=decision.filled_quantity,
                    exit_price=decision.price,
                    exit_date=current_date,
                    fee=decision.fee,
                    stamp_tax=decision.stamp_tax,
                    exit_reason=sell_reason,
                    slippage_cost=abs(sell_price - decision.price) * decision.filled_quantity,
                )
                closed_trades.extend(matched)
                sellable[sym] = max(0, sellable.get(sym, 0) - decision.filled_quantity)

            candidates = []
            for sym, df in dfs.items():
                if curr_dt not in df.index or ledger.quantity(sym) > 0:
                    continue
                hist = df.loc[:curr_dt]
                if len(hist) < 2:
                    continue
                bar = hist.iloc[-1]
                prev_bar = hist.iloc[-2]
                if pd.isna(bar["close"]) or pd.isna(bar["open"]):
                    skipped_count += 1
                    continue
                snapshot = self._snapshot(sym, current_date, hist, bar, prev_bar)
                decision = self.rule_engine.evaluate(snapshot)
                if decision.blocked:
                    rejected_count += 1
                elif decision.tier == CandidateTier.strong:
                    candidates.append((sym, decision.score, snapshot, dict(bar)))

            candidates.sort(key=lambda item: item[1], reverse=True)
            if regime == "extreme_risk":
                blocked_by_regime_count += len(candidates)
                candidates = []

            for sym, _, snapshot, bar in candidates:
                if ledger.open_position_count() >= max_positions:
                    break
                alloc_cap = per_symbol_cap * (0.5 if regime == "weak" else 1.0)
                equity_before = cash + self._positions_value(ledger, dfs, curr_dt)
                alloc = min(cash, equity_before * alloc_cap)
                buy_price = round(snapshot.close * (1 + self.slippage), 4)
                requested_qty = int(alloc / buy_price) // self.lot_size * self.lot_size
                decision = self.execution.decide(
                    side="buy",
                    requested_quantity=requested_qty,
                    price=buy_price,
                    bar=bar,
                    previous_close=float(snapshot.metadata["previous_close"]),
                    limit_pct=float(snapshot.metadata["limit_up_threshold"]),
                )
                self._append_trade(trades, sym, current_date, "strong_signal", decision)
                if decision.fill_status == "rejected":
                    warnings.append(f"{current_date} {sym} entry rejected: {decision.reject_reason}")
                    continue
                total_cost = decision.price * decision.filled_quantity + decision.fee
                if total_cost > cash:
                    continue
                cash -= total_cost
                ledger.buy(sym, decision.filled_quantity, decision.price, current_date, decision.fee)
                sellable[sym] = 0

            positions_value = self._positions_value(ledger, dfs, curr_dt)
            daily_equity.append(
                {
                    "trade_date": current_date,
                    "cash": round(cash, 6),
                    "positions_value": round(positions_value, 6),
                    "total_equity": round(cash + positions_value, 6),
                }
            )

        final_equity = daily_equity[-1]["total_equity"] if daily_equity else initial_cash
        benchmark = self._benchmark(benchmark_symbol, start_date, end_date, daily_equity)
        if benchmark.get("status") != "ready":
            warnings.append("insufficient_benchmark_data")
        metrics = self._metrics(
            initial_cash=initial_cash,
            final_equity=final_equity,
            daily_equity=daily_equity,
            trades=trades,
            closed_trades=closed_trades,
            open_position_count=ledger.open_position_count(),
            skipped_count=skipped_count,
            rejected_count=rejected_count,
            blocked_by_regime_count=blocked_by_regime_count,
            benchmark=benchmark,
        )
        status = "completed" if daily_equity else "insufficient_data"

        run_id = None
        if persist:
            run_id = self._persist(
                start_date=start_date,
                end_date=end_date,
                status=status,
                initial_cash=initial_cash,
                final_equity=final_equity,
                metrics=metrics,
                benchmark_symbol=benchmark_symbol,
                benchmark=benchmark,
                warnings=warnings,
                trades=trades,
                closed_trades=closed_trades,
                daily_equity=daily_equity,
            )

        return {
            "run_id": run_id or 0,
            "status": status,
            "metrics": metrics,
            "trades": len(trades),
            "closed_trades": len(closed_trades),
            "days": len(daily_equity),
            "benchmark": benchmark,
            "execution_warnings": warnings,
            "simulation_only": True,
        }

    def _load_symbol_frames(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        params: list[Any] = []
        if symbols:
            variants = sorted({item for symbol in symbols for item in {symbol, symbol.upper(), symbol.lower()}})
            placeholders = ",".join("?" for _ in variants)
            where_clause = f"symbol IN ({placeholders}) AND quality_status = 'ready'"
            params.extend(variants)
        else:
            where_clause = "quality_status = 'ready'"
        rows = self.store.fetch_all(
            f"""
            SELECT symbol, trade_date, open, high, low, close, volume, amount, quality_status
            FROM daily_bar_cache
            WHERE {where_clause}
            ORDER BY trade_date ASC
            """,
            tuple(params),
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["symbol"]].append(dict(row))
        frames = {}
        for sym, records in grouped.items():
            df = pd.DataFrame(records)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df.set_index("trade_date", inplace=True)
            frames[sym] = df
        return frames

    def _trade_dates(self, dfs: dict[str, pd.DataFrame], start_date: str, end_date: str) -> list[str]:
        dates = {
            index.strftime("%Y-%m-%d")
            for df in dfs.values()
            for index in df.index
            if start_date <= index.strftime("%Y-%m-%d") <= end_date
        }
        return sorted(dates)

    def _snapshot(self, sym: str, current_date: str, hist: pd.DataFrame, bar: pd.Series, prev_bar: pd.Series) -> MarketSnapshot:
        code = normalize_a_share_code(sym)
        board = infer_board_type(code, "")
        limit_pct = limit_up_threshold(board)
        high_250 = hist["high"].tail(250).max()
        high_500 = hist["high"].tail(500).max()
        pct_change = (float(bar["close"]) - float(prev_bar["close"])) / float(prev_bar["close"]) * 100
        five_day_pct = (
            (float(bar["close"]) - float(hist.iloc[-6]["close"])) / float(hist.iloc[-6]["close"]) * 100
            if len(hist) >= 6
            else 0.0
        )
        volume_mean = hist["volume"].iloc[-6:-1].mean() if len(hist) >= 6 else 0
        volume_ratio = float(bar["volume"]) / volume_mean if volume_mean and volume_mean > 0 else 1.0
        return MarketSnapshot(
            symbol=sym,
            trade_date=current_date,
            price=float(bar["close"]),
            pct_change=float(pct_change),
            high=float(bar["high"]),
            low=float(bar["low"]),
            open=float(bar["open"]),
            close=float(bar["close"]),
            volume=float(bar["volume"]),
            amount=float(bar["amount"]),
            historical_high=float(high_250),
            metadata={
                "data_quality": "daily_bar",
                "board_type": board,
                "limit_up_threshold": limit_pct,
                "high_250": float(high_250),
                "high_500": float(high_500),
                "volume_ratio": float(volume_ratio),
                "five_day_pct": float(five_day_pct),
                "previous_close": float(prev_bar["close"]),
            },
        )

    def _limit_pct(self, sym: str) -> float:
        return limit_up_threshold(infer_board_type(normalize_a_share_code(sym), ""))

    def _previous_close(self, df: pd.DataFrame, current_dt: pd.Timestamp) -> float:
        hist = df.loc[:current_dt]
        if len(hist) >= 2:
            return float(hist.iloc[-2]["close"])
        return float(hist.iloc[-1]["close"])

    def _oldest_holding_days(self, ledger: FIFOLedger, symbol: str, current_date: str) -> int:
        lots = ledger.lots.get(symbol, [])
        if not lots:
            return 0
        oldest = min(lot.entry_date for lot in lots)
        return max(0, int((datetime.fromisoformat(current_date) - datetime.fromisoformat(oldest)).days))

    def _positions_value(self, ledger: FIFOLedger, dfs: dict[str, pd.DataFrame], current_dt: pd.Timestamp) -> float:
        value = 0.0
        for sym in list(ledger.lots):
            qty = ledger.quantity(sym)
            if sym in dfs and current_dt in dfs[sym].index:
                value += qty * float(dfs[sym].loc[current_dt]["close"])
            else:
                value += qty * ledger.average_cost(sym)
        return value

    def _append_trade(
        self,
        trades: list[dict[str, Any]],
        symbol: str,
        trade_date: str,
        reason: str,
        decision: ExecutionDecision,
    ) -> None:
        trades.append(
            {
                "symbol": symbol,
                "side": decision.side,
                "quantity": decision.filled_quantity,
                "price": decision.price,
                "fee": decision.fee,
                "stamp_tax": decision.stamp_tax,
                "trade_date": trade_date,
                "reason": reason,
                "fill_status": decision.fill_status,
                "reject_reason": decision.reject_reason,
                "requested_quantity": decision.requested_quantity,
                "filled_quantity": decision.filled_quantity,
                "liquidity_cap_amount": decision.liquidity_cap_amount,
            }
        )

    def _benchmark(
        self,
        benchmark_symbol: str,
        start_date: str,
        end_date: str,
        daily_equity: list[dict[str, Any]],
    ) -> dict[str, Any]:
        symbols = sorted({benchmark_symbol, benchmark_symbol.upper(), benchmark_symbol.lower()})
        placeholders = ",".join("?" for _ in symbols)
        rows = self.store.fetch_all(
            f"""
            SELECT trade_date, close
            FROM daily_bar_cache
            WHERE symbol IN ({placeholders})
              AND quality_status = 'ready'
              AND trade_date >= ?
              AND trade_date <= ?
            ORDER BY trade_date ASC
            """,
            tuple(symbols + [start_date, end_date]),
        )
        if len(rows) < 2:
            return {"symbol": benchmark_symbol, "status": "insufficient_benchmark_data"}
        closes = [float(row["close"]) for row in rows]
        benchmark_return = closes[-1] / closes[0] - 1
        peak = closes[0]
        max_drawdown = 0.0
        for close in closes:
            peak = max(peak, close)
            max_drawdown = max(max_drawdown, (peak - close) / peak if peak else 0.0)
        correlation = None
        if daily_equity and len(rows) > 2:
            eq = pd.DataFrame(daily_equity)
            bm = pd.DataFrame([dict(row) for row in rows])
            merged = eq.merge(bm, on="trade_date", how="inner")
            if len(merged) > 2:
                corr = merged["total_equity"].pct_change().corr(merged["close"].pct_change())
                correlation = None if pd.isna(corr) else round(float(corr), 6)
        strategy_return = (
            daily_equity[-1]["total_equity"] / daily_equity[0]["total_equity"] - 1
            if len(daily_equity) >= 2 and daily_equity[0]["total_equity"]
            else 0.0
        )
        return {
            "symbol": benchmark_symbol,
            "status": "ready",
            "benchmark_return": round(benchmark_return, 6),
            "benchmark_max_drawdown": round(max_drawdown, 6),
            "excess_return": round(strategy_return - benchmark_return, 6),
            "correlation_to_benchmark": correlation,
        }

    def _metrics(
        self,
        initial_cash: float,
        final_equity: float,
        daily_equity: list[dict[str, Any]],
        trades: list[dict[str, Any]],
        closed_trades: list[ClosedTrade],
        open_position_count: int,
        skipped_count: int,
        rejected_count: int,
        blocked_by_regime_count: int,
        benchmark: dict[str, Any],
    ) -> dict[str, Any]:
        total_return = (final_equity - initial_cash) / initial_cash if initial_cash else 0.0
        max_drawdown = 0.0
        peak = initial_cash
        for eq in daily_equity:
            peak = max(peak, eq["total_equity"])
            max_drawdown = max(max_drawdown, (peak - eq["total_equity"]) / peak if peak else 0.0)
        pnls = [trade.realized_pnl for trade in closed_trades]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        closed_count = len(closed_trades)
        win_rate = len(wins) / closed_count if closed_count else 0.0
        average_win = sum(wins) / len(wins) if wins else 0.0
        average_loss = sum(losses) / len(losses) if losses else 0.0
        loss_rate = 1 - win_rate if closed_count else 0.0
        profit_loss_ratio = average_win / abs(average_loss) if average_loss < 0 else 0.0
        expectancy = win_rate * average_win - loss_rate * abs(average_loss)
        exposure_days = len([eq for eq in daily_equity if eq["positions_value"] > 0])
        consecutive_losses = 0
        max_consecutive_losses = 0
        for closed in sorted(closed_trades, key=lambda item: item.exit_date):
            if closed.realized_pnl < 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        metrics = {
            "total_return": round(total_return, 6),
            "annualized_return": round((1 + total_return) ** (252 / len(daily_equity)) - 1, 6)
            if daily_equity
            else 0.0,
            "max_drawdown": round(max_drawdown, 6),
            "win_rate": round(win_rate, 6),
            "profit_loss_ratio": round(profit_loss_ratio, 6),
            "average_win": round(average_win, 6),
            "average_loss": round(average_loss, 6),
            "expectancy": round(expectancy, 6),
            "trade_count": len([trade for trade in trades if trade["fill_status"] != "rejected"]),
            "closed_trade_count": closed_count,
            "open_position_count": open_position_count,
            "average_holding_days": round(
                sum(trade.holding_days for trade in closed_trades) / closed_count if closed_count else 0.0,
                6,
            ),
            "max_consecutive_losses": max_consecutive_losses,
            "exposure_ratio": round(exposure_days / len(daily_equity), 6) if daily_equity else 0.0,
            "skipped_due_to_data_count": skipped_count,
            "rejected_by_risk_count": rejected_count,
            "blocked_by_regime_count": blocked_by_regime_count,
            "partial_fill_count": len([trade for trade in trades if trade["fill_status"] == "partial"]),
            "rejected_execution_count": len([trade for trade in trades if trade["fill_status"] == "rejected"]),
        }
        if benchmark.get("status") == "ready":
            metrics.update(
                {
                    "benchmark_return": benchmark["benchmark_return"],
                    "benchmark_max_drawdown": benchmark["benchmark_max_drawdown"],
                    "excess_return": benchmark["excess_return"],
                    "correlation_to_benchmark": benchmark["correlation_to_benchmark"],
                }
            )
        return metrics

    def _persist(
        self,
        start_date: str,
        end_date: str,
        status: str,
        initial_cash: float,
        final_equity: float,
        metrics: dict[str, Any],
        benchmark_symbol: str,
        benchmark: dict[str, Any],
        warnings: list[str],
        trades: list[dict[str, Any]],
        closed_trades: list[ClosedTrade],
        daily_equity: list[dict[str, Any]],
    ) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO historical_backtest_runs(
                    config_json, data_source, start_date, end_date, status,
                    benchmark_symbol, initial_cash, final_cash, metrics_json,
                    benchmark_json, execution_warnings_json, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    json.dumps(self.config, ensure_ascii=False),
                    "daily_bar_cache",
                    start_date,
                    end_date,
                    status,
                    benchmark_symbol,
                    initial_cash,
                    final_equity,
                    json.dumps(metrics, ensure_ascii=False),
                    json.dumps(benchmark, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )
            run_id = int(cursor.lastrowid)
            for trade in trades:
                conn.execute(
                    """
                    INSERT INTO historical_backtest_trades(
                        run_id, symbol, side, quantity, price, fee, stamp_tax, trade_date,
                        reason, fill_status, reject_reason, requested_quantity,
                        filled_quantity, liquidity_cap_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        trade["symbol"],
                        trade["side"],
                        trade["quantity"],
                        trade["price"],
                        trade["fee"],
                        trade["stamp_tax"],
                        trade["trade_date"],
                        trade["reason"],
                        trade["fill_status"],
                        trade["reject_reason"],
                        trade["requested_quantity"],
                        trade["filled_quantity"],
                        trade["liquidity_cap_amount"],
                    ),
                )
            for closed in closed_trades:
                item = closed.to_dict()
                conn.execute(
                    """
                    INSERT INTO historical_backtest_closed_trades(
                        run_id, symbol, quantity, entry_date, exit_date, entry_price,
                        exit_price, realized_pnl, realized_pnl_pct, holding_days,
                        fees, stamp_tax, slippage_cost, exit_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        item["symbol"],
                        item["quantity"],
                        item["entry_date"],
                        item["exit_date"],
                        item["entry_price"],
                        item["exit_price"],
                        item["realized_pnl"],
                        item["realized_pnl_pct"],
                        item["holding_days"],
                        item["fees"],
                        item["stamp_tax"],
                        item["slippage_cost"],
                        item["exit_reason"],
                    ),
                )
            for eq in daily_equity:
                conn.execute(
                    """
                    INSERT INTO historical_backtest_daily_equity(
                        run_id, trade_date, cash, positions_value, total_equity
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, eq["trade_date"], eq["cash"], eq["positions_value"], eq["total_equity"]),
                )
        return run_id
