from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd
import yaml


DEFAULT_DB_PATH = Path("trading_local.sqlite3")
DEFAULT_RULES_PATH = Path("backend/configs/review_only_buy_sell_rules.yaml")


@dataclass(frozen=True)
class Signal:
    symbol: str
    signal_date: str
    entry_index: int
    entry_date: str
    entry_price: float
    base_len: int
    avg_cost: float
    price_multiple: float
    volume_ratio: float
    base_cv: float
    base_range_pct: float


def load_candidate_rules(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a YAML object")
    if not data.get("review_only") or not data.get("simulation_only"):
        raise ValueError("candidate rules must stay review_only and simulation_only")
    return data


def load_price_frames(db_path: Path) -> dict[str, pd.DataFrame]:
    con = sqlite3.connect(db_path)
    rows = con.execute(
        """
        SELECT symbol, trade_date, open, high, low, close, volume, amount
        FROM daily_bar_cache
        WHERE quality_status = 'ready'
          AND symbol NOT LIKE 'SH000%'
          AND symbol NOT LIKE 'SZ399%'
        ORDER BY symbol, trade_date
        """
    ).fetchall()
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        grouped.setdefault(str(row[0]), []).append(row)

    frames: dict[str, pd.DataFrame] = {}
    for symbol, records in grouped.items():
        frame = pd.DataFrame(
            records,
            columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"],
        )
        for column in ["open", "high", "low", "close", "volume", "amount"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        frame = frame.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)
        if len(frame) < 120:
            continue
        frame["amount_proxy"] = frame["amount"]
        missing_amount = frame["amount_proxy"].isna() | (frame["amount_proxy"] <= 0)
        frame.loc[missing_amount, "amount_proxy"] = frame.loc[missing_amount, "close"] * frame.loc[
            missing_amount, "volume"
        ]
        frame["amount_proxy_used"] = missing_amount
        frame["ma5"] = frame["close"].rolling(5, min_periods=3).mean()
        frame["ma10"] = frame["close"].rolling(10, min_periods=5).mean()
        frame["ma20"] = frame["close"].rolling(20, min_periods=10).mean()
        frame["ma60"] = frame["close"].rolling(60, min_periods=30).mean()
        frame["volume_ma20"] = frame["volume"].rolling(20, min_periods=10).mean()
        frame["volume_ratio"] = frame["volume"] / frame["volume_ma20"]
        frame["daily_return"] = frame["close"].pct_change()
        frame["upper_shadow_pct"] = (frame["high"] - frame[["open", "close"]].max(axis=1)) / frame[
            "close"
        ].replace(0, pd.NA)
        frames[symbol] = frame
    return frames


def find_signals(frame: pd.DataFrame, symbol: str, rules: dict[str, Any], params: dict[str, Any]) -> list[Signal]:
    buy_rules = {str(rule.get("id")): rule for rule in rules.get("buy_rules") or []}
    zone_rule = buy_rules.get("mf26x_pre_markup_cost_zone", {})
    confirm_rule = buy_rules.get("mf26x_breakout_confirmation", {})
    zone_conditions = zone_rule.get("conditions") or {}
    confirm_conditions = confirm_rule.get("conditions") or {}

    min_base_len = int(params.get("min_base_len") or 60)
    base_windows = [int(item) for item in zone_conditions.get("base_window_days_any_of") or [60, 80, 120, 160]]
    base_windows = sorted({item for item in base_windows if item <= 220} | {60, 80, 120, 160})
    base_windows = [item for item in base_windows if item >= min_base_len]
    max_base_cv = float(zone_conditions.get("max_base_cv") or 0.30)
    max_base_range_pct = float(zone_conditions.get("max_base_range_pct") or 90.0)
    min_multiple = float(zone_conditions.get("current_price_min_multiple_of_avg_cost") or 1.0)
    max_multiple = float(
        params.get("max_entry_multiple")
        or zone_conditions.get("current_price_max_multiple_of_avg_cost")
        or 1.45
    )
    reject_multiple = float(zone_conditions.get("reject_if_current_price_multiple_gte") or 2.30)
    min_volume_ratio = float(
        params.get("min_volume_ratio")
        or confirm_conditions.get("min_volume_ratio")
        or zone_conditions.get("min_volume_ratio_on_breakout")
        or 1.50
    )
    max_single_day_chase_pct = float(
        params.get("max_single_day_chase_pct") or confirm_conditions.get("max_single_day_chase_pct") or 12.0
    )
    reject_upper_shadow_pct = float(confirm_conditions.get("reject_if_upper_shadow_pct_gte") or 8.0)

    signals: list[Signal] = []
    if not base_windows:
        return signals

    for index in range(max(base_windows), len(frame) - 1):
        row = frame.iloc[index]
        if pd.isna(row["ma20"]) or pd.isna(row["volume_ratio"]):
            continue
        if float(row["close"]) <= float(row["ma20"]):
            continue
        if not pd.isna(row["ma60"]) and float(row["close"]) < float(row["ma60"]) * 0.98:
            continue
        if float(row["volume_ratio"]) < min_volume_ratio:
            continue
        if float(row.get("daily_return") or 0) * 100 > max_single_day_chase_pct:
            continue
        if float(row.get("upper_shadow_pct") or 0) * 100 >= reject_upper_shadow_pct:
            continue

        selected: Signal | None = None
        for base_len in base_windows:
            if index < base_len:
                continue
            base = frame.iloc[index - base_len : index]
            avg_cost = float(base["close"].mean())
            if avg_cost <= 0:
                continue
            base_min = float(base["close"].min())
            if base_min <= 0:
                continue
            base_cv = float(base["close"].std() / avg_cost)
            base_range_pct = float((base["close"].max() / base_min - 1) * 100)
            price_multiple = float(row["close"] / avg_cost)
            if base_cv > max_base_cv or base_range_pct > max_base_range_pct:
                continue
            if not (min_multiple <= price_multiple <= max_multiple):
                continue
            if price_multiple >= reject_multiple:
                continue
            entry = frame.iloc[index + 1]
            selected = Signal(
                symbol=symbol,
                signal_date=str(row["trade_date"].date()),
                entry_index=index + 1,
                entry_date=str(entry["trade_date"].date()),
                entry_price=float(entry["open"]),
                base_len=base_len,
                avg_cost=avg_cost,
                price_multiple=price_multiple,
                volume_ratio=float(row["volume_ratio"]),
                base_cv=base_cv,
                base_range_pct=base_range_pct,
            )
            break
        if selected:
            signals.append(selected)
    return signals


def _trigger_price(open_price: float, trigger_price: float, direction: str) -> float:
    if direction == "take_profit":
        return open_price if open_price >= trigger_price else trigger_price
    return open_price if open_price <= trigger_price else trigger_price


def simulate_fixed_exit(frame: pd.DataFrame, signal: Signal, params: dict[str, Any]) -> dict[str, Any]:
    stop_loss_pct = float(params.get("stop_loss_pct") or 0.08)
    fixed_take_profit_pct = float(params.get("fixed_take_profit_pct") or 0.15)
    fixed_max_holding_days = int(params.get("fixed_max_holding_days") or 5)
    stop_price = signal.entry_price * (1 - stop_loss_pct)
    take_profit_price = signal.entry_price * (1 + fixed_take_profit_pct)
    max_index = min(len(frame) - 1, signal.entry_index + fixed_max_holding_days)
    exit_index = max_index
    exit_price = float(frame.iloc[max_index]["close"])
    exit_reason = "fixed_max_holding_days"

    for index in range(signal.entry_index, max_index + 1):
        row = frame.iloc[index]
        if float(row["low"]) <= stop_price:
            exit_index = index
            exit_price = _trigger_price(float(row["open"]), stop_price, "stop_loss")
            exit_reason = "fixed_stop_loss"
            break
        if float(row["high"]) >= take_profit_price:
            exit_index = index
            exit_price = _trigger_price(float(row["open"]), take_profit_price, "take_profit")
            exit_reason = "fixed_take_profit"
            break

    pnl_pct = (exit_price / signal.entry_price - 1) * 100
    return {
        "symbol": signal.symbol,
        "signal_date": signal.signal_date,
        "entry_date": signal.entry_date,
        "exit_date": str(frame.iloc[exit_index]["trade_date"].date()),
        "entry_price": round(signal.entry_price, 4),
        "exit_price": round(exit_price, 4),
        "pnl_pct": round(pnl_pct, 4),
        "holding_days": int(exit_index - signal.entry_index + 1),
        "exit_reason": exit_reason,
        "avg_cost": round(signal.avg_cost, 4),
        "base_len": signal.base_len,
        "entry_cost_multiple": round(signal.entry_price / signal.avg_cost, 4),
    }


def _distribution_risk(row: pd.Series, avg_cost: float) -> bool:
    if avg_cost <= 0:
        return False
    multiple = float(row["close"]) / avg_cost
    high_volume_stall = (
        multiple >= 2.30
        and float(row.get("volume_ratio") or 0) >= 2.0
        and float(row.get("daily_return") or 0) <= 0.01
    )
    long_upper_shadow = multiple >= 2.30 and float(row.get("upper_shadow_pct") or 0) >= 0.06
    return bool(high_volume_stall or long_upper_shadow)


def simulate_mf26x_exit(frame: pd.DataFrame, signal: Signal, params: dict[str, Any]) -> dict[str, Any]:
    remaining = 1.0
    realized = 0.0
    stage_245 = False
    stage_260 = False
    risk_reduced = False
    exit_index = signal.entry_index
    exit_reason = "mf26x_end_of_data"
    stop_loss_pct = float(params.get("stop_loss_pct") or 0.08)
    max_holding_days = int(params.get("mf_max_holding_days") or 160)
    failure_guard_days = int(params.get("failure_guard_days") or 0)
    failure_guard_min_gain_pct = float(params.get("failure_guard_min_gain_pct") or 0.08)
    risk_reduce_trigger_pct = float(params.get("risk_reduce_trigger_pct") or 0.0)
    risk_reduce_sell_pct = float(params.get("risk_reduce_sell_pct") or 0.0)
    stop_price = signal.entry_price * (1 - stop_loss_pct)
    max_index = min(len(frame) - 1, signal.entry_index + max_holding_days)
    peak_close = signal.entry_price

    for index in range(signal.entry_index, max_index + 1):
        row = frame.iloc[index]
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        peak_close = max(peak_close, close)

        if low <= stop_price:
            exit_price = _trigger_price(open_price, stop_price, "stop_loss")
            realized += remaining * (exit_price / signal.entry_price - 1)
            remaining = 0.0
            exit_index = index
            exit_reason = "mf26x_stop_loss"
            break

        target_245 = signal.avg_cost * 2.45
        target_260 = signal.avg_cost * 2.60
        if not stage_245 and high >= target_245 and remaining > 0:
            exit_price = _trigger_price(open_price, target_245, "take_profit")
            sell_fraction = min(0.30, remaining)
            realized += sell_fraction * (exit_price / signal.entry_price - 1)
            remaining -= sell_fraction
            stage_245 = True
            exit_index = index
            exit_reason = "mf26x_stage_245"

        if not stage_260 and high >= target_260 and remaining > 0:
            exit_price = _trigger_price(open_price, target_260, "take_profit")
            sell_fraction = min(0.40, remaining)
            realized += sell_fraction * (exit_price / signal.entry_price - 1)
            remaining -= sell_fraction
            stage_260 = True
            exit_index = index
            exit_reason = "mf26x_stage_260"

        if (
            risk_reduce_trigger_pct > 0
            and risk_reduce_sell_pct > 0
            and not risk_reduced
            and not stage_245
            and not stage_260
            and high >= signal.entry_price * (1 + risk_reduce_trigger_pct)
            and remaining > 0
        ):
            trigger_price = signal.entry_price * (1 + risk_reduce_trigger_pct)
            exit_price = _trigger_price(open_price, trigger_price, "take_profit")
            sell_fraction = min(risk_reduce_sell_pct, remaining)
            realized += sell_fraction * (exit_price / signal.entry_price - 1)
            remaining -= sell_fraction
            risk_reduced = True
            stop_price = max(stop_price, signal.entry_price)
            exit_index = index
            exit_reason = "mf26x_risk_reduce"

        if remaining <= 0:
            break

        if _distribution_risk(row, signal.avg_cost):
            realized += remaining * (close / signal.entry_price - 1)
            remaining = 0.0
            exit_index = index
            exit_reason = "mf26x_distribution_watch_exit"
            break

        age = index - signal.entry_index + 1
        no_stage_hit = not stage_245 and not stage_260
        no_progress = peak_close < signal.entry_price * (1 + failure_guard_min_gain_pct)
        weak_close = close < signal.entry_price or (
            not pd.isna(row.get("ma20")) and close < float(row["ma20"])
        )
        if failure_guard_days > 0 and age >= failure_guard_days and no_stage_hit and no_progress and weak_close:
            realized += remaining * (close / signal.entry_price - 1)
            remaining = 0.0
            exit_index = index
            exit_reason = "mf26x_failed_launch_exit"
            break

        if (stage_245 or stage_260) and not pd.isna(row.get("ma10")) and close < float(row["ma10"]):
            realized += remaining * (close / signal.entry_price - 1)
            remaining = 0.0
            exit_index = index
            exit_reason = "mf26x_ma10_residual_exit"
            break

    if remaining > 0:
        row = frame.iloc[max_index]
        exit_price = float(row["close"])
        realized += remaining * (exit_price / signal.entry_price - 1)
        exit_index = max_index
        if exit_reason.startswith("mf26x_stage"):
            exit_reason = "mf26x_partial_then_horizon_exit"
        else:
            exit_reason = "mf26x_horizon_exit"

    pnl_pct = realized * 100
    return {
        "symbol": signal.symbol,
        "signal_date": signal.signal_date,
        "entry_date": signal.entry_date,
        "exit_date": str(frame.iloc[exit_index]["trade_date"].date()),
        "entry_price": round(signal.entry_price, 4),
        "pnl_pct": round(pnl_pct, 4),
        "holding_days": int(exit_index - signal.entry_index + 1),
        "exit_reason": exit_reason,
        "avg_cost": round(signal.avg_cost, 4),
        "base_len": signal.base_len,
        "entry_cost_multiple": round(signal.entry_price / signal.avg_cost, 4),
        "stage_245_hit": stage_245,
        "stage_260_hit": stage_260,
        "risk_reduced": risk_reduced,
    }


def non_overlapping_signals(signals: list[Signal], exits_by_key: dict[tuple[str, str], int]) -> list[Signal]:
    selected: list[Signal] = []
    busy_until: dict[str, int] = {}
    for signal in sorted(signals, key=lambda item: (item.symbol, item.entry_index)):
        if signal.entry_index <= busy_until.get(signal.symbol, -1):
            continue
        selected.append(signal)
        busy_until[signal.symbol] = exits_by_key.get((signal.symbol, signal.entry_date), signal.entry_index)
    return selected


def summarize(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "median_return_pct": 0.0,
            "sum_return_pct": 0.0,
            "avg_holding_days": 0.0,
            "exit_reasons": {},
        }
    returns = [float(trade["pnl_pct"]) for trade in trades]
    wins = [item for item in returns if item > 0]
    return {
        "trade_count": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 4),
        "avg_return_pct": round(mean(returns), 4),
        "median_return_pct": round(median(returns), 4),
        "sum_return_pct": round(sum(returns), 4),
        "avg_holding_days": round(mean(float(trade["holding_days"]) for trade in trades), 4),
        "exit_reasons": dict(Counter(str(trade["exit_reason"]) for trade in trades)),
    }


