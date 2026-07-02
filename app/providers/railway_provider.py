"""RailwayProvider — wraps existing TransitService as a TransportProvider."""

import logging
from typing import List

from app.models.schemas import StopResult
from app.models.transit import (
    TransportJourney,
    TransportMode,
    TransportSegment,
    TransportStop,
    ProviderInfo,
)
from app.providers.base import BaseTransportProvider
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)


class RailwayProvider(BaseTransportProvider):
    provider_id = "railways"
    provider_name = "Indian Railways"
    mode = TransportMode.RAIL

    def is_available(self) -> bool:
        return transit_service.is_loaded

    def get_info(self) -> ProviderInfo:
        s = transit_service.summary
        return ProviderInfo(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            mode=self.mode,
            available=self.is_available(),
            stop_count=s.get("stops", 0),
            data_source="gtfs",
            description="Indian Railways GTFS feed covering all major railway stations and train routes.",
        )

    def search_stops(self, query: str) -> List[TransportStop]:
        results = transit_service.search_stops(query)
        return [self._convert_stop(r, "railways") for r in results]

    def get_stop_by_id(self, stop_id: str) -> TransportStop | None:
        loader = transit_service.get_feed("railways")
        if loader is None:
            return None
        row = loader.get_stop_by_id(stop_id)
        if row is None:
            return None
        return TransportStop(
            stop_id=str(row.get("stop_id", "")),
            stop_name=str(row.get("stop_name", "")),
            lat=float(row.get("stop_lat", 0.0)),
            lon=float(row.get("stop_lon", 0.0)),
            mode=TransportMode.RAIL,
            provider=self.provider_id,
        )

    def find_journeys(
        self,
        source_stop_id: str,
        destination_stop_id: str,
        departure_after: str | None = None,
    ) -> List[TransportJourney]:
        journeys: List[TransportJourney] = []

        direct = transit_service.get_direct_journeys(
            source_stop_id, destination_stop_id, departure_after,
        )
        for j in direct:
            tj = self._convert_journey_route(j, TransportMode.RAIL)
            if tj:
                journeys.append(tj)

        transfers = transit_service.find_transfer_routes(
            source_stop_id, destination_stop_id, departure_after,
        )
        for t in transfers:
            tj = self._convert_transfer_journey(t)
            if tj:
                journeys.append(tj)

        two_transfers = transit_service.find_two_transfer_routes(
            source_stop_id, destination_stop_id, departure_after,
        )
        for t in two_transfers:
            tj = self._convert_transfer_journey(t)
            if tj:
                journeys.append(tj)

        return journeys

    def get_nearby_stops(
        self,
        lat: float,
        lon: float,
        radius_km: float = 2.0,
    ) -> List[TransportStop]:
        from app.models.schemas import NearbyStopResult
        results = transit_service.get_nearby_stops("railways", lat, lon, radius_km)
        return [
            TransportStop(
                stop_id=r.stop_id,
                stop_name=r.stop_name,
                lat=r.lat,
                lon=r.lon,
                mode=TransportMode.RAIL,
                provider=self.provider_id,
            )
            for r in results
        ]

    def get_stops_for_journey_planning(self) -> List[TransportStop]:
        results = transit_service.search_stops("")
        return [self._convert_stop(r, "railways") for r in results[:100]]

    @staticmethod
    def _convert_stop(r: StopResult, provider: str) -> TransportStop:
        return TransportStop(
            stop_id=r.stop_id,
            stop_name=r.stop_name,
            lat=r.lat,
            lon=r.lon,
            mode=TransportMode.RAIL,
            provider=provider,
        )

    @staticmethod
    def _convert_journey_route(
        j: "JourneyRoute",
        mode: TransportMode,
    ) -> TransportJourney | None:
        from app.models.schemas import JourneyRoute
        source_stop = TransportStop(
            stop_id=j.source_stop,
            stop_name=j.source_stop,
            lat=0.0, lon=0.0,
            mode=mode, provider=j.feed,
        )
        dest_stop = TransportStop(
            stop_id=j.destination_stop,
            stop_name=j.destination_stop,
            lat=0.0, lon=0.0,
            mode=mode, provider=j.feed,
        )
        segment = TransportSegment(
            mode=mode,
            provider=j.feed,
            route_name=j.route_name,
            route_id=j.route_id,
            trip_id=j.trip_id,
            source=source_stop,
            destination=dest_stop,
            departure_time=j.departure_time,
            arrival_time=j.arrival_time,
            duration_minutes=j.duration_minutes,
            stops_between=j.stops_between,
            shape_id=j.shape_id,
        )
        return TransportJourney(
            segments=[segment],
            total_duration_minutes=j.duration_minutes,
            total_transfers=0,
            modes_used=[mode],
            providers_used=[j.feed],
            quality=j.quality,
        )

    @staticmethod
    def _convert_transfer_journey(t: "TransferJourney") -> TransportJourney | None:
        from app.models.schemas import TransferJourney, JourneyType
        segments: list[TransportSegment] = []

        for leg, leg_mode in [
            (t.first_leg, TransportMode.RAIL),
            (t.second_leg, TransportMode.RAIL),
        ]:
            src = TransportStop(
                stop_id=leg.source_stop,
                stop_name=leg.source_stop,
                lat=0.0, lon=0.0,
                mode=leg_mode, provider=leg.feed,
            )
            dst = TransportStop(
                stop_id=leg.destination_stop,
                stop_name=leg.destination_stop,
                lat=0.0, lon=0.0,
                mode=leg_mode, provider=leg.feed,
            )
            segments.append(TransportSegment(
                mode=leg_mode,
                provider=leg.feed,
                route_name=leg.route_name,
                route_id=leg.route_id,
                trip_id=leg.trip_id,
                source=src, destination=dst,
                departure_time=leg.departure_time,
                arrival_time=leg.arrival_time,
                duration_minutes=leg.duration_minutes,
                stops_between=leg.stops_between,
                shape_id=leg.shape_id,
            ))

        if t.third_leg:
            leg3 = t.third_leg
            src3 = TransportStop(
                stop_id=leg3.source_stop, stop_name=leg3.source_stop,
                lat=0.0, lon=0.0, mode=TransportMode.RAIL, provider=leg3.feed,
            )
            dst3 = TransportStop(
                stop_id=leg3.destination_stop, stop_name=leg3.destination_stop,
                lat=0.0, lon=0.0, mode=TransportMode.RAIL, provider=leg3.feed,
            )
            segments.append(TransportSegment(
                mode=TransportMode.RAIL,
                provider=leg3.feed,
                route_name=leg3.route_name,
                route_id=leg3.route_id,
                trip_id=leg3.trip_id,
                source=src3, destination=dst3,
                departure_time=leg3.departure_time,
                arrival_time=leg3.arrival_time,
                duration_minutes=leg3.duration_minutes,
                stops_between=leg3.stops_between,
                shape_id=leg3.shape_id,
            ))

        all_modes = list({s.mode for s in segments})
        all_providers = list({s.provider for s in segments})
        return TransportJourney(
            segments=segments,
            total_duration_minutes=t.total_duration,
            total_transfers=len(segments) - 1,
            modes_used=all_modes,
            providers_used=all_providers,
            quality=t.quality,
        )


railway_provider = RailwayProvider()
