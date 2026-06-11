from app.services.agent_tools import TransitAgentTools
from app.services.transit_service import transit_service
import re

transit_service.load_all_feeds("data")
agent_tools = TransitAgentTools()

def test_fast_path(user_query):
    patterns_station = [
        re.compile(r"(?:search\s+stop|find\s+station)\s+(.+?)(?:\Z|\?|\.)", re.IGNORECASE)
    ]
    for p in patterns_station:
        match = p.search(user_query)
        if match:
            print("Matched query:", match.group(1))
            query = match.group(1).strip()
            try:
                res_list = agent_tools.search_stops(query)
                print("res_list type:", type(res_list))
                print("res_list length:", len(res_list))
                
                if isinstance(res_list, list) and len(res_list) > 0:
                    stop = res_list[0]
                    s_name = getattr(stop, "stop_name", "Unknown Stop")
                    s_id = getattr(stop, "stop_id", "Unknown ID")
                    answer = f"Found stop:\n{s_name} ({s_id})"
                else:
                    answer = "Could not find a matching stop."
            except Exception as e:
                print("Exception:", e)
                answer = "Could not find a matching stop."
            print("Answer:", answer)
            return

test_fast_path("Find station chennai centrl")
