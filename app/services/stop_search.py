"""Utilities for searching GTFS stop records."""

import logging
from typing import List

import pandas as pd
from app.models.schemas import StopResult


class StopSearch:
    """Search GTFS stop records using case-insensitive partial matching.

    The search is designed to work with a pandas DataFrame containing GTFS
    stop information, including at least the standard columns
    ``stop_id``, ``stop_name``, ``stop_lat``, and ``stop_lon``.
    """

    REQUIRED_COLUMNS = ("stop_id", "stop_name", "stop_lat", "stop_lon")

    def __init__(self, stops: pd.DataFrame) -> None:
        """Initialize the search index.

        Args:
            stops: A pandas DataFrame containing GTFS stop records.

        Raises:
            TypeError: If ``stops`` is not a pandas DataFrame.
            ValueError: If required columns are missing.
        """
        self.logger = logging.getLogger(__name__)

        if not isinstance(stops, pd.DataFrame):
            message = "Expected a pandas DataFrame for stops."
            self.logger.error(message)
            raise TypeError(message)

        missing_columns = [column for column in self.REQUIRED_COLUMNS if column not in stops.columns]
        if missing_columns:
            message = "Missing required stop columns: " + ", ".join(missing_columns)
            self.logger.error(message)
            raise ValueError(message)

        self.stops = stops.copy()

    def search(self, query: str) -> List[StopResult]:
        """Search for stops using partial, case-insensitive matching.

        Matches are scored so best results appear first. The method returns at
        most 10 results.

        Args:
            query: The user search text.

        Returns:
            A list of ``StopResult`` models sorted by relevance.
        """
        try:
            if not isinstance(query, str):
                raise ValueError("Search query must be a string.")

            normalized_query = query.strip().casefold()
            if not normalized_query:
                return []

            if self.stops.empty:
                return []

            scored_results: List[tuple[int, str, pd.Series]] = []

            for _, row in self.stops.iterrows():
                stop_name = str(row.get("stop_name", "")).strip()
                stop_id = str(row.get("stop_id", "")).strip()
                name_lower = stop_name.casefold()
                id_lower = stop_id.casefold()

                score = 0
                if name_lower.startswith(normalized_query):
                    score += 100
                if normalized_query in name_lower:
                    score += 50
                if normalized_query in id_lower:
                    score += 20

                if score == 0:
                    continue

                scored_results.append((score, name_lower, row))

            scored_results.sort(key=lambda item: (-item[0], item[1], str(item[2].get("stop_id", ""))))

            matches = []
            for _, _, row in scored_results[:10]:
                try:
                    matches.append(
                        StopResult(
                            stop_id=str(row.get("stop_id", "")),
                            stop_name=str(row.get("stop_name", "")),
                            lat=float(row.get("stop_lat", 0.0)),
                            lon=float(row.get("stop_lon", 0.0)),
                        )
                    )
                except (TypeError, ValueError) as exc:
                    self.logger.warning("Skipping invalid stop row during search: %s", exc)
                    continue

            return matches

        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Stop search failed: {exc}"
            self.logger.exception(message)
            return []
