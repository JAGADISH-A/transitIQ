"""Deterministic explanation engine.

Produces structured explanations for railway scenarios without LLM.
"""

import logging
from typing import Any

from app.models.conversation import Explanation

logger = logging.getLogger(__name__)


class ExplanationEngine:
    """Generate structured explanations for railway scenarios."""

    def explain_no_trains(self, source: str = "", destination: str = "") -> Explanation:
        """Explain why no trains were found between two stops."""
        reason = "No direct or connecting trains were found"
        details = [
            f"No train services between {source} and {destination} in the current data.",
            "Possible reasons: different railway zones, no shared routes, or no common interchange stations.",
        ]
        suggestion = "Try a different pair of stations or check if both stations are served by the same railway network."

        if source and destination:
            reason = f"No trains available from {source} to {destination}"

        logger.info("[EXPLANATION] No trains: %s", reason)
        return Explanation(reason=reason, details=details, suggestion=suggestion)

    def explain_transfer(self, transfer_stop: str = "", reason: str = "") -> Explanation:
        """Explain why a transfer is required."""
        details = [
            f"Transfer at {transfer_stop}." if transfer_stop else "A transfer is required.",
            "No single direct train connects both stations.",
        ]
        if not reason:
            reason = "A transfer is required because there is no direct train service"
        suggestion = (
            "Check the transfer time at the interchange station to ensure a comfortable connection."
        )

        logger.info("[EXPLANATION] Transfer: %s", reason)
        return Explanation(reason=reason, details=details, suggestion=suggestion)

    def explain_slower(self, slower_min: int = 0, faster_min: int = 0) -> Explanation:
        """Explain why one option is slower."""
        diff = slower_min - faster_min
        reason = f"This option is {diff} minutes slower"
        details = [
            f"Travel time: {slower_min} min vs {faster_min} min for the faster option.",
        ]
        if diff >= 60:
            details.append(
                f"The difference of {diff} minutes may be significant for time-sensitive travel."
            )
        suggestion = "Consider the faster option if arrival time is a priority."

        logger.info("[EXPLANATION] Slower: diff=%d min", diff)
        return Explanation(reason=reason, details=details, suggestion=suggestion)

    def explain_longer(self, longer_stops: int = 0, shorter_stops: int = 0) -> Explanation:
        """Explain why one option has more stops."""
        diff = longer_stops - shorter_stops
        reason = f"This option has {diff} more stops"
        details = [
            f"Number of stops: {longer_stops} vs {shorter_stops} for the shorter option.",
        ]
        if diff >= 10:
            details.append(
                "More stops typically means longer travel time and more frequent station arrivals."
            )
        suggestion = "Choose the option with fewer stops for a faster journey."

        logger.info("[EXPLANATION] Longer stops: diff=%d", diff)
        return Explanation(reason=reason, details=details, suggestion=suggestion)

    def explain_recommended(
        self,
        reason: str = "",
        criteria: str = "",
    ) -> Explanation:
        """Explain why a particular option is recommended."""
        if not reason:
            reason = "This option is recommended based on overall travel efficiency"
        details = [
            f"Selection criteria: {criteria}." if criteria else "",
            "The recommended option balances travel time, stops, and convenience.",
        ]
        suggestion = "Proceed with this option for the best travel experience."

        logger.info("[EXPLANATION] Recommended: criteria=%s", criteria)
        return Explanation(reason=reason, details=[d for d in details if d], suggestion=suggestion)

    def explain_tight_connection(self, wait_min: int = 0) -> Explanation:
        """Explain a tight connection situation."""
        reason = f"Connection time of {wait_min} minutes may be tight"
        details = [
            f"Available transfer time: {wait_min} minutes.",
            "A minimum of 10 minutes is recommended for platform changes.",
        ]
        if wait_min < 5:
            details.append(
                "This connection is very tight and you may risk missing the connecting train."
            )
        suggestion = "Consider an earlier arrival or a longer buffer between connections."

        logger.info("[EXPLANATION] Tight connection: wait=%d min", wait_min)
        return Explanation(reason=reason, details=details, suggestion=suggestion)


explanation_engine = ExplanationEngine()
