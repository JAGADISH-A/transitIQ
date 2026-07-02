"""Abstract base class for all transport providers."""

from abc import ABC, abstractmethod
from typing import List

from app.models.transit import (
    TransportJourney,
    TransportMode,
    TransportStop,
    ProviderInfo,
)


class BaseTransportProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def mode(self) -> TransportMode: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_info(self) -> ProviderInfo: ...

    @abstractmethod
    def search_stops(self, query: str) -> List[TransportStop]: ...

    @abstractmethod
    def get_stop_by_id(self, stop_id: str) -> TransportStop | None: ...

    def find_journeys(
        self,
        source_stop_id: str,
        destination_stop_id: str,
        departure_after: str | None = None,
    ) -> List[TransportJourney]:
        return []

    def get_nearby_stops(
        self,
        lat: float,
        lon: float,
        radius_km: float = 2.0,
    ) -> List[TransportStop]:
        return []

    def get_stops_for_journey_planning(self) -> List[TransportStop]:
        return []
