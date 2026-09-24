from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import pandas as pd

from app.backtest.execution import BacktestExecutionModel, ExecutionDecision
from app.backtest.execution_contract import (
    FILL_POLICIES,
    FILL_POLICY_RETROSPECTIVE,
    ORDER_MARKET_AT_OPEN,
    ORDER_RESTING_LIMIT,
    ORDER_RESTING_STOP,
    OrderIntent,
    adjudication_bases,
    execution_contract,
)
from app.backtest.ledger import ClosedTrade, FIFOLedger
from app.config import settings
from app.data.fundamentals import FundamentalResolver
from app.data.price_limits import infer_board_type, limit_up_threshold
from app.data.symbols import normalize_a_share_code
from app.market_regime.service import MarketRegimeService
from app.models import CandidateTier, MarketSnapshot
from app.rules.engine import RuleEngine
from app.rules.loader import load_rule_config
from app.storage.sqlite_store import SQLiteStore


PRICE_COLUMNS = ["open", "high", "low", "close"]
NUMERIC_BAR_COLUMNS = PRICE_COLUMNS + ["volume", "amount"]


# Used when a config carries no exit_rules block. Absence must not mean "never
# exit": a caller passing a hand-built config would otherwise hold every
# position to the end of the window and report it as an open-ended run. These
# mirror configs/rules.yaml, so behaviour is the same whether or not the block
# is present.
DEFAULT_EXIT_RULES: dict[str, Any] = {
    "stop_loss_pct": 6.0,
    "partial_take_profit_pct": 15.0,
    "partial_take_profit_ratio": 0.5,
    "break_ma_window": 5,
    "require_below_limit_up_avg": True,
    "max_holding_days": None,
}


