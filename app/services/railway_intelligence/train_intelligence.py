"""Deterministic train intelligence service.

Computes train profiles from GTFS metadata and Indian Railways train number
conventions without LLM involvement.
"""

import logging
from typing import Any

from app.models.conversation import TrainProfile
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)


class TrainIntelligence:
    """Analyze train characteristics using GTFS data and railway conventions."""

    def get_train_profile(
        self,
        train_number: str = "",
        train_name: str = "",
        feed: str | None = None,
        trip_id: str | None = None,
        route_id: str | None = None,
    ) -> TrainProfile:
        """Build a deterministic train profile from available data."""
        profile = TrainProfile()
        profile.train_number = train_number
        profile.train_name = train_name

        self._classify_train_type(profile)
        self._enrich_from_gtfs(profile, feed, trip_id, route_id)
        self._compute_major_stops(profile, feed, trip_id)

        logger.info(
            "[TRAIN_INTELLIGENCE] Profile generated: %s (%s) type=%s",
            profile.train_number, profile.train_name, profile.train_type,
        )
        return profile

    def _classify_train_type(self, profile: TrainProfile) -> None:
        """Classify train type using Indian Railways numbering conventions.

        Number ranges (Indian Railways):
          12xxx    — Shatabdi/JanShatabdi/GaribRath/Duronto/Rajdhani (premium)
          13xxx-19xxx — Superfast Express
          2xxxx-4xxxx — Mail/Express
          5xxxx-6xxxx — Passenger
          7xxxx      — Suburban
          8xxxx      — Special/Holiday
          0xxxx      — Special
        """
        num_str = profile.train_number.strip()
        if not num_str or not num_str.isdigit():
            profile.train_type = "Express"
            profile.service_category = "Long-distance"
            profile.is_express = True
            return

        num = int(num_str[:5]) if len(num_str) >= 5 else int(num_str)

        if 12001 <= num <= 12099:
            profile.train_type = "Shatabdi"
            profile.service_category = "Intercity"
            profile.is_superfast = True
        elif 12101 <= num <= 12199:
            profile.train_type = "Jan Shatabdi"
            profile.service_category = "Intercity"
            profile.is_superfast = True
        elif 12201 <= num <= 12258:
            profile.train_type = "Garib Rath"
            profile.service_category = "Long-distance"
            profile.is_superfast = True
        elif 12259 <= num <= 12279:
            profile.train_type = "Duronto"
            profile.service_category = "Long-distance"
            profile.is_superfast = True
        elif 12280 <= num <= 12299:
            profile.train_type = "Garib Rath"
            profile.service_category = "Long-distance"
            profile.is_superfast = True
        elif 12301 <= num <= 12499:
            profile.train_type = "Rajdhani"
            profile.service_category = "Long-distance"
            profile.is_superfast = True
        elif 12501 <= num <= 12799:
            profile.train_type = "Superfast Express"
            profile.service_category = "Long-distance"
            profile.is_superfast = True
        elif 12801 <= num <= 12999:
            profile.train_type = "Tejas Express"
            profile.service_category = "Intercity"
            profile.is_superfast = True
        elif 13001 <= num <= 13999:
            profile.train_type = "Humsafar"
            profile.service_category = "Long-distance"
            profile.is_superfast = True
        elif 10000 <= num <= 19999:
            profile.train_type = "Superfast Express"
            profile.service_category = "Long-distance"
            profile.is_superfast = True
        elif 20000 <= num <= 49999:
            profile.train_type = "Express"
            profile.service_category = "Long-distance"
            profile.is_express = True
        elif 50000 <= num <= 69999:
            profile.train_type = "Passenger"
            profile.service_category = "Local"
        elif 70000 <= num <= 79999:
            profile.train_type = "Suburban"
            profile.service_category = "Suburban"
        elif 80000 <= num <= 89999:
            profile.train_type = "Special"
            profile.service_category = "Special"
        else:
            profile.train_type = "Express"
            profile.service_category = "Long-distance"
            profile.is_express = True

    def _enrich_from_gtfs(
        self,
        profile: TrainProfile,
        feed: str | None,
        trip_id: str | None,
        route_id: str | None,
    ) -> None:
        """Enrich profile with GTFS route metadata."""
        if not feed or not transit_service.is_loaded:
            return

        loader = transit_service.get_feed(feed)
        if loader is None:
            return

        if route_id and loader.routes is not None:
            route_row = loader.routes[loader.routes["route_id"] == route_id]
            if not route_row.empty:
                row = route_row.iloc[0]
                if not profile.train_name and "route_long_name" in row:
                    profile.train_name = str(row["route_long_name"])
                if not profile.train_number and "route_short_name" in row:
                    profile.train_number = str(row["route_short_name"])

        if trip_id and loader.trips is not None:
            trip_row = loader.trips[loader.trips["trip_id"] == trip_id]
            if not trip_row.empty:
                row = trip_row.iloc[0]
                if not route_id and "route_id" in row:
                    route_id = str(row["route_id"])
                    self._enrich_from_gtfs(profile, feed, None, route_id)

        if trip_id and loader.stop_times is not None:
            try:
                stops_df = loader.stop_times[loader.stop_times["trip_id"] == trip_id].copy()
                if not stops_df.empty:
                    stops_df["stop_sequence"] = stops_df["stop_sequence"].astype(int)
                    stops_df = stops_df.sort_values("stop_sequence")
                    profile.stop_count = len(stops_df)

                    if loader.stops is not None:
                        merged = stops_df.merge(loader.stops, on="stop_id", how="left")
                        profile.terminal_stations = []
                        if not merged.empty:
                            first_stop = merged.iloc[0]
                            last_stop = merged.iloc[-1]
                            profile.terminal_stations.append(
                                str(first_stop.get("stop_name", ""))
                            )
                            profile.terminal_stations.append(
                                str(last_stop.get("stop_name", ""))
                            )

                    if "arrival_time" in stops_df.columns and "departure_time" in stops_df.columns:
                        first_dep = stops_df["departure_time"].iloc[0]
                        last_arr = stops_df["arrival_time"].iloc[-1]
                        if (
                            isinstance(first_dep, str)
                            and isinstance(last_arr, str)
                            and first_dep.strip()
                            and last_arr.strip()
                            and first_dep != "nan"
                            and last_arr != "nan"
                        ):
                            try:
                                fh, fm = map(int, first_dep.split(":")[:2])
                                lh, lm = map(int, last_arr.split(":")[:2])
                                duration = (lh * 60 + lm) - (fh * 60 + fm)
                                if duration > 0:
                                    profile.duration_min = duration
                            except (ValueError, IndexError):
                                pass
            except Exception as exc:
                logger.debug("Could not compute stop data: %s", exc)

    def _compute_major_stops(
        self,
        profile: TrainProfile,
        feed: str | None,
        trip_id: str | None,
    ) -> None:
        """Identify major stops along the train's route."""
        if not feed or not trip_id or not transit_service.is_loaded:
            return

        loader = transit_service.get_feed(feed)
        if loader is None or loader.stop_times is None or loader.stops is None:
            return

        try:
            stops_df = loader.stop_times[loader.stop_times["trip_id"] == trip_id].copy()
            if stops_df.empty:
                return

            stops_df["stop_sequence"] = stops_df["stop_sequence"].astype(int)
            stops_df = stops_df.sort_values("stop_sequence")

            merged = stops_df.merge(loader.stops, on="stop_id", how="left")

            major_keywords = [
                "JUNCTION", "JL", "JN", "CANT", "CANTT", "TERMINAL",
                "TERMINUS", "CENTRAL", "STATION",
            ]
            major_stops = []
            for _, row in merged.iterrows():
                name = str(row.get("stop_name", ""))
                for kw in major_keywords:
                    if kw in name.upper():
                        major_stops.append(name)
                        break

            if major_stops:
                profile.major_stops = major_stops[:10]
        except Exception as exc:
            logger.debug("Could not compute major stops: %s", exc)


train_intelligence = TrainIntelligence()
