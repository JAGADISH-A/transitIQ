"""Lightweight in-memory session manager.

Phase 1 uses a simple in-memory implementation. Future phases may
replace this with Redis, a database, or an auth-backed session store
without changing the public interface.

Phase 2 extends this with conversation memory:
  - conversation history (list of turns)
  - last intent, capability, tools used
  - last assistant reply
  - session start timestamp
"""

from datetime import datetime

from app.models.journey_context import PersistentJourneyContext
from app.models.conversation import ConversationTurn


class SessionManager:
    """Manages the current user's active journey context and conversation state.

    All existing Phase 1 methods remain unchanged.
    Phase 2 additions are clearly separated below.
    """

    def __init__(self) -> None:
        self._current_journey: PersistentJourneyContext | None = None
        self._last_question: str | None = None

        # --- Phase 2: Conversation memory ---
        self._conversation_history: list[ConversationTurn] = []
        self._last_assistant_reply: str | None = None
        self._last_user_message: str | None = None
        self._last_intent: str | None = None
        self._last_capability: str | None = None
        self._last_successful_tool: str | None = None
        self._session_started_at: str | None = None

        # --- Phase 3: Conversation state ---
        self._current_state: str | None = None
        self._conversation_summary: str | None = None
        self._summary_timestamp: str | None = None

        # --- Phase 3: Selected entities ---
        self._selected_train: str | None = None
        self._selected_train_number: str | None = None
        self._selected_station: str | None = None
        self._selected_route_idx: int | None = None
        self._selected_comparison_entity: str | None = None

        # --- Phase 3: Last tool result ---
        self._last_tool_result: dict | None = None

        # --- Phase 3: Resolved reference ---
        self._resolved_reference_type: str | None = None
        self._resolved_reference_value: str | None = None

    # ------------------------------------------------------------------
    # Journey lifecycle (Phase 1 — unchanged)
    # ------------------------------------------------------------------

    def set_current_journey(self, journey: PersistentJourneyContext) -> None:
        """Store the active journey context."""
        self._current_journey = journey

    def get_current_journey(self) -> PersistentJourneyContext | None:
        """Return the stored journey context, or None."""
        return self._current_journey

    def has_active_journey(self) -> bool:
        """Return True when a journey context is available."""
        return self._current_journey is not None

    def clear_current_journey(self) -> None:
        """Remove the stored journey context."""
        self._current_journey = None

    # ------------------------------------------------------------------
    # Conversation state (Phase 1 — unchanged)
    # ------------------------------------------------------------------

    def update_last_question(self, question: str) -> None:
        """Record the user's most recent question."""
        self._last_question = question

    def get_last_question(self) -> str | None:
        """Return the user's most recent question, or None."""
        return self._last_question

    # ------------------------------------------------------------------
    # Conversation memory (Phase 2)
    #
    # Public interface designed for future Redis / DB migration:
    #   - Callers never access private fields directly.
    #   - Replacing in-memory storage requires only updating this class.
    # ------------------------------------------------------------------

    def add_turn(self, role: str, content: str) -> None:
        """Append a conversation turn to the history."""
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        self._conversation_history.append(turn)

    def get_history(self, limit: int = 10) -> list[ConversationTurn]:
        """Return the most recent conversation turns (newest last)."""
        return self._conversation_history[-limit:] if self._conversation_history else []

    def clear_history(self) -> None:
        """Remove all conversation history."""
        self._conversation_history = []

    def set_last_assistant_reply(self, reply: str) -> None:
        """Record the last assistant response."""
        self._last_assistant_reply = reply

    def get_last_assistant_reply(self) -> str | None:
        """Return the last assistant response, or None."""
        return self._last_assistant_reply

    def set_last_user_message(self, message: str) -> None:
        """Record the last user message."""
        self._last_user_message = message

    def get_last_user_message(self) -> str | None:
        """Return the last user message, or None."""
        return self._last_user_message

    def set_last_intent(self, intent: str) -> None:
        """Record the last classified intent."""
        self._last_intent = intent

    def get_last_intent(self) -> str | None:
        """Return the last classified intent, or None."""
        return self._last_intent

    def set_last_capability(self, capability: str) -> None:
        """Record the last capability used."""
        self._last_capability = capability

    def get_last_capability(self) -> str | None:
        """Return the last capability used, or None."""
        return self._last_capability

    def set_last_successful_tool(self, tool: str | None) -> None:
        """Record the last tool that was successfully invoked."""
        self._last_successful_tool = tool

    def get_last_successful_tool(self) -> str | None:
        """Return the last successful tool name, or None."""
        return self._last_successful_tool

    def initialize_session(self) -> None:
        """Mark the session as started (idempotent)."""
        if self._session_started_at is None:
            self._session_started_at = datetime.utcnow().isoformat() + "Z"

    def get_session_started_at(self) -> str | None:
        """Return when the session began, or None."""
        return self._session_started_at

    # ------------------------------------------------------------------
    # Phase 3: Conversation State
    # ------------------------------------------------------------------

    def set_current_state(self, state: str) -> None:
        self._current_state = state

    def get_current_state(self) -> str | None:
        return self._current_state

    # ------------------------------------------------------------------
    # Phase 3: Conversation Summary
    # ------------------------------------------------------------------

    def set_conversation_summary(self, summary: str) -> None:
        self._conversation_summary = summary
        self._summary_timestamp = datetime.utcnow().isoformat() + "Z"

    def get_conversation_summary(self) -> str:
        return self._conversation_summary or ""

    def get_summary_timestamp(self) -> str | None:
        return self._summary_timestamp

    # ------------------------------------------------------------------
    # Phase 3: Selected Entities
    # ------------------------------------------------------------------

    def set_selected_train(self, train_name: str | None, train_number: str | None = None) -> None:
        self._selected_train = train_name
        if train_number:
            self._selected_train_number = train_number

    def get_selected_train(self) -> str | None:
        return self._selected_train

    def get_selected_train_number(self) -> str | None:
        return self._selected_train_number

    def set_selected_station(self, station: str | None) -> None:
        self._selected_station = station

    def get_selected_station(self) -> str | None:
        return self._selected_station

    def set_selected_route_idx(self, idx: int | None) -> None:
        self._selected_route_idx = idx

    def get_selected_route_idx(self) -> int | None:
        return self._selected_route_idx

    def set_selected_comparison_entity(self, entity_type: str | None) -> None:
        self._selected_comparison_entity = entity_type

    def get_selected_comparison_entity(self) -> str | None:
        return self._selected_comparison_entity

    # ------------------------------------------------------------------
    # Phase 3: Last Tool Result
    # ------------------------------------------------------------------

    def set_last_tool_result(self, result: dict | None) -> None:
        self._last_tool_result = result

    def get_last_tool_result(self) -> dict | None:
        return self._last_tool_result

    # ------------------------------------------------------------------
    # Phase 3: Resolved Reference
    # ------------------------------------------------------------------

    def set_resolved_reference(self, ref_type: str | None = None, ref_value: str | None = None) -> None:
        self._resolved_reference_type = ref_type
        self._resolved_reference_value = ref_value

    def get_resolved_reference_type(self) -> str | None:
        return self._resolved_reference_type

    def get_resolved_reference_value(self) -> str | None:
        return self._resolved_reference_value


session_manager = SessionManager()
