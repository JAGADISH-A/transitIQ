import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.transit_service import transit_service
from app.services.quality_engine import JourneyQualityEngine

def test_routes():
    transit_service.load_all_feeds("./data")

    routes_to_test = [
        ("HC", "SBC"),
        ("HC", "BNC"),
        ("HC", "TEN"),
        ("HC", "MDU"),
        ("HC", "NJT")
    ]

    print("=== SPECIFIC ROUTES ===")
    for src, dst in routes_to_test:
        transfer = transit_service.find_transfer_routes(src, dst)
        _, transfer_evaluated = JourneyQualityEngine.evaluate([], transfer, None)
        valid = [t for t in transfer_evaluated if t.quality and t.quality.classification.value != "Rejected"]
        
        if valid:
            top = valid[0]
            print(f"Route: {src} -> {dst} | Found: Yes | Transfer: {top.transfer_stop} | Wait: {top.transfer_wait} | Duration: {top.total_duration}")
        else:
            print(f"Route: {src} -> {dst} | Found: No")

    print("\n=== RANDOM COVERAGE ===")
    loader = transit_service.get_feed("railways")
    stops = loader.stops["stop_id"].tolist()
    random.seed(42)
    pairs = []
    for _ in range(100):
        s1 = random.choice(stops)
        s2 = random.choice(stops)
        if s1 != s2:
            pairs.append((s1, s2))

    found_count = 0
    for src, dst in pairs:
        transfer = transit_service.find_transfer_routes(src, dst)
        _, transfer_evaluated = JourneyQualityEngine.evaluate([], transfer, None)
        valid = [t for t in transfer_evaluated if t.quality and t.quality.classification.value != "Rejected"]
        if valid:
            found_count += 1

    print(f"Coverage: {found_count}/{len(pairs)}")

if __name__ == "__main__":
    test_routes()
