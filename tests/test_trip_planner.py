"""Tests for the find_trip feature with route ranking."""

import pytest
from app.services.transit_service import TransitService
from app.models.schemas import TripResponse

@pytest.fixture
def transit_svc(tmp_path):
    """Fixture providing a TransitService loaded with mock GTFS data."""
    import pandas as pd
    
    # S1 -> S2 (Direct via R1)
    # S1 -> S3 -> S2 (Transfer 1 via R2, R3 - Good transfer, short distance)
    # S1 -> S5 -> S2 (Transfer 2 via R4, R5 - Bad transfer, long distance, many stops)
    
    stops_df = pd.DataFrame([
        {"stop_id": "S1", "stop_name": "Source Stop", "stop_lat": "10.0", "stop_lon": "20.0"},
        {"stop_id": "S2", "stop_name": "Dest Stop", "stop_lat": "10.1", "stop_lon": "20.1"},
        {"stop_id": "S3", "stop_name": "Good Transfer", "stop_lat": "10.05", "stop_lon": "20.05"},
        {"stop_id": "S4", "stop_name": "Isolated Stop", "stop_lat": "10.3", "stop_lon": "20.3"},
        {"stop_id": "S5", "stop_name": "Bad Transfer", "stop_lat": "11.0", "stop_lon": "21.0"},
    ])
    
    routes_df = pd.DataFrame([
        {"route_id": "R1", "route_short_name": "1A", "route_long_name": "Direct"},
        {"route_id": "R2", "route_short_name": "2A", "route_long_name": "Source to Good"},
        {"route_id": "R3", "route_short_name": "3A", "route_long_name": "Good to Dest"},
        {"route_id": "R4", "route_short_name": "4A", "route_long_name": "Source to Bad"},
        {"route_id": "R5", "route_short_name": "5A", "route_long_name": "Bad to Dest"},
    ])
    
    trips_df = pd.DataFrame([
        {"route_id": "R1", "trip_id": "T1"},
        {"route_id": "R2", "trip_id": "T2"},
        {"route_id": "R3", "trip_id": "T3"},
        {"route_id": "R4", "trip_id": "T4"},
        {"route_id": "R5", "trip_id": "T5"},
    ])
    
    stop_times_df = pd.DataFrame([
        # Direct route T1: S1 -> S2 (2 stops)
        {"trip_id": "T1", "stop_id": "S1", "stop_sequence": "1"},
        {"trip_id": "T1", "stop_id": "S2", "stop_sequence": "2"},
        
        # Good Transfer route 1: T2: S1 -> S3 (2 stops)
        {"trip_id": "T2", "stop_id": "S1", "stop_sequence": "1"},
        {"trip_id": "T2", "stop_id": "S3", "stop_sequence": "2"},
        
        # Good Transfer route 2: T3: S3 -> S2 (2 stops)
        {"trip_id": "T3", "stop_id": "S3", "stop_sequence": "1"},
        {"trip_id": "T3", "stop_id": "S2", "stop_sequence": "2"},
        
        # Bad Transfer route 1: T4: S1 -> S5 (5 stops)
        {"trip_id": "T4", "stop_id": "S1", "stop_sequence": "1"},
        {"trip_id": "T4", "stop_id": "S5", "stop_sequence": "5"},
        
        # Bad Transfer route 2: T5: S5 -> S2 (5 stops)
        {"trip_id": "T5", "stop_id": "S5", "stop_sequence": "1"},
        {"trip_id": "T5", "stop_id": "S2", "stop_sequence": "5"},
    ])
    
    class MockGTFSLoader:
        def __init__(self):
            self.stops = stops_df
            self.routes = routes_df
            self.trips = trips_df
            self.stop_times = stop_times_df
            self._loaded = True

        def get_stop_by_id(self, stop_id):
            matches = self.stops[self.stops["stop_id"] == stop_id]
            if matches.empty:
                return None
            return matches.iloc[0]

    svc = TransitService()
    svc._gtfs_loader = MockGTFSLoader()
    from app.services.stop_search import StopSearch
    svc._stop_search = StopSearch(svc._gtfs_loader.stops)
    svc._feeds = {"mock_feed": svc._gtfs_loader, "other_feed": svc._gtfs_loader}
    svc._data_path = str(tmp_path)
    return svc


def test_find_trip_ranks_direct_and_transfers(transit_svc):
    # Requirement: Direct routes always rank above transfer routes (handled by schema separation)
    resp = transit_svc.find_trip("Source Stop", "Dest Stop")
    assert isinstance(resp, TripResponse)
    
    res = resp.results[0]
    assert len(res.direct_routes) == 1
    assert res.direct_routes[0].route_id == "R1"
    
    # We also discovered transfers
    assert len(res.transfer_options) == 2


