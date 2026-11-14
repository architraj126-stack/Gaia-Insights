import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.logging import setup_logging
from backend.app.api.health import router as health_router
from backend.app.api.catalog import router as catalog_router
from backend.app.api.regions import router as regions_router
from backend.app.api.datasets import router as datasets_router
from backend.app.api.admin import router as admin_router
from backend.app.api.analysis import router as analysis_router
from backend.app.api.reports import router as reports_router

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("backend.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Earth Science Explorer API", extra={"env": settings.APP_ENV})

    # -----------------------------------------------------------------------
    # Phase 3a startup sequence:
    # 1. Create all tables (if not already created by Alembic)
    # 2. Seed the catalog from YAML (idempotent upsert)
    # 3. Refresh latest-observation dates from live data sources
    # -----------------------------------------------------------------------
    try:
        from backend.app.db.session import engine
        from backend.app.db.models import Base
        from backend.app.db.seed import seed_catalog
        from backend.app.db.session import AsyncSessionLocal
        from backend.app.services.catalogue_refresh import refresh_all_datasets

        # Create tables (Alembic handles schema; this is a safety net for dev)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncSessionLocal() as session:
            await seed_catalog(session)
            await session.commit()

        async with AsyncSessionLocal() as session:
            await refresh_all_datasets(session)
            await session.commit()

    except Exception as exc:
        logger.error(
            "Startup catalog initialization failed: %s. "
            "API will serve from YAML fallback until DB is available.",
            exc,
            exc_info=False,  # don't log stack trace (may contain conn string details)
        )

    yield
    logger.info("Shutting down Earth Science Explorer API")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:10]}"
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

# Routers
app.include_router(health_router)
app.include_router(catalog_router)
app.include_router(regions_router)
app.include_router(datasets_router)
app.include_router(admin_router)
app.include_router(analysis_router)
app.include_router(reports_router)
