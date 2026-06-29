"""FastAPI application entrypoint."""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.logging_config import configure_logging
from app.metrics import register_custom_collectors
from app.middleware import CorrelationIDMiddleware, MetricsMiddleware
from app.redis_client import redis_conn
from app.routers import admin, client

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("app")

app = FastAPI(title="Photo Delivery Platform", version="0.5.0")

# Middleware — added in reverse execution order (last added = outermost).
# Execution order: CorrelationID first (sets request_id), then Metrics.
app.add_middleware(MetricsMiddleware)
app.add_middleware(CorrelationIDMiddleware)

app.include_router(admin.router)
app.include_router(client.router)

register_custom_collectors()


@app.get("/metrics", tags=["ops"], include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", tags=["ops"])
def health(db: Session = Depends(get_db)) -> dict:
    checks = {"postgres": False, "redis": False}
    try:
        db.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:  # noqa: BLE001
        log.exception("postgres health check failed")
    try:
        checks["redis"] = bool(redis_conn.ping())
    except Exception:  # noqa: BLE001
        log.exception("redis health check failed")
    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "env": settings.env, "checks": checks}


# Serve the React frontend.
# Mounted last so API routes always take precedence.
# In dev (npm run dev), Vite serves the frontend directly at :5173.
_frontend_dist = Path(__file__).parent.parent / "frontend-dist"
if _frontend_dist.exists():
    app.mount("/app", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

