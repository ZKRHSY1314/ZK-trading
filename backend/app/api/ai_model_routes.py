from __future__ import annotations

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/api/ai/model", tags=["ai-model"])


@router.get("/capabilities")
def ai_model_capabilities() -> dict:
    from app.ai.model_service import AIModelGatewayService

    return AIModelGatewayService().capabilities()


@router.post("/explain-code-evolution/{record_id}")
def explain_code_evolution_with_model(record_id: int) -> dict:
    from app.ai.model_service import AIModelGatewayService

    try:
        return AIModelGatewayService().explain_code_evolution(record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit-logs")
def ai_model_audit_logs(operation: str | None = None, limit: int = 50) -> list[dict]:
    from app.ai.model_service import AIModelGatewayService

    return AIModelGatewayService().audit_logs(operation=operation, limit=limit)
