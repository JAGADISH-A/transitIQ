"""Persistent journey context model for conversational AI memory."""

from datetime import datetime
from pydantic import BaseModel


class JourneyStop(BaseModel):
    """A single stop within a journey's stop sequence."""

    stop_id: str
    stop_name: str
    stop_sequence: int


class PersistentJourneyContext(BaseModel):
    """Domain model representing the user's active journey.

    This is NOT an API response model. It is a persistent memory object
    stored server-side so the AI assistant can reference it across
    conversational turns without requiring the frontend to re-send context.

    Extensible by design — add fields as needed for future phases.
    """

    origin: str
    destination: str
    feed_name: str
    train_name: str
    train_number: str
    trip_id: str
    service_id: str
    departure_time: str
    arrival_time: str
    duration: int
    transfer_count: int
    selected_route: dict | None = None
    stop_sequence: list[JourneyStop]
    intermediate_stops: list[str]
    route_summary: str
    created_at: str
