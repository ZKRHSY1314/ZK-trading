from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_DB_PATH = Path("trading_local.sqlite3")
DEFAULT_LIMIT = 80
DEFAULT_WORKERS = 8


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    code: str
    name: str | None
    best_score: float | None


def normalize_a_share_code(symbol: str) -> str:
    match = re.search(r"(\d{6})", symbol)
    if not match:
        raise ValueError(f"Cannot recognize A-share code: {symbol}")
    return match.group(1)


def with_exchange_prefix(symbol: str) -> str:
    code = normalize_a_share_code(symbol)
    return f"SH{code}" if code.startswith(("6", "9")) else f"SZ{code}"


def load_universe(db_path: Path, limit: int) -> list[SymbolInfo]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        WITH universe AS (
            SELECT symbol, name, total_score AS score FROM candidate_scores
            UNION ALL SELECT symbol, name, potential_score AS score FROM potential_search_items
            UNION ALL SELECT symbol, name, priority AS score FROM auto_discovered_candidates
            UNION ALL SELECT symbol, name, NULL AS score FROM main_force_phase_replays
            UNION ALL SELECT symbol, NULL AS name, NULL AS score FROM daily_bar_cache
        )
        SELECT symbol, MAX(name) AS name, MAX(score) AS best_score
        FROM universe
        WHERE symbol NOT LIKE 'SH000%'
          AND symbol NOT LIKE 'SZ399%'
        GROUP BY symbol
        ORDER BY COALESCE(MAX(score), 0) DESC, symbol
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    symbols = [
        SymbolInfo(
            symbol=with_exchange_prefix(row["symbol"]),
            code=normalize_a_share_code(row["symbol"]),
            name=row["name"],
            best_score=row["best_score"],
        )
        for row in rows
    ]
    if all(item.code != "002115" for item in symbols):
        symbols.append(SymbolInfo("SZ002115", "002115", "Sanwei Communication calibration", None))
    return symbols


