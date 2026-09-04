from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from app.api.ai_model_routes import router as ai_model_router
from app.api.full_market_research_routes import router as full_market_research_router
from app.api.offhour_research_routes import router as offhour_research_router
from app.api.public_opinion_routes import router as public_opinion_router
from app.api.routes import router
from app.config import settings
from app.control_plane.router import router as control_plane_router
from app.runtime import process_health, readiness_snapshot
from app.storage.sqlite_store import SQLiteStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_store = SQLiteStore(settings.database_path)
    runtime_store.init()
    app.state.runtime_store = runtime_store
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
app.include_router(control_plane_router)
app.include_router(public_opinion_router)
app.include_router(ai_model_router)
app.include_router(offhour_research_router)
app.include_router(full_market_research_router)


@app.get("/livez")
def livez() -> dict[str, object]:
    return process_health()


@app.get("/readyz")
def readyz(response: Response) -> dict[str, object]:
    snapshot = readiness_snapshot()
    if snapshot["status"] != "ready":
        response.status_code = 503
    return snapshot


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "live_trading_enabled": settings.enable_live_trading,
    }
