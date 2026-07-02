"""Audit script - station existence and search ranking analysis."""
import pandas as pd
import os
import sys
import re

data_root = "data"

# ---------------------------------------------------------------------------
# STEP 1 – Feed Audit
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 1 — FEED AUDIT")
print("=" * 70)
feeds = sorted([f for f in os.listdir(data_root) if os.path.isdir(os.path.join(data_root, f))])
print(f"Total feeds: {len(feeds)}")
print()
print(f"{'Feed':<20} {'Stops':>8} {'Trips':>8} {'Routes':>8}")
print("-" * 48)
for feed in feeds:
    fp = os.path.join(data_root, feed)
    try:
        stops = pd.read_csv(os.path.join(fp, "stops.txt"), dtype=str)
        trips = pd.read_csv(os.path.join(fp, "trips.txt"), dtype=str)
        routes = pd.read_csv(os.path.join(fp, "routes.txt"), dtype=str)
        print(f"{feed:<20} {len(stops):>8} {len(trips):>8} {len(routes):>8}")
    except Exception as e:
        print(f"{feed:<20} ERROR: {e}")

# ---------------------------------------------------------------------------
# STEP 2 – Station Existence Audit
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("STEP 2 — STATION EXISTENCE AUDIT (railways feed)")
print("=" * 70)

target_keywords = [
    "NAGERCOIL", "CHENNAI EGMORE", "CHENNAI CENTRAL",
    "SALEM", "MADURAI", "TIRUNELVELI", "BENGALURU", "KSR", "BANGALORE CANT"
]

for feed in feeds:
    fp = os.path.join(data_root, feed)
    try:
        stops = pd.read_csv(os.path.join(fp, "stops.txt"), dtype=str)
        for kw in target_keywords:
            mask = stops["stop_name"].str.upper().str.contains(kw.upper(), na=False)
            matched = stops[mask]
            for _, row in matched.iterrows():
                sid = str(row.get("stop_id", "")).strip()
                sname = str(row.get("stop_name", "")).strip()
                print(f"  [{feed}] stop_id={sid:20s} | stop_name={sname}")
    except Exception as e:
        print(f"  [{feed}] ERROR: {e}")

# ---------------------------------------------------------------------------
# STEP 3 – Simulate search_stops logic for query "Nagercoil"
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("STEP 3 — SEARCH SIMULATION for 'Nagercoil'")
print("=" * 70)

try:
    sys.path.insert(0, ".")
    from app.services.stop_search import StopSearch
    from app.services.gtfs_loader import GTFSLoader
    from app.services.feed_registry import FeedRegistry

    registry = FeedRegistry(data_root=data_root)
    discovered = registry.discover_feeds()
    print(f"Discovered feeds: {discovered}")
    print()

    queries = ["Nagercoil", "Nagercoil Jn", "Nagercoil Town", "Chennai Egmore", "Salem", "Bangalore"]

    for query in queries:
        print(f"\n--- Query: '{query}' ---")
        all_results = []
        for feed_name in discovered:
            fp = registry.get_feed_path(feed_name)
            try:
                loader = GTFSLoader(str(fp))
                loader.load()
                searcher = StopSearch(loader.stops, feed_name=feed_name)
                results = searcher.search(query)
                for r in results:
                    all_results.append((r.match_score, r.match_tier, feed_name, r.stop_id, r.stop_name))
            except Exception as e:
                print(f"  [{feed_name}] ERROR: {e}")

        all_results.sort(key=lambda x: (-x[0], x[1]))
        print(f"{'Rank':<5} {'Score':>8} {'Tier':>5} {'Feed':<15} {'stop_id':<20} stop_name")
        print("-" * 80)
        for i, (score, tier, fname, sid, sname) in enumerate(all_results[:15], 1):
            print(f"{i:<5} {score:>8.1f} {tier:>5}  {fname:<15} {sid:<20} {sname}")

except Exception as e:
    import traceback
    print(f"ERROR in search simulation: {e}")
    traceback.print_exc()

# ---------------------------------------------------------------------------
# STEP 4 – Fuzzy Ranking Deep Dive for "Nagercoil"
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("STEP 4 — FUZZY RANKING AUDIT for 'Nagercoil' in railways feed")
print("=" * 70)

