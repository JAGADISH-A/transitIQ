"""Conversation context assembly service.

This service does NOT call Groq. It only assembles context data
from backend sources so the AI can answer questions factually.

Phase 1: build_journey_context() and build_ai_context_string() — kept for compatibility.
Phase 2: ConversationContextBuilder — structured context assembly from multiple sources.
"""

import logging
from datetime import datetime
from typing import Any

from app.models.conversation import (
    CapabilityType,
    Clarification,
    ConversationContext,
    ConversationSummary,
    ConversationTurn,
    IntentType,
    ReasoningStrategy,
    ResolvedReference,
)
from app.models.transit import TransportPreference
from app.models.journey_context import (
    JourneyStop,
    PersistentJourneyContext,
)
from app.models.schemas import JourneyResponse, JourneyRoute, TransferJourney
from app.services.session_manager import session_manager
from app.services.transit_service import TransitService

logger = logging.getLogger(__name__)


# ==========================================================================
# Phase 1 helpers (kept for backward compatibility)
# ==========================================================================

def _pick_primary_route(
    routes: list[JourneyRoute],
    transfer_routes: list[TransferJourney],
) -> tuple[JourneyRoute | TransferJourney | None, int]:
    if routes:
        return routes[0], 0
    if transfer_routes:
        tr = transfer_routes[0]
        count = 1
        if tr.third_leg is not None:
            count = 2
        return tr, count
    return None, 0


def _get_stop_sequence(
    transit: TransitService,
    feed: str,
    trip_id: str,
    source_stop: str,
    dest_stop: str,
) -> tuple[list[JourneyStop], list[str]]:
    try:
        trip_stops = transit.get_trip_stops(feed, trip_id)
    except Exception:
        return [], []

    full_sequence = [
        JourneyStop(
            stop_id=s.stop_id,
            stop_name=s.stop_name,
            stop_sequence=s.stop_sequence,
        )
        for s in trip_stops
    ]

    intermediates: list[str] = []
    found_source = False
    found_dest = False
    for s in trip_stops:
        if s.stop_name == source_stop:
            found_source = True
            continue
        if s.stop_name == dest_stop:
            found_dest = True
            continue
        if found_source and not found_dest:
            intermediates.append(s.stop_name)

    return full_sequence, intermediates


def _get_service_id(transit: TransitService, feed: str, trip_id: str) -> str:
    try:
        loader = transit.get_feed(feed)
        if loader is None or loader.trips is None:
            return ""
        trip_row = loader.trips[loader.trips["trip_id"] == trip_id]
        if trip_row.empty:
            return ""
        val = trip_row.iloc[0].get("service_id", "")
        return str(val) if val else ""
    except Exception:
        return ""


def _get_train_number(transit: TransitService, feed: str, route_id: str) -> str:
    try:
        loader = transit.get_feed(feed)
        if loader is None or loader.routes is None:
            return ""
        route_row = loader.routes[loader.routes["route_id"] == route_id]
        if route_row.empty:
            return ""
        val = route_row.iloc[0].get("route_short_name", "")
        return str(val) if val else ""
    except Exception:
        return ""


def _duration_minutes_from_primary(
    primary: JourneyRoute | TransferJourney,
) -> int:
    if hasattr(primary, "duration_minutes") and primary.duration_minutes:
        return primary.duration_minutes
    if hasattr(primary, "total_duration") and primary.total_duration:
        return primary.total_duration
    return 0


def build_journey_context(
    source_stop_id: str,
    destination_stop_id: str,
    journey_response: JourneyResponse,
    transit: TransitService,
) -> PersistentJourneyContext | None:
    """Construct a PersistentJourneyContext from a successful journey search.

    Phase 1 API — kept for backward compatibility with app/api/journey.py.
    """
    if not journey_response.success:
        return None

    primary, transfer_count = _pick_primary_route(
        journey_response.routes, journey_response.transfer_routes
    )
    if primary is None:
        return None

    feed = primary.feed
    trip_id = primary.trip_id
    route_id = primary.route_id

    if hasattr(primary, "source_stop"):
        origin_name = primary.source_stop
        dest_name = primary.destination_stop
    else:
        origin_name = getattr(primary, "transfer_stop", "Unknown")
        dest_name = "Unknown"

    train_name = primary.route_name
    train_number = _get_train_number(transit, feed, route_id)
    service_id = _get_service_id(transit, feed, trip_id)

    departure_time = primary.departure_time or ""
    arrival_time = primary.arrival_time or ""

    duration = _duration_minutes_from_primary(primary)

    stop_sequence, intermediate_stops = _get_stop_sequence(
        transit, feed, trip_id, origin_name, dest_name
    )

    route_summary = f"{origin_name} → {dest_name} via {train_name} ({departure_time} - {arrival_time})"

    return PersistentJourneyContext(
        origin=origin_name,
        destination=dest_name,
        feed_name=feed,
        train_name=train_name,
        train_number=train_number,
        trip_id=trip_id,
        service_id=service_id,
        departure_time=departure_time,
        arrival_time=arrival_time,
        duration=duration,
        transfer_count=transfer_count,
        selected_route=None,
        stop_sequence=stop_sequence,
        intermediate_stops=intermediate_stops,
        route_summary=route_summary,
        created_at=datetime.utcnow().isoformat() + "Z",
    )


