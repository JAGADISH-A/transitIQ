"""Pydantic response schemas for the TransitIQ API."""

from enum import IntEnum
from pydantic import BaseModel


class MatchTier(IntEnum):
    """Deterministic ranking tiers for stop matching. Lower number is better priority."""
    EXACT_ID = 1
    EXACT_NAME = 2
    NORMALIZED_EXACT_NAME = 3
    PREFIX = 4
    TOKEN = 5
    FUZZY = 6


class StopResult(BaseModel):
    """A single transit stop returned from a search."""

    stop_id: str
    stop_name: str
    lat: float
    lon: float
    match_tier: int = MatchTier.FUZZY
    match_score: float = 0.0  # Tie-breaker for same tier


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


class AvailableShapesResponse(BaseModel):
    """Response model for available GTFS shape identifiers."""

    feed: str
    count: int
    shape_ids: list[str]


class ShapePoint(BaseModel):
    """A single point in a GTFS shape polyline."""

    lat: float
    lon: float
    sequence: int


class RouteShapeResponse(BaseModel):
    """Response model describing a GTFS route shape by feed."""

    feed: str
    shape_id: str
    point_count: int
    points: list[ShapePoint]


class TripRoute(BaseModel):
    """A GTFS route that serves a stop, used in trip-planning results."""

    route_id: str
    route_short_name: str
    route_long_name: str
    feed: str
    shape_id: str | None = None


class TransferOption(BaseModel):
    """A single-transfer journey between two stops via a transfer point."""

    transfer_stop_id: str
    transfer_stop_name: str
    route_from: TripRoute
    route_to: TripRoute
    estimated_stop_count: int
    distance_penalty: float
    score: float


class TripResult(BaseModel):
    """Deterministic trip-planning result between a source and destination stop."""

    source_stop_id: str
    source_stop_name: str
    destination_stop_id: str
    destination_stop_name: str
    feed: str
    direct_routes: list[TripRoute]
    transfer_options: list[TransferOption]
    source_match_tier: int = 6
    dest_match_tier: int = 6
    source_match_score: float = 0.0
    dest_match_score: float = 0.0


class TripResponse(BaseModel):
    """API response wrapping one or more trip-planning results across feeds."""

    source: str
    destination: str
    results: list[TripResult]
    feeds_searched: list[str]


class JourneyRoute(BaseModel):
    """A minimal direct route option between two stops."""
    feed: str
    trip_id: str
    route_id: str
    route_name: str
    source_stop: str
    destination_stop: str
    stops_between: int
    shape_id: str | None = None


class JourneyResponse(BaseModel):
    """Response containing matching direct routes for a journey."""
    success: bool
    routes: list[JourneyRoute]
