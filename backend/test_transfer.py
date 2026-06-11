import sys
import os
import asyncio

sys.path.append(os.path.abspath("c:/Users/jagan/Desktop/clutch/new project - transit/backend"))

from app.services.transit_service import transit_service
import time

def test_transfer():
    print("Loading data...")
    transit_service.load_all_feeds("data")
    print("Testing AVD to GDY")
    start = time.time()
    routes = transit_service.find_transfer_routes("AVD", "GDY")
    print(f"Found {len(routes)} transfer routes in {time.time() - start:.2f}s")
    for r in routes[:5]:
        print(f"Fastest: {r.total_duration} mins, Wait: {r.transfer_wait} mins")
        print(f"Transfer stop: {r.transfer_stop}")

if __name__ == "__main__":
    test_transfer()
