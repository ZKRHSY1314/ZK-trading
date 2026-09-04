from __future__ import annotations

import argparse
import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd
import yaml


DEFAULT_DB_PATH = Path("trading_local.sqlite3")
DEFAULT_RULES_PATH = Path("backend/configs/review_only_buy_sell_rules.yaml")
DEFAULT_OUTPUT_PATH = Path("docs/research/monday_buy_plan_2026-06-22.md")


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    code: str
    name: str | None
    best_score: float | None
    source: str


def normalize_a_share_code(symbol: str) -> str:
    match = re.search(r"(\d{6})", str(symbol))
    if not match:
        raise ValueError(f"Cannot recognize A-share code: {symbol}")
    return match.group(1)


def with_exchange_prefix(symbol: str) -> str:
    code = normalize_a_share_code(symbol)
    return f"SH{code}" if code.startswith(("6", "9")) else f"SZ{code}"


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def load_candidate_rules(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        rules = yaml.safe_load(handle) or {}
    if not isinstance(rules, dict):
        raise ValueError(f"{path} did not contain a YAML object")
    if not rules.get("review_only") or not rules.get("simulation_only"):
        raise ValueError("candidate rules must stay review_only and simulation_only")
    if rules.get("writes_rules_yaml") is not False or rules.get("live_ordering") is not False:
        raise ValueError("candidate rules must not write production rules or enable live ordering")
    return rules


def profile_params(rules: dict[str, Any]) -> dict[str, Any]:
    profile = rules.get("sandbox_recommended_profile") or {}
    params: dict[str, Any] = {}
    params.update(profile.get("buy_filters") or {})
    params.update(profile.get("risk_controls") or {})
    return params


def load_universe(db_path: Path, limit: int) -> list[SymbolInfo]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    selects = [
        """
        SELECT symbol, MAX(name) AS name, MAX(total_score) AS score, 'candidate_scores' AS source
        FROM candidate_scores
        WHERE symbol NOT LIKE 'SH000%' AND symbol NOT LIKE 'SZ399%'
        GROUP BY symbol
        """,
        """
        SELECT symbol, MAX(name) AS name, NULL AS score, 'main_force_phase_replays' AS source
        FROM main_force_phase_replays
        WHERE symbol NOT LIKE 'SH000%' AND symbol NOT LIKE 'SZ399%'
        GROUP BY symbol
        """,
    ]
    optional_sources = {
        "potential_search_items": """
            SELECT symbol, MAX(name) AS name, MAX(potential_score) AS score, 'potential_search_items' AS source
            FROM potential_search_items
            WHERE symbol NOT LIKE 'SH000%' AND symbol NOT LIKE 'SZ399%'
            GROUP BY symbol
        """,
        "auto_discovered_candidates": """
            SELECT symbol, MAX(name) AS name, MAX(priority) AS score, 'auto_discovered_candidates' AS source
            FROM auto_discovered_candidates
            WHERE symbol NOT LIKE 'SH000%' AND symbol NOT LIKE 'SZ399%'
            GROUP BY symbol
        """,
    }
    for table, sql in optional_sources.items():
        if table_exists(conn, table):
            selects.append(sql)

    union_sql = " UNION ALL ".join(selects)
    rows = conn.execute(
        f"""
        WITH universe AS ({union_sql})
        SELECT symbol, MAX(name) AS name, MAX(score) AS best_score, MAX(source) AS source
        FROM universe
        GROUP BY symbol
        ORDER BY COALESCE(MAX(score), 0) DESC, symbol
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    output: list[SymbolInfo] = []
    seen: set[str] = set()
    for row in rows:
        try:
            symbol = with_exchange_prefix(row["symbol"])
        except ValueError:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        output.append(
            SymbolInfo(
                symbol=symbol,
                code=normalize_a_share_code(symbol),
                name=row["name"],
                best_score=float(row["best_score"]) if row["best_score"] is not None else None,
                source=row["source"] or "universe",
            )
        )
    return output


def load_phase_replays(db_path: Path) -> dict[str, dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.symbol, r.name, r.latest_phase, r.summary_json, r.features_json, r.created_at
        FROM main_force_phase_replays r
        JOIN (
            SELECT symbol, MAX(created_at) AS latest_created_at
            FROM main_force_phase_replays
            GROUP BY symbol
        ) latest
          ON latest.symbol = r.symbol
         AND latest.latest_created_at = r.created_at
        """
    ).fetchall()
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = with_exchange_prefix(row["symbol"])
        try:
            summary = json.loads(row["summary_json"] or "{}")
        except json.JSONDecodeError:
            summary = {}
        try:
            features = json.loads(row["features_json"] or "{}")
        except json.JSONDecodeError:
            features = {}
        output[symbol] = {
            "name": row["name"],
            "latest_phase": row["latest_phase"],
            "created_at": row["created_at"],
            "summary": summary,
            "features": features,
        }
    return output


def load_local_bars(db_path: Path, symbol: str, limit: int = 900) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT symbol, trade_date, open, high, low, close, volume, amount, source
        FROM daily_bar_cache
        WHERE symbol = ?
          AND quality_status = 'ready'
          AND trade_date != 'ERROR'
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (symbol, max(120, int(limit))),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(
        rows,
        columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount", "source"],
    )
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "amount"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("trade_date").dropna(subset=["trade_date", "close"]).reset_index(drop=True)


def fetch_sina_daily_bars(code: str, datalen: int = 900, retries: int = 2) -> pd.DataFrame:
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    url = (
        "https://quotes.sina.cn/cn/api/jsonp.php/var%20_mondayPlan=/"
        "CN_MarketDataService.getKLineData?"
        f"symbol={prefix}{code}&scale=240&ma=no&datalen={int(datalen)}"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_exc: Exception | None = None
    body = ""
    for attempt in range(max(1, retries)):
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8", errors="ignore")
            break
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < retries:
                sleep(0.8 + attempt)
    else:
        raise RuntimeError(f"Sina daily bars request failed: {last_exc}") from last_exc
    match = re.search(r"var\s+_mondayPlan=\((.*)\);?", body, re.S)
    if not match:
        raise RuntimeError("Sina JSONP response could not be parsed")
    rows = json.loads(match.group(1))
    if not rows:
        return pd.DataFrame()
    raw = pd.DataFrame(rows)
    frame = pd.DataFrame(
        {
            "symbol": with_exchange_prefix(code),
            "trade_date": pd.to_datetime(raw["day"], errors="coerce"),
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "volume": pd.to_numeric(raw["volume"], errors="coerce"),
            "amount": pd.NA,
            "source": "sina.cn.kline_daily_fallback",
        }
    )
    return frame.sort_values("trade_date").dropna(subset=["trade_date", "close"]).reset_index(drop=True)


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in ["open", "high", "low", "close", "volume", "amount"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)
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
    frame["daily_return_pct"] = frame["close"].pct_change() * 100
    body_top = frame[["open", "close"]].max(axis=1)
    frame["upper_shadow_pct"] = (frame["high"] - body_top) / frame["close"].replace(0, pd.NA) * 100
    frame["return_20_pct"] = (frame["close"] / frame["close"].shift(20) - 1) * 100
    frame["return_60_pct"] = (frame["close"] / frame["close"].shift(60) - 1) * 100
    frame["position_120"] = (
        (frame["close"] - frame["low"].rolling(120, min_periods=40).min())
        / (frame["high"].rolling(120, min_periods=40).max() - frame["low"].rolling(120, min_periods=40).min())
    )
    return frame


def best_base(latest_index: int, frame: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any] | None:
    windows = [80, 120, 160, 200, 240, 300, 360, 420, 500]
    min_base_len = int(params.get("min_base_len") or 80)
    max_entry_multiple = float(params.get("max_entry_multiple") or 1.25)
    candidates: list[dict[str, Any]] = []
    latest = frame.iloc[latest_index]
    for base_len in windows:
        if base_len < min_base_len or latest_index < base_len:
            continue
        base = frame.iloc[latest_index - base_len : latest_index]
        avg_cost = float(base["close"].mean())
        base_min = float(base["close"].min())
        if avg_cost <= 0 or base_min <= 0:
            continue
        base_cv = float(base["close"].std() / avg_cost)
        base_range_pct = float((base["close"].max() / base_min - 1) * 100)
        price_multiple = float(latest["close"] / avg_cost)
        stable = base_cv <= 0.30 and base_range_pct <= 90
        near_cost = 1.0 <= price_multiple <= max_entry_multiple
        candidates.append(
            {
                "base_len": base_len,
                "avg_cost": avg_cost,
                "base_cv": base_cv,
                "base_range_pct": base_range_pct,
                "price_multiple": price_multiple,
                "target_245": avg_cost * 2.45,
                "target_260": avg_cost * 2.60,
                "stable": stable,
                "near_cost": near_cost,
                "base_start": str(base.iloc[0]["trade_date"].date()),
                "base_end": str(base.iloc[-1]["trade_date"].date()),
            }
        )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item["stable"],
            item["near_cost"],
            -abs(item["price_multiple"] - 1.08),
            item["base_len"],
        ),
        reverse=True,
    )
    return candidates[0]


