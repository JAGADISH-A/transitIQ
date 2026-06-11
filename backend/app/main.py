"""FastAPI application entrypoint for the TransitIQ backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.feeds import router as feeds_router
from app.api.health import router as health_router
from app.api.journey import router as journey_router
from app.api.routes import router as routes_router
from app.api.stops import router as stops_router
from app.config import get_settings
from app.services.transit_service import transit_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application resources on startup and clean them up on shutdown."""
    settings = get_settings()
    print("TransitIQ Backend Starting...")

    try:
        transit_service.load_all_feeds(settings.GTFS_DATA_PATH)
        logger.info("All GTFS feeds loaded from '%s'", settings.GTFS_DATA_PATH)
    except Exception as exc:
        logger.error("Failed to load GTFS feeds: %s", exc)

    yield


app = FastAPI(title="TransitIQ Backend", version=get_settings().APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(stops_router)
app.include_router(routes_router)
app.include_router(feeds_router)
app.include_router(agent_router)
app.include_router(journey_router)
