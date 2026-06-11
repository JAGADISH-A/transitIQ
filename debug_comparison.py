import logging
import time

from app.services.transit_service import transit_service
from app.services.agent_tools import TransitAgentTools
from app.services.foundry_agent import FoundryTransitAgent

logging.basicConfig(level=logging.ERROR)

def main():
    print("Loading GTFS data...")
    transit_service.load_all_feeds("data")
    
    agent_tools = TransitAgentTools()
    agent = FoundryTransitAgent()

    print("\n--- Test A: search_stops('chennai central') ---")
    res_A = agent_tools.search_stops("chennai central")
    print(f"type(result) = {type(res_A)}")
    print(f"len(result) = {len(res_A)}")
    if res_A:
        print(f"first result = {repr(res_A[0])}")

    print("\n--- Test B: search_stops('chennai centrl') ---")
    res_B = agent_tools.search_stops("chennai centrl")
    print(f"type(result) = {type(res_B)}")
    print(f"len(result) = {len(res_B)}")
    if res_B:
        print(f"first result = {repr(res_B[0])}")

    print("\n--- Test C: FAST_PATH 'Find station chennai central' ---")
    fast_C = agent._fast_path_route("Find station chennai central")
    print(f"extracted query = chennai central")
    print(f"raw search_stops return value = {repr(agent_tools.search_stops('chennai central')[:1])}...")
    print(f"final answer = {fast_C.get('answer') if fast_C else 'None'}")

    print("\n--- Test D: FAST_PATH 'Find station chennai centrl' ---")
    fast_D = agent._fast_path_route("Find station chennai centrl")
    print(f"extracted query = chennai centrl")
    print(f"raw search_stops return value = {repr(agent_tools.search_stops('chennai centrl')[:1])}...")
    print(f"final answer = {fast_D.get('answer') if fast_D else 'None'}")

if __name__ == "__main__":
    main()
