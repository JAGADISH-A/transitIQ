"""Explanation Builder — converts backend reasoning into natural explanations.

No LLM required. All explanations are assembled from structured data.
"""

from typing import Any

from app.models.conversation import (
    ComparisonResult,
    ComparisonResultExtended,
    Explanation,
    RecommendationResult,
)


class ExplanationBuilder:
    """Build natural-language explanations from backend-computed data."""

    @staticmethod
    def build_recommendation_explanation(
        recommendation: RecommendationResult | None,
        context: dict[str, Any] | None = None,
    ) -> Explanation | None:
        if not recommendation or recommendation.recommended_idx < 0:
            return None

        criteria_phrases = {
            "duration": "the shortest travel time",
            "stops": "fewer scheduled stops",
            "departure": "the best departure time",
            "arrival": "the earliest arrival",
        }
        criteria_text = criteria_phrases.get(
            recommendation.criteria, f"the best {recommendation.criteria}"
        )

        details = []
        if recommendation.justification:
            details.append(recommendation.justification)

        suggestion = (
            "Would you like to know more about this option or compare it with another?"
        )

        return Explanation(
            reason=f"I recommend this option because it offers {criteria_text}.",
            details=details,
            suggestion=suggestion,
        )

    @staticmethod
    def build_comparison_explanation(
        comparison: ComparisonResult | ComparisonResultExtended | None,
    ) -> Explanation | None:
        if not comparison:
            return None

        if isinstance(comparison, ComparisonResultExtended):
            advantages = comparison.advantages[:3] if comparison.advantages else []
            disadvantages = comparison.disadvantages[:3] if comparison.disadvantages else []

            details = []
            if advantages:
                details.append(f"Advantages: {'; '.join(advantages)}")
            if disadvantages:
                details.append(f"Trade-offs: {'; '.join(disadvantages)}")

            reason = f"Between these options, {comparison.winner} comes out ahead."
            suggestion = "Would you like to explore one of these options further?"

            return Explanation(
                reason=reason,
                details=details,
                suggestion=suggestion,
            )

        if comparison.items and len(comparison.items) >= 2:
            fastest = comparison.fastest_idx
            fewest = comparison.fewest_stops_idx
            earliest = comparison.earliest_arrival_idx

            details = []
            if fastest >= 0:
                a = comparison.items[fastest]
                details.append(f"Option {fastest + 1} ({a.label}) is the fastest at {a.duration_min} min")
            if fewest >= 0 and fewest != fastest:
                b = comparison.items[fewest]
                details.append(f"Option {fewest + 1} ({b.label}) has the fewest stops ({b.stop_count})")
            if earliest >= 0 and earliest not in (fastest, fewest):
                c = comparison.items[earliest]
                details.append(f"Option {earliest + 1} ({c.label}) arrives earliest at {c.arrival_time}")

            reason = "Here's how these options compare across key factors."
            if details:
                reason = f"Based on the comparison, each option has different strengths."

            suggestion = "Would you like more details on any of these options?"

            return Explanation(
                reason=reason,
                details=details,
                suggestion=suggestion,
            )

        return None

    @staticmethod
    def build_journey_explanation(
        duration: int | None = None,
        stop_count: int | None = None,
        is_overnight: bool = False,
        is_direct: bool = True,
        transfer_count: int = 0,
    ) -> Explanation | None:
        reasons = []
        details = []

        if is_direct and transfer_count == 0:
            reasons.append("This is a direct journey with no transfers needed.")
        elif transfer_count > 0:
            reasons.append(f"This journey requires {transfer_count} transfer(s).")
            details.append("You'll need to change trains at the connecting station.")

        if is_overnight:
            reasons.append("It's an overnight journey, so you can travel while you sleep.")
            details.append("Consider booking a sleeper berth for comfort.")

        if duration:
            if duration > 480:
                details.append(f"At {duration} minutes, this is a long-distance journey.")
            elif duration > 120:
                details.append(f"The journey takes about {duration} minutes.")
            else:
                details.append(f"A relatively short journey at {duration} minutes.")

        if not reasons:
            return None

        return Explanation(
            reason=" ".join(reasons),
            details=details,
            suggestion="Would you like more information about the stops or schedule?",
        )

    @staticmethod
    def build_transfer_explanation(transfer_count: int = 0) -> Explanation | None:
        if transfer_count <= 0:
            return None

        details = []
        if transfer_count == 1:
            reason = "This journey includes one transfer. You'll need to change trains at the connecting station."
        else:
            reason = f"This journey includes {transfer_count} transfers."

        details.append("Transfer stations are noted in the stop sequence above.")
        details.append("Make sure to allow enough time between connections.")

        return Explanation(
            reason=reason,
            details=details,
            suggestion="I can show you the full transfer details if you'd like.",
        )