def hybrid_split_trades(
    fixed_trades: list[dict[str, Any]],
    mf_trades: list[dict[str, Any]],
    fixed_weight: float = 0.50,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    runner_weight = 1 - fixed_weight
    for fixed, mf in zip(fixed_trades, mf_trades):
        output.append(
            {
                "symbol": fixed["symbol"],
                "signal_date": fixed["signal_date"],
                "entry_date": fixed["entry_date"],
                "exit_date": mf["exit_date"],
                "pnl_pct": round(
                    fixed_weight * float(fixed["pnl_pct"]) + runner_weight * float(mf["pnl_pct"]),
                    4,
                ),
                "holding_days": max(int(fixed["holding_days"]), int(mf["holding_days"])),
                "exit_reason": "hybrid_fixed_half_mf26x_runner_half",
                "fixed_exit_reason": fixed["exit_reason"],
                "runner_exit_reason": mf["exit_reason"],
            }
        )
    return output


def params_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "min_base_len": int(args.min_base_len),
        "max_entry_multiple": float(args.max_entry_multiple),
        "min_volume_ratio": float(args.min_volume_ratio),
        "max_single_day_chase_pct": float(args.max_single_day_chase_pct),
        "stop_loss_pct": float(args.stop_loss_pct),
        "fixed_take_profit_pct": float(args.fixed_take_profit_pct),
        "fixed_max_holding_days": int(args.fixed_max_holding_days),
        "mf_max_holding_days": int(args.mf_max_holding_days),
        "failure_guard_days": int(args.failure_guard_days),
        "failure_guard_min_gain_pct": float(args.failure_guard_min_gain_pct),
        "risk_reduce_trigger_pct": float(args.risk_reduce_trigger_pct),
        "risk_reduce_sell_pct": float(args.risk_reduce_sell_pct),
    }


