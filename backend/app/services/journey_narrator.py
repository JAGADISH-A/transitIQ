from typing import List
from app.models.schemas import JourneyRoute, TransferJourney, JourneyNarrative

class JourneyNarratorService:
    @staticmethod
    def generate_narrative(routes: List[JourneyRoute], transfer_routes: List[TransferJourney]) -> JourneyNarrative | None:
        valid_routes = [r for r in routes if r.quality and r.quality.classification != "Rejected"]
        valid_transfers = [t for t in transfer_routes if t.quality and t.quality.classification != "Rejected"]
        
        all_valid = valid_routes + valid_transfers
        if not all_valid:
            return JourneyNarrative(
                headline="Limited Service Available",
                summary="There are no high-quality journeys operating at the moment.",
                recommendation="You may prefer travelling later when direct services resume.",
                warnings=["No recommended routes found"],
                alternatives_available=0
            )
            
        # Get the top recommended route
        # Both arrays should already be sorted by quality score descending.
        # We just pick the absolute best one.
        best_direct = valid_routes[0] if valid_routes else None
        best_transfer = valid_transfers[0] if valid_transfers else None
        
        top_route = None
        is_transfer = False
        if best_direct and best_transfer:
            if best_direct.quality.score >= best_transfer.quality.score:
                top_route = best_direct
            else:
                top_route = best_transfer
                is_transfer = True
        elif best_direct:
            top_route = best_direct
        else:
            top_route = best_transfer
            is_transfer = True
            
        alternatives = len(all_valid) - 1
        warnings = []
        
        if top_route.quality and "VERY_LONG_TRANSFER_WAIT" in top_route.quality.route_flags:
            warnings.append("Extended transfer wait time")
        elif top_route.quality and "LONG_TRANSFER_WAIT" in top_route.quality.route_flags:
            warnings.append("Long transfer wait")
            
        if not is_transfer:
            source = top_route.source_stop
            dest = top_route.destination_stop
            
            return JourneyNarrative(
                headline="Direct Service Available",
                summary=f"A direct train is available from {source} to {dest}.",
                recommendation="This is the fastest available option and requires no transfers.",
                warnings=warnings,
                alternatives_available=alternatives
            )
        else:
            source = top_route.first_leg.source_stop
            dest = top_route.second_leg.destination_stop
            transfer_stop = top_route.transfer_stop
            
            headline = "Transfer Required"
            if top_route.quality and "RISKY_TRANSFER" in top_route.quality.route_flags:
                warnings.append(f"Short {top_route.transfer_wait} min transfer wait")
                
            summary = f"The recommended journey from {source} to {dest} includes a transfer at {transfer_stop}."
            recommendation = "This option balances travel time and transfer convenience."
            
            if top_route.quality and top_route.quality.score < 50:
                headline = "Limited Service Available"
                summary = f"Routes are available, but they require transfers or extended waiting times."
                recommendation = "You may prefer waiting for a later direct service if your travel time is flexible."
                if top_route.transfer_wait > 60:
                    warnings.append(f"{top_route.transfer_wait} minute transfer wait at {transfer_stop}")

            return JourneyNarrative(
                headline=headline,
                summary=summary,
                recommendation=recommendation,
                warnings=warnings,
                alternatives_available=alternatives
            )
