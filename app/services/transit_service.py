"""Transit service facade for GTFS loading and stop search."""

import logging
from typing import Dict, List, Optional

from app.models.schemas import StopResult
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

            self.logger.info("Transit service loaded GTFS feed from %s", data_path)
            return self

        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to load GTFS data in TransitService: {exc}"
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
