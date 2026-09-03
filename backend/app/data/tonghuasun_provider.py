r"""Read-only market-data adapter for the local tonghuasun-codex service.

The third-party plugin exposes market, account, and optional trading APIs from
the local Tonghuashun client.  This adapter intentionally implements only one
hard-coded market-data operation: adjusted daily candles.  It does not expose
a generic request method, account data, positions, orders, or trade actions.

The local access token is discovered from the plugin-owned configuration at
``%LOCALAPPDATA%\TonghuasunCodex``.  It is never copied into this project or
included in errors/status output.  Runtime endpoints must resolve to loopback;
LAN and public addresses are rejected even though the upstream plugin can be
configured to publish them.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

import pandas as pd

from app.data.symbols import normalize_a_share_code


SOURCE = "tonghuasun.local.quotes.candle"
TOKEN_HEADER = "X-Tonghuasun-Codex-Token"
DEFAULT_PORT = 17_180
# daily_bar_cache stores volume in 手; the local host reports 股 (verified).
SHARES_PER_HAND = 100.0
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
_ADJUSTMENT_VALUES = {"": 0, "none": 0, "qfq": 1, "hfq": 2}
_CANDLE_FIELDS = (
    "full_code",
    "security_name",
    "open",
    "high",
    "low",
    "latest",
    "transaction_volume",
    "transaction_amount",
    "date_time",
)


class TonghuasunConfigurationError(RuntimeError):
    """The local plugin is absent or its endpoint is unsafe/invalid."""


class TonghuasunDataError(RuntimeError):
    """The local plugin could not return usable market data."""


class _RejectRedirects(HTTPRedirectHandler):
    """Prevent a local service from forwarding the token to another origin."""

    def redirect_request(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        return None


# Loopback credentials must never travel through a configured system/env proxy.
_NO_REDIRECT_OPENER = build_opener(ProxyHandler({}), _RejectRedirects())


def _open_without_redirect(request: Request, *, timeout: float):
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


@dataclass(frozen=True, slots=True)
class TonghuasunConnection:
    base_url: str
    access_token: str = field(repr=False)
    product_home: Path
    plugin_version: str = ""

    def __post_init__(self) -> None:
        # Injected connections must meet the same boundary as discovered ones.
        object.__setattr__(self, "base_url", _validated_loopback_url(self.base_url))

    @classmethod
    def discover(
        cls,
        product_home: str | os.PathLike[str] | None = None,
    ) -> "TonghuasunConnection":
        home = _product_home(product_home)
        config = _read_json(home / "config.json", required=True)
        endpoint = _read_json(home / "runtime" / "endpoint.json", required=False)

        token = str(config.get("localAccessToken") or "").strip()
        if not token:
            raise TonghuasunConfigurationError(
                "local Tonghuashun plugin configuration has no access token"
            )

        base_url = str(endpoint.get("baseUrl") or "").strip()
        if not base_url:
            port = _safe_port(config.get("preferredPort"))
            base_url = f"http://127.0.0.1:{port}"

        return cls(
            base_url=_validated_loopback_url(base_url),
            access_token=token,
            product_home=home,
            plugin_version=str(endpoint.get("pluginVersion") or ""),
        )


class TonghuasunMarketDataProvider:
    """Fetch adjusted daily candles from the local Tonghuashun plugin only."""

    def __init__(
        self,
        connection: TonghuasunConnection | None = None,
        *,
        product_home: str | os.PathLike[str] | None = None,
        timeout: float = 5.0,
        opener: Callable[..., Any] = _open_without_redirect,
    ) -> None:
        self._connection = connection
        self._product_home = product_home
        self.timeout = max(0.1, float(timeout))
        self._opener = opener

    @property
    def connection(self) -> TonghuasunConnection:
        if self._connection is None:
            self._connection = TonghuasunConnection.discover(self._product_home)
        return self._connection

    def status(self) -> dict[str, Any]:
        """Return non-secret discovery state without probing account/trade APIs."""
        try:
            connection = self.connection
        except TonghuasunConfigurationError as exc:
            return {
                "status": "not_configured",
                "source": SOURCE,
                "reason": str(exc),
                "market_data_only": True,
                "loopback_only": True,
            }
        return {
            "status": "configured",
            "source": SOURCE,
            "base_url": connection.base_url,
            "plugin_version": connection.plugin_version or None,
            "market_data_only": True,
            "loopback_only": True,
        }

    def get_daily_bars(
        self,
        symbol: str,
        adjust: str = "qfq",
        *,
        days: int = 500,
    ) -> pd.DataFrame:
        adjustment_name = str(adjust or "").strip().lower()
        if adjustment_name not in _ADJUSTMENT_VALUES:
            raise ValueError(f"unsupported Tonghuashun adjustment mode: {adjust}")
        limit = max(1, min(int(days), 500))
        full_code = tonghuasun_full_code(symbol)
        code = normalize_a_share_code(symbol)
        payload = {
            "market": 1,
            "security": {"market": 1, "code": code, "fullCode": full_code},
            "codes": [full_code],
            "startTimeUtc": None,
            "endTimeUtc": None,
            "limit": limit,
            "fields": list(_CANDLE_FIELDS),
            "period": 7,
            "adjustment": _ADJUSTMENT_VALUES[adjustment_name],
        }
        data = self._post_candles(payload)
        echoed_adjustment = data.get("adjustment")
        if echoed_adjustment is not None:
            try:
                matches_request = int(echoed_adjustment) == payload["adjustment"]
            except (TypeError, ValueError):
                matches_request = False
            if not matches_request:
                raise TonghuasunDataError(
                    "local Tonghuashun candle response has a mismatched adjustment mode"
                )
        frame = _candle_frame(data, expected_full_code=full_code)
        # The host may append the current candle beyond its requested count.
        # Validate every returned row first, then honor our bounded history API.
        frame = frame.tail(limit).reset_index(drop=True)
        frame.attrs["source"] = SOURCE
        frame.attrs["adjustment_mode"] = adjustment_name or "none"
        # 2026-09-03: the open unit question is now settled empirically rather
        # than from the SDK contract. Against 2,260 overlapping days on 40
        # symbols, transaction_volume / cached-hands has median exactly 100 and
        # 99.7% of rows inside +-0.5% of it, so the host reports 股. Everything
        # downstream (execution.py's SHARES_PER_HAND proxy, 量比 in the backtest
        # snapshot) assumes 手, and a symbol whose history mixes units would
        # show a silent 100x jump in 量比 - so convert here and say so.
        if "volume" in frame.columns:
            frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce") / SHARES_PER_HAND
        frame.attrs["volume_unit"] = "hand"
        return frame

    def _post_candles(self, payload: dict[str, Any]) -> dict[str, Any]:
        connection = self.connection
        request = Request(
            connection.base_url + "/api/v2/quotes/candle",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                TOKEN_HEADER: connection.access_token,
                "User-Agent": "a-share-cockpit/tonghuasun-market-data",
            },
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = _read_bounded(response)
                status = int(getattr(response, "status", 200))
        except HTTPError as exc:
            raw = _read_bounded(exc)
            raise TonghuasunDataError(
                _safe_api_error(
                    raw,
                    fallback=f"local Tonghuashun API HTTP {exc.code}",
                    secret=connection.access_token,
                )
            ) from exc
        except (URLError, OSError) as exc:
            reason = getattr(exc, "reason", None) or str(exc)
            raise TonghuasunDataError(
                f"cannot connect to local Tonghuashun market-data service: {reason}"
            ) from exc

        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TonghuasunDataError(
                f"local Tonghuashun API returned invalid JSON (HTTP {status})"
            ) from exc
        if not isinstance(value, dict):
            raise TonghuasunDataError("local Tonghuashun API returned a non-object response")
        if value.get("ok") is False:
            raise TonghuasunDataError(
                _safe_envelope_error(value, secret=connection.access_token)
            )
        data = value.get("data")
        if not isinstance(data, dict):
            raise TonghuasunDataError("local Tonghuashun candle response has no data object")
        return data


def tonghuasun_full_code(symbol: str) -> str:
    code = normalize_a_share_code(symbol)
    raw = str(symbol or "").strip().upper()
    if raw.startswith("BJ") or code.startswith(("4", "8", "92")):
        suffix = "BJ"
    elif raw.startswith("SZ") or code.startswith(("0", "2", "3")):
        suffix = "SZ"
    else:
        suffix = "SH"
    return f"{code}.{suffix}"


def _candle_frame(
    data: dict[str, Any],
    *,
    expected_full_code: str,
) -> pd.DataFrame:
    records_by_date: dict[str, dict[str, Any]] = {}
    items = data.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            _validate_response_security(item.get("security"), expected_full_code)
            points = item.get("points")
            if not isinstance(points, list):
                continue
            for point in points:
                if not isinstance(point, dict):
                    continue
                values = point.get("values")
                if not isinstance(values, dict):
                    continue
                returned_full_code = values.get("full_code")
                if returned_full_code:
                    _validate_response_security(
                        {"fullCode": returned_full_code},
                        expected_full_code,
                    )
                trade_date = _trade_date(
                    values.get("date_time") or point.get("timestampUtc")
                )
                if trade_date is None:
                    continue
                record = _validated_candle_record(trade_date, values)
                existing = records_by_date.get(trade_date)
                if existing is not None and existing != record:
                    raise TonghuasunDataError(
                        f"local Tonghuashun returned conflicting candles for {trade_date}"
                    )
                records_by_date[trade_date] = record
    columns = ["date", "open", "high", "low", "close", "volume", "amount"]
    records = [records_by_date[key] for key in sorted(records_by_date)]
    return pd.DataFrame(records, columns=columns)


def _validate_response_security(value: Any, expected_full_code: str) -> None:
    if not isinstance(value, dict):
        raise TonghuasunDataError(
            "local Tonghuashun candle response is missing security identity"
        )
    returned = str(value.get("fullCode") or value.get("code") or "").strip().upper()
    if not returned:
        raise TonghuasunDataError(
            "local Tonghuashun candle response is missing security identity"
        )
    try:
        returned_code = normalize_a_share_code(returned)
        expected_code = normalize_a_share_code(expected_full_code)
    except ValueError as exc:
        raise TonghuasunDataError(
            "local Tonghuashun candle response has an invalid security identity"
        ) from exc
    if returned_code != expected_code:
        raise TonghuasunDataError(
            "local Tonghuashun candle response returned a different security"
        )
    if returned not in {
        expected_code,
        expected_full_code,
        expected_full_code[-2:] + expected_code,
    }:
        raise TonghuasunDataError(
            "local Tonghuashun candle response returned a different exchange"
        )


def _validated_candle_record(
    trade_date: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    names = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "latest",
        "volume": "transaction_volume",
        "amount": "transaction_amount",
    }
    parsed: dict[str, float] = {}
    for output_name, source_name in names.items():
        try:
            parsed[output_name] = float(values[source_name])
        except (KeyError, TypeError, ValueError) as exc:
            raise TonghuasunDataError(
                f"local Tonghuashun candle {trade_date} has invalid {source_name}"
            ) from exc
    if any(not math.isfinite(value) for value in parsed.values()):
        raise TonghuasunDataError(
            f"local Tonghuashun candle {trade_date} has non-finite values"
        )
    if any(parsed[name] <= 0 for name in ("open", "high", "low", "close")):
        raise TonghuasunDataError(
            f"local Tonghuashun candle {trade_date} has non-positive OHLC"
        )
    if parsed["volume"] < 0 or parsed["amount"] < 0:
        raise TonghuasunDataError(
            f"local Tonghuashun candle {trade_date} has negative volume or amount"
        )
    tolerance = 1e-8
    if (
        parsed["high"] + tolerance < max(parsed["open"], parsed["close"])
        or parsed["low"] - tolerance > min(parsed["open"], parsed["close"])
        or parsed["high"] + tolerance < parsed["low"]
    ):
        raise TonghuasunDataError(
            f"local Tonghuashun candle {trade_date} violates OHLC ordering"
        )
    return {"date": trade_date, **parsed}


def _trade_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(int(value)) if isinstance(value, (int, float)) else str(value).strip()
    digits = "".join(character for character in text if character.isdigit())
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(digits) == 8 and len(text) <= 10:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.tz_convert(ZoneInfo("Asia/Shanghai"))
    return parsed.date().isoformat()


def _product_home(value: str | os.PathLike[str] | None) -> Path:
    if value is not None:
        return Path(value).expanduser().resolve()
    override = (
        os.environ.get("TONGHUASUN_AGENT_HOME", "").strip()
        or os.environ.get("TONGHUASUN_CODEX_HOME", "").strip()
    )
    if override:
        return Path(os.path.expandvars(override)).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        raise TonghuasunConfigurationError(
            "LOCALAPPDATA is unavailable; cannot discover the local Tonghuashun plugin"
        )
    return (Path(local_app_data) / "TonghuasunCodex").resolve()


def _read_json(path: Path, *, required: bool) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if required:
            raise TonghuasunConfigurationError(
                f"local Tonghuashun plugin is not configured: {path}"
            ) from None
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise TonghuasunConfigurationError(
            f"cannot read local Tonghuashun plugin configuration: {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise TonghuasunConfigurationError(
            f"local Tonghuashun plugin configuration is not an object: {path}"
        )
    return value


def _safe_port(value: Any) -> int:
    return value if isinstance(value, int) and 1_024 <= value <= 65_535 else DEFAULT_PORT


def _validated_loopback_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise TonghuasunConfigurationError(
            "local Tonghuashun endpoint has an invalid port"
        ) from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port is None
        or not 1_024 <= port <= 65_535
    ):
        raise TonghuasunConfigurationError(
            "local Tonghuashun endpoint must be an HTTP loopback origin"
        )
    return value.rstrip("/")


def _read_bounded(response: Any) -> bytes:
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise TonghuasunDataError("local Tonghuashun API response exceeds size limit")
    return raw


def _safe_api_error(raw: bytes, *, fallback: str, secret: str = "") -> str:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return fallback
    return (
        _safe_envelope_error(value, secret=secret)
        if isinstance(value, dict)
        else fallback
    )


def _safe_envelope_error(value: dict[str, Any], *, secret: str = "") -> str:
    error = value.get("error")
    details = error if isinstance(error, dict) else {}
    code = str(details.get("code") or error or "api_error")[:80]
    message = str(
        details.get("message") or value.get("message") or "request failed"
    )[:500]
    if secret:
        code = code.replace(secret, "[redacted]")
        message = message.replace(secret, "[redacted]")
    return f"local Tonghuashun API error [{code}]: {message}"
