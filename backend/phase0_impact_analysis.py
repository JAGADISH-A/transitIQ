"""
PHASE 0 — Station Complex Impact Analysis
==========================================
For each proposed complex, calculate:
  1. Routes that become UNLOCKED (previously failing, now possible)
  2. New reachable destinations added per complex
  3. False positive risk assessment
  4. Network statistics

NO routing engine changes. Read-only data analysis.
"""

import pandas as pd
import sys, os

sys.path.insert(0, ".")

from app.utils.geo_utils import haversine

DATA_PATH = "data/railways"

# ---------------------------------------------------------------------------
# Load GTFS tables
# ---------------------------------------------------------------------------
print("Loading GTFS data...")
stop_times = pd.read_csv(f"{DATA_PATH}/stop_times.txt")
trips      = pd.read_csv(f"{DATA_PATH}/trips.txt")
routes     = pd.read_csv(f"{DATA_PATH}/routes.txt")
stops      = pd.read_csv(f"{DATA_PATH}/stops.txt")

print(f"  Stops: {len(stops):,}")
print(f"  Trips: {len(trips):,}")
print(f"  Stop times: {len(stop_times):,}")

# ---------------------------------------------------------------------------
# Helper: Get all stops reachable FROM a given stop_id
#   (any stop that appears AFTER stop_id on the same trip)
# ---------------------------------------------------------------------------
def stops_reachable_from(stop_id: str) -> set[str]:
    """All stop_ids reachable AFTER stop_id (forward direction)."""
    origin_st = stop_times[stop_times["stop_id"] == stop_id][["trip_id", "stop_sequence"]]
    if origin_st.empty:
        return set()
    # Join with all stop_times to find stops that are AFTER on the same trip
    merged = stop_times.merge(origin_st, on="trip_id", suffixes=("", "_origin"))
    after = merged[merged["stop_sequence"].astype(int) > merged["stop_sequence_origin"].astype(int)]
    return set(after["stop_id"].unique())


def stops_that_can_reach(stop_id: str) -> set[str]:
    """All stop_ids that can reach stop_id (backward direction — stops BEFORE stop_id)."""
    dest_st = stop_times[stop_times["stop_id"] == stop_id][["trip_id", "stop_sequence"]]
    if dest_st.empty:
        return set()
    merged = stop_times.merge(dest_st, on="trip_id", suffixes=("", "_dest"))
    before = merged[merged["stop_sequence"].astype(int) < merged["stop_sequence_dest"].astype(int)]
    return set(before["stop_id"].unique())


def stop_name(stop_id: str) -> str:
    row = stops[stops["stop_id"] == stop_id]
    return str(row.iloc[0]["stop_name"]) if not row.empty else stop_id


def stop_coords(stop_id: str) -> tuple[float, float] | None:
    row = stops[stops["stop_id"] == stop_id]
    if row.empty:
        return None
    try:
        return float(row.iloc[0]["stop_lat"]), float(row.iloc[0]["stop_lon"])
    except (ValueError, TypeError):
        return None


def route_count_for_stop(stop_id: str) -> int:
    st = stop_times[stop_times["stop_id"] == stop_id]
    if st.empty:
        return 0
    trip_ids = set(st["trip_id"])
    route_ids = set(trips[trips["trip_id"].isin(trip_ids)]["route_id"])
    return len(route_ids)


# ---------------------------------------------------------------------------
# Complex definitions
# ---------------------------------------------------------------------------
COMPLEXES = [
    {
        "complex_id": "MSB_MS",
        "label": "MSB ↔ MS (Chennai Beach ↔ Chennai Egmore)",
        "stop_a": "MSB",
        "stop_b": "MS",
        "walk_time_min": 10,
        "walk_m": 950,
    },
    {
        "complex_id": "MAS_MASS",
        "label": "MAS ↔ MASS (Chennai Central ↔ Chennai Central Suburban)",
        "stop_a": "MAS",
        "stop_b": "MASS",
        "walk_time_min": 5,
        "walk_m": 400,
    },
    {
        "complex_id": "NCJ_NJT",
        "label": "NCJ ↔ NJT (Nagercoil Junction ↔ Nagercoil Town)",
        "stop_a": "NCJ",
        "stop_b": "NJT",
        "walk_time_min": 30,
        "walk_m": 2500,
    },
]

SEPARATOR = "=" * 72


# ---------------------------------------------------------------------------
# Test routes: things that currently FAIL and SHOULD work after walk transfer
# ---------------------------------------------------------------------------
EXPECTED_UNLOCKS = [
    ("HC",  "NJT", "Hindu College → Nagercoil Town"),
    ("HC",  "MDU", "Hindu College → Madurai"),
    ("HC",  "TEN", "Hindu College → Tirunelveli"),
    ("HC",  "SA",  "Hindu College → Salem"),
    ("HC",  "CBE", "Hindu College → Coimbatore"),
    ("PRBL","NJT", "Perambur Loco Works → Nagercoil Town"),
    ("MBM", "NJT", "Mambalam → Nagercoil Town"),
]


