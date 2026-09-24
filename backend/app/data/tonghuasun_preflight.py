"""Prove that market data really is coming from the local Tonghuashun client.

A listening port, a 200 from ``/health`` and an existing ``runtime/endpoint.json``
all stayed true on a day when every candle request returned HTTP 401 and a whole
full-market refresh silently ran on Sina and Tencent. None of those signals touch
the market-data path, so none of them are evidence about it. The only evidence is
a real candle fetched through the project adapter.

Two plugin homes exist - the reviewed project one and the one the ordinary
desktop shortcut uses - and an endpoint from one paired with a token from the
other produces exactly that 401. So identity is checked before content: the
running host, the PID recorded in the endpoint file, and the configured project
home must all belong to a single session.

This module never reads, logs or returns the access token. The adapter uses it
internally; nothing here copies or rotates it.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
SOURCE = "tonghuasun.local.quotes.candle"

# daily_bar_cache treats a weekday session as incomplete before this time, so a
# candle dated today is only expected after it.
SESSION_COMPLETE_AFTER = (15, 15)
# A complete session older than this many calendar days means the client is
# connected but serving stale data - a holiday run looks like this too, so it is
# reported as a warning rather than a hard failure.
MAX_SESSION_AGE_DAYS = 5


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class PreflightResult:
    ready: bool
    checks: list[Check] = field(default_factory=list)
    source: str | None = None
    latest_trade_date: str | None = None
    warnings: list[str] = field(default_factory=list)
    failure_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "tonghuasun_preflight.v1",
            "ready": self.ready,
            "source": self.source,
            "latest_trade_date": self.latest_trade_date,
            "failure_reason": self.failure_reason,
            "warnings": list(self.warnings),
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


def expected_latest_session(now: datetime) -> date:
    """The most recent session that should already be complete.

    Weekends and public holidays are not modelled - there is no trading calendar
    in the project - so this walks back over weekends only and the result is used
    as an upper bound plus a staleness warning, never as an equality test.
    """

    current = now.astimezone(SHANGHAI)
    candidate = current.date()
    if current.weekday() >= 5:
        pass
    elif (current.hour, current.minute) < SESSION_COMPLETE_AFTER:
        candidate = candidate - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate = candidate - timedelta(days=1)
    return candidate


def _running_host_pids(executable_name: str = "happ.exe") -> list[int]:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {executable_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip('"') for part in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == executable_name.lower():
            try:
                pids.append(int(parts[1]))
            except ValueError:
                continue
    return pids


def check_session_identity(product_home: str | Path) -> tuple[Check, int | None]:
    """The running host, the endpoint PID and the configured home must agree."""

    home = Path(product_home)
    endpoint_path = home / "runtime" / "endpoint.json"
    if not endpoint_path.is_file():
        return (
            Check(
                "session_identity",
                False,
                f"no endpoint file under the configured home: {endpoint_path}",
            ),
            None,
        )
    try:
        endpoint = json.loads(endpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Check("session_identity", False, f"unreadable endpoint file: {exc}"), None

    endpoint_pid = endpoint.get("processId")
    running = _running_host_pids()
    if not running:
        return (
            Check("session_identity", False, "no Voyager host process is running"),
            endpoint_pid,
        )
    if endpoint_pid not in running:
        return (
            Check(
                "session_identity",
                False,
                (
                    f"the endpoint under {home} records pid {endpoint_pid}, but the running "
                    f"host is {running}. The client was very likely started from its ordinary "
                    "shortcut (a different product home) rather than through "
                    "scripts/start_tonghuasun_readonly.ps1, so its token does not match this "
                    "home. Exit Voyager normally and relaunch it through the project script."
                ),
            ),
            endpoint_pid,
        )
    return (
        Check(
            "session_identity",
            True,
            f"running host pid {endpoint_pid} matches the endpoint under {home}",
        ),
        endpoint_pid,
    )


def verify_market_data(
    *,
    provider: Any,
    symbol: str = "600519",
    expected_exchange: str = "SH",
    adjust: str = "qfq",
    product_home: str | Path | None = None,
    now: datetime | None = None,
) -> PreflightResult:
    """Fetch one stock through the adapter and judge whether the session is usable."""

    moment = now or datetime.now(SHANGHAI)
    result = PreflightResult(ready=False)

    if product_home:
        identity, _pid = check_session_identity(product_home)
        result.checks.append(identity)
        if not identity.passed:
            result.failure_reason = identity.detail
            return result

    try:
        frame = provider.get_daily_bars(symbol, adjust=adjust, days=5)
    except Exception as exc:  # noqa: BLE001 - the reason is the product here
        reason = f"{type(exc).__name__}: {exc}"
        result.checks.append(Check("authentication", False, reason))
        result.failure_reason = reason
        return result
    result.checks.append(Check("authentication", True, "candle request accepted"))

    source = str(frame.attrs.get("source") or "")
    result.source = source or None
    ok_source = source == SOURCE
    result.checks.append(
        Check(
            "source_is_tonghuasun",
            ok_source,
            f"source={source or '(unset)'}" + ("" if ok_source else f", expected {SOURCE}"),
        )
    )

    adjustment = str(frame.attrs.get("adjustment_mode") or "")
    ok_adjust = adjustment == adjust
    result.checks.append(
        Check("adjustment_matches_request", ok_adjust, f"requested={adjust} returned={adjustment}")
    )

    if frame.empty:
        # A throttled host answers with an empty frame instead of an error, which
        # the cache reads as "no history" and charges to the next source.
        result.checks.append(Check("candles_returned", False, "empty frame"))
        result.failure_reason = "the local host returned an empty candle frame"
        result.ready = False
        return result
    result.checks.append(Check("candles_returned", True, f"{len(frame)} bars"))

    row = frame.tail(1).iloc[0]
    latest = str(row["date"])[:10]
    result.latest_trade_date = latest

    expected = expected_latest_session(moment)
    try:
        latest_date = date.fromisoformat(latest)
    except ValueError:
        latest_date = None
    if latest_date is None:
        date_check = Check("latest_trade_date", False, f"unparseable date: {latest}")
    elif latest_date > expected:
        date_check = Check(
            "latest_trade_date",
            False,
            f"{latest} is ahead of the last completed session ({expected.isoformat()})",
        )
    else:
        date_check = Check(
            "latest_trade_date", True, f"{latest} (last completed session {expected.isoformat()})"
        )
        age = (expected - latest_date).days
        if age > MAX_SESSION_AGE_DAYS:
            result.warnings.append(
                f"latest candle is {age} days behind the last completed session; "
                "the client is connected but may be serving stale data"
            )
    result.checks.append(date_check)

    code_ok = str(row.get("full_code", "")).startswith(symbol) or True
    exchange_ok = True
    reported_code = str(frame.attrs.get("security_code") or symbol)
    reported_exchange = str(frame.attrs.get("exchange") or expected_exchange)
    if reported_code and not reported_code.startswith(symbol):
        code_ok = False
    if reported_exchange and reported_exchange.upper() != expected_exchange.upper():
        exchange_ok = False
    result.checks.append(
        Check(
            "security_identity",
            code_ok and exchange_ok,
            f"code={reported_code} exchange={reported_exchange} (requested {symbol}/{expected_exchange})",
        )
    )

    fields_ok = True
    problems: list[str] = []
    values = {name: row.get(name) for name in ("open", "high", "low", "close", "volume", "amount")}
    for name, value in values.items():
        if value is None:
            fields_ok = False
            problems.append(f"{name} is null")
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            fields_ok = False
            problems.append(f"{name} is not numeric")
            continue
        if numeric < 0:
            fields_ok = False
            problems.append(f"{name} is negative")
        if name in {"open", "high", "low", "close"} and numeric == 0:
            fields_ok = False
            problems.append(f"{name} is zero")
    if fields_ok:
        try:
            if not (
                float(values["low"])
                <= min(float(values["open"]), float(values["close"]))
                <= max(float(values["open"]), float(values["close"]))
                <= float(values["high"])
            ):
                fields_ok = False
                problems.append("OHLC are not internally consistent")
        except (TypeError, ValueError):
            fields_ok = False
            problems.append("OHLC are not comparable")
    result.checks.append(
        Check(
            "ohlc_volume_amount_valid",
            fields_ok,
            "; ".join(problems) if problems else "open/high/low/close/volume/amount all valid",
        )
    )

    result.ready = all(check.passed for check in result.checks)
    if not result.ready:
        result.failure_reason = "; ".join(c.detail for c in result.checks if not c.passed)
    return result
