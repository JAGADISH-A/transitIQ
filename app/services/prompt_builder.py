"""Prompt builder for the Conversation Intelligence Engine.

ALL prompts are built in this single location.
No other service manipulates prompt strings directly.

Parts implemented:
  Part 7 — Prompt Builder: system, developer, context, user
  Part 8 — TransitIQ Personality
  Part 9 — Reasoning Strategy hints
"""

import logging
from typing import Any

from app.models.conversation import (
    ConversationContext,
    IntentType,
    ReasoningStrategy,
)
from app.models.journey_context import PersistentJourneyContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TransitIQ Personality (Part 8)
# ---------------------------------------------------------------------------

_TRANSTIQ_PERSONALITY = """\
You are TransitIQ, a knowledgeable unified transit intelligence assistant.

PERSONALITY:
- Calm, professional, and patient
- Trustworthy and honest
- Conversational and friendly
- Proactive — suggest useful follow-up questions
- Concise — prefer short, informative answers over long explanations

RULES:
- Never hallucinate. If you don't know something, say so honestly.
- Never invent trains, schedules, or stations.
- When a journey context is provided, treat it as factual and authoritative.
  Do NOT ask the user to confirm information already in the context.
- Prefer backend-provided facts over your own training knowledge.
- Explain naturally instead of dumping raw structured data.
- If the user asks about their current journey, answer using the journey context
  first. Only suggest new searches if the context does not apply.
- If information is unavailable, say: "I don't have that information yet."

CAPABILITIES:
- Railway journey planning across Indian Railways
- Bus transport information (state transport buses)
- Metro/rapid transit information (Chennai, Delhi, Bangalore, Hyderabad, Mumbai)
- Ferry and water transport information (Mumbai, Kolkata, Kochi, Varanasi)
- Multi-modal journey planning combining rail, bus, metro, and ferry
- Station and stop information across all transport modes
"""

# ---------------------------------------------------------------------------
# Intent-specific instructions
# ---------------------------------------------------------------------------

_INTENT_INSTRUCTIONS: dict[IntentType, str] = {
    IntentType.ROUTE_CONTEXT_QA: (
        "The user is asking about their current journey. "
        "Use the journey context below to answer factually. "
        "Do NOT suggest a new route search unless the user explicitly asks."
    ),
    IntentType.ROUTE_EXPLANATION: (
        "Explain the route recommendation naturally. "
        "Mention key stops, duration, and what makes this route a good choice."
    ),
    IntentType.FOLLOW_UP: (
        "The user is continuing their previous conversation. "
        "Refer to the conversation history and current journey context."
    ),
    IntentType.STATION_INFORMATION: (
        "Station lookup results are provided below. "
        "Present the station information clearly."
    ),
    IntentType.TRAIN_INFORMATION: (
        "Answer questions about the specific train using available data."
    ),
    IntentType.KNOWLEDGE_QUERY: (
        "Answer based on your general railway knowledge. "
        "Be accurate but explain in simple terms."
    ),
    IntentType.SCHEDULE_QUERY: (
        "Answer schedule-related questions. If schedule data is not available, "
        "explain what you can determine from the journey context."
    ),
    IntentType.COMPARISON: (
        "The comparison results below are computed by the backend. "
        "DO NOT recompute or second-guess them. "
        "Simply explain the comparison in natural language."
    ),
    IntentType.RECOMMENDATION: (
        "The recommendation below is computed by the backend. "
        "DO NOT recompute or suggest alternatives not listed. "
        "Explain why the recommended option is the best choice."
    ),
    IntentType.BOOKING: (
        "The user wants to book a ticket. "
        "If journey context is available, ask them to confirm the details. "
        "If missing information is detected, ask clarifying questions."
    ),
}

