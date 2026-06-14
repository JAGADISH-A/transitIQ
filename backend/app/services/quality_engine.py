from typing import List, Union, Tuple
from app.models.schemas import JourneyRoute, TransferJourney, JourneyQuality, QualityClassification
from datetime import datetime, timedelta

class JourneyQualityEngine:
    @staticmethod
    def _parse_time_string(time_str: str) -> int:
        """Parses HH:MM:SS or HH:MM string into total minutes."""
        if not time_str or time_str.strip() == "nan":
            return 0
        parts = time_str.strip().split(':')
        if len(parts) < 2:
            return 0
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return 0

    @staticmethod
    def _get_classification(score: float) -> QualityClassification:
        if score >= 85:
            return QualityClassification.EXCELLENT
        elif score >= 70:
            return QualityClassification.GOOD
        elif score >= 50:
            return QualityClassification.ACCEPTABLE
        elif score >= 30:
            return QualityClassification.POOR
        else:
            return QualityClassification.LOW_QUALITY

    @classmethod
    def evaluate(
        cls, 
        routes: List[JourneyRoute], 
        transfer_routes: List[TransferJourney], 
        departure_after: str | None
    ) -> Tuple[List[JourneyRoute], List[TransferJourney]]:
        
        all_journeys = []
        for r in routes:
            all_journeys.append(("DIRECT", r))
        for t in transfer_routes:
            all_journeys.append(("TRANSFER", t))
            
        if not all_journeys:
            return [], []

        # Find best duration
        best_duration = float('inf')
        for type_, j in all_journeys:
            if type_ == "DIRECT" and j.duration_minutes is not None:
                best_duration = min(best_duration, j.duration_minutes)
            elif type_ == "TRANSFER":
                best_duration = min(best_duration, j.total_duration)
                
        # Handle case where no duration could be parsed
        if best_duration == float('inf'):
            best_duration = 0
            
        # Parse departure_after
        requested_dep_minutes = 0
        if departure_after:
            requested_dep_minutes = cls._parse_time_string(departure_after)
            
        # Evaluate each journey
        for type_, j in all_journeys:
            score = 100.0
            rejection_reason = None
            flags = []
            
            # Extract common metrics
            if type_ == "DIRECT":
                transfers = 0
                wait = 0
                duration = j.duration_minutes or 0
                dep_minutes = cls._parse_time_string(j.departure_time) if j.departure_time else 0
            else:
                transfers = 2 if getattr(j, 'third_leg', None) else 1
                wait = j.transfer_wait
                if transfers == 2 and getattr(j, 'transfer_wait_2', None) is not None:
                    wait = max(j.transfer_wait, j.transfer_wait_2)
                duration = j.total_duration
                dep_minutes = cls._parse_time_string(j.first_leg.departure_time) if j.first_leg.departure_time else 0
                
            # 1. Rejection Layer
            if type_ == "TRANSFER" and wait > 120:
                rejection_reason = "Transfer wait exceeds maximum threshold"
            elif best_duration > 0 and duration > best_duration * 2:
                rejection_reason = "Travel duration exceeds maximum threshold compared to best route"
                
            if rejection_reason:
                j.quality = JourneyQuality(
                    score=0,
                    classification=QualityClassification.REJECTED,
                    recommendation_reason=rejection_reason,
                    route_flags=["REJECTED"]
                )
                continue
                
            # 2. Transfer Count Penalty
            if transfers == 1:
                score -= 15
            elif transfers == 2:
                score -= 35
            elif transfers >= 3:
                score -= 60
                
            # 3. Transfer Wait Time Penalty
            if type_ == "TRANSFER":
                if wait <= 3:
                    score -= 25
                    flags.append("RISKY_TRANSFER")
                elif 3 < wait <= 8:
                    score -= 0
                elif 8 < wait <= 15:
                    score += 5
                    flags.append("OPTIMAL_TRANSFER")
                elif 15 < wait <= 30:
                    score -= 5
                elif 30 < wait <= 60:
                    score -= 20
                elif 60 < wait <= 90:
                    score -= 35
                    flags.append("LONG_TRANSFER_WAIT")
                elif wait > 90:
                    score -= 50
                    flags.append("VERY_LONG_TRANSFER_WAIT")
                    
            # 4. Departure Relevance Penalty
            if requested_dep_minutes > 0 and dep_minutes >= requested_dep_minutes:
                gap = dep_minutes - requested_dep_minutes
                if 30 < gap <= 60:
                    score -= 5
                elif 60 < gap <= 120:
                    score -= 15
                elif 120 < gap <= 240:
                    score -= 30
                elif gap > 240:
                    score -= 50
            
            # 5. Travel Duration Penalty
            if duration > best_duration and best_duration > 0:
                score -= max(0, duration - best_duration) * 0.5
                
            if duration == best_duration and best_duration > 0:
                flags.append("FASTEST_ROUTE")
                
            if type_ == "DIRECT":
                flags.append("DIRECT_SERVICE")
                
            # Check for overnight journey
            if type_ == "DIRECT":
                if j.arrival_display and j.arrival_display.day_offset > 0:
                    flags.append("OVERNIGHT_JOURNEY")
            else:
                last_leg = j.third_leg if getattr(j, 'third_leg', None) else j.second_leg
                if last_leg.arrival_display and last_leg.arrival_display.day_offset > 0:
                    flags.append("OVERNIGHT_JOURNEY")
                
            # Cap score between 0 and 100
            score = max(0, min(100, score))
            
            # Set recommendation reason
            reason = "Standard Route"
            if "FASTEST_ROUTE" in flags:
                reason = "Fastest service available"
            elif type_ == "TRANSFER" and "OPTIMAL_TRANSFER" in flags:
                reason = "Best transfer balance"
            elif type_ == "DIRECT":
                reason = "Direct route without transfers"
                
            j.quality = JourneyQuality(
                score=score,
                classification=cls._get_classification(score),
                recommendation_reason=reason,
                route_flags=flags
            )

        # Sort the output lists based on score descending
        def get_score(journey):
            return journey.quality.score if journey.quality else 0
            
        routes.sort(key=get_score, reverse=True)
        transfer_routes.sort(key=get_score, reverse=True)

        return routes, transfer_routes
