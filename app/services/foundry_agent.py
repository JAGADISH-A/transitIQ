"""Groq API tool-calling integration for TransitIQ.

This service keeps the existing FastAPI and TransitAgentTools architecture intact,
while adding a Groq-compatible tool-calling layer. The model can decide which
transit tool to invoke, and this class executes those tool calls and returns a
final natural-language response.

Recovery: Some models occasionally fail to emit proper OpenAI tool_calls,
placing the intended tool name and JSON arguments inside reasoning_content
instead. The _recover_from_reasoning() method detects this condition and
re-routes the call through the normal execute_tool_call path.
"""

import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq

from app.config import get_settings
from app.services.agent_tools import agent_tools
from app.services.ai_planner import ai_planner
from app.services.transit_service import transit_service
from app.services.session_manager import session_manager
from app.services.context_builder import build_ai_context_string


# ---------------------------------------------------------------------------
# Known tool names — used by recovery parser to match reasoning text
# ---------------------------------------------------------------------------
_KNOWN_TOOLS = frozenset({
    "get_available_feeds",
    "search_stops",
    "search_stops_in_feed",
    "nearby_stops",
    "find_trip",
    "get_available_providers",
    "search_stops_all_modes",
    "find_multi_modal_journey",
})

# Pre-compiled regex: match a known tool name mentioned in free text
_TOOL_NAME_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _KNOWN_TOOLS) + r")\b"
)

# Pre-compiled regex: extract JSON objects (complete or truncated)
_JSON_OBJECT_PATTERN = re.compile(r"\{[^{}]*\}", re.DOTALL)
_JSON_PARTIAL_PATTERN = re.compile(r"\{[^{}]*$", re.DOTALL)  # truncated: opens but never closes

# ---------------------------------------------------------------------------
# Heuristic intent phrases → tool mapping
# Order matters: search_stops_in_feed patterns checked before search_stops
# because "search stops in <feed>" should match the more specific tool.
# ---------------------------------------------------------------------------
_HEURISTIC_RULES: List[Tuple[str, List[re.Pattern]]] = [
    ("find_trip", [
        re.compile(r"how\s+(?:do|to|can)\s+(?:i\s+)?get\s+from\b", re.IGNORECASE),
        re.compile(r"plan\s+(?:a\s+)?trip\s+from\b", re.IGNORECASE),
        re.compile(r"travel\s+from\b", re.IGNORECASE),
        re.compile(r"trip\s+from\b", re.IGNORECASE),
        re.compile(r"route\s+between\b", re.IGNORECASE),
        re.compile(r"directions\s+from\b", re.IGNORECASE),
    ]),
    ("search_stops_in_feed", [
        re.compile(r"search\s+(?:for\s+)?stops?\s+in\b", re.IGNORECASE),
        re.compile(r"find\s+(?:the\s+)?stops?\s+in\b", re.IGNORECASE),
        re.compile(r"look\s+(?:for\s+)?stops?\s+in\b", re.IGNORECASE),
        re.compile(r"stops?\s+in\s+(?:the\s+)?\w+\s+feed", re.IGNORECASE),
    ]),
    ("search_stops", [
        re.compile(r"search\s+(?:for\s+)?stops?", re.IGNORECASE),
        re.compile(r"find\s+(?:the\s+)?(?:transit\s+)?stops?", re.IGNORECASE),
        re.compile(r"look\s+(?:for\s+)?(?:transit\s+)?stops?", re.IGNORECASE),
    ]),
    ("nearby_stops", [
        re.compile(r"nearby\s+stops?", re.IGNORECASE),
        re.compile(r"stops?\s+near(?:by)?\b", re.IGNORECASE),
        re.compile(r"close\s+to\b.*stops?", re.IGNORECASE),
        re.compile(r"within\s+[\d.]+\s*(?:km|kilometer|mile)", re.IGNORECASE),
    ]),
    ("get_available_feeds", [
        re.compile(r"available\s+feeds?", re.IGNORECASE),
        re.compile(r"list\s+(?:the\s+)?feeds?", re.IGNORECASE),
        re.compile(r"what\s+feeds?", re.IGNORECASE),
        re.compile(r"which\s+feeds?", re.IGNORECASE),
        re.compile(r"get\s+(?:the\s+)?feeds?", re.IGNORECASE),
    ]),
]

# Extract quoted strings from prose (e.g., "Chennai Central")
_QUOTED_STRING_PATTERN = re.compile(r'["\']([^"\']{2,})["\']')

