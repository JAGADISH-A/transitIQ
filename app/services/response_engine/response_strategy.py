from enum import Enum

from app.models.conversation import IntentType


class ResponseStrategy(str, Enum):
    """Three-tier response strategy.

    DIRECT  — Backend has everything. No LLM call. ResponseFormatter handles it.
    HYBRID  — Backend computes reasoning. Try LLM for polish; fallback to DIRECT.
    LLM_ONLY — Requires genuine reasoning or knowledge generation. Use existing path.
    """

    DIRECT = "DIRECT"
    HYBRID = "HYBRID"
    LLM_ONLY = "LLM_ONLY"


class ResponseDecision:
    """Result of strategy selection."""

    def __init__(
        self,
        strategy: ResponseStrategy,
        response_type: str,
        template_name: str = "",
        needs_tools: bool = False,
    ):
        self.strategy = strategy
        self.response_type = response_type
        self.template_name = template_name
        self.needs_tools = needs_tools


# --- DIRECT strategy candidates (no LLM needed) ---

_DIRECT_INTENTS = {
    IntentType.GREETING,
    IntentType.HELP,
    IntentType.SMALL_TALK,
}

_DIRECT_CAPABILITY_ANSWERS = {
    IntentType.GREETING,
    IntentType.HELP,
    IntentType.SMALL_TALK,
}

# --- HYBRID strategy candidates ---

_HYBRID_INTENTS = {
    IntentType.STATION_INFORMATION,
    IntentType.TRAIN_INFORMATION,
    IntentType.SCHEDULE_QUERY,
    IntentType.KNOWLEDGE_QUERY,
}

# --- LLM_ONLY intents ---

_LLM_ONLY_INTENTS = {
    IntentType.UNKNOWN,
    IntentType.MULTI_MODAL_QUERY,
    IntentType.MODAL_FILTER,
}


def _classify_response_type(intent: IntentType) -> str:
    """Map intent to a response type name."""
    mapping = {
        IntentType.GREETING: "GREETING",
        IntentType.HELP: "HELP",
        IntentType.SMALL_TALK: "SMALL_TALK",
        IntentType.STATION_INFORMATION: "STATION_PROFILE",
        IntentType.TRAIN_INFORMATION: "TRAIN_PROFILE",
        IntentType.SCHEDULE_QUERY: "SCHEDULE_INFO",
        IntentType.NEW_JOURNEY: "JOURNEY_SUMMARY",
        IntentType.ROUTE_CONTEXT_QA: "ROUTE_OVERVIEW",
        IntentType.ROUTE_EXPLANATION: "ROUTE_EXPLANATION",
        IntentType.COMPARISON: "COMPARISON",
        IntentType.RECOMMENDATION: "RECOMMENDATION",
        # CLARIFICATION is handled by context, not intent
        IntentType.KNOWLEDGE_QUERY: "KNOWLEDGE",
        IntentType.FOLLOW_UP: "ROUTE_OVERVIEW",
        IntentType.BOOKING: "BOOKING",
        IntentType.MULTI_MODAL_QUERY: "MULTI_MODAL",
        IntentType.MODAL_FILTER: "MULTI_MODAL",
        IntentType.UNKNOWN: "UNKNOWN",
    }
    return mapping.get(intent, "UNKNOWN")


def decide_strategy(
    intent: IntentType,
    has_direct_answer: bool = False,
    has_journey: bool = False,
    has_railway_intel: bool = False,
    needs_tools: bool = False,
    groq_available: bool = True,
) -> ResponseDecision:
    """Determine the response strategy based on intent and context.

    Priority:
      1. If capability already provided a direct answer → DIRECT
      2. If intent is in DIRECT list → DIRECT
      3. If intent requires tools → needs_tools path
      4. If intent is in HYBRID list → HYBRID
      5. Otherwise → LLM_ONLY
    """
    response_type = _classify_response_type(intent)

    # Direct answers from capability (greeting, help, etc.)
    if has_direct_answer:
        return ResponseDecision(
            strategy=ResponseStrategy.DIRECT,
            response_type=response_type,
            template_name=response_type.lower(),
        )

    # Intent-level DIRECT candidates
    if intent in _DIRECT_INTENTS:
        return ResponseDecision(
            strategy=ResponseStrategy.DIRECT,
            response_type=response_type,
            template_name=response_type.lower(),
        )

    # Tools needed — route through foundry_agent / LLM
    if needs_tools:
        return ResponseDecision(
            strategy=ResponseStrategy.LLM_ONLY,
            response_type=response_type,
            needs_tools=True,
        )

    # HYBRID candidates — backend has data, LLM can polish
    if intent in _HYBRID_INTENTS:
        return ResponseDecision(
            strategy=ResponseStrategy.HYBRID,
            response_type=response_type,
            template_name=response_type.lower(),
        )

    # Comparison / Recommendation — backend computes, try HYBRID
    if intent in (IntentType.COMPARISON, IntentType.RECOMMENDATION):
        return ResponseDecision(
            strategy=ResponseStrategy.HYBRID if has_railway_intel else ResponseStrategy.LLM_ONLY,
            response_type=response_type,
            template_name=response_type.lower(),
        )

    # Route context with journey — backend data available
    if intent in (IntentType.ROUTE_CONTEXT_QA, IntentType.ROUTE_EXPLANATION, IntentType.FOLLOW_UP):
        if has_journey:
            return ResponseDecision(
                strategy=ResponseStrategy.HYBRID,
                response_type=response_type,
                template_name=response_type.lower(),
            )
        return ResponseDecision(
            strategy=ResponseStrategy.LLM_ONLY,
            response_type=response_type,
            template_name=response_type.lower(),
        )

    # LLM_ONLY for everything else
    return ResponseDecision(
        strategy=ResponseStrategy.LLM_ONLY,
        response_type=response_type,
        template_name=response_type.lower(),
    )
