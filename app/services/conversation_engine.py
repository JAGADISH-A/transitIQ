"""Conversation Intelligence Engine — the single entry point for every AI request.

Architecture:
  User → Engine → Intent Analysis → Context Assembly → Capability Selection
         → Tool Selection → Groq → Natural Response

The backend is the decision maker. The LLM is the communicator.

Part 2 — Conversation Intelligence Engine
Part 9 — Reasoning Strategy
Part 10 — Structured Logging

Phase 3 — Multi-Turn Reasoning & Conversation Intelligence
  - Conversation State Machine
  - Reference Resolution
  - Ellipsis Resolution
  - Clarification Engine
  - Memory Compression
  - Explanation / Recommendation / Comparison Reasoning
"""

import logging
import re
import time
from typing import Any

from groq import Groq

from app.config import get_settings
from app.models.conversation import (
    CapabilityType,
    Clarification,
    ComparisonItem,
    ComparisonResult,
    ConversationState,
    ConversationSummary,
    IntentType,
    RecommendationResult,
    ResolvedReference,
)
from app.models.transit import TransportPreference
from app.services.capabilities import CapabilityResult, capability_router
from app.services.clarification_engine import clarification_engine
from app.services.context_builder import context_builder
from app.services.conversation_state import state_engine
from app.services.foundry_agent import foundry_transit_agent
from app.services.intent_classifier import intent_classifier
from app.services.prompt_builder import prompt_builder
from app.services.railway_intelligence import railway_intelligence
from app.services.reference_resolver import reference_resolver
from app.services.session_manager import session_manager
from app.services.response_engine import (
    ResponseStrategy,
    ResponseDecision,
    ResponseType,
    ResponseFormatter,
    decide_strategy,
)

SUMARRY_THRESHOLD = 8

logger = logging.getLogger(__name__)


