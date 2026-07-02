import sys
import os

patch_content = """
    def find_two_transfer_routes(self, source_stop_id: str, destination_stop_id: str, departure_after: str | None = None) -> list["TransferJourney"]:
        from app.models.schemas import JourneyRoute, TransferJourney, JourneyType
        import pandas as pd
        
        print(f"\\n[2_TRANSFER_SEARCH]\\n{source_stop_id}\\n{destination_stop_id}")

        transfer_journeys = []
        MAX_TRANSFER_CANDIDATES = 200
        MAX_RETURNED_ROUTES = 30

        for feed_name, loader in self._feeds.items():
            stop_times = loader.stop_times
            trips = loader.trips
            routes = loader.routes
            stops = loader.stops

            if stop_times is None or trips is None or routes is None or stops is None:
                continue

            source_st = stop_times[stop_times["stop_id"] == source_stop_id]
            if source_st.empty: continue
            
            if departure_after:
                dep_after_pad = departure_after.strip().zfill(8)
                dt_series = source_st["departure_time"].astype(str).str.strip().str.zfill(8)
                source_st = source_st[dt_series >= dep_after_pad]
            
            if source_st.empty: continue
            source_st = source_st.sort_values(by="departure_time").head(MAX_TRANSFER_CANDIDATES)
            
            source_trips = trips[trips["trip_id"].isin(source_st["trip_id"])]
            source_trip_ids = source_trips["trip_id"].unique()
            
            first_leg_st = stop_times[stop_times["trip_id"].isin(source_trip_ids)]
            first_leg_merged = first_leg_st.merge(source_st[["trip_id", "stop_sequence", "departure_time"]], on="trip_id", suffixes=("", "_source"))
            reachable_st = first_leg_merged[first_leg_merged["stop_sequence"].astype(int) > first_leg_merged["stop_sequence_source"].astype(int)]
            s_a = reachable_st["stop_id"].unique()
            if len(s_a) == 0: continue

            dest_st = stop_times[stop_times["stop_id"] == destination_stop_id]
            if dest_st.empty: continue
            
            dest_trips = trips[trips["trip_id"].isin(dest_st["trip_id"])]
            dest_trip_ids = dest_trips["trip_id"].unique()
            
            third_leg_st = stop_times[stop_times["trip_id"].isin(dest_trip_ids)]
            third_leg_merged = third_leg_st.merge(dest_st[["trip_id", "stop_sequence", "arrival_time"]], on="trip_id", suffixes=("", "_dest"))
            boarding_st = third_leg_merged[third_leg_merged["stop_sequence"].astype(int) < third_leg_merged["stop_sequence_dest"].astype(int)]
            s_b = boarding_st["stop_id"].unique()
            if len(s_b) == 0: continue

            leg2_start_st = stop_times[stop_times["stop_id"].isin(s_a)]
            leg2_end_st = stop_times[stop_times["stop_id"].isin(s_b)]
            
            leg2_merged = leg2_start_st.merge(leg2_end_st, on="trip_id", suffixes=("_A", "_B"))
            leg2_valid = leg2_merged[leg2_merged["stop_sequence_A"].astype(int) < leg2_merged["stop_sequence_B"].astype(int)]
            if leg2_valid.empty: continue
            
            seen_transfer_triplets = set()
            
            source_name_row = stops[stops["stop_id"] == source_stop_id]
            dest_name_row = stops[stops["stop_id"] == destination_stop_id]
            source_name = source_name_row.iloc[0]["stop_name"] if not source_name_row.empty else source_stop_id
            dest_name = dest_name_row.iloc[0]["stop_name"] if not dest_name_row.empty else destination_stop_id
            
            for _, leg2_row in leg2_valid.iterrows():
                t_a_id = leg2_row["stop_id_A"]
                t_b_id = leg2_row["stop_id_B"]
                leg2_trip_id = leg2_row["trip_id"]
                
                t_a_arrs = reachable_st[reachable_st["stop_id"] == t_a_id]
                t_b_deps = boarding_st[boarding_st["stop_id"] == t_b_id]
                
                for _, leg1_arr_row in t_a_arrs.iterrows():
                    leg1_trip_id = leg1_arr_row["trip_id"]
                    arr1_time = str(leg1_arr_row["arrival_time"])
                    dep2_time = str(leg2_row["departure_time_A"])
                    
                    try:
                        a1h, a1m, _ = map(int, arr1_time.split(':')[:2])
                        d2h, d2m, _ = map(int, dep2_time.split(':')[:2])
                        a1_total = a1h * 60 + a1m
                        d2_total = d2h * 60 + d2m
                        wait1 = d2_total - a1_total
                    except: continue
                    
                    if not (3 <= wait1 <= 120): continue
                    
                    for _, leg3_dep_row in t_b_deps.iterrows():
                        leg3_trip_id = leg3_dep_row["trip_id"]
                        
                        dedupe_key = (str(leg1_trip_id), str(leg2_trip_id), str(leg3_trip_id))
                        if dedupe_key in seen_transfer_triplets: continue
                        
                        arr2_time = str(leg2_row["arrival_time_B"])
                        dep3_time = str(leg3_dep_row["departure_time"])
                        
                        try:
                            a2h, a2m, _ = map(int, arr2_time.split(':')[:2])
                            d3h, d3m, _ = map(int, dep3_time.split(':')[:2])
                            a2_total = a2h * 60 + a2m
                            d3_total = d3h * 60 + d3m
                            wait2 = d3_total - a2_total
                        except: continue
                        
                        if not (3 <= wait2 <= 120): continue
                        
                        first_dep_time = str(leg1_arr_row["departure_time_source"])
                        third_arr_time = str(leg3_dep_row["arrival_time_dest"])
                        try:
                            fdh, fdm, _ = map(int, first_dep_time.split(':')[:2])
                            tah, tam, _ = map(int, third_arr_time.split(':')[:2])
                            total_dur = (tah * 60 + tam) - (fdh * 60 + fdm)
                        except: continue
                        
                        ta_name_row = stops[stops["stop_id"] == t_a_id]
                        ta_name = str(ta_name_row.iloc[0]["stop_name"]) if not ta_name_row.empty else t_a_id
                        tb_name_row = stops[stops["stop_id"] == t_b_id]
                        tb_name = str(tb_name_row.iloc[0]["stop_name"]) if not tb_name_row.empty else t_b_id

                        print(f"\\n[TRANSFER_A]\\n{ta_name}\\n{wait1}")
                        print(f"\\n[TRANSFER_B]\\n{tb_name}\\n{wait2}")
                        print(f"\\n[ROUTE_FOUND]\\n{total_dur}\\n2")

                        seen_transfer_triplets.add(dedupe_key)
                        
                        l1_route_id = trips[trips["trip_id"] == leg1_trip_id].iloc[0]["route_id"]
                        l2_route_id = trips[trips["trip_id"] == leg2_trip_id].iloc[0]["route_id"]
                        l3_route_id = trips[trips["trip_id"] == leg3_trip_id].iloc[0]["route_id"]
                        
                        def get_r_name(r_id):
                            rt = routes[routes["route_id"] == r_id].iloc[0]
                            short = rt.get("route_short_name", "")
                            long_n = rt.get("route_long_name", "")
                            return str(long_n) if pd.notna(long_n) and long_n else str(short)
                            
                        l1_rname = get_r_name(l1_route_id)
                        l2_rname = get_r_name(l2_route_id)
                        l3_rname = get_r_name(l3_route_id)
                        
                        leg1 = JourneyRoute(
                            journey_type=JourneyType.DIRECT, feed=feed_name,
                            trip_id=str(leg1_trip_id), route_id=str(l1_route_id), route_name=l1_rname,
                            source_stop=str(source_name), destination_stop=str(ta_name),
                            stops_between=int(leg1_arr_row["stop_sequence"]) - int(leg1_arr_row["stop_sequence_source"]),
                            departure_time=first_dep_time, arrival_time=arr1_time,
                            departure_display=parse_gtfs_time_to_display(first_dep_time),
                            arrival_display=parse_gtfs_time_to_display(arr1_time),
                            duration_minutes=a1_total - (fdh*60+fdm)
                        )
                        leg2 = JourneyRoute(
                            journey_type=JourneyType.DIRECT, feed=feed_name,
                            trip_id=str(leg2_trip_id), route_id=str(l2_route_id), route_name=l2_rname,
                            source_stop=str(ta_name), destination_stop=str(tb_name),
                            stops_between=int(leg2_row["stop_sequence_B"]) - int(leg2_row["stop_sequence_A"]),
                            departure_time=dep2_time, arrival_time=arr2_time,
                            departure_display=parse_gtfs_time_to_display(dep2_time),
                            arrival_display=parse_gtfs_time_to_display(arr2_time),
                            duration_minutes=a2_total - d2_total
                        )
                        leg3 = JourneyRoute(
                            journey_type=JourneyType.DIRECT, feed=feed_name,
                            trip_id=str(leg3_trip_id), route_id=str(l3_route_id), route_name=l3_rname,
                            source_stop=str(tb_name), destination_stop=str(dest_name),
                            stops_between=int(leg3_dep_row["stop_sequence_dest"]) - int(leg3_dep_row["stop_sequence"]),
                            departure_time=dep3_time, arrival_time=third_arr_time,
                            departure_display=parse_gtfs_time_to_display(dep3_time),
                            arrival_display=parse_gtfs_time_to_display(third_arr_time),
                            duration_minutes=tah*60+tam - d3_total
                        )
                        
                        transfer_journeys.append(TransferJourney(
                            journey_type=JourneyType.TRANSFER,
                            transfer_stop=ta_name,
                            first_leg=leg1,
                            second_leg=leg2,
                            total_duration=total_dur,
                            transfer_wait=wait1,
                            third_leg=leg3,
                            transfer_stop_2=tb_name,
                            transfer_wait_2=wait2
                        ))
                        
                        if len(seen_transfer_triplets) >= MAX_TRANSFER_CANDIDATES: break
                    if len(seen_transfer_triplets) >= MAX_TRANSFER_CANDIDATES: break
                if len(seen_transfer_triplets) >= MAX_TRANSFER_CANDIDATES: break
                        
        transfer_journeys.sort(key=lambda j: (
            j.third_leg.arrival_time if getattr(j, 'third_leg', None) and getattr(j.third_leg, 'arrival_time', None) else "99:99:99",
            j.total_duration
        ))
        
        return transfer_journeys[:MAX_RETURNED_ROUTES]
"""

target = r"c:\Users\jagan\Desktop\clutch\new project - transit\backend\app\services\transit_service.py"
with open(target, "r", encoding="utf-8") as f:
    code = f.read()

parts = code.split("    def get_trip_stops(self, feed_name: str, trip_id: str) -> list[\"TripStop\"]:")
if len(parts) == 2:
    new_code = parts[0] + patch_content + "\\n    def get_trip_stops(self, feed_name: str, trip_id: str) -> list[\"TripStop\"]:" + parts[1]
    with open(target, "w", encoding="utf-8") as f:
        f.write(new_code)
    print("Patched successfully")
else:
    print("Could not find insertion point")
