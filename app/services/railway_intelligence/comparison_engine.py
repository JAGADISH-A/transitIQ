"""Deterministic comparison engine.

Compares routes or trains using structured criteria without LLM.
"""

import logging
from typing import Any

from app.models.conversation import (
    ComparisonResult,
    ComparisonResultExtended,
    ComparisonTable,
    ComparisonItem,
)

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """Compare routes or trains across multiple dimensions."""

    def compare_all(
        self,
        items: list[ComparisonItem],
    ) -> ComparisonResultExtended:
        """Compare all options and return structured results with winner."""
        extended = ComparisonResultExtended()

        if len(items) < 2:
            return extended

        if len(items) == 2:
            tables = self._build_comparison_tables(items[0], items[1])
            extended.comparison_table = tables
            a, b = items[0], items[1]
            extended.winner, adv, disadv = self._determine_winner(a, b)
            extended.advantages = adv
            extended.disadvantages = disadv
        else:
            fastest = self._find_fastest(items)
            fewest = self._find_fewest_stops(items)
            earliest = self._find_earliest_arrival(items)
            tables = []
            for i, item in enumerate(items):
                vals = f"{item.duration_min} min, {item.stop_count} stops"
                if item.departure_time and item.arrival_time:
                    vals += f", {item.departure_time}-{item.arrival_time}"
                tables.append(ComparisonTable(
                    attribute=f"Option {i + 1}: {item.label}",
                    value_a=vals,
                    value_b="",
                    winner="",
                ))

            advantages = []
            if fastest >= 0:
                advantages.append(
                    f"Fastest: {items[fastest].label} ({items[fastest].duration_min} min)"
                )
            if fewest >= 0:
                advantages.append(
                    f"Fewest stops: {items[fewest].label} ({items[fewest].stop_count})"
                )
            if earliest >= 0:
                advantages.append(
                    f"Earliest arrival: {items[earliest].label} ({items[earliest].arrival_time})"
                )
            extended.comparison_table = tables
            extended.advantages = advantages

            fastest_label = items[fastest].label if fastest >= 0 else "unknown"
            extended.winner = f"Fastest: {fastest_label}"

        logger.info(
            "[COMPARISON] Compared %d items, winner=%s",
            len(items), extended.winner,
        )
        return extended

    def compare_first_two(
        self,
        items: list[ComparisonItem],
    ) -> ComparisonResultExtended:
        """Compare only the first two items."""
        if len(items) < 2:
            return ComparisonResultExtended()
        return self.compare_all(items[:2])

    def compare_specific(
        self,
        a: ComparisonItem,
        b: ComparisonItem,
    ) -> ComparisonResultExtended:
        """Compare two specific items."""
        return self.compare_all([a, b])

    @staticmethod
    def _build_comparison_tables(
        a: ComparisonItem,
        b: ComparisonItem,
    ) -> list[ComparisonTable]:
        tables = []
        winner_fastest = "a" if (a.duration_min or 9999) < (b.duration_min or 9999) else "b"
        if a.duration_min == b.duration_min:
            winner_fastest = "tie"
        tables.append(ComparisonTable(
            attribute="Duration (min)",
            value_a=str(a.duration_min) if a.duration_min else "N/A",
            value_b=str(b.duration_min) if b.duration_min else "N/A",
            winner=winner_fastest,
        ))

        winner_stops = "a" if (a.stop_count or 999) < (b.stop_count or 999) else "b"
        if a.stop_count == b.stop_count:
            winner_stops = "tie"
        tables.append(ComparisonTable(
            attribute="Stops",
            value_a=str(a.stop_count) if a.stop_count else "N/A",
            value_b=str(b.stop_count) if b.stop_count else "N/A",
            winner=winner_stops,
        ))

        if a.departure_time and b.departure_time:
            winner_dep = "a" if a.departure_time > b.departure_time else "b"
            if a.departure_time == b.departure_time:
                winner_dep = "tie"
            tables.append(ComparisonTable(
                attribute="Departure",
                value_a=a.departure_time,
                value_b=b.departure_time,
                winner=winner_dep,
            ))

        if a.arrival_time and b.arrival_time:
            winner_arr = "a" if a.arrival_time < b.arrival_time else "b"
            if a.arrival_time == b.arrival_time:
                winner_arr = "tie"
            tables.append(ComparisonTable(
                attribute="Arrival",
                value_a=a.arrival_time,
                value_b=b.arrival_time,
                winner=winner_arr,
            ))

        return tables

    @staticmethod
    def _determine_winner(
        a: ComparisonItem,
        b: ComparisonItem,
    ) -> tuple[str, list[str], list[str]]:
        """Determine the winner and compile advantages/disadvantages."""
        advantages_a = []
        advantages_b = []

        if a.duration_min and b.duration_min:
            if a.duration_min < b.duration_min:
                advantages_a.append(f"{a.duration_min - b.duration_min} min faster")
            elif b.duration_min < a.duration_min:
                advantages_b.append(f"{b.duration_min - a.duration_min} min faster")

        if a.stop_count and b.stop_count:
            if a.stop_count < b.stop_count:
                advantages_a.append(f"{b.stop_count - a.stop_count} fewer stops")
            elif b.stop_count < a.stop_count:
                advantages_b.append(f"{a.stop_count - b.stop_count} fewer stops")

        if a.departure_time and b.departure_time:
            if a.departure_time > b.departure_time:
                advantages_a.append(f"Later departure ({a.departure_time})")
            else:
                advantages_b.append(f"Later departure ({b.departure_time})")

        if a.arrival_time and b.arrival_time:
            if a.arrival_time < b.arrival_time:
                advantages_a.append(f"Earlier arrival ({a.arrival_time})")
            else:
                advantages_b.append(f"Earlier arrival ({b.arrival_time})")

        score_a = len(advantages_a)
        score_b = len(advantages_b)

        if score_a > score_b:
            return "a", advantages_a, advantages_b
        elif score_b > score_a:
            return "b", advantages_b, advantages_a
        else:
            return "tie", advantages_a, advantages_b

    @staticmethod
    def _find_fastest(items: list[ComparisonItem]) -> int:
        best_idx = -1
        best_duration = float("inf")
        for i, item in enumerate(items):
            if item.duration_min and item.duration_min < best_duration:
                best_duration = item.duration_min
                best_idx = i
        return best_idx

    @staticmethod
    def _find_fewest_stops(items: list[ComparisonItem]) -> int:
        best_idx = -1
        best_stops = float("inf")
        for i, item in enumerate(items):
            if item.stop_count and item.stop_count < best_stops:
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


comparison_engine = ComparisonEngine()
