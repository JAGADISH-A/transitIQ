"""Response Formatter — orchestrator for backend-first responses.

Orchestrates templates, markdown, explanations, and personality
to produce polished responses without any LLM involvement.
"""

import logging
from typing import Any

from app.models.conversation import (
    ComparisonResult,
    ComparisonResultExtended,
    ConversationContext,
    Explanation,
    IntentType,
    JourneyInsights,
    RailwayKnowledge,
    RecommendationResult,
    RouteInsights,
    StationProfile,
    TrainProfile,
)
from app.models.journey_context import PersistentJourneyContext

from app.services.response_engine.response_type import ResponseType
from app.services.response_engine.response_templates import ResponseTemplates
from app.services.response_engine.markdown_formatter import MarkdownFormatter
from app.services.response_engine.explanation_builder import ExplanationBuilder
from app.services.response_engine.personality import TransitIQPersonality

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Generates polished, deterministic responses from structured data.

    No prompts. No AI. Pure backend formatting.
    """

    def __init__(self):
        self.templates = ResponseTemplates()
        self.markdown = MarkdownFormatter()
        self.explainer = ExplanationBuilder()

    def format_response(
        self,
        response_type: str,
        ctx: ConversationContext | None = None,
        intent: IntentType | None = None,
        cap_result: Any = None,
    ) -> str | None:
        """Format a response based on the response type and available context.

        Returns None if the type cannot be handled (caller should fall back).
        """
        method_name = f"_format_{response_type.lower()}"
        method = getattr(self, method_name, None)
        if method:
            try:
                result = method(ctx=ctx, intent=intent, cap_result=cap_result)
                if result:
                    return self.markdown.render(result)
            except Exception as exc:
                logger.warning("[RESPONSE_FORMATTER] %s failed: %s", method_name, exc)
        return None

    # ------------------------------------------------------------------
    # Format methods — one per ResponseType
    # ------------------------------------------------------------------

    @staticmethod
    def _format_greeting(**kwargs) -> str:
        return ResponseTemplates.greeting()

    @staticmethod
    def _format_help(**kwargs) -> str:
        return ResponseTemplates.help_text()

    @staticmethod
    def _format_small_talk(**kwargs) -> str:
        return ResponseTemplates.small_talk()

    @staticmethod
    def _format_journey_summary(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        if ctx and ctx.current_journey:
            return ResponseTemplates.journey_summary(ctx.current_journey)
        journey = _get_journey(kwargs.get("cap_result"))
        if journey:
            return ResponseTemplates.journey_summary(journey)
        return ResponseTemplates.no_journey()

    @staticmethod
    def _format_station_profile(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        station = ctx.station_profile if ctx else None
        cap_result = kwargs.get("cap_result")

        station_results = None
        if cap_result and hasattr(cap_result, "context_data"):
            station_results = cap_result.context_data.get("station_results")

        if station:
            return ResponseTemplates.station_profile(station)
        if station_results:
            return ResponseTemplates.station_profile(None, station_results)

        if ctx and ctx.current_journey:
            return _format_journey_based_station(ctx.current_journey)

        return "I couldn't find station information for that query."

    @staticmethod
    def _format_train_profile(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        train = ctx.train_profile if ctx else None
        if train:
            return ResponseTemplates.train_profile(train)
        journey = _get_journey(kwargs.get("cap_result")) or (ctx.current_journey if ctx else None)
        if journey:
            return ResponseTemplates.train_profile(
                TrainProfile(
                    train_number=journey.train_number,
                    train_name=journey.train_name,
                )
            )
        return "I couldn't find information for that train."

    @staticmethod
    def _format_route_overview(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        journey = ctx.current_journey if ctx else None
        if journey:
            insight_text = _build_insight_section(ctx)
            overview = ResponseTemplates.route_overview(journey)
            if insight_text:
                return f"{overview}\n\n{insight_text}"
            return overview
        return ResponseTemplates.no_journey()

    @staticmethod
    def _format_route_explanation(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        explanation = ctx.explanation if ctx else None
        if explanation:
            return ResponseTemplates.route_explanation(explanation)
        journey = ctx.current_journey if ctx else None
        if journey:
            exp = ExplanationBuilder.build_journey_explanation(
                duration=journey.duration,
                stop_count=len(journey.intermediate_stops) if journey.intermediate_stops else 0,
                transfer_count=journey.transfer_count,
            )
            if exp:
                return ResponseTemplates.route_explanation(exp, journey)
        return None

    @staticmethod
    def _format_recommendation(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        rec = ctx.recommendation_result if ctx else None
        journey = ctx.current_journey if ctx else None

        if rec:
            exp = ExplanationBuilder.build_recommendation_explanation(rec)
            template_result = ResponseTemplates.recommendation(rec, journey)
            parts = []
            if exp:
                parts.append(ResponseTemplates.route_explanation(exp))
            if template_result:
                parts.append(template_result)
            if parts:
                return "\n\n".join(parts)

        if journey:
            return ResponseTemplates.journey_summary(journey)

        return None

    @staticmethod
    def _format_comparison(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        comparison = ctx.comparison_extended if ctx else None
        if not comparison:
            comparison = ctx.comparison_result if ctx else None
        if comparison:
            exp = ExplanationBuilder.build_comparison_explanation(comparison)
            template_result = ResponseTemplates.comparison(comparison)
            parts = []
            if template_result:
                parts.append(template_result)
            if exp:
                parts.append(ResponseTemplates.route_explanation(exp))
            if parts:
                return "\n\n".join(parts)
        return None

    @staticmethod
    def _format_clarification(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        if ctx and ctx.clarification and ctx.clarification.needed:
            return ResponseTemplates.clarification_question(ctx.clarification.question)
        return None

    @staticmethod
    def _format_schedule_info(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        journey = ctx.current_journey if ctx else None
        if journey:
            return ResponseTemplates.schedule_info(journey)
        return None

    @staticmethod
    def _format_knowledge(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        knowledge = ctx.railway_knowledge if ctx else None
        if knowledge:
            return ResponseTemplates.knowledge_answer(knowledge)
        return None

    @staticmethod
    def _format_error(**kwargs) -> str:
        return ResponseTemplates.error_message()

    @staticmethod
    def _format_unknown(**kwargs) -> str | None:
        return None

    @staticmethod
    def _format_booking(**kwargs) -> str | None:
        ctx = kwargs.get("ctx")
        journey = ctx.current_journey if ctx else None
        if journey:
            summary = ResponseTemplates.journey_summary(journey)
            return f"{summary}\n\nWould you like to confirm booking for this journey?"
        return "I'd be happy to help with a booking. First, tell me where you'd like to go!"

    @staticmethod
    def _format_goodbye(**kwargs) -> str:
        return ResponseTemplates.goodbye()

    @staticmethod
    def _format_multi_modal(**kwargs) -> str | None:
        return None


def _get_journey(cap_result: Any) -> PersistentJourneyContext | None:
    if cap_result and hasattr(cap_result, "route_data") and cap_result.route_data:
        data = cap_result.route_data
        if isinstance(data, dict) and "origin" in data:
            try:
                return PersistentJourneyContext(**data)
            except Exception:
                pass
    return None


def _build_insight_section(ctx: ConversationContext | None) -> str | None:
    if not ctx:
        return None
    parts = []
    if ctx.journey_insights:
        insight = ResponseTemplates.journey_insight(ctx.journey_insights)
        if insight:
            parts.append(insight)
    if ctx.route_insights:
        ri = ctx.route_insights
        route_parts = [f"**Route Type:** {ri.route_type}"]
        if ri.service_scope:
            route_parts.append(f"**Service:** {ri.service_scope}")
        if ri.stop_count:
            route_parts.append(f"**Total stops:** {ri.stop_count}")
        parts.append("\n".join(route_parts))
    if not parts:
        return None
    return "\n\n".join(parts)
