import asyncio
import random
import time
import json
from app.services.transit_service import transit_service

async def main():
    print("Loading GTFS feeds...")
    transit_service.load_all_feeds("./data")
    
    loader = transit_service._feeds.get("railways")
    stops = loader.stops["stop_id"].tolist()
    
    random.seed(42) # fixed seed for consistency
    pairs = []
    while len(pairs) < 100:
        s1, s2 = random.sample(stops, 2)
        pairs.append((s1, s2))
        
    print(f"Testing {len(pairs)} pairs...")
    
    results = {
        "direct": 0,
        "transfer": 0,
        "failed": 0,
        "details": []
    }
    
    start_time = time.time()
    for i, (src, dst) in enumerate(pairs):
        if i % 10 == 0:
            print(f"Progress: {i}/100")
            
        direct = transit_service.get_direct_journeys(src, dst)
        transfer = []
        if not direct:
            transfer = transit_service.find_transfer_routes(src, dst)
            
        if direct:
            results["direct"] += 1
            results["details"].append((src, dst, "direct", len(direct)))
        elif transfer:
            results["transfer"] += 1
            results["details"].append((src, dst, "transfer", len(transfer)))
        else:
            results["failed"] += 1
            results["details"].append((src, dst, "failed", 0))
            
    end_time = time.time()
    print(f"Completed in {end_time - start_time:.2f} seconds")
    
    with open("audit_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