def build_ai_context_string() -> str:
    """Assemble a plain-text context block for the AI system prompt.

    Phase 1 API — kept for backward compatibility with app/services/foundry_agent.py.
    Returns an empty string when there is no active journey.
    """
    ctx = session_manager.get_current_journey()
    if ctx is None:
        return ""

    lines = [
        "=== Current Journey Context (factual data from the transit backend) ===",
        "",
        f"  Origin:       {ctx.origin}",
        f"  Destination:  {ctx.destination}",
        f"  Feed:         {ctx.feed_name}",
        f"  Train:        {ctx.train_name}",
        f"  Train No:     {ctx.train_number}",
        f"  Departure:    {ctx.departure_time}",
        f"  Arrival:      {ctx.arrival_time}",
        f"  Duration:     {ctx.duration} min",
        f"  Transfers:    {ctx.transfer_count}",
        f"  Summary:      {ctx.route_summary}",
        "",
        "  Stop sequence:",
    ]

    for stop in ctx.stop_sequence:
        marker = ""
        if stop.stop_name == ctx.origin:
            marker = "  ← DEPART"
        elif stop.stop_name == ctx.destination:
            marker = "  ← ARRIVE"
        lines.append(f"    {stop.stop_sequence}. {stop.stop_name}{marker}")

    if ctx.intermediate_stops:
        lines.append("")
        lines.append("  Intermediate stops:")
        for name in ctx.intermediate_stops:
            lines.append(f"    - {name}")

    lines.append("")
    lines.append(
        "IMPORTANT: Use the journey context above to answer the user's question "
        "factually. Do NOT ask the user for information already present in this "
        "context. If the question is about this journey, answer based on the data provided."
    )
    lines.append("============================================================")

    return "\n".join(lines)


# ==========================================================================
# Phase 2 — ConversationContextBuilder
# ==========================================================================

