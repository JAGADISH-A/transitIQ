"""Multi-modal journey planner — combines transport providers for end-to-end routing."""

import logging
from typing import List, Tuple

from app.models.transit import (
    TransportJourney,
    TransportMode,
    TransportPreference,
    TransportSegment,
    TransportStop,
    TransferSuggestion,
)
from app.providers.registry import provider_registry
from app.utils.geo_utils import haversine

logger = logging.getLogger(__name__)

_MAX_WALK_DISTANCE_M = 1000
_MAX_TRANSFER_STOPS = 5


class MultiModalPlanner:
    def plan(
        self,
        source_query: str,
        destination_query: str,
        preferences: TransportPreference | None = None,
        departure_after: str | None = None,
    ) -> List[TransportJourney]:
        prefs = preferences or TransportPreference()
        results: List[TransportJourney] = []

        # Step 1: Find stops across all providers for source and destination
        source_stops = provider_registry.search_stops_all(source_query)
        dest_stops = provider_registry.search_stops_all(destination_query)

        if not source_stops or not dest_stops:
            return []

        # Step 2: Try single-provider journeys (direct within same provider)
        results.extend(self._find_single_provider_journeys(
            source_stops, dest_stops, prefs, departure_after,
        ))

        # Step 3: Try multi-modal journeys via transfer points
        results.extend(self._find_multi_modal_journeys(
            source_stops, dest_stops, prefs, departure_after,
        ))

        # Step 4: Filter by preferences
        results = self._filter_by_preferences(results, prefs)

        # Step 5: Sort by quality/duration
        results.sort(key=lambda j: (
            j.total_duration_minutes or 999999,
            j.total_transfers,
        ))

        return results[:10]

    def _find_single_provider_journeys(
        self,
        source_stops: List[TransportStop],
        dest_stops: List[TransportStop],
        prefs: TransportPreference,
        departure_after: str | None,
    ) -> List[TransportJourney]:
        results: List[TransportJourney] = []
        # Group stops by provider
        source_by_provider: dict[str, List[TransportStop]] = {}
        for s in source_stops:
            source_by_provider.setdefault(s.provider, []).append(s)
        dest_by_provider: dict[str, List[TransportStop]] = {}
        for d in dest_stops:
            dest_by_provider.setdefault(d.provider, []).append(d)

        shared_providers = set(source_by_provider.keys()) & set(dest_by_provider.keys())
        for pid in shared_providers:
            provider = provider_registry.get_provider(pid)
            if not provider or not provider.is_available():
                continue
            if prefs.avoided_modes and provider.mode in prefs.avoided_modes:
                continue
            for src in source_by_provider[pid][:_MAX_TRANSFER_STOPS]:
                for dst in dest_by_provider[pid][:_MAX_TRANSFER_STOPS]:
                    try:
                        journeys = provider.find_journeys(src.stop_id, dst.stop_id, departure_after)
                        results.extend(journeys)
                    except Exception as exc:
                        logger.debug("Provider %s journey find failed: %s", pid, exc)
        return results

    def _find_multi_modal_journeys(
        self,
        source_stops: List[TransportStop],
        dest_stops: List[TransportStop],
        prefs: TransportPreference,
        departure_after: str | None,
    ) -> List[TransportJourney]:
        results: List[TransportJourney] = []
        providers = provider_registry.available_providers()

        for first_provider in providers:
            if prefs.avoided_modes and first_provider.mode in prefs.avoided_modes:
                continue
            if not first_provider.is_available():
                continue

            # Try first-provider journey from source to some intermediate point
            for src in source_stops:
                if src.provider != first_provider.provider_id:
                    continue
                first_leg_stops = first_provider.get_stops_for_journey_planning()
                for mid in first_leg_stops:
                    if mid.stop_id == src.stop_id:
                        continue
                    try:
                        first_legs = first_provider.find_journeys(
                            src.stop_id, mid.stop_id, departure_after,
                        )
                    except Exception:
                        continue

                    for first_leg in first_legs:
                        # Try second-provider journey from intermediate to destination
                        for second_provider in providers:
                            if second_provider.provider_id == first_provider.provider_id:
                                continue
                            if prefs.avoided_modes and second_provider.mode in prefs.avoided_modes:
                                continue
                            if not second_provider.is_available():
                                continue

                            # Find a transfer point: mid stop should be near a stop in second provider
                            nearby = second_provider.get_nearby_stops(
                                mid.lat, mid.lon, radius_km=1.0,
                            )
                            for transfer_stop in nearby:
                                for dst in dest_stops:
                                    if dst.provider != second_provider.provider_id:
                                        continue
                                    if transfer_stop.stop_id == dst.stop_id:
                                        continue
                                    try:
                                        second_legs = second_provider.find_journeys(
                                            transfer_stop.stop_id, dst.stop_id, departure_after,
                                        )
                                    except Exception:
                                        continue

                                    for second_leg in second_legs:
                                        combined = self._combine_journeys(
                                            first_leg, second_leg,
                                        )
                                        if combined:
                                            results.append(combined)
        return results

    @staticmethod
    def _combine_journeys(
        first: TransportJourney,
        second: TransportJourney,
    ) -> TransportJourney | None:
        if not first.segments or not second.segments:
            return None
        all_segments = first.segments + second.segments
        all_modes = list(set(s.mode for s in all_segments))
        all_providers = list(set(s.provider for s in all_segments))
        total_duration = (first.total_duration_minutes or 0) + (second.total_duration_minutes or 0)
        transfers = first.total_transfers + second.total_transfers + 1
        return TransportJourney(
            segments=all_segments,
            total_duration_minutes=total_duration,
            total_transfers=transfers,
            modes_used=all_modes,
            providers_used=all_providers,
        )

    @staticmethod
    def _filter_by_preferences(
        journeys: List[TransportJourney],
        prefs: TransportPreference,
    ) -> List[TransportJourney]:
        if not prefs.avoided_modes and not prefs.preferred_modes and prefs.max_transfers is None:
            return journeys

        filtered: List[TransportJourney] = []
        for j in journeys:
            if prefs.avoided_modes:
                if any(m in prefs.avoided_modes for m in j.modes_used):
                    continue
            if prefs.preferred_modes:
                if not all(m in prefs.preferred_modes for m in j.modes_used):
                    continue
            if prefs.max_transfers is not None:
                if j.total_transfers > prefs.max_transfers:
                    continue
            filtered.append(j)
        return filtered

    def suggest_transfers(
        self,
        source_stop: TransportStop,
        destination_stop: TransportStop,
    ) -> List[TransferSuggestion]:
        suggestions: List[TransferSuggestion] = []
        providers = provider_registry.available_providers()

        for provider in providers:
            if provider.provider_id == source_stop.provider:
                continue
            nearby = provider.get_nearby_stops(
                source_stop.lat, source_stop.lon, radius_km=1.0,
            )
            for ns in nearby:
                if ns.stop_id == source_stop.stop_id:
                    continue
                dist = haversine(source_stop.lat, source_stop.lon, ns.lat, ns.lon)
                walk_time = int(dist * 12)
                suggestions.append(TransferSuggestion(
                    from_provider=source_stop.provider,
                    to_provider=provider.provider_id,
                    from_stop=source_stop,
                    to_stop=ns,
                    walk_distance_m=int(dist * 1000),
                    walk_time_minutes=walk_time,
                    transfer_quality="good" if dist <= 0.5 else "moderate",
                ))
        return suggestions[:5]

    def find_first_last_mile(
        self,
        main_stop: TransportStop,
        query: str,
        preferences: TransportPreference | None = None,
    ) -> List[TransportJourney]:
        results: List[TransportJourney] = []
        prefs = preferences or TransportPreference()
        providers = provider_registry.available_providers()

        for provider in providers:
            if provider.provider_id == main_stop.provider:
                continue
            if prefs.avoided_modes and provider.mode in prefs.avoided_modes:
                continue
            nearby_stops = provider.search_stops(query)
            for ns in nearby_stops:
                try:
                    journeys = provider.find_journeys(ns.stop_id, main_stop.stop_id)
                    results.extend(journeys)
                except Exception:
                    continue
        return results


multi_modal_planner = MultiModalPlanner()
