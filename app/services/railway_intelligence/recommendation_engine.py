"""Deterministic recommendation engine.

Computes route/train recommendations using scoring criteria without LLM.
"""

import logging
from typing import Any

from app.models.conversation import RecommendationResult, ComparisonItem
from app.models.journey_context import PersistentJourneyContext

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Compute recommendations using structured scoring criteria."""

    def compute(
        self,
        items: list[ComparisonItem] = None,
        criteria: str = "recommended",
    ) -> RecommendationResult:
        """Compute the best option from a list of comparison items.

        Supported criteria:
          - "fastest" / "shortest_duration"
          - "fewest_transfers"
          - "earliest_arrival"
          - "latest_departure"
          - "fewest_stops"
          - "longest_transfer_buffer"
          - "recommended" (weighted composite)
        """
        if not items:
            return RecommendationResult()

        result = RecommendationResult(criteria=criteria)

        if criteria == "shortest_duration" or criteria == "fastest":
            idx = self._find_fastest(items)
            result.recommended_idx = idx
            result.criteria = criteria
            if idx >= 0:
                result.justification = (
                    f"Shortest travel time at {items[idx].duration_min} minutes."
                )
        elif criteria == "fewest_stops":
            idx = self._find_fewest_stops(items)
            result.recommended_idx = idx
            if idx >= 0:
                result.justification = (
                    f"Fewest stops with {items[idx].stop_count} stops."
                )
        elif criteria == "earliest_arrival":
            idx = self._find_earliest_arrival(items)
            result.recommended_idx = idx
            result.criteria = criteria
            if idx >= 0:
                result.justification = (
                    f"Earliest arrival at {items[idx].arrival_time}."
                )
        elif criteria == "latest_departure":
            idx = self._find_latest_departure(items)
            result.recommended_idx = idx
            result.criteria = criteria
            if idx >= 0:
                result.justification = (
                    f"Latest departure at {items[idx].departure_time}."
                )
        else:
            idx = self._find_recommended(items)
            result.recommended_idx = idx
            result.criteria = "recommended"
            if idx >= 0:
                result.justification = (
                    f"Best overall option: {items[idx].duration_min} min, "
                    f"{items[idx].stop_count} stops."
                )

        logger.info(
            "[RECOMMENDATION] criteria=%s idx=%d items=%d",
            result.criteria, result.recommended_idx, len(items),
        )
        return result

    def compute_from_journey(
        self,
        journey: PersistentJourneyContext | None,
    ) -> RecommendationResult:
        """Compute a simple recommendation from a single journey context."""
        if journey is None:
            return RecommendationResult()

        item = ComparisonItem(
            label=f"{journey.train_name} ({journey.train_number})",
            duration_min=journey.duration,
            stop_count=len(journey.stop_sequence),
            departure_time=journey.departure_time,
            arrival_time=journey.arrival_time,
            train_name=journey.train_name,
            train_number=journey.train_number,
        )
        return self.compute(items=[item], criteria="recommended")

    @staticmethod
    def _find_fastest(items: list[ComparisonItem]) -> int:
        best_idx = -1
        best_duration = float("inf")
        for i, item in enumerate(items):
            if item.duration_min > 0 and item.duration_min < best_duration:
                best_duration = item.duration_min
                best_idx = i
        return best_idx

    @staticmethod
    def _find_fewest_stops(items: list[ComparisonItem]) -> int:
        best_idx = -1
        best_stops = float("inf")
        for i, item in enumerate(items):
            if item.stop_count > 0 and item.stop_count < best_stops:
                best_stops = item.stop_count
                best_idx = i
        return best_idx

    @staticmethod
    def _find_earliest_arrival(items: list[ComparisonItem]) -> int:
        best_idx = -1
        best_arrival = "99:99"
        for i, item in enumerate(items):
            if item.arrival_time and item.arrival_time < best_arrival:
                best_arrival = item.arrival_time
                best_idx = i
        return best_idx

    @staticmethod
    def _find_latest_departure(items: list[ComparisonItem]) -> int:
        best_idx = -1
        best_departure = "00:00"
        for i, item in enumerate(items):
            if item.departure_time and item.departure_time > best_departure:
                best_departure = item.departure_time
                best_idx = i
        return best_idx

    def _find_recommended(self, items: list[ComparisonItem]) -> int:
        """Weighted composite scoring for best overall option.

        Scoring factors (lower is better):
          - Duration (40%)
          - Stop count (25%)
          - Arrival time (20%)  — earlier is better
          - Departure time (15%) — later is better
        """
        if not items:
            return -1

        scores = []
        for item in items:
            score = 0.0

            dur = item.duration_min if item.duration_min > 0 else 600
            score += 0.40 * min(dur / 600, 2.0)

            stops = item.stop_count if item.stop_count > 0 else 10
            score += 0.25 * min(stops / 30, 2.0)

            if item.arrival_time:
                try:
                    h, m = map(int, item.arrival_time.split(":")[:2])
                    arr_mins = h * 60 + m
                    score += 0.20 * min(arr_mins / 1440, 1.0)
                except (ValueError, IndexError):
                    score += 0.20

            if item.departure_time:
                try:
                    h, m = map(int, item.departure_time.split(":")[:2])
                    dep_mins = h * 60 + m
                    score += 0.15 * (1.0 - min(dep_mins / 1440, 1.0))
                except (ValueError, IndexError):
                    score += 0.15

            scores.append(score)

        if not scores:
            return -1
        return scores.index(min(scores))


recommendation_engine = RecommendationEngine()
