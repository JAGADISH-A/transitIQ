"""Health check API routes."""

from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.services.transit_service import transit_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return the application health status."""
    return HealthResponse(
        status="ok",
        app_name="TransitIQ",
        version="1.0.0",
        gtfs_loaded=transit_service.is_loaded,
    )
