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


@router.get("/status")
def control_plane_status() -> dict:
    return ControlPlaneService().status()


@router.post("/run-once")
def run_control_plane(input_data: ControlPlaneRunInput | None = None) -> dict:
    payload = input_data or ControlPlaneRunInput()
    return ControlPlaneService().run_once(**payload.model_dump())
