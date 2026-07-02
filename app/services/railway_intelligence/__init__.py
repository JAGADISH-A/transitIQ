"""Railway Intelligence Layer — Phase 4 of TransitIQ.

Every capability is independent and composable.
The backend computes railway knowledge deterministically.
"""

import logging
from typing import Any

from app.models.conversation import (
    CapabilityType,
    ConversationContext,
    Explanation,
    IntentType,
    JourneyInsights,
    RailwayKnowledge,
    ReasoningStrategy,
    TrainProfile,
    StationProfile,
    RouteInsights,
    ComparisonItem,
    ComparisonResultExtended,
)

from app.services.railway_intelligence.train_intelligence import train_intelligence
from app.services.railway_intelligence.station_intelligence import station_intelligence
from app.services.railway_intelligence.route_intelligence import route_intelligence
from app.services.railway_intelligence.journey_insights import journey_insights_engine
from app.services.railway_intelligence.recommendation_engine import recommendation_engine
from app.services.railway_intelligence.comparison_engine import comparison_engine
from app.services.railway_intelligence.explanation_engine import explanation_engine
from app.services.railway_intelligence.knowledge_engine import knowledge_engine

logger = logging.getLogger(__name__)


class RailwayIntelligenceOrchestrator:
    """Orchestrates all railway intelligence engines.

    Determines which engines to run based on context and intent,
    and returns structured data for the PromptBuilder.
    """

    def __init__(self) -> None:
        self.train_intel = train_intelligence
        self.station_intel = station_intelligence
        self.route_intel = route_intelligence
        self.insights = journey_insights_engine
        self.recommendation = recommendation_engine
        self.comparison = comparison_engine
        self.explanation = explanation_engine
        self.knowledge = knowledge_engine

    def process(
        self,
        intent: IntentType,
        query: str,
        ctx: ConversationContext,
    ) -> dict[str, Any]:
        """Run relevant intelligence engines based on intent and context.

        Returns a dict with structured railway intelligence data fields.
        """
        data: dict[str, Any] = {}
        start_time = __import__("time").perf_counter()

        journey = ctx.current_journey

        if intent == IntentType.TRAIN_INFORMATION:
            data = self._handle_train_intel(query, journey)
        elif intent == IntentType.STATION_INFORMATION:
            data = self._handle_station_intel(query)
        elif intent == IntentType.KNOWLEDGE_QUERY:
            data = self._handle_knowledge(query)
        elif intent in (IntentType.COMPARISON, IntentType.RECOMMENDATION):
            data = self._handle_comparison_recommendation(intent, query, ctx)

        if journey and intent in (
            IntentType.ROUTE_CONTEXT_QA,
            IntentType.ROUTE_EXPLANATION,
            IntentType.FOLLOW_UP,
        ):
            data["journey_insights"] = self.insights.get_insights(journey=journey)
            data["train_profile"] = self.train_intel.get_train_profile(
                train_number=journey.train_number,
                train_name=journey.train_name,
                feed=journey.feed_name,
                trip_id=journey.trip_id,
            )
            data["route_insights"] = self.route_intel.get_route_insights(
                stop_count=len(journey.stop_sequence),
                transfer_count=journey.transfer_count,
                duration_min=journey.duration,
            )

        elapsed_ms = int((__import__("time").perf_counter() - start_time) * 1000)
        if data:
            engines = [k for k in data.keys()]
            logger.info(
                "[RAILWAY_INTELLIGENCE] intent=%s engines=%s elapsed=%dms",
                intent.value, engines, elapsed_ms,
            )

        return data

    def _handle_train_intel(
        self,
        query: str,
        journey: Any,
    ) -> dict[str, Any]:
        """Handle train information requests."""
        data: dict[str, Any] = {}

        if journey:
            profile = self.train_intel.get_train_profile(
                train_number=journey.train_number,
                train_name=journey.train_name,
                feed=journey.feed_name,
                trip_id=journey.trip_id,
            )
            data["train_profile"] = profile
            data["journey_insights"] = self.insights.get_insights(journey=journey)
            data["route_insights"] = self.route_intel.get_route_insights(
                stop_count=len(journey.stop_sequence),
                transfer_count=journey.transfer_count,
                duration_min=journey.duration,
            )
        else:
            import re
            train_match = re.search(r"\b(\d{4,5})\b", query)
            if train_match:
                profile = self.train_intel.get_train_profile(
                    train_number=train_match.group(1),
                    train_name="",
                )
                data["train_profile"] = profile

        return data

    def _handle_station_intel(self, query: str) -> dict[str, Any]:
        """Handle station information requests."""
        data: dict[str, Any] = {}
        import re

        station_name = self._extract_station_name(query)
        if station_name:
            profile = self.station_intel.get_station_profile(station_name=station_name)
            data["station_profile"] = profile

        return data

    def _handle_knowledge(self, query: str) -> dict[str, Any]:
        """Handle railway knowledge queries."""
        data: dict[str, Any] = {}
        answer = self.knowledge.answer(query)
        if answer:
            data["railway_knowledge"] = answer
        return data

    def _handle_comparison_recommendation(
        self,
        intent: IntentType,
        query: str,
        ctx: ConversationContext,
    ) -> dict[str, Any]:
        """Handle comparison and recommendation requests."""
        data: dict[str, Any] = {}
        journey = ctx.current_journey

        items: list[ComparisonItem] = []

        if ctx.comparison_result and ctx.comparison_result.items:
            items = ctx.comparison_result.items
        elif journey:
            items.append(ComparisonItem(
                label=f"{journey.train_name} ({journey.train_number})",
                duration_min=journey.duration,
                stop_count=len(journey.stop_sequence),
                departure_time=journey.departure_time,
                arrival_time=journey.arrival_time,
                train_name=journey.train_name,
                train_number=journey.train_number,
            ))

        if items:
            if intent == IntentType.RECOMMENDATION:
                criteria = self._detect_criteria(query)
                rec = self.recommendation.compute(items=items, criteria=criteria)
                data["recommendation_result"] = rec
                data["explanation"] = self.explanation.explain_recommended(
                    reason=rec.justification, criteria=rec.criteria,
                )
            elif intent == IntentType.COMPARISON:
                comp = self.comparison.compare_all(items)
                data["comparison_extended"] = comp
                data["explanation"] = self._explain_comparison(comp)

        return data

    @staticmethod
    def _detect_criteria(query: str) -> str:
        """Detect recommendation criteria from query text."""
        q = query.lower()
        if any(w in q for w in ["fastest", "quickest", "shortest dur"]):
            return "fastest"
        if "fewest stop" in q or "least stop" in q:
            return "fewest_stops"
        if "earliest" in q or "early" in q:
            return "earliest_arrival"
        if "latest" in q:
            return "latest_departure"
        return "recommended"

    @staticmethod
    def _explain_comparison(comp: ComparisonResultExtended) -> Explanation:
        """Generate explanation from comparison result."""
        reason = f"Comparison result: {comp.winner} wins"
        if comp.advantages:
            reason = "; ".join(comp.advantages)
        suggestion = "Consider the advantages listed above for your decision."
        return Explanation(
            reason=reason,
            details=comp.advantages + comp.disadvantages,
            suggestion=suggestion,
        )

    @staticmethod
    def _extract_station_name(text: str) -> str | None:
        """Best-effort extraction of a station name from query."""
        import re

        patterns = [
            re.compile(r"(?:tell me about|about|info on|info about|search)\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"(?:station|stop)\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"where is\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"what stations?\s+(?:are|is)\s+(?:in|near|at|on)\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"(?:is|was)\s+(.+?)\s+(?:a|an|the)?\s*(?:junction|terminal|station|stop)\b", re.IGNORECASE),
        ]

        for p in patterns:
            match = p.search(text)
            if match:
                return match.group(1).strip()
        return None


railway_intelligence = RailwayIntelligenceOrchestrator()
