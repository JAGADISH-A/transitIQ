"""Curated railway knowledge engine.

Answers static railway questions using backend knowledge without LLM.
All knowledge is curated and deterministic.
"""

import logging
import re
from typing import Any

from app.models.conversation import RailwayKnowledge

logger = logging.getLogger(__name__)


class KnowledgeEngine:
    """Answer railway knowledge questions using curated backend data."""

    _KNOWLEDGE_BASE: dict[str, dict[str, str]] = {
        "rac": {
            "answer": (
                "RAC (Reservation Against Cancellation) is a confirmed but shared berth. "
                "You get a seat number but may have to share the berth (3 passengers share 2 berths). "
                "RAC tickets are boarded and travel on the train. Once confirmed, you get a full berth."
            ),
            "category": "Reservation",
        },
        "wl": {
            "answer": (
                "WL (Waitlist) means your ticket is on the waiting list. "
                "You do NOT have a confirmed berth. If cancellations happen before chart preparation, "
                "you move up the waitlist and may get confirmed. If still waitlisted after charting, "
                "you cannot board the train. The ticket is fully refundable if not confirmed."
            ),
            "category": "Reservation",
        },
        "gnwl": {
            "answer": (
                "GNWL (General Waitlist) is the standard waitlist for general quota tickets. "
                "Passengers from any station can be on GNWL. It has higher priority than PQWL "
                "and moves faster as cancellations occur across all stations."
            ),
            "category": "Waitlist",
        },
        "pqwl": {
            "answer": (
                "PQWL (Pooled Quota Waitlist) is the waitlist for tickets booked from intermediate "
                "stations (not originating stations). PQWL has lower priority than GNWL. "
                "Cancellations from intermediate stations are fewer, so PQWL moves slower."
            ),
            "category": "Waitlist",
        },
        "rlwl": {
            "answer": (
                "RLWL (Remote Location Waitlist) is for tickets booked from remote or non-terminal "
                "stations. It has its own quota and priority. RLWL passengers may not get confirmed "
                "as easily as GNWL passengers."
            ),
            "category": "Waitlist",
        },
        "tqwl": {
            "answer": (
                "TQWL (Tatkal Quota Waitlist) is the waitlist specifically for Tatkal quota tickets. "
                "Tatkal bookings open one day before departure. TQWL moves only if Tatkal quota "
                "bookings are cancelled."
            ),
            "category": "Waitlist",
        },
        "tatkal": {
            "answer": (
                "Tatkal is a premium booking scheme that allows last-minute confirmed tickets "
                "at higher prices. Tatkal bookings open at 10:00 AM (AC classes) and 11:00 AM "
                "(non-AC classes) one day before the train's departure. A Tatkal charge applies "
                "on top of the base fare. Tatkal tickets are non-refundable even if waitlisted."
            ),
            "category": "Booking",
        },
        "premium tatkal": {
            "answer": (
                "Premium Tatkal is a dynamic pricing variant of Tatkal where fares increase "
                "with demand. It was introduced to prevent scalping. Premium Tatkal tickets "
                "are non-refundable and non-transferable."
            ),
            "category": "Booking",
        },
        "chart preparation": {
            "answer": (
                "Chart Preparation is the process of finalizing the passenger list and berth "
                "allocation for a train. It happens 4 hours before departure for general trains "
                "and 30 minutes before for premium trains (Rajdhani, Shatabdi, Duronto). "
                "After charting, no changes can be made to the reservation."
            ),
            "category": "Operations",
        },
        "chart": {
            "answer": (
                "Chart Preparation is the process of finalizing the passenger list and berth "
                "allocation for a train. It happens 4 hours before departure for general trains "
                "and 30 minutes before for premium trains (Rajdhani, Shatabdi, Duronto). "
                "After charting, no changes can be made to the reservation."
            ),
            "category": "Operations",
        },
        "superfast": {
            "answer": (
                "A Superfast train in Indian Railways charges a Superfast surcharge on top of "
                "the base fare. These trains typically have higher average speeds (55+ km/h) "
                "and fewer stops than Mail/Express trains. Superfast trains have numbers "
                "starting with 1 (e.g., 12001 Shatabdi, 12301 Rajdhani)."
            ),
            "category": "Classification",
        },
        "superfast surcharge": {
            "answer": (
                "Superfast surcharge is an additional fee charged on Superfast trains. "
                "It is approximately 10-30% of the base fare depending on the class. "
                "This surcharge is in addition to the base fare and any other applicable charges."
            ),
            "category": "Fares",
        },
        "express": {
            "answer": (
                "An Express train (Mail/Express) is the most common type of long-distance "
                "train in Indian Railways. Express trains typically have numbers starting "
                "with 1-4 (e.g., 12627 Karnataka Express). They stop at more stations than "
                "Superfast trains and have lower fares."
            ),
            "category": "Classification",
        },
        "passenger": {
            "answer": (
                "A Passenger train is a local or slow train that stops at almost all stations "
                "along the route. Passenger trains typically have numbers starting with 5 or 6. "
                "They are the most affordable option but take the longest time."
            ),
            "category": "Classification",
        },
        "junction": {
            "answer": (
                "A railway junction is a station where three or more railway lines meet or "
                "diverge. Junctions are important interchange points where passengers can "
                "switch trains. Examples: Chennai Central (MAS), Villupuram (VM), "
                "Madurai (MDU), Coimbatore (CBE)."
            ),
            "category": "Station Types",
        },
        "halt": {
            "answer": (
                "A halt station is a small railway station where trains stop only briefly "
                "(usually 1-2 minutes). Halts typically have minimal infrastructure and limited "
                "staff. They serve rural areas and small towns. Unlike regular stations, "
                "many express trains skip halt stations."
            ),
            "category": "Station Types",
        },
        "terminal": {
            "answer": (
                "A terminal station is where a train line ends or originates. Trains arriving "
                "at a terminal typically terminate there and may be turned around for the "
                "return journey. Examples include: Chennai Central (MAS), Mumbai CSMT, "
                "Howrah (HWH), New Delhi (NDLS)."
            ),
            "category": "Station Types",
        },
        "pantry car": {
            "answer": (
                "A pantry car is a dedicated coach in a train that serves meals to passengers. "
                "Trains with pantry cars typically have a 'P' suffix in their class codes. "
                "Pantry car services offer hot meals prepared onboard. Rajdhani, Shatabdi, "
                "Duronto, and many Superfast trains have pantry cars."
            ),
            "category": "Onboard Services",
        },
        "pnr": {
            "answer": (
                "PNR (Passenger Name Record) is a unique 10-digit number assigned to every "
                "train ticket booking in Indian Railways. You can use the PNR number to check "
                "your booking status, including confirmation status (CNF), RAC, or WL. "
                "PNR status can be checked online at IRCTC or via railway enquiry systems."
            ),
            "category": "Booking",
        },
        "platform ticket": {
            "answer": (
                "A platform ticket (also called a platform pass) allows a person to enter "
                "a railway platform without traveling. It costs about ₹10-30 depending on the "
                "station. Platform tickets are valid for 2 hours at most stations. They are "
                "purchased from the station's ticket counter."
            ),
            "category": "Station Services",
        },
        "coach position": {
            "answer": (
                "Coach position tells you the order of coaches in a train from the engine "
                "(locomotive). For example, 'Coach E1 is the 5th coach from the engine'. "
                "Knowing coach position helps you stand at the right spot on the platform "
                "while waiting for your train. Coach position varies by train and direction."
            ),
            "category": "Station Services",
        },
        "cnf": {
            "answer": (
                "CNF (Confirmed) means your ticket is confirmed and you have a specific "
                "berth/seat allocated. Confirmed tickets have a coach number and berth "
                "number (e.g., S5/43 means Sleeper class, Coach 5, Berth 43). "
                "You can board the train with a confirmed ticket."
            ),
            "category": "Reservation",
        },
    }

    def answer(self, query: str) -> RailwayKnowledge | None:
        """Answer a railway knowledge question using curated data."""
        query_lower = query.lower().strip()

        known_keys = {
            "rac": "rac",
            "waitlist": "wl",
            "wl ": "wl",
            "gnwl": "gnwl",
            "pqwl": "pqwl",
            "rlwl": "rlwl",
            "tqwl": "tqwl",
            "tatkal": "tatkal",
            "premium tatkal": "premium tatkal",
            "chart preparation": "chart preparation",
            "chart prepare": "chart preparation",
            "what is a chart": "chart",
            "superfast": "superfast",
            "super fast": "superfast",
            "super-fast": "superfast",
            "express train": "express",
            "passenger train": "passenger",
            "junction station": "junction",
            "what is a junction": "junction",
            "halt station": "halt",
            "what is a halt": "halt",
            "terminal station": "terminal",
            "pantry": "pantry car",
            "pnr": "pnr",
            "platform ticket": "platform ticket",
            "coach position": "coach position",
            "confirmed": "cnf",
            "what is cnf": "cnf",
        }

        comparison_phrases = [
            "difference between gnwl and pqwl", "gnwl vs pqwl", "pqwl vs gnwl",
            "difference between rlwl and pqwl", "rlwl vs pqwl", "pqwl vs rlwl",
            "difference between gnwl and rlwl", "gnwl vs rlwl", "rlwl vs gnwl",
        ]
        for phrase in comparison_phrases:
            if phrase in query_lower:
                return RailwayKnowledge(
                    topic="GNWL vs PQWL",
                    answer=self._get_comparison_answer("gnwl", "pqwl"),
                    category="Waitlist",
                )

        matched_key = None
        for pattern, key in known_keys.items():
            if pattern in query_lower:
                matched_key = key
                break

        if not matched_key:
            return None

        entry = self._KNOWLEDGE_BASE.get(matched_key)
        if entry is None:
            return None

        logger.info(
            "[KNOWLEDGE_ENGINE] Lookup: topic=%s category=%s",
            matched_key, entry.get("category", ""),
        )
        return RailwayKnowledge(
            topic=matched_key,
            answer=entry["answer"],
            category=entry["category"],
        )

    @staticmethod
    def _get_comparison_answer(topic_a: str, topic_b: str) -> str:
        return (
            "GNWL (General Waitlist) is for tickets from originating and major stations. "
            "It has higher priority and moves faster due to more cancellations. "
            "PQWL (Pooled Quota Waitlist) is for intermediate stations. "
            "It has lower priority and moves slower because fewer cancellations happen "
            "from intermediate stations. GNWL passengers are more likely to get confirmed "
            "than PQWL passengers."
        )


knowledge_engine = KnowledgeEngine()
