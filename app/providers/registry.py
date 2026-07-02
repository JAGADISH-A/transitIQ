"""Provider registry — discovers and routes queries to transport providers."""

import logging
from typing import Dict, List

from app.models.transit import (
    TransportJourney,
    TransportMode,
    TransportStop,
    ProviderInfo,
)
from app.providers.base import BaseTransportProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, BaseTransportProvider] = {}

    def register(self, provider: BaseTransportProvider) -> None:
        self._providers[provider.provider_id] = provider
        logger.info(
            "[PROVIDER_REGISTRY] Registered: %s (%s) available=%s",
            provider.provider_id, provider.mode.value, provider.is_available(),
        )

    def get_provider(self, provider_id: str) -> BaseTransportProvider | None:
        return self._providers.get(provider_id)

    def list_providers(self) -> List[ProviderInfo]:
        return [p.get_info() for p in self._providers.values()]

    def available_providers(self) -> List[BaseTransportProvider]:
        return [p for p in self._providers.values() if p.is_available()]

    def search_stops_all(self, query: str) -> List[TransportStop]:
        results: List[TransportStop] = []
        seen: set[tuple[str, str]] = set()
        for provider in self._providers.values():
            if not provider.is_available():
                continue
            for stop in provider.search_stops(query):
                key = (stop.provider, stop.stop_id)
                if key not in seen:
                    seen.add(key)
                    results.append(stop)
        return results

    def find_journeys_across_providers(
        self,
        source_stop_id: str,
        destination_stop_id: str,
        departure_after: str | None = None,
    ) -> Dict[str, List[TransportJourney]]:
        results: Dict[str, List[TransportJourney]] = {}
        for provider in self.available_providers():
            try:
                journeys = provider.find_journeys(
                    source_stop_id, destination_stop_id, departure_after,
                )
                if journeys:
                    results[provider.provider_id] = journeys
            except Exception as exc:
                logger.warning(
                    "[PROVIDER_REGISTRY] %s.find_journeys failed: %s",
                    provider.provider_id, exc,
                )
        return results

    def get_stops_for_journey_planning(self) -> Dict[str, list[TransportStop]]:
        result: Dict[str, list[TransportStop]] = {}
        for provider in self.available_providers():
            stops = provider.get_stops_for_journey_planning()
            if stops:
                result[provider.provider_id] = stops
        return result


provider_registry = ProviderRegistry()
