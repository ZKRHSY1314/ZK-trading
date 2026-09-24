"""Pure, in-memory checks for small daily-bar source acceptance samples.

No requests, database access, cache writes, or trading actions occur here.
Matching requested adjustments is not proof of the vendor's actual adjustment.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


ALIASES = {
    "date": ("date", "日期"),
    "open": ("open", "开盘"),
    "high": ("high", "最高"),
    "low": ("low", "最低"),
    "close": ("close", "收盘"),
    "volume": ("volume", "成交量"),
    "amount": ("amount", "成交额"),
}
PRICES = ("open", "high", "low", "close")
NUMERIC = (*PRICES, "volume", "amount")
_AUDIT = "_source_comparison"
_KNOWN_ADJUSTMENTS = {"qfq", "hfq", "none"}
_METADATA = (
    "source",
    "adjustment_mode",
    "request_adjustment",
    "volume_unit",
    "amount_unit",
    "symbol",
)


def _date(value: Any) -> pd.Timestamp:
    """Interpret numeric YYYYMMDD as dates, never epoch nanoseconds."""
    try:
        if value is None or pd.isna(value):
            return pd.NaT
        if isinstance(value, (int, float)):
            if not math.isfinite(value) or int(value) != value:
                return pd.NaT
            value = str(int(value))
            if len(value) != 8:
                return pd.NaT
        parsed = pd.Timestamp(value)
        if pd.isna(parsed):
            return pd.NaT
        if parsed.tzinfo is not None:
            parsed = parsed.tz_convert("Asia/Shanghai").tz_localize(None)
        return parsed.normalize()
    except (TypeError, ValueError, OverflowError):
        return pd.NaT


def _mode(value: Any) -> str:
    name = str(value).strip().lower() if value is not None else "unknown"
    return name if name in _KNOWN_ADJUSTMENTS else "unknown"


def _unit(value: Any, quantity: str) -> str:
    name = str(value).strip().lower() if value is not None else "unknown"
    aliases = {
        "volume": {
            "share": "shares",
            "shares": "shares",
            "股": "shares",
            "lot": "lots",
            "lots": "lots",
            "hand": "lots",
            "hands": "lots",
            "手": "lots",
        },
        "amount": {"yuan": "cny", "rmb": "cny", "cny": "cny", "元": "cny"},
    }
    # Matching arbitrary strings (e.g. mixed_or_unknown) cannot certify a unit.
    return aliases[quantity].get(name, "unknown")


def _finite_number(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def _iso_dates(dates) -> list[str]:
    return [date.date().isoformat() for date in sorted(dates)]


def normalize_frame(
    frame: pd.DataFrame,
    days: int = 120,
    as_of: str | None = None,
    *,
    request_adjustment: str | None = None,
) -> pd.DataFrame:
    """Normalize aliases without deleting, filling, or repairing original rows.

    ``days`` selects the most recent N unique valid dates <= ``as_of``;
    duplicates on those dates remain visible. Every original row is retained,
    and ``_in_window`` identifies the comparison sample. Source metadata is
    copied, not invented. An explicit adjustment records the caller's request
    only, and conflicts with existing known metadata block price comparison.
    """
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("days must be a positive integer")
    end = (
        _date(as_of)
        if as_of is not None
        else pd.Timestamp.now("Asia/Shanghai").tz_localize(None).normalize()
    )
    if pd.isna(end):
        raise ValueError("as_of must be a valid date")
    out = pd.DataFrame(index=range(len(frame)))
    missing_columns, ambiguous_columns = [], []
    input_missing, invalid_numeric = {}, {}
    for name, aliases in ALIASES.items():
        positions = [i for i, column in enumerate(frame.columns) if column in aliases]
        if not positions:
            missing_columns.append(name)
            values = pd.Series([None] * len(frame), dtype=object)
        else:
            if len(positions) > 1:
                ambiguous_columns.append(name)
            values = frame.iloc[:, positions[0]].reset_index(drop=True)
        input_missing[name] = int(values.isna().sum())
        if name == "date":
            out[name] = pd.to_datetime(values.map(_date), errors="coerce")
        else:
            out[name] = pd.to_numeric(values, errors="coerce").astype(float)
            invalid_numeric[name] = int((out[name].isna() & values.notna()).sum())

    dates = out.loc[out["date"].notna() & (out["date"] <= end), "date"]
    window_dates = sorted(dates.unique())[-days:]
    out["_in_window"] = out["date"].isin(window_dates)
    out.attrs = {key: frame.attrs[key] for key in _METADATA if key in frame.attrs}
    modes = [_mode(frame.attrs.get(key)) for key in ("request_adjustment", "adjustment_mode")]
    if request_adjustment is not None:
        modes.append(_mode(request_adjustment))
        out.attrs["request_adjustment"] = _mode(request_adjustment)
    elif "request_adjustment" not in out.attrs:
        out.attrs["request_adjustment"] = _mode(frame.attrs.get("adjustment_mode"))
    out.attrs[_AUDIT] = {
        "days": days,
        "as_of": end.date().isoformat(),
        "missing_columns": missing_columns,
        "ambiguous_columns": ambiguous_columns,
        "input_missing_values": input_missing,
        "invalid_numeric_values": invalid_numeric,
        "adjustment_metadata_conflict": len(set(modes) - {"unknown"}) > 1,
    }
    return out


def _normalized(frame: pd.DataFrame) -> pd.DataFrame:
    return frame if _AUDIT in frame.attrs and "_in_window" in frame else normalize_frame(frame)


def _masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    finite = frame[list(NUMERIC)].apply(lambda series: series.map(math.isfinite))
    finite_prices = finite[list(PRICES)].all(axis=1)
    invalid_ohlc = finite_prices & (
        (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
        | (frame["low"] > frame[["open", "close"]].min(axis=1))
    )
    duplicate = frame["date"].notna() & frame["date"].duplicated(keep=False)
    future = frame["date"] > pd.Timestamp(frame.attrs[_AUDIT]["as_of"])
    invalid_price = ~finite_prices | (frame[list(PRICES)] <= 0).any(axis=1) | invalid_ohlc
    invalid = (
        frame["date"].isna()
        | duplicate
        | future
        | ~finite.all(axis=1)
        | invalid_price
        | (frame[["volume", "amount"]] < 0).any(axis=1)
    )
    return {
        "duplicate": duplicate,
        "future": future,
        "invalid_ohlc": invalid_ohlc,
        "invalid_price": invalid_price,
        "invalid": invalid,
    }


def _date_range(series: pd.Series) -> tuple[str | None, str | None]:
    valid = series.dropna()
    if valid.empty:
        return None, None
    return valid.min().date().isoformat(), valid.max().date().isoformat()


def profile_frame(frame: pd.DataFrame) -> dict[str, Any]:
    """Return JSON-safe full-input and selected-window quality evidence."""
    f = _normalized(frame)
    audit, masks = f.attrs[_AUDIT], _masks(f)
    window = f["_in_window"]
    date_min, date_max = _date_range(f["date"])
    window_min, window_max = _date_range(f.loc[window, "date"])
    invalid_count = int(masks["invalid"].sum())
    metadata_issue = bool(
        audit["missing_columns"]
        or audit["ambiguous_columns"]
        or audit["adjustment_metadata_conflict"]
    )
    return {
        "source": str(f.attrs.get("source", "unknown")),
        "request_adjustment": _mode(f.attrs.get("request_adjustment")),
        "adjustment_evidence": "request_metadata_only_not_actual_adjustment_verification",
        "volume_unit": _unit(f.attrs.get("volume_unit"), "volume"),
        "amount_unit": _unit(f.attrs.get("amount_unit"), "amount"),
        **audit,
        "rows": len(f),
        "window_rows": int(window.sum()),
        "unique_dates": int(f["date"].nunique()),
        "window_unique_dates": int(f.loc[window, "date"].nunique()),
        "date_min": date_min,
        "date_max": date_max,
        "window_date_min": window_min,
        "window_date_max": window_max,
        "missing_values": {name: int(f[name].isna().sum()) for name in ALIASES},
        "window_missing_values": {name: int(f.loc[window, name].isna().sum()) for name in ALIASES},
        "infinite_values": {name: int(f[name].map(math.isinf).sum()) for name in NUMERIC},
        "negative_values": {name: int((f[name] < 0).sum()) for name in NUMERIC},
        "non_positive_price_values": {name: int((f[name] <= 0).sum()) for name in PRICES},
        "invalid_dates": int(f["date"].isna().sum()),
        "duplicate_date_rows": int(masks["duplicate"].sum()),
        "duplicate_dates": int(f.loc[masks["duplicate"], "date"].nunique()),
        "future_date_rows": int(masks["future"].sum()),
        "ohlc_invalid_rows": int(masks["invalid_ohlc"].sum()),
        "invalid_rows": invalid_count,
        "window_invalid_rows": int((masks["invalid"] & window).sum()),
        "quality_status": (
            "no_data"
            if f.empty
            else "review_required"
            if invalid_count or metadata_issue
            else "structurally_valid"
        ),
        "window_quality_status": (
            "no_data"
            if not window.any()
            else "review_required"
            if (masks["invalid"] & window).any() or metadata_issue
            else "structurally_valid"
        ),
    }


def compare_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    price_tolerance: float = 0.011,
) -> dict[str, Any]:
    """Compare dated samples, not a claim that either source is ground truth.

    Bad/duplicate price rows cannot enter comparisons. Unknown/different request
    adjustment modes block numerical equivalence. Unit observations never infer
    a confirmed unit or convert unknown units. Amount/volume equality uses only
    a tiny numerical tolerance, not the RMB price tolerance.
    """
    if not math.isfinite(price_tolerance) or not 0 <= price_tolerance <= 0.011:
        raise ValueError("price_tolerance must be between 0 and 0.011 RMB")
    left_frame, right_frame = _normalized(left), _normalized(right)
    lp, rp = profile_frame(left_frame), profile_frame(right_frame)
    lm, rm = _masks(left_frame), _masks(right_frame)
    ld = set(left_frame.loc[left_frame["_in_window"], "date"])
    rd = set(right_frame.loc[right_frame["_in_window"], "date"])
    reasons = []
    if "unknown" in {lp["request_adjustment"], rp["request_adjustment"]}:
        reasons.append("unknown_request_adjustment")
    elif lp["request_adjustment"] != rp["request_adjustment"]:
        reasons.append("different_request_adjustment")
    if lp["adjustment_metadata_conflict"] or rp["adjustment_metadata_conflict"]:
        reasons.append("conflicting_adjustment_metadata")
    if lp["ambiguous_columns"] or rp["ambiguous_columns"]:
        reasons.append("ambiguous_column_aliases")
    if (
        left_frame.attrs.get("symbol")
        and right_frame.attrs.get("symbol")
        and left_frame.attrs["symbol"] != right_frame.attrs["symbol"]
    ):
        reasons.append("different_security_metadata")
    good_l = left_frame["_in_window"] & ~lm["duplicate"] & ~lm["invalid_price"]
    good_r = right_frame["_in_window"] & ~rm["duplicate"] & ~rm["invalid_price"]
    paired = left_frame.loc[good_l].merge(
        right_frame.loc[good_r], on="date", suffixes=("_left", "_right")
    )
    result: dict[str, Any] = {
        "left": lp,
        "right": rp,
        "overlap_dates": _iso_dates(ld & rd),
        "overlap_count": len(ld & rd),
        "left_only_dates": _iso_dates(ld - rd),
        "right_only_dates": _iso_dates(rd - ld),
        "complete_date_coverage": bool(ld and rd and ld == rd),
        "price_tolerance_rmb": price_tolerance,
        "price_comparison": {"status": "not_comparable", "reasons": reasons},
        "quantity_comparison": {},
        "caveats": [
            "Matching requested adjustment is not verification of actual adjustment.",
            "Agreement between sources is not independent proof of accuracy.",
            "Missing dates are coverage gaps, not automatically missing trading sessions.",
            "Security identity must also be checked by the caller/provider.",
        ],
    }
    if reasons:
        return result
    if paired.empty:
        result["price_comparison"] = {"status": "no_overlap", "compared_rows": 0}
        return result
    field_differences = {}
    mismatched = pd.Series(False, index=paired.index)
    for name in PRICES:
        differences = (paired[f"{name}_left"] - paired[f"{name}_right"]).abs()
        # A numerical epsilon prevents a one-cent difference failing due to IEEE rounding.
        mismatch = differences > price_tolerance + 1e-10
        mismatched |= mismatch
        field_differences[name] = {
            "max_absolute_difference_rmb": _finite_number(differences.max()),
            "difference_overflow_rows": int(differences.map(math.isinf).sum()),
            "mismatched_rows": int(mismatch.sum()),
        }
    result["price_comparison"] = {
        "status": "compared",
        "basis": "same_known_request_adjustment_not_vendor_certified",
        "compared_rows": len(paired),
        "excluded_overlap_dates": _iso_dates((ld & rd) - set(paired["date"])),
        "within_tolerance": not bool(mismatched.any()),
        "mismatched_dates": _iso_dates(set(paired.loc[mismatched, "date"])),
        "fields": field_differences,
    }
    for name in ("volume", "amount"):
        unit_l, unit_r = lp[f"{name}_unit"], rp[f"{name}_unit"]
        lv, rv = paired[f"{name}_left"], paired[f"{name}_right"]
        valid = lv.map(math.isfinite) & rv.map(math.isfinite) & (lv >= 0) & (rv >= 0)
        ratios = lv[valid & (rv > 0)] / rv[valid & (rv > 0)]
        quantities: dict[str, Any] = {
            "left_unit": unit_l,
            "right_unit": unit_r,
            "valid_paired_rows": int(valid.sum()),
            "status": "unknown_units" if "unknown" in {unit_l, unit_r} else "different_units",
            "equivalent": None,
            "observed_left_over_right_ratio_median": (
                _finite_number(ratios.median()) if len(ratios) else None
            ),
            "non_finite_ratio_rows": int((~ratios.map(math.isfinite)).sum()),
            "ratio_evidence": "observation_only_not_unit_verification",
        }
        if unit_l == unit_r != "unknown":
            differences = (lv[valid] - rv[valid]).abs()
            quantities.update(
                status="compared" if valid.any() else "no_valid_pairs",
                equivalent=(
                    bool((differences <= 1e-8 + rv[valid].abs() * 1e-9).all())
                    if valid.all() and len(valid)
                    else None
                ),
                max_absolute_difference=(
                    _finite_number(differences.max()) if len(differences) else None
                ),
            )
        result["quantity_comparison"][name] = quantities
    return result
