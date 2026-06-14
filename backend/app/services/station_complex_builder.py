"""Station Complex Builder for TransitIQ.

Scans the railways GTFS feed and groups nearby stops into station complexes.
A complex is a set of stops within a configurable radius that passengers can
reasonably walk between to change services.

Usage (standalone):
    python -m app.services.station_complex_builder

Output:
    backend/data/railways/station_complexes.json
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

import pandas as pd

from app.utils.geo_utils import haversine

logger = logging.getLogger(__name__)

# Walking speed: ~5 km/h → 83 m/min
# Average walking time for 1 km = 12 minutes
WALK_SPEED_M_PER_MIN = 83.3
MAX_WALK_RADIUS_KM = 1.0  # Only group stops within 1 km

# Manually confirmed complexes (ground-truth seeds).
# These override distance-based grouping with accurate walk times.
SEED_COMPLEXES: list[dict] = [
    {
        "complex_id": "CHENNAI_BEACH_EGMORE",
        "description": "Chennai Beach <-> Chennai Egmore (~3.67km, ~18 min auto/walk)",
        "stops": ["MSB", "MS"],
        "walk_time_minutes": 18,
        "walk_distance_m": 3670,
    },
    {
        "complex_id": "CHENNAI_CENTRAL_SUBURBAN",
        "description": "Chennai Central ↔ Chennai Central Suburban (~400m walk)",
        "stops": ["MAS", "MASS"],
        "walk_time_minutes": 5,
        "walk_distance_m": 400,
    },
    {
        "complex_id": "NAGERCOIL_COMPLEX",
        "description": "Nagercoil Junction <-> Nagercoil Town (~3.86km, ~30 min auto)",
        "stops": ["NCJ", "NJT"],
        "walk_time_minutes": 30,
        "walk_distance_m": 3863,
    },
    {
        "complex_id": "TAMBARAM_COMPLEX",
        "description": "Tambaram ↔ Tambaram East (~300m walk)",
        "stops": ["TBM", "TBME"],
        "walk_time_minutes": 4,
        "walk_distance_m": 300,
    },
    {
        "complex_id": "PERAMBUR_COMPLEX",
        "description": "Perambur ↔ Perambur Loco Works (~600m walk)",
        "stops": ["PER", "PRBL"],
        "walk_time_minutes": 7,
        "walk_distance_m": 600,
    },
]


@dataclass
class StationComplex:
    complex_id: str
    description: str
    stops: list[str]
    walk_time_minutes: int
    walk_distance_m: int
    is_seed: bool = False


def build_complexes(stops_df: pd.DataFrame) -> list[StationComplex]:
    """Build station complexes from a stops DataFrame.

    Seeds are merged first, then auto-discovery adds any remaining
    proximity clusters not already covered.

    Args:
        stops_df: DataFrame with columns [stop_id, stop_name, stop_lat, stop_lon].

    Returns:
        List of StationComplex objects, sorted by complex_id.
    """
    complexes: list[StationComplex] = []
    covered_stops: set[str] = set()

    # --- Step 1: Add seed complexes (ground-truth) ---
    for seed in SEED_COMPLEXES:
        # Only include stops that actually exist in this feed
        present = [s for s in seed["stops"] if s in stops_df["stop_id"].values]
        if len(present) < 2:
            logger.debug("Seed complex '%s': only %d stop(s) found in feed, skipping", seed["complex_id"], len(present))
            continue

        complexes.append(StationComplex(
            complex_id=seed["complex_id"],
            description=seed["description"],
            stops=present,
            walk_time_minutes=seed["walk_time_minutes"],
            walk_distance_m=seed["walk_distance_m"],
            is_seed=True,
        ))
        covered_stops.update(present)
        logger.info("Added seed complex '%s': %s", seed["complex_id"], present)

    # --- Step 2: Auto-discover proximity clusters ---
    # Build a coordinate lookup for remaining stops
    remaining = stops_df[~stops_df["stop_id"].isin(covered_stops)].copy()
    remaining = remaining.dropna(subset=["stop_lat", "stop_lon"])

    try:
        remaining["stop_lat"] = remaining["stop_lat"].astype(float)
        remaining["stop_lon"] = remaining["stop_lon"].astype(float)
    except (ValueError, TypeError):
        logger.warning("Could not convert stop coordinates to float, skipping auto-discovery")
        return complexes

    stop_rows = remaining.to_dict("records")
    visited: set[str] = set()

    for i, stop_a in enumerate(stop_rows):
        if stop_a["stop_id"] in visited:
            continue

        cluster = [stop_a["stop_id"]]
        for j, stop_b in enumerate(stop_rows):
            if i == j or stop_b["stop_id"] in visited:
                continue
            dist = haversine(
                float(stop_a["stop_lat"]), float(stop_a["stop_lon"]),
                float(stop_b["stop_lat"]), float(stop_b["stop_lon"]),
            )
            if dist <= MAX_WALK_RADIUS_KM:
                cluster.append(stop_b["stop_id"])

        if len(cluster) >= 2:
            # Estimate walk distance as average pairwise distance
            total_dist_km = 0.0
            pairs = 0
            for p in range(len(cluster)):
                for q in range(p + 1, len(cluster)):
                    row_p = remaining[remaining["stop_id"] == cluster[p]].iloc[0]
                    row_q = remaining[remaining["stop_id"] == cluster[q]].iloc[0]
                    d = haversine(float(row_p["stop_lat"]), float(row_p["stop_lon"]),
                                  float(row_q["stop_lat"]), float(row_q["stop_lon"]))
                    total_dist_km += d
                    pairs += 1

            avg_dist_m = int((total_dist_km / pairs) * 1000) if pairs else 500
            walk_time = max(3, int(avg_dist_m / WALK_SPEED_M_PER_MIN))

            complex_id = f"AUTO_{cluster[0]}_{'_'.join(cluster[1:])}"
            complexes.append(StationComplex(
                complex_id=complex_id,
                description=f"Auto-discovered cluster: {', '.join(cluster)}",
                stops=cluster,
                walk_time_minutes=walk_time,
                walk_distance_m=avg_dist_m,
                is_seed=False,
            ))
            visited.update(cluster)
            logger.debug("Auto-discovered complex '%s': %s (avg ~%dm walk)", complex_id, cluster, avg_dist_m)

    complexes.sort(key=lambda c: c.complex_id)
    return complexes


def build_walk_lookup(complexes: list[StationComplex]) -> dict[str, list[dict]]:
    """Build a bidirectional stop_id → list[{mate_stop_id, walk_time, walk_distance}] mapping.

    This is the runtime lookup used by the routing engine during transfer search.

    Args:
        complexes: List of StationComplex objects.

    Returns:
        Dict mapping each stop_id to its list of walkable mates.
    """
    lookup: dict[str, list[dict]] = {}

    for cx in complexes:
        for stop_a in cx.stops:
            for stop_b in cx.stops:
                if stop_a == stop_b:
                    continue
                if stop_a not in lookup:
                    lookup[stop_a] = []
                lookup[stop_a].append({
                    "mate_stop_id": stop_b,
                    "walk_time_minutes": cx.walk_time_minutes,
                    "walk_distance_m": cx.walk_distance_m,
                    "complex_id": cx.complex_id,
                })

    return lookup


def save_complexes(complexes: list[StationComplex], output_path: str) -> None:
    """Serialize station complexes to JSON.

    Args:
        complexes: List of StationComplex to serialize.
        output_path: Absolute path to output JSON file.
    """
    data = []
    for cx in complexes:
        data.append({
            "complex_id": cx.complex_id,
            "description": cx.description,
            "stops": cx.stops,
            "walk_time_minutes": cx.walk_time_minutes,
            "walk_distance_m": cx.walk_distance_m,
            "is_seed": cx.is_seed,
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d station complexes to %s", len(complexes), output_path)


def load_complexes(json_path: str) -> list[StationComplex]:
    """Load station complexes from JSON.

    Args:
        json_path: Path to station_complexes.json.

    Returns:
        List of StationComplex objects.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [
        StationComplex(
            complex_id=item["complex_id"],
            description=item.get("description", ""),
            stops=item["stops"],
            walk_time_minutes=item["walk_time_minutes"],
            walk_distance_m=item["walk_distance_m"],
            is_seed=item.get("is_seed", False),
        )
        for item in data
    ]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Resolve path to railway stops
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", ".."))
    stops_path = os.path.join(project_root, "data", "railways", "stops.txt")
    output_path = os.path.join(project_root, "data", "railways", "station_complexes.json")

    if not os.path.exists(stops_path):
        print(f"ERROR: stops.txt not found at {stops_path}")
        sys.exit(1)

    stops_df = pd.read_csv(stops_path)
    print(f"Loaded {len(stops_df)} stops from {stops_path}")

    complexes = build_complexes(stops_df)

    print(f"\n=== Station Complexes ({len(complexes)} total) ===")
    walk_pairs = 0
    for cx in complexes:
        tag = "[SEED]" if cx.is_seed else "[AUTO]"
        print(f"  {tag} {cx.complex_id}: {cx.stops} — {cx.walk_time_minutes} min walk, {cx.walk_distance_m}m")
        walk_pairs += len(cx.stops) * (len(cx.stops) - 1)

    print(f"\nTotal bidirectional walk edges: {walk_pairs}")

    save_complexes(complexes, output_path)
    print(f"\nSaved to: {output_path}")
