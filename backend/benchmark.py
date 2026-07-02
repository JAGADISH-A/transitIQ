import sys
import os
import time
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.transit_service import transit_service
from app.services.quality_engine import JourneyQualityEngine

def run_benchmarks():
    transit_service.load_all_feeds("./data")

    routes_to_test = [
        ("HC", "NJT"),
        ("HC", "TEN"),
        ("HC", "MDU"),
        ("HC", "SBC"),
        ("MS", "NDLS")
    ]

    print("=== 2-TRANSFER BENCHMARK ===")
    
    for src, dst in routes_to_test:
        print(f"\\nEvaluating {src} -> {dst}")
        
        # Test 1-transfer first to see if it triggers
        transfer_routes = transit_service.find_transfer_routes(src, dst)
        
        tracemalloc.start()
        start_time = time.time()
        
        # Force running the 2-transfer search to benchmark it
        two_transfer_routes = transit_service.find_two_transfer_routes(src, dst)
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # We need to evaluate them to know valid routes found
        _, evaluated = JourneyQualityEngine.evaluate([], two_transfer_routes, None)
        valid_routes = [r for r in evaluated if r.quality and r.quality.classification.value != "Rejected"]
        
        print(f"Execution Time: {end_time - start_time:.2f} seconds")
        print(f"Memory Usage: {peak / 10**6:.2f} MB")
        print(f"Routes Found: {len(valid_routes)}")
        
if __name__ == "__main__":
    run_benchmarks()
