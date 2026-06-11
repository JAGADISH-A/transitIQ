"""Journey planner API endpoint."""
import logging
from fastapi import APIRouter, Query

from app.models.schemas import JourneyResponse
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/journey", response_model=JourneyResponse)
def get_journey(
    source_stop_id: str = Query(..., description="Source stop ID"),
    destination_stop_id: str = Query(..., description="Destination stop ID"),
) -> JourneyResponse:
    """Find a direct journey between two stops."""
    logger.info(
        "Journey search requested: source='%s', destination='%s'",
        source_stop_id,
        destination_stop_id,
    )

    routes = transit_service.get_direct_journeys(source_stop_id, destination_stop_id)

    logger.info(
        "Journey search result: source='%s', destination='%s', routes_found=%d",
        source_stop_id,
        destination_stop_id,
        len(routes),
    )

    return JourneyResponse(success=True, routes=routes)

