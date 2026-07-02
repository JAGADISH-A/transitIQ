"""FerryProvider — ferry/water transport provider with built-in stop data.

Ready for future GTFS feeds from ferry agencies.
"""

import logging
from typing import List

from app.models.transit import (
    TransportJourney,
    TransportMode,
    TransportSegment,
    TransportStop,
    ProviderInfo,
)
from app.providers.base import BaseTransportProvider
from app.utils.geo_utils import haversine

logger = logging.getLogger(__name__)

_BUILTIN_STOPS: list[dict] = [
    # Mumbai
    {"id": "gateway_of_india", "name": "Gateway of India Ferry", "lat": 18.9219, "lon": 72.8346},
    {"id": "elephanta", "name": "Elephanta Island Ferry", "lat": 18.9685, "lon": 72.9277},
    {"id": "mazagaon", "name": "Mazagaon Ferry", "lat": 18.9650, "lon": 72.8520},
    # Kolkata
    {"id": "howrah_ferry", "name": "Howrah Ferry Terminal", "lat": 22.5851, "lon": 88.3305},
    {"id": "kolkata_ferry", "name": "Kolkata Ferry Terminal", "lat": 22.5726, "lon": 88.3475},
    # Kochi
    {"id": "fort_kochi", "name": "Fort Kochi Ferry", "lat": 9.9658, "lon": 76.2413},
    {"id": "vypin", "name": "Vypin Ferry Terminal", "lat": 10.0000, "lon": 76.2375},
    # Varanasi
    {"id": "varanasi_ghat", "name": "Varanasi Ghat Ferry", "lat": 25.3085, "lon": 83.0110},
    {"id": "ramnagar", "name": "Ramnagar Ferry", "lat": 25.2788, "lon": 83.0360},
]

_SIMULATED_ROUTES: list[dict] = [
    {"from": "gateway_of_india", "to": "elephanta", "name": "Elephanta Ferry", "duration": 60, "stops": 0},
    {"from": "elephanta", "to": "gateway_of_india", "name": "Elephanta Ferry", "duration": 60, "stops": 0},
    {"from": "gateway_of_india", "to": "mazagaon", "name": "Harbor Ferry", "duration": 15, "stops": 0},
    {"from": "howrah_ferry", "to": "kolkata_ferry", "name": "Hooghly Ferry", "duration": 10, "stops": 0},
    {"from": "kolkata_ferry", "to": "howrah_ferry", "name": "Hooghly Ferry", "duration": 10, "stops": 0},
    {"from": "fort_kochi", "to": "vypin", "name": "Kochi Water Metro", "duration": 25, "stops": 2},
    {"from": "vypin", "to": "fort_kochi", "name": "Kochi Water Metro", "duration": 25, "stops": 2},
    {"from": "varanasi_ghat", "to": "ramnagar", "name": "Ganga Ferry", "duration": 15, "stops": 0},
    {"from": "ramnagar", "to": "varanasi_ghat", "name": "Ganga Ferry", "duration": 15, "stops": 0},
]


class FerryProvider(BaseTransportProvider):
    provider_id = "ferry"
    provider_name = "Ferry & Water Transport"
    mode = TransportMode.FERRY

    def is_available(self) -> bool:
        return True

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            mode=self.mode,
            available=True,
            stop_count=len(_BUILTIN_STOPS),
            data_source="built-in",
            description="Ferry and water transport services across coastal cities and rivers. Covers Mumbai, Kolkata, Kochi, and Varanasi.",
        )

    def search_stops(self, query: str) -> List[TransportStop]:
        q = query.lower().strip()
        results: List[TransportStop] = []
        for s in _BUILTIN_STOPS:
            if q in s["name"].lower() or q in s["id"].lower():
                results.append(self._make_stop(s))
        return results[:10]

    def get_stop_by_id(self, stop_id: str) -> TransportStop | None:
        for s in _BUILTIN_STOPS:
            if s["id"] == stop_id:
                return self._make_stop(s)
        return None

    def find_journeys(
        self,
        source_stop_id: str,
        destination_stop_id: str,
        departure_after: str | None = None,
    ) -> List[TransportJourney]:
        source_stop = self.get_stop_by_id(source_stop_id)
        dest_stop = self.get_stop_by_id(destination_stop_id)
        if not source_stop or not dest_stop:
            return []

        routes = []
        for r in _SIMULATED_ROUTES:
            if r["from"] == source_stop_id and r["to"] == destination_stop_id:
                routes.append(r)

        if not routes:
            dist = haversine(source_stop.lat, source_stop.lon, dest_stop.lat, dest_stop.lon)
            if dist <= 20:
                routes.append({
                    "from": source_stop_id, "to": destination_stop_id,
                    "name": "Ferry Service", "duration": max(10, int(dist * 5)), "stops": 0,
                })

        results: List[TransportJourney] = []
        for r in routes:
            segment = TransportSegment(
                mode=TransportMode.FERRY,
                provider=self.provider_id,
                route_name=r["name"],
                route_id=f"ferry_{r['from']}_{r['to']}",
                source=source_stop,
                destination=dest_stop,
                duration_minutes=r["duration"],
                stops_between=r["stops"],
            )
            results.append(TransportJourney(
                segments=[segment],
                total_duration_minutes=r["duration"],
                total_transfers=0,
                modes_used=[TransportMode.FERRY],
                providers_used=[self.provider_id],
            ))
        return results

    def get_nearby_stops(
        self,
        lat: float,
        lon: float,
        radius_km: float = 2.0,
    ) -> List[TransportStop]:
        results: List[TransportStop] = []
        for s in _BUILTIN_STOPS:
            dist = haversine(lat, lon, s["lat"], s["lon"])
            if dist <= radius_km:
                results.append(self._make_stop(s))
        results.sort(key=lambda r: haversine(lat, lon, r.lat, r.lon))
        return results[:10]

    def get_stops_for_journey_planning(self) -> List[TransportStop]:
        return [self._make_stop(s) for s in _BUILTIN_STOPS]

    @staticmethod
    def _make_stop(s: dict) -> TransportStop:
        return TransportStop(
            stop_id=s["id"],
            stop_name=s["name"],
            lat=s["lat"],
            lon=s["lon"],
            mode=TransportMode.FERRY,
            provider="ferry",
        )


ferry_provider = FerryProvider()
