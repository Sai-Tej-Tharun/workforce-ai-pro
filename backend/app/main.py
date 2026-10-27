"""WorkForce AI Pro – FastAPI application entrypoint."""
import asyncio, logging, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import Base, engine
from . import models  # noqa: F401  (register tables)
from .ws import manager
from .routers import (auth, employees, departments, attendance, leave, payroll, notifications, chat, documents, datasets,
                      predictions, monitoring, interventions, analytics, recommendations, reports, audit, tasks, performance)

log = logging.getLogger("workforce")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    manager.loop = asyncio.get_running_loop()
    yield


app = FastAPI(
    title="WorkForce AI Pro API",
    description="HR Attrition Prediction & Workforce Intelligence Platform. JWT auth (Bearer) + RBAC: ADMIN, HR, MANAGER, EMPLOYEE.",
    version="1.0.0", lifespan=lifespan,
)
@app.get("/")
def root():
    return {
        "message": "WorkForce AI Pro API is running",
        "status": "healthy",
        "docs": "/docs"
    }
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_and_timing(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - t0) * 1000:.1f}"
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


for r in (auth, employees, departments, attendance, leave, payroll, notifications, chat, documents, datasets, predictions,
          monitoring, interventions, analytics, recommendations, reports, audit, tasks, performance):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health", tags=["System"])
def health():
    return {"status": "ok", "service": settings.PROJECT_NAME, "online_users": len(manager.online_user_ids())}
