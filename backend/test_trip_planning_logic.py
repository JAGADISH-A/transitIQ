import sys
sys.path.insert(0, ".")

from app.services.transit_service import transit_service
from app.models.schemas import TripRoute, TransferOption, TripResult

def get_routes_for_stop(loader, stop_id):
    stop_times = loader.stop_times
    trips = loader.trips
    routes = loader.routes
    
    s_times = stop_times[stop_times['stop_id'] == stop_id]
    s_trips = trips[trips['trip_id'].isin(s_times['trip_id'])]
    s_routes = routes[routes['route_id'].isin(s_trips['route_id'])]
    return s_routes

transit_service.load_all_feeds("data")

print("Feeds:", transit_service.available_feeds())

source_query = "Chennai Central"
dest_query = "Egmore"

for feed_name, loader in transit_service._feeds.items():
    print(f"Checking feed: {feed_name}")
    from app.services.stop_search import StopSearch
    searcher = StopSearch(loader.stops)
    
    source_results = searcher.search(source_query)
    dest_results = searcher.search(dest_query)
    
    if source_results and dest_results:
        source_stop = source_results[0]
        dest_stop = dest_results[0]
        
        print(f"  Source: {source_stop.stop_name} ({source_stop.stop_id})")
        print(f"  Dest: {dest_stop.stop_name} ({dest_stop.stop_id})")
        
        source_routes = get_routes_for_stop(loader, source_stop.stop_id)
        dest_routes = get_routes_for_stop(loader, dest_stop.stop_id)
        
        source_route_ids = set(source_routes['route_id'])
        dest_route_ids = set(dest_routes['route_id'])
        
        direct_route_ids = source_route_ids.intersection(dest_route_ids)
        print(f"  Direct routes: {direct_route_ids}")
        
        if not direct_route_ids:
            # find transfers
            trips = loader.trips
            stop_times = loader.stop_times
            
            source_trips_all = trips[trips['route_id'].isin(source_route_ids)]
            dest_trips_all = trips[trips['route_id'].isin(dest_route_ids)]
            
            source_stops_all = set(stop_times[stop_times['trip_id'].isin(source_trips_all['trip_id'])]['stop_id'])
            dest_stops_all = set(stop_times[stop_times['trip_id'].isin(dest_trips_all['trip_id'])]['stop_id'])
            
            transfer_stop_ids = source_stops_all.intersection(dest_stops_all)
            print(f"  Transfer stops: {list(transfer_stop_ids)[:5]}")
