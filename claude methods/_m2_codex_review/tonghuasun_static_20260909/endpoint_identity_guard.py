"""Pure-data endpoint freshness gate for a future reviewed integration.

This module was created AFTER the 2026-09-10 probe stopped on HTTP 401.
It was not used by that capture, does not change its evidence or authorization,
and does not authorize another request. Passing only establishes the supplied
metadata predicates; the caller must separately establish metadata provenance.

No filesystem/configuration/token reads, network, process discovery, services,
or production imports occur here. All required metadata must be supplied by
the caller. Missing fields fail closed. Outputs never echo supplied data.
"""
from __future__ import annotations

from datetime import datetime, timezone


EXPECTED_BASE_URL = "http://127.0.0.1:17180"
EXPECTED_PORT = 17180
START_EARLIEST_SECONDS = -2.0
START_LATEST_SECONDS = 300.0


def _aware_utc(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError):
            return None
    else:
        return None
    try:
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _positive_pid(value: object) -> bool:
    return type(value) is int and value > 0


def validate_endpoint_identity(
    endpoint: object,
    *,
    current_pid: object,
    host_created_at: object,
    endpoint_mtime: object,
) -> dict[str, object]:
    """Check only supplied endpoint/process/file metadata, with no side effects.

    Timestamps accept timezone-aware datetime objects or ISO 8601 strings.
    The plugin start must be between host creation minus two seconds and plus
    300 seconds, inclusively. File mtime must be at least host creation minus
    two seconds. No upper mtime bound is claimed by this contract.

    Required endpoint keys: baseUrl, port, processId, startedAtUtc,
    listenAddresses, lanBaseUrls. Extra keys are ignored and never returned.
    """
    errors: list[str] = []
    if type(endpoint) is not dict:
        return {"passed": False, "errors": ["endpoint_metadata_not_object"]}

    if endpoint.get("baseUrl") != EXPECTED_BASE_URL:
        errors.append("endpoint_origin_not_exact_loopback")
    if type(endpoint.get("port")) is not int or endpoint["port"] != EXPECTED_PORT:
        errors.append("endpoint_port_invalid")

    endpoint_pid = endpoint.get("processId")
    if not _positive_pid(current_pid):
        errors.append("current_process_id_invalid")
    if not _positive_pid(endpoint_pid):
        errors.append("endpoint_process_id_invalid")
    elif _positive_pid(current_pid) and endpoint_pid != current_pid:
        errors.append("endpoint_process_id_mismatch")

    addresses = endpoint.get("listenAddresses")
    if type(addresses) is not list or addresses != ["127.0.0.1"]:
        errors.append("listen_addresses_not_exact_loopback")
    lan_urls = endpoint.get("lanBaseUrls")
    if type(lan_urls) is not list or lan_urls:
        errors.append("lan_base_urls_not_explicitly_empty")

    host_time = _aware_utc(host_created_at)
    start_time = _aware_utc(endpoint.get("startedAtUtc"))
    mtime = _aware_utc(endpoint_mtime)
    if host_time is None:
        errors.append("host_creation_time_invalid_or_timezone_missing")
    if start_time is None:
        errors.append("endpoint_start_time_invalid_or_timezone_missing")
    if mtime is None:
        errors.append("endpoint_mtime_invalid_or_timezone_missing")

    if host_time is not None and start_time is not None:
        delta = (start_time - host_time).total_seconds()
        if not START_EARLIEST_SECONDS <= delta <= START_LATEST_SECONDS:
            errors.append("endpoint_start_outside_host_start_window")
    if host_time is not None and mtime is not None:
        if (mtime - host_time).total_seconds() < START_EARLIEST_SECONDS:
            errors.append("endpoint_mtime_predates_host_start_window")

    return {"passed": not errors, "errors": errors}