class BacktestEngine:
    def __init__(self, config: dict | None = None):
        self.config = config or load_rule_config()
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.rule_engine = RuleEngine(self.config)
        # Exit parameters live in rules.yaml so the strategy owns them; see the
        # exit_rules block there for why the old hardcoded 5-day close was wrong.
        self.exit_rules = dict(self.config.get("exit_rules") or DEFAULT_EXIT_RULES)
        # The ARMED window is strategy state, but rule evaluation is stateless,
        # so the engine tracks it and feeds it back in as snapshot metadata.
        self.s0_params = next(
            (
                dict(rule.get("params") or {})
                for rule in self.config.get("rules", [])
                if rule.get("id") == "dengzhan_low_position_limit_up"
                and rule.get("enabled", True)
            ),
            None,
        )
        self.armed_window_days = int((self.s0_params or {}).get("armed_window_days") or 0)
        self.execution = BacktestExecutionModel()
        self.fee_rate = settings.commission_rate
        self.stamp_tax = settings.stamp_tax_rate
        self.slippage = settings.slippage_rate
        self.lot_size = settings.min_order_lot
        self._fundamentals: FundamentalResolver | None = None
        self._project_fundamentals = False

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
        allow_projected_fundamentals: bool = False,
        fill_policy: str = FILL_POLICY_RETROSPECTIVE,
        include_intents: bool = False,
    ) -> dict[str, Any]:
        """Run the daily-bar backtest; see app.backtest.execution_contract.

        Order intents are always committed from pre-open information.
        ``fill_policy`` names how fills are adjudicated afterwards:
        ``daily_bar_retrospective`` (default, the historical assumptions) or
        ``pre_open_causal``. ``include_intents`` returns every committed intent
        with its fingerprint for audit and metamorphic checks.
        """

        if fill_policy not in FILL_POLICIES:
            raise ValueError(f"unknown fill policy: {fill_policy!r}")
        order_intents: list[OrderIntent] = []
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
        # Load the same snapshots as live selection. By default each bar is
        # resolved at its own decision cutoff so today's snapshot cannot leak
        # into history. The projection in app.data.fundamentals only ever has
        # a *current* snapshot, so strict point-in-time leaves every historical
        # bar without market cap and the band gates dark. A caller may opt in
        # to the projection explicitly; the run is then stamped as not
        # point-in-time and must be read as an approximation.
        self._fundamentals = FundamentalResolver(self.store)
        self._project_fundamentals = allow_projected_fundamentals
        if not len(self._fundamentals):
            warnings.append(
                "fundamental_snapshots_empty: market cap and PB gates are inactive"
            )
        elif allow_projected_fundamentals:
            warnings.append(
                "fundamental_projection_enabled: market cap and PB are projected "
                "from the latest snapshot onto historical closes; not point-in-time"
            )
        elif not self._fundamentals.visible_symbol_count(end_date):
            warnings.append(
                "fundamental_snapshots_unavailable_at_backtest_cutoff: "
                "future snapshots were excluded"
            )

        skipped_count = 0
        rejected_count = 0
        blocked_by_regime_count = 0
        evaluated_bars = 0
        unknown_bars = 0
        missing_input_counts: Counter[str] = Counter()
        rule_outcomes: dict[str, Counter[str]] = defaultdict(Counter)
        rule_fail_reasons: dict[str, Counter[str]] = defaultdict(Counter)
        entry_signal_count = 0
        entry_attempt_count = 0
        entry_fill_count = 0
        regime_service = MarketRegimeService()
        pending_candidates: list[tuple[str, float, MarketSnapshot, dict[str, Any]]] = []
        # The MA-break exit needs the limit-up bar's average price, and the
        # partial take-profit must fire once per position rather than daily.
        entry_context: dict[str, dict[str, Any]] = {}
        partial_taken: set[str] = set()
        # symbol -> bar count of its own history when the arming S0 fired.
        armed_at_bar: dict[str, int] = {}
        armed_entry_count = 0
        exit_reason_counts: Counter[str] = Counter()

        for current_date in all_dates:
            curr_dt = pd.to_datetime(current_date)
            for sym in list(ledger.lots):
                sellable[sym] = ledger.quantity(sym)

            regime_data = regime_service.get_latest_regime(current_date)
            regime = regime_data.get("regime", "neutral")

            # Pre-open snapshot. Every order of this session is committed from
            # what is known before the open: start-of-session cash, positions
            # marked at their last CLOSED bar, and the pre-open position count
            # (plus the opening print as a market order's reference price). The
            # old path valued holdings at today's close, let intraday stop and
            # take-profit proceeds fund open-time buys, and let an earlier fill's
            # daily-bar capacity resize the next buy - all unknowable at the open.
            cash_at_open = cash
            marks_at_open = self._pre_open_positions_value(ledger, dfs, curr_dt)
            equity_at_open = cash_at_open + marks_at_open
            positions_at_open = ledger.open_position_count()

            # --- exit intents: closed-bar rules at the open, or resting orders ---
            exit_plans: list[tuple[str, dict[str, Any], list[OrderIntent]]] = []
            for sym in list(ledger.lots):
                if sym not in dfs or curr_dt not in dfs[sym].index:
                    continue
                bar = dict(dfs[sym].loc[curr_dt])
                intents = self._exit_intents(
                    sym=sym,
                    session=current_date,
                    df=dfs[sym],
                    curr_dt=curr_dt,
                    opening=float(bar["open"]),
                    avg_cost=ledger.average_cost(sym),
                    holding_days=self._oldest_holding_days(ledger, sym, current_date),
                    limit_up_avg=(entry_context.get(sym) or {}).get("limit_up_avg_price"),
                    partial_taken=sym in partial_taken,
                    held_quantity=ledger.quantity(sym),
                    available=sellable.get(sym, 0),
                )
                if intents:
                    exit_plans.append((sym, bar, intents))
                    order_intents.extend(intents)

            # --- entry intents: budget from the pre-open snapshot only ---
            entry_candidates = pending_candidates
            deferred_candidates = []
            entry_plans: list[tuple[OrderIntent, dict[str, Any], dict[str, Any]]] = []
            reserved_cash = 0.0
            for sym, signal_score, snapshot, signal_context in entry_candidates:
                # Slots freed by this session's exits open up next session.
                if positions_at_open + len(entry_plans) >= max_positions:
                    deferred_candidates.append((sym, signal_score, snapshot, signal_context))
                    continue
                if sym not in dfs or curr_dt not in dfs[sym].index:
                    deferred_candidates.append((sym, signal_score, snapshot, signal_context))
                    continue
                bar = dict(dfs[sym].loc[curr_dt])
                signal_regime = str(signal_context.get("signal_regime") or "neutral")
                alloc_cap = per_symbol_cap * (0.5 if signal_regime == "weak" else 1.0)
                available_cash = cash_at_open - reserved_cash
                budget = max(0.0, min(available_cash, equity_at_open * alloc_cap))
                buy_price = round(float(bar["open"]) * (1 + self.slippage), 4)
                requested_qty = self._affordable_quantity(budget, buy_price)
                notional = requested_qty * buy_price
                intent = OrderIntent(
                    session=current_date,
                    symbol=sym,
                    side="buy",
                    order_type=ORDER_MARKET_AT_OPEN,
                    reason="prior_close_strong_signal",
                    requested_quantity=requested_qty,
                    reference_price=buy_price,
                    budget=round(budget, 6),
                    reserved_cash=round(notional + self.execution.estimated_fee(notional), 6),
                    sizing_inputs={
                        "cash_at_open": round(cash_at_open, 6),
                        "reserved_before": round(reserved_cash, 6),
                        "positions_marked_at_last_close": round(marks_at_open, 6),
                        "equity_at_open": round(equity_at_open, 6),
                        "allocation_cap": alloc_cap,
                        "signal_regime": signal_regime,
                    },
                )
                reserved_cash += intent.reserved_cash
                entry_plans.append((intent, bar, signal_context))
                order_intents.append(intent)

            # --- adjudication, strictly after every intent is committed ---
            resting_plans = []
            for sym, bar, intents in exit_plans:
                if intents[0].order_type == ORDER_MARKET_AT_OPEN:
                    opening = float(bar["open"])
                    fill = self._adjudicate_sell(
                        intents[0], dfs[sym], curr_dt, bar, opening, fill_policy
                    )
                    cash += self._apply_sell(
                        fill, intents[0], opening, ledger, trades, closed_trades, warnings,
                        sellable, exit_reason_counts, partial_taken, entry_context,
                    )
                else:
                    resting_plans.append((sym, bar, intents))

            for intent, bar, signal_context in entry_plans:
                sym = intent.symbol
                bases = adjudication_bases(fill_policy, ORDER_MARKET_AT_OPEN)
                decision = self.execution.decide(
                    side="buy",
                    requested_quantity=intent.requested_quantity,
                    price=intent.reference_price,
                    bar=bar,
                    previous_close=self._previous_close(dfs[sym], curr_dt),
                    limit_pct=self._limit_pct(sym),
                    price_band_basis=bases["price_band_basis"],
                    capacity_basis=bases["capacity_basis"],
                    capacity_bar=self._prior_bar(dfs[sym], curr_dt),
                )
                entry_attempt_count += 1
                total_cost = decision.price * decision.filled_quantity + decision.fee
                if decision.fill_status != "rejected" and total_cost > cash + 1e-9:
                    # Unreachable while reservations cover fees; kept fail-closed.
                    decision = self.execution._rejected(
                        "buy", intent.requested_quantity, intent.reference_price,
                        "insufficient_cash_at_fill",
                    )
                self._append_trade(trades, sym, current_date, intent.reason, decision, intent=intent)
                if decision.fill_status == "rejected":
                    warnings.append(f"{current_date} {sym} entry blocked: {decision.reject_reason}")
                    continue
                cash -= total_cost
                ledger.buy(sym, decision.filled_quantity, decision.price, current_date, decision.fee)
                sellable[sym] = 0
                entry_fill_count += 1
                entry_context.setdefault(
                    sym,
                    {"limit_up_avg_price": self._signal_average_price(signal_context)},
                )

            for sym, bar, intents in resting_plans:
                # Resting orders need the session's path; only its high/low is
                # known, so the stop is checked before the take-profit.
                for intent in intents:
                    triggered_price = self._resting_fill_price(intent, bar)
                    if triggered_price is None:
                        continue
                    fill = self._adjudicate_sell(
                        intent, dfs[sym], curr_dt, bar, triggered_price, fill_policy
                    )
                    cash += self._apply_sell(
                        fill, intent, triggered_price, ledger, trades, closed_trades, warnings,
                        sellable, exit_reason_counts, partial_taken, entry_context,
                    )
                    break

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
                armed_age: int | None = None
                if self.armed_window_days > 0 and sym in armed_at_bar:
                    elapsed = len(hist) - armed_at_bar[sym]
                    if elapsed > self.armed_window_days:
                        armed_at_bar.pop(sym, None)
                    elif elapsed >= 1:
                        armed_age = elapsed
                snapshot = self._snapshot(
                    sym, current_date, hist, bar, prev_bar, armed_age=armed_age
                )
                decision = self.rule_engine.evaluate(snapshot)
                evaluated_bars += 1
                if self.armed_window_days > 0 and self.s0_params is not None:
                    # Arm (or re-arm) on a genuine same-bar S0. Checked directly
                    # rather than read off the rule hit, which by now also passes
                    # for a carried-over window and could not be told apart.
                    if self.rule_engine.signals.same_bar_s0(snapshot, self.s0_params).passed:
                        armed_at_bar[sym] = len(hist)
                    elif armed_age is not None:
                        armed_entry_count += 1
                if decision.unknown_rule_ids:
                    unknown_bars += 1
                for name in decision.missing_inputs:
                    missing_input_counts[name] += 1
                # Per-rule outcomes answer "why did nothing fire" directly,
                # instead of leaving it to be inferred from an aggregate count.
                for hit in decision.hits:
                    rule_outcomes[hit.rule_id][hit.evaluation] += 1
                    if hit.evaluation != "pass":
                        rule_fail_reasons[hit.rule_id][hit.reason[:60]] += 1
                if decision.blocked:
                    rejected_count += 1
                elif decision.tier == CandidateTier.strong:
                    candidates.append(
                        (
                            sym,
                            decision.score,
                            snapshot,
                            {**dict(bar), "signal_regime": regime},
                        )
                    )

            candidates.sort(key=lambda item: item[1], reverse=True)
            entry_signal_count += len(candidates)
            if regime == "extreme_risk":
                blocked_by_regime_count += len(candidates)
                candidates = []
            pending_symbols = {item[0] for item in candidates}
            pending_candidates = [
                item for item in deferred_candidates if item[0] not in pending_symbols
            ] + candidates

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
        benchmark = self._benchmark(
            benchmark_symbol,
            start_date,
            end_date,
            daily_equity,
            strategy_observed=entry_fill_count > 0,
        )
        if benchmark.get("status") != "ready":
            warnings.append("insufficient_benchmark_data")
        # Which exit actually fired matters as much as the return: a run whose
        # exits are all max_holding_days measured the horizon, not the strategy.
        metrics_exit_reasons = dict(sorted(exit_reason_counts.items()))
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
            evaluated_bars=evaluated_bars,
            unknown_bars=unknown_bars,
            missing_input_counts=missing_input_counts,
            rule_outcomes=rule_outcomes,
            rule_fail_reasons=rule_fail_reasons,
            entry_signal_count=entry_signal_count,
            entry_attempt_count=entry_attempt_count,
            entry_fill_count=entry_fill_count,
            pending_entry_count=len(pending_candidates),
        )
        metrics["fundamental_point_in_time"] = not allow_projected_fundamentals
        metrics["execution_contract"] = execution_contract(
            fill_policy, fundamentals_point_in_time=not allow_projected_fundamentals
        )
        metrics["order_intent_count"] = len(order_intents)
        metrics["exit_reason_counts"] = metrics_exit_reasons
        metrics["armed_window_days"] = self.armed_window_days
        metrics["armed_window_bar_count"] = armed_entry_count
        # A run that evaluated bars but never produced a fill is not a result of
        # zero return; it is the absence of a signal. Reporting it as
        # "completed" with total_return 0.0 is how 39 empty runs were mistaken
        # for evidence that the strategy simply broke even.
        if not daily_equity:
            status = "insufficient_data"
        elif (metrics["signal_unknown_ratio"] or 0.0) > 0.05:
            status = "degraded"
            warnings.append(
                "signal_data_degraded: "
                f"unknown_ratio={metrics['signal_unknown_ratio']} exceeds 0.05"
            )
        elif not entry_signal_count:
            status = "no_signal"
            warnings.append(
                "no_entry_signal: "
                f"evaluated_bars={evaluated_bars} "
                f"unknown_bars={unknown_bars} "
                f"missing_inputs={dict(missing_input_counts)}"
            )
        elif not entry_fill_count:
            status = "no_fill"
            warnings.append(
                "entry_signals_not_filled: "
                f"signals={entry_signal_count} attempts={entry_attempt_count} "
                f"rejected={metrics['rejected_execution_count']} "
                f"blocked_by_regime={blocked_by_regime_count}"
            )
        else:
            status = "completed"

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
            **(
                {"order_intents": [intent.to_dict() for intent in order_intents]}
                if include_intents
                else {}
            ),
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
            for column in NUMERIC_BAR_COLUMNS:
                df[column] = pd.to_numeric(df[column], errors="coerce")
            df.dropna(subset=PRICE_COLUMNS, inplace=True)
            df[["volume", "amount"]] = df[["volume", "amount"]].fillna(0.0)
            if df.empty:
                continue
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

    def _snapshot(
        self,
        sym: str,
        current_date: str,
        hist: pd.DataFrame,
        bar: pd.Series,
        prev_bar: pd.Series,
        *,
        armed_age: int | None = None,
    ) -> MarketSnapshot:
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
        close = float(bar["close"])
        fundamentals = (
            self._fundamentals.resolve(
                sym, close, as_of=None if self._project_fundamentals else current_date
            )
            if self._fundamentals is not None
            else None
        )
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
            pb=fundamentals.pb if fundamentals else None,
            market_cap_billion=fundamentals.market_cap_billion if fundamentals else None,
            metadata={
                "data_quality": "daily_bar",
                "fundamental_method": fundamentals.method if fundamentals else None,
                "fundamental_snapshot_as_of": (
                    fundamentals.snapshot_as_of if fundamentals else None
                ),
                "fundamental_snapshot_available_at": (
                    fundamentals.snapshot_available_at if fundamentals else None
                ),
                "fundamental_snapshot_source": (
                    fundamentals.snapshot_source if fundamentals else None
                ),
                "board_type": board,
                "limit_up_threshold": limit_pct,
                "high_250": float(high_250),
                "high_500": float(high_500),
                "volume_ratio": float(volume_ratio),
                "five_day_pct": float(five_day_pct),
                "previous_close": float(prev_bar["close"]),
                "dengzhan_armed_age": armed_age,
            },
        )

    @staticmethod
    def _signal_average_price(signal_context: dict[str, Any]) -> float | None:
        """Average traded price of the signal bar (the limit-up day).

        The spec's primary exit is "close below the MA *and* below the limit-up
        day's average price", so that price has to be captured at entry. It is
        amount / shares where the feed reports 成交额; volume is stored in 手.
        """

        try:
            amount = float(signal_context.get("amount") or 0)
            volume = float(signal_context.get("volume") or 0)
        except (TypeError, ValueError):
            return None
        if amount > 0 and volume > 0:
            return amount / (volume * 100.0)
        # No reported turnover: fall back to the bar's typical price.
        try:
            high = float(signal_context["high"])
            low = float(signal_context["low"])
            close = float(signal_context["close"])
        except (KeyError, TypeError, ValueError):
            return None
        typical = (high + low + close) / 3.0
        return typical if typical > 0 else None

    def _broke_ma_support(
        self,
        df: pd.DataFrame,
        curr_dt: pd.Timestamp,
        window: int,
        limit_up_avg: float | None,
        require_below_limit_up_avg: bool,
    ) -> tuple[bool, bool]:
        """Did the last *closed* bar break support? Returns (broke, confirmed).

        Evaluated on bars strictly before ``curr_dt`` and executed at this bar's
        open, so no close is used to trade the same session. ``confirmed`` is
        False when the limit-up average price was required but unavailable; the
        caller keeps that distinction in the exit reason rather than silently
        treating an unconfirmed break as the real one.
        """

        prior = df.loc[:curr_dt].iloc[:-1]
        if len(prior) < window:
            return False, False
        moving_average = float(prior["close"].tail(window).mean())
        last_close = float(prior.iloc[-1]["close"])
        if last_close >= moving_average:
            return False, False
        if not require_below_limit_up_avg:
            return True, True
        if limit_up_avg is None:
            return True, False
        return (last_close < float(limit_up_avg)), True

    def _exit_intents(
        self,
        *,
        sym: str,
        session: str,
        df: pd.DataFrame,
        curr_dt: pd.Timestamp,
        opening: float,
        avg_cost: float,
        holding_days: int,
        limit_up_avg: float | None,
        partial_taken: bool,
        held_quantity: int,
        available: int,
    ) -> list[OrderIntent]:
        """Resolve rules.yaml ``exit_rules`` into orders committed before the open.

        Rules evaluated on closed bars (MA break) or the calendar (holding days)
        become one market-at-open sell. Otherwise the position carries resting
        orders for the session - a stop and, once per position, a take-profit -
        whose trigger prices are fixed from the average cost before the open.
        Whether they trigger is adjudicated afterwards from the session's range.
        """

        if available <= 0:
            return []
        rules = self.exit_rules

        def sell(order_type, reason, quantity, reference, trigger=None, ratio=1.0):
            return OrderIntent(
                session=session,
                symbol=sym,
                side="sell",
                order_type=order_type,
                reason=reason,
                requested_quantity=int(quantity),
                reference_price=float(reference),
                trigger_price=None if trigger is None else round(float(trigger), 6),
                sizing_inputs={"average_cost": round(avg_cost, 6), "exit_ratio": ratio,
                               "held_quantity": held_quantity, "sellable_quantity": available},
            )

        window = rules.get("break_ma_window")
        if window:
            broke, confirmed = self._broke_ma_support(
                df,
                curr_dt,
                int(window),
                limit_up_avg,
                bool(rules.get("require_below_limit_up_avg", True)),
            )
            if broke:
                reason = "ma_break" if confirmed else "ma_break_limit_up_avg_unknown"
                return [sell(ORDER_MARKET_AT_OPEN, reason, available, opening)]

        max_holding_days = rules.get("max_holding_days")
        if max_holding_days is not None and holding_days >= int(max_holding_days):
            return [sell(ORDER_MARKET_AT_OPEN, "max_holding_days", available, opening)]

        intents: list[OrderIntent] = []
        stop_loss_pct = rules.get("stop_loss_pct")
        if stop_loss_pct is not None:
            stop = avg_cost * (1 - float(stop_loss_pct) / 100.0)
            intents.append(sell(ORDER_RESTING_STOP, "stop_loss", available, stop, trigger=stop))

        take_profit_pct = rules.get("partial_take_profit_pct")
        if take_profit_pct is not None and not partial_taken:
            ratio = min(1.0, max(0.0, float(rules.get("partial_take_profit_ratio", 0.5))))
            if ratio > 0:
                target = avg_cost * (1 + float(take_profit_pct) / 100.0)
                if ratio >= 1.0:
                    quantity = available
                else:
                    # A position too small to halve keeps running until a full
                    # exit reason fires; no take-profit order is placed.
                    scaled = int(held_quantity * ratio) // self.lot_size * self.lot_size
                    quantity = min(available, scaled)
                if quantity > 0:
                    reason = "partial_take_profit" if ratio < 1.0 else "take_profit"
                    intents.append(
                        sell(ORDER_RESTING_LIMIT, reason, quantity, target, trigger=target, ratio=ratio)
                    )
        return intents

    @staticmethod
    def _resting_fill_price(intent: OrderIntent, bar: dict[str, Any]) -> float | None:
        """Daily-range touch adjudication of a resting order; None if not triggered."""

        opening = float(bar["open"])
        trigger = float(intent.trigger_price)
        if intent.order_type == ORDER_RESTING_STOP and float(bar["low"]) <= trigger:
            return opening if opening <= trigger else trigger
        if intent.order_type == ORDER_RESTING_LIMIT and float(bar["high"]) >= trigger:
            return opening if opening >= trigger else trigger
        return None

    def _adjudicate_sell(
        self,
        intent: OrderIntent,
        df: pd.DataFrame,
        curr_dt: pd.Timestamp,
        bar: dict[str, Any],
        fill_price: float,
        fill_policy: str,
    ) -> ExecutionDecision:
        bases = adjudication_bases(fill_policy, intent.order_type)
        return self.execution.decide(
            side="sell",
            requested_quantity=intent.requested_quantity,
            price=round(fill_price * (1 - self.slippage), 4),
            bar=bar,
            previous_close=self._previous_close(df, curr_dt),
            limit_pct=self._limit_pct(intent.symbol),
            price_band_basis=bases["price_band_basis"],
            capacity_basis=bases["capacity_basis"],
            capacity_bar=self._prior_bar(df, curr_dt),
        )

    def _apply_sell(
        self,
        decision: ExecutionDecision,
        intent: OrderIntent,
        fill_price: float,
        ledger: FIFOLedger,
        trades: list[dict[str, Any]],
        closed_trades: list[ClosedTrade],
        warnings: list[str],
        sellable: dict[str, int],
        exit_reason_counts: Counter[str],
        partial_taken: set[str],
        entry_context: dict[str, dict[str, Any]],
    ) -> float:
        """Book an adjudicated sell; returns the cash it adds (0 when rejected)."""

        sym = intent.symbol
        self._append_trade(trades, sym, intent.session, intent.reason, decision, intent=intent)
        if decision.fill_status == "rejected":
            warnings.append(f"{intent.session} {sym} exit blocked: {decision.reject_reason}")
            return 0.0
        proceeds = decision.price * decision.filled_quantity - decision.fee - decision.stamp_tax
        matched = ledger.sell(
            symbol=sym,
            quantity=decision.filled_quantity,
            exit_price=decision.price,
            exit_date=intent.session,
            fee=decision.fee,
            stamp_tax=decision.stamp_tax,
            exit_reason=intent.reason,
            slippage_cost=abs(fill_price - decision.price) * decision.filled_quantity,
        )
        closed_trades.extend(matched)
        sellable[sym] = max(0, sellable.get(sym, 0) - decision.filled_quantity)
        exit_reason_counts[intent.reason] += 1
        if float(intent.sizing_inputs.get("exit_ratio", 1.0)) < 1.0:
            partial_taken.add(sym)
        if ledger.quantity(sym) <= 0:
            entry_context.pop(sym, None)
            partial_taken.discard(sym)
        return proceeds

    def _affordable_quantity(self, budget: float, price: float) -> int:
        """Largest whole-lot quantity whose notional plus commission fits the budget."""

        if budget <= 0 or price <= 0:
            return 0
        quantity = int(budget / price) // self.lot_size * self.lot_size
        while quantity > 0 and (
            quantity * price + self.execution.estimated_fee(quantity * price) > budget + 1e-9
        ):
            quantity -= self.lot_size
        return max(0, quantity)

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

    @staticmethod
    def _prior_bar(df: pd.DataFrame | None, current_dt: pd.Timestamp) -> dict[str, Any] | None:
        """The last bar strictly before ``current_dt``: what was final at its open."""

        if df is None or df.empty:
            return None
        position = int(df.index.searchsorted(current_dt, side="left"))
        return dict(df.iloc[position - 1]) if position > 0 else None

    def _pre_open_positions_value(
        self, ledger: FIFOLedger, dfs: dict[str, pd.DataFrame], current_dt: pd.Timestamp
    ) -> float:
        """Holdings marked at their last closed bar before this session (cost if none)."""

        value = 0.0
        for sym in list(ledger.lots):
            prior = self._prior_bar(dfs.get(sym), current_dt)
            mark = float(prior["close"]) if prior is not None else ledger.average_cost(sym)
            value += ledger.quantity(sym) * mark
        return value

    def _positions_value(self, ledger: FIFOLedger, dfs: dict[str, pd.DataFrame], current_dt: pd.Timestamp) -> float:
        """End-of-session mark at the session close; never used for open-time sizing."""

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
        *,
        intent: OrderIntent | None = None,
    ) -> None:
        trades.append(
            {
                "intent_id": intent.intent_id if intent else None,
                "order_type": intent.order_type if intent else None,
                "price_band_basis": decision.price_band_basis,
                "capacity_basis": decision.capacity_basis,
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
                "liquidity_basis": decision.liquidity_basis,
            }
        )

    def _benchmark(
        self,
        benchmark_symbol: str,
        start_date: str,
        end_date: str,
        daily_equity: list[dict[str, Any]],
        *,
        strategy_observed: bool,
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
        closes = [float(row["close"]) for row in rows if row["close"] is not None and not pd.isna(row["close"])]
        if len(closes) < 2:
            return {"symbol": benchmark_symbol, "status": "insufficient_benchmark_data"}
        benchmark_return = closes[-1] / closes[0] - 1
        peak = closes[0]
        max_drawdown = 0.0
        for close in closes:
            peak = max(peak, close)
            max_drawdown = max(max_drawdown, (peak - close) / peak if peak else 0.0)
        correlation = None
        if strategy_observed and daily_equity and len(rows) > 2:
            eq = pd.DataFrame(daily_equity)
            bm = pd.DataFrame([dict(row) for row in rows])
            merged = eq.merge(bm, on="trade_date", how="inner")
            if len(merged) > 2:
                corr = merged["total_equity"].pct_change().corr(merged["close"].pct_change())
                correlation = None if pd.isna(corr) else round(float(corr), 6)
        strategy_return = (
            daily_equity[-1]["total_equity"] / daily_equity[0]["total_equity"] - 1
            if strategy_observed
            and len(daily_equity) >= 2
            and daily_equity[0]["total_equity"]
            else 0.0
        )
        return {
            "symbol": benchmark_symbol,
            "status": "ready",
            "benchmark_return": round(benchmark_return, 6),
            "benchmark_max_drawdown": round(max_drawdown, 6),
            "excess_return": (
                round(strategy_return - benchmark_return, 6)
                if strategy_observed
                else None
            ),
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
        evaluated_bars: int = 0,
        unknown_bars: int = 0,
        missing_input_counts: Counter[str] | None = None,
        rule_outcomes: dict[str, Counter[str]] | None = None,
        rule_fail_reasons: dict[str, Counter[str]] | None = None,
        entry_signal_count: int = 0,
        entry_attempt_count: int = 0,
        entry_fill_count: int = 0,
        pending_entry_count: int = 0,
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

        counts = missing_input_counts or Counter()
        metrics["signal_evaluated_bars"] = evaluated_bars
        metrics["signal_unknown_bars"] = unknown_bars
        metrics["signal_unknown_ratio"] = (
            round(unknown_bars / evaluated_bars, 6) if evaluated_bars else None
        )
        metrics["signal_missing_inputs"] = dict(counts.most_common())
        # How much of the fill liquidity came from reported 成交额 versus the
        # volume x price proxy. A run that is mostly proxied is still a valid
        # backtest, but its liquidity caps are estimates and should say so.
        metrics["liquidity_basis_counts"] = dict(
            Counter(
                trade.get("liquidity_basis")
                for trade in trades
                if trade["fill_status"] != "rejected" and trade.get("liquidity_basis")
            )
        )
        metrics["signal_rule_outcomes"] = {
            rule_id: dict(outcome) for rule_id, outcome in (rule_outcomes or {}).items()
        }
        metrics["signal_top_rejections"] = {
            rule_id: dict(reasons.most_common(3))
            for rule_id, reasons in (rule_fail_reasons or {}).items()
        }
        # Coverage of the inputs the rules actually need. Below 0.95 the run is
        # measuring data gaps, not the strategy.
        metrics["signal_input_coverage"] = (
            round(1 - unknown_bars / evaluated_bars, 6) if evaluated_bars else None
        )
        metrics["entry_signal_count"] = entry_signal_count
        metrics["entry_attempt_count"] = entry_attempt_count
        metrics["entry_fill_count"] = entry_fill_count
        metrics["pending_entry_count"] = pending_entry_count

        if not metrics["trade_count"]:
            # No fills means these were never measured. Zero is a value; None is
            # the absence of one, and the difference decides whether a run is
            # evidence about the strategy or evidence about the pipeline.
            for key in (
                "total_return",
                "annualized_return",
                "max_drawdown",
                "exposure_ratio",
            ):
                metrics[key] = None
        if not closed_count:
            for key in (
                "win_rate",
                "profit_loss_ratio",
                "average_win",
                "average_loss",
                "expectancy",
                "average_holding_days",
            ):
                metrics[key] = None

        if benchmark.get("status") == "ready":
            strategy_measured = bool(metrics["trade_count"])
            metrics.update(
                {
                    "benchmark_return": benchmark["benchmark_return"],
                    "benchmark_max_drawdown": benchmark["benchmark_max_drawdown"],
                    "excess_return": benchmark["excess_return"] if strategy_measured else None,
                    "correlation_to_benchmark": (
                        benchmark["correlation_to_benchmark"] if strategy_measured else None
                    ),
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