def test_find_trip_ranks_best_transfer_first(transit_svc):
    # Requirement: Best transfer route ranks above less efficient transfer routes
    # Remove direct route to focus on transfers
    transit_svc._feeds["mock_feed"].stop_times = transit_svc._feeds["mock_feed"].stop_times[
        transit_svc._feeds["mock_feed"].stop_times["trip_id"] != "T1"
    ]
    
    resp = transit_svc.find_trip("Source Stop", "Dest Stop")
    res = resp.results[0]
    
    # We have 2 transfer options: Good (S3) and Bad (S5)
    assert len(res.transfer_options) == 2
    
    # Good transfer should be first
    best_transfer = res.transfer_options[0]
    worst_transfer = res.transfer_options[1]
    
    assert best_transfer.transfer_stop_id == "S3"
    assert worst_transfer.transfer_stop_id == "S5"
    
    # Requirement: Score ordering is correct
    assert best_transfer.score < worst_transfer.score
    
    # Requirement: Smaller estimated_stop_count
    assert best_transfer.estimated_stop_count == (2-1) + (2-1) # 2
    assert worst_transfer.estimated_stop_count == (5-1) + (5-1) # 8


def test_find_trip_missing_stop_sequence_handled_safely(transit_svc):
    # Remove stop_sequence from one of the stops
    st_df = transit_svc._feeds["mock_feed"].stop_times.copy()
    st_df.loc[st_df["stop_id"] == "S3", "stop_sequence"] = None
    transit_svc._feeds["mock_feed"].stop_times = st_df
    
    # Should not crash, should fallback gracefully
    resp = transit_svc.find_trip("Source Stop", "Dest Stop")
    assert len(resp.results) > 0


def test_find_trip_no_results(transit_svc):
    resp = transit_svc.find_trip("Source Stop", "Isolated Stop")
    assert len(resp.results) == 0


def test_find_trip_across_feeds(transit_svc):
    resp = transit_svc.find_trip("Source Stop", "Dest Stop")
    assert resp.feeds_searched == ["mock_feed", "other_feed"]
    assert len(resp.results) == 2


def test_find_trip_result_limit(transit_svc):
    # Add dummy transfers to exceed limit of 2
    import pandas as pd
    new_stops = pd.DataFrame([
        {"stop_id": f"S{i}", "stop_name": f"Dummy {i}", "stop_lat": "10.1", "stop_lon": "20.1"}
        for i in range(10, 15)
    ])
    new_trips = pd.DataFrame([
        {"route_id": f"R{i}", "trip_id": f"T{i}"}
        for i in range(10, 20)
    ])
    new_routes = pd.DataFrame([
        {"route_id": f"R{i}", "route_short_name": f"D{i}", "route_long_name": f"Dummy Route {i}"}
        for i in range(10, 20)
    ])
    
    # T10-14 go Source to Dummy
    # T15-19 go Dummy to Dest
    st_rows = []
    for i in range(5):
        stop_id = f"S{i+10}"
        st_rows.extend([
            {"trip_id": f"T{i+10}", "stop_id": "S1", "stop_sequence": "1"},
            {"trip_id": f"T{i+10}", "stop_id": stop_id, "stop_sequence": "2"},
            {"trip_id": f"T{i+15}", "stop_id": stop_id, "stop_sequence": "1"},
            {"trip_id": f"T{i+15}", "stop_id": "S2", "stop_sequence": "2"},
        ])
    new_st = pd.DataFrame(st_rows)
    
    loader = transit_svc._feeds["mock_feed"]
    loader.stops = pd.concat([loader.stops, new_stops], ignore_index=True)
    loader.trips = pd.concat([loader.trips, new_trips], ignore_index=True)
    loader.routes = pd.concat([loader.routes, new_routes], ignore_index=True)
    loader.stop_times = pd.concat([loader.stop_times, new_st], ignore_index=True)
    
    # Ensure limit works (set to 2)
    resp = transit_svc.find_trip("Source Stop", "Dest Stop", max_transfer_results=2)
    res = resp.results[0]
    assert len(res.transfer_options) == 2


