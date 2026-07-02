"""Deterministic station intelligence service.

Computes station profiles from GTFS metadata, inferring characteristics like
junction, terminal, and major station status from available data.
"""

import logging
from typing import Any

from app.models.conversation import StationProfile
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)


class StationIntelligence:
    """Analyze station characteristics using GTFS data and naming conventions."""

    JUNCTION_KEYWORDS = ["JUNCTION", "JL", "JN"]
    TERMINAL_KEYWORDS = ["TERMINAL", "TERMINUS", "TERMINI", "CANT", "CANTT"]
    MAJOR_KEYWORDS = ["CENTRAL", "STATION", "TERMINAL", "JUNCTION"]

    def get_station_profile(
        self,
        station_name: str = "",
        station_id: str = "",
        feed: str | None = None,
    ) -> StationProfile:
        """Build a deterministic station profile from available data."""
        profile = StationProfile()
        profile.station_name = station_name

        self._classify_station_from_name(profile)
        self._enrich_from_gtfs(profile, station_id, feed)

        logger.info(
            "[STATION_INTELLIGENCE] Profile generated: %s junction=%s terminal=%s major=%s",
            profile.station_name, profile.is_junction, profile.is_terminal,
            profile.is_major_station,
        )
        return profile

    def _classify_station_from_name(self, profile: StationProfile) -> None:
        """Classify station based on naming conventions."""
        name_upper = profile.station_name.upper()

        for kw in self.JUNCTION_KEYWORDS:
            if kw in name_upper:
                profile.is_junction = True
                break

        for kw in self.TERMINAL_KEYWORDS:
            if kw in name_upper:
                profile.is_terminal = True
                break

        for kw in self.MAJOR_KEYWORDS:
            if kw in name_upper:
                profile.is_major_station = True
                break

    def _enrich_from_gtfs(
        self,
        profile: StationProfile,
        station_id: str | None,
        feed: str | None,
    ) -> None:
        """Enrich profile with GTFS station data."""
        if not feed or not transit_service.is_loaded:
            return

        loader = transit_service.get_feed(feed)
        if loader is None or loader.stops is None:
            return

        stop_row = None
        if station_id:
            matches = loader.stops[loader.stops["stop_id"].astype(str) == str(station_id)]
            if not matches.empty:
                stop_row = matches.iloc[0]

        if stop_row is None and profile.station_name:
            name_matches = loader.stops[
                loader.stops["stop_name"].str.upper() == profile.station_name.upper()
            ]
            if not name_matches.empty:
                stop_row = name_matches.iloc[0]

        if stop_row is None:
            name_matches = loader.stops[
                loader.stops["stop_name"].str.contains(
                    profile.station_name.upper(), case=False, na=False
                )
            ]
            if not name_matches.empty:
                stop_row = name_matches.iloc[0]

        if stop_row is not None:
            profile.station_code = str(stop_row.get("stop_id", ""))
            profile.station_name = str(stop_row.get("stop_name", profile.station_name))

            lat = stop_row.get("stop_lat")
            lon = stop_row.get("stop_lon")
            if lat and lon:
                try:
                    profile.latitude = float(lat)
                    profile.longitude = float(lon)
                except (ValueError, TypeError):
                    pass

        if profile.station_name and not profile.is_junction:
            profile._is_junction = self._detect_junction_from_routes(
                profile.station_code or profile.station_name, feed
            )

        if profile.station_code or profile.station_name:
            route_count = self._count_connecting_routes(profile, feed)
            if route_count >= 3:
                profile.is_junction = True
                profile.is_major_station = True

        platform_estimate = self._estimate_platforms(profile)
        if platform_estimate:
            profile.estimated_platform_count = platform_estimate

    def _detect_junction_from_routes(
        self,
        station_id: str,
        feed: str | None,
    ) -> bool:
        """Detect if a station serves as a junction by checking how many
        distinct routes pass through it.
        """
        if not feed or not transit_service.is_loaded:
            return False

        loader = transit_service.get_feed(feed)
        if loader is None or loader.stop_times is None or loader.trips is None:
            return False

        try:
            stop_times_for_stop = loader.stop_times[
                loader.stop_times["stop_id"].astype(str) == str(station_id)
            ]
            if stop_times_for_stop.empty:
                return False

            trip_ids = stop_times_for_stop["trip_id"].unique()
            matching_trips = loader.trips[
                loader.trips["trip_id"].isin(trip_ids)
            ]
            if matching_trips.empty:
                return False

            distinct_route_ids = matching_trips["route_id"].nunique()
            return distinct_route_ids >= 3
        except Exception as exc:
            logger.debug("Could not detect junction status: %s", exc)
            return False

    def _count_connecting_routes(
        self,
        profile: StationProfile,
        feed: str | None,
    ) -> int:
        """Count distinct routes serving this station."""
        sid = profile.station_code or profile.station_name
        if not feed or not sid or not transit_service.is_loaded:
            return 0

        loader = transit_service.get_feed(feed)
        if loader is None or loader.stop_times is None or loader.trips is None:
            return 0

        try:
            matches = loader.stop_times[
                loader.stop_times["stop_id"].astype(str) == str(sid)
            ]
            if matches.empty:
                matches = loader.stop_times[
                    loader.stop_times["stop_id"].str.contains(
                        str(sid), case=False, na=False
                    )
                ]
            if matches.empty:
                return 0

            trip_ids = matches["trip_id"].unique()
            matching_trips = loader.trips[
                loader.trips["trip_id"].isin(trip_ids)
            ]
            if matching_trips.empty:
                return 0

            route_ids = matching_trips["route_id"].unique()
            connected_routes = [str(r) for r in route_ids]
            profile.connecting_routes = connected_routes[:10]
            return len(route_ids)
        except Exception as exc:
            logger.debug("Could not count routes: %s", exc)
            return 0

    @staticmethod
    def _estimate_platforms(profile: StationProfile) -> int | None:
        """Estimate platform count based on station classification."""
        if profile.is_major_station and profile.is_junction:
            return 8
        if profile.is_junction:
            return 5
        if profile.is_terminal:
            return 4
        if profile.is_major_station:
            return 3
        return None


station_intelligence = StationIntelligence()