def fetch_sina_daily_bars(code: str, datalen: int = 1200, retries: int = 3) -> pd.DataFrame:
    prefix = "sh" if code.startswith("6") else "sz"
    url = (
        "https://quotes.sina.cn/cn/api/jsonp.php/var%20_mainForce26x=/"
        "CN_MarketDataService.getKLineData?"
        f"symbol={prefix}{code}&scale=240&ma=no&datalen={datalen}"
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
                sleep(1.0 + attempt)
    else:
        raise RuntimeError(f"Sina daily bars request failed: {last_exc}") from last_exc
    match = re.search(r"var\s+_mainForce26x=\((.*)\);?", body, re.S)
    if not match:
        raise RuntimeError("Sina JSONP response could not be parsed")
    rows = json.loads(match.group(1))
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    bars = pd.DataFrame(
        {
            "date": frame["day"],
            "open": pd.to_numeric(frame["open"], errors="coerce"),
            "close": pd.to_numeric(frame["close"], errors="coerce"),
            "high": pd.to_numeric(frame["high"], errors="coerce"),
            "low": pd.to_numeric(frame["low"], errors="coerce"),
            "volume": pd.to_numeric(frame["volume"], errors="coerce"),
        }
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce")
    bars = bars.dropna(subset=["date", "close", "high", "low", "volume"])
    return bars.sort_values("date").reset_index(drop=True)


def scan_bars(info: SymbolInfo, bars: pd.DataFrame) -> dict[str, Any] | None:
    if len(bars) < 160:
        return None

    frame = bars.copy()
    frame["vol_ma20"] = frame["volume"].rolling(20, min_periods=5).mean()
    frame["vol_ratio"] = frame["volume"] / frame["vol_ma20"]
    n = len(frame)
    candidates: list[dict[str, Any]] = []

    for base_len in (120, 160, 200, 240, 300, 360, 420, 500):
        if n < base_len + 40:
            continue
        for base_end in range(base_len, n - 30, 5):
            base = frame.iloc[base_end - base_len : base_end]
            base_avg = float(base["close"].mean())
            if base_avg <= 0 or math.isnan(base_avg):
                continue
            base_min = float(base["close"].min())
            base_max = float(base["close"].max())
            if base_min <= 0:
                continue
            base_range = base_max / base_min - 1
            base_cv = float(base["close"].std() / base_avg)
            if base_range > 1.6 or base_cv > 0.38:
                continue

            future = frame.iloc[base_end : min(n, base_end + 300)]
            if len(future) < 20:
                continue
            peak_pos = int(future["high"].idxmax())
            peak_high = float(frame.loc[peak_pos, "high"])
            peak_ratio = peak_high / base_avg
            if not 1.9 <= peak_ratio <= 3.4:
                continue

            after = frame.iloc[peak_pos + 1 : min(n, peak_pos + 160)]
            drawdown = 0.0
            if len(after):
                drawdown = float(after["close"].min()) / peak_high - 1
            future_vol_ratio = (
                float(future["vol_ratio"].max()) if future["vol_ratio"].notna().any() else 0.0
            )

            target_score = max(0.0, 1 - abs(peak_ratio - 2.6) / 0.7) * 35
            stable_score = max(0.0, 1 - base_cv / 0.30) * 15 + max(
                0.0, 1 - base_range / 1.5
            ) * 10
            long_score = min(base_len / 360, 1) * 12
            launch_score = min(max(peak_ratio - 1.0, 0) / 1.6, 1) * 13
            draw_score = min(max(-drawdown, 0) / 0.4, 1) * 10
            vol_score = min(max(future_vol_ratio - 1, 0) / 3, 1) * 5
            score = target_score + stable_score + long_score + launch_score + draw_score + vol_score

            candidates.append(
                {
                    "symbol": info.symbol,
                    "name": info.name,
                    "candidate_best_score": info.best_score,
                    "pattern_score": round(score, 4),
                    "base_len": base_len,
                    "base_start": frame.loc[base.index[0], "date"].date().isoformat(),
                    "base_end": frame.loc[base.index[-1], "date"].date().isoformat(),
                    "peak_date": frame.loc[peak_pos, "date"].date().isoformat(),
                    "avg_cost": round(base_avg, 4),
                    "target_26x": round(base_avg * 2.6, 4),
                    "peak_high": round(peak_high, 4),
                    "peak_to_cost": round(peak_ratio, 4),
                    "target_error_pct": round((peak_ratio / 2.6 - 1) * 100, 3),
                    "base_range_pct": round(base_range * 100, 3),
                    "base_cv": round(base_cv, 4),
                    "days_to_peak": peak_pos - base_end + 1,
                    "post_peak_drawdown_pct": round(drawdown * 100, 3),
                    "max_future_volume_ratio": round(future_vol_ratio, 4),
                }
            )

    if not candidates:
        return None
    candidates.sort(key=lambda item: item["pattern_score"], reverse=True)
    return candidates[0]


def scan_symbol(info: SymbolInfo) -> dict[str, Any]:
    try:
        bars = fetch_sina_daily_bars(info.code)
        result = scan_bars(info, bars)
        if result is None:
            return {"symbol": info.symbol, "name": info.name, "status": "no_match", "bars": len(bars)}
        result["status"] = "matched"
        result["bars"] = len(bars)
        result["data_source"] = "sina.cn.kline_daily_fallback"
        return result
    except Exception as exc:
        return {"symbol": info.symbol, "name": info.name, "status": "error", "error": str(exc)}


def render_markdown(results: list[dict[str, Any]], min_score: float) -> str:
    matched = [item for item in results if item.get("status") == "matched"]
    matched = [item for item in matched if float(item.get("pattern_score", 0)) >= min_score]
    matched.sort(key=lambda item: item["pattern_score"], reverse=True)
    lines = [
        "# Main-force 2.6x Sandbox Scan",
        "",
        "Research-only scan. The 2.6x level is treated as a take-profit/risk zone, not a buy signal.",
        "No orders, no broker API, no rules.yaml mutation.",
        "",
        f"Matched above threshold: {len(matched)}",
        "",
        "| rank | symbol | name | score | base | avg cost | 2.6x take-profit | peak | peak/cost | error | drawdown | volume ratio |",
        "|---:|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, item in enumerate(matched[:30], 1):
        row = dict(item)
        row["name"] = row.get("name") or ""
        lines.append(
            "| {rank} | {symbol} | {name} | {score:.2f} | {base_start}..{base_end} ({base_len}) | "
            "{avg_cost:.2f} | {target_26x:.2f} | {peak_high:.2f} @ {peak_date} | {peak_to_cost:.2f} | "
            "{target_error_pct:.1f}% | {post_peak_drawdown_pct:.1f}% | {max_future_volume_ratio:.2f} |".format(
                rank=idx,
                score=float(item["pattern_score"]),
                **row,
            )
        )
    errors = [item for item in results if item.get("status") == "error"]
    no_match = [item for item in results if item.get("status") == "no_match"]
    lines.extend(
        [
            "",
            f"Scanned: {len(results)}",
            f"No match: {len(no_match)}",
            f"Errors: {len(errors)}",
        ]
    )
    if errors:
        lines.append("")
        lines.append("## Errors")
        for item in errors[:20]:
            lines.append(f"- {item.get('symbol')}: {item.get('error')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only scan for 2.6x main-force pull-up cases.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--min-score", type=float, default=62.0)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    universe = load_universe(db_path, max(1, args.limit))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(scan_symbol, info): info for info in universe}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(
        key=lambda item: (
            item.get("status") == "matched",
            float(item.get("pattern_score", 0) or 0),
        ),
        reverse=True,
    )

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(results, args.min_score))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
