"""Backend capability routing for the Conversation Intelligence Engine.

Each capability encapsulates the logic needed for a class of user intent.
Capabilities decide what backend services are required and return structured
results that Groq can use for natural-language generation.

New capabilities can be added without modifying existing ones:
  1. Create a new class inheriting from BaseCapability.
  2. Register it in CapabilityRouter.
  3. Done.
"""

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from app.models.conversation import (
    CapabilityType,
    ConversationContext,
    IntentType,
    ReasoningStrategy,
)
from app.services.agent_tools import agent_tools
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capability result
# ---------------------------------------------------------------------------

class CapabilityResult:
    """Structured result from a capability execution."""

    def __init__(
        self,
        needs_llm: bool = True,
        answer: str | None = None,
        context_data: dict | None = None,
        tools_used: list[str] | None = None,
        route_data: dict | None = None,
    ) -> None:
        self.needs_llm = needs_llm
        self.answer = answer
        self.context_data = context_data or {}
        self.tools_used = tools_used or []
        self.route_data = route_data


# ---------------------------------------------------------------------------
# Base capability
# ---------------------------------------------------------------------------

class BaseCapability(ABC):
    """Abstract base for all capabilities."""

    @property
    @abstractmethod
    def name(self) -> CapabilityType:
        ...

    @abstractmethod
    def can_handle(self, intent: IntentType) -> bool:
        ...

    @abstractmethod
    def execute(self, ctx: ConversationContext) -> CapabilityResult:
        ...


# ---------------------------------------------------------------------------
# ConversationCapability — GREETING, HELP, SMALL_TALK
# ---------------------------------------------------------------------------

class ConversationCapability(BaseCapability):
    """Handles greetings, help requests, and small talk.

    Does not need GTFS data or Groq.
    """

    _HANDLED_INTENTS = {
        IntentType.GREETING,
        IntentType.HELP,
        IntentType.SMALL_TALK,
    }

    _GREETING_RESPONSES = [
        "Hello! I'm TransitIQ, your railway travel assistant. How can I help you today?",
        "Hi there! Ready to help with your journey planning. Where would you like to go?",
        "Namaste! TransitIQ here. Let me know your destination and I'll find the best route for you.",
    ]

    _HELP_RESPONSE = (
        "I can help you with:\n\n"
        "Journey Planning — Tell me where you want to go (e.g., \"From Valliyur to Nanguneri\")\n"
        "Station Information — Ask about stations (e.g., \"What stations are near Chennai?\")\n"
        "Railway Knowledge — Ask about terms like RAC, Tatkal, waitlist, etc.\n"
        "Route Details — Once you have a route, ask about stops, timing, transfers\n\n"
        "Multi-Modal Transport — Combine rail, bus, metro, and ferry (e.g., \"Train to Madurai, then bus\")\n\n"
        "What would you like to know?"
    )

    @property
    def name(self) -> CapabilityType:
        return CapabilityType.CONVERSATION

    def can_handle(self, intent: IntentType) -> bool:
        return intent in self._HANDLED_INTENTS

    def execute(self, ctx: ConversationContext) -> CapabilityResult:
        if ctx.intent == IntentType.GREETING:
            idx = hash(ctx.user_query) % len(self._GREETING_RESPONSES)
            return CapabilityResult(
                needs_llm=False,
                answer=self._GREETING_RESPONSES[idx],
            )

        if ctx.intent == IntentType.HELP:
            return CapabilityResult(
                needs_llm=False,
                answer=self._HELP_RESPONSE,
            )

        if ctx.intent == IntentType.SMALL_TALK:
            return CapabilityResult(
                needs_llm=False,
                answer="I'm doing great, thanks for asking! I'm here to help you with your railway travel. Is there a journey I can help you plan?",
            )

        return CapabilityResult(needs_llm=True)


# ---------------------------------------------------------------------------
# JourneyContextCapability — ROUTE_CONTEXT_QA, ROUTE_EXPLANATION, FOLLOW_UP
# ---------------------------------------------------------------------------

