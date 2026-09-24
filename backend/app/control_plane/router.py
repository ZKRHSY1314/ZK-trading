from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.control_plane.service import ControlPlaneService


router = APIRouter(prefix="/api/control-plane", tags=["control-plane"])


class ControlPlaneRunInput(BaseModel):
    profile: Literal["adaptive", "pulse", "training", "maintenance", "full"] = "adaptive"
    limit: int = Field(default=30, ge=5, le=120)
    monitor_limit: int = Field(default=5, ge=1, le=20)
    review_symbol: str = "SZ002081"
    requested_by: str = "codex_control_plane"
    # Defaults to "manual", not "scheduled". This endpoint is reachable from the
    # cockpit's run button and from anything else that can POST, and an
    # unspecified caller is by definition not the scheduler. Defaulting the other
    # way meant a human clicking Run consumed that day's official claim - which
    # is a primary key, so the real scheduled run afterwards could only get
    # "already_recorded" and the day lost its official snapshot for good.
    # The scheduled worker asks for it explicitly.
    #
    # Note the boundary this relies on: any caller that can reach this endpoint
    # may still ASK for "scheduled" and consume the day's official claim. The
    # only thing preventing that today is that run_stack.ps1 binds uvicorn to
    # 127.0.0.1, so the caller is already on this machine. That is a deployment
    # property, not an API guarantee - if this is ever bound to a routable
    # address, "scheduled" needs real authorization here rather than a default.
    run_kind: Literal["scheduled", "manual", "replay", "challenger"] = "manual"


@router.get("/status")
def control_plane_status() -> dict:
    return ControlPlaneService().status()


@router.post("/run-once")
def run_control_plane(input_data: ControlPlaneRunInput | None = None) -> dict:
    payload = input_data or ControlPlaneRunInput()
    return ControlPlaneService().run_once(**payload.model_dump())
