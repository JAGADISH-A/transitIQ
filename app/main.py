"""FastAPI application entrypoint for the TransitIQ backend."""

import logging
from contextlib import asynccontextmanager

from app.api.routes import router as routes_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.agent import router as agent_router
from app.api.ai import router as ai_router
from app.api.journey import router as journey_router

from app.api.feeds import router as feeds_router
from app.api.health import router as health_router
from app.api.stops import router as stops_router
from app.config import get_settings
from app.services.transit_service import transit_service
from app.providers.registry import provider_registry
from app.providers.railway_provider import railway_provider
from app.providers.bus_provider import bus_provider
from app.providers.metro_provider import metro_provider
from app.providers.ferry_provider import ferry_provider

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
        print(f"[OK] Loaded {summary.get('stops', 0)} stops")
        print(f"[OK] Loaded {summary.get('routes', 0)} routes")
        print(f"[OK] Loaded {summary.get('trips', 0)} trips")
        print(f"[OK] Loaded {summary.get('stop_times', 0)} stop_times")
        print(f"[OK] Loaded {summary.get('shapes', 0)} shapes")

        # Phase 5 — Register transport providers
        provider_registry.register(railway_provider)
        provider_registry.register(bus_provider)
        provider_registry.register(metro_provider)
        provider_registry.register(ferry_provider)
        provider_count = len(provider_registry.list_providers())
        print(f"[OK] Registered {provider_count} transport providers")

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
app.include_router(agent_router)
app.include_router(ai_router)
app.include_router(journey_router)