class ConversationIntelligenceEngine:
    """Orchestrator for all AI requests.

    This is the single entry point. Every AI request flows through here.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Groq | None = None
        if self.settings.GROQ_API_KEY:
            try:
                self._client = Groq(api_key=self.settings.GROQ_API_KEY)
            except Exception as exc:
                logger.warning("Groq client unavailable: %s", exc)
        self._response_engine: ResponseFormatter | None = None

        # Metrics counters
        self.metrics = {
            "total_requests": 0,
            "direct_responses": 0,
            "hybrid_responses": 0,
            "llm_responses": 0,
            "groq_failures": 0,
            "fallback_responses": 0,
            "estimated_tokens_saved": 0,
            "total_latency_ms": 0,
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process(self, user_query: str) -> dict[str, Any]:
        """Process a user message through the full intelligence pipeline.

        Returns a dict matching the existing /agent/foundry response format
        so the API contract remains unchanged.
        """
        start_time = time.perf_counter()
        session_manager.initialize_session()
        session_manager.update_last_question(user_query)

        # ------------------------------------------------------------------
        # Step 1 — Intent Classification
        # ------------------------------------------------------------------
        intent, confidence = intent_classifier.classify(user_query)
        session_manager.set_last_intent(intent.value)

        # ------------------------------------------------------------------
        # Step 2 — Capability Selection
        # ------------------------------------------------------------------
        capability = capability_router.select(intent)
        session_manager.set_last_capability(capability.name.value)

        # ------------------------------------------------------------------
        # Step 3 — Conversation State (Phase 3)
        # ------------------------------------------------------------------
        has_journey = session_manager.has_active_journey()
        current_state = session_manager.get_current_state() or "NO_CONTEXT"
        next_state = state_engine.transition(
            current_state, intent, user_query, has_journey,
        )
        session_manager.set_current_state(next_state)

        # ------------------------------------------------------------------
        # Step 4 — Reference & Ellipsis Resolution (Phase 3)
        # ------------------------------------------------------------------
        resolved_ref = self._resolve_references(user_query, intent, next_state)

        # ------------------------------------------------------------------
        # Step 5 — Clarification Detection (Phase 3)
        # ------------------------------------------------------------------
        clarification = self._detect_clarification(user_query, next_state)

        # ------------------------------------------------------------------
        # Step 6 — Conversation Summary Compression (Phase 3)
        # ------------------------------------------------------------------
        conv_summary = self._compress_summary()

        # ------------------------------------------------------------------
        # Step 7 — Context Assembly
        # ------------------------------------------------------------------
        comparison_result = self._compute_comparison(user_query, intent)
        recommendation_result = self._compute_recommendation(user_query, intent)

        # Phase 4 — Railway Intelligence computation (before Groq)
        railway_intel_data = self._compute_railway_intelligence(
            intent, user_query, comparison_result, recommendation_result,
        )

        # Phase 5 — Transport preference detection
        transport_pref = self._detect_transport_preference(user_query, intent)

        ctx = context_builder.build(
            user_query=user_query,
            intent=intent,
            capability=capability.name,
            conversation_state=next_state,
            resolved_reference=resolved_ref,
            conversation_summary=conv_summary,
            clarification=clarification,
            comparison_result=comparison_result,
            recommendation_result=recommendation_result,
            railway_intel_data=railway_intel_data,
            transport_preference=transport_pref,
        )

        # ------------------------------------------------------------------
        # Step 8 — Capability Execution
        # ------------------------------------------------------------------
        cap_result: CapabilityResult = capability.execute(ctx)
        ctx.capability_result = {
            "context_data": cap_result.context_data,
            "tools_used": cap_result.tools_used,
        }
        if cap_result.tools_used:
            session_manager.set_last_successful_tool(cap_result.tools_used[-1])

        # ------------------------------------------------------------------
        # Step 9 — Response Generation
        # ------------------------------------------------------------------
        response, provider, tools_used, route_data = self._generate_response(
            user_query=user_query,
            ctx=ctx,
            cap_result=cap_result,
        )

        # --- Metrics tracking ---
        self.metrics["total_requests"] += 1
        strategy_tag = None
        if provider == "engine":
            strategy_tag = "direct"
            self.metrics["direct_responses"] += 1
        elif provider == "groq":
            strategy_tag = "llm"
            self.metrics["llm_responses"] += 1
        elif provider in ("capability", "clarification"):
            strategy_tag = "direct"
            self.metrics["direct_responses"] += 1
        elif provider == "foundry":
            strategy_tag = "llm"
            self.metrics["llm_responses"] += 1
        if strategy_tag == "direct":
            self.metrics["estimated_tokens_saved"] += 500

        # ------------------------------------------------------------------
        # Step 10 — Update Session Memory
        # ------------------------------------------------------------------
        session_manager.add_turn("user", user_query)
        session_manager.add_turn("assistant", response)
        session_manager.set_last_assistant_reply(response)
        session_manager.set_last_user_message(user_query)

        # --- Phase 3 session updates ---
        if resolved_ref and resolved_ref.type.value != "NONE":
            session_manager.set_resolved_reference(
                resolved_ref.type.value, resolved_ref.value,
            )
        if clarification and clarification.needed:
            session_manager.set_selected_comparison_entity(
                clarification.missing_type.value,
            )

        # ------------------------------------------------------------------
        # Step 11 — Structured Logging
        # ------------------------------------------------------------------
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        railway_intel_fields = ",".join(railway_intel_data.keys()) if railway_intel_data else ""
        strategy_label = strategy_tag or "unknown"
        self.metrics["total_latency_ms"] += elapsed_ms
        self._log_engine(
            intent=intent,
            capability=capability.name,
            has_journey=has_journey,
            needs_tools=ctx.needs_tools or bool(cap_result.context_data.get("needs_tools")),
            provider=provider,
            tools_used=tools_used,
            elapsed_ms=elapsed_ms,
            conversation_state=next_state,
            ref_type=resolved_ref.type.value if resolved_ref else "NONE",
            clarification_needed=clarification.needed if clarification else False,
            railway_intel=railway_intel_fields,
        )
        logger.info(
            "[METRICS] strategy=%s provider=%s elapsed=%dms total_requests=%d tokens_saved=%d",
            strategy_label,
            provider,
            elapsed_ms,
            self.metrics["total_requests"],
            self.metrics["estimated_tokens_saved"],
        )

        return {
            "answer": response,
            "provider": provider,
            "classification": f"INTENT:{intent.value}",
            "execution_time_ms": elapsed_ms,
            "tools_used": tools_used,
            "route_data": route_data,
        }

    # ------------------------------------------------------------------
    # Response generation (Phase 3 — added clarification path)
    # ------------------------------------------------------------------

    def _generate_response(
        self,
        user_query: str,
        ctx: Any,
        cap_result: CapabilityResult,
    ) -> tuple[str, str, list[str], Any]:
        """Generate the final response based on strategy-based routing.

        Backend decides. Backend formats. AI enhances.

        Strategies:
          DIRECT   → ResponseFormatter produces the response. No LLM.
          HYBRID   → Try Groq for polish. Fallback to DIRECT on failure.
          LLM_ONLY → Existing Groq path (or foundry_agent for tools).
        """

        # --- Strategy Selection ---
        has_direct_answer = (not cap_result.needs_llm and bool(cap_result.answer))
        has_journey = bool(ctx.current_journey)
        needs_tools = bool(cap_result.context_data.get("needs_tools"))
        has_railway_intel = bool(ctx.train_profile or ctx.station_profile or ctx.journey_insights)
        groq_available = self._client is not None

        decision = decide_strategy(
            intent=ctx.intent,
            has_direct_answer=has_direct_answer,
            has_journey=has_journey,
            has_railway_intel=has_railway_intel,
            needs_tools=needs_tools,
            groq_available=groq_available,
        )

        self._response_engine = getattr(self, "_response_engine", None)
        if self._response_engine is None:
            self._response_engine = ResponseFormatter()

        logger.info(
            "[ENGINE] strategy=%s response_type=%s intent=%s",
            decision.strategy.value, decision.response_type, ctx.intent.value,
        )

        # --------------------------------------------------------------
        # DIRECT — Backend formats, no LLM
        # --------------------------------------------------------------
        if decision.strategy == ResponseStrategy.DIRECT:
            if has_direct_answer and cap_result.answer:
                return cap_result.answer, "capability", cap_result.tools_used, cap_result.route_data

            formatted = self._response_engine.format_response(
                response_type=decision.response_type,
                ctx=ctx,
                intent=ctx.intent,
                cap_result=cap_result,
            )
            if formatted:
                return formatted, "engine", cap_result.tools_used, cap_result.route_data

            return (
                self._build_fallback_response(ctx),
                "engine", cap_result.tools_used, cap_result.route_data,
            )

        # --------------------------------------------------------------
        # Path: Clarification needed (Phase 3)
        # --------------------------------------------------------------
        if ctx.clarification and ctx.clarification.needed:
            logger.info(
                "[ENGINE] clarification needed: %s", ctx.clarification.missing_type.value,
            )
            formatted = self._response_engine.format_response(
                response_type="clarification",
                ctx=ctx, intent=ctx.intent, cap_result=cap_result,
            )
            if formatted:
                return formatted, "clarification", [], None
            return ctx.clarification.question, "clarification", [], None

        # --------------------------------------------------------------
        # LLM_ONLY or HYBRID — needs tools → foundry_agent
        # --------------------------------------------------------------
        if needs_tools:
            logger.info("[ENGINE] needs_tools=True → delegating to foundry_agent")
            try:
                foundry_result = foundry_transit_agent.answer(user_query)
                return (
                    foundry_result.get("answer", "I could not generate a response."),
                    foundry_result.get("provider", "foundry"),
                    foundry_result.get("tools_used", cap_result.tools_used),
                    foundry_result.get("route_data"),
                )
            except Exception as exc:
                logger.warning("[ENGINE] foundry_agent failed: %s", exc)
                fallback = self._build_fallback_response(ctx)
                return fallback, "engine", [], None

        # --------------------------------------------------------------
        # HYBRID — Try Groq, fallback to DIRECT on failure
        # --------------------------------------------------------------
        if decision.strategy == ResponseStrategy.HYBRID:
            if groq_available:
                try:
                    response = self._call_groq(ctx)
                    return response, "groq", cap_result.tools_used, cap_result.route_data
                except Exception as exc:
                    logger.warning("[ENGINE] HYBRID Groq failed → DIRECT fallback: %s", exc)

            formatted = self._response_engine.format_response(
                response_type=decision.response_type,
                ctx=ctx, intent=ctx.intent, cap_result=cap_result,
            )
            if formatted:
                return formatted, "engine", cap_result.tools_used, cap_result.route_data

            fallback = self._build_fallback_response(ctx)
            return fallback, "engine", [], None

        # --------------------------------------------------------------
        # LLM_ONLY — Standard LLM generation
        # --------------------------------------------------------------
        try:
            response = self._call_groq(ctx)
            return response, "groq", cap_result.tools_used, cap_result.route_data
        except Exception as exc:
            logger.warning("[ENGINE] Groq call failed: %s", exc)
            formatted = self._response_engine.format_response(
                response_type=decision.response_type,
                ctx=ctx, intent=ctx.intent, cap_result=cap_result,
            )
            if formatted:
                return formatted, "engine", [], None
            fallback = self._build_fallback_response(ctx)
            return fallback, "engine", [], None

    # ------------------------------------------------------------------
    # Groq invocation
    # ------------------------------------------------------------------

    def _call_groq(self, ctx: Any) -> str:
        """Send a context-rich prompt to Groq for natural language generation.

        This path is for queries where the backend has already gathered
        the needed data. Groq only needs to produce a natural response.
        """
        if self._client is None:
            logger.warning("Groq client unavailable — returning context-only response")
            return self._build_fallback_response(ctx)

        system_prompt = prompt_builder.build_system_prompt(ctx)
        user_message = prompt_builder.build_user_message(ctx)

        try:
            response = self._client.chat.completions.create(
                model=self.settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=512,
            )

            content = response.choices[0].message.content
            return content or "I could not generate a response."
        except Exception as exc:
            logger.exception("[GROQ_CALL_FAILED]")
            return f"I encountered an error while processing your request: {exc}"

    @staticmethod
    def _build_fallback_response(ctx: Any) -> str:
        """Build a natural response from context when Groq is unavailable."""
        journey = ctx.current_journey
        if journey:
            lines = [
                f"Here's what I know about your trip from {journey.origin} to {journey.destination}:",
                f"",
                f"  Train: {journey.train_name} ({journey.train_number})",
                f"  Departure: {journey.departure_time}",
                f"  Arrival: {journey.arrival_time}",
                f"  Duration: {journey.duration} minutes",
            ]
            if journey.intermediate_stops:
                lines.append(f"  Stops on the way: {', '.join(journey.intermediate_stops)}")
            return "\n".join(lines)
        return "I can help you plan your railway journey. Just tell me your destination!"

    # ------------------------------------------------------------------
    # Phase 3 — Clarification Detection helper
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_clarification(query: str, state: str) -> Clarification:
        """Detect missing information using session data."""
        journey = session_manager.get_current_journey()

        class _ClarifyCtx:
            def __init__(self):
                self.current_journey = journey

        return clarification_engine.detect(query, _ClarifyCtx())

    # ------------------------------------------------------------------
    # Phase 3 — Reference & Ellipsis Resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_references(
        query: str,
        intent: IntentType,
        state: str,
    ) -> ResolvedReference:
        """Resolve references and ellipsis in the user query.

        Reference resolution uses the dedicated ReferenceResolver.
        Ellipsis resolution checks for single-word inherited queries.
        """
        # Build a minimal context for the resolver
        journey = session_manager.get_current_journey()
        history = session_manager.get_history(limit=4)

        class _MiniCtx:
            def __init__(self):
                self.current_journey = journey
                self.conversation_history = history
                self.resolved_reference = ResolvedReference()

        ctx = _MiniCtx()
        return reference_resolver.resolve(query, ctx)

    # ------------------------------------------------------------------
    # Phase 3 — Conversation Summary Compression
    # ------------------------------------------------------------------

    def _compress_summary(self) -> ConversationSummary | None:
        """Compress older conversation turns when history exceeds threshold.

        The summary stores key information from older turns so the
        full history does not need to be sent to the LLM.
        """
        history = session_manager.get_history(limit=20)
        if len(history) < SUMARRY_THRESHOLD:
            return None

        existing_summary = session_manager.get_conversation_summary()
        if existing_summary:
            return ConversationSummary(
                summary_text=existing_summary,
                turn_count=len(history),
                created_at=session_manager.get_summary_timestamp() or "",
            )

        # Build summary from old turns (retain only last N as raw history)
        turns_to_summarise = history[:-6]
        summary_parts = []
        decisions = []
        unresolved = []

        for turn in turns_to_summarise:
            text = turn.content[:120]
            if turn.role == "user":
                summary_parts.append(f"U: {text}")
                if "?" in text and len(text) < 40:
                    unresolved.append(text)
            else:
                summary_parts.append(f"A: {text}")

            # Detect decisions from assistant responses
            if turn.role == "assistant" and re.search(
                r"\b(you should|recommend|book|take|board)\b", text, re.IGNORECASE,
            ):
                decisions.append(text[:80])

        summary_text = " | ".join(summary_parts[-6:])
        session_manager.set_conversation_summary(summary_text)

        journey = session_manager.get_current_journey()

        return ConversationSummary(
            summary_text=summary_text,
            journey_context=journey.route_summary if journey else "",
            important_decisions=decisions[-3:] if decisions else [],
            unresolved_questions=unresolved[-3:] if unresolved else [],
            selected_train=session_manager.get_selected_train(),
            selected_station=session_manager.get_selected_station(),
            last_intent=session_manager.get_last_intent(),
            turn_count=len(history),
            created_at=session_manager.get_summary_timestamp() or "",
        )

    # ------------------------------------------------------------------
    # Phase 3 — Recommendation Reasoning
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_recommendation(
        query: str,
        intent: IntentType,
    ) -> RecommendationResult | None:
        """Compute recommendation reasoning when the user asks for one.

        Currently returns None since multi-route data is not yet populated.
        This serves as the foundation for Phase 4 when route search
        results are available in session memory.
        """
        if intent != IntentType.RECOMMENDATION:
            return None

        # Placeholder — Phase 4 will use actual route data
        return RecommendationResult(
            recommended_idx=0,
            criteria="duration",
            justification="Shortest travel time.",
        )

    # ------------------------------------------------------------------
    # Phase 5 — Transport preference detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_transport_preference(
        query: str,
        intent: IntentType,
    ) -> TransportPreference | None:
        """Detect transport mode preferences from the query."""
        if intent not in (IntentType.MULTI_MODAL_QUERY, IntentType.MODAL_FILTER):
            return None

        from app.models.transit import TransportMode
        q = query.lower()
        avoided: list[TransportMode] = []
        preferred: list[TransportMode] = []

        if re.search(r"\bavoid\s+(bus|buses)\b", q):
            avoided.append(TransportMode.BUS)
        if re.search(r"\bavoid\s+(metro)\b", q):
            avoided.append(TransportMode.METRO)
        if re.search(r"\bavoid\s+(ferry)\b", q):
            avoided.append(TransportMode.FERRY)
        if re.search(r"\b(no|don'?t)\s+(want\s+)?(transfers|changing)\b", q):
            pass

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

    # ------------------------------------------------------------------
    # Phase 4 — Railway Intelligence
    # ------------------------------------------------------------------

    def _compute_railway_intelligence(
        self,
        intent: IntentType,
        query: str,
        comparison_result: Any,
        recommendation_result: Any,
    ) -> dict | None:
        """Compute railway intelligence data before Groq is invoked.

        Uses deterministic backend engines for train profiles, station profiles,
        journey insights, recommendations, comparisons, explanations, and
        railway knowledge. The LLM only communicates these results.
        """
        if intent not in (
            IntentType.TRAIN_INFORMATION,
            IntentType.STATION_INFORMATION,
            IntentType.KNOWLEDGE_QUERY,
            IntentType.COMPARISON,
            IntentType.RECOMMENDATION,
            IntentType.ROUTE_CONTEXT_QA,
            IntentType.ROUTE_EXPLANATION,
            IntentType.FOLLOW_UP,
        ):
            return None

        # Build a minimal context for the orchestrator
        journey = session_manager.get_current_journey()

        class _RailwayCtx:
            def __init__(self):
                self.current_journey = journey
                self.comparison_result = comparison_result
                self.recommendation_result = recommendation_result

        ctx = _RailwayCtx()

        data = railway_intelligence.process(intent, query, ctx)

        if data:
            logger.info(
                "[RAILWAY_INTELLIGENCE] Computed: intent=%s fields=%s",
                intent.value, list(data.keys()),
            )
        return data

    # ------------------------------------------------------------------
    # Phase 3 — Comparative Reasoning
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_comparison(
        query: str,
        intent: IntentType,
    ) -> ComparisonResult | None:
        """Compute comparison between routes/items when the user asks.

        Currently returns None since multi-route data is not yet stored.
        This serves as the foundation for Phase 4.
        """
        if intent != IntentType.COMPARISON:
            return None

        # Placeholder — Phase 4 will use actual route data from session
        return ComparisonResult(
            items=[],
            criteria_used=["duration"],
        )

    # ------------------------------------------------------------------
    # Structured logging (Phase 3 — added state, ref, clarification)
    # ------------------------------------------------------------------

    @staticmethod
    def _log_engine(
        intent: IntentType,
        capability: CapabilityType,
        has_journey: bool,
        needs_tools: bool,
        provider: str,
        tools_used: list[str],
        elapsed_ms: int,
        conversation_state: str = "",
        ref_type: str = "NONE",
        clarification_needed: bool = False,
        railway_intel: str = "",
    ) -> None:
        """Emit structured debug log for the full pipeline."""
        logger.info(
            "[ENGINE] intent=%s | capability=%s | state=%s | ref=%s | clarify=%s "
            "| journey=%s | needs_tools=%s | provider=%s | tools=%s | railway=%s | elapsed=%dms",
            intent.value,
            capability.value,
            conversation_state,
            ref_type,
            clarification_needed,
            has_journey,
            needs_tools,
            provider,
            tools_used or [],
            railway_intel,
            elapsed_ms,
        )


engine = ConversationIntelligenceEngine()
