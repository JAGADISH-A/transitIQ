"""FastAPI application entrypoint for the TransitIQ backend."""

import logging
from contextlib import asynccontextmanager

from app.api.routes import router as routes_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.feeds import router as feeds_router
from app.api.health import router as health_router
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
        feeds = transit_service.available_feeds()
        print("Loaded feeds:")
        for feed_name in feeds:
            print(f"- {feed_name}")
        summary = transit_service.summary
        print(f"✓ Loaded {summary.get('stops', 0)} stops")
        print(f"✓ Loaded {summary.get('routes', 0)} routes")
        print(f"✓ Loaded {summary.get('trips', 0)} trips")
        print(f"✓ Loaded {summary.get('stop_times', 0)} stop_times")
        print(f"✓ Loaded {summary.get('shapes', 0)} shapes")
        print("TransitIQ Ready.")
    except Exception as exc:
        logger.warning("GTFS data unavailable during startup: %s", exc)
        print("TransitIQ Ready.")

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
app.include_router(feeds_router)
app.include_router(routes_router)
