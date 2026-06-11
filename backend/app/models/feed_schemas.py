"""Pydantic models for GTFS feed metadata responses."""

from pydantic import BaseModel, ConfigDict


class FeedInfo(BaseModel):
    """Information about a single GTFS feed."""

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str


class FeedSummary(BaseModel):
    """Summary counts for one GTFS feed."""

    model_config = ConfigDict(extra="forbid")

    feed_name: str
    stops: int
    routes: int
    trips: int
    stop_times: int
    shapes: int


class AvailableFeedsResponse(BaseModel):
    """Response model for listing available GTFS feeds."""

    model_config = ConfigDict(extra="forbid")

    feeds: list[str]
