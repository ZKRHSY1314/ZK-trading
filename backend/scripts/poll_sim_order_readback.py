import argparse
import json
import time
import urllib.request
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "http://127.0.0.1:8000"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "backend" / "logs" / "sim_cockpit_order_poll.jsonl"
CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
TRADING_WINDOWS = (
    (datetime_time(9, 30), datetime_time(11, 30)),
    (datetime_time(13, 0), datetime_time(15, 0)),
)


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 180) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_health(api_base: str) -> dict[str, Any]:
    health = request_json("GET", f"{api_base}/health", timeout=10)
    if health.get("live_trading_enabled") is not False:
        raise RuntimeError(f"live trading must stay disabled: {health}")
    return health


def latest_verification_id(api_base: str) -> int:
    request_json("GET", f"{api_base}/api/sim-cockpit/window-detection?record=true", timeout=45)
    status = request_json("GET", f"{api_base}/api/sim-cockpit/status", timeout=20)
    verification = status.get("latest_verification") or {}
    if verification.get("status") != "verified":
        raise RuntimeError(f"simulation window is not verified: {verification}")
    if verification.get("live_trading_enabled"):
        raise RuntimeError(f"verified window reported live trading enabled: {verification}")
    return int(verification["id"])


def screen_readback(api_base: str, verification_id: int, args: argparse.Namespace, readback_type: str) -> dict[str, Any]:
    payload = {
        "action_id": args.action_id,
        "readback_type": readback_type,
        "symbol": args.symbol,
        "price": args.price,
        "quantity": args.quantity,
        "order_id": args.order_id,
        "window_verification_id": verification_id,
        "screen_confirmation": "SIMULATION_SCREEN_CLICK",
        "recorded_by": "poll_sim_order_readback",
        "note": "automated pending/fill/position follow-up for simulated screen order",
    }
    return request_json("POST", f"{api_base}/api/sim-cockpit/screen-readback", payload=payload, timeout=60)


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload") or {}
    screen = payload.get("screen_readback") or {}
    interpretation = screen.get("interpretation") or {}
    return {
        "id": result.get("id"),
        "readback_type": result.get("readback_type"),
        "status": result.get("status"),
        "screen_status": screen.get("status"),
        "matched": interpretation.get("matched") or {},
        "requires_visual_or_ocr_review": interpretation.get("requires_visual_or_ocr_review") is True,
        "limitation": interpretation.get("limitation"),
        "post_screenshot": (screen.get("post_readback_screenshot") or {}).get("artifact_ref"),
    }


def append_log(record: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def market_session(now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(CHINA_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=CHINA_TZ)
    local = current.astimezone(CHINA_TZ)
    weekday = local.weekday()
    is_weekend = weekday >= 5
    current_time = local.time()
    in_window = (not is_weekend) and any(start <= current_time <= end for start, end in TRADING_WINDOWS)
    if is_weekend:
        reason = "weekend_closed"
        status = "closed"
    elif current_time < TRADING_WINDOWS[0][0]:
        reason = "before_morning_session"
        status = "pre_open"
    elif TRADING_WINDOWS[0][1] < current_time < TRADING_WINDOWS[1][0]:
        reason = "midday_break"
        status = "break"
    elif current_time > TRADING_WINDOWS[1][1]:
        reason = "after_close"
        status = "closed"
    else:
        reason = "trading_window_open" if in_window else "outside_trading_window"
        status = "open" if in_window else "closed"
    return {
        "schema_version": "cn_a_share_market_session.v1",
        "status": status,
        "is_open": in_window,
        "reason": reason,
        "checked_at": local.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "trading_windows": [
            {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")} for start, end in TRADING_WINDOWS
        ],
        "holiday_calendar_loaded": False,
        "holiday_calendar_note": "Weekend and intraday session guard only; official holiday overrides are not configured.",
    }


def classify_poll_status(results: list[dict[str, Any]], session: dict[str, Any]) -> str:
    statuses = {item["readback_type"]: item["status"] for item in results}
    if statuses.get("screen_today_trades") == "fill_detected" or statuses.get("screen_positions") == "position_detected":
        return "filled_or_position_detected"
    if statuses.get("screen_today_orders") == "pending_order_detected":
        if session.get("is_open"):
            return "pending_order_detected"
        return "pending_order_waiting_for_market_session"
    if any(item.get("requires_visual_or_ocr_review") for item in results):
        return "screen_table_unparsed"
    if not session.get("is_open"):
        return "waiting_for_market_session"
    return "no_fill_or_position_detected"


def poll(args: argparse.Namespace) -> dict[str, Any]:
    health = ensure_health(args.api_base)
    attempts: list[dict[str, Any]] = []
    final_status = "not_finished"
    for attempt in range(1, args.attempts + 1):
        session = market_session()
        verification_id = latest_verification_id(args.api_base)
        results = [
            compact_result(screen_readback(args.api_base, verification_id, args, "today_orders")),
            compact_result(screen_readback(args.api_base, verification_id, args, "today_trades")),
            compact_result(screen_readback(args.api_base, verification_id, args, "positions")),
        ]
        final_status = classify_poll_status(results, session)
        attempt_record = {
            "attempt": attempt,
            "recorded_at": datetime.now(CHINA_TZ).isoformat(timespec="seconds"),
            "verification_id": verification_id,
            "results": results,
            "status": final_status,
            "market_session": session,
            "simulation_only": True,
            "live_trading_enabled": health.get("live_trading_enabled"),
        }
        attempts.append(attempt_record)
        append_log(attempt_record)
        should_wait_for_market = (
            args.wait_when_closed
            and final_status in {"pending_order_waiting_for_market_session", "waiting_for_market_session"}
            and attempt < args.attempts
        )
        if (
            final_status == "filled_or_position_detected"
            or (
                final_status in {"pending_order_waiting_for_market_session", "waiting_for_market_session"}
                and not should_wait_for_market
            )
            or attempt == args.attempts
        ):
            break
        time.sleep(max(1, args.interval_seconds))
    return {
        "schema_version": "sim_cockpit_order_poll.v1",
        "status": final_status,
        "attempt_count": len(attempts),
        "symbol": args.symbol,
        "order_id": args.order_id,
        "action_id": args.action_id,
        "attempts": attempts,
        "log_path": str(LOG_PATH),
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll simulated screen order readbacks until fill/position evidence appears.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--action-id", type=int, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument(
        "--wait-when-closed",
        action="store_true",
        help="Keep polling through closed market sessions until attempts are exhausted or fill/position evidence appears.",
    )
    args = parser.parse_args()
    print(json.dumps(poll(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
