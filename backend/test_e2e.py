import os
import json
import logging
import time

logging.basicConfig(level=logging.ERROR)

from app.services.transit_service import transit_service
print("Loading GTFS feeds... (this may take a few seconds)")
transit_service.load_all_feeds("./data")
print("Feeds loaded.\n")

from app.services.foundry_agent import foundry_transit_agent

queries = [
    "How do I get from chennai egmore to chennai central?",
    "Route from avadi to tiruniravur",
    "Find station chennai central"
]

for i, query in enumerate(queries, 1):
    print(f"--- Query {i}: {query} ---")
    start_time = time.perf_counter()
    
    # We simulate loading previously to isolate execution time for the query itself
    # But inside answer(), it calculates its own time. We will print both.
    result = foundry_transit_agent.answer(query)
    
    total_time_ms = (time.perf_counter() - start_time) * 1000
    
    print(f"Classification: {result.get('classification')}")
    print(f"Reported execution_time_ms: {result.get('execution_time_ms'):.2f} ms (Measured: {total_time_ms:.2f} ms)")
    
    # foundry_agent.py returns a list of tools used in `tools_used` if FAST_PATH
    # Let's see what is inside the result.
    # To count transfer options, we can check the 'raw_results' or parse the answer.
    
    print(f"Final Answer:\n{result.get('answer')}")
    
    route_data = result.get('route_data')
    if route_data:
        # Just print top level keys, transfer count, and the first transfer option
        results = route_data.get('results', [])
        print(f"route_data.source: {route_data.get('source')}")
        print(f"route_data.destination: {route_data.get('destination')}")
        if results:
            trip_result = results[0]
            print(f"feed: {trip_result.get('feed')}")
            transfers = trip_result.get('transfer_options', [])
            print(f"Transfer options count: {len(transfers)}")
            if transfers:
                print("Sample transfer option:")
                print(json.dumps(transfers[0], indent=2, default=str))
    
    print("-" * 50 + "\n")