def run_backtest_core(rules: dict[str, Any], frames: dict[str, pd.DataFrame], params: dict[str, Any]) -> dict[str, Any]:
    all_signals: list[Signal] = []
    skipped_amount_rows = 0
    total_rows = 0
    for symbol, frame in frames.items():
        total_rows += len(frame)
        skipped_amount_rows += int(frame["amount_proxy_used"].sum())
        all_signals.extend(find_signals(frame, symbol, rules, params))

    fixed_preliminary: list[dict[str, Any]] = []
    mf_preliminary: list[dict[str, Any]] = []
    exit_index_by_signal: dict[tuple[str, str], int] = {}
    frame_by_symbol = frames
    for signal in all_signals:
        frame = frame_by_symbol[signal.symbol]
        mf_trade = simulate_mf26x_exit(frame, signal, params)
        mf_preliminary.append(mf_trade)
        exit_index_by_signal[(signal.symbol, signal.entry_date)] = signal.entry_index + int(
            mf_trade["holding_days"]
        )

    selected_signals = non_overlapping_signals(all_signals, exit_index_by_signal)
    for signal in selected_signals:
        frame = frame_by_symbol[signal.symbol]
        fixed_preliminary.append(simulate_fixed_exit(frame, signal, params))
    mf_trades = [simulate_mf26x_exit(frame_by_symbol[signal.symbol], signal, params) for signal in selected_signals]

    fixed_summary = summarize(fixed_preliminary)
    mf_summary = summarize(mf_trades)
    hybrid_trades = hybrid_split_trades(fixed_preliminary, mf_trades)
    hybrid_summary = summarize(hybrid_trades)
    return {
        "review_only": True,
        "simulation_only": True,
        "params": params,
        "data": {
            "symbols": len(frames),
            "rows": total_rows,
            "amount_proxy_used_rows": skipped_amount_rows,
            "amount_proxy_used": skipped_amount_rows > 0,
        },
        "signals": {
            "raw_signal_count": len(all_signals),
            "non_overlapping_signal_count": len(selected_signals),
        },
        "fixed_exit": fixed_summary,
        "mf26x_exit": mf_summary,
        "hybrid_split": hybrid_summary,
        "delta": {
            "avg_return_pct": round(mf_summary["avg_return_pct"] - fixed_summary["avg_return_pct"], 4),
            "win_rate": round(mf_summary["win_rate"] - fixed_summary["win_rate"], 4),
            "avg_holding_days": round(mf_summary["avg_holding_days"] - fixed_summary["avg_holding_days"], 4),
        },
        "hybrid_delta_vs_fixed": {
            "avg_return_pct": round(hybrid_summary["avg_return_pct"] - fixed_summary["avg_return_pct"], 4),
            "win_rate": round(hybrid_summary["win_rate"] - fixed_summary["win_rate"], 4),
            "avg_holding_days": round(
                hybrid_summary["avg_holding_days"] - fixed_summary["avg_holding_days"], 4
            ),
        },
        "sample_trades": {
            "mf26x_top_winners": sorted(mf_trades, key=lambda item: item["pnl_pct"], reverse=True)[:10],
            "mf26x_top_losers": sorted(mf_trades, key=lambda item: item["pnl_pct"])[:10],
        },
    }


