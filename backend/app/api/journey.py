"""Journey planner API endpoint."""
import logging
from fastapi import APIRouter, Query

from app.models.schemas import JourneyResponse, TripStopsResponse
from fastapi import HTTPException
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/journey", response_model=JourneyResponse)
def get_journey(
    source_stop_id: str = Query(..., description="Source stop ID"),
    destination_stop_id: str = Query(..., description="Destination stop ID"),
    departure_after: str | None = Query(None, description="Return only routes departing after this time (HH:MM:SS)"),
) -> JourneyResponse:
    """Find a direct journey between two stops."""
    logger.info(
        "Journey search requested: source='%s', destination='%s', departure_after='%s'",
        source_stop_id,
        destination_stop_id,
        departure_after,
    )

    routes = transit_service.get_direct_journeys(
        source_stop_id, destination_stop_id, departure_after
    )

    transfer_routes = transit_service.find_transfer_routes(
        source_stop_id, destination_stop_id, departure_after
    )

    logger.info(
        "Journey search result: source='%s', destination='%s', departure_after='%s', routes_found=%d, transfers_found=%d",
        source_stop_id,
        destination_stop_id,
        departure_after,
        len(routes),
        len(transfer_routes)
    )

    return JourneyResponse(success=True, routes=routes, transfer_routes=transfer_routes)


@router.get("/trips/{feed_name}/{trip_id}/stops", response_model=TripStopsResponse)
def get_trip_stops(
    feed_name: str,
    trip_id: str,
) -> TripStopsResponse:
    """Return all stops for a given trip in chronological order."""
    logger.info("Trip stops requested for feed '%s', trip '%s'", feed_name, trip_id)
    try:
        stops = transit_service.get_trip_stops(feed_name, trip_id)
        return TripStopsResponse(
            feed=feed_name,
            trip_id=trip_id,
            stops=stops
        )
    except ValueError as e:
        logger.warning("Trip stops not found: %s", str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Trip stops endpoint failed")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