class JourneyContextCapability(BaseCapability):
    """Answers questions about the current journey using stored context.

    No backend tools are needed — all data is already in the session.
    Phase 3: Also handles COMPARISON, RECOMMENDATION, and BOOKING.
    """

    _HANDLED_INTENTS = {
        IntentType.ROUTE_CONTEXT_QA,
        IntentType.ROUTE_EXPLANATION,
        IntentType.FOLLOW_UP,
        IntentType.COMPARISON,
        IntentType.RECOMMENDATION,
        IntentType.BOOKING,
    }

    @property
    def name(self) -> CapabilityType:
        return CapabilityType.JOURNEY_CONTEXT

    def can_handle(self, intent: IntentType) -> bool:
        return intent in self._HANDLED_INTENTS

    def execute(self, ctx: ConversationContext) -> CapabilityResult:
        if ctx.current_journey is None:
            return CapabilityResult(
                needs_llm=False,
                answer="I don't see an active journey in your session. Would you like to plan a new trip? Just tell me your destination!",
            )

        return CapabilityResult(
            needs_llm=True,
            context_data={
                "reasoning_strategy": ReasoningStrategy.JOURNEY_CONTEXT_ONLY.value,
                "has_journey": True,
            },
        )


# ---------------------------------------------------------------------------
# StationCapability — STATION_INFORMATION
# ---------------------------------------------------------------------------

