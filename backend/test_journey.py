import asyncio
from app.services.transit_service import transit_service
import sys
import logging

logging.basicConfig(level=logging.INFO)

def main():
    transit_service.load_all_feeds("data")
    
    source_results = transit_service.search_stops("Avadi")
    dest_results = transit_service.search_stops("Tiruninravur")
    
    print("Source results:")
    for r in source_results:
        print(f"  {r.stop_id}: {r.stop_name} (tier: {r.match_tier}, score: {r.match_score})")
        
    print("Dest results:")
    for r in dest_results:
        print(f"  {r.stop_id}: {r.stop_name} (tier: {r.match_tier}, score: {r.match_score})")
        
    if not source_results or not dest_results:
        return
        
    s_id = source_results[0].stop_id
    d_id = dest_results[0].stop_id
    
    print(f"\nSearching journeys from {s_id} to {d_id}")
    journeys = transit_service.get_direct_journeys(s_id, d_id)
    print(f"Found {len(journeys)} journeys.")
    
if __name__ == "__main__":
    main()
