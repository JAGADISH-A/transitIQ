"""AI intent extraction endpoints."""

import logging

from fastapi import APIRouter, Body, HTTPException, status

from app.models.schemas import JourneyIntentRequest, JourneyIntentResponse
from app.services.journey_intent_service import journey_intent_service
from app.services.transit_service import transit_service

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger(__name__)

@router.post("/plan", response_model=JourneyIntentResponse)
def extract_journey_intent(request: JourneyIntentRequest = Body(...)):
    """Extract journey planning parameters from natural language."""
    try:
        if not transit_service.is_loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GTFS data is not loaded yet.",
            )

        prompt = request.prompt
        if not prompt or not prompt.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt must be a non-empty string."
            )

        intent = journey_intent_service.extract_intent(prompt, request.context)
        return intent

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to extract journey intent")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        ) from exc
