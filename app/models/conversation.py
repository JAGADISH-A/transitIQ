"""Conversation models for the Conversation Intelligence Engine."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel

from app.models.journey_context import PersistentJourneyContext
from app.models.transit import TransportMode, TransportPreference


# ---------------------------------------------------------------------------
# Intent types (Part 3)
# ---------------------------------------------------------------------------

class IntentType(str, Enum):
    """Backend-classified intent types for the conversation engine."""

    NEW_JOURNEY = "NEW_JOURNEY"
    FOLLOW_UP = "FOLLOW_UP"
    STATION_INFORMATION = "STATION_INFORMATION"
    TRAIN_INFORMATION = "TRAIN_INFORMATION"
    SCHEDULE_QUERY = "SCHEDULE_QUERY"
    ROUTE_EXPLANATION = "ROUTE_EXPLANATION"
    ROUTE_CONTEXT_QA = "ROUTE_CONTEXT_QA"
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
    SMALL_TALK = "SMALL_TALK"
    GREETING = "GREETING"
    HELP = "HELP"
    COMPARISON = "COMPARISON"
    RECOMMENDATION = "RECOMMENDATION"
    BOOKING = "BOOKING"
    MODAL_FILTER = "MODAL_FILTER"
    MULTI_MODAL_QUERY = "MULTI_MODAL_QUERY"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Capability types (Part 4)
# ---------------------------------------------------------------------------

class CapabilityType(str, Enum):
    """Backend capabilities that the engine can invoke."""

    CONVERSATION = "CONVERSATION"
    JOURNEY_CONTEXT = "JOURNEY_CONTEXT"
    JOURNEY_PLANNING = "JOURNEY_PLANNING"
    STATION = "STATION"
    SCHEDULE = "SCHEDULE"
    KNOWLEDGE = "KNOWLEDGE"
    RAILWAY_INTELLIGENCE = "RAILWAY_INTELLIGENCE"
    MULTI_MODAL = "MULTI_MODAL"
    FALLBACK = "FALLBACK"


# ---------------------------------------------------------------------------
# Reasoning strategy (Part 9)
# ---------------------------------------------------------------------------

class ReasoningStrategy(str, Enum):
    """What kind of processing the question requires."""

    JOURNEY_CONTEXT_ONLY = "JOURNEY_CONTEXT_ONLY"
    CONVERSATION_MEMORY = "CONVERSATION_MEMORY"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"
    BACKEND_TOOL = "BACKEND_TOOL"
    LLM_ONLY = "LLM_ONLY"
    COMPARISON = "COMPARISON"
    RECOMMENDATION = "RECOMMENDATION"
    EXPLANATION = "EXPLANATION"
    MULTI_MODAL = "MULTI_MODAL"
    MODAL_FILTER = "MODAL_FILTER"


# ---------------------------------------------------------------------------
# Conversation turn (Part 5)
# ---------------------------------------------------------------------------

class ConversationTurn(BaseModel):
    """A single exchange in the conversation history."""

    role: str
    content: str
    timestamp: str


# ---------------------------------------------------------------------------
# Conversation State (Phase 3)
# ---------------------------------------------------------------------------

class ConversationState(str, Enum):
    """Deterministic conversation state for the engine.

    State transitions are computed entirely in the backend.
    The LLM never decides or modifies conversation state.
    """

    NO_CONTEXT = "NO_CONTEXT"
    JOURNEY_ACTIVE = "JOURNEY_ACTIVE"
    ROUTES_FOUND = "ROUTES_FOUND"
    TRAIN_SELECTED = "TRAIN_SELECTED"
    DISCUSSING_ROUTE = "DISCUSSING_ROUTE"
    DISCUSSING_STATION = "DISCUSSING_STATION"
    DISCUSSING_TIMINGS = "DISCUSSING_TIMINGS"
    DISCUSSING_EXPLANATION = "DISCUSSING_EXPLANATION"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    GENERAL_CHAT = "GENERAL_CHAT"


# ---------------------------------------------------------------------------
# Reference Resolution (Phase 3)
# ---------------------------------------------------------------------------

class ReferenceType(str, Enum):
    """Types of references the resolver can detect."""

    PRONOUN = "PRONOUN"
    ORDINAL = "ORDINAL"
    COMPARATIVE = "COMPARATIVE"
    TEMPORAL = "TEMPORAL"
    LOCATIVE = "LOCATIVE"
    POSSESSIVE = "POSSESSIVE"
    ELLIPSIS = "ELLIPSIS"
    NONE = "NONE"


class ResolvedReference(BaseModel):
    """A resolved reference from the user's query."""

    type: ReferenceType = ReferenceType.NONE
    value: str | None = None
    confidence: float = 0.0
    source: str = ""


# ---------------------------------------------------------------------------
# Conversation Summary (Phase 3)
# ---------------------------------------------------------------------------

class ConversationSummary(BaseModel):
    """Compressed summary of older conversation turns."""

    summary_text: str = ""
    journey_context: str = ""
    important_decisions: list[str] = []
    unresolved_questions: list[str] = []
    selected_train: str | None = None
    selected_station: str | None = None
    last_intent: str | None = None
    turn_count: int = 0
    created_at: str = ""


# ---------------------------------------------------------------------------
# Missing Information Detection (Phase 3)
# ---------------------------------------------------------------------------

class MissingInfoType(str, Enum):
    """Types of missing information the clarification engine can detect."""

    NONE = "NONE"
    DESTINATION = "DESTINATION"
    ORIGIN = "ORIGIN"
    DATE = "DATE"
    TIME = "TIME"
    TRAIN = "TRAIN"
    TRAIN_CLASS = "TRAIN_CLASS"
    STATION = "STATION"
    COMPARISON_TARGET = "COMPARISON_TARGET"
    AMBIGUOUS_QUANTITY = "AMBIGUOUS_QUANTITY"
    SEAT_TYPE = "SEAT_TYPE"
    JOURNEY = "JOURNEY"


