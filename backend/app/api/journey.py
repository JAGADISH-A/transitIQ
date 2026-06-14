"""Journey planner API endpoint."""
import logging
from datetime import datetime
from app.models.schemas import JourneyResponse, TripStopsResponse
from fastapi import APIRouter, Query, HTTPException
from app.services.transit_service import transit_service
from app.services.quality_engine import JourneyQualityEngine
from app.services.journey_narrator import JourneyNarratorService

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
        "[JOURNEY_REQUEST_RECEIVED]\nsource_stop_id=%s\ndestination_stop_id=%s\ndeparture_after=%s",
        source_stop_id,
        destination_stop_id,
        departure_after,
    )

    if not departure_after:
        now = datetime.now()
        departure_after = f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"

    try:
        import time
        logger.info("[ROUTING_START]\nsource=%s\ndestination=%s", source_stop_id, destination_stop_id)
        
        start = time.monotonic()
        routes = transit_service.get_direct_journeys(
            source_stop_id, destination_stop_id, departure_after
        )
        logger.info("[TIMING] get_direct_journeys=%.2fs", time.monotonic() - start)

        start = time.monotonic()
        transfer_routes = transit_service.find_transfer_routes(
            source_stop_id, destination_stop_id, departure_after
        )
        logger.info("[TIMING] find_transfer_routes=%.2fs", time.monotonic() - start)

        if not routes and not transfer_routes and departure_after:
            # If all journeys for today have expired, automatically search for next available service
            logger.info("No active journeys found after %s, searching next available service", departure_after)
            
            start = time.monotonic()
            routes = transit_service.get_direct_journeys(
                source_stop_id, destination_stop_id, "00:00:00"
            )
            logger.info("[TIMING] get_direct_journeys=%.2fs", time.monotonic() - start)
            
            start = time.monotonic()
            transfer_routes = transit_service.find_transfer_routes(
                source_stop_id, destination_stop_id, "00:00:00"
            )
            logger.info("[TIMING] find_transfer_routes=%.2fs", time.monotonic() - start)

        if not routes and not transfer_routes:
            logger.info("No direct or 1-transfer routes found, falling back to 2-transfer search")
            
            start = time.monotonic()
            transfer_routes = transit_service.find_two_transfer_routes(
                source_stop_id, destination_stop_id, departure_after
            )
            logger.info("[TIMING] find_two_transfer_routes=%.2fs", time.monotonic() - start)
            
            if not transfer_routes and departure_after:
                start = time.monotonic()
                transfer_routes = transit_service.find_two_transfer_routes(
                    source_stop_id, destination_stop_id, "00:00:00"
                )
                logger.info("[TIMING] find_two_transfer_routes=%.2fs", time.monotonic() - start)

        logger.info(
            "Journey search result: source='%s', destination='%s', departure_after='%s', routes_found=%d, transfers_found=%d",
            source_stop_id,
            destination_stop_id,
            departure_after,
            len(routes),
            len(transfer_routes)
        )

        start = time.monotonic()
        routes, transfer_routes = JourneyQualityEngine.evaluate(routes, transfer_routes, departure_after)
        logger.info("[TIMING] JourneyQualityEngine.evaluate=%.2fs", time.monotonic() - start)
        
        # Sort transfer routes by quality score (descending), duration (ascending), and arrival minutes (ascending)
        def get_arrival_minutes(j):
            time_str = None
            if getattr(j, 'third_leg', None) and getattr(j.third_leg, 'arrival_time', None):
                time_str = j.third_leg.arrival_time
            elif getattr(j, 'second_leg', None) and getattr(j.second_leg, 'arrival_time', None):
                time_str = j.second_leg.arrival_time
            
            if time_str:
                return JourneyQualityEngine._parse_time_string(time_str)
            return 999999  # Large value fallback for missing arrival times

        def route_sorting_key(j):
            score = j.quality.score if (j.quality and j.quality.score is not None) else 0
            duration = j.total_duration if j.total_duration is not None else float('inf')
            arrival_mins = get_arrival_minutes(j)
            return (-score, duration, arrival_mins)

        transfer_routes.sort(key=route_sorting_key)
        transfer_routes = transfer_routes[:30]
        
        start = time.monotonic()
        narrative = JourneyNarratorService.generate_narrative(routes, transfer_routes)
        logger.info("[TIMING] JourneyNarratorService.generate_narrative=%.2fs", time.monotonic() - start)

        logger.info("[FINAL_ROUTE_COUNT]\ncount=%d", len(routes) + len(transfer_routes))
        
        start = time.monotonic()
        response = JourneyResponse(success=True, narrative=narrative, routes=routes, transfer_routes=transfer_routes)
        logger.info("[TIMING] JourneyResponse creation=%.2fs", time.monotonic() - start)
        return response

    except Exception as e:
        logger.exception("[ROUTING_FAILURE]")
        raise


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
