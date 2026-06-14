"""Stop search API routes."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.models.schemas import NearbyStopsResponse, SearchResponse, StopResult
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stops/search", response_model=SearchResponse)
def search_stops(q: str = Query(..., min_length=2, description="Search query for stop names or IDs")) -> SearchResponse:
    """Search for stops using the transit service."""
    try:
        if not transit_service.is_loaded:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GTFS data is not loaded yet.")

        results: list[StopResult] = transit_service.search_stops(q)
        return SearchResponse(query=q, results=results, count=len(results))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/stops/search/feed", response_model=SearchResponse)
def search_stops_in_feed(
    q: str = Query(..., min_length=2, description="Search query for stop names or IDs"),
    feed: str = Query(..., min_length=1, description="GTFS feed name to search in"),
) -> SearchResponse:
    """Search for stops within a selected GTFS feed."""
    try:
        available_feeds = transit_service.available_feeds()
        if feed not in available_feeds:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Feed '{feed}' does not exist.")

        results: list[StopResult] = transit_service.search_stops_in_feed(q, feed)
        return SearchResponse(query=q, results=results, count=len(results))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/stops/nearby", response_model=NearbyStopsResponse)
def nearby_stops(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    feed: Optional[str] = Query(None, min_length=1, description="GTFS feed name"),
    radius_km: float = Query(2.0, ge=0.0, description="Search radius in kilometers"),
) -> NearbyStopsResponse:
    """Return nearby stops for a selected GTFS feed, or all feeds if not specified."""
    # Log received coordinates
    logger.info("Received request for nearby stops: lat=%f, lon=%f, feed=%s, radius_km=%f", lat, lon, feed, radius_km)

    # Validate coordinate ranges
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        logger.warning("Invalid latitude/longitude received: lat=%f, lon=%f", lat, lon)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Latitude must be between -90 and 90, and longitude between -180 and 180."
        )

    try:
        if not transit_service.is_loaded:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GTFS data is not loaded yet.")

        if feed:
            if feed not in transit_service.available_feeds():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Feed '{feed}' does not exist.")
            results = transit_service.get_nearby_stops(
                feed_name=feed,
                lat=lat,
                lon=lon,
                radius_km=radius_km,
            )
            feed_name_to_return = feed
        else:
            results = transit_service.get_nearby_stops_all_feeds(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
            )
            feed_name_to_return = "all"

        # Check for empty results and return custom response
        if not results:
            logger.info("No nearby stops found for coordinates lat=%f, lon=%f in feed %s", lat, lon, feed_name_to_return)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "stops": [],
                    "message": "No nearby stops found"
                }
            )

        return NearbyStopsResponse(feed=feed_name_to_return, count=len(results), results=results)

    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Validation error in nearby_stops: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected exception occurred in nearby_stops route: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {exc}",
        ) from exc
