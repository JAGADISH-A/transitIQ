"""Stop search API routes."""

from fastapi import APIRouter, HTTPException, Query, status

from app.models.schemas import SearchResponse, StopResult
from app.services.transit_service import transit_service

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
