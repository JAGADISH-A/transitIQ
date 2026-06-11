import os
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)

print("\n--- 1. VERIFYING RAW GTFS FILES ---")

# Load GTFS files directly
stops_path = os.path.join("data", "railways", "stops.txt")
stop_times_path = os.path.join("data", "railways", "stop_times.txt")
trips_path = os.path.join("data", "railways", "trips.txt")

stops_df = pd.read_csv(stops_path, dtype=str)
stop_times_df = pd.read_csv(stop_times_path, dtype=str)
trips_df = pd.read_csv(trips_path, dtype=str)

# Verify MS
ms_stops = stops_df[stops_df['stop_id'] == 'MS']
ms_st = stop_times_df[stop_times_df['stop_id'] == 'MS']
print(f"MS in stops.txt: {len(ms_stops)} records. Names: {ms_stops['stop_name'].tolist() if not ms_stops.empty else 'None'}")
print(f"MS in stop_times.txt: {len(ms_st)} records.")

# Verify MASS
mass_stops = stops_df[stops_df['stop_id'] == 'MASS']
mass_st = stop_times_df[stop_times_df['stop_id'] == 'MASS']
print(f"MASS in stops.txt: {len(mass_stops)} records. Names: {mass_stops['stop_name'].tolist() if not mass_stops.empty else 'None'}")
print(f"MASS in stop_times.txt: {len(mass_st)} records.")

# Check for trips containing both
ms_trips = set(ms_st['trip_id'].tolist())
mass_trips = set(mass_st['trip_id'].tolist())

common_trips = ms_trips.intersection(mass_trips)
print(f"Trips containing BOTH MS and MASS: {len(common_trips)}")
if common_trips:
    print(f"Example common trips: {list(common_trips)[:5]}")
else:
    print("NO TRIPS CONTAIN BOTH STOPS.")

print("\n--- 2. RUNNING ROUTING DIAGNOSTICS ---")
from app.services.transit_service import transit_service
transit_service.load_all_feeds("./data")
result = transit_service.find_trip("MS", "MASS")
print(f"Result count: {len(result.results)}")
