import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import baselines, health, ingest, state, stats, trends
from app.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime_secrets()
    logger.info("Vigil backend starting up")
    yield
    logger.info("Vigil backend shutting down")


app = FastAPI(
    title="Vigil Backend",
    description="Physiological data ingestion and intelligence API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

app.include_router(ingest.router)
app.include_router(health.router)
app.include_router(stats.router)
app.include_router(trends.router)
app.include_router(baselines.router)
app.include_router(state.router)
