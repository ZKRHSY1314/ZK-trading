from __future__ import annotations

import json

import pandas as pd
import pytest

from app.data.source_comparison import compare_frames, normalize_frame, profile_frame


def bars(dates=("2026-09-01", "2026-09-02", "2026-09-03"), **attrs):
    frame = pd.DataFrame(
        [
            {
                "date": date,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100.0,
                "amount": 1050.0,
            }
            for date in dates
        ]
    )
    frame.attrs.update(source="synthetic", **attrs)
    return frame


def norm(frame, **kwargs):
    return normalize_frame(frame, as_of="2026-09-03", **kwargs)


def test_aliases_metadata_and_input_are_preserved_without_filling():
    original = bars(adjustment_mode="qfq", volume_unit="shares")
    original = original.rename(
        columns={
            "date": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
            "amount": "成交额",
        }
    )
    original.loc[0, "成交量"] = None
    before = original.copy(deep=True)
    frame = norm(original)
    pd.testing.assert_frame_equal(before, original)
    assert pd.isna(frame.loc[0, "volume"])
    assert frame.attrs["source"] == "synthetic"
    assert frame.attrs["request_adjustment"] == "qfq"
    assert frame.attrs["volume_unit"] == "shares"
    assert profile_frame(frame)["missing_values"]["volume"] == 1


def test_days_are_unique_bar_dates_not_calendar_days_and_rows_are_never_dropped():
    frame = bars(("2026-08-20", "2026-08-31", "2026-09-03", "2026-09-03", "bad", "2026-09-04"))
    frame.loc[0, "amount"] = -1
    frame = norm(frame, days=2)
    profile = profile_frame(frame)
    assert len(frame) == 6
    assert frame["_in_window"].tolist() == [False, True, True, True, False, False]
    assert profile["window_unique_dates"] == 2
    assert profile["invalid_dates"] == 1
    assert profile["duplicate_date_rows"] == 2
    assert profile["future_date_rows"] == 1
    assert profile["negative_values"]["amount"] == 1
    assert profile["invalid_rows"] == 5
    assert profile["quality_status"] == "review_required"


def test_turnover_is_not_amount_and_missing_values_are_not_zero():
    frame = bars().drop(columns="amount")
    frame["turnover"] = 8.5
    frame = norm(frame)
    assert frame["amount"].isna().all()
    assert profile_frame(frame)["missing_columns"] == ["amount"]
    assert profile_frame(frame)["quality_status"] == "review_required"


def test_window_quality_is_separate_from_older_full_history_defects():
    frame = bars(("2020-01-01", "2026-09-01", "2026-09-02", "2026-09-03"))
    frame.loc[0, "amount"] = None
    profile = profile_frame(norm(frame, days=3))
    assert profile["quality_status"] == "review_required"
    assert profile["missing_values"]["amount"] == 1
    assert profile["window_quality_status"] == "structurally_valid"
    assert profile["window_missing_values"]["amount"] == 0
    assert profile["window_invalid_rows"] == 0


def test_invalid_numeric_values_ohlc_nonpositive_and_infinity_are_reported():
    frame = bars()
    frame["open"] = frame["open"].astype(object)
    frame.loc[0, "open"] = "nonsense"
    frame.loc[1, "high"] = 8
    frame.loc[2, "close"] = 0
    frame.loc[2, "volume"] = float("inf")
    profile = profile_frame(norm(frame))
    assert profile["invalid_numeric_values"]["open"] == 1
    assert profile["infinite_values"]["volume"] == 1
    assert profile["ohlc_invalid_rows"] == 2
    assert profile["non_positive_price_values"]["close"] == 1
    assert profile["invalid_rows"] == 3
    json.dumps(profile, allow_nan=False)


@pytest.mark.parametrize(
    "value, expected",
    [
        (20260903, "2026-09-03"),
        (20260903.0, "2026-09-03"),
        ("2026-09-02T16:00:00Z", "2026-09-03"),
        ("20260230", None),
        (123, None),
        (["not", "a", "date"], None),
    ],
)
def test_date_parsing_is_calendar_aware(value, expected):
    frame = norm(bars((value,)))
    assert (None if pd.isna(frame.loc[0, "date"]) else str(frame.loc[0, "date"].date())) == expected


