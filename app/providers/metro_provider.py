"""MetroProvider — metro/rapid transit provider with built-in stop data.

Ready for future GTFS feeds from metro agencies.
"""

import logging
import math
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
    # Chennai Metro
    {"id": "chennai_central_metro", "name": "Chennai Central Metro", "lat": 13.0831, "lon": 80.2695},
    {"id": "egmore_metro", "name": "Egmore Metro", "lat": 13.0759, "lon": 80.2576},
    {"id": "washermanpet", "name": "Washermanpet Metro", "lat": 13.1133, "lon": 80.2865},
    {"id": "t_nagar", "name": "T.Nagar Metro", "lat": 13.0400, "lon": 80.2349},
    {"id": "guindy", "name": "Guindy Metro", "lat": 13.0068, "lon": 80.2205},
    {"id": "airport_metro", "name": "Chennai Airport Metro", "lat": 12.9811, "lon": 80.1635},
    # Delhi Metro
    {"id": "new_delhi_metro", "name": "New Delhi Metro", "lat": 28.6427, "lon": 77.2193},
    {"id": "kashmere_gate_metro", "name": "Kashmere Gate Metro", "lat": 28.6690, "lon": 77.2280},
    {"id": "rajiv_chowk", "name": "Rajiv Chowk Metro", "lat": 28.6325, "lon": 77.2195},
    {"id": "central_secretariat", "name": "Central Secretariat Metro", "lat": 28.6150, "lon": 77.2090},
    # Bangalore Metro
    {"id": "majestic_metro", "name": "Majestic (Nadaprabhu Kempegowda) Metro", "lat": 12.9762, "lon": 77.5711},
    {"id": "mg_road_metro", "name": "MG Road Metro", "lat": 12.9716, "lon": 77.5946},
    {"id": "indiranagar", "name": "Indiranagar Metro", "lat": 12.9719, "lon": 77.6407},
    # Hyderabad Metro
    {"id": "ameerpet", "name": "Ameerpet Metro", "lat": 17.4352, "lon": 78.4414},
    {"id": "hi_tec_city", "name": "HITEC City Metro", "lat": 17.4474, "lon": 78.3779},
    {"id": "mg_bus_metro", "name": "MG Bus Station Metro", "lat": 17.3764, "lon": 78.4782},
    # Mumbai Metro
    {"id": "ghatkopar_metro", "name": "Ghatkopar Metro", "lat": 19.0887, "lon": 72.9089},
    {"id": "versova_metro", "name": "Versova Metro", "lat": 19.1353, "lon": 72.8222},
    {"id": "andheri_metro", "name": "Andheri Metro", "lat": 19.1196, "lon": 72.8460},
]

_SIMULATED_ROUTES: list[dict] = [
    # Chennai Metro - Blue Line
    {"from": "washermanpet", "to": "chennai_central_metro", "name": "Chennai Metro Blue", "duration": 5, "stops": 2},
    {"from": "chennai_central_metro", "to": "egmore_metro", "name": "Chennai Metro Blue", "duration": 3, "stops": 1},
    {"from": "egmore_metro", "to": "t_nagar", "name": "Chennai Metro Blue", "duration": 8, "stops": 3},
    {"from": "t_nagar", "to": "guindy", "name": "Chennai Metro Blue", "duration": 7, "stops": 2},
    {"from": "guindy", "to": "airport_metro", "name": "Chennai Metro Blue", "duration": 5, "stops": 1},
    # Delhi Metro - Yellow Line
    {"from": "kashmere_gate_metro", "to": "new_delhi_metro", "name": "Delhi Metro Yellow", "duration": 4, "stops": 1},
    {"from": "new_delhi_metro", "to": "rajiv_chowk", "name": "Delhi Metro Yellow", "duration": 3, "stops": 1},
    {"from": "rajiv_chowk", "to": "central_secretariat", "name": "Delhi Metro Yellow", "duration": 2, "stops": 1},
    # Bangalore Metro - Purple Line
    {"from": "majestic_metro", "to": "mg_road_metro", "name": "Bangalore Metro Purple", "duration": 5, "stops": 2},
    {"from": "mg_road_metro", "to": "indiranagar", "name": "Bangalore Metro Purple", "duration": 6, "stops": 2},
    # Hyderabad Metro - Red Line
    {"from": "ameerpet", "to": "hi_tec_city", "name": "Hyderabad Metro Red", "duration": 8, "stops": 3},
    {"from": "ameerpet", "to": "mg_bus_metro", "name": "Hyderabad Metro Red", "duration": 10, "stops": 4},
    # Mumbai Metro - Line 1
    {"from": "versova_metro", "to": "andheri_metro", "name": "Mumbai Metro Line 1", "duration": 4, "stops": 1},
    {"from": "andheri_metro", "to": "ghatkopar_metro", "name": "Mumbai Metro Line 1", "duration": 12, "stops": 5},
]


class MetroProvider(BaseTransportProvider):
    provider_id = "metro"
    provider_name = "City Metro Systems"
    mode = TransportMode.METRO

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
            description="Metro rail systems across major Indian cities. Covers Chennai, Delhi, Bangalore, Hyderabad, and Mumbai metro networks.",
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
            if dist <= 30:
                routes.append({
                    "from": source_stop_id, "to": destination_stop_id,
                    "name": f"Metro Line", "duration": max(5, int(dist * 2.5)), "stops": max(1, int(dist / 2)),
                })

        results: List[TransportJourney] = []
        for r in routes:
            segment = TransportSegment(
                mode=TransportMode.METRO,
                provider=self.provider_id,
                route_name=r["name"],
                route_id=f"metro_{r['from']}_{r['to']}",
                source=source_stop,
                destination=dest_stop,
                duration_minutes=r["duration"],
                stops_between=r["stops"],
            )
            results.append(TransportJourney(
                segments=[segment],
                total_duration_minutes=r["duration"],
                total_transfers=0,
                modes_used=[TransportMode.METRO],
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
            mode=TransportMode.METRO,
            provider="metro",
        )


metro_provider = MetroProvider()
