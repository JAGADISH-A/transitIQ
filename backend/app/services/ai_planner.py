"""Simple AI-facing transit planning helpers."""

import logging
from typing import Optional, Dict, Any

from app.models.schemas import StopResult
from app.services.agent_tools import agent_tools


class TransitAIPlanner:
    """Provide simple destination lookup and trip-planning helpers for AI use."""

    def __init__(self) -> None:
        """Initialize the planner and logger."""
        self.logger = logging.getLogger(__name__)

    def find_destination_stop(self, destination: str) -> Optional[StopResult]:
        """Find the first matching stop for a destination search query.

        Args:
            destination: Search text to use when looking up a destination stop.

        Returns:
            The first matching StopResult if one is found; otherwise None.
        """
        try:
            if not isinstance(destination, str) or not destination.strip():
                raise ValueError("destination must be a non-empty string.")

            results = agent_tools.search_stops(destination)
            stop = results[0] if results else None
            if stop is not None:
                self.logger.info(
                    "Found destination stop '%s' (%s) for query '%s'",
                    stop.stop_name,
                    stop.stop_id,
                    destination,
                )
            else:
                self.logger.warning("No destination stop found for query '%s'", destination)
            return stop
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to find destination stop for '{destination}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def answer_query(self, user_query: str) -> dict:
        """Answer a natural-language destination query using stop lookup.

        Args:
            user_query: The user's natural-language destination query.

        Returns:
            A dictionary with either a structured failure response or a
            successful destination match answer.
        """
        try:
            if not isinstance(user_query, str) or not user_query.strip():
                self.logger.warning("Empty user query received.")
                return {
                    "success": False,
                    "answer": "I could not find a matching destination.",
                }

            normalized = user_query.strip().lower()
            prefixes = ("take me to ", "go to ", "travel to ", "reach ")
            destination = user_query.strip()

            for prefix in prefixes:
                if normalized.startswith(prefix):
                    destination = user_query.strip()[len(prefix):].strip()
                    break

            self.logger.info("Processing destination query: '%s'", user_query)
            self.logger.info("Normalized destination phrase: '%s'", destination)

            stop = self.find_destination_stop(destination)
            if stop is None:
                self.logger.warning("No destination found for query '%s'", user_query)
                return {
                    "success": False,
                    "answer": "I could not find a matching destination.",
                }

            self.logger.info("Resolved destination '%s' to stop '%s'", destination, stop.stop_name)
            return {
                "success": True,
                "answer": f"I found a matching stop: {stop.stop_name} (Stop ID: {stop.stop_id}).",
                "destination": stop.stop_name,
                "stop_id": stop.stop_id,
                "latitude": stop.lat,
                "longitude": stop.lon,
            }
        except Exception as exc:  # pragma: no cover - defensive error handling
            self.logger.exception("Failed to answer user query '%s': %s", user_query, exc)
            return {
                "success": False,
                "answer": "I could not find a matching destination.",
            }

    def plan_trip(self, destination: str) -> Dict[str, Any]:
        """Build a simple trip-planning result for a destination query.

        Args:
            destination: The destination text to search for.

        Returns:
            A dictionary indicating whether the destination was found and,
            when successful, the stop details for the destination.
        """
        try:
            if not isinstance(destination, str) or not destination.strip():
                raise ValueError("destination must be a non-empty string.")

            stop = self.find_destination_stop(destination)
            if stop is None:
                return {
                    "success": False,
                    "message": f"Could not find destination '{destination}'.",
                }

            return {
                "success": True,
                "destination": stop.stop_name,
                "stop_id": stop.stop_id,
                "latitude": stop.lat,
                "longitude": stop.lon,
            }
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to plan trip for destination '{destination}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc


ai_planner = TransitAIPlanner()
