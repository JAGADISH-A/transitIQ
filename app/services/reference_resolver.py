"""Reference resolution engine for the Conversation Intelligence Engine.

Resolves pronouns, ordinals, temporal references, and ellipsis
entirely in the backend without LLM involvement.
"""

import logging
import re
from typing import Any

from app.models.conversation import (
    ConversationContext,
    ConversationTurn,
    ReferenceType,
    ResolvedReference,
)
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)


class ReferenceResolver:
    """Resolves references in user queries using conversation context.

    Sources inspected in order:
      1. Journey Context
      2. Conversation History
      3. Current Conversation State
      4. Last Tool Result
      5. Last Selected Train / Station
    """

    # Ordinal pattern: "the first one", "second train", "third option"
    _ORDINAL_PATTERN = re.compile(
        r"\b(the\s+)?(first|second|third|fourth|fifth|last|next|previous)\s*(one|train|route|option|station|stop|result)?\b",
        re.IGNORECASE,
    )

    # Pronoun pattern
    _PRONOUN_PATTERN = re.compile(
        r"\b(it|that|this|those|these)\b",
        re.IGNORECASE,
    )

    # Comparative pattern
    _COMPARATIVE_PATTERN = re.compile(
        r"\b(earlier|later|same|other|another)\s*(one|train|route|option|station|stop)?\b",
        re.IGNORECASE,
    )

    # Temporal ellipsis — single time words that inherit from context
    _TEMPORAL_ELLIPSIS_PATTERN = re.compile(
        r"^(tomorrow|today|tonight|now|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
        r"|morning|afternoon|evening|night|noon|midnight"
        r"|next\s+(week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"|this\s+(week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r")\s*\??$",
        re.IGNORECASE,
    )

    # Locative ellipsis
    _LOCATIVE_PATTERN = re.compile(
        r"\b(here|there)\b",
        re.IGNORECASE,
    )

    # Single-word ellipsis: "Platform?", "Stops?", "Duration?", "Distance?"
    _SINGLE_WORD_ELLIPSIS = re.compile(
        r"^(platform|stops?|duration|distance|fare|cost|price|time|schedule|route|train|station)"
        r"\s*\??$",
        re.IGNORECASE,
    )

    def resolve(
        self,
        query: str,
        ctx: ConversationContext,
    ) -> ResolvedReference:
        """Resolve any references in the user query.

        Returns a ResolvedReference with the resolved value and source.
        If no reference is found, returns a NONE type reference.
        """
        q = query.strip()

        # 1. Temporal ellipsis: "Tomorrow?", "Monday?"
        match = self._TEMPORAL_ELLIPSIS_PATTERN.match(q)
        if match:
            value = match.group(1).lower()
            return ResolvedReference(
                type=ReferenceType.TEMPORAL,
                value=value,
                confidence=0.95,
                source="query_pattern",
            )

        # 2. Single-word ellipsis: "Platform?", "Stops?"
        match = self._SINGLE_WORD_ELLIPSIS.match(q)
        if match:
            value = match.group(1).lower()
            resolved = self._resolve_single_word_ellipsis(value, ctx)
            return resolved

        # 3. Ordinal reference: "first one", "second train"
        match = self._ORDINAL_PATTERN.search(q)
        if match:
            return self._resolve_ordinal(match, ctx)

        # 4. Comparative: "earlier one", "same route"
        match = self._COMPARATIVE_PATTERN.search(q)
        if match:
            return self._resolve_comparative(match, ctx)

        # 5. Preposition + time: "after that", "before 8 AM" (before pronouns to avoid "that" catching "after that")
        if re.search(r"\b(after|before|around|by)\s", q, re.IGNORECASE):
            return self._resolve_preposition_time(q, ctx)

        # 6. Pronoun: "it", "that", "this"
        if self._PRONOUN_PATTERN.search(q):
            return self._resolve_pronoun(q, ctx)

        # 7. Locative: "here", "there"
        if self._LOCATIVE_PATTERN.search(q):
            return self._resolve_locative(q, ctx)

        return ResolvedReference()

    @staticmethod
    def _resolve_single_word_ellipsis(
        word: str,
        ctx: ConversationContext,
    ) -> ResolvedReference:
        """Resolve a single-word ellipsis by inheriting from context."""
        word_lower = word.lower().rstrip("?")

        mapping = {
            "platform": ("platform", "station"),
            "stops": ("stops", "journey"),
            "stop": ("stops", "journey"),
            "duration": ("duration", "journey"),
            "distance": ("distance", "journey"),
            "fare": ("fare", "journey"),
            "cost": ("fare", "journey"),
            "price": ("fare", "journey"),
            "time": ("time", "journey"),
            "schedule": ("schedule", "journey"),
            "route": ("route", "journey"),
            "train": ("train", "journey"),
            "station": ("station", "journey"),
        }

        entry = mapping.get(word_lower)
        if entry:
            return ResolvedReference(
                type=ReferenceType.ELLIPSIS,
                value=entry[0],
                confidence=0.9,
                source=entry[1],
            )

        return ResolvedReference()

    @staticmethod
    def _resolve_ordinal(
        match: re.Match,
        ctx: ConversationContext,
    ) -> ResolvedReference:
        """Resolve ordinal references like 'first one', 'second train'."""
        ordinal_map = {
            "first": 1, "second": 2, "third": 3,
            "fourth": 4, "fifth": 5,
        }
        word = match.group(2).lower()

        if word == "last":
            return ResolvedReference(
                type=ReferenceType.ORDINAL,
                value="last",
                confidence=0.85,
                source="context_last_item",
            )

        if word == "next":
            return ResolvedReference(
                type=ReferenceType.ORDINAL,
                value="next",
                confidence=0.85,
                source="context_next_item",
            )

        if word == "previous":
            return ResolvedReference(
                type=ReferenceType.ORDINAL,
                value="previous",
                confidence=0.85,
                source="context_previous_item",
            )

        idx = ordinal_map.get(word, 1)

        # Determine what the ordinal refers to
        entity_type = match.group(3)  # "train", "route", "option", "station", etc.
        if entity_type:
            entity_type = entity_type.lower()

        return ResolvedReference(
            type=ReferenceType.ORDINAL,
            value=str(idx),
            confidence=0.85,
            source=entity_type or "context_list",
        )

    @staticmethod
    def _resolve_comparative(
        match: re.Match,
        ctx: ConversationContext,
    ) -> ResolvedReference:
        """Resolve comparative references like 'earlier one', 'same route'."""
        word = match.group(1).lower()

        if word == "same":
            journey = ctx.current_journey
            if journey:
                return ResolvedReference(
                    type=ReferenceType.POSSESSIVE,
                    value="current_journey",
                    confidence=0.9,
                    source="journey_context",
                )
            return ResolvedReference(
                type=ReferenceType.POSSESSIVE,
                value="current_topic",
                confidence=0.7,
                source="conversation_history",
            )

        if word in ("earlier", "later"):
            return ResolvedReference(
                type=ReferenceType.COMPARATIVE,
                value=word,
                confidence=0.8,
                source="time_comparison",
            )

        if word in ("other", "another"):
            return ResolvedReference(
                type=ReferenceType.COMPARATIVE,
                value="alternative",
                confidence=0.75,
                source="context_alternative",
            )

        return ResolvedReference()

    @staticmethod
    def _resolve_pronoun(
        query: str,
        ctx: ConversationContext,
    ) -> ResolvedReference:
        """Resolve pronouns by inspecting context and history."""
        q_lower = query.lower()

        # "this" typically refers to current journey
        if re.search(r"\bthis\b", q_lower):
            if ctx.current_journey:
                return ResolvedReference(
                    type=ReferenceType.PRONOUN,
                    value="current_journey",
                    confidence=0.85,
                    source="journey_context",
                )
            return ResolvedReference(
                type=ReferenceType.PRONOUN,
                value="current_topic",
                confidence=0.7,
                source="conversation_history",
            )

        # "it", "that", "those", "these" — check history for last mentioned entity
        if re.search(r"\b(it|that|those|these)\b", q_lower):
            history = session_manager.get_history(limit=4)
            if history:
                # Look at last assistant reply for candidate entity
                last_assistant = session_manager.get_last_assistant_reply() or ""
                last_user = session_manager.get_last_user_message() or ""
                journey = ctx.current_journey

                # Check if last user message mentioned a train number
                train_match = re.search(r"\b(\d{4,5})\b", last_user)
                if train_match and journey:
                    return ResolvedReference(
                        type=ReferenceType.PRONOUN,
                        value=f"train_{train_match.group(1)}",
                        confidence=0.8,
                        source="conversation_history",
                    )

                # Check for station name in history
                station_match = re.search(
                    r"\b(station|stop)\s+(\w+)\b", last_assistant, re.IGNORECASE,
                )
                if station_match:
                    return ResolvedReference(
                        type=ReferenceType.PRONOUN,
                        value=station_match.group(2),
                        confidence=0.75,
                        source="conversation_history",
                    )

                # Default to current journey
                if journey:
                    return ResolvedReference(
                        type=ReferenceType.PRONOUN,
                        value="current_journey",
                        confidence=0.7,
                        source="journey_context",
                    )

            # No history, default to journey
            if ctx.current_journey:
                return ResolvedReference(
                    type=ReferenceType.PRONOUN,
                    value="current_journey",
                    confidence=0.7,
                    source="journey_context",
                )

        return ResolvedReference()

    @staticmethod
    def _resolve_locative(
        query: str,
        ctx: ConversationContext,
    ) -> ResolvedReference:
        """Resolve 'here' and 'there' references."""
        q_lower = query.lower()
        journey = ctx.current_journey

        if re.search(r"\bhere\b", q_lower) and journey:
            return ResolvedReference(
                type=ReferenceType.LOCATIVE,
                value=journey.origin,
                confidence=0.9,
                source="journey_origin",
            )

        if re.search(r"\bthere\b", q_lower) and journey:
            return ResolvedReference(
                type=ReferenceType.LOCATIVE,
                value=journey.destination,
                confidence=0.9,
                source="journey_destination",
            )

        return ResolvedReference()

    @staticmethod
    def _resolve_preposition_time(
        query: str,
        ctx: ConversationContext,
    ) -> ResolvedReference:
        """Resolve references like 'after that', 'before 8 AM'."""
        q_lower = query.lower()

        # Extract preposition + possible time
        prep_match = re.search(
            r"\b(after|before|around|by)\s+(\d{1,2}\s*(:?\d{2})?\s*(AM|PM|am|pm)?|that|it|this)\b",
            q_lower,
        )
        if prep_match:
            prep = prep_match.group(1).lower()
            ref = prep_match.group(2).lower()

            # "after that", "before it" -> temporal reference to current journey
            if ref in ("that", "it", "this"):
                if ctx.current_journey:
                    return ResolvedReference(
                        type=ReferenceType.TEMPORAL,
                        value=f"{prep}_journey",
                        confidence=0.85,
                        source="journey_context",
                    )

            # "before 8 AM", "after 5 PM" -> time constraint reference
            time_match = re.match(r"(\d{1,2})(:?\d{2})?\s*(AM|PM|am|pm)?", ref)
            if time_match:
                return ResolvedReference(
                    type=ReferenceType.TEMPORAL,
                    value=f"{prep}_{ref}",
                    confidence=0.9,
                    source="query_constraint",
                )

        return ResolvedReference()


reference_resolver = ReferenceResolver()