@pytest.mark.parametrize(
    "left_mode,right_mode,reason",
    [
        (None, None, "unknown_request_adjustment"),
        ("qfq", None, "unknown_request_adjustment"),
        ("unknown", "unknown", "unknown_request_adjustment"),
        ("qfq", "hfq", "different_request_adjustment"),
        ("none", "qfq", "different_request_adjustment"),
    ],
)
def test_unknown_or_different_adjustment_cannot_be_called_equivalent(left_mode, right_mode, reason):
    left = norm(bars(), request_adjustment=left_mode)
    right = norm(bars(), request_adjustment=right_mode)
    result = compare_frames(left, right)
    assert result["price_comparison"]["status"] == "not_comparable"
    assert reason in result["price_comparison"]["reasons"]


def test_explicit_request_metadata_is_not_upstream_adjustment_verification():
    frame = norm(bars(), request_adjustment="qfq")
    result = compare_frames(frame, frame)
    assert result["price_comparison"]["within_tolerance"]
    assert (
        result["price_comparison"]["basis"] == "same_known_request_adjustment_not_vendor_certified"
    )
    assert result["left"]["request_adjustment"] == "qfq"
    assert "not_actual_adjustment_verification" in result["left"]["adjustment_evidence"]


def test_conflicting_adjustment_metadata_is_not_overridden_silently():
    left = norm(bars(adjustment_mode="none"), request_adjustment="qfq")
    right = norm(bars(), request_adjustment="qfq")
    result = compare_frames(left, right)
    assert "conflicting_adjustment_metadata" in result["price_comparison"]["reasons"]


def test_all_price_fields_use_same_date_tolerance_and_report_coverage_gaps():
    left = norm(bars(("2026-08-31", "2026-09-01", "2026-09-02")), request_adjustment="qfq")
    right_raw = bars(("2026-09-01", "2026-09-02", "2026-09-03"))
    right_raw.loc[0, "open"] += 0.01
    right_raw.loc[1, "high"] += 0.02
    right = norm(right_raw, request_adjustment="qfq")
    result = compare_frames(left, right)
    assert result["overlap_count"] == 2
    assert result["left_only_dates"] == ["2026-08-31"]
    assert result["right_only_dates"] == ["2026-09-03"]
    assert not result["complete_date_coverage"]
    assert result["price_comparison"]["compared_rows"] == 2
    assert not result["price_comparison"]["within_tolerance"]
    assert result["price_comparison"]["mismatched_dates"] == ["2026-09-02"]
    assert result["price_comparison"]["fields"]["open"]["mismatched_rows"] == 0
    assert set(result["price_comparison"]["fields"]) == {"open", "high", "low", "close"}


def test_duplicate_and_bad_ohlc_dates_cannot_join_as_normal_price_pairs():
    left = norm(
        bars(("2026-09-01", "2026-09-02", "2026-09-02", "2026-09-03")), request_adjustment="none"
    )
    right_raw = bars()
    right_raw.loc[2, "high"] = 5
    right = norm(right_raw, request_adjustment="none")
    result = compare_frames(left, right)
    assert result["overlap_count"] == 3
    assert result["price_comparison"]["compared_rows"] == 1
    assert result["price_comparison"]["excluded_overlap_dates"] == ["2026-09-02", "2026-09-03"]
    assert result["left"]["quality_status"] == "review_required"