def phase_label(phase: str | None) -> str:
    return {
        "accumulation": "吸筹",
        "test_pull": "试盘",
        "markup": "拉升",
        "distribution": "派发",
        "post_distribution_watch": "出货后观察",
        "observe": "观察",
    }.get(str(phase or ""), str(phase or "unknown"))


def evaluate_symbol(
    info: SymbolInfo,
    frame: pd.DataFrame,
    params: dict[str, Any],
    phase_info: dict[str, Any] | None,
    expected_last_trade_date: str,
) -> dict[str, Any]:
    if frame.empty or len(frame) < 120:
        return {
            "symbol": info.symbol,
            "name": info.name,
            "status": "data_error",
            "action": "skip",
            "reasons": ["insufficient_daily_bars"],
        }
    frame = add_indicators(frame)
    if frame.empty or len(frame) < 120:
        return {
            "symbol": info.symbol,
            "name": info.name,
            "status": "data_error",
            "action": "skip",
            "reasons": ["insufficient_valid_daily_bars"],
        }

    latest_index = len(frame) - 1
    latest = frame.iloc[latest_index]
    base = best_base(latest_index, frame, params)
    latest_date = str(latest["trade_date"].date())
    reasons: list[str] = []
    positive: list[str] = []
    warnings: list[str] = []

    if latest_date < expected_last_trade_date:
        warnings.append(f"latest_data_before_expected_last_trade_date:{latest_date}<{expected_last_trade_date}")
    if base is None:
        return {
            "symbol": info.symbol,
            "name": info.name,
            "status": "no_base",
            "action": "skip",
            "latest_date": latest_date,
            "latest_close": round(float(latest["close"]), 4),
            "reasons": ["no_valid_long_base"],
            "warnings": warnings,
        }

    close = float(latest["close"])
    volume_ratio = float(latest.get("volume_ratio") or 0)
    daily_return_pct = float(latest.get("daily_return_pct") or 0)
    upper_shadow_pct = float(latest.get("upper_shadow_pct") or 0)
    ma20 = float(latest.get("ma20") or 0)
    ma60 = float(latest.get("ma60") or 0)
    return_20_pct = float(latest.get("return_20_pct") or 0)
    return_60_pct = float(latest.get("return_60_pct") or 0)
    position_120 = float(latest.get("position_120") or 0)
    phase = (phase_info or {}).get("latest_phase")

    min_volume_ratio = float(params.get("min_volume_ratio") or 2.0)
    max_single_day_chase_pct = float(params.get("max_single_day_chase_pct") or 12.0)
    max_entry_multiple = float(params.get("max_entry_multiple") or 1.25)

    if base["stable"]:
        positive.append("long_base_stable")
    else:
        reasons.append("base_not_stable_enough")
    if 1.0 <= base["price_multiple"] <= max_entry_multiple:
        positive.append("price_near_base_cost")
    else:
        reasons.append("price_not_in_pre_markup_cost_zone")
    if volume_ratio >= min_volume_ratio:
        positive.append("volume_breakout_confirmed")
    else:
        reasons.append("volume_ratio_below_entry_filter")
    if close > ma20:
        positive.append("close_above_ma20")
    else:
        reasons.append("close_not_above_ma20")
    if ma60 <= 0 or close >= ma60 * 0.98:
        positive.append("ma60_reclaim_ok")
    else:
        reasons.append("close_below_ma60_reclaim_zone")
    if daily_return_pct <= max_single_day_chase_pct:
        positive.append("not_single_day_chase")
    else:
        reasons.append("single_day_chase_too_high")
    if upper_shadow_pct < 8:
        positive.append("upper_shadow_ok")
    else:
        reasons.append("upper_shadow_distribution_risk")

    overextended = False
    if base["price_multiple"] >= 2.30:
        overextended = True
        reasons.append("already_near_26x_risk_zone")
    if return_20_pct > 35:
        overextended = True
        reasons.append("return_20_overextended")
    if return_60_pct > 60:
        overextended = True
        reasons.append("return_60_overextended")
    if position_120 > 0.88:
        overextended = True
        reasons.append("near_120d_high_chase_risk")
    if phase in {"distribution", "post_distribution_watch"}:
        reasons.append(f"phase_risk:{phase}")
    elif phase in {"accumulation", "test_pull", "markup"}:
        positive.append(f"phase_support:{phase}")
    else:
        warnings.append(f"phase_unknown_or_unmatched:{phase}")

    score = 0.0
    score += max(0.0, 1 - base["base_cv"] / 0.30) * 18
    score += max(0.0, 1 - base["base_range_pct"] / 90.0) * 12
    score += min(base["base_len"] / 240.0, 1.0) * 8
    score += max(0.0, 1 - max(base["price_multiple"] - 1.0, 0) / max(max_entry_multiple - 1.0, 0.01)) * 16
    score += min(volume_ratio / 3.0, 1.0) * 16
    score += 8 if close > ma20 else -8
    score += 5 if ma60 <= 0 or close >= ma60 * 0.98 else -5
    phase_score = {"accumulation": 10, "test_pull": 9, "markup": 4, "observe": 2, None: 0}.get(phase, -14)
    score += phase_score
    score -= 12 if return_20_pct > 35 else 0
    score -= 8 if return_60_pct > 60 else 0
    score -= 10 if position_120 > 0.88 else 0
    score += min(max((info.best_score or 0) - 50, 0) / 25, 1) * 5

    strict_ready = (
        base["stable"]
        and 1.0 <= base["price_multiple"] <= max_entry_multiple
        and volume_ratio >= min_volume_ratio
        and close > ma20
        and (ma60 <= 0 or close >= ma60 * 0.98)
        and daily_return_pct <= max_single_day_chase_pct
        and upper_shadow_pct < 8
        and not overextended
        and phase not in {"distribution", "post_distribution_watch"}
        and latest_date >= expected_last_trade_date
    )
    watch_ready = (
        base["stable"]
        and 0.96 <= base["price_multiple"] <= 1.35
        and volume_ratio >= 1.35
        and close > ma20 * 0.985
        and daily_return_pct <= max_single_day_chase_pct
        and phase not in {"distribution", "post_distribution_watch"}
        and latest_date >= expected_last_trade_date
    )

    if strict_ready:
        action = "conditional_buy"
        status = "candidate_ready"
    elif watch_ready:
        action = "watch_for_monday_confirmation"
        status = "watch"
    elif overextended or phase in {"distribution", "post_distribution_watch"}:
        action = "avoid_chase"
        status = "risk_reject"
    else:
        action = "skip"
        status = "filter_reject"

    max_buy_price = min(close * 1.03, base["avg_cost"] * max_entry_multiple)
    invalid_price = base["avg_cost"] * 2.30

    return {
        "symbol": info.symbol,
        "name": info.name or (phase_info or {}).get("name"),
        "source": str(latest.get("source") or info.source),
        "candidate_best_score": round(float(info.best_score), 4) if info.best_score is not None else None,
        "status": status,
        "action": action,
        "score": round(score, 4),
        "latest_date": latest_date,
        "latest_close": round(close, 4),
        "latest_volume_ratio": round(volume_ratio, 4),
        "daily_return_pct": round(daily_return_pct, 4),
        "upper_shadow_pct": round(upper_shadow_pct, 4),
        "return_20_pct": round(return_20_pct, 4),
        "return_60_pct": round(return_60_pct, 4),
        "position_120": round(position_120, 4),
        "latest_phase": phase,
        "latest_phase_name": phase_label(phase),
        "base_len": base["base_len"],
        "base_start": base["base_start"],
        "base_end": base["base_end"],
        "avg_cost": round(base["avg_cost"], 4),
        "price_multiple": round(base["price_multiple"], 4),
        "base_cv": round(base["base_cv"], 4),
        "base_range_pct": round(base["base_range_pct"], 4),
        "target_245": round(base["target_245"], 4),
        "target_260": round(base["target_260"], 4),
        "max_buy_price": round(max_buy_price, 4),
        "invalid_price_gte": round(invalid_price, 4),
        "positive": positive,
        "reasons": sorted(set(reasons)),
        "warnings": sorted(set(warnings)),
        "amount_proxy_used": bool(frame["amount_proxy_used"].any()),
    }


