"""Deterministic conversation state machine.

The backend owns conversation state. The LLM never decides or modifies state.
Every transition is computed from: current state, intent, query content,
journey presence, and capability result.
"""

import logging
import re
from typing import Any

from app.models.conversation import (
    ConversationState,
    IntentType,
)

logger = logging.getLogger(__name__)


class ConversationStateEngine:
    """Deterministic state machine for conversation transitions.

    Usage:
        state_engine = ConversationStateEngine()
        next_state = state_engine.transition(current_state, intent, query, has_journey, cap_result)
    """

    def transition(
        self,
        current_state: str,
        intent: IntentType,
        query: str,
        has_journey: bool,
        cap_result: dict[str, Any] | None = None,
    ) -> str:
        """Compute the next conversation state deterministically."""
        next_state = self._compute_current_state(intent, query, has_journey, cap_result)
        logger.info(
            "[STATE] %s + %s -> %s",
            current_state, intent.value, next_state,
        )
        return next_state

    def initial_state(self) -> str:
        return ConversationState.NO_CONTEXT.value

    @staticmethod
    def _compute_current_state(
        intent: IntentType,
        query: str,
        has_journey: bool,
        cap_result: dict[str, Any] | None = None,
    ) -> str:
        q = query.lower()

        # Greeting / Help / Small talk -> GENERAL_CHAT
        if intent in (IntentType.GREETING, IntentType.HELP, IntentType.SMALL_TALK):
            return ConversationState.GENERAL_CHAT.value

        # Knowledge queries -> GENERAL_CHAT (not about a specific journey)
        if intent == IntentType.KNOWLEDGE_QUERY:
            return ConversationState.GENERAL_CHAT.value

        # Station information -> DISCUSSING_STATION
        if intent == IntentType.STATION_INFORMATION:
            return ConversationState.DISCUSSING_STATION.value

        # Train information -> TRAIN_SELECTED if journey exists, else DISCUSSING_ROUTE
        if intent == IntentType.TRAIN_INFORMATION:
            return ConversationState.TRAIN_SELECTED.value if has_journey else ConversationState.DISCUSSING_ROUTE.value

        # Schedule queries -> DISCUSSING_TIMINGS
        if intent == IntentType.SCHEDULE_QUERY:
            return ConversationState.DISCUSSING_TIMINGS.value

        # Route explanation -> DISCUSSING_EXPLANATION
        if intent == IntentType.ROUTE_EXPLANATION:
            return ConversationState.DISCUSSING_EXPLANATION.value

        # New journey planning
        if intent == IntentType.NEW_JOURNEY:
            if has_journey:
                return ConversationState.JOURNEY_ACTIVE.value
            # Check if routes were found in cap_result
            if cap_result and cap_result.get("routes_found"):
                return ConversationState.ROUTES_FOUND.value
            return ConversationState.NO_CONTEXT.value

        # Follow-up -> inherit based on query content
        if intent == IntentType.FOLLOW_UP:
            if has_journey:
                return ConversationState.JOURNEY_ACTIVE.value
            return ConversationState.NO_CONTEXT.value

        # Comparison
        if intent == IntentType.COMPARISON:
            return ConversationState.DISCUSSING_ROUTE.value

        # Recommendation
        if intent == IntentType.RECOMMENDATION:
            return ConversationState.DISCUSSING_ROUTE.value

        # Booking
        if intent == IntentType.BOOKING:
            return ConversationState.WAITING_FOR_CLARIFICATION.value

        # Route context QA -> determine sub-state from query content
        if intent == IntentType.ROUTE_CONTEXT_QA:
            if not has_journey:
                return ConversationState.NO_CONTEXT.value
            if re.search(r"\bwhy\b", q):
                return ConversationState.DISCUSSING_EXPLANATION.value
            if re.search(r"\b(stations?|stops?|board|get\s*off|deboard|alight)\b", q):
                return ConversationState.DISCUSSING_STATION.value
            if re.search(r"\b(time|schedule|when|how\s*long|duration|minute|hour|arrival|departure)\b", q):
                return ConversationState.DISCUSSING_TIMINGS.value
            return ConversationState.DISCUSSING_ROUTE.value

        # Unknown -> WAITING_FOR_CLARIFICATION if we have context, else NO_CONTEXT
        if intent == IntentType.UNKNOWN:
            if has_journey:
                return ConversationState.WAITING_FOR_CLARIFICATION.value
            return ConversationState.NO_CONTEXT.value

        return ConversationState.NO_CONTEXT.value


state_engine = ConversationStateEngine()