def test_unknown_quantity_units_only_report_unverified_observed_ratio():
    left_raw = bars(volume_unit="unknown")
    left_raw["volume"] *= 100
    left = norm(left_raw, request_adjustment="qfq")
    right = norm(bars(volume_unit="lots"), request_adjustment="qfq")
    result = compare_frames(left, right)
    volume = result["quantity_comparison"]["volume"]
    assert volume["status"] == "unknown_units"
    assert volume["equivalent"] is None
    assert volume["observed_left_over_right_ratio_median"] == 100
    assert volume["ratio_evidence"] == "observation_only_not_unit_verification"
    assert result["quantity_comparison"]["amount"]["equivalent"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "unit", ["mixed_or_unknown", "unknown_shares", "assumed_shares", "widgets"]
)
def test_matching_unverified_unit_labels_never_prove_equivalence(unit):
    frame = norm(bars(volume_unit=unit, amount_unit=unit), request_adjustment="none")
    result = compare_frames(frame, frame)
    for quantity in ("volume", "amount"):
        assert result["quantity_comparison"][quantity]["status"] == "unknown_units"
        assert result["quantity_comparison"][quantity]["equivalent"] is None


def test_known_unit_aliases_are_comparable_but_wrong_quantity_units_are_not():
    left = norm(bars(volume_unit="hand", amount_unit="yuan"), request_adjustment="none")
    right = norm(bars(volume_unit="lots", amount_unit="cny"), request_adjustment="none")
    result = compare_frames(left, right)
    assert result["quantity_comparison"]["volume"]["equivalent"] is True
    assert result["quantity_comparison"]["amount"]["equivalent"] is True
    invalid = norm(bars(volume_unit="yuan", amount_unit="shares"), request_adjustment="none")
    result = compare_frames(invalid, invalid)
    assert result["quantity_comparison"]["volume"]["equivalent"] is None
    assert result["quantity_comparison"]["amount"]["equivalent"] is None


def test_confirmed_equal_units_can_be_compared_but_invalid_values_stay_unknown():
    left = norm(bars(volume_unit="shares", amount_unit="yuan"), request_adjustment="none")
    right = norm(bars(volume_unit="shares", amount_unit="yuan"), request_adjustment="none")
    result = compare_frames(left, right)
    assert result["quantity_comparison"]["volume"]["equivalent"] is True
    assert result["quantity_comparison"]["amount"]["equivalent"] is True
    right.loc[0, "amount"] = float("nan")
    right.loc[1, "volume"] += 1
    result = compare_frames(left, right)
    assert result["quantity_comparison"]["amount"]["equivalent"] is None
    assert result["quantity_comparison"]["volume"]["equivalent"] is False


def test_empty_input_is_not_a_successful_match():
    frame = norm(bars(()), request_adjustment="qfq")
    result = compare_frames(frame, frame)
    assert result["left"]["quality_status"] == "no_data"
    assert result["price_comparison"]["status"] == "no_overlap"
    assert result["complete_date_coverage"] is False


def test_extreme_quantity_ratio_remains_json_safe_not_a_unit_claim():
    left_raw, right_raw = bars(), bars()
    left_raw["volume"] = 1e308
    right_raw["volume"] = 1e-300
    result = compare_frames(
        norm(left_raw, request_adjustment="none"),
        norm(right_raw, request_adjustment="none"),
    )
    volume = result["quantity_comparison"]["volume"]
    assert volume["observed_left_over_right_ratio_median"] is None
    assert volume["non_finite_ratio_rows"] == 3
    assert volume["equivalent"] is None
    json.dumps(result, allow_nan=False)


def test_ambiguous_aliases_are_reported_and_block_comparison():
    raw = bars()
    raw["开盘"] = raw["open"]
    frame = norm(raw, request_adjustment="qfq")
    result = compare_frames(frame, frame)
    assert result["left"]["ambiguous_columns"] == ["open"]
    assert "ambiguous_column_aliases" in result["price_comparison"]["reasons"]


@pytest.mark.parametrize("days", [0, -1, True, 1.5])
def test_invalid_window_is_rejected(days):
    with pytest.raises(ValueError, match="days"):
        norm(bars(), days=days)


@pytest.mark.parametrize("tolerance", [0.012, -1, float("inf"), float("nan")])
def test_relaxing_price_tolerance_above_bound_is_rejected(tolerance):
    with pytest.raises(ValueError, match="0.011"):
        compare_frames(norm(bars()), norm(bars()), price_tolerance=tolerance)
