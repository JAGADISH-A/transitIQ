"""Rule-based journey insight engine.

Computes travel insights from journey metadata without LLM involvement.
All rules are deterministic and conservative.
"""

import logging
from datetime import datetime
from typing import Any

from app.models.conversation import JourneyInsights
from app.models.journey_context import PersistentJourneyContext

logger = logging.getLogger(__name__)


class JourneyInsightsEngine:
    """Generate deterministic travel insights for a journey."""

    OVERNIGHT_THRESHOLD = 60  # min departure after 21:00 or arrival before 06:00
    LONG_JOURNEY_THRESHOLD = 480  # 8 hours
    SHORT_TRIP_THRESHOLD = 60  # 1 hour
    MANY_STOPS_THRESHOLD = 15
    EXPRESS_STOPS_THRESHOLD = 3
    TIGHT_CONNECTION_THRESHOLD = 10  # minutes
    COMFORTABLE_CONNECTION_MIN = 15
    COMFORTABLE_CONNECTION_MAX = 45

    def get_insights(
        self,
        journey: PersistentJourneyContext | None = None,
        departure_time: str | None = None,
        arrival_time: str | None = None,
        duration_min: int | None = None,
        stop_count: int = 0,
        transfer_count: int = 0,
        transfer_wait_min: int | None = None,
    ) -> JourneyInsights:
        """Compute journey insights from available data."""
        insights = JourneyInsights()

        if journey:
            departure_time = departure_time or journey.departure_time
            arrival_time = arrival_time or journey.arrival_time
            duration_min = duration_min or journey.duration
            stop_count = stop_count or len(journey.stop_sequence)
            transfer_count = transfer_count or journey.transfer_count

        self._classify_time(insights, departure_time, arrival_time)
        self._classify_length(insights, duration_min)
        self._classify_stops(insights, stop_count)
        self._classify_transfer(insights, transfer_count, transfer_wait_min)

        logger.info(
            "[JOURNEY_INSIGHTS] Generated: overnight=%s daytime=%s long=%s short=%s transfer=%s",
            insights.is_overnight, insights.is_daytime,
            insights.is_long_journey, insights.is_short_trip,
            insights.requires_transfer,
        )
        return insights

    @staticmethod
    def _parse_time(time_str: str | None) -> int | None:
        """Parse HH:MM (or HH:MM:SS) to minutes since midnight."""
        if not time_str or not isinstance(time_str, str) or time_str.strip() == "nan":
            return None
        try:
            parts = time_str.strip().split(":")
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            return hours * 60 + minutes
        except (ValueError, IndexError):
            return None

    def _classify_time(
        self,
        insights: JourneyInsights,
        departure: str | None,
        arrival: str | None,
    ) -> None:
        """Determine if journey is overnight, daytime, or neither."""
        dep_min = self._parse_time(departure)
        arr_min = self._parse_time(arrival)

        if dep_min is not None and arr_min is not None:
            if dep_min >= 1260 or arr_min <= 360:
                insights.is_overnight = True
            elif dep_min >= 21 * 60 and arr_min <= 6 * 60:
                insights.is_overnight = True
            elif arr_min < dep_min:
                insights.is_overnight = True

            if 360 <= dep_min <= 1320 and 360 <= arr_min <= 1320:
                if not insights.is_overnight:
                    insights.is_daytime = True
        elif dep_min is not None:
            if dep_min >= 1260 or dep_min < 360:
                insights.is_overnight = True
            if 360 <= dep_min <= 1320:
                insights.is_daytime = True
        elif arr_min is not None:
            if arr_min < 360:
                insights.is_overnight = True
            if 360 <= arr_min <= 1320:
                insights.is_daytime = True

    def _classify_length(
        self,
        insights: JourneyInsights,
        duration_min: int | None,
    ) -> None:
        """Classify journey length."""
        if duration_min is not None:
            if duration_min >= self.LONG_JOURNEY_THRESHOLD:
                insights.is_long_journey = True
            if duration_min <= self.SHORT_TRIP_THRESHOLD:
                insights.is_short_trip = True

    def _classify_stops(
        self,
        insights: JourneyInsights,
        stop_count: int,
    ) -> None:
        """Classify based on stop count."""
        if stop_count >= self.MANY_STOPS_THRESHOLD:
            insights.many_stops = True
        if 0 < stop_count <= self.EXPRESS_STOPS_THRESHOLD:
            insights.express_trip = True

    def _classify_transfer(
        self,
        insights: JourneyInsights,
        transfer_count: int,
        transfer_wait_min: int | None,
    ) -> None:
        """Classify transfer characteristics."""
        if transfer_count > 0:
            insights.requires_transfer = True

        if transfer_wait_min is not None:
            if transfer_wait_min < self.TIGHT_CONNECTION_THRESHOLD:
                insights.tight_connection = True
            if (
                self.COMFORTABLE_CONNECTION_MIN
                <= transfer_wait_min
                <= self.COMFORTABLE_CONNECTION_MAX
            ):
                insights.comfortable_connection = True


journey_insights_engine = JourneyInsightsEngine()
