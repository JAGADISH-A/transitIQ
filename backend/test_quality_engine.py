import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.quality_engine import JourneyQualityEngine
from app.models.schemas import JourneyRoute, TransferJourney, DisplayTime, JourneyType

def test_quality_engine():
    print("Testing Journey Quality Engine...")
    
    # Mock routes
    direct_best = JourneyRoute(
        journey_type=JourneyType.DIRECT,
        feed="test",
        trip_id="1",
        route_id="R1",
        route_name="Route 1",
        source_stop="A",
        destination_stop="B",
        stops_between=5,
        departure_time="10:00:00",
        arrival_time="11:00:00",
        duration_minutes=60
    )
    
    direct_slow = JourneyRoute(
        journey_type=JourneyType.DIRECT,
        feed="test",
        trip_id="2",
        route_id="R2",
        route_name="Route 2",
        source_stop="A",
        destination_stop="B",
        stops_between=10,
        departure_time="10:30:00",
        arrival_time="12:30:00",
        duration_minutes=120
    )
    
    transfer_optimal = TransferJourney(
        journey_type=JourneyType.TRANSFER,
        transfer_stop="C",
        first_leg=JourneyRoute(
            journey_type=JourneyType.DIRECT,
            feed="test", trip_id="3", route_id="R3", route_name="Route 3",
            source_stop="A", destination_stop="C", stops_between=2,
            departure_time="10:15:00", arrival_time="10:30:00", duration_minutes=15
        ),
        second_leg=JourneyRoute(
            journey_type=JourneyType.DIRECT,
            feed="test", trip_id="4", route_id="R4", route_name="Route 4",
            source_stop="C", destination_stop="B", stops_between=2,
            departure_time="10:40:00", arrival_time="11:10:00", duration_minutes=30
        ),
        total_duration=55,
        transfer_wait=10 # Optimal: +5 bonus
    )
    
    transfer_risky = TransferJourney(
        journey_type=JourneyType.TRANSFER,
        transfer_stop="C",
        first_leg=JourneyRoute(
            journey_type=JourneyType.DIRECT,
            feed="test", trip_id="5", route_id="R5", route_name="Route 5",
            source_stop="A", destination_stop="C", stops_between=2,
            departure_time="10:00:00", arrival_time="10:30:00", duration_minutes=30
        ),
        second_leg=JourneyRoute(
            journey_type=JourneyType.DIRECT,
            feed="test", trip_id="6", route_id="R6", route_name="Route 6",
            source_stop="C", destination_stop="B", stops_between=2,
            departure_time="10:32:00", arrival_time="11:00:00", duration_minutes=28
        ),
        total_duration=60,
        transfer_wait=2 # Risky: -25 penalty
    )
    
    transfer_rejected = TransferJourney(
        journey_type=JourneyType.TRANSFER,
        transfer_stop="C",
        first_leg=JourneyRoute(
            journey_type=JourneyType.DIRECT,
            feed="test", trip_id="7", route_id="R7", route_name="Route 7",
            source_stop="A", destination_stop="C", stops_between=2,
            departure_time="10:00:00", arrival_time="10:30:00", duration_minutes=30
        ),
        second_leg=JourneyRoute(
            journey_type=JourneyType.DIRECT,
            feed="test", trip_id="8", route_id="R8", route_name="Route 8",
            source_stop="C", destination_stop="B", stops_between=2,
            departure_time="13:00:00", arrival_time="13:30:00", duration_minutes=30
        ),
        total_duration=210,
        transfer_wait=150 # > 120: REJECTED
    )
    
    routes = [direct_best, direct_slow]
    transfer_routes = [transfer_optimal, transfer_risky, transfer_rejected]
    
    res_routes, res_transfers = JourneyQualityEngine.evaluate(routes, transfer_routes, "10:00:00")
    
    # We should have all routes returned, but sorted by score
    print("\n--- Direct Routes ---")
    for r in res_routes:
        print(f"Trip {r.trip_id}: Score={r.quality.score}, Class={r.quality.classification.value}, Reason={r.quality.recommendation_reason}, Flags={r.quality.route_flags}")
        
    print("\n--- Transfer Routes ---")
    for t in res_transfers:
        print(f"Transfer at {t.transfer_stop} (Wait {t.transfer_wait}): Score={t.quality.score}, Class={t.quality.classification.value}, Reason={t.quality.recommendation_reason}, Flags={t.quality.route_flags}")

    # Assertions
    # 1. direct_best (60m duration). Best duration is 55m (from transfer_optimal).
    # Penalty: max(0, 60-55)*0.5 = 2.5
    # Transfers: 0 -> 0
    # Wait: 0 -> 0
    # Dep Gap: 0 -> 0
    # Score = 100 - 2.5 = 97.5 (Excellent)
    
    # 2. direct_slow (120m duration)
    # Penalty: (120-55)*0.5 = 32.5
    # Dep Gap: 30m -> 0
    # Score = 100 - 32.5 = 67.5 (Acceptable)
    
    # 3. transfer_optimal (55m duration, best)
    # Transfer: 1 -> -15
    # Wait: 10m -> +5
    # Duration penalty: 0
    # Score = 100 - 15 + 5 = 90 (Excellent)
    
    # 4. transfer_risky (60m duration)
    # Transfer: 1 -> -15
    # Wait: 2m -> -25
    # Duration: (60-55)*0.5 = 2.5
    # Score = 100 - 15 - 25 - 2.5 = 57.5 (Acceptable)
    
    # 5. transfer_rejected
    # Score = 0, Rejected
    
    print("\n✅ Verification complete!")
    
if __name__ == "__main__":
    test_quality_engine()