def can_route_direct(src: str, dst: str) -> bool:
    """Returns True if src→dst is directly routable (no transfer needed)."""
    src_st = stop_times[stop_times["stop_id"] == src][["trip_id", "stop_sequence"]]
    dst_st = stop_times[stop_times["stop_id"] == dst][["trip_id", "stop_sequence"]]
    if src_st.empty or dst_st.empty:
        return False
    merged = src_st.merge(dst_st, on="trip_id", suffixes=("_s", "_d"))
    valid = merged[merged["stop_sequence_s"].astype(int) < merged["stop_sequence_d"].astype(int)]
    return not valid.empty


def can_route_via_transfer(src: str, dst: str) -> bool:
    """Returns True if src→dst is routable with exactly one same-stop transfer."""
    src_fwd = stops_reachable_from(src)
    dst_bwd = stops_that_can_reach(dst)
    return bool(src_fwd.intersection(dst_bwd))


def can_route_via_walk_transfer(src: str, dst: str, walk_bridge: dict[str, str]) -> bool:
    """
    Returns True if src→dst is routable using one walk bridge.
    walk_bridge: { stop_a → stop_b, stop_b → stop_a }
    """
    src_fwd = stops_reachable_from(src)
    dst_bwd = stops_that_can_reach(dst)

    # Direct transfer (no walking needed)
    if src_fwd.intersection(dst_bwd):
        return True

    # Expand src_fwd through walk bridge
    expanded_src_fwd = set(src_fwd)
    for stop_id in src_fwd:
        if stop_id in walk_bridge:
            expanded_src_fwd.add(walk_bridge[stop_id])

    return bool(expanded_src_fwd.intersection(dst_bwd))


# ===========================================================================
print()
print(SEPARATOR)
print("  PHASE 0 — STATION COMPLEX IMPACT ANALYSIS")
print(SEPARATOR)

for cx in COMPLEXES:
    a, b = cx["stop_a"], cx["stop_b"]
    label = cx["label"]

    print()
    print(SEPARATOR)
    print(f"  COMPLEX: {label}")
    print(SEPARATOR)

    # --- Existence check ---
    a_exists = a in stops["stop_id"].values
    b_exists = b in stops["stop_id"].values
    print(f"\n  Stop Existence:")
    print(f"    {a} ({stop_name(a)}): {'✓ EXISTS' if a_exists else '✗ NOT FOUND'}")
    print(f"    {b} ({stop_name(b)}): {'✓ EXISTS' if b_exists else '✗ NOT FOUND'}")

    if not a_exists or not b_exists:
        print(f"\n  ⚠ Cannot analyse — one or both stops missing from feed.")
        continue

    # --- Physical distance verification ---
    coords_a = stop_coords(a)
    coords_b = stop_coords(b)
    if coords_a and coords_b:
        dist_km = haversine(coords_a[0], coords_a[1], coords_b[0], coords_b[1])
        print(f"\n  Physical Distance: {dist_km*1000:.0f}m ({dist_km:.3f} km)")
        print(f"  Configured Walk: {cx['walk_m']}m / {cx['walk_time_min']} minutes")
        if dist_km * 1000 > cx["walk_m"] * 2:
            print(f"  ⚠ WARNING: Configured distance ({cx['walk_m']}m) is much smaller than actual ({dist_km*1000:.0f}m)")
    else:
        print(f"\n  Physical Distance: Could not compute (missing coordinates)")

    # --- Current route counts ---
    routes_from_a = route_count_for_stop(a)
    routes_from_b = route_count_for_stop(b)
    print(f"\n  Current Route Coverage:")
    print(f"    {a} ({stop_name(a)}): {routes_from_a} routes")
    print(f"    {b} ({stop_name(b)}): {routes_from_b} routes")

    # --- Reachable stop sets ---
    print(f"\n  Computing reachable stop sets (this may take a moment)...")
    fwd_a = stops_reachable_from(a)
    fwd_b = stops_reachable_from(b)
    bwd_a = stops_that_can_reach(a)
    bwd_b = stops_that_can_reach(b)

    print(f"    Stops reachable FROM {a}: {len(fwd_a)}")
    print(f"    Stops reachable FROM {b}: {len(fwd_b)}")
    print(f"    Stops that can reach {a}: {len(bwd_a)}")
    print(f"    Stops that can reach {b}: {len(bwd_b)}")

    # --- New destinations unlocked ---
    # If a passenger walks A→B, they gain access to everything reachable from B
    # that was NOT already reachable from A
    new_from_a = fwd_b - fwd_a - {a, b}
    new_from_b = fwd_a - fwd_b - {a, b}

    print(f"\n  New Destinations Unlocked:")
    print(f"    Via {a}→walk→{b}: {len(new_from_a)} additional stops")
    if new_from_a:
        sample = list(new_from_a)[:10]
        for s in sample:
            print(f"      → {s} ({stop_name(s)})")
        if len(new_from_a) > 10:
            print(f"      ... and {len(new_from_a)-10} more")

    print(f"    Via {b}→walk→{a}: {len(new_from_b)} additional stops")
    if new_from_b:
        sample = list(new_from_b)[:10]
        for s in sample:
            print(f"      → {s} ({stop_name(s)})")
        if len(new_from_b) > 10:
            print(f"      ... and {len(new_from_b)-10} more")

    # --- Sources that GAIN access ---
    # Stops that can reach A but not B (gain B's destinations after walk)
    sources_gain_via_a = bwd_a - bwd_b - {a, b}
    sources_gain_via_b = bwd_b - bwd_a - {a, b}
    print(f"\n  Source Stops That Gain New Connectivity:")
    print(f"    Stops that can reach {a} but NOT {b}: {len(sources_gain_via_a)} sources gain access via {a}→walk→{b}")
    print(f"    Stops that can reach {b} but NOT {a}: {len(sources_gain_via_b)} sources gain access via {b}→walk→{a}")

    # Show sample of most significant sources
    if sources_gain_via_a:
        sample = list(sources_gain_via_a)[:8]
        for s in sample:
            print(f"      ← {s} ({stop_name(s)})")