_REASONING_HINTS: dict[ReasoningStrategy, str] = {
    ReasoningStrategy.JOURNEY_CONTEXT_ONLY: (
        "STRATEGY: Journey Context — All information needed is in the context below. "
        "No GTFS lookup is required. Answer directly from the provided data."
    ),
    ReasoningStrategy.CONVERSATION_MEMORY: (
        "STRATEGY: Conversation Memory — Refer to the conversation history. "
        "The user may be referring to a previous topic."
    ),
    ReasoningStrategy.KNOWLEDGE_BASE: (
        "STRATEGY: Knowledge — Answer from your training knowledge. "
        "A structured knowledge base will replace this in a future update."
    ),
    ReasoningStrategy.BACKEND_TOOL: (
        "STRATEGY: Backend Tool — Tool results are provided below. "
        "Synthesize a natural answer from the tool output."
    ),
    ReasoningStrategy.LLM_ONLY: (
        "STRATEGY: LLM Reasoning — No backend data is required. "
        "Answer naturally based on your training."
    ),
    ReasoningStrategy.COMPARISON: (
        "STRATEGY: Comparison — Comparison data is provided by the backend below. "
        "Present the comparison clearly. Highlight the key differences. "
        "DO NOT recompute — the backend already determined the fastest, fewest stops, etc."
    ),
    ReasoningStrategy.RECOMMENDATION: (
        "STRATEGY: Recommendation — The recommended option is computed by the backend. "
        "Explain why this option is recommended. "
        "Mention the criteria used (duration, stops, timing)."
    ),
    ReasoningStrategy.EXPLANATION: (
        "STRATEGY: Explanation — The user is asking 'why' or 'how'. "
        "Provide a structured explanation. Consider: "
        "schedule availability, direct connectivity, time of day, day of week."
    ),
    ReasoningStrategy.MULTI_MODAL: (
        "STRATEGY: Multi-Modal Transport — The user wants to combine multiple transport modes "
        "(rail, bus, metro, ferry). Available providers are listed below. "
        "Suggest realistic multi-modal journeys using the available transport modes. "
        "Consider transfer points where different modes connect."
    ),
    ReasoningStrategy.MODAL_FILTER: (
        "STRATEGY: Transport Mode Preference — The user specified transport mode preferences "
        "(avoid certain modes, prefer only certain modes). "
        "Respect these preferences when making recommendations."
    ),
}


