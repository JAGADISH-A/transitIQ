"""TransitIQ Nationwide Coverage Investigation.

Audits the railway GTFS routing graph and traces specific journey failures
to identify root causes for routing gaps.
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Force UTF-8 for Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

DATA_ROOT = os.path.join(os.path.dirname(__file__), "data")
RAILWAYS_PATH = os.path.join(DATA_ROOT, "railways")

# Test cases: (source_code, dest_code, source_name_hint, dest_name_hint)
FAILED_JOURNEYS = [
    ("HC", "NJT", "Hindu College", "Nagercoil Town"),
    ("HC", "TEN", "Hindu College", "Tirunelveli"),
    ("HC", "MDU", "Hindu College", "Madurai"),
    ("HC", "SBC", "Hindu College", "Bangalore"),
    ("HC", "BNC", "Hindu College", "Bangalore Cantonment"),
]


def load_railway_gtfs():
    """Load raw GTFS CSVs for the railways feed."""
    stops = pd.read_csv(os.path.join(RAILWAYS_PATH, "stops.txt"), dtype=str)
    routes = pd.read_csv(os.path.join(RAILWAYS_PATH, "routes.txt"), dtype=str)
    trips = pd.read_csv(os.path.join(RAILWAYS_PATH, "trips.txt"), dtype=str)
    stop_times = pd.read_csv(os.path.join(RAILWAYS_PATH, "stop_times.txt"), dtype=str)
    return stops, routes, trips, stop_times


def audit_graph(stops, routes, trips, stop_times):
    """Audit the railway routing graph for connectivity."""
    print("=" * 80)
    print("SECTION 1: RAILWAY GRAPH AUDIT")
    print("=" * 80)

    total_stops = len(stops)
    total_routes = len(routes)
    total_trips = len(trips)
    total_stop_times = len(stop_times)

    print(f"\n--- Raw GTFS Counts ---")
    print(f"  Stops:      {total_stops:,}")
    print(f"  Routes:     {total_routes:,}")
    print(f"  Trips:      {total_trips:,}")
    print(f"  Stop_times: {total_stop_times:,}")

    # Build adjacency: which stops are connected by at least one trip?
    # Two stops are "connected" if they appear on the same trip.
    print(f"\n--- Building Stop Adjacency Graph ---")

    # For each trip, get the ordered list of stops
    stop_times_sorted = stop_times.sort_values(["trip_id", "stop_sequence"])

    # Build adjacency set: stop_id -> set of stop_ids reachable on same trip
    adjacency = defaultdict(set)
    stops_served = set()

    # Group by trip and connect consecutive stops
    trip_groups = stop_times_sorted.groupby("trip_id")["stop_id"]
    for trip_id, stop_ids in trip_groups:
        stop_list = stop_ids.tolist()
        stops_served.update(stop_list)
        for i in range(len(stop_list) - 1):
            adjacency[stop_list[i]].add(stop_list[i + 1])
            adjacency[stop_list[i + 1]].add(stop_list[i])

    stops_in_graph = len(adjacency)
    stops_not_in_graph = total_stops - stops_in_graph
    total_edges = sum(len(v) for v in adjacency.values()) // 2

    print(f"  Stops served by trips: {len(stops_served):,}")
    print(f"  Stops in adjacency graph: {stops_in_graph:,}")
    print(f"  Stops with NO trips: {stops_not_in_graph:,}")
    print(f"  Total edges (stop pairs): {total_edges:,}")

    # Connected components analysis (BFS)
    print(f"\n--- Connected Components Analysis ---")
    visited = set()
    components = []

    for stop_id in adjacency:
        if stop_id in visited:
            continue
        # BFS
        component = set()
        queue = [stop_id]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    queue.append(neighbor)
        components.append(component)

    components.sort(key=len, reverse=True)
    print(f"  Total connected components: {len(components)}")

    # Show top 10 components
    stop_name_map = dict(zip(stops["stop_id"], stops["stop_name"]))
    for i, comp in enumerate(components[:10]):
        sample_names = [stop_name_map.get(sid, sid) for sid in list(comp)[:5]]
        print(f"  Component {i+1}: {len(comp):,} stops — samples: {', '.join(sample_names)}")

    if len(components) > 10:
        remaining = sum(len(c) for c in components[10:])
        print(f"  ... + {len(components) - 10} more components ({remaining} stops total)")

    largest = components[0] if components else set()
    print(f"\n  Largest component: {len(largest):,} stops ({len(largest)/stops_in_graph*100:.1f}% of served stops)")

    # Top 50 transfer hubs (most connected stops)
    print(f"\n--- Top 50 Transfer Hubs (Most Connected Stops) ---")
    hub_scores = [(sid, len(neighbors)) for sid, neighbors in adjacency.items()]
    hub_scores.sort(key=lambda x: x[1], reverse=True)

    for rank, (sid, degree) in enumerate(hub_scores[:50], 1):
        name = stop_name_map.get(sid, sid)
        print(f"  {rank:3d}. {sid:10s} | {name:40s} | {degree} connections")

    return adjacency, components, stop_name_map, stops_served


def trace_journey_failure(source_code, dest_code, source_hint, dest_hint,
                          stops, routes, trips, stop_times,
                          adjacency, components, stop_name_map):
    """Trace exactly where routing fails for a specific journey."""
    print(f"\n{'=' * 80}")
    print(f"TRACE: {source_code} ({source_hint}) → {dest_code} ({dest_hint})")
    print(f"{'=' * 80}")

    # Step 1: Find matching stop IDs
    source_matches = stops[stops["stop_id"].str.upper() == source_code.upper()]
    dest_matches = stops[stops["stop_id"].str.upper() == dest_code.upper()]

    # Also try partial name match
    if source_matches.empty:
        source_matches = stops[stops["stop_name"].str.contains(source_hint, case=False, na=False)]
    if dest_matches.empty:
        dest_matches = stops[stops["stop_name"].str.contains(dest_hint, case=False, na=False)]

    print(f"\n  Source matches for '{source_code}':")
    if source_matches.empty:
        print(f"    ❌ NO STOP FOUND — this is a stop resolution failure")
        return "STOP_NOT_FOUND"
    for _, row in source_matches.iterrows():
        print(f"    ✓ {row['stop_id']} — {row['stop_name']}")

    print(f"\n  Destination matches for '{dest_code}':")
    if dest_matches.empty:
        print(f"    ❌ NO STOP FOUND — this is a stop resolution failure")
        return "STOP_NOT_FOUND"
    for _, row in dest_matches.iterrows():
        print(f"    ✓ {row['stop_id']} — {row['stop_name']}")

    src_id = source_matches.iloc[0]["stop_id"]
    dst_id = dest_matches.iloc[0]["stop_id"]

    # Step 2: Check which component each stop is in
    src_component = None
    dst_component = None
    for i, comp in enumerate(components):
        if src_id in comp:
            src_component = i
        if dst_id in comp:
            dst_component = i

    print(f"\n  Component membership:")
    if src_component is not None:
        print(f"    Source {src_id}: Component {src_component + 1} ({len(components[src_component])} stops)")
    else:
        print(f"    Source {src_id}: ❌ NOT IN ANY COMPONENT (no trips serve this stop)")

    if dst_component is not None:
        print(f"    Dest   {dst_id}: Component {dst_component + 1} ({len(components[dst_component])} stops)")
    else:
        print(f"    Dest   {dst_id}: ❌ NOT IN ANY COMPONENT (no trips serve this stop)")

    if src_component is not None and dst_component is not None and src_component != dst_component:
        print(f"    ⚠️  DISCONNECTED — stops are in different graph components!")
        print(f"       No amount of transfers can connect them within the current GTFS data.")
        return "DISCONNECTED_COMPONENTS"
    elif src_component is not None and dst_component is not None and src_component == dst_component:
        print(f"    ✓ Same component — theoretically reachable")

    # Step 3: Check direct routes
    print(f"\n  Direct route analysis:")
    src_trips = set(stop_times[stop_times["stop_id"] == src_id]["trip_id"])
    dst_trips = set(stop_times[stop_times["stop_id"] == dst_id]["trip_id"])
    common_trips = src_trips & dst_trips

    print(f"    Trips serving source: {len(src_trips)}")
    print(f"    Trips serving dest:   {len(dst_trips)}")
    print(f"    Common trips:         {len(common_trips)}")

    if common_trips:
        # Check direction
        valid_direction = 0
        for trip_id in list(common_trips)[:10]:
            trip_st = stop_times[stop_times["trip_id"] == trip_id]
            src_seq = trip_st[trip_st["stop_id"] == src_id]["stop_sequence"].astype(int).iloc[0]
            dst_seq = trip_st[trip_st["stop_id"] == dst_id]["stop_sequence"].astype(int).iloc[0]
            if src_seq < dst_seq:
                valid_direction += 1

        print(f"    Valid direction (src before dst): {valid_direction}/{min(len(common_trips), 10)} sampled")
        if valid_direction > 0:
            print(f"    ✓ DIRECT ROUTE EXISTS — routing engine should find this")
            return "DIRECT_EXISTS"
        else:
            print(f"    ⚠️  Common trips exist but ALL in wrong direction")
            return "WRONG_DIRECTION"
    else:
        print(f"    ❌ No direct route exists")

    # Step 4: Check 1-transfer possibility
    print(f"\n  1-transfer analysis:")
    src_reachable = set()
    for trip_id in src_trips:
        trip_stops = stop_times[stop_times["trip_id"] == trip_id]
        src_row = trip_stops[trip_stops["stop_id"] == src_id]
        if src_row.empty:
            continue
        src_seq = int(src_row.iloc[0]["stop_sequence"])
        downstream = trip_stops[trip_stops["stop_sequence"].astype(int) > src_seq]["stop_id"]
        src_reachable.update(downstream.tolist())

    dst_reachable = set()
    for trip_id in dst_trips:
        trip_stops = stop_times[stop_times["trip_id"] == trip_id]
        dst_row = trip_stops[trip_stops["stop_id"] == dst_id]
        if dst_row.empty:
            continue
        dst_seq = int(dst_row.iloc[0]["stop_sequence"])
        upstream = trip_stops[trip_stops["stop_sequence"].astype(int) < dst_seq]["stop_id"]
        dst_reachable.update(upstream.tolist())

    transfer_stops = src_reachable & dst_reachable

    print(f"    Stops reachable FROM source: {len(src_reachable)}")
    print(f"    Stops reachable TO dest:     {len(dst_reachable)}")
    print(f"    Common transfer stops:       {len(transfer_stops)}")

    if transfer_stops:
        # Show top transfer candidates
        sample = list(transfer_stops)[:10]
        print(f"    Transfer candidates (sample):")
        for sid in sample:
            name = stop_name_map.get(sid, sid)
            print(f"      • {sid} — {name}")
        print(f"    ✓ 1-TRANSFER ROUTE IS POSSIBLE — engine should find this")
        return "1_TRANSFER_POSSIBLE"
    else:
        print(f"    ❌ No 1-transfer route possible")

    # Step 5: Check 2-transfer possibility (via BFS on the component)
    print(f"\n  Multi-transfer analysis (BFS shortest path):")
    if src_component is not None and dst_component is not None and src_component == dst_component:
        # BFS from src to dst in adjacency graph
        from collections import deque
        visited_bfs = {src_id}
        queue_bfs = deque([(src_id, 0)])
        found = False
        while queue_bfs:
            node, depth = queue_bfs.popleft()
            if node == dst_id:
                print(f"    ✓ Reachable in {depth} hops (consecutive stop pairs)")
                found = True
                break
            if depth > 100:
                break
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited_bfs:
                    visited_bfs.add(neighbor)
                    queue_bfs.append((neighbor, depth + 1))

        if not found:
            print(f"    ❌ Not reachable within 100 hops")
            return "UNREACHABLE"

        # Now check what minimum transfers are needed
        # This requires checking trip overlap more carefully
        print(f"    → This journey requires 2+ transfers, which the engine does NOT support (1-transfer max)")
        return "NEEDS_MULTI_TRANSFER"
    else:
        print(f"    ❌ Cannot reach — different components or missing from graph")
        return "DISCONNECTED"


def summarize_failures(failure_results):
    """Summarize failure categories."""
    print(f"\n{'=' * 80}")
    print(f"SECTION 3: FAILURE SUMMARY")
    print(f"{'=' * 80}")

    categories = defaultdict(list)
    for journey, reason in failure_results:
        categories[reason].append(journey)

    for reason, journeys in sorted(categories.items()):
        print(f"\n  {reason}:")
        for j in journeys:
            print(f"    • {j[0]} → {j[1]} ({j[2]} → {j[3]})")


def main():
    print("TransitIQ Nationwide Coverage Investigation")
    print("=" * 80)
    print()

    stops, routes, trips, stop_times = load_railway_gtfs()

    # Ensure stop_sequence is sortable
    stop_times["stop_sequence"] = stop_times["stop_sequence"].astype(int)

    adjacency, components, stop_name_map, stops_served = audit_graph(stops, routes, trips, stop_times)

    # Section 2: Trace failed journeys
    print(f"\n{'=' * 80}")
    print(f"SECTION 2: FAILED JOURNEY TRACES")
    print(f"{'=' * 80}")

    failure_results = []
    for src_code, dst_code, src_hint, dst_hint in FAILED_JOURNEYS:
        reason = trace_journey_failure(
            src_code, dst_code, src_hint, dst_hint,
            stops, routes, trips, stop_times,
            adjacency, components, stop_name_map,
        )
        failure_results.append(((src_code, dst_code, src_hint, dst_hint), reason))

    summarize_failures(failure_results)

    # Section 4: Recommendation
    print(f"\n{'=' * 80}")
    print(f"SECTION 4: COVERAGE IMPROVEMENT RECOMMENDATIONS")
    print(f"{'=' * 80}")

    # Analyze what % of stop pairs are reachable with 1-transfer vs need 2+
    print(f"\n  Computing reachability statistics...")

    # For a random sample of stop pairs, check 1-transfer reachability
    import random
    served_list = list(stops_served)
    if len(served_list) > 200:
        sample_stops = random.sample(served_list, 200)
    else:
        sample_stops = served_list

    same_component_pairs = 0
    direct_pairs = 0
    one_transfer_pairs = 0
    unreachable_one_transfer = 0
    total_pairs_tested = 0

    # Build trip-to-stops mapping for faster lookup
    trip_to_stops = stop_times.groupby("trip_id")["stop_id"].apply(set).to_dict()
    stop_to_trips = defaultdict(set)
    for trip_id, sids in trip_to_stops.items():
        for sid in sids:
            stop_to_trips[sid].add(trip_id)

    for i in range(min(500, len(sample_stops) * (len(sample_stops) - 1) // 2)):
        s1, s2 = random.sample(sample_stops, 2)
        total_pairs_tested += 1

        # Same component?
        s1_comp = None
        s2_comp = None
        for ci, comp in enumerate(components):
            if s1 in comp:
                s1_comp = ci
            if s2 in comp:
                s2_comp = ci

        if s1_comp is not None and s2_comp is not None and s1_comp == s2_comp:
            same_component_pairs += 1
        else:
            continue

        # Direct?
        common = stop_to_trips[s1] & stop_to_trips[s2]
        if common:
            direct_pairs += 1
            continue

        # 1-transfer?
        s1_reachable_trips = stop_to_trips[s1]
        s1_reachable_stops = set()
        for tid in s1_reachable_trips:
            s1_reachable_stops.update(trip_to_stops[tid])

        s2_reachable_trips = stop_to_trips[s2]
        s2_reachable_stops = set()
        for tid in s2_reachable_trips:
            s2_reachable_stops.update(trip_to_stops[tid])

        transfer_candidates = s1_reachable_stops & s2_reachable_stops
        if transfer_candidates:
            one_transfer_pairs += 1
        else:
            unreachable_one_transfer += 1

    print(f"\n  Reachability Sample ({total_pairs_tested} random stop pairs):")
    print(f"    Same component:        {same_component_pairs} ({same_component_pairs/max(total_pairs_tested,1)*100:.1f}%)")
    print(f"    Direct route exists:   {direct_pairs} ({direct_pairs/max(total_pairs_tested,1)*100:.1f}%)")
    print(f"    1-transfer reachable:  {one_transfer_pairs} ({one_transfer_pairs/max(total_pairs_tested,1)*100:.1f}%)")
    print(f"    Needs 2+ transfers:    {unreachable_one_transfer} ({unreachable_one_transfer/max(total_pairs_tested,1)*100:.1f}%)")

    coverage_1t = (direct_pairs + one_transfer_pairs) / max(same_component_pairs, 1) * 100
    coverage_2t = same_component_pairs / max(total_pairs_tested, 1) * 100
    print(f"\n  Coverage with 1-transfer engine: {coverage_1t:.1f}% of same-component pairs")
    print(f"  Coverage with 2-transfer engine: would reach ~{coverage_2t:.1f}% of all tested pairs")
    print(f"  Gap (needs 2+ transfers):        {unreachable_one_transfer} pairs ({unreachable_one_transfer/max(same_component_pairs,1)*100:.1f}% of reachable)")

    print(f"\n  --- RECOMMENDATION ---")
    print(f"  The minimum backend change for maximum coverage improvement:")
    print(f"  → Implement a 2-transfer routing engine in find_transfer_routes()")
    print(f"  → This would cover journeys like HC→MDU, HC→TEN, HC→SBC")
    print(f"  → These fail because no single intermediate stop is served by")
    print(f"    both a train from HC AND a train to the destination.")
    print(f"  → A 2-transfer engine chains: HC→X (transfer) X→Y (transfer) Y→DEST")


if __name__ == "__main__":
    main()
