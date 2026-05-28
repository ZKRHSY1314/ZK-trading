from fastapi import FastAPI

from app.api.routes import router
from app.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "live_trading_enabled": settings.enable_live_trading,
    }
