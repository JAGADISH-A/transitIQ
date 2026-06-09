"""Transit service facade for GTFS loading and stop search."""

import logging
from typing import Dict, List, Optional

from app.models.schemas import StopResult
from app.services.feed_registry import FeedRegistry
from app.services.gtfs_loader import GTFSLoader
from app.services.stop_search import StopSearch


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

    def search_stops(self, query: str) -> List[StopResult]:
        """Search stops using the configured GTFS feed.

        Args:
            query: The text to match against stop identifiers and names.

        Returns:
            A list of stop result models sorted by relevance.

        Raises:
            RuntimeError: If the service has not been loaded yet.
        """
        if not self.is_loaded or self._stop_search is None:
            raise RuntimeError("TransitService must be loaded before searching stops.")

        try:
            return self._stop_search.search(query)
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Stop search failed in TransitService: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc


transit_service = TransitService()
