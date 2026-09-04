from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings


router = APIRouter(prefix="/api/research/offhour", tags=["offhour-research"])


class OffhourResearchRunInput(BaseModel):
    limit: int = 100
    strategy_limit: int = 50
    history_days: int = 240
    write_artifact: bool = True
    refresh_history: bool = False
    requested_by: str = "codex"


@router.get("/capabilities")
def offhour_research_capabilities() -> dict:
    from app.research.offhour import OffhourResearchLoopService

    return OffhourResearchLoopService().capabilities()


@router.post("/run")
def run_offhour_research(input_data: OffhourResearchRunInput | None = None) -> dict:
    from app.research.offhour import OffhourResearchLoopService

    payload = input_data or OffhourResearchRunInput()
    return OffhourResearchLoopService().run(
        limit=payload.limit,
        strategy_limit=payload.strategy_limit,
        history_days=payload.history_days,
        write_artifact=payload.write_artifact,
        refresh_history=payload.refresh_history,
        requested_by=payload.requested_by,
    )


@router.get("/runs/latest")
def latest_offhour_research_run() -> dict:
    from app.research.offhour import OffhourResearchLoopService

    latest = OffhourResearchLoopService().latest_run()
    if latest is None:
        return {
            "status": "empty",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
    return latest


@router.get("/runs/{run_id}")
def get_offhour_research_run(run_id: int) -> dict:
    from app.research.offhour import OffhourResearchLoopService

    item = OffhourResearchLoopService().get_run(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Offhour research run not found")
    return item


@router.get("/model-candidates/latest")
def latest_offhour_model_candidate() -> dict:
    from app.research.offhour import OffhourResearchLoopService

    return OffhourResearchLoopService().latest_model_candidate()


@router.get("/simulation-review-plan/latest")
def latest_offhour_simulation_review_plan(limit: int = 12) -> dict:
    from app.research.offhour import OffhourResearchLoopService

    return OffhourResearchLoopService().latest_simulation_review_plan(limit=limit)


@router.get("/strategy-learning-packet/latest")
def latest_offhour_strategy_learning_packet(limit: int = 8) -> dict:
    from app.research.offhour import OffhourResearchLoopService

    return OffhourResearchLoopService().latest_strategy_learning_packet(limit=limit)