# Extract coordinate-like numbers from prose
_COORDINATE_PATTERN = re.compile(
    r'(?:lat(?:itude)?\s*[:=]?\s*([\d.+-]+))|'
    r'(?:lon(?:gitude)?\s*[:=]?\s*([\d.+-]+))|'
    r'(?:radius\s*[:=]?\s*([\d.]+))',
    re.IGNORECASE,
)

# Extract feed name from prose like "in the railways feed" or "in railways"
_FEED_IN_PROSE_PATTERN = re.compile(
    r'(?:in\s+(?:the\s+)?)(\w+)(?:\s+feed)?',
    re.IGNORECASE,
)


class FoundryTransitAgent:
    """Use Groq API tool-calling to answer transit questions.

    The service intentionally uses the existing TransitAgentTools wrapper as the
    source of truth for GTFS lookups. Groq only decides which tool to call and
    receives structured outputs back from the tool layer.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize the Groq integration.

        Args:
            model: Groq model name. If omitted, the setting value is used
                or a safe default is chosen.
        """
        self.logger = logging.getLogger(__name__)
        settings = get_settings()

        self.api_key = settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self._client = None

        self.logger.info("Using Groq model: %s", self.model)
        self.logger.info("GROQ_API_KEY present: %s", bool(self.api_key))

        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
                self.logger.info("Groq client initialized.")
            except Exception as exc:
                self.logger.warning("Groq client initialization failed: %s", exc)
                self._client = None

    def _fast_path_route(self, user_query: str) -> Optional[Dict[str, Any]]:
        """Intent Router to bypass reasoning for simple transit lookups."""
        patterns_trip = [
            re.compile(r"(?:route|trip|directions)\s+from\s+(.+?)\s+to\s+(.+?)(?:\Z|\?|\.)", re.IGNORECASE),
            re.compile(r"how\s+(?:do|can)\s+i\s+get\s+from\s+(.+?)\s+to\s+(.+?)(?:\Z|\?|\.)", re.IGNORECASE)
        ]
        patterns_station = [
            re.compile(r"(?:search\s+stop|find\s+station)\s+(.+?)(?:\Z|\?|\.)", re.IGNORECASE)
        ]

        # Check trip routing
        for p in patterns_trip:
            match = p.search(user_query)
            if match:
                self.logger.info("[ROUTER] Matched route query")
                source = match.group(1).strip()
                dest = match.group(2).strip()
                
                route_data = None
                try:
                    res_dict = agent_tools.find_trip(source, dest)
                    results = res_dict.get("results", [])
                    
                    route_data = {
                        "source": source,
                        "destination": dest,
                        "results": results
                    }
                    
                    if results:
                        trip = results[0]
                        s_name = trip.get("source_stop_name", "Source")
                        d_name = trip.get("destination_stop_name", "Destination")
                        
                        transfer_opts = trip.get("transfer_options", [])
                        direct_opts = trip.get("direct_routes", [])
                        
                        if direct_opts:
                            answer = f"Found a direct route from {s_name} to {d_name}."
                        elif transfer_opts:
                            answer = f"Found {len(transfer_opts)} transfer options from {s_name} to {d_name}."
                        else:
                            answer = f"Found a route from {s_name} to {d_name}."
                    else:
                        answer = "I searched available feeds but could not find a route between the requested stops."
                except Exception as e:
                    self.logger.exception("[ROUTER] find_trip exception")
                    answer = "I searched available feeds but could not find a route between the requested stops."
                
                return {
                    "answer": answer,
                    "tools_used": ["find_trip"],
                    "route_data": route_data
                }
                
        # Check station lookup
        for p in patterns_station:
            match = p.search(user_query)
            if match:
                self.logger.info("[ROUTER] Matched station search query")
                query = match.group(1).strip()
                
                try:
                    self.logger.warning("RAW USER QUERY: %r", user_query)
                    self.logger.warning("EXTRACTED QUERY: %r", query)
                    
                    res_list = agent_tools.search_stops(query)
                    
                    self.logger.warning("RESULT COUNT: %s", len(res_list) if res_list else 0)
                    self.logger.warning("RESULTS: %s", res_list[:3] if res_list else [])
                    
                    self.logger.warning("FAST_PATH query = %s", query)
                    self.logger.warning("FAST_PATH results count = %s", len(res_list) if isinstance(res_list, list) else 'NOT_A_LIST')
                    self.logger.warning("FAST_PATH first result = %s", res_list[0] if isinstance(res_list, list) and len(res_list) > 0 else None)
                    
                    if isinstance(res_list, list) and len(res_list) > 0:
                        stop = res_list[0]
                        s_name = getattr(stop, "stop_name", "Unknown Stop")
                        s_id = getattr(stop, "stop_id", "Unknown ID")
                        
                        self.logger.info(f"[STATION_SEARCH] top_result={s_name} ({s_id})")
                        self.logger.info(f"[STATION_SEARCH] tier={getattr(stop, 'match_tier', 'Unknown')}")
                        self.logger.info(f"[STATION_SEARCH] score={getattr(stop, 'match_score', 'Unknown')}")
                        
                        answer = f"Found stop:\n{s_name} ({s_id})"
                    else:
                        answer = "Could not find a matching stop."
                except Exception as e:
                    self.logger.exception("[ROUTER] search_stops exception: %s", e)
                    answer = "Could not find a matching stop."
                    
                return {
                    "answer": answer,
                    "tools_used": ["search_stops"]
                }
                
        return None

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    def tool_definitions(self) -> List[Dict[str, Any]]:
        """Return the JSON-schema tool definitions exposed to the model.

        Dynamically injects available feed names so the model never invents them.
        If only one feed exists, the feed parameter is removed from tools that
        require it (automatically filled at execution time).
        """
        valid_feeds = self._get_valid_feeds()
        feed_list_str = ", ".join(valid_feeds) if valid_feeds else "none loaded"
        single_feed = valid_feeds[0] if len(valid_feeds) == 1 else None

        # tool shared for search_stops_in_feed and nearby_stops
        if single_feed:
            feed_param_description = f"(auto-filled: only feed '{single_feed}' is available)"
        else:
            feed_param_description = f"Must be one of: {feed_list_str}"

        # search_stops_in_feed: conditionally include feed parameter
        search_stops_in_feed_params = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Text to search in stop names or IDs.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }
        if not single_feed:
            search_stops_in_feed_params["properties"]["feed"] = {
                "type": "string",
                "minLength": 1,
                "description": feed_param_description,
            }
            search_stops_in_feed_params["required"] = ["query", "feed"]

        # nearby_stops: conditionally include feed parameter
        nearby_stops_params = {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "Latitude in decimal degrees.",
                },
                "lon": {
                    "type": "number",
                    "description": "Longitude in decimal degrees.",
                },
                "radius_km": {
                    "type": "number",
                    "description": "Search radius in kilometers.",
                    "default": 2.0,
                },
            },
            "required": ["lat", "lon"],
            "additionalProperties": False,
        }
        if not single_feed:
            nearby_stops_params["properties"]["feed"] = {
                "type": "string",
                "minLength": 1,
                "description": feed_param_description,
            }
            nearby_stops_params["required"] = ["feed", "lat", "lon"]

        return [
            {
                "type": "function",
                "function": {
                    "name": "get_available_feeds",
                    "description": "List all available GTFS feeds currently loaded by the backend.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_trip",
                    "description": "Find transit routes between a source and destination stop. Returns direct routes if available, otherwise suggests transfer options.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Source stop name or ID."
                            },
                            "destination": {
                                "type": "string",
                                "description": "Destination stop name or ID."
                            }
                        },
                        "required": ["source", "destination"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_stops",
                    "description": "Find transit stops by stop name or stop ID across all loaded GTFS feeds.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Text to search for in stop names or IDs.",
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_stops_in_feed",
                    "description": f"Find transit stops within one specific GTFS feed.{' (feed auto-filled)' if single_feed else ''}",
                    "parameters": search_stops_in_feed_params,
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "nearby_stops",
                    "description": f"Find nearby stops for a feed and coordinate pair.{' (feed auto-filled)' if single_feed else ''}",
                    "parameters": nearby_stops_params,
                },
            },
            # --- Phase 5: Multi-modal transport tools ---
            {
                "type": "function",
                "function": {
                    "name": "get_available_providers",
                    "description": "List all available transport providers (rail, bus, metro, ferry) and their status.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_stops_all_modes",
                    "description": "Search stops across ALL transport modes (rail, bus, metro, ferry) by name or ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Text to search for in stop names or IDs.",
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_multi_modal_journey",
                    "description": "Plan a multi-modal journey combining rail, bus, metro, and ferry. Provide source and destination stop names.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Source stop name or location."
                            },
                            "destination": {
                                "type": "string",
                                "description": "Destination stop name or location."
                            },
                            "preferences": {
                                "type": "object",
                                "description": "Optional transport preferences (e.g., avoid buses, use only trains).",
                                "properties": {
                                    "avoided_modes": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Modes to avoid: RAIL, BUS, METRO, FERRY"
                                    },
                                    "preferred_modes": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Only use these modes: RAIL, BUS, METRO, FERRY"
                                    }
                                }
                            }
                        },
                        "required": ["source", "destination"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _tool_handler(self, name: str) -> Any:
        """Return a callable for the named tool, using the existing wrapper class."""
        handlers = {
            "get_available_feeds": agent_tools.get_available_feeds,
            "search_stops": agent_tools.search_stops,
            "search_stops_in_feed": agent_tools.search_stops_in_feed,
            "nearby_stops": agent_tools.nearby_stops,
            "find_trip": agent_tools.find_trip,
            "get_available_providers": agent_tools.get_available_providers,
            "search_stops_all_modes": agent_tools.search_stops_all_modes,
            "find_multi_modal_journey": agent_tools.find_multi_modal_journey,
        }
        if name not in handlers:
            raise ValueError(f"Unsupported tool '{name}'.")
        return handlers[name]

    def _get_valid_feeds(self) -> List[str]:
        feeds = transit_service.available_feeds()
        return feeds if feeds else []

    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a model-requested function call and return the tool result.

        The returned structure is compatible with the OpenAI/Groq tool-calling
        protocol, so the model can continue reasoning over the structured output.
        """
        try:
            tool_name = (tool_call.get("function") or {}).get("name")
            raw_arguments = (tool_call.get("function") or {}).get("arguments", "{}")
            if raw_arguments is None or raw_arguments == "null":
                raw_arguments = "{}"
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            if arguments is None:
                arguments = {}

            # If only one feed loaded, auto-fill feed parameters
            valid_feeds = self._get_valid_feeds()
            if len(valid_feeds) == 1:
                single_feed = valid_feeds[0]
                if tool_name in ("search_stops_in_feed", "nearby_stops") and "feed" not in arguments:
                    arguments["feed"] = single_feed

            # Validate feed names before dispatching
            if tool_name in ("search_stops_in_feed", "nearby_stops"):
                feed_arg = arguments.get("feed", "")
                if feed_arg and valid_feeds and feed_arg not in valid_feeds:
                    return {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": json.dumps({"error": f"Feed '{feed_arg}' not found. Available feeds: {valid_feeds}"}),
                    }

            handler = self._tool_handler(tool_name)
            result = handler(**arguments)

            return {
                "role": "tool",
                "tool_call_id": tool_call.get("id"),
                "content": json.dumps(result, default=_json_default),
            }
        except Exception as exc:  # pragma: no cover - defensive runtime handling
            self.logger.exception("Tool execution failed for call %s", tool_call)
            return {
                "role": "tool",
                "tool_call_id": tool_call.get("id"),
                "content": json.dumps({"error": str(exc)}),
            }

    # ------------------------------------------------------------------
    # Reasoning-content recovery (model workaround)
    # ------------------------------------------------------------------

    def _recover_from_reasoning(
        self,
        reasoning_content: str,
        user_query: str = "",
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Attempt to extract a tool call from malformed reasoning text.

        Three-tier recovery strategy:
          Tier 1 — Exact tool name + complete JSON in reasoning.
          Tier 2 — Heuristic phrase matching + complete/partial JSON.
          Tier 3 — Heuristic phrase matching + argument extraction from prose.

        Returns:
            A (tool_name, arguments_dict) tuple if recovery succeeds, else None.
        """
        if not reasoning_content or not isinstance(reasoning_content, str):
            return None

        text = reasoning_content

        # ---- Tier 1: exact tool name in text ----
        tool_matches = _TOOL_NAME_PATTERN.findall(text)
        inferred_tool: Optional[str] = tool_matches[-1] if tool_matches else None

        if inferred_tool:
            print(f"[RECOVERY] Tier 1: exact tool name found — {inferred_tool}")
        else:
            # ---- Tier 2 / Tier 3 entry: heuristic phrase matching ----
            inferred_tool = self._infer_tool_from_phrases(text)
            if inferred_tool:
                print(f"[RECOVERY-INFERRED] Tier 2: heuristic matched — tool={inferred_tool}")
            else:
                print("[RECOVERY] No tool identified (exact or heuristic) in reasoning_content")
                return None

        # ---- Try to extract arguments (best-effort, multiple strategies) ----
        args = self._extract_arguments(text, inferred_tool, user_query)
        print(f"[RECOVERY-INFERRED] tool={inferred_tool} args={args}")
        return inferred_tool, args

    def _infer_tool_from_phrases(self, text: str) -> Optional[str]:
        """Match heuristic phrases against reasoning text to infer tool intent."""
        for tool_name, patterns in _HEURISTIC_RULES:
            for pattern in patterns:
                if pattern.search(text):
                    return tool_name
        return None

    def _extract_arguments(
        self,
        text: str,
        tool_name: str,
        user_query: str,
    ) -> Dict[str, Any]:
        """Extract tool arguments from reasoning text using multiple strategies.

        Strategy priority:
          1. Complete JSON object in text  → return as-is.
          2. Truncated/partial JSON repaired → merge with prose extraction
             to fill missing keys.
          3. Argument values extracted from prose + quoted strings.
          4. Fallback to user_query as the search term.
        """
        # -- Strategy 1: complete JSON --
        complete_args = self._try_complete_json(text)
        if complete_args is not None:
            print(f"[RECOVERY] Args via complete JSON: {complete_args}")
            return complete_args

        # -- Always run prose extraction (used as merge base or standalone) --
        prose_args = self._extract_args_from_prose(text, tool_name, user_query)

        # -- Strategy 2: partial / truncated JSON repair + prose merge --
        partial_args = self._try_partial_json(text)
        if partial_args is not None:
            print(f"[RECOVERY] Args via partial JSON repair: {partial_args}")
            # Merge: prose fills keys that partial JSON missed
            merged = {**prose_args, **partial_args}
            print(f"[RECOVERY] Merged with prose: {merged}")
            return merged

        # -- Strategy 3 & 4: prose extraction / user_query fallback --
        print(f"[RECOVERY] Args via prose extraction: {prose_args}")
        return prose_args

    # -- argument extraction helpers --

    @staticmethod
    def _try_complete_json(text: str) -> Optional[Dict[str, Any]]:
        """Return the last valid JSON object found in *text*, or None."""
        candidates = _JSON_OBJECT_PATTERN.findall(text)
        for candidate in reversed(candidates):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    @staticmethod
    def _try_partial_json(text: str) -> Optional[Dict[str, Any]]:
        """Attempt to repair a truncated JSON object.

        Handles cases like:  {"query": "Chennai Central", "feed":
        Strategy: find the partial block, extract all complete key-value pairs
        that were successfully written before truncation.
        """
        partial_match = _JSON_PARTIAL_PATTERN.search(text)
        if not partial_match:
            return None

        fragment = partial_match.group(0)
        print(f"[RECOVERY] Partial JSON fragment detected: {fragment!r}")

        # Extract all complete "key": "value" pairs from the fragment
        kv_pattern = re.compile(r'"(\w+)"\s*:\s*"([^"]*?)"')
        pairs = kv_pattern.findall(fragment)

        # Also extract numeric values: "key": 123.45
        kv_num_pattern = re.compile(r'"(\w+)"\s*:\s*([\d.+-]+)')
        num_pairs = kv_num_pattern.findall(fragment)

        if not pairs and not num_pairs:
            return None

        result: Dict[str, Any] = {}
        for key, value in pairs:
            result[key] = value
        for key, value in num_pairs:
            if key not in result:  # string pairs take priority
                try:
                    result[key] = float(value) if "." in value else int(value)
                except ValueError:
                    result[key] = value

        return result if result else None

    @staticmethod
    def _extract_args_from_prose(
        text: str,
        tool_name: str,
        user_query: str,
    ) -> Dict[str, Any]:
        """Last-resort: build arguments from quoted strings and prose patterns."""
        args: Dict[str, Any] = {}

        # Tools that need no arguments
        if tool_name == "get_available_feeds":
            return args

        # -- Extract quoted strings as candidate search terms --
        quoted = _QUOTED_STRING_PATTERN.findall(text)

        # -- Extract feed name from prose --
        feed_match = _FEED_IN_PROSE_PATTERN.search(text)
        feed_name = feed_match.group(1) if feed_match else None
        # Filter out common false positives
        if feed_name and feed_name.lower() in {
            "the", "a", "an", "this", "that", "it", "all", "some",
            "order", "for", "our",
        }:
            feed_name = None

        if tool_name == "search_stops":
            # Use first quoted string, or fall back to user_query
            args["query"] = quoted[0] if quoted else user_query.strip()

        elif tool_name == "search_stops_in_feed":
            args["query"] = quoted[0] if quoted else user_query.strip()
            if feed_name:
                args["feed"] = feed_name
            elif len(quoted) >= 2:
                # Second quoted string might be the feed
                args["feed"] = quoted[1]

        elif tool_name == "nearby_stops":
            # Try to extract coordinates
            for match in _COORDINATE_PATTERN.finditer(text):
                lat_val, lon_val, radius_val = match.groups()
                if lat_val:
                    args["lat"] = float(lat_val)
                if lon_val:
                    args["lon"] = float(lon_val)
                if radius_val:
                    args["radius_km"] = float(radius_val)
            if feed_name:
                args["feed"] = feed_name

        return args

    # ------------------------------------------------------------------
    # Main answer method
    # ------------------------------------------------------------------

    def answer(self, user_query: str) -> Dict[str, Any]:
        """Answer the user query using Groq tool-calling when available.

        If no Groq API key is configured, the method falls back to the existing
        planner logic so the API remains usable in local development.
        """
        start_time = time.perf_counter()

        fast_result = self._fast_path_route(user_query)
        if fast_result is not None:
            self.logger.info("[ROUTER] Query classified as FAST_PATH")
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                **fast_result,
                "classification": "FAST_PATH",
                "provider": "fast_path",
                "execution_time_ms": elapsed_ms,
            }

        self.logger.info("[ROUTER] Query classified as REASONING_PATH")

        if not isinstance(user_query, str) or not user_query.strip():
            return {"answer": "I can help with transit questions. Please provide a destination or location query.", "provider": "local"}

        if self._client is None:
            print("GROQ CLIENT IS NONE")
            self.logger.warning("Groq client unavailable; using local planner fallback for query '%s'", user_query)
            return {
                "answer": ai_planner.answer_query(user_query).get("answer", "I could not find a matching destination."),
                "provider": "local",
            }

        valid_feeds = self._get_valid_feeds()
        feed_list_str = ", ".join(valid_feeds) if valid_feeds else "none"
        single_feed = valid_feeds[0] if len(valid_feeds) == 1 else None

        if single_feed:
            feed_instruction = (
                f"The only available GTFS feed is '{single_feed}'. "
                f"All queries use this feed automatically. Do NOT ask the user to specify a feed."
            )
        else:
            feed_instruction = (
                f"Available GTFS feeds: {feed_list_str}. "
                f"You MUST only use these exact feed names in tool calls. "
                f"Do NOT invent feed names."
            )

        # Inject persistent journey context if one exists
        journey_context_block = build_ai_context_string()
        journey_section = (
            f"\n\n{journey_context_block}\n\n"
            if journey_context_block
            else ""
        )

        system_prompt = (
            "You are TransitIQ, a helpful unified transit intelligence assistant. "
            "Use the available tools to answer questions about rail, bus, metro, and ferry transport. "
            "Use find_trip for railway journeys, find_multi_modal_journey for combined transport modes. "
            "Prefer concise, natural-language answers based on the tool results.\n\n"
            f"FEED INFORMATION:\n{feed_instruction}\n\n"
            f"{journey_section}"
            "CRITICAL TOOL-CALLING RULES:\n"
            "- When you need external data, you MUST emit a proper tool_call using the OpenAI function-calling format.\n"
            "- NEVER write tool names or JSON arguments inside your reasoning or response text.\n"
            "- NEVER describe a tool call in prose instead of actually invoking it.\n"
            "- If you need to call a tool, use the tool_calls mechanism. Do NOT output the call as text.\n"
            "- Each tool call must include the function name and a valid JSON arguments object.\n"
            "- After receiving tool results, synthesize a helpful natural-language answer for the user."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        tool_calls_used: List[str] = []
        successful_tool_results: List[tuple] = []
        final_answer = "I could not generate a response from the model."

        print(f"\n{'='*60}")
        print(f"[GROQ-DIAG] START query={user_query!r}")
        print(f"{'='*60}")

        iteration = 0
        for _ in range(5):
            iteration += 1
            print(f"\n[GROQ-DIAG] --- Loop iteration {iteration} ---")
            print(f"[GROQ-DIAG] Messages count before call: {len(messages)}")

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_definitions(),
                tool_choice="auto",
                temperature=0.1,
            )

            # --- Diagnostic: completion object ---
            print(f"[GROQ-DIAG] COMPLETION (iter {iteration}) = {response}")
            print(f"[GROQ-DIAG] choices count = {len(response.choices) if response.choices else 0}")

            if not response.choices:
                print(f"[GROQ-DIAG] *** WARNING: response.choices is empty/None! ***")

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            print(f"[GROQ-DIAG] MESSAGE (iter {iteration}) = {message}")
            print(f"[GROQ-DIAG] finish_reason  = {finish_reason}")
            print(f"[GROQ-DIAG] message.role    = {getattr(message, 'role', 'N/A')}")
            print(f"[GROQ-DIAG] message.content = {getattr(message, 'content', 'N/A')!r}")
            print(f"[GROQ-DIAG] message.content type = {type(getattr(message, 'content', None))}")
            print(f"[GROQ-DIAG] message.tool_calls = {getattr(message, 'tool_calls', 'N/A')}")

            # Check for reasoning_content
            reasoning_content = getattr(message, "reasoning_content", None) or ""
            if reasoning_content:
                print(f"[GROQ-DIAG] reasoning_content present ({len(reasoning_content)} chars)")
                print(f"[GROQ-DIAG] reasoning_content = {reasoning_content!r:.500}")

            assistant_message = message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else {
                "role": getattr(message, "role", "assistant"),
                "content": getattr(message, "content", None),
            }
            print(f"[GROQ-DIAG] assistant_message appended = {assistant_message}")
            messages.append(assistant_message)

            self.logger.info(f"COMPLETION FINISH_REASON: {finish_reason}")
            self.logger.info(f"COMPLETION CONTENT: {getattr(message, 'content', None)}")
            self.logger.info(f"COMPLETION TOOL_CALLS: {getattr(message, 'tool_calls', None)}")
            self.logger.info(f"COMPLETION REASONING: {reasoning_content}")

            tool_calls = getattr(message, "tool_calls", None) or []
            print(f"[GROQ-DIAG] TOOL CALLS (iter {iteration}) = {tool_calls}")
            print(f"[GROQ-DIAG] tool_calls count = {len(tool_calls)}")

            if not tool_calls:
                raw_content = getattr(message, "content", None)

                # ---------------------------------------------------------
                # RECOVERY: detect reasoning_content with embedded tool call
                # ---------------------------------------------------------
                if not raw_content and reasoning_content:
                    print(f"[RECOVERY] Model failed to emit tool_call (iter {iteration})")
                    print(f"[RECOVERY] finish_reason={finish_reason}, content={raw_content!r}")
                    print(f"[RECOVERY] reasoning_content detected ({len(reasoning_content)} chars)")
                    self.logger.warning(
                        "[RECOVERY] reasoning_content fallback triggered for query '%s'",
                        user_query,
                    )

                    recovered = self._recover_from_reasoning(reasoning_content, user_query)

                    if recovered is not None:
                        recovered_tool, recovered_args = recovered
                        print(f"[RECOVERY] Tool inferred: {recovered_tool}")
                        print(f"[RECOVERY] Arguments: {recovered_args}")

                        REQUIRED_ARGS = {
                            "find_trip": ["source", "destination"],
                            "search_stops": ["query"],
                            "search_stops_in_feed": ["query", "feed"],
                            "nearby_stops": ["feed", "lat", "lon"]
                        }

                        missing = [
                            arg for arg in REQUIRED_ARGS.get(recovered_tool, [])
                            if arg not in recovered_args
                        ]

                        if missing:
                            self.logger.warning(
                                "[RECOVERY] Rejecting inferred tool '%s'. Missing args: %s",
                                recovered_tool,
                                missing,
                            )
                            continue

                        # Synthesize an OpenAI-compatible tool_call dict
                        synthetic_id = f"recovered_{uuid.uuid4().hex[:12]}"
                        synthetic_tool_call = {
                            "id": synthetic_id,
                            "type": "function",
                            "function": {
                                "name": recovered_tool,
                                "arguments": json.dumps(recovered_args),
                            },
                        }

                        # Replace the last assistant message with one that
                        # includes the synthetic tool_call, so the model sees
                        # a valid conversation history on the next iteration.
                        messages[-1] = {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [synthetic_tool_call],
                        }

                        tool_calls_used.append(recovered_tool)
                        print(f"[RECOVERY] Executing recovered tool: {recovered_tool}")
                        tool_result = self.execute_tool_call(synthetic_tool_call)
                        print(f"[RECOVERY] Tool completed: {tool_result}")
                        messages.append(tool_result)

                        try:
                            content_dict = json.loads(tool_result["content"])
                            if isinstance(content_dict, (dict, list)) and ("error" not in content_dict if isinstance(content_dict, dict) else True):
                                successful_tool_results.append((recovered_tool, content_dict))
                        except Exception:
                            pass

                        print(f"[RECOVERY] Continuing conversation loop")

                        # Continue — next iteration sends tool result to model.
                        continue
                    else:
                        print(f"[RECOVERY] All recovery tiers failed — no tool or args could be extracted")
                        self.logger.warning(
                            "[RECOVERY] All tiers failed for reasoning_content: %s",
                            reasoning_content[:500],
                        )

                # Normal exit: model returned text content (or nothing)
                print(f"[GROQ-DIAG] No tool calls — extracting final answer")
                print(f"[GROQ-DIAG] raw message.content = {raw_content!r}")
                print(f"[GROQ-DIAG] bool(raw_content)   = {bool(raw_content)}")
                
                if not raw_content and reasoning_content:
                    final_answer = reasoning_content
                else:
                    final_answer = raw_content or final_answer
                
                print(f"[GROQ-DIAG] final_answer after assignment = {final_answer!r}")
                if final_answer == "I could not generate a response from the model.":
                    print(f"[GROQ-DIAG] *** BUG HIT: content was falsy, fell back to default error string ***")
                    print(f"[GROQ-DIAG] *** completion object  = {response} ***")
                    print(f"[GROQ-DIAG] *** choices count      = {len(response.choices) if response.choices else 0} ***")
                    print(f"[GROQ-DIAG] *** message.content    = {getattr(message, 'content', None)!r} ***")
                    print(f"[GROQ-DIAG] *** message.tool_calls = {getattr(message, 'tool_calls', None)} ***")
                    print(f"[GROQ-DIAG] *** reasoning_content  = {reasoning_content!r:.500} ***")
                break

            for tool_call in tool_calls:
                tool_name = getattr(getattr(tool_call, "function", None), "name", None)
                print(f"[GROQ-DIAG] Executing tool: {tool_name}")
                if tool_name:
                    tool_calls_used.append(tool_name)
                tool_result = self.execute_tool_call(tool_call.model_dump() if hasattr(tool_call, "model_dump") else tool_call)
                print(f"[GROQ-DIAG] TOOL RESULT ({tool_name}) = {tool_result}")
                messages.append(tool_result)

                try:
                    content_dict = json.loads(tool_result["content"])
                    if isinstance(content_dict, (dict, list)) and ("error" not in content_dict if isinstance(content_dict, dict) else True):
                        successful_tool_results.append((tool_name, content_dict))
                except Exception:
                    pass
        else:
            print(f"[GROQ-DIAG] *** Exhausted max iterations (5) ***")
            self.logger.warning("Reached maximum tool-calling iterations for query '%s'", user_query)

        if final_answer == "I could not generate a response from the model." and successful_tool_results:
            print("[FALLBACK] Building response from tool results")
            self.logger.info("[FALLBACK] Building response from tool results")
            
            fallback_parts = []
            for t_name, t_data in successful_tool_results:
                if t_name in ("search_stops", "search_stops_in_feed", "nearby_stops"):
                    if isinstance(t_data, list) and len(t_data) > 0:
                        stop = t_data[0]
                        stop_name = stop.get("stop_name", "Unknown Stop")
                        stop_id = stop.get("stop_id", "Unknown ID")
                        fallback_parts.append(f"I found the following stop:\n\n{stop_name} ({stop_id})")
                elif t_name == "find_trip":
                    results = t_data.get("results", [])
                    if not results:
                        fallback_parts.append("I searched available feeds but could not find a route between the requested stops.")
                    else:
                        trip = results[0]
                        source = trip.get("source_stop_name", "Source")
                        dest = trip.get("destination_stop_name", "Destination")
                        feed = trip.get("feed", "unknown feed")
                        fallback_parts.append(f"I found a route from {source} to {dest} in the {feed} feed.")
                elif t_name == "get_available_feeds":
                    if isinstance(t_data, list):
                        fallback_parts.append(f"The available feeds are: {', '.join(str(f) for f in t_data)}")
            
            if fallback_parts:
                final_answer = "\n\n".join(fallback_parts)
                print("[FALLBACK] Generated fallback answer")
                self.logger.info("[FALLBACK] Generated fallback answer")

        print(f"\n[GROQ-DIAG] === RETURNING ===")
        print(f"[GROQ-DIAG] final_answer   = {final_answer!r}")
        print(f"[GROQ-DIAG] tools_used     = {tool_calls_used}")
        print(f"[GROQ-DIAG] is_default_err = {final_answer == 'I could not generate a response from the model.'}")
        print(f"{'='*60}\n")

        self.logger.info(f"RETURN ITERATION: {iteration}")
        self.logger.info(f"RETURN FINAL_ANSWER: {final_answer}")
        self.logger.info(f"RETURN TOOLS_USED: {tool_calls_used}")
        self.logger.info(f"RETURN PROVIDER: groq")

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "answer": final_answer,
            "provider": "groq",
            "tools_used": tool_calls_used,
            "classification": "REASONING_PATH",
            "execution_time_ms": elapsed_ms,
        }


foundry_transit_agent = FoundryTransitAgent()


def _json_default(value: Any) -> Any:
    """Serialize Pydantic models and other non-JSON-native values safely."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)
