"""Utilities for searching GTFS stop records."""

import logging
from typing import List

import pandas as pd
import re
from app.models.schemas import StopResult, MatchTier

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    HAS_RAPIDFUZZ = False

class StopSearch:
    """Search GTFS stop records using case-insensitive partial matching.

    The search is designed to work with a pandas DataFrame containing GTFS
    stop information, including at least the standard columns
    ``stop_id``, ``stop_name``, ``stop_lat``, and ``stop_lon``.
    """

    REQUIRED_COLUMNS = ("stop_id", "stop_name", "stop_lat", "stop_lon")

    def __init__(self, stops: pd.DataFrame, feed_name: str | None = None) -> None:
        """Initialize the search index.

        Args:
            stops: A pandas DataFrame containing GTFS stop records.
            feed_name: Optional name of the GTFS feed.

        Raises:
            TypeError: If ``stops`` is not a pandas DataFrame.
            ValueError: If required columns are missing.
        """
        self.logger = logging.getLogger(__name__)

        if not isinstance(stops, pd.DataFrame):
            message = "Expected a pandas DataFrame for stops."
            self.logger.error(message)
            raise TypeError(message)

        missing_columns = [column for column in self.REQUIRED_COLUMNS if column not in stops.columns]
        if missing_columns:
            message = "Missing required stop columns: " + ", ".join(missing_columns)
            self.logger.error(message)
            raise ValueError(message)

        self.stops = stops.copy()
        self.feed_name = feed_name

    def search(self, query: str) -> List[StopResult]:
        """Search for stops using partial, case-insensitive matching.

        Matches are scored so best results appear first. The method returns at
        most 10 results.

        Args:
            query: The user search text.

        Returns:
            A list of ``StopResult`` models sorted by relevance.
        """
        try:
            if not isinstance(query, str):
                raise ValueError("Search query must be a string.")

            normalized_query = query.strip().casefold()
            if not normalized_query:
                return []

            if self.stops.empty:
                return []

            scored_results: List[tuple[int, float, str, StopResult]] = []

            for row in self.stops.itertuples():
                try:
                    stop_name = str(getattr(row, "stop_name", "")).strip()
                    stop_id = str(getattr(row, "stop_id", "")).strip()
                    name_lower = stop_name.casefold()
                    id_lower = stop_id.casefold()

                    tier = None
                    
                    # Filter out generic mock city objects (timestamp-based numeric IDs)
                    if len(stop_id) >= 12 and stop_id.isdigit():
                        continue

                    # City aliases to boost major GTFS stations when users search by city name
                    city_aliases = {
                        "bangalore": ["SBC", "BNC", "YPR", "SMVB"],
                        "bengaluru": ["SBC", "BNC", "YPR", "SMVB"],
                        "chennai": ["MAS", "MS", "TBM", "PER"],
                        "madras": ["MAS", "MS", "TBM", "PER"]
                    }
                    
                    is_alias_match = False
                    if normalized_query in city_aliases and stop_id in city_aliases[normalized_query]:
                        is_alias_match = True

                    # Tier 1: Exact stop_id match or alias match
                    if id_lower == normalized_query or stop_id == query or is_alias_match:
                        tier = MatchTier.EXACT_ID
                    # Tier 2: Exact stop_name match
                    elif stop_name == query:
                        tier = MatchTier.EXACT_NAME
                    # Tier 3: Normalized exact name match
                    elif name_lower == normalized_query:
                        tier = MatchTier.NORMALIZED_EXACT_NAME
                    else:
                        # Token matching pre-computation
                        tokens = re.split(r'\W+', name_lower)
                        
                        # Tier 4: Prefix match
                        if name_lower.startswith(normalized_query):
                            tier = MatchTier.PREFIX
                        # Tier 5: Token match
                        elif normalized_query in tokens:
                            tier = MatchTier.TOKEN
                        # Tier 6: Fuzzy/Substring match
                        elif normalized_query in name_lower or normalized_query in id_lower:
                            tier = MatchTier.FUZZY

                    if tier is None:
                        continue

                    base_score = 0
                    if tier == MatchTier.EXACT_ID:
                        base_score = 1000
                    elif tier == MatchTier.EXACT_NAME:
                        base_score = 900
                    elif tier == MatchTier.NORMALIZED_EXACT_NAME:
                        base_score = 800
                    elif tier == MatchTier.PREFIX:
                        base_score = 700
                    elif tier == MatchTier.TOKEN:
                        base_score = 600
                    elif tier == MatchTier.FUZZY:
                        base_score = 500

                    tie_breaker_score = base_score - abs(len(stop_name) - len(query))
                    
                    if self.feed_name == "railways":
                        tie_breaker_score += 150
                    try:
                        stop_lat = float(getattr(row, "stop_lat", 0.0))
                        stop_lon = float(getattr(row, "stop_lon", 0.0))
                    except (ValueError, TypeError):
                        stop_lat = 0.0
                        stop_lon = 0.0
                        
                    result_model = StopResult(
                        stop_id=stop_id,
                        stop_name=stop_name,
                        lat=stop_lat,
                        lon=stop_lon,
                        match_tier=tier.value,
                        match_score=tie_breaker_score
                    )
                    
                    scored_results.append((tier.value, tie_breaker_score, name_lower, result_model))
                except Exception as exc:
                    self.logger.warning("Skipping invalid stop row during search: %s", exc)
                    continue

            # Sort by tie_breaker_score (descending = better), then tier (ascending = better), then name_lower
            scored_results.sort(key=lambda item: (-item[1], item[0], item[2], item[3].stop_id))

            has_strong_match = any(item[0] <= MatchTier.TOKEN.value for item in scored_results)
            
            if not has_strong_match:
                fuzzy_results: List[tuple[int, float, str, StopResult]] = []
                # Fallback to fuzzy matching
                for row in self.stops.itertuples():
                    stop_name = str(getattr(row, "stop_name", "")).strip()
                    stop_id = str(getattr(row, "stop_id", "")).strip()
                    name_lower = stop_name.casefold()

                    # Filter out generic mock city objects (timestamp-based numeric IDs)
                    if len(stop_id) >= 12 and stop_id.isdigit():
                        continue
                    
                    score = 0.0
                    if HAS_RAPIDFUZZ:
                        score = fuzz.WRatio(normalized_query, name_lower)
                    else:
                        seq = difflib.SequenceMatcher(None, normalized_query, name_lower)
                        score = seq.ratio() * 100.0

                    query_tokens = [t for t in re.split(r'\W+', normalized_query) if t]
                    candidate_tokens = [t for t in re.split(r'\W+', name_lower) if t]
                    
                    token_bonus = 0.0
                    matched_tokens_count = 0
                    
                    for q_token in query_tokens:
                        best_token_match = 0.0
                        for c_token in candidate_tokens:
                            if HAS_RAPIDFUZZ:
                                tok_score = fuzz.ratio(q_token, c_token)
                            else:
                                tok_score = difflib.SequenceMatcher(None, q_token, c_token).ratio() * 100.0
                            if tok_score > best_token_match:
                                best_token_match = tok_score
                        
                        if best_token_match >= 85.0:
                            token_bonus += 5.0
                            matched_tokens_count += 1

                    if matched_tokens_count > 1:
                        token_bonus += 5.0 * matched_tokens_count

                    if matched_tokens_count == len(query_tokens) and len(query_tokens) > 0:
                        token_bonus += 10.0

                    final_score = 500 + score + token_bonus
                    if self.feed_name == "railways":
                        final_score += 150
                        
                    # Safe confidence threshold (using base score to avoid false positives getting boosted)
                    if score >= 80.0:
                        self.logger.info("[FUZZY_RANK] candidate='%s' base_score=%.2f token_bonus=%.2f final_score=%.2f", stop_name, score, token_bonus, final_score)
                        
                        try:
                            stop_lat = float(getattr(row, "stop_lat", 0.0))
                            stop_lon = float(getattr(row, "stop_lon", 0.0))
                        except (ValueError, TypeError):
                            stop_lat = 0.0
                            stop_lon = 0.0
                            
                        result_model = StopResult(
                            stop_id=stop_id,
                            stop_name=stop_name,
                            lat=stop_lat,
                            lon=stop_lon,
                            match_tier=MatchTier.FUZZY.value,
                            match_score=final_score
                        )
                        fuzzy_results.append((MatchTier.FUZZY.value, final_score, name_lower, result_model))
                
                if fuzzy_results:
                    # Sort fuzzy results by score (descending = better)
                    fuzzy_results.sort(key=lambda item: (-item[1], item[2], item[3].stop_id))
                    # If we found fuzzy results above threshold, use them instead of the poor substring matches
                    scored_results = fuzzy_results

            # Return only top 10
            matches = [item[3] for item in scored_results[:10]]
            return matches

        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Stop search failed: {exc}"
            self.logger.exception(message)
            return []
