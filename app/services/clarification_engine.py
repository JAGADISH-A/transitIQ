"""Deterministic clarification engine.

Detects incomplete or ambiguous questions and determines what
information is missing. Returns structured clarification requests
instead of allowing the LLM to hallucinate.
"""

import logging
import re
from typing import Any

from app.models.conversation import (
    Clarification,
    ConversationContext,
    MissingInfoType,
)
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)


class ClarificationEngine:
    """Detects missing information in user queries and produces clarifications.

    The engine is entirely deterministic. No LLM is used.
    """

    # Patterns that indicate missing information
    _AMBIGUOUS_QUANTITY_PATTERNS = [
        re.compile(r"\bhow\s+much\b", re.IGNORECASE),
        re.compile(r"\bhow\s+many\b", re.IGNORECASE),
        re.compile(r"\bwhat(\'s| is)\s+the\s+(cost|price|fare|rate)\b", re.IGNORECASE),
    ]

    _DESTINATION_NEEDED_PATTERNS = [
        re.compile(r"\bbook\s+(a\s+)?ticket\b", re.IGNORECASE),
        re.compile(r"\b(reserve|book|purchase)\s+(a\s+)?(ticket|seat|berth)\b", re.IGNORECASE),
        re.compile(r"^\s*book\s*$", re.IGNORECASE),
        re.compile(r"^\s*ticket\s*$", re.IGNORECASE),
    ]

    _AMBIGUOUS_WHERE_PATTERNS = [
        re.compile(r"^\s*where\??\s*$", re.IGNORECASE),
        re.compile(r"^\s*where\s+(to|should|do|can)\??\s*$", re.IGNORECASE),
    ]

    _AMBIGUOUS_WHEN_PATTERNS = [
        re.compile(r"^\s*when\??\s*$", re.IGNORECASE),
        re.compile(r"^\s*when\s+(does|is|will|should|can)\??\s*$", re.IGNORECASE),
    ]

    _AMBIGUOUS_PLATFORM_PATTERNS = [
        re.compile(r"^\s*platform\??\s*$", re.IGNORECASE),
        re.compile(r"\bplatform\s+number\??$", re.IGNORECASE),
        re.compile(r"\bwhich\s+platform\b", re.IGNORECASE),
    ]

    _STATION_NEEDED_PATTERNS = [
        re.compile(r"^\s*distance\??\s*$", re.IGNORECASE),
        re.compile(r"^\s*fare\??\s*$", re.IGNORECASE),
        re.compile(r"^\s*duration\??\s*$", re.IGNORECASE),
    ]

    _TRAIN_NEEDED_PATTERNS = [
        re.compile(r"\bwhich\s+(train|route)\b", re.IGNORECASE),
    ]

    _SEAT_TYPE_PATTERNS = [
        re.compile(r"\b(seat|berth|class|coach)\s+(type|class|preference)\b", re.IGNORECASE),
    ]

    def detect(self, query: str, ctx: ConversationContext) -> Clarification:
        """Detect if the query is missing information that needs clarification.

        Returns a Clarification object. If no clarification is needed,
        needed=False is returned.
        """
        q = query.strip()
        journey = ctx.current_journey
        history = session_manager.get_history(limit=4)

        # 1. "Book ticket" — missing destination/train
        if self._check_any(q, self._DESTINATION_NEEDED_PATTERNS):
            return Clarification(
                needed=True,
                missing_type=MissingInfoType.DESTINATION,
                question="Which train would you like to book?",
                context_hint="No destination or train specified for booking.",
            )

        # 2. Bare "How much?" — ambiguous quantity
        if self._check_any(q, self._AMBIGUOUS_QUANTITY_PATTERNS):
            hints = []
            if journey:
                hints.append("fare for this journey")
                hints.append("distance")
                hints.append("travel time")
            else:
                hints.append("journey fare")
                hints.append("distance")
                hints.append("ticket price")

            return Clarification(
                needed=True,
                missing_type=MissingInfoType.AMBIGUOUS_QUANTITY,
                question=f"Are you asking about the {' or '.join(hints)}?",
                context_hint=f"Could refer to: {', '.join(hints)}",
            )

        # 3. Bare "Where?" — ambiguous location
        if self._check_any(q, self._AMBIGUOUS_WHERE_PATTERNS):
            if journey:
                return Clarification(
                    needed=True,
                    missing_type=MissingInfoType.AMBIGUOUS_QUANTITY,
                    question="Are you asking about where to board, where to get off, or a station location?",
                    context_hint="Could refer to boarding point, destination, or station search.",
                )
            return Clarification(
                needed=True,
                missing_type=MissingInfoType.AMBIGUOUS_QUANTITY,
                question="Which station are you looking for?",
                context_hint="No station specified.",
            )

        # 4. Bare "When?" — ambiguous time
        if self._check_any(q, self._AMBIGUOUS_WHEN_PATTERNS):
            if journey:
                return Clarification(
                    needed=True,
                    missing_type=MissingInfoType.TIME,
                    question=f"Are you asking about departure ({journey.departure_time}), arrival ({journey.arrival_time}), or a different time?",
                    context_hint="Could refer to departure, arrival, or schedule query.",
                )
            return Clarification(
                needed=True,
                missing_type=MissingInfoType.TIME,
                question="What time are you asking about?",
                context_hint="No time context specified.",
            )

        # 5. Bare "Platform?" — needs train/station context
        if self._check_any(q, self._AMBIGUOUS_PLATFORM_PATTERNS):
            if journey:
                return Clarification(
                    needed=False,
                    missing_type=MissingInfoType.NONE,
                    question="",
                    context_hint="Ask about platform for the journey.",
                )
            return Clarification(
                needed=True,
                missing_type=MissingInfoType.TRAIN,
                question="Which train or station are you asking about?",
                context_hint="No train or station specified for platform query.",
            )

        # 6. "Which train?" — needs suggestion
        if self._check_any(q, self._TRAIN_NEEDED_PATTERNS):
            if journey:
                return Clarification(
                    needed=False,
                    missing_type=MissingInfoType.NONE,
                    question="",
                    context_hint=f"User asking about {journey.train_name}.",
                )
            return Clarification(
                needed=True,
                missing_type=MissingInfoType.DESTINATION,
                question="Where would you like to travel?",
                context_hint="No destination to suggest a train.",
            )

        # 7. Bare "Distance?", "Fare?", "Duration?" — needs journey context
        if self._check_any(q, self._STATION_NEEDED_PATTERNS):
            if not journey:
                return Clarification(
                    needed=True,
                    missing_type=MissingInfoType.JOURNEY,
                    question="Which journey are you asking about? Please set a destination first.",
                    context_hint="No active journey to query.",
                )
            return Clarification(
                needed=False,
                missing_type=MissingInfoType.NONE,
                question="",
                context_hint="Can use current journey context to answer.",
            )

        # 8. Ambiguous "What about X?" with ellipsis
        about_match = re.match(
            r"\bwhat\s+about\s+(.+?)\??$", q, re.IGNORECASE,
        )
        if about_match:
            subject = about_match.group(1).strip().lower()
            if subject in ("tomorrow", "monday", "tuesday", "wednesday", "thursday",
                          "friday", "saturday", "sunday", "today", "next week", "next month"):
                if journey:
                    return Clarification(
                        needed=False,
                        missing_type=MissingInfoType.NONE,
                        question="",
                        context_hint=(
                            f"User asking about {subject} for {journey.origin}→{journey.destination}. "
                            "Inherit journey context and use schedule data."
                        ),
                    )

        return Clarification()

    @staticmethod
    def _check_any(text: str, patterns: list[re.Pattern]) -> bool:
        return any(p.search(text) for p in patterns)


clarification_engine = ClarificationEngine()