class StationCapability(BaseCapability):
    """Looks up station information using the transit service."""

    @property
    def name(self) -> CapabilityType:
        return CapabilityType.STATION

    def can_handle(self, intent: IntentType) -> bool:
        return intent == IntentType.STATION_INFORMATION

    def execute(self, ctx: ConversationContext) -> CapabilityResult:
        query = ctx.user_query

        # Extract potential station name from query
        station_name = self._extract_station_name(query)
        tools_used: list[str] = []

        if station_name and transit_service.is_loaded:
            try:
                results = agent_tools.search_stops(station_name)
                tools_used.append("search_stops")
                if results:
                    stop = results[0]
                    return CapabilityResult(
                        needs_llm=True,
                        context_data={
                            "station_results": [
                                {
                                    "stop_id": r.stop_id,
                                    "stop_name": r.stop_name,
                                    "feed": getattr(r, "feed", "unknown"),
                                }
                                for r in results[:5]
                            ],
                            "top_match": {
                                "stop_id": stop.stop_id,
                                "stop_name": stop.stop_name,
                            },
                            "reasoning_strategy": ReasoningStrategy.BACKEND_TOOL.value,
                        },
                        tools_used=tools_used,
                    )
            except Exception as exc:
                logger.warning("Station lookup failed: %s", exc)

        return CapabilityResult(
            needs_llm=True,
            context_data={
                "reasoning_strategy": ReasoningStrategy.BACKEND_TOOL.value,
                "station_results": [],
            },
        )

    @staticmethod
    def _extract_station_name(text: str) -> str | None:
        """Best-effort extraction of a station name from the query."""
        import re

        patterns = [
            re.compile(r"(?:search|find|look\s+up)\s+(?:for\s+)?(?:station|stop)\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"(?:station|stop)\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"where\s+is\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"what\s+stations?\s+(?:are|is)\s+(?:in|near|at|on)\s+(.+?)(?:\?|$)", re.IGNORECASE),
            re.compile(r"(?:info|information|details)\s+(?:about|on|for)\s+(.+?)(?:\?|$)", re.IGNORECASE),
        ]

        for p in patterns:
            match = p.search(text)
            if match:
                return match.group(1).strip()
        return None


# ---------------------------------------------------------------------------
# KnowledgeCapability — KNOWLEDGE_QUERY (placeholder for Phase 3)
# ---------------------------------------------------------------------------

class KnowledgeCapability(BaseCapability):
    """Answers railway knowledge questions (RAC, quotas, etc.).

    Phase 2: placeholder that delegates to Groq for natural explanation.
    Phase 3: will query a structured knowledge base instead.
    """

    @property
    def name(self) -> CapabilityType:
        return CapabilityType.KNOWLEDGE

    def can_handle(self, intent: IntentType) -> bool:
        return intent == IntentType.KNOWLEDGE_QUERY

    def execute(self, ctx: ConversationContext) -> CapabilityResult:
        return CapabilityResult(
            needs_llm=True,
            context_data={
                "reasoning_strategy": ReasoningStrategy.KNOWLEDGE_BASE.value,
                "knowledge_context": "Answer based on your general knowledge. "
                    "This will be replaced by a structured knowledge base in a future update.",
            },
        )


# ---------------------------------------------------------------------------
# TransportCapability — MULTI_MODAL_QUERY, MODAL_FILTER (Phase 5)
# ---------------------------------------------------------------------------

class TransportCapability(BaseCapability):
    """Handles multi-modal transport and mode-filter queries.

    Provides context about available transport modes, providers,
    and multi-modal journey planning to the LLM.
    """

    _HANDLED_INTENTS = {
        IntentType.MULTI_MODAL_QUERY,
        IntentType.MODAL_FILTER,
    }

    @property
    def name(self) -> CapabilityType:
        return CapabilityType.MULTI_MODAL

    def can_handle(self, intent: IntentType) -> bool:
        return intent in self._HANDLED_INTENTS

    def execute(self, ctx: ConversationContext) -> CapabilityResult:
        from app.providers.registry import provider_registry
        from app.services.conversation_engine import engine as _engine

        providers = provider_registry.list_providers()
        provider_summary = [
            {
                "id": p.provider_id,
                "name": p.provider_name,
                "mode": p.mode.value,
                "available": p.available,
                "stop_count": p.stop_count,
            }
            for p in providers
        ]

        # Detect mode preferences from query
        preference = self._detect_preferences(ctx.user_query)

        strategy = ReasoningStrategy.MULTI_MODAL
        if ctx.intent == IntentType.MODAL_FILTER:
            strategy = ReasoningStrategy.MODAL_FILTER

        context_data = {
            "reasoning_strategy": strategy.value,
            "available_providers": provider_summary,
            "transport_preference": preference.model_dump() if preference else None,
        }

        return CapabilityResult(
            needs_llm=True,
            context_data=context_data,
        )

    @staticmethod
    def _detect_preferences(query: str) -> "TransportPreference | None":
        from app.models.transit import TransportMode, TransportPreference
        q = query.lower()

        avoided: list[TransportMode] = []
        preferred: list[TransportMode] = []

        if re.search(r"\bavoid\s+(bus|buses)\b", q):
            avoided.append(TransportMode.BUS)
        if re.search(r"\bavoid\s+(metro)\b", q):
            avoided.append(TransportMode.METRO)
        if re.search(r"\bavoid\s+(ferry)\b", q):
            avoided.append(TransportMode.FERRY)
        if re.search(r"\b(no|avoid|don'?t)\s+(transfers|changing)\b", q):
            pass  # handled via max_transfers

        if re.search(r"\b(use|take|prefer)\s+only\s+(trains?|rail)\b", q):
            preferred = [TransportMode.RAIL]
        if re.search(r"\b(use|take|prefer)\s+only\s+(bus)\b", q):
            preferred = [TransportMode.BUS]
        if re.search(r"\b(use|take|prefer)\s+only\s+(metro)\b", q):
            preferred = [TransportMode.METRO]

        if not avoided and not preferred:
            return None

        return TransportPreference(
            preferred_modes=preferred,
            avoided_modes=avoided,
        )


# ---------------------------------------------------------------------------
# FallbackCapability — UNKNOWN (delegates to Groq with tools)
# ---------------------------------------------------------------------------

class FallbackCapability(BaseCapability):
    """Handles unknown intents by delegating to Groq with tool definitions.

    Preserves the current foundry_agent behaviour for queries the
    engine cannot classify with confidence.
    """

    @property
    def name(self) -> CapabilityType:
        return CapabilityType.FALLBACK

    def can_handle(self, intent: IntentType) -> bool:
        return True  # Catch-all

    def execute(self, ctx: ConversationContext) -> CapabilityResult:
        return CapabilityResult(
            needs_llm=True,
            context_data={
                "reasoning_strategy": ReasoningStrategy.LLM_ONLY.value,
                "needs_tools": True,
            },
        )


# ---------------------------------------------------------------------------
# Capability Router
# ---------------------------------------------------------------------------

class CapabilityRouter:
    """Selects the appropriate capability for a given intent."""

    def __init__(self) -> None:
        self._capabilities: list[BaseCapability] = [
            ConversationCapability(),
            JourneyContextCapability(),
            StationCapability(),
            TransportCapability(),
            KnowledgeCapability(),
            FallbackCapability(),
        ]
        self._name_map = {c.name: c for c in self._capabilities}

    def select(self, intent: IntentType) -> BaseCapability:
        """Return the first capability that can handle the given intent."""
        for cap in self._capabilities:
            if cap.can_handle(intent):
                logger.info(
                    "[CAPABILITY_ROUTER] intent=%s → capability=%s",
                    intent.value, cap.name.value,
                )
                return cap
        return self._name_map[CapabilityType.FALLBACK]

    def get_capability(self, name: CapabilityType) -> BaseCapability:
        """Return a capability by type name."""
        return self._name_map.get(name, self._name_map[CapabilityType.FALLBACK])


capability_router = CapabilityRouter()
