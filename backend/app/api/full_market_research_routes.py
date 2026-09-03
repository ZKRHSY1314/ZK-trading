from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.candidates.full_market_score_calibration import (
    FullMarketScoreCalibrationService,
)
from app.data.market_history import MarketHistoryStore


router = APIRouter(
    prefix="/api/candidates/full-market-calibration",
    tags=["full-market-research"],
)


class FullMarketCalibrationRunInput(BaseModel):
    """Bounded research parameters; persistence is intentionally not user-selectable."""

    model_config = ConfigDict(extra="forbid")

    horizon_trading_days: int = Field(default=20, ge=1, le=250)
    target_return_pct: float = Field(default=8.0, ge=0.1, le=100.0)
    min_history_bars: int = Field(default=60, ge=60, le=500)
    lookback_bars: int = Field(default=120, ge=60, le=500)
    validation_fraction: float = Field(default=0.2, ge=0.1, le=0.5)
    score_bin_width: int = Field(default=10, ge=1, le=50)
    sample_stride: int = Field(default=10, ge=1, le=60)
    min_train_samples: int = Field(default=200, ge=1, le=1_000_000)
    min_validation_samples: int = Field(default=50, ge=1, le=1_000_000)
    min_bin_samples: int = Field(default=30, ge=1, le=1_000_000)
    as_of_date: date | None = None

    @model_validator(mode="after")
    def validate_cross_field_bounds(self) -> "FullMarketCalibrationRunInput":
        if self.lookback_bars < self.min_history_bars:
            raise ValueError("lookback_bars must be at least min_history_bars")
        if 100 % self.score_bin_width:
            raise ValueError("score_bin_width must evenly divide 100")
        return self


def _service(request: Request) -> FullMarketScoreCalibrationService:
    return FullMarketScoreCalibrationService(
        store=request.app.state.runtime_store,
        history_store=MarketHistoryStore(),
    )


@router.get("/latest")
def latest_full_market_calibration(request: Request) -> dict:
    return _service(request).latest()


@router.post("/run")
def run_full_market_calibration(
    request: Request,
    input_data: FullMarketCalibrationRunInput | None = None,
) -> dict:
    payload = input_data or FullMarketCalibrationRunInput()
    try:
        return _service(request).run(
            **payload.model_dump(mode="json"),
            persist=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
