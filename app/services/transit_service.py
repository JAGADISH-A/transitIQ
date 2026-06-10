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

            for loader in self._feeds.values():
                searcher = StopSearch(loader.stops)
                for result in searcher.search(query):
                    dedupe_key = (str(result.stop_id), str(result.stop_name))
                    if dedupe_key in seen:
                        continue

                    seen.add(dedupe_key)
                    results.append(result)

            results.sort(key=lambda item: (item.stop_name or "").lower())
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

        for feed_name, loader in self._feeds.items():
            searcher = StopSearch(loader.stops)
            source_matches = searcher.search(source)
            dest_matches = searcher.search(destination)

            if not source_matches or not dest_matches:
                continue

            # Take the best match for source and destination in this feed
            source_stop = source_matches[0]
            dest_stop = dest_matches[0]

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

            # 1. Find direct routes
            direct_route_ids = source_route_ids.intersection(dest_route_ids)
            direct_trip_routes: List[TripRoute] = []
            
            for r_id in direct_route_ids:
                r_row = routes[routes["route_id"] == r_id].iloc[0]
                direct_trip_routes.append(
                    TripRoute(
                        route_id=str(r_row.get("route_id", "")),
                        route_short_name=str(r_row.get("route_short_name", "")),
                        route_long_name=str(r_row.get("route_long_name", "")),
                        feed=feed_name,
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
                if t_source_tr.empty:
                    continue
                    
                t_source_trip_id = t_source_tr["trip_id"].iloc[0]
                t_source_r_id = t_source_tr["route_id"].iloc[0]

                # Find a route from transfer to dest
                t_dest_tr = dest_trips_all[dest_trips_all["trip_id"].isin(t_stop_st["trip_id"])]
                if t_dest_tr.empty:
                    continue
                    
                t_dest_trip_id = t_dest_tr["trip_id"].iloc[0]
                t_dest_r_id = t_dest_tr["route_id"].iloc[0]

                if t_source_r_id and t_dest_r_id:
                    r_source_row = routes[routes["route_id"] == t_source_r_id].iloc[0]
                    r_dest_row = routes[routes["route_id"] == t_dest_r_id].iloc[0]
                    
                    # Stop sequence calculation
                    t_source_st_all = stop_times[stop_times["trip_id"] == t_source_trip_id]
                    t_dest_st_all = stop_times[stop_times["trip_id"] == t_dest_trip_id]
                    
                    try:
                        source_seq_val = t_source_st_all[t_source_st_all["stop_id"] == source_stop.stop_id]["stop_sequence"].iloc[0]
                        t_source_seq_val = t_source_st_all[t_source_st_all["stop_id"] == t_stop_id]["stop_sequence"].iloc[0]
                        t_dest_seq_val = t_dest_st_all[t_dest_st_all["stop_id"] == t_stop_id]["stop_sequence"].iloc[0]
                        dest_seq_val = t_dest_st_all[t_dest_st_all["stop_id"] == dest_stop.stop_id]["stop_sequence"].iloc[0]
                        
                        source_seq = int(source_seq_val) if not pd.isna(source_seq_val) else 0
                        t_source_seq = int(t_source_seq_val) if not pd.isna(t_source_seq_val) else 0
                        t_dest_seq = int(t_dest_seq_val) if not pd.isna(t_dest_seq_val) else 0
                        dest_seq = int(dest_seq_val) if not pd.isna(dest_seq_val) else 0
                        
                        # Validate direction: transfer must happen after source, dest after transfer
                        if t_source_seq <= source_seq or dest_seq <= t_dest_seq:
                            continue # Invalid transfer sequence direction
                            
                        estimated_stop_count = (t_source_seq - source_seq) + (dest_seq - t_dest_seq)
                    except (IndexError, ValueError):
                        # Fallback if stop_sequence is missing or malformed
                        estimated_stop_count = 10
                        
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
                            ),
                            route_to=TripRoute(
                                route_id=str(r_dest_row.get("route_id", "")),
                                route_short_name=str(r_dest_row.get("route_short_name", "")),
                                route_long_name=str(r_dest_row.get("route_long_name", "")),
                                feed=feed_name,
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
                    )
                )

        return TripResponse(
            source=source,
            destination=destination,
            results=results,
            feeds_searched=feeds_searched,
        )


transit_service = TransitService()
