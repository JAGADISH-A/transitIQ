"""Backend intent classifier for the Conversation Intelligence Engine.

Uses deterministic rules first. Only falls back to Groq when
confidence is low. This prevents unnecessary LLM calls for
simple queries.
"""

import json
import logging
import re
from typing import Optional

from groq import Groq

from app.config import get_settings
from app.models.conversation import IntentType
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classify user messages into backend-recognised intents.

    Tier 1 — Deterministic rules (fast, no LLM cost)
    Tier 2 — LLM fallback (when deterministic confidence is low)
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Groq | None = None
        if self.settings.GROQ_API_KEY:
            try:
                self._client = Groq(api_key=self.settings.GROQ_API_KEY)
            except Exception as exc:
                logger.warning("Groq client unavailable for intent fallback: %s", exc)
        self.model = self.settings.GROQ_MODEL

    # ------------------------------------------------------------------
    # Tier 1 — Deterministic rules
    # ------------------------------------------------------------------

    _GREETING_PATTERNS = [
        re.compile(r"^(hello|hi|hey|good\s*(morning|afternoon|evening)|namaste|vanakkam)\b", re.IGNORECASE),
        re.compile(r"^yo\b", re.IGNORECASE),
    ]

    _HELP_PATTERNS = [
        re.compile(r"\bhelp\b", re.IGNORECASE),
        re.compile(r"\bwhat can you do\b", re.IGNORECASE),
        re.compile(r"\bhow (do you|can you) (work|help)\b", re.IGNORECASE),
        re.compile(r"\bcapabilities\b", re.IGNORECASE),
        re.compile(r"\bwhat (are|is) your (features?|commands?)\b", re.IGNORECASE),
    ]

    _SMALL_TALK_PATTERNS = [
        re.compile(r"\bhow are you\b", re.IGNORECASE),
        re.compile(r"\bwhat('s| is|s) up\b", re.IGNORECASE),
        re.compile(r"\bhow('s| is) it going\b", re.IGNORECASE),
        re.compile(r"\b(nice|great|awesome)\s+(to meet you|weather)\b", re.IGNORECASE),
    ]

    _NEW_JOURNEY_PATTERNS = [
        re.compile(r"(?:from|between)\s+.+\s+to\s+", re.IGNORECASE),
        re.compile(r"how\s+(?:do|can|to)\s+(?:i\s+)?(?:get|go|travel|reach)\s+", re.IGNORECASE),
        re.compile(r"how\s+go\s+\w+", re.IGNORECASE),
        re.compile(r"(?:plan|find|search|show)\s+(?:a\s+)?(?:route|trip|journey|way)\s+", re.IGNORECASE),
        re.compile(r"(?:i\s+(?:want|would\s+like|need)\s+(?:to\s+)?(?:go|travel|reach))\s+", re.IGNORECASE),
        re.compile(r"^(?:route|trip|journey|travel|directions?)\s+(?:from|between|to)\b", re.IGNORECASE),
        re.compile(r".+\s*(?:->|→|to)\s+.+", re.IGNORECASE),
    ]

    _STATION_PATTERNS = [
        re.compile(r"\b(?:search|find|look\s+up)\s+(?:for\s+)?(?:station|stop)\b", re.IGNORECASE),
        re.compile(r"\bwhere\s+is\b.+(?:station|stop)\b", re.IGNORECASE),
        re.compile(r"\b(?:station|stop)\s+information\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+stations?\b", re.IGNORECASE),
        re.compile(r"\bnearby\s", re.IGNORECASE),
        re.compile(r"\binfo\s+about\s+(?:station|stop)\b", re.IGNORECASE),
        # Phase 4 — Station classification patterns
        re.compile(r"\bis\s+\w+\s+(?:a\s+)?(?:junction|terminal|halt)\b", re.IGNORECASE),
        re.compile(r"\bis\s+.+?(?:a\s+)?(?:junction|terminal|halt)\b", re.IGNORECASE),
        re.compile(r"\btell\s+me\s+about\s+\w+\s+(?:station|stop)\b", re.IGNORECASE),
        re.compile(r"\btell\s+me\s+about\s+.+?(?:station|stop)\b", re.IGNORECASE),
        re.compile(r"\bmajor\s+stations?\s+(?:on|along|in)\b", re.IGNORECASE),
        re.compile(r"\bwhere\s+should\s+i\s+board\b", re.IGNORECASE),
    ]

    _TRAIN_PATTERNS = [
        re.compile(r"\binformation\s+(?:about|regarding|on)\s+(?:train|express)\b", re.IGNORECASE),
        re.compile(r"\btrain\s+(?:info|number|details)\b", re.IGNORECASE),
        re.compile(r"\b(?:coach|berth|seat)\s+(?:position|layout|composition|information)\b", re.IGNORECASE),
        re.compile(r"\babout\s+(?:train|express|passenger)\s+\d+\b", re.IGNORECASE),
        re.compile(r"\btell\s+me\s+about\s+(?:\w+\s+)?train\b", re.IGNORECASE),
        re.compile(r"\b(?:explain|describe)\s+this\s+train\b", re.IGNORECASE),
        # Phase 4 — Train classification patterns
        re.compile(r"\b(?:what\s+type|is\s+this)\s+(?:of\s+)?train\b", re.IGNORECASE),
        re.compile(r"\bis\s+this\s+(?:a\s+)?(?:superfast|express)\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+(?:type|kind|class)\s+(?:of\s+)?train\s+(?:is\s+)?\d+\b", re.IGNORECASE),
    ]

    _SCHEDULE_PATTERNS = [
        re.compile(r"\b(?:when|what\s+time)\s+(?:does|is|will)\b", re.IGNORECASE),
        re.compile(r"\bschedule\b", re.IGNORECASE),
        re.compile(r"\btimings?\b", re.IGNORECASE),
        re.compile(r"\bdeparture\s+time\b", re.IGNORECASE),
        re.compile(r"\barrival\s+time\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+time\b", re.IGNORECASE),
    ]

    _KNOWLEDGE_PATTERNS = [
        re.compile(r"\bwhat\s+is\s+(?:a|an|the)\s+(?!station|stop|train|route|schedule|fastest|best|shortest|quickest|earliest|cheapest)\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+is\s+(?:waitlist|chair\s+car)\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+(?:does|is)\s+RAC\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+(?:does|is)\s+(?:CNF|WL|GNWL|PQWL|RLWL|TQWL|RSWL|TATKAL|QUEUE)\b", re.IGNORECASE),
        re.compile(r"\b(?:explain|tell\s+me\s+about)\s+(?:RAC|tatkal|quota|waitlist)\b", re.IGNORECASE),
        re.compile(r"\b(?:general|sleeper|AC|chair\s+car)\s+(?:class|coach)\b", re.IGNORECASE),
        re.compile(r"\bhow\s+(?:does|is)\s+(?:RAC|waitlist|tatkal)\s", re.IGNORECASE),
    ]

    _ROUTE_CONTEXT_QA_PATTERNS = [
        re.compile(r"\b(?:stations?|stops?)\s+(?:on\s+the\s+way|along|between|in\s+between)\b", re.IGNORECASE),
        re.compile(r"\b(?:where|which\s+station)\s+(?:should\s+i\s+)?board\b", re.IGNORECASE),
        re.compile(r"\b(?:where|which\s+station)\s+(?:should\s+i\s+)?(?:get\s+off|deboard|alight|disembark)\b", re.IGNORECASE),
        re.compile(r"\b(?:how\s+long|duration|travel\s+time)\b", re.IGNORECASE),
        re.compile(r"\b(?:next\s+station|last\s+station|final\s+stop)\b", re.IGNORECASE),
        re.compile(r"\bwhy\s+(?:are|is)\s+there\s+(?:no|not)\s+(?:trains?|routes?)\b", re.IGNORECASE),
        # Phase 4 — Journey insight patterns
        re.compile(r"\b(overnight|daytime)\s+(train|trip|journey)\b", re.IGNORECASE),
        re.compile(r"\b(?:is\s+this\s+)?(?:a\s+)?(?:long\s+journey|short\s+trip)\b", re.IGNORECASE),
        re.compile(r"\b(?:how\s+many|number\s+of)\s+stops\b", re.IGNORECASE),
        re.compile(r"\b(?:will\s+i|do\s+i)\s+need\s+to\s+transfer\b", re.IGNORECASE),
        re.compile(r"\bis\s+\d+\s+minutes?\s+(enough|sufficient)\b", re.IGNORECASE),
        re.compile(r"\b(?:is\s+this|is\s+it)\s+(?:an?\s+)?(?:express|overnight|direct)\s+(?:train|trip|journey)\b", re.IGNORECASE),
        re.compile(r"\b(?:how\s+far|distance|how\s+many\s+km)\b", re.IGNORECASE),
    ]

    _FOLLOW_UP_PATTERNS = [
        re.compile(r"^(and|then|what\s+about|next|after\s+that)\b", re.IGNORECASE),
        re.compile(r"\btell\s+me\s+more\b", re.IGNORECASE),
        re.compile(r"^(ok|okay|thanks|thank\s+you).*\?", re.IGNORECASE),
    ]

    # --- Phase 3: New intent patterns ---
    _COMPARISON_PATTERNS = [
        re.compile(r"\b(which|compare|comparison)\s+(is|has|would|will|arrives|departs|reaches)\b", re.IGNORECASE),
        re.compile(r"\bcompare\b", re.IGNORECASE),
        re.compile(r"\bwhich\s+(is|one(\s+is)?)\s+(faster|better|shorter|quicker|earlier)\b", re.IGNORECASE),
        re.compile(r"\b(faster|quicker|earlier|shorter)\s+than\b", re.IGNORECASE),
        re.compile(r"\bfewer\s+stops?\b", re.IGNORECASE),
        re.compile(r"\bbetter\s+(option|route|choice)\b", re.IGNORECASE),
    ]

    _RECOMMENDATION_PATTERNS = [
        re.compile(r"\b(recommend|suggest|best|top)\s+(a|the|me|one)?\s*(\w+\s+)?(route|option|train|journey|way)\b", re.IGNORECASE),
        re.compile(r"\bwhat(\'s| is)\s+(the\s+)?(best|fastest|shortest|quickest|earliest|cheapest)\b", re.IGNORECASE),
        re.compile(r"\brecommend\s+one\b", re.IGNORECASE),
        re.compile(r"\bwhich\s+.+?\s+(recommend|suggest)\b", re.IGNORECASE),
    ]

    _BOOKING_PATTERNS = [
        re.compile(r"\bbook\s+(a\s+)?(ticket|berth)\b", re.IGNORECASE),
        re.compile(r"\b(reserve|purchase)\s+(a\s+)?(ticket|seat|berth)\b", re.IGNORECASE),
        re.compile(r"^\s*book\s*$", re.IGNORECASE),
    ]

    # --- Phase 5: Multi-modal transport patterns ---
    _MULTI_MODAL_PATTERNS = [
        re.compile(r"\b(metro|bus|ferry)\s+(after|afterwards|then|from|at)\b", re.IGNORECASE),
        re.compile(r"\b(take|use|get)\s+(the\s+)?(metro|bus|ferry)\s+(after|from|at|to)\b", re.IGNORECASE),
        re.compile(r"\b(switch|change|transfer)\s+to\s+(the\s+)?(metro|bus|ferry)\s+(after|once|when)\b", re.IGNORECASE),
        re.compile(r"\b(bus|metro|ferry)\s+from\s+(the\s+)?(last|final|next|nearest)\s+(station|stop)\b", re.IGNORECASE),
        re.compile(r"\bwhat['']s\s+(the\s+)?(fastest|best|quickest)\s+combination\b", re.IGNORECASE),
        re.compile(r"\b(first.?mile|last.?mile)\b", re.IGNORECASE),
        re.compile(r"\b(combine|multi.?modal|mixed)\s+(transport|mode|journey|travel)\b", re.IGNORECASE),
        re.compile(r"\b(combine|mix)\s+\w+\s+(?:and|with)\s+\w+\b", re.IGNORECASE),
        re.compile(r"\b(first|then|after)\s+(take|use|get|switch|board)\s+(the\s+)?(metro|bus|ferry)\b", re.IGNORECASE),
        re.compile(r"\bfirst\s+(train|bus|metro|ferry)\s+then\s+(train|bus|metro|ferry)\b", re.IGNORECASE),
    ]

    _MODAL_FILTER_PATTERNS = [
        re.compile(r"\bavoid\s+(bus(?:es)?|metro|ferry|changing)\b", re.IGNORECASE),
        re.compile(r"\b(use|take|prefer)\s+only\s+(trains?|rail|bus|metro|ferry)\b", re.IGNORECASE),
        re.compile(r"\bonly\s+(trains?|rail|bus|metro|ferry)\b", re.IGNORECASE),
        re.compile(r"\b(use\s+)?no\s+(buses?|metro|ferry|transfers)\b", re.IGNORECASE),
        re.compile(r"\b(avoid|no|don'?t)\s+(want\s+)?(transfers|changing)\b", re.IGNORECASE),
    ]

    def _check_patterns(self, text: str, patterns: list[re.Pattern]) -> bool:
        """Return True if any pattern matches the text."""
        return any(p.search(text) for p in patterns)

    def _classify_deterministic(self, text: str) -> tuple[IntentType, float]:
        """Apply deterministic rules. Returns (intent, confidence)."""

        text_stripped = text.strip()

        # Priority order matters — check most specific first.

        # GREETING — short, no other content
        if self._check_patterns(text_stripped, self._GREETING_PATTERNS):
            # Pure greeting with 1-3 words
            word_count = len(text_stripped.split())
            if word_count <= 4:
                return IntentType.GREETING, 0.95

        # HELP
        if self._check_patterns(text_stripped, self._HELP_PATTERNS):
            return IntentType.HELP, 0.9

        # SMALL_TALK
        if self._check_patterns(text_stripped, self._SMALL_TALK_PATTERNS):
            return IntentType.SMALL_TALK, 0.9

        # KNOWLEDGE_QUERY — check before NEW_JOURNEY since "what is" could be ambiguous
        if self._check_patterns(text_stripped, self._KNOWLEDGE_PATTERNS):
            return IntentType.KNOWLEDGE_QUERY, 0.85

        # ROUTE_CONTEXT_QA — check early when a journey is active so that
        # journey-context questions (e.g. "What stations are on the way?")
        # take priority over generic STATION_INFORMATION or SCHEDULE_QUERY.
        if session_manager.has_active_journey():
            if self._check_patterns(text_stripped, self._ROUTE_CONTEXT_QA_PATTERNS):
                return IntentType.ROUTE_CONTEXT_QA, 0.9

            # FOLLOW_UP — only if a journey exists and question references it
            if self._check_patterns(text_stripped, self._FOLLOW_UP_PATTERNS):
                return IntentType.FOLLOW_UP, 0.75

            # Generic question about the current journey (no specific pattern)
            if len(text_stripped) > 10 and "?" in text_stripped:
                return IntentType.ROUTE_CONTEXT_QA, 0.6

        # STATION_INFORMATION
        if self._check_patterns(text_stripped, self._STATION_PATTERNS):
            return IntentType.STATION_INFORMATION, 0.85

        # TRAIN_INFORMATION
        if self._check_patterns(text_stripped, self._TRAIN_PATTERNS):
            return IntentType.TRAIN_INFORMATION, 0.8

        # SCHEDULE_QUERY
        if self._check_patterns(text_stripped, self._SCHEDULE_PATTERNS):
            return IntentType.SCHEDULE_QUERY, 0.8

        # MODAL_FILTER (Phase 5) — check before NEW_JOURNEY since broad
        # 'to' patterns could match multi-modal queries
        if self._check_patterns(text_stripped, self._MODAL_FILTER_PATTERNS):
            return IntentType.MODAL_FILTER, 0.85

        # MULTI_MODAL_QUERY (Phase 5)
        if self._check_patterns(text_stripped, self._MULTI_MODAL_PATTERNS):
            return IntentType.MULTI_MODAL_QUERY, 0.85

        # NEW_JOURNEY — broad patterns for trip planning
        if self._check_patterns(text_stripped, self._NEW_JOURNEY_PATTERNS):
            return IntentType.NEW_JOURNEY, 0.85

        # COMPARISON (Phase 3) — check before general routing
        if self._check_patterns(text_stripped, self._COMPARISON_PATTERNS):
            return IntentType.COMPARISON, 0.85

        # RECOMMENDATION (Phase 3)
        if self._check_patterns(text_stripped, self._RECOMMENDATION_PATTERNS):
            return IntentType.RECOMMENDATION, 0.85

        # BOOKING (Phase 3)
        if self._check_patterns(text_stripped, self._BOOKING_PATTERNS):
            return IntentType.BOOKING, 0.85

        # FOLLOW_UP without journey
        if self._check_patterns(text_stripped, self._FOLLOW_UP_PATTERNS):
            return IntentType.FOLLOW_UP, 0.5

        return IntentType.UNKNOWN, 0.0

    # ------------------------------------------------------------------
    # Tier 2 — LLM fallback
    # ------------------------------------------------------------------

    def _classify_with_llm(self, text: str) -> tuple[IntentType, float]:
        """Use Groq to classify when deterministic rules are uncertain."""
        if self._client is None:
            return IntentType.UNKNOWN, 0.0

        try:
            valid_intents = [e.value for e in IntentType]
            system_prompt = (
                "You are an intent classifier for a railway transit assistant. "
                "Classify the user's message into exactly one of these intents:\n\n"
                f"{', '.join(valid_intents)}\n\n"
                "NEW_JOURNEY: User wants to plan a trip from one place to another.\n"
                "FOLLOW_UP: User is continuing a previous conversation about a journey.\n"
                "STATION_INFORMATION: User wants information about a specific station/stop.\n"
                "TRAIN_INFORMATION: User wants details about a specific train.\n"
                "SCHEDULE_QUERY: User is asking about departure/arrival times.\n"
                "ROUTE_EXPLANATION: User wants the reasoning behind a route recommendation.\n"
                "ROUTE_CONTEXT_QA: User has a question about their current journey.\n"
                "KNOWLEDGE_QUERY: User is asking about railway knowledge (RAC, quotas, etc.).\n"
                "SMALL_TALK: Casual conversation not related to transit.\n"
                "GREETING: Simple greeting or salutation.\n"
                "HELP: User is asking what the assistant can do.\n"
                "UNKNOWN: Cannot determine the intent.\n\n"
                "COMPARISON: User is comparing two or more routes, trains, or options.\n"
                "RECOMMENDATION: User wants a recommendation for the best option.\n"
                "BOOKING: User wants to book a ticket.\n"
                "MODAL_FILTER: User wants to filter by transport mode (avoid buses, use only trains, etc.).\n"
                "MULTI_MODAL_QUERY: User is asking about multi-modal transport, combining bus/metro/ferry with rail.\n\n"
                "Return ONLY a JSON object: {\"intent\": \"INTENT_TYPE\"}"
            )

            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            content = response.choices[0].message.content
            if content:
                parsed = json.loads(content)
                intent_str = parsed.get("intent", "UNKNOWN")
                try:
                    intent = IntentType(intent_str)
                    return intent, 0.7
                except ValueError:
                    pass
        except Exception as exc:
            logger.warning("LLM intent classification failed: %s", exc)

        return IntentType.UNKNOWN, 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> tuple[IntentType, float]:
        """Classify the user message into an intent.

        Returns (IntentType, confidence) where confidence is 0.0–1.0.
        """
        if not text or not text.strip():
            return IntentType.UNKNOWN, 0.0

        # Tier 1: deterministic
        intent, confidence = self._classify_deterministic(text)
        if confidence >= 0.7:
            logger.info(
                "[INTENT_CLASSIFIER] Deterministic: %s (confidence=%.2f) query=%r",
                intent.value, confidence, text[:80],
            )
            return intent, confidence

        # Tier 2: LLM fallback
        llm_intent, llm_confidence = self._classify_with_llm(text)
        if llm_confidence > confidence:
            logger.info(
                "[INTENT_CLASSIFIER] LLM fallback: %s (confidence=%.2f) query=%r",
                llm_intent.value, llm_confidence, text[:80],
            )
            return llm_intent, llm_confidence

        logger.info("[INTENT_CLASSIFIER] Unknown: query=%r", text[:80])
        return IntentType.UNKNOWN, 0.0


intent_classifier = IntentClassifier()
