"""Pydantic response schemas for the TransitIQ API."""

from pydantic import BaseModel


class StopResult(BaseModel):
    """A single transit stop returned from a search."""

    stop_id: str
    stop_name: str
    lat: float
    lon: float


class SearchResponse(BaseModel):
    """Aggregated search response wrapping a list of stop results."""

    query: str
    results: list[StopResult]
    count: int


class HealthResponse(BaseModel):
    """Health-check endpoint response."""

    status: str
    app_name: str
    version: str
    gtfs_loaded: bool


class NearbyStopResult(BaseModel):
    """A nearby transit stop with its distance from a reference point."""

    stop_id: str
    stop_name: str
    lat: float
    lon: float
    distance_km: float


class NearbyStopsResponse(BaseModel):
    """Response model for nearby-stop search results."""

    feed: str
    count: int
    results: list[NearbyStopResult]
