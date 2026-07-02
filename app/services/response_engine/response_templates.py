"""Response Templates — structured templates for every ResponseType.

Templates receive structured objects. Templates never receive raw prompts.
"""

import random
from typing import Any

from app.models.conversation import (
    ComparisonResult,
    ComparisonResultExtended,
    Explanation,
    JourneyInsights,
    RailwayKnowledge,
    RecommendationResult,
    RouteInsights,
    StationProfile,
    TrainProfile,
)
from app.models.journey_context import PersistentJourneyContext

from app.services.response_engine.personality import TransitIQPersonality
from app.services.response_engine.markdown_formatter import MarkdownFormatter


class ResponseTemplates:
    """Collection of template methods, one per ResponseType."""

    @staticmethod
    def greeting() -> str:
        greeting = random.choice(TransitIQPersonality.GREETING_VARIATIONS)
        return f"{greeting} How can I help you today?"

    @staticmethod
    def help_text() -> str:
        return (
            f"I can help you with:\n\n"
            f"**Journey Planning** — Tell me where you want to go "
            f"(e.g., *From Valliyur to Nanguneri*)\n"
            f"**Station Information** — Ask about stations "
            f"(e.g., *What stations are near Chennai?*)\n"
            f"**Train Details** — Look up train profiles "
            f"(e.g., *Train 12601 details*)\n"
            f"**Railway Knowledge** — Ask about RAC, Tatkal, waitlist, etc.\n"
            f"**Route Details** — Once you have a route, ask about stops, "
            f"timing, transfers\n"
            f"**Multi-Modal Transport** — Combine rail, bus, metro, and ferry\n\n"
            f"What would you like to know?"
        )

    @staticmethod
    def small_talk() -> str:
        return (
            "I'm doing great, thanks for asking! I'm here to help with "
            "your railway travel. Is there a journey I can help you plan?"
        )

    @staticmethod
    def journey_summary(journey: PersistentJourneyContext | None) -> str:
        if not journey:
            return (
                "I don't have an active journey to summarize. "
                "Tell me where you'd like to go and I'll plan a route for you."
            )
        lines = [f"**{journey.origin} → {journey.destination}**"]
        lines.append("")
        lines.append(f"🚆 **Train:** {journey.train_name} ({journey.train_number})")
        lines.append(f"🕐 **Departure:** {journey.departure_time}")
        lines.append(f"🕐 **Arrival:** {journey.arrival_time}")
        lines.append(f"⏱ **Duration:** {journey.duration} minutes")
        if journey.transfer_count > 0:
            lines.append(f"🔄 **Transfers:** {journey.transfer_count}")
        if journey.intermediate_stops:
            count = len(journey.intermediate_stops)
            lines.append(f"📍 **Stops en route:** {count} intermediate stops")
        return "\n".join(lines)

    @staticmethod
    def station_profile(
        station: StationProfile | None,
        station_results: list[dict] | None = None,
    ) -> str:
        if station:
            parts = [f"**{station.station_name} ({station.station_code})**"]
            parts.append("")
            if station.is_junction:
                parts.append("🔀 **Junction station** — connects multiple routes")
            if station.is_terminal:
                parts.append("🏁 **Terminal station** — trains originate/terminate here")
            if station.is_major_station:
                parts.append("⭐ **Major station** — significant railway hub")
            if station.estimated_platform_count:
                parts.append(f"**Platforms:** approximately {station.estimated_platform_count}")
            if station.connecting_routes:
                parts.append(f"**Connecting routes:** {len(station.connecting_routes)}")
            if station.zone:
                parts.append(f"**Zone:** {station.zone}")
            return "\n".join(parts)

        if station_results and len(station_results) > 0:
            parts = [f"Found **{len(station_results)}** matching station(s):"]
            parts.append("")
            for sr in station_results[:5]:
                name = sr.get("stop_name", "?")
                sid = sr.get("stop_id", "?")
                parts.append(f"• **{name}** ({sid})")
            return "\n".join(parts)

        return "I couldn't find any stations matching your query."

    @staticmethod
    def train_profile(train: TrainProfile | None) -> str:
        if not train:
            return "I couldn't find information for that train."
        parts = [f"**{train.train_name} ({train.train_number})**"]
        parts.append("")
        if train.train_type:
            parts.append(f"**Type:** {train.train_type}")
        if train.service_category:
            parts.append(f"**Category:** {train.service_category}")
        if train.duration_min:
            parts.append(f"⏱ **Duration:** {train.duration_min} minutes")
        if train.distance_km:
            parts.append(f"📏 **Distance:** {train.distance_km} km")
        if train.stop_count:
            parts.append(f"📍 **Stops:** {train.stop_count}")
        if train.major_stops:
            parts.append(f"**Major stations:** {', '.join(train.major_stops[:7])}")
        if train.terminal_stations:
            parts.append(f"**Terminals:** {', '.join(train.terminal_stations)}")
        if train.operating_days:
            parts.append(f"**Runs on:** {', '.join(train.operating_days)}")
        return "\n".join(parts)

    @staticmethod
    def route_overview(journey: PersistentJourneyContext | None) -> str:
        if not journey:
            return "No route information available."
        parts = [f"🚆 **Route Overview**"]
        parts.append("")
        parts.append(f"**{journey.origin} → {journey.destination}**")
        parts.append(f"**Train:** {journey.train_name} ({journey.train_number})")
        parts.append(f"**Departure:** {journey.departure_time} → **Arrival:** {journey.arrival_time}")
        parts.append(f"**Duration:** {journey.duration} minutes")
        if journey.intermediate_stops:
            parts.append("")
            parts.append(f"**Stops on the way ({len(journey.intermediate_stops)}):**")
            for name in journey.intermediate_stops[:10]:
                parts.append(f"• {name}")
            if len(journey.intermediate_stops) > 10:
                parts.append(f"… and {len(journey.intermediate_stops) - 10} more")
        return "\n".join(parts)

    @staticmethod
    def recommendation(
        recommendation: RecommendationResult | None,
        journey: PersistentJourneyContext | None = None,
    ) -> str:
        if not recommendation or recommendation.recommended_idx < 0:
            return None

        criteria_map = {
            "duration": "shortest travel time",
            "stops": "fewest stops",
            "departure": "best departure time",
            "arrival": "earliest arrival",
        }
        criteria_text = criteria_map.get(recommendation.criteria, recommendation.criteria)
        parts = [f"I recommend this option because it offers the **{criteria_text}**."]
        if recommendation.justification:
            parts.append(recommendation.justification)
        if journey:
            parts.append("")
            parts.append(f"🚆 **{journey.train_name} ({journey.train_number})**")
            parts.append(f"**{journey.origin} → {journey.destination}**")
            parts.append(f"**Departure:** {journey.departure_time} → **Arrival:** {journey.arrival_time}")
            parts.append(f"**Duration:** {journey.duration} minutes")
        return "\n".join(parts)

    @staticmethod
    def comparison(
        comparison: ComparisonResult | ComparisonResultExtended | None,
    ) -> str:
        if not comparison:
            return None

        if isinstance(comparison, ComparisonResultExtended):
            lines = ["**Comparison Results**"]
            lines.append("")
            for row in comparison.comparison_table:
                prefix = "✓" if row.winner else ""
                lines.append(f"• **{row.attribute}:** {row.value_a} vs {row.value_b}")
            if comparison.advantages:
                lines.append("")
                lines.append(f"**Advantages:** {' • '.join(comparison.advantages[:3])}")
            if comparison.disadvantages:
                lines.append(f"**Disadvantages:** {' • '.join(comparison.disadvantages[:3])}")
            return "\n".join(lines)

        if comparison.items:
            lines = ["**Comparison Results**"]
            lines.append("")
            for i, item in enumerate(comparison.items):
                lines.append(f"**Option {i + 1}:** {item.label}")
                if item.duration_min:
                    lines.append(f"  ⏱ Duration: {item.duration_min} min")
                if item.stop_count:
                    lines.append(f"  📍 Stops: {item.stop_count}")
                if item.departure_time:
                    lines.append(f"  🕐 Departure: {item.departure_time}")
                if item.arrival_time:
                    lines.append(f"  🕐 Arrival: {item.arrival_time}")
                lines.append("")
            highlights = []
            if comparison.fastest_idx >= 0:
                highlights.append(f"⚡ Fastest: Option {comparison.fastest_idx + 1}")
            if comparison.fewest_stops_idx >= 0:
                highlights.append(f"📍 Fewest stops: Option {comparison.fewest_stops_idx + 1}")
            if highlights:
                lines.extend(highlights)
            return "\n".join(lines)

        return None

    @staticmethod
    def route_explanation(
        explanation: Explanation | None,
        journey: PersistentJourneyContext | None = None,
    ) -> str:
        if not explanation:
            return None
        parts = [explanation.reason]
        if explanation.details:
            parts.append("")
            for d in explanation.details[:4]:
                parts.append(f"• {d}")
        if explanation.suggestion:
            parts.append("")
            parts.append(f"💡 {explanation.suggestion}")
        return "\n".join(parts)

    @staticmethod
    def schedule_info(journey: PersistentJourneyContext | None) -> str:
        if not journey:
            return "I don't have schedule information available."
        parts = [
            f"**Schedule for {journey.train_name} ({journey.train_number})**",
            "",
            f"**Departure:** {journey.departure_time} from {journey.origin}",
            f"**Arrival:** {journey.arrival_time} at {journey.destination}",
            f"**Duration:** {journey.duration} minutes",
        ]
        return "\n".join(parts)

    @staticmethod
    def journey_insight(insights: JourneyInsights | None) -> str:
        if not insights:
            return None
        flags = []
        if insights.is_overnight: flags.append("🌙 This is an **overnight** journey")
        if insights.is_daytime: flags.append("☀️ This is a **daytime** journey")
        if insights.is_long_journey: flags.append("⏱ This is a **long journey**")
        if insights.is_short_trip: flags.append("📍 This is a **short trip**")
        if insights.requires_transfer: flags.append("🔄 **Requires a transfer**")
        if insights.tight_connection: flags.append("⚠️ **Tight connection** — be mindful of transfer time")
        if insights.comfortable_connection: flags.append("✅ **Comfortable connection** — ample transfer time")
        if insights.many_stops: flags.append("📌 **Many stops** along the route")
        if insights.express_trip: flags.append("⚡ **Express trip** — limited stops")
        if not flags:
            return None
        parts = ["**Journey Insights**", ""]
        parts.extend(flags)
        return "\n".join(parts)

    @staticmethod
    def knowledge_answer(knowledge: RailwayKnowledge | None) -> str:
        if not knowledge:
            return None
        parts = [f"**{knowledge.topic}**"]
        parts.append("")
        parts.append(knowledge.answer)
        return "\n".join(parts)

    @staticmethod
    def clarification_question(question: str) -> str:
        return question

    @staticmethod
    def error_message(message: str = "") -> str:
        if message:
            return f"I encountered an issue: {message} Please try again or rephrase your query."
        return (
            "I'm sorry, I couldn't process that request. "
            "Please try again or ask for help to see what I can do."
        )

    @staticmethod
    def no_journey() -> str:
        return (
            "I don't see an active journey in your session. "
            "Would you like to plan a new trip? Just tell me your destination!"
        )

    @staticmethod
    def goodbye() -> str:
        return (
            "Goodbye! Safe travels. Feel free to come back anytime "
            "for help with your journeys."
        )
