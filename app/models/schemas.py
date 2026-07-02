"""Pydantic response schemas for the TransitIQ API."""

from datetime import datetime
from enum import Enum, IntEnum
from typing import Optional

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


class IntentType(str, Enum):
    NEW_SEARCH = "NEW_SEARCH"
    MODIFY_TIME = "MODIFY_TIME"
    MODIFY_FILTER = "MODIFY_FILTER"
    OPTIMIZE_ROUTE = "OPTIMIZE_ROUTE"
    EXPLAIN_ROUTE = "EXPLAIN_ROUTE"
    ROUTE_CONTEXT_QA = "ROUTE_CONTEXT_QA"
    CONTEXT_EXPIRED = "CONTEXT_EXPIRED"


class JourneyContext(BaseModel):
    source: Optional[str] = None
    destination: Optional[str] = None
    source_stop_id: Optional[str] = None
    destination_stop_id: Optional[str] = None
    departure_time: Optional[str] = None
    preference: Optional[str] = None
    last_updated: Optional[str] = None
    route: Optional[dict] = None


class JourneyIntentRequest(BaseModel):
    prompt: str
    context: Optional[JourneyContext] = None


class JourneyIntentResponse(BaseModel):
    intent_type: IntentType
    source: Optional[str] = None
    destination: Optional[str] = None
    departure_time: Optional[str] = None
    preference: Optional[str] = None
    error_message: Optional[str] = None


class DisplayTime(BaseModel):
    display_time: str
    day_offset: int


class QualityClassification(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    ACCEPTABLE = "Acceptable"
    POOR = "Poor"
    LOW_QUALITY = "Low Quality"
    REJECTED = "Rejected"


class JourneyQuality(BaseModel):
    score: float
    classification: QualityClassification
    recommendation_reason: str | None = None
    route_flags: list[str] = []


class JourneyNarrative(BaseModel):
    headline: str
    summary: str
    recommendation: str
    warnings: list[str]
    alternatives_available: int


class LegType(str, Enum):
    TRAIN = "TRAIN"
    WALK = "WALK"


class JourneyType(str, Enum):
    DIRECT = "DIRECT"
    TRANSFER = "TRANSFER"


class JourneyRoute(BaseModel):
    journey_type: JourneyType = JourneyType.DIRECT
    feed: str
    trip_id: str
    route_id: str
    route_name: str
    source_stop: str
    destination_stop: str
    stops_between: int
    departure_time: str | None = None
    arrival_time: str | None = None
    departure_display: DisplayTime | None = None
    arrival_display: DisplayTime | None = None
    duration_minutes: int | None = None
    shape_id: str | None = None
    quality: JourneyQuality | None = None


class WalkLeg(BaseModel):
    leg_type: LegType = LegType.WALK
    from_stop_id: str
    from_stop_name: str
    to_stop_id: str
    to_stop_name: str
    walk_time_minutes: int
    walk_distance_m: int
    complex_id: str


class TransferJourney(BaseModel):
    journey_type: JourneyType = JourneyType.TRANSFER
    transfer_stop: str
    first_leg: JourneyRoute
    second_leg: JourneyRoute
    total_duration: int
    transfer_wait: int
    walk_leg: WalkLeg | None = None
    quality: JourneyQuality | None = None
    third_leg: JourneyRoute | None = None
    transfer_stop_2: str | None = None
    transfer_wait_2: int | None = None


class JourneyResponse(BaseModel):
    success: bool
    narrative: JourneyNarrative | None = None
    routes: list[JourneyRoute]
    transfer_routes: list[TransferJourney] = []


class TripStop(BaseModel):
    stop_id: str
    stop_name: str
    stop_sequence: int
    arrival_time: str | None = None
    departure_time: str | None = None
    arrival_display: DisplayTime | None = None
    departure_display: DisplayTime | None = None
    stop_lat: float | None = None
    stop_lon: float | None = None


class TripStopsResponse(BaseModel):
    feed: str
    trip_id: str
    stops: list[TripStop]

