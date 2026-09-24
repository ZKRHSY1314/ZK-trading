from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.forecasting.evidence import ForecastEvidenceService
from app.storage.sqlite_store import SQLiteStore


router = APIRouter(prefix="/api/forecast", tags=["forecast-evidence"])


@router.get("/evidence")
def forecast_evidence(as_of: datetime | None = None, include_inferred: bool = False) -> dict:
    """Canonical forecast evidence for the scoreboard. Read-only: never labels or persists.

    ``include_inferred`` admits shape-inferred snapshots; the result is then
    exploratory and can never make a horizon strategy-eligible.
    """

    if as_of is not None and as_of.tzinfo is None:
        raise HTTPException(status_code=422, detail="as_of must include a timezone offset")
    store = SQLiteStore(settings.database_path)
    return ForecastEvidenceService(store).summary(as_of, include_inferred=include_inferred)
