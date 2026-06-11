import logging
from app.services.transit_service import transit_service
from app.services.agent_tools import TransitAgentTools
from app.services.foundry_agent import FoundryTransitAgent

logging.basicConfig(level=logging.INFO)

def main():
    print("Loading GTFS...")
    transit_service.load_all_feeds("data")
    
    print("\nRunning search_stops('chennai centrl')...")
    tools = TransitAgentTools()
    res = tools.search_stops("chennai centrl")
    
    print("\nRAW RESULTS:")
    for i, r in enumerate(res[:5]):
        print(f"{i+1}: {repr(r)}")
        
    print("\nRunning FAST_PATH router...")
    agent = FoundryTransitAgent()
    fast_path_res = agent._fast_path_route("Find station chennai centrl")
    print(f"\nFAST_PATH RESPONSE:\n{fast_path_res}")

if __name__ == "__main__":
    main()
