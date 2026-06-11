"""Transit service facade for GTFS loading and stop search."""

import logging
import math
from typing import Dict, List, Optional
import pandas as pd

from app.models.schemas import NearbyStopResult, ShapePoint, StopResult, TripResult, TripRoute, TransferOption, TripResponse
from app.services.feed_registry import FeedRegistry
from app.services.gtfs_loader import GTFSLoader
from app.services.stop_search import StopSearch
from app.utils.geo_utils import haversine


class TransitService:
    """Central service for GTFS access and stop searching.

    This class acts as the single source of truth for GTFS-related operations.
    API routes should use this service instead of interacting with the loader
    directly.
    """

    def __init__(self) -> None:
        """Initialize the service with internal GTFS loader and stop search state."""
        self.logger = logging.getLogger(__name__)
        self._gtfs_loader: Optional[GTFSLoader] = None
        self._stop_search: Optional[StopSearch] = None
        self._data_path: Optional[str] = None
        self._feeds: Dict[str, GTFSLoader] = {}

    @property
    def is_loaded(self) -> bool:
        """Return whether the GTFS data has been loaded."""
        return self._gtfs_loader is not None and self._stop_search is not None

    @property
    def summary(self) -> Dict[str, int]:
        """Return a summary of the currently loaded GTFS feed."""
        if not self.is_loaded or self._gtfs_loader is None:
            return {"stops": 0, "routes": 0, "trips": 0, "stop_times": 0, "shapes": 0}
        return self._gtfs_loader.summary()

    def load(self, data_path: str) -> "TransitService":
        """Load GTFS data from the provided directory.

        Args:
            data_path: Path to the GTFS feed directory.

        Returns:
            The current service instance for chaining.

        Raises:
            ValueError: If the data path is not a valid string.
            RuntimeError: If the GTFS data cannot be loaded.
        """
        try:
            if not isinstance(data_path, str) or not data_path.strip():
                raise ValueError("data_path must be a non-empty string.")

            self._data_path = data_path
            self._gtfs_loader = GTFSLoader(data_path=data_path)
            self._gtfs_loader.load()
            self._stop_search = StopSearch(self._gtfs_loader.stops)
            self._feeds = {"default": self._gtfs_loader}

            self.logger.info("Transit service loaded GTFS feed from %s", data_path)
            return self

        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to load GTFS data in TransitService: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def load_all_feeds(self, data_root: str) -> "TransitService":
        """Load all GTFS feed folders under the provided data root.

        Args:
            data_root: Directory containing feed folders.

        Returns:
            The current service instance for chaining.
        """
        try:
            if not isinstance(data_root, str) or not data_root.strip():
                raise ValueError("data_root must be a non-empty string.")

            registry = FeedRegistry(data_root=data_root)
            feed_names = registry.discover_feeds()
            self._feeds = {}

            for feed_name in feed_names:
                try:
                    feed_path = registry.get_feed_path(feed_name)
                    loader = GTFSLoader(str(feed_path))
                    loader.load()
                    self._feeds[feed_name] = loader
                    self.logger.info("Loaded GTFS feed '%s' from %s", feed_name, feed_path)
                except Exception as exc:
                    self.logger.warning("Skipping GTFS feed '%s': %s", feed_name, exc)

            if self._feeds:
                first_feed = next(iter(self._feeds.values()))
                self._gtfs_loader = first_feed
                self._stop_search = StopSearch(first_feed.stops)
            else:
                self._gtfs_loader = None
                self._stop_search = None

            self._data_path = data_root
            self.logger.info("Loaded %d GTFS feed(s) from %s", len(self._feeds), data_root)
            return self

        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to load GTFS feeds in TransitService: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def available_feeds(self) -> List[str]:
        """Return the names of all discovered GTFS feeds."""
        try:
            return list(self._feeds.keys()) if self._feeds else []
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to list GTFS feeds: {exc}"
            self.logger.exception(message)
            return []

    def get_feed(self, feed_name: str) -> Optional[GTFSLoader]:
        """Return the GTFS loader for the specified feed name.

        Args:
            feed_name: Name of the GTFS feed.

        Returns:
            The matching GTFSLoader, or None if not found.
        """
        try:
            return self._feeds.get(feed_name)
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to get GTFS feed '{feed_name}': {exc}"
            self.logger.exception(message)
            return None

    def search_stops_in_feed(self, query: str, feed_name: str) -> List[StopResult]:
        """Search stops within a specific GTFS feed.

        Args:
            query: Search text to match against stop identifiers and names.
            feed_name: Name of the GTFS feed to search.

        Returns:
            A list of StopResult models.

        Raises:
            ValueError: If the feed name is invalid.
            RuntimeError: If the feed is not available or cannot be searched.
        """
        try:
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query must be a non-empty string.")

            if not isinstance(feed_name, str) or not feed_name.strip():
                raise ValueError("feed_name must be a non-empty string.")

            loader = self.get_feed(feed_name)
            if loader is None:
                raise RuntimeError(f"GTFS feed '{feed_name}' is not available.")

            searcher = StopSearch(loader.stops)
            return searcher.search(query)
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to search stops in feed '{feed_name}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def get_nearby_stops(
        self,
        feed_name: str,
        lat: float,
        lon: float,
        radius_km: float = 2.0,
    ) -> List[NearbyStopResult]:
        """Return nearby stops for a given feed and coordinate.

        Args:
            feed_name: Name of the GTFS feed to search within.
            lat: Reference latitude in decimal degrees.
            lon: Reference longitude in decimal degrees.
            radius_km: Maximum search radius in kilometers.

        Returns:
            A list of nearby stop results sorted by distance.

        Raises:
            RuntimeError: If the requested feed does not exist.
        """
        try:
            if not isinstance(feed_name, str) or not feed_name.strip():
                raise ValueError("feed_name must be a non-empty string.")

            loader = self.get_feed(feed_name)
            if loader is None:
                raise RuntimeError(f"GTFS feed '{feed_name}' is not available.")

            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                raise ValueError("lat and lon must be numeric values.")

            if not isinstance(radius_km, (int, float)) or radius_km < 0:
                raise ValueError("radius_km must be a non-negative number.")

            results: List[NearbyStopResult] = []
            for _, row in loader.stops.iterrows():
                try:
                    stop_lat = float(row.get("stop_lat", 0.0))
                    stop_lon = float(row.get("stop_lon", 0.0))
                except (TypeError, ValueError):
                    continue

                if not math.isfinite(stop_lat) or not math.isfinite(stop_lon):
                    continue

                distance_km = haversine(lat, lon, stop_lat, stop_lon)
                if distance_km <= radius_km:
                    results.append(
                        NearbyStopResult(
                            stop_id=str(row.get("stop_id", "")),
                            stop_name=str(row.get("stop_name", "")),
                            lat=stop_lat,
                            lon=stop_lon,
                            distance_km=distance_km,
                        )
                    )

            results.sort(key=lambda item: item.distance_km)
            return results[:20]
        except ValueError: 
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to find nearby stops for feed '{feed_name}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def search_stops_all_feeds(self, query: str) -> List[StopResult]:
        """Search stops across every loaded GTFS feed.

        Args:
            query: The text to match against stop identifiers and names.

        Returns:
            A deduplicated list of stop results sorted alphabetically by
            stop name, limited to a maximum of 20 items.

        Raises:
            ValueError: If the query is empty or not a non-empty string.
            RuntimeError: If no GTFS feeds are loaded.
        """
        try:
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query must be a non-empty string.")

            if not self._feeds:
                raise RuntimeError("No GTFS feeds are loaded.")

            results: List[StopResult] = []
            seen: set[tuple[str, str]] = set()

            for feed_name, loader in self._feeds.items():
                searcher = StopSearch(loader.stops, feed_name=feed_name)
                for result in searcher.search(query):
                    dedupe_key = (str(result.stop_id), str(result.stop_name))
                    if dedupe_key in seen:
                        continue

                    seen.add(dedupe_key)
                    results.append(result)

            results.sort(key=lambda item: (-item.match_score, item.match_tier, (item.stop_name or "").lower()))
            return results[:20]
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to search stops across all feeds: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def get_route_shape(
        self,
        feed_name: str,
        shape_id: str,
    ) -> List[ShapePoint]:
        """Return the ordered shape points for a GTFS route shape.

        Args:
            feed_name: Name of the GTFS feed that contains the shape.
            shape_id: Identifier of the requested GTFS shape.

        Returns:
            A list of ShapePoint objects ordered by GTFS sequence.

        Raises:
            ValueError: If feed_name or shape_id is empty.
            RuntimeError: If the feed is not available or the shape cannot be found.
        """
        try:
            if not isinstance(feed_name, str) or not feed_name.strip():
                raise ValueError("feed_name must be a non-empty string.")

            if not isinstance(shape_id, str) or not shape_id.strip():
                raise ValueError("shape_id must be a non-empty string.")

            loader = self.get_feed(feed_name)
            if loader is None:
                raise RuntimeError(f"GTFS feed '{feed_name}' is not available.")

            if not hasattr(loader, "shapes") or loader.shapes is None:
                raise RuntimeError(f"No shape data is available for feed '{feed_name}'.")

            shape_rows = loader.shapes[loader.shapes["shape_id"] == shape_id].copy()
            if shape_rows.empty:
                raise RuntimeError(f"Shape '{shape_id}' was not found in feed '{feed_name}'.")

            shape_rows["shape_pt_sequence"] = shape_rows["shape_pt_sequence"].astype(int)
            shape_rows = shape_rows.sort_values(by="shape_pt_sequence")

            points: List[ShapePoint] = []
            for _, row in shape_rows.iterrows():
                points.append(
                    ShapePoint(
                        lat=float(row.get("shape_pt_lat", 0.0)),
                        lon=float(row.get("shape_pt_lon", 0.0)),
                        sequence=int(row.get("shape_pt_sequence", 0)),
                    )
                )

            self.logger.info(
                "Loaded %d shape point(s) for feed '%s' and shape '%s'",
                len(points),
                feed_name,
                shape_id,
            )
            return points
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to retrieve shape '{shape_id}' for feed '{feed_name}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def get_available_shapes(self, feed_name: str) -> List[str]:
        """Return all available GTFS shape identifiers for a feed.

        Args:
            feed_name: Name of the GTFS feed to inspect.

        Returns:
            A sorted list of unique shape IDs from the feed's shapes data.

        Raises:
            ValueError: If feed_name is empty or not a string.
            RuntimeError: If the feed is not available, no shapes data exists,
                or the shape_id column is missing.
        """
        try:
            if not isinstance(feed_name, str) or not feed_name.strip():
                raise ValueError("feed_name must be a non-empty string.")

            loader = self.get_feed(feed_name)
            if loader is None:
                raise RuntimeError(f"GTFS feed '{feed_name}' is not available.")

            if not hasattr(loader, "shapes") or loader.shapes is None or loader.shapes.empty:
                raise RuntimeError(f"No shapes data is available for feed '{feed_name}'.")

            if "shape_id" not in loader.shapes.columns:
                raise RuntimeError(f"Shape data for feed '{feed_name}' is missing the 'shape_id' column.")

            shape_ids = sorted(
                loader.shapes["shape_id"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            self.logger.info(
                "Found %d unique shape ID(s) for feed '%s'",
                len(shape_ids),
                feed_name,
            )
            return shape_ids
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to retrieve available shapes for feed '{feed_name}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def search_stops(self, query: str) -> List[StopResult]:
        """Search stops across all loaded GTFS feeds.

        Args:
            query: The text to match against stop identifiers and names.

        Returns:
            A deduplicated list of stop results sorted alphabetically by
            stop name, limited to a maximum of 20 items.

        Raises:
            RuntimeError: If the service has not been loaded yet.
        """
        if not self.is_loaded or self._stop_search is None:
            raise RuntimeError("TransitService must be loaded before searching stops.")

        try:
            return self.search_stops_all_feeds(query)
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Stop search failed in TransitService: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def find_trip(self, source: str, destination: str, stop_count_weight: float = 1.0, distance_weight: float = 1.0, max_transfer_results: int = 5) -> TripResponse:
        """Find deterministic direct or single-transfer routes between two stops across all feeds.

        Args:
            source: Source stop query.
            destination: Destination stop query.
            stop_count_weight: Weight for estimated stop count in scoring.
            distance_weight: Weight for distance penalty in scoring.
            max_transfer_results: Maximum number of transfer options to return.

        Returns:
            A TripResponse containing direct and transfer routes across available feeds.

        Raises:
            RuntimeError: If the service has not been loaded.
            ValueError: If queries are empty.
        """
        if not self.is_loaded or not self._feeds:
            raise RuntimeError("TransitService must be loaded before finding trips.")

        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be a non-empty string.")
        if not isinstance(destination, str) or not destination.strip():
            raise ValueError("destination must be a non-empty string.")

        results: List[TripResult] = []
        feeds_searched: List[str] = list(self._feeds.keys())

        # Stage 1: Evaluate stop matching across all feeds
        feed_candidates = []
        for feed_name, loader in self._feeds.items():
            searcher = StopSearch(loader.stops)
            source_matches = searcher.search(source)
            dest_matches = searcher.search(destination)

            if not source_matches or not dest_matches:
                continue

            source_stop = source_matches[0]
            dest_stop = dest_matches[0]
            tier_sum = source_stop.match_tier + dest_stop.match_tier
            score_sum = source_stop.match_score + dest_stop.match_score
            
            # [DIAGNOSTICS] Log feed candidates before processing trips
            self.logger.info(
                f"[DIAGNOSTICS] Feed '{feed_name}' match -> "
                f"Source: {source_stop.stop_name} (Tier {source_stop.match_tier}) | "
                f"Dest: {dest_stop.stop_name} (Tier {dest_stop.match_tier}) | "
                f"Tier Sum: {tier_sum}"
            )
            
            feed_candidates.append((tier_sum, -score_sum, feed_name, loader, source_stop, dest_stop))

        if not feed_candidates:
            return TripResponse(
                source=source,
                destination=destination,
                results=[],
                feeds_searched=feeds_searched,
            )

        # Sort feeds by best match tiers
        feed_candidates.sort(key=lambda x: (x[0], x[1]))
        best_tier_sum = feed_candidates[0][0]

        # Stage 2: Only search for trips in the feeds with the best matching stops
        for tier_sum, neg_score_sum, feed_name, loader, source_stop, dest_stop in feed_candidates:
            if tier_sum > best_tier_sum:
                self.logger.info(f"Skipping feed '{feed_name}' (Tier Sum {tier_sum} > Best {best_tier_sum})")
                continue

            stop_times = loader.stop_times
            trips = loader.trips
            routes = loader.routes

            if stop_times is None or trips is None or routes is None:
                continue

            # Get trips and routes serving the source stop
            source_st = stop_times[stop_times["stop_id"] == source_stop.stop_id]
            source_tr = trips[trips["trip_id"].isin(source_st["trip_id"])]
            source_routes = routes[routes["route_id"].isin(source_tr["route_id"])]

            # Get trips and routes serving the destination stop
            dest_st = stop_times[stop_times["stop_id"] == dest_stop.stop_id]
            dest_tr = trips[trips["trip_id"].isin(dest_st["trip_id"])]
            dest_routes = routes[routes["route_id"].isin(dest_tr["route_id"])]

            source_route_ids = set(source_routes["route_id"])
            dest_route_ids = set(dest_routes["route_id"])

            self.logger.info(
                f"[DIAGNOSTICS] Routing in feed '{feed_name}' - "
                f"source_stop_id: {source_stop.stop_id}, "
                f"dest_stop_id: {dest_stop.stop_id}, "
                f"routes serving source: {len(source_route_ids)}, "
                f"routes serving destination: {len(dest_route_ids)}"
            )

            # 1. Find direct routes
            direct_route_ids = source_route_ids.intersection(dest_route_ids)
            direct_trip_routes: List[TripRoute] = []
            
            common_trip_ids = set(source_tr["trip_id"]).intersection(set(dest_tr["trip_id"]))
            self.logger.info(
                f"[DIAGNOSTICS] Feed '{feed_name}' - "
                f"common routes: {len(direct_route_ids)}, "
                f"common trips: {len(common_trip_ids)}"
            )

            
            for r_id in direct_route_ids:
                r_row = routes[routes["route_id"] == r_id].iloc[0]
                
                # Extract shape_id from a common trip on this route
                shape_id = None
                r_trips = trips[(trips["route_id"] == r_id) & (trips["trip_id"].isin(common_trip_ids))]
                if not r_trips.empty:
                    val = r_trips.iloc[0].get("shape_id")
                    shape_id = str(val) if not pd.isna(val) else None

                direct_trip_routes.append(
                    TripRoute(
                        route_id=str(r_row.get("route_id", "")),
                        route_short_name=str(r_row.get("route_short_name", "")),
                        route_long_name=str(r_row.get("route_long_name", "")),
                        feed=feed_name,
                        shape_id=shape_id,
                    )
                )

            # 2. Find transfer options
            transfer_options: List[TransferOption] = []
            
            # Find all stops on all source routes
            source_trips_all = trips[trips["route_id"].isin(source_route_ids)]
            source_stops_all = set(
                stop_times[stop_times["trip_id"].isin(source_trips_all["trip_id"])]["stop_id"]
            )

            # Find all stops on all dest routes
            dest_trips_all = trips[trips["route_id"].isin(dest_route_ids)]
            dest_stops_all = set(
                stop_times[stop_times["trip_id"].isin(dest_trips_all["trip_id"])]["stop_id"]
            )

            transfer_stop_ids = list(source_stops_all.intersection(dest_stops_all))
            
            self.logger.info(
                f"[DIAGNOSTICS] Feed '{feed_name}' - "
                f"transfer candidates (common stops): {len(transfer_stop_ids)}"
            )

            for t_stop_id in transfer_stop_ids:
                t_stop_row = loader.get_stop_by_id(t_stop_id)
                if t_stop_row is None:
                    continue
                t_stop_name = str(t_stop_row.get("stop_name", ""))
                t_stop_lat = float(t_stop_row.get("stop_lat", 0.0))
                t_stop_lon = float(t_stop_row.get("stop_lon", 0.0))

                # Find a route from source to transfer
                t_stop_st = stop_times[stop_times["stop_id"] == t_stop_id]
                t_source_tr = source_trips_all[source_trips_all["trip_id"].isin(t_stop_st["trip_id"])]
                
                valid_source_trip_id = None
                valid_source_r_id = None
                source_seq = 0
                t_source_seq = 0
                
                if not t_source_tr.empty:
                    for _, t_row in t_source_tr.iterrows():
                        trip_id = t_row["trip_id"]
                        t_st_all = stop_times[stop_times["trip_id"] == trip_id]
                        try:
                            s_seq_val = t_st_all[t_st_all["stop_id"] == source_stop.stop_id]["stop_sequence"].iloc[0]
                            ts_seq_val = t_st_all[t_st_all["stop_id"] == t_stop_id]["stop_sequence"].iloc[0]
                            s_seq = int(s_seq_val) if not pd.isna(s_seq_val) else 0
                            ts_seq = int(ts_seq_val) if not pd.isna(ts_seq_val) else 0
                            
                            if s_seq < ts_seq:
                                valid_source_trip_id = trip_id
                                valid_source_r_id = t_row["route_id"]
                                source_seq = s_seq
                                t_source_seq = ts_seq
                                break
                        except (IndexError, ValueError):
                            continue

                # Find a route from transfer to dest
                t_dest_tr = dest_trips_all[dest_trips_all["trip_id"].isin(t_stop_st["trip_id"])]
                
                valid_dest_trip_id = None
                valid_dest_r_id = None
                t_dest_seq = 0
                dest_seq = 0
                
                if not t_dest_tr.empty:
                    for _, t_row in t_dest_tr.iterrows():
                        trip_id = t_row["trip_id"]
                        t_st_all = stop_times[stop_times["trip_id"] == trip_id]
                        try:
                            td_seq_val = t_st_all[t_st_all["stop_id"] == t_stop_id]["stop_sequence"].iloc[0]
                            d_seq_val = t_st_all[t_st_all["stop_id"] == dest_stop.stop_id]["stop_sequence"].iloc[0]
                            td_seq = int(td_seq_val) if not pd.isna(td_seq_val) else 0
                            d_seq = int(d_seq_val) if not pd.isna(d_seq_val) else 0
                            
                            if td_seq < d_seq:
                                valid_dest_trip_id = trip_id
                                valid_dest_r_id = t_row["route_id"]
                                t_dest_seq = td_seq
                                dest_seq = d_seq
                                break
                        except (IndexError, ValueError):
                            continue

                self.logger.info(
                    f"[TRANSFER]\n"
                    f"candidate_stop={t_stop_id}\n"
                    f"source_trip_count={len(t_source_tr)}\n"
                    f"dest_trip_count={len(t_dest_tr)}\n"
                    f"valid_source_trip_found={valid_source_trip_id is not None}\n"
                    f"valid_dest_trip_found={valid_dest_trip_id is not None}"
                )

                if valid_source_trip_id and valid_dest_trip_id:
                    r_source_row = routes[routes["route_id"] == valid_source_r_id].iloc[0]
                    r_dest_row = routes[routes["route_id"] == valid_dest_r_id].iloc[0]
                    
                    source_shape_id = None
                    s_trip_match = trips[trips["trip_id"] == valid_source_trip_id]
                    if not s_trip_match.empty:
                        val = s_trip_match.iloc[0].get("shape_id")
                        source_shape_id = str(val) if not pd.isna(val) else None

                    dest_shape_id = None
                    d_trip_match = trips[trips["trip_id"] == valid_dest_trip_id]
                    if not d_trip_match.empty:
                        val = d_trip_match.iloc[0].get("shape_id")
                        dest_shape_id = str(val) if not pd.isna(val) else None
                    
                    estimated_stop_count = (t_source_seq - source_seq) + (dest_seq - t_dest_seq)
                        
                    # Distance penalty calculation
                    source_lat = float(source_stop.lat) if source_stop.lat else 0.0
                    source_lon = float(source_stop.lon) if source_stop.lon else 0.0
                    dest_lat = float(dest_stop.lat) if dest_stop.lat else 0.0
                    dest_lon = float(dest_stop.lon) if dest_stop.lon else 0.0
                    
                    # Source to Transfer + Transfer to Destination distance
                    if source_lat and source_lon and t_stop_lat and t_stop_lon and dest_lat and dest_lon:
                        dist_to_transfer = haversine(source_lat, source_lon, t_stop_lat, t_stop_lon)
                        dist_to_dest = haversine(t_stop_lat, t_stop_lon, dest_lat, dest_lon)
                        distance_penalty = dist_to_transfer + dist_to_dest
                    else:
                        distance_penalty = 100.0 # Fallback penalty
                        
                    # Scoring: Use configurable parameters
                    score = (stop_count_weight * estimated_stop_count) + (distance_weight * distance_penalty)

                    transfer_options.append(
                        TransferOption(
                            transfer_stop_id=str(t_stop_id),
                            transfer_stop_name=t_stop_name,
                            route_from=TripRoute(
                                route_id=str(r_source_row.get("route_id", "")),
                                route_short_name=str(r_source_row.get("route_short_name", "")),
                                route_long_name=str(r_source_row.get("route_long_name", "")),
                                feed=feed_name,
                                shape_id=source_shape_id,
                            ),
                            route_to=TripRoute(
                                route_id=str(r_dest_row.get("route_id", "")),
                                route_short_name=str(r_dest_row.get("route_short_name", "")),
                                route_long_name=str(r_dest_row.get("route_long_name", "")),
                                feed=feed_name,
                                shape_id=dest_shape_id,
                            ),
                            estimated_stop_count=estimated_stop_count,
                            distance_penalty=distance_penalty,
                            score=score
                        )
                    )
            
            # Sort transfer options by score and limit
            transfer_options.sort(key=lambda x: x.score)
            transfer_options = transfer_options[:max_transfer_results]

            # Add to results if we found direct routes or transfer options
            if direct_trip_routes or transfer_options:
                results.append(
                    TripResult(
                        source_stop_id=source_stop.stop_id,
                        source_stop_name=source_stop.stop_name,
                        destination_stop_id=dest_stop.stop_id,
                        destination_stop_name=dest_stop.stop_name,
                        feed=feed_name,
                        direct_routes=direct_trip_routes,
                        transfer_options=transfer_options,
                        source_match_tier=source_stop.match_tier,
                        dest_match_tier=dest_stop.match_tier,
                        source_match_score=source_stop.match_score,
                        dest_match_score=dest_stop.match_score,
                    )
                )


        # 4. Sort results by feed consistency and match quality
        # Lower tier sum is better. Then higher score sum is better (less penalty).
        results.sort(key=lambda r: (
            r.source_match_tier + r.dest_match_tier,
            -(r.source_match_score + r.dest_match_score)
        ))

        return TripResponse(
            source=source,
            destination=destination,
            results=results,
            feeds_searched=feeds_searched,
        )

    def get_direct_journeys(self, source_stop_id: str, destination_stop_id: str, departure_after: str | None = None) -> list["JourneyRoute"]:
        """Find direct trips between two stops across all loaded feeds.

        Searches every loaded GTFS feed for trips that visit both the source
        and destination stop (in the correct order).  Results are deduplicated
        by (feed, route_id) so each route appears at most once per feed.
        """
        from app.models.schemas import JourneyRoute
        import pandas as pd

        self.logger.info(
            "Journey planner invoked: source_stop_id='%s', destination_stop_id='%s', departure_after='%s'",
            source_stop_id,
            destination_stop_id,
            departure_after,
        )

        journeys: list[JourneyRoute] = []
        seen_routes: set[tuple[str, str]] = set()  # (feed, route_id)

        for feed_name, loader in self._feeds.items():
            stop_times = loader.stop_times
            trips = loader.trips
            routes = loader.routes
            stops = loader.stops

            # Guard against missing data
            if stop_times is None or trips is None or routes is None or stops is None:
                self.logger.warning("Feed '%s' has missing GTFS tables, skipping", feed_name)
                continue

            if "stop_id" not in stop_times.columns:
                self.logger.warning("Feed '%s' stop_times missing 'stop_id' column, skipping", feed_name)
                continue

            # Find trips serving the source
            source_st = stop_times[stop_times["stop_id"] == source_stop_id]
            if source_st.empty:
                self.logger.debug("Feed '%s': source stop '%s' not found", feed_name, source_stop_id)
                continue

            # Find trips serving the destination
            dest_st = stop_times[stop_times["stop_id"] == destination_stop_id]
            if dest_st.empty:
                self.logger.debug("Feed '%s': destination stop '%s' not found", feed_name, destination_stop_id)
                continue

            # Merge to find common trips where source comes before destination
            common = source_st.merge(
                dest_st,
                on="trip_id",
                suffixes=("_source", "_dest"),
            )

            if common.empty:
                self.logger.debug("Feed '%s': no common trips between '%s' and '%s'", feed_name, source_stop_id, destination_stop_id)
                continue

            # Filter for valid direction (source before destination)
            valid_trips = common[
                common["stop_sequence_source"].astype(int) < common["stop_sequence_dest"].astype(int)
            ]

            if valid_trips.empty:
                self.logger.debug("Feed '%s': common trips exist but none in correct direction", feed_name)
                continue

            if "departure_time_source" in valid_trips.columns:
                if departure_after:
                    valid_trips = valid_trips[valid_trips["departure_time_source"].astype(str) >= departure_after]
                
                if valid_trips.empty:
                    self.logger.debug("Feed '%s': trips found but none matched departure_after", feed_name)
                    continue
                    
                valid_trips = valid_trips.sort_values(by="departure_time_source")

            # Fetch stop names
            source_stop_row = stops[stops["stop_id"] == source_stop_id]
            dest_stop_row = stops[stops["stop_id"] == destination_stop_id]
            s_name = source_stop_row.iloc[0]["stop_name"] if not source_stop_row.empty else source_stop_id
            d_name = dest_stop_row.iloc[0]["stop_name"] if not dest_stop_row.empty else destination_stop_id

            feed_match_count = 0
            for _, row in valid_trips.iterrows():
                trip_id = row["trip_id"]
                stops_between = int(row["stop_sequence_dest"]) - int(row["stop_sequence_source"])

                # Look up route
                trip_row = trips[trips["trip_id"] == trip_id]
                if trip_row.empty:
                    continue
                route_id = str(trip_row.iloc[0]["route_id"])

                # Deduplicate: one entry per (feed, route_id)
                dedupe_key = (feed_name, route_id)
                if dedupe_key in seen_routes:
                    continue
                seen_routes.add(dedupe_key)

                route_row = routes[routes["route_id"] == route_id]
                if route_row.empty:
                    continue

                r_short = route_row.iloc[0].get("route_short_name", "")
                r_long = route_row.iloc[0].get("route_long_name", "")
                route_name = str(r_long) if pd.notna(r_long) and r_long else str(r_short)

                shape_id_val = trip_row.iloc[0].get("shape_id")
                shape_id = str(shape_id_val) if pd.notna(shape_id_val) and str(shape_id_val).strip() else None

                departure_time = str(row.get("departure_time_source", ""))
                if pd.isna(row.get("departure_time_source")) or not departure_time.strip() or departure_time == "nan":
                    departure_time = None

                arrival_time = str(row.get("arrival_time_dest", ""))
                if pd.isna(row.get("arrival_time_dest")) or not arrival_time.strip() or arrival_time == "nan":
                    arrival_time = str(row.get("departure_time_dest", ""))
                    if pd.isna(row.get("departure_time_dest")) or not arrival_time.strip() or arrival_time == "nan":
                        arrival_time = None

                duration_minutes = None
                if departure_time and arrival_time:
                    try:
                        dh, dm, ds = map(int, departure_time.split(':'))
                        ah, am, _ = map(int, arrival_time.split(':'))
                        d_total = dh * 60 + dm
                        a_total = ah * 60 + am
                        duration_minutes = a_total - d_total
                    except (ValueError, AttributeError):
                        pass

                journeys.append(
                    JourneyRoute(
                        feed=feed_name,
                        trip_id=str(trip_id),
                        route_id=route_id,
                        route_name=route_name,
                        source_stop=str(s_name),
                        destination_stop=str(d_name),
                        stops_between=stops_between,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        duration_minutes=duration_minutes,
                        shape_id=shape_id,
                    )
                )
                feed_match_count += 1

                self.logger.info(
                    "  [%s] route '%s' (%s) — %d stops between %s → %s",
                    feed_name,
                    route_name,
                    route_id,
                    stops_between,
                    s_name,
                    d_name,
                )

            self.logger.info(
                "Feed '%s': %d unique route(s) found for %s → %s",
                feed_name,
                feed_match_count,
                source_stop_id,
                destination_stop_id,
            )

        self.logger.info(
            "Journey search complete: source='%s', destination='%s', departure_after='%s', total_routes=%d",
            source_stop_id,
            destination_stop_id,
            departure_after,
            len(journeys),
        )

        # Sort results by departure_time ascending, putting None values at the end
        journeys.sort(key=lambda j: j.departure_time if j.departure_time is not None else "99:99:99")

        return journeys

    def get_trip_stops(self, feed_name: str, trip_id: str) -> list["TripStop"]:
        """Return all stops for a given trip_id in chronological order."""
        if not self.is_loaded:
            raise RuntimeError("GTFS feeds are not loaded.")

        if feed_name not in self._feeds:
            raise ValueError(f"Feed '{feed_name}' not found.")

        loader = self._feeds[feed_name]
        stop_times = loader.stop_times
        stops = loader.stops

        if stop_times is None or stops is None:
            raise RuntimeError(f"Missing GTFS data for feed '{feed_name}'.")

        # Get stop_times for the trip
        trip_st = stop_times[stop_times["trip_id"] == trip_id].copy()
        if trip_st.empty:
            raise ValueError(f"Trip '{trip_id}' not found or has no stops.")

        # Ensure correct ordering
        trip_st["stop_sequence"] = trip_st["stop_sequence"].astype(int)
        trip_st = trip_st.sort_values(by="stop_sequence")

        self.logger.info(
            "Journey planner invoked: source_stop_id='%s', destination_stop_id='%s', departure_after='%s'",
            source_stop_id,
            destination_stop_id,
            departure_after,
        )

        journeys: list[JourneyRoute] = []
        seen_routes: set[tuple[str, str]] = set()  # (feed, route_id)

        for feed_name, loader in self._feeds.items():
            stop_times = loader.stop_times
            trips = loader.trips
            routes = loader.routes
            stops = loader.stops

            # Guard against missing data
            if stop_times is None or trips is None or routes is None or stops is None:
                self.logger.warning("Feed '%s' has missing GTFS tables, skipping", feed_name)
                continue

            if "stop_id" not in stop_times.columns:
                self.logger.warning("Feed '%s' stop_times missing 'stop_id' column, skipping", feed_name)
                continue

            # Find trips serving the source
            source_st = stop_times[stop_times["stop_id"] == source_stop_id]
            if source_st.empty:
                self.logger.debug("Feed '%s': source stop '%s' not found", feed_name, source_stop_id)
                continue

            # Find trips serving the destination
            dest_st = stop_times[stop_times["stop_id"] == destination_stop_id]
            if dest_st.empty:
                self.logger.debug("Feed '%s': destination stop '%s' not found", feed_name, destination_stop_id)
                continue

            # Merge to find common trips where source comes before destination
            common = source_st.merge(
                dest_st,
                on="trip_id",
                suffixes=("_source", "_dest"),
            )

            if common.empty:
                self.logger.debug("Feed '%s': no common trips between '%s' and '%s'", feed_name, source_stop_id, destination_stop_id)
                continue

            # Filter for valid direction (source before destination)
            valid_trips = common[
                common["stop_sequence_source"].astype(int) < common["stop_sequence_dest"].astype(int)
            ]

            if valid_trips.empty:
                self.logger.debug("Feed '%s': common trips exist but none in correct direction", feed_name)
                continue

            if "departure_time_source" in valid_trips.columns:
                if departure_after:
                    valid_trips = valid_trips[valid_trips["departure_time_source"].astype(str) >= departure_after]
                
                if valid_trips.empty:
                    self.logger.debug("Feed '%s': trips found but none matched departure_after", feed_name)
                    continue
                    
                valid_trips = valid_trips.sort_values(by="departure_time_source")

            # Fetch stop names
            source_stop_row = stops[stops["stop_id"] == source_stop_id]
            dest_stop_row = stops[stops["stop_id"] == destination_stop_id]
            s_name = source_stop_row.iloc[0]["stop_name"] if not source_stop_row.empty else source_stop_id
            d_name = dest_stop_row.iloc[0]["stop_name"] if not dest_stop_row.empty else destination_stop_id

            feed_match_count = 0
            for _, row in valid_trips.iterrows():
                trip_id = row["trip_id"]
                stops_between = int(row["stop_sequence_dest"]) - int(row["stop_sequence_source"])

                # Look up route
                trip_row = trips[trips["trip_id"] == trip_id]
                if trip_row.empty:
                    continue
                route_id = str(trip_row.iloc[0]["route_id"])

                # Deduplicate: one entry per (feed, route_id)
                dedupe_key = (feed_name, route_id)
                if dedupe_key in seen_routes:
                    continue
                seen_routes.add(dedupe_key)

                route_row = routes[routes["route_id"] == route_id]
                if route_row.empty:
                    continue

                r_short = route_row.iloc[0].get("route_short_name", "")
                r_long = route_row.iloc[0].get("route_long_name", "")
                route_name = str(r_long) if pd.notna(r_long) and r_long else str(r_short)

                shape_id_val = trip_row.iloc[0].get("shape_id")
                shape_id = str(shape_id_val) if pd.notna(shape_id_val) and str(shape_id_val).strip() else None

                departure_time = str(row.get("departure_time_source", ""))
                if pd.isna(row.get("departure_time_source")) or not departure_time.strip() or departure_time == "nan":
                    departure_time = None

                arrival_time = str(row.get("arrival_time_dest", ""))
                if pd.isna(row.get("arrival_time_dest")) or not arrival_time.strip() or arrival_time == "nan":
                    arrival_time = str(row.get("departure_time_dest", ""))
                    if pd.isna(row.get("departure_time_dest")) or not arrival_time.strip() or arrival_time == "nan":
                        arrival_time = None

                duration_minutes = None
                if departure_time and arrival_time:
                    try:
                        dh, dm, ds = map(int, departure_time.split(':'))
                        ah, am, _ = map(int, arrival_time.split(':'))
                        d_total = dh * 60 + dm
                        a_total = ah * 60 + am
                        duration_minutes = a_total - d_total
                    except (ValueError, AttributeError):
                        pass

                journeys.append(
                    JourneyRoute(
                        feed=feed_name,
                        trip_id=str(trip_id),
                        route_id=route_id,
                        route_name=route_name,
                        source_stop=str(s_name),
                        destination_stop=str(d_name),
                        stops_between=stops_between,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        duration_minutes=duration_minutes,
                        shape_id=shape_id,
                    )
                )
                feed_match_count += 1

                self.logger.info(
                    "  [%s] route '%s' (%s) — %d stops between %s → %s",
                    feed_name,
                    route_name,
                    route_id,
                    stops_between,
                    s_name,
                    d_name,
                )

            self.logger.info(
                "Feed '%s': %d unique route(s) found for %s → %s",
                feed_name,
                feed_match_count,
                source_stop_id,
                destination_stop_id,
            )

        self.logger.info(
            "Journey search complete: source='%s', destination='%s', departure_after='%s', total_routes=%d",
            source_stop_id,
            destination_stop_id,
            departure_after,
            len(journeys),
        )

        journeys.sort(key=lambda j: j.departure_time if j.departure_time is not None else "99:99:99")

        return journeys

    def find_transfer_routes(self, source_stop_id: str, destination_stop_id: str, departure_after: str | None = None) -> list["TransferJourney"]:
        """Find one-transfer trips between two stops across all loaded feeds."""
        from app.models.schemas import JourneyRoute, TransferJourney, JourneyType
        import pandas as pd

        transfer_journeys: list[TransferJourney] = []
        MAX_TRANSFER_CANDIDATES = 100

        for feed_name, loader in self._feeds.items():
            stop_times = loader.stop_times
            trips = loader.trips
            routes = loader.routes
            stops = loader.stops

            if stop_times is None or trips is None or routes is None or stops is None:
                continue

            # Step 1: Find valid first-leg journeys departing from source_stop_id
            source_st = stop_times[stop_times["stop_id"] == source_stop_id]
            if source_st.empty:
                continue

            if departure_after:
                source_st = source_st[source_st["departure_time"].astype(str) >= departure_after]

            if source_st.empty:
                continue

            # Limit to the first trips starting from here to avoid exploding complexity
            source_st = source_st.sort_values(by="departure_time").head(MAX_TRANSFER_CANDIDATES)

            # Step 2: Collect reachable intermediate stops
            source_trips = trips[trips["trip_id"].isin(source_st["trip_id"])]
            source_trip_ids = source_trips["trip_id"].unique()

            # Find all stops reached by these trips AFTER the source stop
            first_leg_st = stop_times[stop_times["trip_id"].isin(source_trip_ids)]
            first_leg_merged = first_leg_st.merge(
                source_st[["trip_id", "stop_sequence", "departure_time"]],
                on="trip_id",
                suffixes=("", "_source")
            )
            # Only stops after the source stop on the first leg
            reachable_st = first_leg_merged[first_leg_merged["stop_sequence"].astype(int) > first_leg_merged["stop_sequence_source"].astype(int)]
            intermediate_stop_ids = reachable_st["stop_id"].unique()

            if len(intermediate_stop_ids) == 0:
                continue

            # Step 3: Find valid second-leg journeys reaching the destination
            dest_st = stop_times[stop_times["stop_id"] == destination_stop_id]
            if dest_st.empty:
                continue

            dest_trips = trips[trips["trip_id"].isin(dest_st["trip_id"])]
            dest_trip_ids = dest_trips["trip_id"].unique()

            second_leg_st = stop_times[stop_times["trip_id"].isin(dest_trip_ids)]
            second_leg_merged = second_leg_st.merge(
                dest_st[["trip_id", "stop_sequence", "arrival_time"]],
                on="trip_id",
                suffixes=("", "_dest")
            )
            # Only stops before the destination stop on the second leg
            boarding_st = second_leg_merged[second_leg_merged["stop_sequence"].astype(int) < second_leg_merged["stop_sequence_dest"].astype(int)]
            valid_transfer_stop_ids = boarding_st["stop_id"].unique()

            # Intersect reachable stops from source with boarding stops to dest
            actual_transfer_stops = set(intermediate_stop_ids).intersection(valid_transfer_stop_ids)

            if not actual_transfer_stops:
                continue

            self.logger.info(f"Feed '{feed_name}': Found {len(actual_transfer_stops)} potential transfer stops between {source_stop_id} and {destination_stop_id}")

            # Collect source and dest stop names
            source_name_row = stops[stops["stop_id"] == source_stop_id]
            dest_name_row = stops[stops["stop_id"] == destination_stop_id]
            source_name = source_name_row.iloc[0]["stop_name"] if not source_name_row.empty else source_stop_id
            dest_name = dest_name_row.iloc[0]["stop_name"] if not dest_name_row.empty else destination_stop_id

            seen_transfer_pairs: set[tuple[str, str, str]] = set() # (transfer_stop, first_route, second_route)
            
            for t_stop_id in actual_transfer_stops:
                # Find arrival times at t_stop_id for first leg
                t_arr_st = reachable_st[reachable_st["stop_id"] == t_stop_id]
                # Find departure times at t_stop_id for second leg
                t_dep_st = boarding_st[boarding_st["stop_id"] == t_stop_id]

                t_name_row = stops[stops["stop_id"] == t_stop_id]
                t_name = str(t_name_row.iloc[0]["stop_name"]) if not t_name_row.empty else t_stop_id

                for _, arr_row in t_arr_st.iterrows():
                    arr_time = str(arr_row["arrival_time"])
                    if pd.isna(arr_time) or not arr_time.strip() or arr_time == "nan":
                        continue

                    # Step 4: Validate transfer timing
                    # arrival(first_leg) < departure(second_leg)
                    # Minimum transfer time: 3 minutes
                    try:
                        ah, am, _ = map(int, arr_time.split(':'))
                        arr_total = ah * 60 + am
                    except (ValueError, AttributeError):
                        continue

                    # Filter second leg departures
                    valid_deps = []
                    for _, dep_row in t_dep_st.iterrows():
                        dep_time = str(dep_row["departure_time"])
                        if pd.isna(dep_time) or not dep_time.strip() or dep_time == "nan":
                            continue
                        
                        try:
                            dh, dm, _ = map(int, dep_time.split(':'))
                            dep_total = dh * 60 + dm
                        except (ValueError, AttributeError):
                            continue

                        transfer_wait = dep_total - arr_total
                        if 3 <= transfer_wait <= 120:  # Valid transfer window: 3 mins to 2 hours
                            valid_deps.append((dep_row, transfer_wait, dep_time, dep_total))

                    if not valid_deps:
                        continue

                    # Extract first leg route info
                    first_trip_id = arr_row["trip_id"]
                    first_trip = trips[trips["trip_id"] == first_trip_id].iloc[0]
                    first_route_id = str(first_trip["route_id"])
                    first_route = routes[routes["route_id"] == first_route_id].iloc[0]
                    r_short = first_route.get("route_short_name", "")
                    r_long = first_route.get("route_long_name", "")
                    first_r_name = str(r_long) if pd.notna(r_long) and r_long else str(r_short)
                    
                    first_dep_time = str(arr_row["departure_time_source"])
                    first_duration = None
                    try:
                        fdh, fdm, _ = map(int, first_dep_time.split(':'))
                        first_duration = arr_total - (fdh * 60 + fdm)
                    except (ValueError, AttributeError):
                        pass

                    for dep_row, transfer_wait, second_dep_time, dep_total in valid_deps:
                        second_trip_id = dep_row["trip_id"]
                        second_trip = trips[trips["trip_id"] == second_trip_id].iloc[0]
                        second_route_id = str(second_trip["route_id"])
                        
                        dedupe_key = (t_stop_id, first_route_id, second_route_id)
                        if dedupe_key in seen_transfer_pairs:
                            continue
                        
                        second_route = routes[routes["route_id"] == second_route_id].iloc[0]
                        sr_short = second_route.get("route_short_name", "")
                        sr_long = second_route.get("route_long_name", "")
                        second_r_name = str(sr_long) if pd.notna(sr_long) and sr_long else str(sr_short)
                        
                        # Find second leg arrival at dest
                        second_arr_time = str(dep_row["arrival_time_dest"])
                        
                        second_duration = None
                        try:
                            sah, sam, _ = map(int, second_arr_time.split(':'))
                            dest_total = sah * 60 + sam
                            second_duration = dest_total - dep_total
                        except (ValueError, AttributeError):
                            pass

                        if first_duration is not None and second_duration is not None:
                            total_duration = first_duration + transfer_wait + second_duration

                            seen_transfer_pairs.add(dedupe_key)
                            
                            leg1 = JourneyRoute(
                                journey_type=JourneyType.DIRECT,
                                feed=feed_name,
                                trip_id=str(first_trip_id),
                                route_id=str(first_route_id),
                                route_name=str(first_r_name),
                                source_stop=str(source_name),
                                destination_stop=str(t_name),
                                stops_between=int(arr_row["stop_sequence"]) - int(arr_row["stop_sequence_source"]),
                                departure_time=first_dep_time,
                                arrival_time=arr_time,
                                duration_minutes=first_duration,
                                shape_id=str(first_trip.get("shape_id")) if pd.notna(first_trip.get("shape_id")) else None
                            )

                            leg2 = JourneyRoute(
                                journey_type=JourneyType.DIRECT,
                                feed=feed_name,
                                trip_id=str(second_trip_id),
                                route_id=str(second_route_id),
                                route_name=str(second_r_name),
                                source_stop=str(t_name),
                                destination_stop=str(dest_name),
                                stops_between=int(dep_row["stop_sequence_dest"]) - int(dep_row["stop_sequence"]),
                                departure_time=second_dep_time,
                                arrival_time=second_arr_time,
                                duration_minutes=second_duration,
                                shape_id=str(second_trip.get("shape_id")) if pd.notna(second_trip.get("shape_id")) else None
                            )

                            transfer_journeys.append(TransferJourney(
                                journey_type=JourneyType.TRANSFER,
                                transfer_stop=t_name,
                                first_leg=leg1,
                                second_leg=leg2,
                                total_duration=total_duration,
                                transfer_wait=transfer_wait
                            ))

                            if len(seen_transfer_pairs) >= MAX_TRANSFER_CANDIDATES:
                                break
                    if len(seen_transfer_pairs) >= MAX_TRANSFER_CANDIDATES:
                        break
                if len(seen_transfer_pairs) >= MAX_TRANSFER_CANDIDATES:
                    break
                    
        # Step 6: Sort transfer journeys by Earliest arrival, Lowest transfer wait, Shortest duration
        transfer_journeys.sort(key=lambda j: (
            j.second_leg.arrival_time if j.second_leg.arrival_time else "99:99:99",
            j.transfer_wait,
            j.total_duration
        ))

        return transfer_journeys

    def get_trip_stops(self, feed_name: str, trip_id: str) -> list["TripStop"]:
        """Return all stops for a given trip_id in chronological order."""
        if not self.is_loaded:
            raise RuntimeError("GTFS feeds are not loaded.")

        if feed_name not in self._feeds:
            raise ValueError(f"Feed '{feed_name}' not found.")

        loader = self._feeds[feed_name]
        stop_times = loader.stop_times
        stops = loader.stops

        if stop_times is None or stops is None:
            raise RuntimeError(f"Missing GTFS data for feed '{feed_name}'.")

        # Get stop_times for the trip
        trip_st = stop_times[stop_times["trip_id"] == trip_id].copy()
        if trip_st.empty:
            raise ValueError(f"Trip '{trip_id}' not found or has no stops.")

        # Ensure correct ordering
        trip_st["stop_sequence"] = trip_st["stop_sequence"].astype(int)
        trip_st = trip_st.sort_values(by="stop_sequence")

        # Merge with stops to get stop names
        merged = trip_st.merge(stops, on="stop_id", how="left")

        from app.models.schemas import TripStop
        results = []
        for _, row in merged.iterrows():
            arr_time = str(row["arrival_time"]) if "arrival_time" in row and pd.notna(row["arrival_time"]) else None
            dep_time = str(row["departure_time"]) if "departure_time" in row and pd.notna(row["departure_time"]) else None
            lat = float(row["stop_lat"]) if "stop_lat" in row and pd.notna(row["stop_lat"]) else None
            lon = float(row["stop_lon"]) if "stop_lon" in row and pd.notna(row["stop_lon"]) else None
            
            results.append(TripStop(
                stop_id=str(row["stop_id"]),
                stop_name=str(row["stop_name"]) if "stop_name" in row and pd.notna(row["stop_name"]) else str(row["stop_id"]),
                stop_sequence=int(row["stop_sequence"]),
                arrival_time=arr_time,
                departure_time=dep_time,
                stop_lat=lat,
                stop_lon=lon
            ))

        return results


transit_service = TransitService()