def test_stop_search_ranking():
    from app.services.stop_search import StopSearch
    from app.models.schemas import MatchTier
    import pandas as pd
    
    stops_df = pd.DataFrame([
        {"stop_id": "MS", "stop_name": "Chennai Egmore", "stop_lat": "13.0", "stop_lon": "80.0"},
        {"stop_id": "MASS", "stop_name": "Chennai Central Suburban", "stop_lat": "13.1", "stop_lon": "80.1"},
        {"stop_id": "123", "stop_name": "MS Terminal", "stop_lat": "13.2", "stop_lon": "80.2"},
        {"stop_id": "456", "stop_name": "Some MS Stop", "stop_lat": "13.3", "stop_lon": "80.3"},
        {"stop_id": "CMS", "stop_name": "Kochi Bus Stop", "stop_lat": "10.0", "stop_lon": "76.0"},
        {"stop_id": "789", "stop_name": "High Mass Light", "stop_lat": "10.1", "stop_lon": "76.1"},
    ])
    searcher = StopSearch(stops_df)

    # 1. Exact stop_id matching
    res_ms = searcher.search("MS")
    assert res_ms[0].stop_id == "MS"
    assert res_ms[0].match_tier == MatchTier.EXACT_ID
    
    # 2. Exact stop_name matching
    res_name = searcher.search("Chennai Egmore")
    assert res_name[0].stop_id == "MS"
    assert res_name[0].match_tier == MatchTier.EXACT_NAME
    
    # 3. Prefix matching
    res_prefix = searcher.search("MS Term")
    assert res_prefix[0].stop_id == "123"
    assert res_prefix[0].match_tier == MatchTier.PREFIX
    
    # 4. Token matching
    assert res_ms[1].stop_id == "123" # Prefix "MS Terminal"
    assert res_ms[1].match_tier == MatchTier.PREFIX
    assert res_ms[2].stop_id == "456" # Token "Some MS Stop"
    assert res_ms[2].match_tier == MatchTier.TOKEN
    assert res_ms[3].stop_id == "CMS" # Fuzzy substring "CMS"
    assert res_ms[3].match_tier == MatchTier.FUZZY
    
    # 5. Fuzzy matching
    res_mass = searcher.search("MASS")
    assert res_mass[0].stop_id == "MASS" # Exact ID
    assert res_mass[0].match_tier == MatchTier.EXACT_ID
    assert res_mass[1].stop_id == "789" # Token match "High Mass Light"
    assert res_mass[1].match_tier == MatchTier.TOKEN


def test_cross_feed_ambiguity(transit_svc):
    import pandas as pd
    
    # Set up Chennai feed
    chennai_stops = pd.DataFrame([
        {"stop_id": "MS", "stop_name": "Chennai Egmore", "stop_lat": "13.0", "stop_lon": "80.0"},
        {"stop_id": "MASS", "stop_name": "Chennai Central Suburban", "stop_lat": "13.1", "stop_lon": "80.1"},
    ])
    chennai_routes = pd.DataFrame([{"route_id": "R1", "route_short_name": "C1", "route_long_name": "Chennai Route"}])
    chennai_trips = pd.DataFrame([{"route_id": "R1", "trip_id": "T1"}])
    chennai_st = pd.DataFrame([
        {"trip_id": "T1", "stop_id": "MS", "stop_sequence": "1"},
        {"trip_id": "T1", "stop_id": "MASS", "stop_sequence": "2"},
    ])
    
    class MockChennai:
        def __init__(self):
            self.stops = chennai_stops
            self.routes = chennai_routes
            self.trips = chennai_trips
            self.stop_times = chennai_st
        def get_stop_by_id(self, stop_id):
            matches = self.stops[self.stops["stop_id"] == stop_id]
            return matches.iloc[0] if not matches.empty else None
            
    # Set up Kochi feed
    kochi_stops = pd.DataFrame([
        {"stop_id": "CMS", "stop_name": "Kochi Bus Stop", "stop_lat": "10.0", "stop_lon": "76.0"},
        {"stop_id": "789", "stop_name": "High Mass Light", "stop_lat": "10.1", "stop_lon": "76.1"},
    ])
    kochi_routes = pd.DataFrame([{"route_id": "K1", "route_short_name": "K1", "route_long_name": "Kochi Route"}])
    kochi_trips = pd.DataFrame([{"route_id": "K1", "trip_id": "KT1"}])
    kochi_st = pd.DataFrame([
        {"trip_id": "KT1", "stop_id": "CMS", "stop_sequence": "1"},
        {"trip_id": "KT1", "stop_id": "789", "stop_sequence": "2"},
    ])

    class MockKochi:
        def __init__(self):
            self.stops = kochi_stops
            self.routes = kochi_routes
            self.trips = kochi_trips
            self.stop_times = kochi_st
        def get_stop_by_id(self, stop_id):
            matches = self.stops[self.stops["stop_id"] == stop_id]
            return matches.iloc[0] if not matches.empty else None
            
    transit_svc._feeds = {"kochi": MockKochi(), "chennai": MockChennai()}
    transit_svc._gtfs_loader = True
    transit_svc._stop_search = True
    
    # 6. Cross-feed collisions 
    resp = transit_svc.find_trip("MS", "MASS")
    
    # Expected: "chennai" feed should be the first result
    assert resp.results[0].feed == "chennai"
    # Kochi feed shouldn't outrank Chennai since Kochi uses fuzzy matches while Chennai uses Exact IDs
    
    assert resp.results[0].source_stop_id == "MS"
    assert resp.results[0].destination_stop_id == "MASS"

