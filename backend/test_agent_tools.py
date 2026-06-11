from app.services.agent_tools import TransitAgentTools
from app.services.transit_service import transit_service

# Load the GTFS data
transit_service.load_all_feeds("data")

tools = TransitAgentTools()
try:
    print("Calling search_stops...")
    results = tools.search_stops("chennai centrl")
    print(results)
except Exception as e:
    print("Exception caught:", e)
