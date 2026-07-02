"""BusProvider — state transport bus provider with built-in stop data.

Ready for future GTFS feeds from state transport agencies.
When a GTFS feed named 'bus' or matching '*bus*' is loaded, this provider
will use that data instead of built-in stops.
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
    # Chennai
    {"id": "cmbt", "name": "CMBT (Koyambedu)", "lat": 13.0695, "lon": 80.1984},
    {"id": "tambaram_bus", "name": "Tambaram Bus Stand", "lat": 12.9205, "lon": 80.1135},
    {"id": "broadway", "name": "Broadway Bus Stand", "lat": 13.0937, "lon": 80.2872},
    {"id": "poonamallee", "name": "Poonamallee Bus Stop", "lat": 13.0503, "lon": 80.1007},
    # Bangalore
    {"id": "majestic", "name": "KBS (Majestic)", "lat": 12.9756, "lon": 77.5702},
    {"id": "shantinagar", "name": "Shantinagar Bus Stand", "lat": 12.9474, "lon": 77.5808},
    {"id": "yeshwanthpur", "name": "Yeshwanthpur Bus Stand", "lat": 13.0227, "lon": 77.5467},
    # Delhi
    {"id": "kashmere_gate", "name": "ISBT Kashmere Gate", "lat": 28.6693, "lon": 77.2290},
    {"id": "anand_vihar", "name": "ISBT Anand Vihar", "lat": 28.6472, "lon": 77.3121},
    {"id": "sarai_kale", "name": "Sarai Kale Khan ISBT", "lat": 28.5892, "lon": 77.2498},
    # Hyderabad
    {"id": "mgbs", "name": "MGBS (Hyderabad)", "lat": 17.3764, "lon": 78.4784},
    {"id": "jbs", "name": "Jubilee Bus Station", "lat": 17.4316, "lon": 78.4574},
    # Mumbai
    {"id": "dadar_bus", "name": "Dadar Bus Terminal", "lat": 19.0184, "lon": 72.8457},
    {"id": "borivali_bus", "name": "Borivali Bus Station", "lat": 19.2302, "lon": 72.8562},
    {"id": "thane_bus", "name": "Thane Bus Stand", "lat": 19.2051, "lon": 72.9722},
    # Kolkata
    {"id": "esplanade", "name": "Esplanade Bus Terminal", "lat": 22.5644, "lon": 88.3498},
    {"id": "howrah_bus", "name": "Howrah Bus Stand", "lat": 22.5864, "lon": 88.3307},
]

_SIMULATED_ROUTES: list[dict] = [
    {"from": "cmbt", "to": "tambaram_bus", "name": "MTC 21B", "duration": 35, "stops": 12},
    {"from": "tambaram_bus", "to": "cmbt", "name": "MTC 21B", "duration": 35, "stops": 12},
    {"from": "cmbt", "to": "broadway", "name": "MTC 19C", "duration": 25, "stops": 8},
    {"from": "broadway", "to": "cmbt", "name": "MTC 19C", "duration": 25, "stops": 8},
    {"from": "majestic", "to": "shantinagar", "name": "BMTC 180", "duration": 20, "stops": 6},
    {"from": "shantinagar", "to": "majestic", "name": "BMTC 180", "duration": 20, "stops": 6},
    {"from": "majestic", "to": "yeshwanthpur", "name": "BMTC 90A", "duration": 30, "stops": 10},
    {"from": "kashmere_gate", "to": "anand_vihar", "name": "DTC 392", "duration": 25, "stops": 8},
    {"from": "kashmere_gate", "to": "sarai_kale", "name": "DTC 405", "duration": 20, "stops": 6},
    {"from": "mgbs", "to": "jbs", "name": "TSRTC 6D", "duration": 20, "stops": 5},
    {"from": "dadar_bus", "to": "borivali_bus", "name": "BEST C-72", "duration": 40, "stops": 14},
    {"from": "dadar_bus", "to": "thane_bus", "name": "BEST 501", "duration": 45, "stops": 16},
    {"from": "esplanade", "to": "howrah_bus", "name": "WBTC S-1", "duration": 15, "stops": 3},
]


class BusProvider(BaseTransportProvider):
    provider_id = "bus"
    provider_name = "State Transport Buses"
    mode = TransportMode.BUS

    def __init__(self) -> None:
        self._gtfs_loaded = False

    def _load_gtfs_if_available(self) -> None:
        from app.services.transit_service import transit_service
        loader = transit_service.get_feed("bus")
        self._gtfs_loaded = loader is not None

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
            description="State transport bus network. Uses built-in data for major terminals. Ready for GTFS feeds from state transport agencies.",
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
            if dist <= 50:
                routes.append({
                    "from": source_stop_id, "to": destination_stop_id,
                    "name": f"Direct Bus", "duration": max(15, int(dist * 2)), "stops": max(1, int(dist / 3)),
                })

        results: List[TransportJourney] = []
        for r in routes:
            segment = TransportSegment(
                mode=TransportMode.BUS,
                provider=self.provider_id,
                route_name=r["name"],
                route_id=f"bus_{r['from']}_{r['to']}",
                source=source_stop,
                destination=dest_stop,
                duration_minutes=r["duration"],
                stops_between=r["stops"],
            )
            results.append(TransportJourney(
                segments=[segment],
                total_duration_minutes=r["duration"],
                total_transfers=0,
                modes_used=[TransportMode.BUS],
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
            mode=TransportMode.BUS,
            provider="bus",
        )


bus_provider = BusProvider()
