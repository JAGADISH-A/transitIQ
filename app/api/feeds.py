"""Feed discovery API routes."""

from fastapi import APIRouter

from app.models.feed_schemas import AvailableFeedsResponse
from app.services.transit_service import transit_service

router = APIRouter()


@router.get("/feeds", response_model=AvailableFeedsResponse)
def list_feeds() -> AvailableFeedsResponse:
    """Return the names of all available GTFS feeds."""
    return AvailableFeedsResponse(feeds=transit_service.available_feeds())