def load_or_fetch(info: SymbolInfo, db_path: Path, refresh_sina: bool) -> tuple[pd.DataFrame, str | None]:
    if refresh_sina:
        try:
            return fetch_sina_daily_bars(info.code), None
        except Exception as exc:
            local = load_local_bars(db_path, info.symbol)
            if not local.empty:
                local = local.copy()
                local["source"] = local["source"].astype(str) + "_cached_after_sina_error"
                return local, str(exc)
            return pd.DataFrame(), str(exc)
    return load_local_bars(db_path, info.symbol), None


def evaluate_universe(
    universe: list[SymbolInfo],
    db_path: Path,
    params: dict[str, Any],
    phase_replays: dict[str, dict[str, Any]],
    expected_last_trade_date: str,
    refresh_sina: bool,
    workers: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def run_one(info: SymbolInfo) -> dict[str, Any]:
        frame, fetch_error = load_or_fetch(info, db_path, refresh_sina)
        row = evaluate_symbol(info, frame, params, phase_replays.get(info.symbol), expected_last_trade_date)
        if fetch_error:
            row.setdefault("warnings", []).append(f"sina_fetch_error:{fetch_error}")
        return row

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
        futures = {executor.submit(run_one, info): info for info in universe}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(
        key=lambda item: (
            item.get("action") == "conditional_buy",
            item.get("action") == "watch_for_monday_confirmation",
            float(item.get("score") or -999),
        ),
        reverse=True,
    )
    return results


def action_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in results:
        action = str(item.get("action") or "unknown")
        counts[action] = counts.get(action, 0) + 1
    return counts


def render_candidate_table(rows: list[dict[str, Any]], limit: int) -> list[str]:
    lines = [
        "| rank | action | symbol | name | phase | close | avg cost | cost x | vol x | score | plan price | TP watch | main reasons |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for idx, item in enumerate(rows[:limit], 1):
        reasons = item.get("reasons") or []
        positives = item.get("positive") or []
        reason_text = ", ".join((positives[:3] + reasons[:2])[:5])
        lines.append(
            f"| {idx} | {item.get('action')} | {item.get('symbol')} | {item.get('name') or ''} | "
            f"{item.get('latest_phase_name') or ''} | {float(item.get('latest_close') or 0):.2f} | "
            f"{float(item.get('avg_cost') or 0):.2f} | {float(item.get('price_multiple') or 0):.2f} | "
            f"{float(item.get('latest_volume_ratio') or 0):.2f} | {float(item.get('score') or 0):.1f} | "
            f"{float(item.get('max_buy_price') or 0):.2f} | {float(item.get('target_260') or 0):.2f} | "
            f"{reason_text} |"
        )
    return lines


def render_markdown(report: dict[str, Any], top_n: int) -> str:
    results = report["results"]
    conditional = [row for row in results if row.get("action") == "conditional_buy"]
    watch = [row for row in results if row.get("action") == "watch_for_monday_confirmation"]
    avoid = [row for row in results if row.get("action") == "avoid_chase"]
    lines = [
        f"# Monday Buy Plan {report['plan_date']}",
        "",
        "Review-only / simulation-only. This file is a conditional plan, not an order list.",
        "",
        "## Safety Gate",
        "",
        f"- live_trading_enabled_required_false: {report['safety']['live_trading_enabled_required_false']}",
        f"- writes_rules_yaml: {report['safety']['writes_rules_yaml']}",
        f"- live_ordering: {report['safety']['live_ordering']}",
        "",
        "## Data",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- expected_last_trade_date: {report['expected_last_trade_date']}",
        f"- refresh_sina: {report['refresh_sina']}",
        f"- universe_size: {report['universe_size']}",
        f"- action_counts: `{json.dumps(report['action_counts'], ensure_ascii=False)}`",
        f"- amount_proxy_used: {report['amount_proxy_used']}",
        "",
        "## Conditional Buys",
        "",
    ]
    if conditional:
        lines.extend(render_candidate_table(conditional, top_n))
    else:
        lines.append("No conditional_buy candidates passed all filters. Keep plan at watch-only.")

    lines.extend(
        [
            "",
            "## Watch List",
            "",
        ]
    )
    if watch:
        lines.extend(render_candidate_table(watch, top_n))
    else:
        lines.append("No watch_for_monday_confirmation candidates.")

    lines.extend(
        [
            "",
            "## Avoid Chasing",
            "",
        ]
    )
    if avoid:
        lines.extend(render_candidate_table(avoid, min(top_n, 12)))
    else:
        lines.append("No avoid_chase candidates in the displayed set.")

    lines.extend(
        [
            "",
            "## Monday Execution Conditions",
            "",
            "These conditions are for simulation/review only:",
            "",
            "1. Do not act before 09:35. Require opening auction and first minutes to confirm price is not a one-day chase.",
            "2. For a conditional_buy candidate, simulated entry is allowed only if opening gap is <= 3%, price stays <= plan price, and first-30-minute volume confirms active demand.",
            "3. Reject immediately if price is at/near limit-up with no liquidity, intraday upper-shadow distribution appears, or price reaches the invalid 2.30x cost warning zone.",
            "4. Split the simulated position: 50% fixed track with 15% take-profit, 8% stop-loss, 5-day max hold; 50% runner track with 2.45x/2.60x staged exits.",
            "5. Total simulated exposure should remain capped; no real order, no broker API, no Tonghuashun click.",
            "",
            "## Full Result JSON",
            "",
            "```json",
            json.dumps(
                {
                    "plan_date": report["plan_date"],
                    "expected_last_trade_date": report["expected_last_trade_date"],
                    "action_counts": report["action_counts"],
                    "conditional_buy": conditional[:top_n],
                    "watch": watch[:top_n],
                    "avoid_chase": avoid[: min(top_n, 12)],
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
        ]
    )
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    rules = load_candidate_rules(Path(args.rules_path))
    params = profile_params(rules)
    db_path = Path(args.db_path)
    universe = load_universe(db_path, int(args.limit))
    phase_replays = load_phase_replays(db_path)
    results = evaluate_universe(
        universe=universe,
        db_path=db_path,
        params=params,
        phase_replays=phase_replays,
        expected_last_trade_date=str(args.expected_last_trade_date),
        refresh_sina=bool(args.refresh_sina),
        workers=int(args.workers),
    )
    return {
        "review_only": True,
        "simulation_only": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "plan_date": str(args.plan_date),
        "expected_last_trade_date": str(args.expected_last_trade_date),
        "rules_path": str(args.rules_path),
        "profile_id": (rules.get("sandbox_recommended_profile") or {}).get("id"),
        "refresh_sina": bool(args.refresh_sina),
        "universe_size": len(universe),
        "action_counts": action_counts(results),
        "amount_proxy_used": any(bool(row.get("amount_proxy_used")) for row in results),
        "safety": {
            "live_trading_enabled_required_false": True,
            "writes_rules_yaml": False,
            "live_ordering": False,
            "real_trading": False,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate review-only Monday buy plan from MF26x rules.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--rules-path", default=str(DEFAULT_RULES_PATH))
    parser.add_argument("--plan-date", default="2026-06-22")
    parser.add_argument("--expected-last-trade-date", default="2026-06-18")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--refresh-sina", action="store_true")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "json":
        output = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        output = render_markdown(report, int(args.top_n))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
