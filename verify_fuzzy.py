import sys
import pandas as pd
from app.services.stop_search import StopSearch
from app.models.schemas import StopResult

# Mock the railways feed stops
stops_data = [
    {"stop_id": "MS", "stop_name": "CHENNAI EGMORE", "stop_lat": 13.0, "stop_lon": 80.0},
    {"stop_id": "MASS", "stop_name": "CHENNAI CENTRAL SUBURBAN STATION", "stop_lat": 13.08, "stop_lon": 80.2},
    {"stop_id": "MAS", "stop_name": "CHENNAI", "stop_lat": 13.08, "stop_lon": 80.2},
    {"stop_id": "TI", "stop_name": "TIRUNINRAVUR", "stop_lat": 13.1, "stop_lon": 80.1},
    {"stop_id": "AB", "stop_name": "AMBATTUR", "stop_lat": 13.11, "stop_lon": 80.15},
]
df = pd.DataFrame(stops_data)

searcher = StopSearch(df)

def verify(query):
    print(f"\nQuery: '{query}'")
    results = searcher.search(query)
    for i, r in enumerate(results):
        print(f"Rank #{i+1}: {r.stop_name} (Score: {r.match_score:.2f}, Tier: {r.match_tier})")

verify("chennai centrl")
verify("tiruniravur")
verify("egmore")
