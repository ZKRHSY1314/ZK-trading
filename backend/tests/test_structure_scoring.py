from app.learning.structure_scoring import ObservableStructureScorer


def _features(**overrides):
    values = {
        "price_percentile_250d": 35.0,
        "volume_ratio": 1.05,
        "upper_shadow_ratio": 0.1,
        "ma5_slope": 1.1,
        "ma20_slope": 0.5,
        "bars_count": 240,
        "avg_amount_20": 120_000_000,
        "recent_high_breakout": False,
        "is_limit_like": False,
        "is_near_limit": False,
    }
    values.update(overrides)
    return values


def test_constructive_base_scores_as_pre_markup_not_distribution():
    result = ObservableStructureScorer.score(
        _features(),
        position_class="LOW_BASE",
        sector_probability=0.72,
    )

    assert result.pre_markup_probability > 0.8
    assert result.distribution_probability < 0.4
    assert result.distribution_veto is False
    assert "base_position" in result.evidence


def test_high_volume_upper_shadow_triggers_distribution_veto():
    result = ObservableStructureScorer.score(
        _features(
            price_percentile_250d=91,
            volume_ratio=5.2,
            upper_shadow_ratio=0.58,
            ma5_slope=-2.2,
            ma20_slope=-1.2,
            is_near_limit=True,
        ),
        position_class="HIGH_DISTRIBUTION",
        sector_probability=0.8,
    )

    assert result.distribution_probability > 0.8
    assert result.distribution_probability > result.pre_markup_probability
    assert result.distribution_veto is True
    assert "long_upper_shadow" in result.evidence


def test_missing_history_degrades_confidence_and_never_vetoes():
    result = ObservableStructureScorer.score(
        {"bars_count": 5, "volume_ratio": 6.0, "upper_shadow_ratio": 0.8},
        position_class="HIGH_DISTRIBUTION",
    )

    assert result.confidence < 0.1
    assert result.distribution_veto is False
    assert "price_percentile_250d" in result.missing_features
