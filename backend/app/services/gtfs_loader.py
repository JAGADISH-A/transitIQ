"""Utilities for loading and querying GTFS feed files."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


class GTFSLoader:
    """Load and inspect a GTFS data directory.

    This class validates the required GTFS files, loads them into pandas
    DataFrames, and provides convenience methods for accessing route and stop
    information.
    """

    REQUIRED_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
    OPTIONAL_FILES = ("shapes.txt",)

    def __init__(self, data_path: str) -> None:
        """Initialize the loader.

        Args:
            data_path: Path to the GTFS feed directory.

        Raises:
            FileNotFoundError: If the provided path does not exist.
        """
        self.data_path = Path(data_path).expanduser().resolve()
        self.logger = logging.getLogger(__name__)

        if not self.data_path.exists() or not self.data_path.is_dir():
            raise FileNotFoundError(f"GTFS data path does not exist: {self.data_path}")

        self._stops: Optional[pd.DataFrame] = None
        self._routes: Optional[pd.DataFrame] = None
        self._trips: Optional[pd.DataFrame] = None
        self._stop_times: Optional[pd.DataFrame] = None
        self._shapes: Optional[pd.DataFrame] = None
        self._loaded = False

    @property
    def stops(self) -> pd.DataFrame:
        """Return the loaded stops table."""
        if self._stops is None:
            self.load()
        return self._stops

    @property
    def routes(self) -> pd.DataFrame:
        """Return the loaded routes table."""
        if self._routes is None:
            self.load()
        return self._routes

    @property
    def trips(self) -> pd.DataFrame:
        """Return the loaded trips table."""
        if self._trips is None:
            self.load()
        return self._trips

    @property
    def stop_times(self) -> pd.DataFrame:
        """Return the loaded stop_times table."""
        if self._stop_times is None:
            self.load()
        return self._stop_times

    @property
    def shapes(self) -> Optional[pd.DataFrame]:
        """Return the loaded shapes table, or None if it is unavailable."""
        if self._shapes is None and not self._loaded:
            self.load()
        return self._shapes

    def _validate_required_files(self) -> None:
        """Ensure all required GTFS files are present."""
        missing_files = [name for name in self.REQUIRED_FILES if not (self.data_path / name).is_file()]
        if missing_files:
            message = "Missing required GTFS files: " + ", ".join(missing_files)
            self.logger.error(message)
            raise FileNotFoundError(message)

    def load(self) -> "GTFSLoader":
        """Load all GTFS files into pandas DataFrames.

        Returns:
            The current loader instance for chaining.

        Raises:
            RuntimeError: If the GTFS files cannot be read.
        """
        try:
            self._validate_required_files()

            self._stops = pd.read_csv(self.data_path / "stops.txt", dtype=str)
            self._routes = pd.read_csv(self.data_path / "routes.txt", dtype=str)
            self._trips = pd.read_csv(self.data_path / "trips.txt", dtype=str)
            self._stop_times = pd.read_csv(self.data_path / "stop_times.txt", dtype=str)

            shapes_path = self.data_path / "shapes.txt"
            if shapes_path.exists() and shapes_path.is_file():
                self._shapes = pd.read_csv(shapes_path, dtype=str)
                self.logger.info("Loaded optional GTFS shapes file from %s", shapes_path)
            else:
                self._shapes = None
                self.logger.warning("Optional GTFS shapes.txt was not found in %s", self.data_path)

            self._loaded = True
            self.logger.info("Successfully loaded GTFS feed from %s", self.data_path)
            return self

        except FileNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to load GTFS data from {self.data_path}: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def summary(self) -> Dict[str, Any]:
        """Return a simple summary of the loaded GTFS tables.

        Returns:
            A dictionary with row counts for each GTFS table.
        """
        if not self._loaded:
            self.load()

        summary_data: Dict[str, Any] = {}
        summary_data["stops"] = len(self._stops) if self._stops is not None else 0
        summary_data["routes"] = len(self._routes) if self._routes is not None else 0
        summary_data["trips"] = len(self._trips) if self._trips is not None else 0
        summary_data["stop_times"] = len(self._stop_times) if self._stop_times is not None else 0
        summary_data["shapes"] = len(self._shapes) if self._shapes is not None else 0
        return summary_data

    def get_stop_by_id(self, stop_id: str) -> Optional[pd.Series]:
        """Return a stop row by its stop_id.

        Args:
            stop_id: The stop identifier to look up.

        Returns:
            The matching row as a pandas Series, or None if not found.
        """
        if self._stops is None:
            self.load()

        if self._stops is None:
            return None

        matches = self._stops[self._stops["stop_id"].astype(str) == str(stop_id)]
        if matches.empty:
            return None
        return matches.iloc[0]

    def get_route_by_id(self, route_id: str) -> Optional[pd.Series]:
        """Return a route row by its route_id.

        Args:
            route_id: The route identifier to look up.

        Returns:
            The matching row as a pandas Series, or None if not found.
        """
        if self._routes is None:
            self.load()

        if self._routes is None:
            return None

        matches = self._routes[self._routes["route_id"].astype(str) == str(route_id)]
        if matches.empty:
            return None
        return matches.iloc[0]