def run_backtest(args: argparse.Namespace) -> dict[str, Any]:
    rules = load_candidate_rules(Path(args.rules_path))
    frames = load_price_frames(Path(args.db_path))
    return run_backtest_core(rules, frames, params_from_args(args))


def robust_score(summary: dict[str, Any]) -> float:
    stop_loss_count = int(summary["exit_reasons"].get("mf26x_stop_loss", 0))
    stop_loss_rate = stop_loss_count / max(1, int(summary["trade_count"])) * 100
    return round(
        float(summary["avg_return_pct"])
        + float(summary["median_return_pct"])
        + float(summary["win_rate"]) * 0.05
        - stop_loss_rate * 0.10,
        4,
    )


def run_grid_search(args: argparse.Namespace) -> dict[str, Any]:
    rules = load_candidate_rules(Path(args.rules_path))
    frames = load_price_frames(Path(args.db_path))
    rows: list[dict[str, Any]] = []
    practical_grid = [
        (60, 1.45, 1.5, 0.08),
        (60, 1.35, 1.5, 0.08),
        (60, 1.25, 2.0, 0.08),
        (60, 1.15, 2.0, 0.08),
        (80, 1.45, 1.5, 0.08),
        (80, 1.35, 1.5, 0.08),
        (80, 1.25, 2.0, 0.08),
        (80, 1.15, 2.0, 0.08),
        (120, 1.45, 1.5, 0.08),
        (120, 1.35, 1.5, 0.08),
        (120, 1.25, 2.0, 0.08),
        (120, 1.15, 2.0, 0.08),
        (80, 1.25, 2.0, 0.06),
        (120, 1.25, 2.0, 0.06),
    ]
    for min_base_len, max_entry_multiple, min_volume_ratio, stop_loss_pct in practical_grid:
        params = params_from_args(args)
        params.update(
            {
                "min_base_len": min_base_len,
                "max_entry_multiple": max_entry_multiple,
                "min_volume_ratio": min_volume_ratio,
                "stop_loss_pct": stop_loss_pct,
            }
        )
        report = run_backtest_core(rules, frames, params)
        mf = report["mf26x_exit"]
        fixed = report["fixed_exit"]
        rows.append(
            {
                "params": params,
                "signals": report["signals"],
                "mf26x": mf,
                "fixed": fixed,
                "delta": report["delta"],
                "robust_score": robust_score(mf),
            }
        )
    eligible = [row for row in rows if row["mf26x"]["trade_count"] >= int(args.min_grid_trades)]
    eligible.sort(key=lambda item: item["robust_score"], reverse=True)
    return {
        "review_only": True,
        "simulation_only": True,
        "grid_count": len(rows),
        "eligible_count": len(eligible),
        "min_grid_trades": int(args.min_grid_trades),
        "top": eligible[:15],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MF26x Strategy Sandbox Backtest",
        "",
        "Review-only / simulation-only. Amount proxy is used only inside this sandbox when amount is missing.",
        "",
        "## Data",
        "",
        f"- params: `{json.dumps(report['params'], ensure_ascii=False)}`",
        f"- symbols: {report['data']['symbols']}",
        f"- rows: {report['data']['rows']}",
        f"- amount_proxy_used_rows: {report['data']['amount_proxy_used_rows']}",
        f"- raw_signal_count: {report['signals']['raw_signal_count']}",
        f"- non_overlapping_signal_count: {report['signals']['non_overlapping_signal_count']}",
        "",
        "## Exit Comparison",
        "",
        "| track | trades | win rate | avg return | median return | sum return | avg holding |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label in [("fixed_exit", "fixed 8/15/5d"), ("mf26x_exit", "mf26x staged")]:
        summary = report[key]
        lines.append(
            f"| {label} | {summary['trade_count']} | {summary['win_rate']:.2f}% | "
            f"{summary['avg_return_pct']:.2f}% | {summary['median_return_pct']:.2f}% | "
            f"{summary['sum_return_pct']:.2f}% | {summary['avg_holding_days']:.2f} |"
        )
    summary = report["hybrid_split"]
    lines.append(
        f"| hybrid 50/50 | {summary['trade_count']} | {summary['win_rate']:.2f}% | "
        f"{summary['avg_return_pct']:.2f}% | {summary['median_return_pct']:.2f}% | "
        f"{summary['sum_return_pct']:.2f}% | {summary['avg_holding_days']:.2f} |"
    )
    lines.extend(
        [
            "",
            "## Delta",
            "",
            f"- avg_return_pct: {report['delta']['avg_return_pct']:.2f}",
            f"- win_rate: {report['delta']['win_rate']:.2f}",
            f"- avg_holding_days: {report['delta']['avg_holding_days']:.2f}",
            "",
            "## MF26x Exit Reasons",
            "",
        ]
    )
    for reason, count in sorted(report["mf26x_exit"]["exit_reasons"].items()):
        lines.append(f"- {reason}: {count}")
    return "\n".join(lines)


def render_grid_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MF26x Strategy Parameter Grid",
        "",
        "Review-only / simulation-only parameter comparison.",
        "",
        f"- grid_count: {report['grid_count']}",
        f"- eligible_count: {report['eligible_count']}",
        f"- min_grid_trades: {report['min_grid_trades']}",
        "",
        "| rank | robust | trades | win | avg | median | stop-loss exits | min base | max entry x | min volume | stop loss |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(report["top"], 1):
        params = row["params"]
        mf = row["mf26x"]
        lines.append(
            f"| {index} | {row['robust_score']:.2f} | {mf['trade_count']} | {mf['win_rate']:.2f}% | "
            f"{mf['avg_return_pct']:.2f}% | {mf['median_return_pct']:.2f}% | "
            f"{int(mf['exit_reasons'].get('mf26x_stop_loss', 0))} | {params['min_base_len']} | "
            f"{params['max_entry_multiple']:.2f} | {params['min_volume_ratio']:.2f} | "
            f"{params['stop_loss_pct']:.2f} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review-only MF26x staged exit sandbox backtest.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--rules-path", default=str(DEFAULT_RULES_PATH))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--grid-search", action="store_true")
    parser.add_argument("--min-grid-trades", type=int, default=20)
    parser.add_argument("--min-base-len", type=int, default=60)
    parser.add_argument("--max-entry-multiple", type=float, default=1.45)
    parser.add_argument("--min-volume-ratio", type=float, default=1.5)
    parser.add_argument("--max-single-day-chase-pct", type=float, default=12.0)
    parser.add_argument("--stop-loss-pct", type=float, default=0.08)
    parser.add_argument("--fixed-take-profit-pct", type=float, default=0.15)
    parser.add_argument("--fixed-max-holding-days", type=int, default=5)
    parser.add_argument("--mf-max-holding-days", type=int, default=160)
    parser.add_argument("--failure-guard-days", type=int, default=0)
    parser.add_argument("--failure-guard-min-gain-pct", type=float, default=0.08)
    parser.add_argument("--risk-reduce-trigger-pct", type=float, default=0.0)
    parser.add_argument("--risk-reduce-sell-pct", type=float, default=0.0)
    args = parser.parse_args()

    report = run_grid_search(args) if args.grid_search else run_backtest(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.grid_search:
        print(render_grid_markdown(report))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