print()
print(SEPARATOR)
print("  EXPECTED ROUTE UNLOCKS — Test Cases")
print(SEPARATOR)
print()

# Build the walk bridge from all complexes
walk_bridge: dict[str, str] = {}
for cx in COMPLEXES:
    walk_bridge[cx["stop_a"]] = cx["stop_b"]
    walk_bridge[cx["stop_b"]] = cx["stop_a"]

print(f"  {'Route':<45} {'Direct':>8} {'1-Transfer':>12} {'Walk-Transfer':>15} {'Status'}")
print(f"  {'-'*45} {'-'*8} {'-'*12} {'-'*15} {'-'*20}")

for src, dst, label in EXPECTED_UNLOCKS:
    src_exists = src in stops["stop_id"].values
    dst_exists = dst in stops["stop_id"].values

    if not src_exists or not dst_exists:
        status = "STOP MISSING"
        print(f"  {label:<45} {'?':>8} {'?':>12} {'?':>15} {status}")
        continue

    direct    = can_route_direct(src, dst)
    transfer  = can_route_via_transfer(src, dst)
    walk_xfer = can_route_via_walk_transfer(src, dst, walk_bridge)

    if direct:
        status = "✓ ALREADY WORKS (direct)"
    elif transfer:
        status = "✓ ALREADY WORKS (transfer)"
    elif walk_xfer:
        status = "🆕 NEWLY UNLOCKED"
    else:
        status = "✗ STILL FAILS"

    print(f"  {label:<45} {'✓' if direct else '✗':>8} {'✓' if transfer else '✗':>12} {'✓' if walk_xfer else '✗':>15}  {status}")


print()
print(SEPARATOR)
print("  FALSE POSITIVE RISK ASSESSMENT")
print(SEPARATOR)
print()
print("  False positives = routes that technically appear valid via walking but")
print("  are not operationally sensible (too far, wrong direction, etc.)")
print()

for cx in COMPLEXES:
    a, b = cx["stop_a"], cx["stop_b"]
    if a not in stops["stop_id"].values or b not in stops["stop_id"].values:
        continue

    coords_a = stop_coords(a)
    coords_b = stop_coords(b)
    dist_m = haversine(coords_a[0], coords_a[1], coords_b[0], coords_b[1]) * 1000 if (coords_a and coords_b) else 0

    risk = "LOW"
    reasons = []

    if dist_m > 2000:
        risk = "MEDIUM"
        reasons.append(f"distance {dist_m:.0f}m > 2km (requires auto/taxi, not true walking)")
    if cx["walk_time_min"] > 20:
        risk = "MEDIUM"
        reasons.append(f"walk time {cx['walk_time_min']} min is significant")
    if dist_m > 5000:
        risk = "HIGH"
        reasons.append(f"distance {dist_m:.0f}m > 5km (operationally implausible as a walk)")

    if not reasons:
        reasons.append("short distance, well-established interchange")

    print(f"  {cx['complex_id']}: Risk={risk}")
    for r in reasons:
        print(f"    • {r}")

print()
print(SEPARATOR)
print("  SUMMARY")
print(SEPARATOR)
