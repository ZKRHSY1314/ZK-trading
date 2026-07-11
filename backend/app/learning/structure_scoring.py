from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


STRUCTURE_MODEL_VERSION = "observable_structure_v1"


@dataclass(frozen=True)
class StructureScore:
    pre_markup_probability: float
    distribution_probability: float
    confidence: float
    distribution_veto: bool
    evidence: tuple[str, ...]
    missing_features: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_version": STRUCTURE_MODEL_VERSION,
            "pre_markup_probability": self.pre_markup_probability,
            "distribution_probability": self.distribution_probability,
            "confidence": self.confidence,
            "distribution_veto": self.distribution_veto,
            "evidence": list(self.evidence),
            "missing_features": list(self.missing_features),
            "review_only": True,
            "observable_proxy_only": True,
        }


class ObservableStructureScorer:
    """Fast, explainable baseline for structure ranking.

    This scorer never claims to observe a hidden market actor.  It converts
    point-in-time price/volume proxies into two competing review probabilities:
    pre-markup structure and distribution risk.  The probabilities are a
    baseline to be calibrated by the Forecast Ledger, not trading permission.
    """

    REQUIRED = (
        "price_percentile_250d",
        "volume_ratio",
        "upper_shadow_ratio",
        "ma5_slope",
        "ma20_slope",
        "bars_count",
    )

    @classmethod
    def score(
        cls,
        features: dict[str, Any],
        *,
        position_class: str | None = None,
        sector_probability: float | None = None,
    ) -> StructureScore:
        missing = tuple(key for key in cls.REQUIRED if features.get(key) is None)
        evidence: list[str] = []
        pre = -0.7
        distribution = -1.0

        percentile = cls._number(features.get("price_percentile_250d"))
        volume_ratio = cls._number(features.get("volume_ratio"))
        upper_shadow = cls._number(features.get("upper_shadow_ratio"))
        ma5_slope = cls._number(features.get("ma5_slope"))
        ma20_slope = cls._number(features.get("ma20_slope"))
        bars_count = cls._number(features.get("bars_count")) or 0.0

        if percentile is not None:
            if 12 <= percentile <= 58:
                pre += 1.25
                evidence.append("base_position")
            elif percentile >= 78:
                distribution += 1.15
                evidence.append("high_price_position")
            elif percentile <= 8:
                pre -= 0.35
                evidence.append("weak_extreme_low")

        if volume_ratio is not None:
            if 0.65 <= volume_ratio <= 1.45:
                pre += 0.8
                evidence.append("controlled_volume")
            elif 1.45 < volume_ratio <= 2.2:
                pre += 0.25
                evidence.append("moderate_volume_confirmation")
            elif volume_ratio >= 2.8:
                distribution += min(1.4, (volume_ratio - 2.2) / 2.0)
                evidence.append("abnormal_volume_expansion")

        if upper_shadow is not None:
            if upper_shadow >= 0.42:
                distribution += 1.1
                pre -= 0.35
                evidence.append("long_upper_shadow")
            elif upper_shadow <= 0.18:
                pre += 0.25
                evidence.append("limited_upper_shadow")

        if ma5_slope is not None:
            if 0 < ma5_slope <= 3.5:
                pre += 0.55
                evidence.append("controlled_short_trend")
            elif ma5_slope < -1.5:
                distribution += 0.45
                evidence.append("short_trend_weakening")
        if ma20_slope is not None:
            if 0 <= ma20_slope <= 2.0:
                pre += 0.4
                evidence.append("stable_medium_trend")
            elif ma20_slope < -1.0:
                pre -= 0.3
                evidence.append("medium_trend_decline")

        if features.get("recent_high_breakout"):
            pre += 0.2
            distribution += 0.15
            evidence.append("breakout_requires_confirmation")
        if features.get("is_limit_like") or features.get("is_near_limit"):
            distribution += 0.25
            pre -= 0.15
            evidence.append("late_momentum_risk")
        if position_class == "HIGH_DISTRIBUTION":
            distribution += 1.0
            evidence.append("legacy_distribution_class")
        elif position_class in {"LOW_BASE", "MID_RECOVERY"}:
            pre += 0.35
            evidence.append("constructive_position_class")

        if sector_probability is not None:
            bounded_sector = max(0.0, min(1.0, float(sector_probability)))
            pre += (bounded_sector - 0.5) * 0.8
            evidence.append("sector_prior")

        completeness = max(0.0, 1.0 - len(missing) / len(cls.REQUIRED))
        history_factor = min(1.0, bars_count / 120.0)
        amount_factor = 1.0 if features.get("avg_amount_20") not in {None, 0, 0.0} else 0.7
        confidence = round(completeness * history_factor * amount_factor, 4)
        pre_probability = round(cls._sigmoid(pre) * confidence, 4)
        distribution_probability = round(cls._sigmoid(distribution) * confidence, 4)
        distribution_veto = confidence >= 0.45 and distribution_probability >= 0.62

        return StructureScore(
            pre_markup_probability=pre_probability,
            distribution_probability=distribution_probability,
            confidence=confidence,
            distribution_veto=distribution_veto,
            evidence=tuple(dict.fromkeys(evidence)),
            missing_features=missing,
        )

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
