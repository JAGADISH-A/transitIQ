"""Deterministic route intelligence service.

Classifies and analyzes routes using GTFS data and distance heuristics.
"""

import logging
from typing import Any

from app.models.conversation import RouteInsights

logger = logging.getLogger(__name__)


class RouteIntelligence:
    """Analyze route characteristics from journey data."""

    def get_route_insights(
        self,
        stop_count: int = 0,
        transfer_count: int = 0,
        duration_min: int | None = None,
        distance_km: float | None = None,
        stops_between: int = 0,
    ) -> RouteInsights:
        """Generate deterministic insights about a route."""
        insights = RouteInsights(
            stop_count=stop_count,
            transfer_count=transfer_count,
            duration_min=duration_min,
            distance_km=distance_km,
        )

        self._classify_route_type(insights)
        self._classify_service_scope(insights)
        self._compute_major_junctions(insights)

        logger.info(
            "[ROUTE_INTELLIGENCE] Insights: type=%s scope=%s stops=%d transfers=%d",
            insights.route_type, insights.service_scope,
            insights.stop_count, insights.transfer_count,
        )
        return insights

    def _classify_route_type(self, insights: RouteInsights) -> None:
        """Classify whether the route is direct, transfer, or circular."""
        if insights.transfer_count == 0:
            insights.route_type = "direct"
        elif insights.transfer_count == 1:
            insights.route_type = "transfer"
        elif insights.transfer_count >= 2:
            insights.route_type = "multi-transfer"

    def _classify_service_scope(self, insights: RouteInsights) -> None:
        """Classify the service scope based on duration and stops."""
        if insights.duration_min is not None:
            if insights.duration_min >= 600:
                insights.service_scope = "long-distance"
            elif insights.duration_min >= 180:
                insights.service_scope = "regional"
            elif insights.duration_min >= 60:
                insights.service_scope = "intercity"
            else:
                insights.service_scope = "suburban"
        elif insights.stop_count >= 20:
            insights.service_scope = "long-distance"
        elif insights.stop_count >= 8:
            insights.service_scope = "regional"
        elif insights.stop_count >= 3:
            insights.service_scope = "intercity"
        else:
            insights.service_scope = "suburban"

    def _compute_major_junctions(self, insights: RouteInsights) -> None:
        """Identify major junctions along the route.
        This is a placeholder — full implementation requires GTFS trip data.
        """
        if insights.stop_count > 10:
            insights.major_junctions = []
        elif insights.stop_count > 5:
            insights.major_junctions = []

    def get_route_classification_label(self, insights: RouteInsights) -> str:
        """Return a human-readable route classification label."""
        parts = [insights.service_scope.replace("-", " ").title()]
        if insights.route_type == "transfer":
            parts.append("with Transfer")
        elif insights.route_type == "multi-transfer":
            parts.append("with Multiple Transfers")
        return " · ".join(parts)


route_intelligence = RouteIntelligence()