try:
    fp = os.path.join(data_root, "railways")
    stops_df = pd.read_csv(os.path.join(fp, "stops.txt"), dtype=str)
    query = "nagercoil"

    try:
        from rapidfuzz import fuzz
        HAS_RAPIDFUZZ = True
    except ImportError:
        import difflib
        HAS_RAPIDFUZZ = False

    print(f"Using rapidfuzz: {HAS_RAPIDFUZZ}")
    print()

    candidates = []
    for _, row in stops_df.iterrows():
        stop_name = str(row.get("stop_name", "")).strip()
        stop_id = str(row.get("stop_id", "")).strip()
        name_lower = stop_name.casefold()

        if HAS_RAPIDFUZZ:
            base_score = fuzz.WRatio(query, name_lower)
        else:
            seq = __import__("difflib").SequenceMatcher(None, query, name_lower)
            base_score = seq.ratio() * 100.0

        query_tokens = [t for t in re.split(r"\W+", query) if t]
        candidate_tokens = [t for t in re.split(r"\W+", name_lower) if t]

        token_bonus = 0.0
        matched_count = 0
        for q_tok in query_tokens:
            best = 0.0
            for c_tok in candidate_tokens:
                if HAS_RAPIDFUZZ:
                    s = fuzz.ratio(q_tok, c_tok)
                else:
                    s = __import__("difflib").SequenceMatcher(None, q_tok, c_tok).ratio() * 100.0
                if s > best:
                    best = s
            if best >= 85.0:
                token_bonus += 5.0
                matched_count += 1

        if matched_count > 1:
            token_bonus += 5.0 * matched_count
        if matched_count == len(query_tokens) and len(query_tokens) > 0:
            token_bonus += 10.0

        final_score = 500 + base_score + token_bonus + 150  # +150 for railways feed

        if base_score >= 70:
            candidates.append((final_score, base_score, token_bonus, stop_id, stop_name))

    candidates.sort(key=lambda x: -x[0])
    print(f"{'#':<4} {'final':>8} {'base':>8} {'bonus':>8} {'stop_id':<20} stop_name")
    print("-" * 70)
    for i, (fs, bs, tb, sid, sn) in enumerate(candidates[:20], 1):
        print(f"{i:<4} {fs:>8.1f} {bs:>8.1f} {tb:>8.1f} {sid:<20} {sn}")

except Exception as e:
    import traceback
    print(f"ERROR in fuzzy audit: {e}")
    traceback.print_exc()

# ---------------------------------------------------------------------------
# STEP 8 – Route Graph Check: Chennai Egmore → Nagercoil Junction
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("STEP 8 — ROUTE GRAPH CHECK: Chennai Egmore → Nagercoil Junction")
print("=" * 70)

try:
    fp = os.path.join(data_root, "railways")
    stops_df = pd.read_csv(os.path.join(fp, "stops.txt"), dtype=str)
    stop_times_df = pd.read_csv(os.path.join(fp, "stop_times.txt"), dtype=str)
    trips_df = pd.read_csv(os.path.join(fp, "trips.txt"), dtype=str)

    # Find Chennai Egmore stop IDs
    egmore_mask = stops_df["stop_name"].str.upper().str.contains("EGMORE", na=False)
    nagercoli_mask = stops_df["stop_name"].str.upper().str.contains("NAGERCOIL", na=False)

    egmore_stops = stops_df[egmore_mask][["stop_id", "stop_name"]]
    nagercoil_stops = stops_df[nagercoli_mask][["stop_id", "stop_name"]]

    print("Chennai Egmore stops:")
    print(egmore_stops.to_string())
    print()
    print("Nagercoil stops:")
    print(nagercoil_stops.to_string())

    if not egmore_stops.empty and not nagercoil_stops.empty:
        src_ids = set(egmore_stops["stop_id"])
        dst_ids = set(nagercoil_stops["stop_id"])

        src_trips = set(stop_times_df[stop_times_df["stop_id"].isin(src_ids)]["trip_id"])
        dst_trips = set(stop_times_df[stop_times_df["stop_id"].isin(dst_ids)]["trip_id"])

        common_trips = src_trips.intersection(dst_trips)
        print()
        print(f"Trips serving any Chennai Egmore stop: {len(src_trips)}")
        print(f"Trips serving any Nagercoil stop: {len(dst_trips)}")
        print(f"Common trips (both source and dest): {len(common_trips)}")

        if common_trips:
            print("Sample common trip IDs:", list(common_trips)[:5])
except Exception as e:
    import traceback
    print(f"ERROR in graph check: {e}")
    traceback.print_exc()
