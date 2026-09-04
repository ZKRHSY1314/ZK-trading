"""Bounded, read-only comparison of local candles and existing public loaders.

No store/service constructor, refresh, DB write, client restart, or source-policy
mutation is allowed here. Provider frames live only in child/parent memory; the
optional output contains quality/latency summaries, not a market-data backfill.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
SOURCES = ("tonghuasun", "legacy_chain", "sina_reference")


def probe(source: str, symbol: str, days: int, product_home: str) -> dict:
    import pandas as pd
    from app.data.akshare_provider import AkshareProvider
    from app.data.daily_bar_cache import DailyBarCacheService
    from app.data.tonghuasun_provider import TonghuasunMarketDataProvider

    # Import costs are outside the timer, including AKShare's lazy import.
    import akshare  # noqa: F401

    attempts = []
    started = time.perf_counter()
    try:
        if source == "tonghuasun":
            frame = TonghuasunMarketDataProvider(
                product_home=product_home, timeout=8
            ).get_daily_bars(symbol, adjust="qfq", days=days)
        elif source == "legacy_chain":
            step_start = time.perf_counter()
            try:
                frame = AkshareProvider().get_daily_bars(symbol[:6], adjust="qfq")
                if frame is None or frame.empty:
                    raise ValueError("empty primary response")
                frame.attrs.update(source="akshare.stock_zh_a_hist", adjustment_mode="qfq", volume_unit="hand", amount_unit="yuan")
                attempts.append({"source": "akshare.stock_zh_a_hist", "status": "success", "seconds": time.perf_counter() - step_start})
            except Exception as exc:
                attempts.append({"source": "akshare.stock_zh_a_hist", "status": "failed", "error_type": type(exc).__name__, "seconds": time.perf_counter() - step_start})
                # Only the existing stateless loader; __init__ would init SQLite.
                stateless = object.__new__(DailyBarCacheService)
                step_start = time.perf_counter()
                frame = stateless._load_tencent_qfq_daily_bars(symbol, days=days)
                frame.attrs.setdefault("source", "tencent.fqkline.qfq")
                # No volume unit claim from the name alone; amount is absent.
                attempts.append({"source": frame.attrs["source"], "status": "success", "seconds": time.perf_counter() - step_start})
        elif source == "sina_reference":
            frame = AkshareProvider().get_daily_bars_sina(symbol, adjust="qfq")
            frame.attrs["amount_unit"] = "yuan"
        else:
            raise ValueError("unsupported source")
        elapsed = time.perf_counter() - started
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise ValueError("empty frame")
        # Narrow attributes: never forward exceptions, raw requests, or tokens.
        attrs = {key: frame.attrs[key] for key in ("source", "adjustment_mode", "volume_unit", "amount_unit") if key in frame.attrs}
        return {"status": "success", "seconds": elapsed, "attempts": attempts,
                "captured_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                "attributes": attrs, "frame": json.loads(frame.to_json(orient="split", date_format="iso"))}
    except Exception as exc:
        return {"status": "failed", "seconds": time.perf_counter() - started,
                "error_type": type(exc).__name__, "attempts": attempts}


def run_probe(source: str, symbol: str, days: int, product_home: str, deadline: float) -> dict:
    command = [sys.executable, str(Path(__file__).resolve()), "--probe", source,
               "--symbols", symbol, "--days", str(days), "--product-home", product_home]
    started = time.perf_counter()
    try:
        result = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True,
                                encoding="utf-8", timeout=deadline,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        # Only this read-only benchmark child is stopped, never the market client.
        return {"status": "timeout", "seconds": None, "deadline_seconds": deadline,
                "process_wall_seconds": time.perf_counter() - started}
    if result.returncode:
        return {"status": "worker_failed", "seconds": None, "exit_code": result.returncode}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "invalid_worker_output", "seconds": None}
    value["process_wall_seconds"] = time.perf_counter() - started
    return value


def cached_sample(symbol: str, days: int):
    import pandas as pd
    from app.config import settings

    path = settings.database_path.resolve()
    if not path.is_file():
        return pd.DataFrame()
    # URI read-only prevents accidental creation; query_only adds defense in depth.
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        aliases = (symbol[:6], symbol, symbol[-2:] + symbol[:6])
        available = {row[0] for row in connection.execute(
            "SELECT DISTINCT symbol FROM daily_bar_cache WHERE symbol IN (?, ?, ?) "
            "AND trade_date != 'ERROR'", aliases)}
        selected = next((alias for alias in aliases if alias in available), None)
        if selected is None:
            return pd.DataFrame()
        # Different historical symbol spellings are separate cache series. Do
        # not merge aliases into artificial duplicate dates before LIMIT.
        frame = pd.read_sql_query(
            "SELECT trade_date AS date,open,high,low,close,volume,amount,source,"
            "adjustment_mode,volume_unit,quality_status,updated_at FROM daily_bar_cache "
            "WHERE symbol = ? AND trade_date != 'ERROR' "
            "ORDER BY trade_date DESC LIMIT ?", connection,
            params=(selected, days))
    frame.attrs["selected_cache_symbol"] = selected
    frame.attrs["symbol"] = symbol
    for key in ("source", "adjustment_mode", "volume_unit"):
        values = frame[key].dropna().unique() if key in frame else []
        frame.attrs[key] = str(values[0]) if len(values) == 1 else "mixed_or_unknown"
    if frame.attrs.get("source") in {"akshare.stock_zh_a_daily", "akshare.stock_zh_a_hist"}:
        frame.attrs["amount_unit"] = "yuan"
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Perform bounded read-only requests.")
    parser.add_argument("--symbols", nargs="+", default=["600519.SH", "000001.SZ", "300750.SZ"])
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--deadline", type=float, default=40)
    parser.add_argument("--product-home", default=os.environ.get("TONGHUASUN_AGENT_HOME", ""))
    parser.add_argument("--output", type=Path, help="New summary JSON under the repo's ignored output directory.")
    parser.add_argument("--probe", choices=SOURCES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    import re
    if not 1 <= args.days <= 500 or not 1 <= args.rounds <= 3 or not 1 <= len(args.symbols) <= 6:
        parser.error("Bounded to 1-500 days, 1-3 rounds and 1-6 symbols.")
    if not 10 <= args.deadline <= 60 or any(not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", s) for s in args.symbols):
        parser.error("Use canonical stock codes and a 10-60 second child deadline.")
    if args.probe:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = probe(args.probe, args.symbols[0], args.days, args.product_home)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    plan = {"symbols": args.symbols, "requested_bars": args.days, "rounds": args.rounds,
            "sources": SOURCES, "sina_rounds": 1, "writes_market_database": False,
            "timing": "current retrieval implementation excluding imports/normalization/DB writes; legacy includes primary failure and fallback; AKShare/Sina fetch full history while THS/Tencent request bounded bars",
            "cached_comparison": "existing rows are read-only snapshots, not a live-source latency baseline"}
    if not args.run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if not args.product_home:
        parser.error("Explicit --product-home or process TONGHUASUN_AGENT_HOME is required.")
    target = None
    if args.output:
        allowed_root = (BACKEND.parent / "output").resolve()
        target = args.output.resolve()
        if not target.is_relative_to(allowed_root) or target.suffix != ".json" or target.exists():
            parser.error("Output must be a new .json below repository output/.")
    import pandas as pd
    from app.data.source_comparison import normalize_frame, profile_frame, compare_frames
    as_of = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    report = {"plan": plan, "as_of": as_of, "started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "runs": [], "comparisons": [], "cached_profiles": []}
    first_frames = {}
    for round_index in range(args.rounds):
        for symbol in args.symbols:
            order = ["tonghuasun", "legacy_chain"]
            if (round_index + args.symbols.index(symbol)) % 2:
                order.reverse()
            for source in order:
                result = run_probe(source, symbol, args.days, args.product_home, args.deadline)
                row = {"source": source, "symbol": symbol, "round": round_index + 1, **result}
                raw = row.pop("frame", None)
                if raw:
                    frame = pd.DataFrame(raw["data"], columns=raw["columns"])
                    frame.attrs.update(row["attributes"])
                    frame.attrs["symbol"] = symbol
                    normalized = normalize_frame(frame, days=args.days, as_of=as_of, request_adjustment="qfq")
                    row["profile"] = profile_frame(normalized)
                    first_frames.setdefault((source, symbol), normalized)
                report["runs"].append(row)
                print(json.dumps({key: row.get(key) for key in ("source", "symbol", "round", "status", "seconds", "attempts")}, ensure_ascii=False), flush=True)
    for symbol in args.symbols:
        source = "sina_reference"
        result = run_probe(source, symbol, args.days, args.product_home, args.deadline)
        raw = result.pop("frame", None)
        if raw:
            frame = pd.DataFrame(raw["data"], columns=raw["columns"])
            frame.attrs.update(result["attributes"])
            frame.attrs["symbol"] = symbol
            normalized = normalize_frame(frame, days=args.days, as_of=as_of, request_adjustment="qfq")
            result["profile"] = profile_frame(normalized)
            first_frames[(source, symbol)] = normalized
        report["runs"].append({"source": source, "symbol": symbol, "round": 1, **result})
        print(json.dumps({"source": source, "symbol": symbol, "status": result["status"], "seconds": result.get("seconds")}), flush=True)
        cached = cached_sample(symbol, args.days)
        if not cached.empty:
            normalized = normalize_frame(cached, days=args.days, as_of=as_of)
            first_frames[("existing_cache", symbol)] = normalized
            report["cached_profiles"].append({"symbol": symbol, "selected_cache_symbol": cached.attrs["selected_cache_symbol"], "profile": profile_frame(normalized)})
        for other in ("legacy_chain", "sina_reference", "existing_cache"):
            left, right = first_frames.get(("tonghuasun", symbol)), first_frames.get((other, symbol))
            if left is not None and right is not None:
                report["comparisons"].append({"symbol": symbol, "left_source": "tonghuasun", "right_source": other, **compare_frames(left, right)})
    report["latency_summary"] = []
    for source in SOURCES:
        runs = [row for row in report["runs"] if row["source"] == source]
        times = [row["seconds"] for row in runs if row["status"] == "success"]
        report["latency_summary"].append({"source": source, "attempted": len(runs), "successes": len(times),
                                           "median_seconds": statistics.median(times) if times else None,
                                           "min_seconds": min(times) if times else None, "max_seconds": max(times) if times else None})
    report["finished_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, allow_nan=False, indent=2)
        print(json.dumps({"summary_path": str(target), "latency_summary": report["latency_summary"]}, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
