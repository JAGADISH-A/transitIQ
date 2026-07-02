"""Unified transport data models for multi-modal transit."""

from enum import Enum
from pydantic import BaseModel


class TransportMode(str, Enum):
    RAIL = "RAIL"
    BUS = "BUS"
    METRO = "METRO"
    FERRY = "FERRY"
    WALK = "WALK"
    TRAM = "TRAM"
    OTHER = "OTHER"


class TransportStop(BaseModel):
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    mode: TransportMode
    provider: str
    stop_code: str | None = None
    zone: str | None = None
    wheelchair_accessible: bool | None = None


class TransportSegment(BaseModel):
    mode: TransportMode
    provider: str
    route_name: str
    route_id: str
    trip_id: str | None = None
    source: TransportStop
    destination: TransportStop
    departure_time: str | None = None
    arrival_time: str | None = None
    duration_minutes: int | None = None
    stops_between: int = 0
    distance_km: float | None = None
    shape_id: str | None = None


class TransportJourney(BaseModel):
    segments: list[TransportSegment]
    total_duration_minutes: int | None = None
    total_transfers: int = 0
    modes_used: list[TransportMode] = []
    providers_used: list[str] = []
    quality: "JourneyQuality | None" = None
    narrative_summary: str | None = None


class TransportPreference(BaseModel):
    preferred_modes: list[TransportMode] = []
    avoided_modes: list[TransportMode] = []
    max_transfers: int | None = None
    max_walk_minutes: int | None = None
    accessibility_required: bool = False
    optimized_for: str = "balanced"


class ProviderInfo(BaseModel):
    provider_id: str
    provider_name: str
    mode: TransportMode
    available: bool
    stop_count: int
    data_source: str
    description: str


class TransferSuggestion(BaseModel):
    from_provider: str
    to_provider: str
    from_stop: TransportStop
    to_stop: TransportStop
    walk_distance_m: int
    walk_time_minutes: int
    transfer_quality: str = "unknown"


from app.models.schemas import JourneyQuality
