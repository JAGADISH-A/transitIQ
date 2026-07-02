"""Simple AI-agent tool wrappers for the transit service and multi-modal providers."""

import logging
from typing import List

from app.models.schemas import NearbyStopResult, StopResult
from app.models.transit import TransportStop, TransportPreference
from app.services.transit_service import transit_service


class TransitAgentTools:
    """Expose simple transit-service helper methods for AI agents."""

    def __init__(self) -> None:
        """Initialize the tool wrapper and logger."""
        self.logger = logging.getLogger(__name__)

    def get_available_feeds(self) -> List[str]:
        """Return the currently available GTFS feed names."""
        try:
            feeds = transit_service.available_feeds()
            self.logger.info("Agent requested available feeds: %d feed(s)", len(feeds))
            return feeds
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to retrieve available feeds: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def search_stops(self, query: str) -> List[StopResult]:
        """Search stops across the currently loaded GTFS data."""
        try:
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query must be a non-empty string.")

            results = transit_service.search_stops(query)
            
            # Diagnostic logging for top candidates
            for i, res in enumerate(results[:3]):
                self.logger.info(
                    "[DIAGNOSTICS] Search stop '%s' candidate %d: id='%s' name='%s' tier=%d score=%.1f",
                    query, i+1, res.stop_id, res.stop_name, res.match_tier, res.match_score
                )
            
            self.logger.info("Agent searched stops for query '%s': %d result(s)", query, len(results))
            return results
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to search stops: {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def search_stops_in_feed(self, query: str, feed: str) -> List[StopResult]:
        """Search stops within a specific GTFS feed."""
        try:
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query must be a non-empty string.")
            if not isinstance(feed, str) or not feed.strip():
                raise ValueError("feed must be a non-empty string.")

            results = transit_service.search_stops_in_feed(query, feed)
            
            # Diagnostic logging for top candidates
            for i, res in enumerate(results[:3]):
                self.logger.info(
                    "[DIAGNOSTICS] Feed '%s' search '%s' candidate %d: id='%s' name='%s' tier=%d score=%.1f",
                    feed, query, i+1, res.stop_id, res.stop_name, res.match_tier, res.match_score
                )
                
            self.logger.info(
                "Agent searched feed '%s' for query '%s': %d result(s)",
                feed,
                query,
                len(results),
            )
            return results
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to search stops in feed '{feed}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc

    def nearby_stops(
        self,
        feed: str,
        lat: float,
        lon: float,
        radius_km: float = 2.0,
    ) -> List[NearbyStopResult]:
        """Return nearby stops for a specific GTFS feed and coordinate."""
        try:
            if not isinstance(feed, str) or not feed.strip():
                raise ValueError("feed must be a non-empty string.")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                raise ValueError("lat and lon must be numeric values.")
            if not isinstance(radius_km, (int, float)) or radius_km < 0:
                raise ValueError("radius_km must be a non-negative number.")

            results = transit_service.get_nearby_stops(feed_name=feed, lat=lat, lon=lon, radius_km=radius_km)
            self.logger.info(
                "Agent requested nearby stops for feed '%s' at (%.4f, %.4f) within %.2f km: %d result(s)",
                feed,
                lat,
                lon,
                radius_km,
                len(results),
            )
            return results
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to find nearby stops for feed '{feed}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc


    def find_trip(self, source: str, destination: str) -> dict:
        """Find routes between source and destination stops.
        
        Args:
            source: Source stop name or ID.
            destination: Destination stop name or ID.
            
        Returns:
            A dict representation of the TripResponse containing direct and transfer routes.
        """
        try:
            if not isinstance(source, str) or not source.strip():
                raise ValueError("source must be a non-empty string.")
            if not isinstance(destination, str) or not destination.strip():
                raise ValueError("destination must be a non-empty string.")

            result = transit_service.find_trip(source=source, destination=destination)
            
            if result.results:
                best_match = result.results[0]
                self.logger.info(
                    "[DIAGNOSTICS] Trip selected feed='%s', source='%s' (tier %d), dest='%s' (tier %d)",
                    best_match.feed, best_match.source_stop_name, best_match.source_match_tier,
                    best_match.destination_stop_name, best_match.dest_match_tier
                )
                for i, alt in enumerate(result.results[1:3]):
                    self.logger.info(
                        "[DIAGNOSTICS] Trip alternate %d feed='%s', source='%s' (tier %d), dest='%s' (tier %d)",
                        i+1, alt.feed, alt.source_stop_name, alt.source_match_tier, alt.destination_stop_name, alt.dest_match_tier
                    )
            
            self.logger.info(
                "Agent requested trip from '%s' to '%s': %d feed(s) searched, %d result(s)",
                source,
                destination,
                len(result.feeds_searched),
                len(result.results),
            )
            return result.model_dump()
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to find trip from '{source}' to '{destination}': {exc}"
            self.logger.exception(message)
            raise RuntimeError(message) from exc


    # ------------------------------------------------------------------
    # Phase 5 — Multi-modal transport tools
    # ------------------------------------------------------------------

    def get_available_providers(self) -> list[dict]:
        """Return information about all available transport providers."""
        try:
            from app.providers.registry import provider_registry
            providers = provider_registry.list_providers()
            return [p.model_dump() for p in providers]
        except Exception as exc:
            self.logger.warning("Failed to list providers: %s", exc)
            return []

    def search_stops_all_modes(self, query: str) -> list[dict]:
        """Search stops across all transport providers (rail, bus, metro, ferry)."""
        try:
            from app.providers.registry import provider_registry
            results = provider_registry.search_stops_all(query)
            return [s.model_dump() for s in results[:20]]
        except Exception as exc:
            self.logger.warning("Multi-modal stop search failed: %s", exc)
            return []

    def find_multi_modal_journey(
        self,
        source: str,
        destination: str,
        preferences: dict | None = None,
    ) -> dict:
        """Find multi-modal journeys combining rail, bus, metro, and ferry."""
        try:
            from app.providers.multi_modal_planner import multi_modal_planner
            pref = TransportPreference(**(preferences or {}))
            journeys = multi_modal_planner.plan(source, destination, pref)
            return {
                "source": source,
                "destination": destination,
                "journeys": [j.model_dump() for j in journeys],
                "count": len(journeys),
            }
        except Exception as exc:
            self.logger.warning("Multi-modal journey planning failed: %s", exc)
            return {"source": source, "destination": destination, "journeys": [], "count": 0}


agent_tools = TransitAgentTools()
