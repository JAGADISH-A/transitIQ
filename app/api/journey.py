"""Journey planner API endpoint."""
import logging
from datetime import datetime
from app.models.schemas import JourneyResponse, TripStopsResponse
from fastapi import APIRouter, Query, HTTPException
from app.services.transit_service import transit_service
from app.services.quality_engine import JourneyQualityEngine
from app.services.journey_narrator import JourneyNarratorService
from app.services.session_manager import session_manager
from app.services.context_builder import build_journey_context

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/journey", response_model=JourneyResponse)
def get_journey(
    source_stop_id: str = Query(..., description="Source stop ID"),
    destination_stop_id: str = Query(..., description="Destination stop ID"),
    departure_after: str | None = Query(None, description="Return only routes departing after this time (HH:MM:SS)"),
) -> JourneyResponse:
    """Find a direct journey between two stops."""
    logger.info("[JOURNEY_REQUEST] source=%s dest=%s after=%s", source_stop_id, destination_stop_id, departure_after)

    if not departure_after:
        now = datetime.now()
        departure_after = f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"

    try:
        routes = transit_service.get_direct_journeys(source_stop_id, destination_stop_id, departure_after)
        transfer_routes = transit_service.find_transfer_routes(source_stop_id, destination_stop_id, departure_after)

        if not routes and not transfer_routes and departure_after:
            logger.info("No active journeys after %s, searching from 00:00", departure_after)
            routes = transit_service.get_direct_journeys(source_stop_id, destination_stop_id, "00:00:00")
            transfer_routes = transit_service.find_transfer_routes(source_stop_id, destination_stop_id, "00:00:00")

        if not routes and not transfer_routes:
            logger.info("No direct/1-transfer routes, falling back to 2-transfer search")
            transfer_routes = transit_service.find_two_transfer_routes(source_stop_id, destination_stop_id, departure_after)

            if not transfer_routes and departure_after:
                transfer_routes = transit_service.find_two_transfer_routes(source_stop_id, destination_stop_id, "00:00:00")

        routes, transfer_routes = JourneyQualityEngine.evaluate(routes, transfer_routes, departure_after)

        def get_arrival_minutes(j):
            time_str = None
            if getattr(j, 'third_leg', None) and getattr(j.third_leg, 'arrival_time', None):
                time_str = j.third_leg.arrival_time
            elif getattr(j, 'second_leg', None) and getattr(j.second_leg, 'arrival_time', None):
                time_str = j.second_leg.arrival_time
            if time_str:
                return JourneyQualityEngine._parse_time_string(time_str)
            return 999999

        def route_sorting_key(j):
            score = j.quality.score if (j.quality and j.quality.score is not None) else 0
            duration = j.total_duration if j.total_duration is not None else float('inf')
            arrival_mins = get_arrival_minutes(j)
            return (-score, duration, arrival_mins)

        transfer_routes.sort(key=route_sorting_key)
        transfer_routes = transfer_routes[:30]

        narrative = JourneyNarratorService.generate_narrative(routes, transfer_routes)

        response = JourneyResponse(success=True, narrative=narrative, routes=routes, transfer_routes=transfer_routes)

        # Auto-save journey context for AI conversational memory
        try:
            ctx = build_journey_context(source_stop_id, destination_stop_id, response, transit_service)
            if ctx is not None:
                session_manager.set_current_journey(ctx)
                logger.info(
                    "[JOURNEY_SAVED] origin=%s dest=%s train=%s",
                    ctx.origin, ctx.destination, ctx.train_name,
                )
        except Exception as ctx_err:
            logger.warning("[JOURNEY_SAVE_FAILED] %s", ctx_err)

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
        return TripStopsResponse(feed=feed_name, trip_id=trip_id, stops=stops)
    except ValueError as e:
        logger.warning("Trip stops not found: %s", str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Trip stops endpoint failed")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