class PromptBuilder:
    """Builds all prompts for the Conversation Intelligence Engine.

    Every prompt is assembled here. No other code builds prompt strings.
    """

    # ------------------------------------------------------------------
    # Build methods
    # ------------------------------------------------------------------

    def build_system_prompt(self, ctx: ConversationContext) -> str:
        """Build the system prompt with TransitIQ personality and context."""
        sections = [
            _TRANSTIQ_PERSONALITY,
            "",
            self._build_feed_section(ctx),
            "",
            self._build_intent_section(ctx),
            "",
            self._build_reasoning_section(ctx),
            "",
            self._build_state_section(ctx),
            "",
            self._build_reference_section(ctx),
            "",
            self._build_summary_section(ctx),
            "",
            self._build_clarification_section(ctx),
            "",
            self._build_multi_modal_section(ctx),
            "",
            self._build_comparison_section(ctx),
            "",
            self._build_railway_intelligence(ctx),
            "",
            self._build_context_section(ctx),
        ]

        if ctx.capability_result:
            cap_data = ctx.capability_result.get("context_data", {})
            if cap_data:
                sections.append("")
                sections.append(self._build_capability_result_section(cap_data))

        return "\n".join(s for s in sections if s)

    def build_system_prompt_legacy(
        self,
        feed_instruction: str,
        journey_section: str,
    ) -> str:
        """Build a backward-compatible system prompt for direct Groq calls.

        Used by foundry_agent when the engine falls through to REASONING_PATH.
        """
        return (
            "You are TransitIQ, a helpful unified transit intelligence assistant. "
            "Use the available tools to answer questions about rail, bus, metro, and ferry transport. "
            "Use find_trip for railway journeys, find_multi_modal_journey for combined transport modes. "
            "Prefer concise, natural-language answers based on the tool results.\n\n"
            f"FEED INFORMATION:\n{feed_instruction}\n\n"
            f"{journey_section}"
            "CRITICAL TOOL-CALLING RULES:\n"
            "- When you need external data, you MUST emit a proper tool_call using the OpenAI function-calling format.\n"
            "- NEVER write tool names or JSON arguments inside your reasoning or text response.\n"
            "- NEVER describe a tool call in prose instead of actually invoking it.\n"
            "- If you need to call a tool, use the tool_calls mechanism. Do NOT output the call as text.\n"
            "- Each tool call must include the function name and a valid JSON arguments object.\n"
            "- After receiving tool results, synthesize a helpful natural-language answer for the user."
        )

    def build_user_message(self, ctx: ConversationContext) -> str:
        """Build the user message for the LLM."""
        return ctx.user_query

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_railway_intelligence(ctx: ConversationContext) -> str:
        """Build railway intelligence sections from backend-computed data."""
        sections = []

        if ctx.train_profile:
            tp = ctx.train_profile
            sections.append("=== TRAIN PROFILE (backend-computed) ===")
            sections.append(f"  Train: {tp.train_name} ({tp.train_number})")
            sections.append(f"  Type: {tp.train_type}")
            sections.append(f"  Category: {tp.service_category}")
            if tp.stop_count:
                sections.append(f"  Stops: {tp.stop_count}")
            if tp.duration_min:
                sections.append(f"  Duration: {tp.duration_min} min")
            if tp.major_stops:
                sections.append(f"  Major stations: {', '.join(tp.major_stops[:5])}")
            if tp.terminal_stations:
                sections.append(f"  Terminals: {', '.join(tp.terminal_stations)}")
            sections.append("")

        if ctx.station_profile:
            sp = ctx.station_profile
            sections.append("=== STATION PROFILE (backend-computed) ===")
            sections.append(f"  Station: {sp.station_name} ({sp.station_code})")
            sections.append(f"  Junction: {'Yes' if sp.is_junction else 'No'}")
            sections.append(f"  Terminal: {'Yes' if sp.is_terminal else 'No'}")
            sections.append(f"  Major station: {'Yes' if sp.is_major_station else 'No'}")
            if sp.estimated_platform_count:
                sections.append(f"  Estimated platforms: {sp.estimated_platform_count}")
            if sp.connecting_routes:
                sections.append(f"  Connecting routes: {len(sp.connecting_routes)}")
            sections.append("")

        if ctx.journey_insights:
            ji = ctx.journey_insights
            flags = []
            if ji.is_overnight: flags.append("Overnight")
            if ji.is_daytime: flags.append("Daytime")
            if ji.is_long_journey: flags.append("Long journey")
            if ji.is_short_trip: flags.append("Short trip")
            if ji.requires_transfer: flags.append("Requires transfer")
            if ji.tight_connection: flags.append("Tight connection")
            if ji.comfortable_connection: flags.append("Comfortable connection")
            if ji.many_stops: flags.append("Many stops")
            if ji.express_trip: flags.append("Express trip")
            if flags:
                sections.append("=== JOURNEY INSIGHTS (backend-computed) ===")
                sections.append("  Characteristics: " + ", ".join(flags))
                sections.append("")

        if ctx.route_insights:
            ri = ctx.route_insights
            sections.append("=== ROUTE INSIGHTS (backend-computed) ===")
            sections.append(f"  Route type: {ri.route_type}")
            sections.append(f"  Service scope: {ri.service_scope}")
            if ri.stop_count:
                sections.append(f"  Total stops: {ri.stop_count}")
            if ri.transfer_count:
                sections.append(f"  Transfers: {ri.transfer_count}")
            sections.append("")

        if ctx.comparison_extended:
            ce = ctx.comparison_extended
            sections.append("=== BACKEND-COMPUTED COMPARISON ===")
            sections.append(f"  Winner: {ce.winner}")
            for row in ce.comparison_table:
                winner_mark = " ← WIN" if row.winner == "a" else (" ← WIN" if row.winner == "b" else "")
                sections.append(f"  {row.attribute}: A={row.value_a} B={row.value_b}{winner_mark}")
            if ce.advantages:
                sections.append(f"  Advantages: {'; '.join(ce.advantages[:3])}")
            if ce.disadvantages:
                sections.append(f"  Disadvantages: {'; '.join(ce.disadvantages[:3])}")
            sections.append("  INSTRUCTION: Present this comparison naturally. The data is authoritative.")
            sections.append("")

        if ctx.explanation:
            ex = ctx.explanation
            sections.append("=== BACKEND-COMPUTED EXPLANATION ===")
            sections.append(f"  Reason: {ex.reason}")
            if ex.details:
                for d in ex.details[:3]:
                    sections.append(f"  - {d}")
            if ex.suggestion:
                sections.append(f"  Suggestion: {ex.suggestion}")
            sections.append("")

        if ctx.railway_knowledge:
            rk = ctx.railway_knowledge
            sections.append("=== RAILWAY KNOWLEDGE (backend-curated) ===")
            sections.append(f"  Topic: {rk.topic}")
            sections.append(f"  Category: {rk.category}")
            sections.append(f"  Answer: {rk.answer}")
            sections.append("  INSTRUCTION: Present the knowledge above in natural language. Do NOT add additional facts.")
            sections.append("")

        return "\n".join(sections)

    @staticmethod
    def _build_feed_section(ctx: ConversationContext) -> str:
        if ctx.current_feed:
            return f"CURRENT FEED: {ctx.current_feed}\nAll queries use this feed unless otherwise specified."
        return "No GTFS feed is currently active."

    @staticmethod
    def _build_intent_section(ctx: ConversationContext) -> str:
        intent = ctx.intent.value
        instruction = _INTENT_INSTRUCTIONS.get(ctx.intent, "")
        parts = [f"USER INTENT: {intent}"]
        if instruction:
            parts.append(f"INSTRUCTION: {instruction}")
        return "\n".join(parts)

    @staticmethod
    def _build_reasoning_section(ctx: ConversationContext) -> str:
        hint = _REASONING_HINTS.get(ctx.reasoning_strategy, "")
        return hint

    @staticmethod
    def _build_multi_modal_section(ctx: ConversationContext) -> str:
        """Build multi-modal transport context section."""
        sections = []

        if ctx.available_providers:
            sections.append("=== AVAILABLE TRANSPORT PROVIDERS ===")
            for p in ctx.available_providers:
                sections.append(
                    f"  {p.get('mode', '?')}: {p.get('name', '?')} "
                    f"({'Available' if p.get('available') else 'Unavailable'}) "
                    f"- {p.get('stop_count', 0)} stops"
                )
            sections.append("")

        if ctx.transport_preference:
            pref = ctx.transport_preference
            parts = []
            if pref.preferred_modes:
                parts.append(f"Preferred modes: {', '.join(m.value for m in pref.preferred_modes)}")
            if pref.avoided_modes:
                parts.append(f"Avoided modes: {', '.join(m.value for m in pref.avoided_modes)}")
            if pref.max_transfers is not None:
                parts.append(f"Max transfers: {pref.max_transfers}")
            if parts:
                sections.append("=== TRANSPORT PREFERENCES ===")
                for p in parts:
                    sections.append(f"  {p}")
                sections.append("  INSTRUCTION: Respect these preferences when suggesting routes.")
                sections.append("")

        if ctx.transport_mode_context:
            sections.append("=== TRANSPORT MODE CONTEXT ===")
            for line in ctx.transport_mode_context:
                sections.append(f"  {line}")
            sections.append("")

        if ctx.multi_modal_journeys:
            sections.append("=== MULTI-MODAL JOURNEY OPTIONS ===")
            for i, j in enumerate(ctx.multi_modal_journeys):
                modes = ", ".join(j.get("modes_used", []))
                providers = ", ".join(j.get("providers_used", []))
                dur = j.get("total_duration_minutes", "?")
                xfers = j.get("total_transfers", 0)
                sections.append(f"  [{i + 1}] Modes: {modes} | Providers: {providers} | Duration: {dur} min | Transfers: {xfers}")
            sections.append("  INSTRUCTION: Present these options clearly, explaining what each segment involves.")
            sections.append("")

        return "\n".join(sections)

    @staticmethod
    def _build_context_section(ctx: ConversationContext) -> str:
        """Build the context section with journey data and conversation history."""
        sections = []

        journey = ctx.current_journey
        if journey:
            sections.append("=== CURRENT JOURNEY ===")
            sections.append(f"  Origin:       {journey.origin}")
            sections.append(f"  Destination:  {journey.destination}")
            sections.append(f"  Train:        {journey.train_name}")
            sections.append(f"  Train No:     {journey.train_number}")
            sections.append(f"  Departure:    {journey.departure_time}")
            sections.append(f"  Arrival:      {journey.arrival_time}")
            sections.append(f"  Duration:     {journey.duration} min")
            sections.append(f"  Transfers:    {journey.transfer_count}")
            sections.append(f"  Summary:      {journey.route_summary}")
            sections.append("")
            sections.append("  Stop sequence:")
            for stop in journey.stop_sequence:
                marker = ""
                if stop.stop_name == journey.origin:
                    marker = "  ← DEPART"
                elif stop.stop_name == journey.destination:
                    marker = "  ← ARRIVE"
                sections.append(f"    {stop.stop_sequence}. {stop.stop_name}{marker}")

            if journey.intermediate_stops:
                sections.append("")
                sections.append("  Intermediate stops:")
                for name in journey.intermediate_stops:
                    sections.append(f"    - {name}")
            sections.append("")

        history = ctx.conversation_history
        if history:
            sections.append("=== RECENT CONVERSATION ===")
            for turn in history:
                label = "User" if turn.role == "user" else "Assistant"
                sections.append(f"  {label}: {turn.content[:200]}")
            sections.append("")

        sections.append(f"=== CURRENT TIME ===\n  {ctx.current_time}")

        sections.append("")
        sections.append(
            "INSTRUCTIONS: Use the context above to answer the user's question. "
            "If the journey context is present, treat it as authoritative. "
            "Explain naturally. Suggest useful follow-up questions when appropriate."
        )

        return "\n".join(sections)

    @staticmethod
    def _build_capability_result_section(data: dict[str, Any]) -> str:
        """Build a section from capability execution results."""
        sections = []

        station_results = data.get("station_results")
        if station_results:
            sections.append("=== STATION LOOKUP RESULTS ===")
            for sr in station_results:
                sections.append(f"  - {sr.get('stop_name', '?')} ({sr.get('stop_id', '?')})")

        tool_results = data.get("tool_results")
        if tool_results:
            sections.append("=== TOOL RESULTS ===")
            sections.append(str(tool_results))

        if sections:
            sections.append("")
        return "\n".join(sections)

    @staticmethod
    def build_developer_prompt() -> str:
        """Build an optional developer/system-level prompt.

        Currently empty placeholder for future use.
        """
        return ""

    # ------------------------------------------------------------------
    # Phase 3 Section Builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_state_section(ctx: ConversationContext) -> str:
        """Build the conversation state section."""
        state = ctx.conversation_state
        if not state or state == "NO_CONTEXT":
            return ""
        return f"CONVERSATION STATE: {state}"

    @staticmethod
    def _build_reference_section(ctx: ConversationContext) -> str:
        """Build the resolved reference section."""
        ref = ctx.resolved_reference
        if not ref or ref.type.value == "NONE":
            return ""
        parts = [f"RESOLVED REFERENCE: type={ref.type.value}"]

        _MAPPING = {
            "current_journey": "The user is referring to the current journey displayed below.",
            "current_topic": "The user is referring to the previous topic in conversation history.",
        }

        explanation = _MAPPING.get(ref.value)
        if explanation:
            parts.append(f"  Explanation: {explanation}")
        elif ref.value:
            parts.append(f"  Value: {ref.value}")
        if ref.source:
            parts.append(f"  Source: {ref.source}")
        parts.append("  Use this resolved reference to answer — do NOT ask which one.")
        return "\n".join(parts)

    @staticmethod
    def _build_summary_section(ctx: ConversationContext) -> str:
        """Build the conversation summary section."""
        summary = ctx.conversation_summary
        if not summary or not summary.summary_text:
            return ""
        parts = [
            "=== CONVERSATION SUMMARY (older turns) ===",
            f"  Summary: {summary.summary_text}",
        ]
        if summary.important_decisions:
            parts.append(f"  Key decisions: {'; '.join(summary.important_decisions)}")
        if summary.unresolved_questions:
            parts.append(f"  Unresolved: {'; '.join(summary.unresolved_questions)}")
        if summary.selected_train:
            parts.append(f"  Selected train: {summary.selected_train}")
        if summary.selected_station:
            parts.append(f"  Selected station: {summary.selected_station}")
        parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _build_clarification_section(ctx: ConversationContext) -> str:
        """Build the clarification section."""
        clarification = ctx.clarification
        if not clarification or not clarification.needed:
            return ""
        parts = [
            "CLARIFICATION NEEDED:",
            f"  Missing: {clarification.missing_type.value}",
            f"  Ask: {clarification.question}",
        ]
        if clarification.context_hint:
            parts.append(f"  Context: {clarification.context_hint}")
        parts.append(
            "  INSTRUCTION: Ask the clarification question above. "
            "Do NOT guess the answer."
        )
        return "\n".join(parts)

    @staticmethod
    def _build_comparison_section(ctx: ConversationContext) -> str:
        """Build the comparison and recommendation section."""
        sections = []

        comparison = ctx.comparison_result
        if comparison and comparison.items:
            sections.append("=== BACKEND-COMPUTED COMPARISON ===")
            sections.append("  Comparison criteria used: " + ", ".join(comparison.criteria_used))
            for i, item in enumerate(comparison.items):
                sections.append(f"  [{i + 1}] {item.label}")
                if item.duration_min:
                    sections.append(f"      Duration: {item.duration_min} min")
                if item.stop_count:
                    sections.append(f"      Stops: {item.stop_count}")
                if item.departure_time:
                    sections.append(f"      Departure: {item.departure_time}")
                if item.arrival_time:
                    sections.append(f"      Arrival: {item.arrival_time}")
            if comparison.fastest_idx >= 0:
                sections.append(f"  Fastest: option #{comparison.fastest_idx + 1}")
            if comparison.fewest_stops_idx >= 0:
                sections.append(f"  Fewest stops: option #{comparison.fewest_stops_idx + 1}")
            if comparison.earliest_arrival_idx >= 0:
                sections.append(f"  Earliest arrival: option #{comparison.earliest_arrival_idx + 1}")
            if comparison.latest_departure_idx >= 0:
                sections.append(f"  Latest departure: option #{comparison.latest_departure_idx + 1}")
            sections.append("  INSTRUCTION: Present this comparison naturally. The data is authoritative.")
            sections.append("")

        recommendation = ctx.recommendation_result
        if recommendation and recommendation.recommended_idx >= 0:
            sections.append("=== BACKEND-COMPUTED RECOMMENDATION ===")
            sections.append(f"  Recommended: option #{recommendation.recommended_idx + 1}")
            sections.append(f"  Criteria: {recommendation.criteria}")
            if recommendation.justification:
                sections.append(f"  Justification: {recommendation.justification}")
            sections.append("  INSTRUCTION: Explain this recommendation. Do NOT suggest alternatives.")
            sections.append("")

        return "\n".join(sections)


prompt_builder = PromptBuilder()