class Clarification(BaseModel):
    """A structured clarification request."""

    needed: bool = False
    missing_type: MissingInfoType = MissingInfoType.NONE
    question: str = ""
    context_hint: str = ""


# ---------------------------------------------------------------------------
# Comparison & Recommendation (Phase 3)
# ---------------------------------------------------------------------------

class ComparisonItem(BaseModel):
    """An item in a comparison result."""

    label: str
    duration_min: int = 0
    stop_count: int = 0
    departure_time: str = ""
    arrival_time: str = ""
    train_name: str = ""
    train_number: str = ""


class ComparisonResult(BaseModel):
    """Backend-computed comparison between two or more items."""

    items: list[ComparisonItem] = []
    fastest_idx: int = -1
    fewest_stops_idx: int = -1
    earliest_arrival_idx: int = -1
    latest_departure_idx: int = -1
    criteria_used: list[str] = []


class RecommendationResult(BaseModel):
    """Backend-computed recommendation reasoning."""

    recommended_idx: int = -1
    criteria: str = ""
    justification: str = ""


# ---------------------------------------------------------------------------
# Phase 4 — Railway Intelligence Models
# ---------------------------------------------------------------------------

class TrainProfile(BaseModel):
    """Deterministic analysis of a train's characteristics."""

    train_number: str = ""
    train_name: str = ""
    train_type: str = ""
    service_category: str = ""
    average_speed: float | None = None
    distance_km: int | None = None
    duration_min: int | None = None
    operating_days: list[str] = []
    major_stops: list[str] = []
    terminal_stations: list[str] = []
    stop_count: int = 0
    is_superfast: bool = False
    is_express: bool = False


class StationProfile(BaseModel):
    """Deterministic analysis of a railway station."""

    station_code: str = ""
    station_name: str = ""
    is_junction: bool = False
    is_terminal: bool = False
    is_major_station: bool = False
    is_interchange: bool = False
    estimated_platform_count: int | None = None
    connecting_routes: list[str] = []
    zone: str = ""
    latitude: float | None = None
    longitude: float | None = None


class JourneyInsights(BaseModel):
    """Rule-based travel insights for a journey."""

    is_overnight: bool = False
    is_daytime: bool = False
    is_long_journey: bool = False
    is_short_trip: bool = False
    requires_transfer: bool = False
    tight_connection: bool = False
    comfortable_connection: bool = False
    many_stops: bool = False
    express_trip: bool = False


class RouteInsights(BaseModel):
    """Deterministic route classification."""

    route_type: str = ""  # direct, transfer, circular
    service_scope: str = ""  # long-distance, regional, intercity, suburban
    stop_count: int = 0
    transfer_count: int = 0
    duration_min: int | None = None
    distance_km: float | None = None
    major_junctions: list[str] = []


class ComparisonTable(BaseModel):
    """A row in a comparison table."""

    attribute: str
    value_a: str = ""
    value_b: str = ""
    winner: str = ""  # "a", "b", or "tie"


class ComparisonResultExtended(BaseModel):
    """Extended comparison with table and structured reasoning."""

    winner: str = ""
    comparison_table: list[ComparisonTable] = []
    advantages: list[str] = []
    disadvantages: list[str] = []


class Explanation(BaseModel):
    """Structured explanation from the backend."""

    reason: str = ""
    details: list[str] = []
    suggestion: str = ""


class RailwayKnowledge(BaseModel):
    """Curated railway knowledge answer."""

    topic: str = ""
    answer: str = ""
    category: str = ""


# ---------------------------------------------------------------------------
# Conversation Context (Part 1, extended Phase 3)
# ---------------------------------------------------------------------------

class ConversationContext(BaseModel):
    """Structured context object assembled for every AI request.

    The PromptBuilder converts this object into prompt text.
    No other code should manipulate prompt strings directly.
    """

    current_journey: PersistentJourneyContext | None = None
    conversation_history: list[ConversationTurn] = []
    last_question: str | None = None
    current_time: str
    current_feed: str | None = None
    selected_route: dict | None = None
    user_query: str
    intent: IntentType
    intent_confidence: float = 1.0
    capability: CapabilityType | None = None
    reasoning_strategy: ReasoningStrategy = ReasoningStrategy.LLM_ONLY
    available_tools: list[str] = []
    knowledge_context: str | None = None
    system_context: str | None = None
    capability_result: dict | None = None
    needs_tools: bool = False

    # --- Phase 3 fields ---
    conversation_state: str = "NO_CONTEXT"
    resolved_reference: ResolvedReference = ResolvedReference()
    conversation_summary: ConversationSummary = ConversationSummary()
    clarification: Clarification = Clarification()
    comparison_result: ComparisonResult | None = None
    recommendation_result: RecommendationResult | None = None
    missing_info_type: MissingInfoType = MissingInfoType.NONE

    # --- Phase 4 — Railway Intelligence fields ---
    train_profile: "TrainProfile | None" = None
    station_profile: "StationProfile | None" = None
    journey_insights: "JourneyInsights | None" = None
    route_insights: "RouteInsights | None" = None
    comparison_extended: "ComparisonResultExtended | None" = None
    explanation: "Explanation | None" = None
    railway_knowledge: "RailwayKnowledge | None" = None

    # --- Phase 5 — Multi-modal transport fields ---
    transport_preference: "TransportPreference | None" = None
    available_providers: list[dict] = []
    multi_modal_journeys: list[dict] = []
    transport_mode_context: list[str] = []