class ConversationContextBuilder:
    """Assembles a structured ConversationContext from multiple backend sources.

    Sources:
      - PersistentJourneyContext (from SessionManager)
      - Conversation History (from SessionManager)
      - Session State (last question, intent, capability)
      - Current Time
      - Detected Intent
      - Selected Capability
      - Knowledge Context (placeholder)
      - Current Feed

    This class does NOT communicate with Groq.
    """

    def build(
        self,
        user_query: str,
        intent: IntentType,
        capability: CapabilityType | None = None,
        capability_result: dict | None = None,
        conversation_state: str | None = None,
        resolved_reference: ResolvedReference | None = None,
        conversation_summary: ConversationSummary | None = None,
        clarification: Clarification | None = None,
        comparison_result: Any = None,
        recommendation_result: Any = None,
        railway_intel_data: dict | None = None,
        transport_preference: TransportPreference | None = None,
    ) -> ConversationContext:
        """Assemble context from all available sources."""
        journey = session_manager.get_current_journey()
        history = session_manager.get_history(limit=6)

        context = ConversationContext(
            user_query=user_query,
            intent=intent,
            capability=capability,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            current_journey=journey,
            current_feed=journey.feed_name if journey else None,
            conversation_history=history,
            last_question=session_manager.get_last_question(),
            capability_result=capability_result,
            system_context=self._build_system_context(journey, intent),
        )

        context.reasoning_strategy = self._determine_reasoning_strategy(
            intent, journey is not None, capability_result
        )

        context.needs_tools = context.reasoning_strategy in (
            ReasoningStrategy.BACKEND_TOOL,
        )

        # --- Phase 3 fields ---
        context.conversation_state = conversation_state or "NO_CONTEXT"
        context.resolved_reference = resolved_reference or ResolvedReference()
        context.conversation_summary = conversation_summary or ConversationSummary()
        context.clarification = clarification or Clarification()
        context.comparison_result = comparison_result
        context.recommendation_result = recommendation_result
        if clarification and clarification.needed:
            context.missing_info_type = clarification.missing_type

        # --- Phase 4 — Railway Intelligence fields ---
        if railway_intel_data:
            self._apply_railway_intel(context, railway_intel_data)

        # --- Phase 5 — Multi-modal transport fields ---
        if transport_preference:
            context.transport_preference = transport_preference
        self._populate_transport_mode_context(context)

        return context

    @staticmethod
    def _apply_railway_intel(
        context: ConversationContext,
        data: dict,
    ) -> None:
        """Apply railway intelligence data to the context."""
        from app.models.conversation import (
            TrainProfile,
            StationProfile,
            JourneyInsights,
            RouteInsights,
            ComparisonResultExtended,
            Explanation,
            RailwayKnowledge,
        )

        tp = data.get("train_profile")
        if tp and isinstance(tp, TrainProfile):
            context.train_profile = tp

        sp = data.get("station_profile")
        if sp and isinstance(sp, StationProfile):
            context.station_profile = sp

        ji = data.get("journey_insights")
        if ji and isinstance(ji, JourneyInsights):
            context.journey_insights = ji

        ri = data.get("route_insights")
        if ri and isinstance(ri, RouteInsights):
            context.route_insights = ri

        ce = data.get("comparison_extended")
        if ce and isinstance(ce, ComparisonResultExtended):
            context.comparison_extended = ce

        ex = data.get("explanation")
        if ex and isinstance(ex, Explanation):
            context.explanation = ex

        rk = data.get("railway_knowledge")
        if rk and isinstance(rk, RailwayKnowledge):
            context.railway_knowledge = rk

    def _build_system_context(
        self,
        journey: PersistentJourneyContext | None,
        intent: IntentType,
    ) -> str:
        """Build a short system-level context snippet."""
        parts = []
        if journey:
            parts.append(f"Active journey: {journey.route_summary}")
        parts.append(f"Intent: {intent.value}")
        return " | ".join(parts)

    @staticmethod
    def _populate_transport_mode_context(context: ConversationContext) -> None:
        """Populate multi-modal transport context from capability results."""
        cap_data = context.capability_result.get("context_data", {}) if context.capability_result else {}
        providers = cap_data.get("available_providers")
        if providers:
            context.available_providers = providers

        preference_data = cap_data.get("transport_preference")
        if preference_data:
            try:
                context.transport_preference = TransportPreference(**preference_data)
            except Exception:
                pass

        mode_context_lines = []
        if context.current_journey:
            mode_context_lines.append(f"Current journey uses: RAIL (Indian Railways)")
        if context.available_providers:
            active = [p for p in context.available_providers if p.get("available")]
            modes = ", ".join(p.get("mode", "?") for p in active)
            mode_context_lines.append(f"Available transport modes: {modes}")
        context.transport_mode_context = mode_context_lines

    def _determine_reasoning_strategy(
        self,
        intent: IntentType,
        has_journey: bool,
        capability_result: dict | None = None,
    ) -> ReasoningStrategy:
        """Determine what kind of processing the question requires.

        Part 9 — Reasoning Strategy.
        """
        strategy_map: dict[IntentType, ReasoningStrategy] = {
            IntentType.GREETING: ReasoningStrategy.LLM_ONLY,
            IntentType.HELP: ReasoningStrategy.LLM_ONLY,
            IntentType.SMALL_TALK: ReasoningStrategy.LLM_ONLY,
            IntentType.KNOWLEDGE_QUERY: ReasoningStrategy.KNOWLEDGE_BASE,
            IntentType.STATION_INFORMATION: ReasoningStrategy.BACKEND_TOOL,
            IntentType.TRAIN_INFORMATION: ReasoningStrategy.BACKEND_TOOL,
            IntentType.SCHEDULE_QUERY: ReasoningStrategy.BACKEND_TOOL,
            IntentType.NEW_JOURNEY: ReasoningStrategy.BACKEND_TOOL,
        }

        if intent in (IntentType.ROUTE_CONTEXT_QA, IntentType.ROUTE_EXPLANATION):
            if has_journey:
                return ReasoningStrategy.JOURNEY_CONTEXT_ONLY
            return ReasoningStrategy.CONVERSATION_MEMORY

        if intent == IntentType.FOLLOW_UP:
            if has_journey:
                return ReasoningStrategy.JOURNEY_CONTEXT_ONLY
            return ReasoningStrategy.CONVERSATION_MEMORY

        # Phase 3 strategies
        if intent == IntentType.COMPARISON:
            return ReasoningStrategy.COMPARISON

        if intent == IntentType.RECOMMENDATION:
            return ReasoningStrategy.RECOMMENDATION

        if intent == IntentType.BOOKING:
            return ReasoningStrategy.JOURNEY_CONTEXT_ONLY if has_journey else ReasoningStrategy.LLM_ONLY

        return strategy_map.get(intent, ReasoningStrategy.LLM_ONLY)

    def get_available_feed(self) -> str | None:
        """Return the name of the currently active feed, if any."""
        if not transit_service.is_loaded:
            return None
        feeds = transit_service.available_feeds()
        return feeds[0] if feeds else None


context_builder = ConversationContextBuilder()
