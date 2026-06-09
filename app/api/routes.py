"""Route-related API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from app.models.schemas import AvailableShapesResponse, RouteShapeResponse
from app.services.transit_service import transit_service

router = APIRouter()


@router.get("/routes/shapes", response_model=AvailableShapesResponse)
def get_available_shapes(
    feed: str = Query(..., min_length=1, description="GTFS feed name"),
) -> AvailableShapesResponse:
    """Return all available GTFS shape IDs for a selected feed."""
    try:
        if not transit_service.is_loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GTFS data is not loaded yet.",
            )

        if feed not in transit_service.available_feeds():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed '{feed}' does not exist.",
            )

        shape_ids = transit_service.get_available_shapes(feed)
        return AvailableShapesResponse(feed=feed, count=len(shape_ids), shape_ids=shape_ids)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/routes/shape", response_model=RouteShapeResponse)
def get_route_shape(
    feed: str = Query(..., min_length=1, description="GTFS feed name"),
    shape_id: str = Query(..., min_length=1, description="GTFS shape identifier"),
) -> RouteShapeResponse:
    """Return the ordered shape points for a selected route shape."""
    try:
        if not transit_service.is_loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GTFS data is not loaded yet.",
            )

        if feed not in transit_service.available_feeds():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed '{feed}' does not exist.",
            )

        points = transit_service.get_route_shape(feed_name=feed, shape_id=shape_id)
        return RouteShapeResponse(
            feed=feed,
            shape_id=shape_id,
            point_count=len(points),
            points=points,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
