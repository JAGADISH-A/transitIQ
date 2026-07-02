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


# ---------------------------------------------------------------------------
# Known tool names — used by recovery parser to match reasoning text
# ---------------------------------------------------------------------------
_KNOWN_TOOLS = frozenset({
    "get_available_feeds",
    "search_stops",
    "search_stops_in_feed",
    "nearby_stops",
    "find_trip",
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

        self.logger.info("[GROQ-INIT] Model: %s", self.model)
        self.logger.info("[GROQ-INIT] API key present: %s", bool(self.api_key))

        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
                self.logger.info("[GROQ-INIT] Groq client initialized.")
            except Exception as exc:
                self.logger.error("[GROQ-INIT] Failed to initialize Groq client: %s", exc)
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
        """Return the JSON-schema tool definitions exposed to the model."""
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
                    "description": "Find transit stops within one specific GTFS feed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Text to search in stop names or IDs.",
                            },
                            "feed": {
                                "type": "string",
                                "minLength": 1,
                                "description": "The GTFS feed name to search in.",
                            },
                        },
                        "required": ["query", "feed"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "nearby_stops",
                    "description": "Find nearby stops for a feed and coordinate pair.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "feed": {
                                "type": "string",
                                "minLength": 1,
                                "description": "The GTFS feed name.",
                            },
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
                        "required": ["feed", "lat", "lon"],
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
        }
        if name not in handlers:
            raise ValueError(f"Unsupported tool '{name}'.")
        return handlers[name]

    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a model-requested function call and return the tool result.

        The returned structure is compatible with the OpenAI/Groq tool-calling
        protocol, so the model can continue reasoning over the structured output.
        """
        try:
            tool_name = (tool_call.get("function") or {}).get("name")
            raw_arguments = (tool_call.get("function") or {}).get("arguments", "{}")
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments

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
    # Rich Route Context Builder
    # ------------------------------------------------------------------

    def build_structured_route_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Build a rich, structured route narrative context from raw dictionary.

        Omit missing/empty fields entirely to avoid placeholders.
        """
        route = context.get('route', {})
        if not route:
            self.logger.warning("[BUILD-CTX] route missing from context — keys=%s", list(context.keys()) if isinstance(context, dict) else "N/A")
            return {}

        transfer_risk = context.get('transferRisk', {})
        recommendation = context.get('recommendation', {})
        intel = context.get('workspaceIntelligence', {})
        all_routes = context.get('allRoutes', [])

        structured = {}

        # 1. Format duration helper
        def get_duration_str(mins: Any) -> Optional[str]:
            if not mins:
                return None
            try:
                m = int(float(mins))
                if m < 60:
                    return f"{m}m"
                h = m // 60
                rem_m = m % 60
                return f"{h}h {rem_m}m" if rem_m > 0 else f"{h}h"
            except (ValueError, TypeError):
                return str(mins)

        # Helper to validate a value is not empty or a placeholder
        def is_valid(val: Any) -> bool:
            if val is None:
                return False
            val_str = str(val).strip().upper()
            if not val_str or val_str in ("N/A", "UNKNOWN", "NONE", "UNDEFINED"):
                return False
            return True

        # 2. journeySummary
        source = route.get("sourceName")
        dest = route.get("destName")
        dep_time = route.get("departureTime")
        arr_time = route.get("arrivalTime")
        duration = get_duration_str(route.get("durationMinutes"))
        transfers = route.get("transferCount", 0)

        summary_parts = []
        if is_valid(source) and is_valid(dest):
            summary_parts.append(f"{source} to {dest}")
        if is_valid(dep_time):
            summary_parts.append(f"departing at {dep_time}")
        if is_valid(arr_time):
            summary_parts.append(f"arriving at {arr_time}")
        if is_valid(duration):
            summary_parts.append(f"({duration} total)")

        if transfers == 0:
            summary_parts.append("direct service")
        elif transfers == 1:
            transfer_station = route.get("transferStopName")
            if is_valid(transfer_station):
                summary_parts.append(f"1 transfer at {transfer_station}")
            else:
                summary_parts.append("1 transfer")
        else:
            summary_parts.append(f"{transfers} transfers")

        if summary_parts:
            structured["journeySummary"] = " ".join(summary_parts)

        # 3. transferDetails (omit if direct)
        if transfers > 0:
            transfer_station = route.get("transferStopName")
            wait_mins = route.get("transferWait")
            details = []
            if is_valid(transfer_station):
                details.append(f"Connection at {transfer_station}.")
            if wait_mins is not None:
                try:
                    w = int(float(wait_mins))
                    details.append(f"Waiting time is {w} minutes.")
                except (ValueError, TypeError):
                    details.append(f"Waiting time is {wait_mins} minutes.")

            # Advice / instructions
            risk_message = transfer_risk.get("message")
            if is_valid(risk_message):
                details.append(risk_message)

            if details:
                structured["transferDetails"] = " ".join(details)

        # 4. recommendationReasons
        reasons = recommendation.get("reasons") or []
        rec_reason_str = recommendation.get("reason")
        if rec_reason_str and rec_reason_str not in reasons:
            reasons = [rec_reason_str] + list(reasons)

        valid_reasons = [r for r in reasons if is_valid(r)]
        if valid_reasons:
            structured["recommendationReasons"] = valid_reasons

        # 5. tradeoffs
        # Extract from comparison tradeoff objects
        tradeoff_objs = recommendation.get("comparison", {}).get("tradeoffs", []) or []
        tradeoff_list = []
        for t in tradeoff_objs:
            title = t.get("title")
            desc = t.get("description")
            if is_valid(title) and is_valid(desc):
                tradeoff_list.append(f"{title}: {desc}")
            elif is_valid(desc):
                tradeoff_list.append(desc)

        # Also check direct tradeoffs list if any
        direct_tradeoffs = context.get("tradeoffs", []) or []
        for t in direct_tradeoffs:
            if isinstance(t, dict):
                desc = t.get("description") or t.get("title")
                if is_valid(desc):
                    tradeoff_list.append(desc)
            elif is_valid(t):
                tradeoff_list.append(str(t))

        if tradeoff_list:
            structured["tradeoffs"] = tradeoff_list

        # 6. travelTips
        tips = intel.get("tips") or []
        valid_tips = [t for t in tips if is_valid(t)]
        if valid_tips:
            structured["travelTips"] = valid_tips

        # 7. riskAssessment
        risk_lvl = transfer_risk.get("level")
        risk_msg = transfer_risk.get("message")
        risk_title = transfer_risk.get("title")

        risk_parts = []
        if is_valid(risk_lvl):
            risk_parts.append(f"Level: {risk_lvl.upper()}")
        if is_valid(risk_title):
            risk_parts.append(risk_title)
        if is_valid(risk_msg) and risk_msg not in risk_parts:
            risk_parts.append(risk_msg)

        if risk_parts:
            structured["riskAssessment"] = " — ".join(risk_parts)

        # 8. bestAlternative & alternativeReason (Alternatives should be ranked)
        if all_routes:
            active_id = route.get("id")
            # Filter out active route
            alts = [r for r in all_routes if r.get("id") != active_id]
            if alts:
                # Rank: If active is NOT the recommended route, the recommended route is the best alternative
                rec_route_id = recommendation.get("recommendedRouteId")
                best_alt = None
                alt_reason = ""

                if rec_route_id and active_id != rec_route_id:
                    rec_alt = next((r for r in alts if r.get("id") == rec_route_id), None)
                    if rec_alt:
                        best_alt = rec_alt
                        alt_reason = "This is TransitIQ's recommended route because it offers the optimal balance of speed and transfer safety."

                # Otherwise, find the fastest alternative or the one with fewer transfers
                if not best_alt:
                    # Sort alternatives by duration
                    sorted_alts = sorted(alts, key=lambda x: x.get("durationMinutes", 999999))
                    if sorted_alts:
                        best_alt = sorted_alts[0]
                        active_dur = route.get("durationMinutes", 0)
                        best_alt_dur = best_alt.get("durationMinutes", 0)

                        if best_alt_dur < active_dur:
                            diff = active_dur - best_alt_dur
                            alt_reason = f"Faster journey by {diff} minutes, but requires {best_alt.get('transferCount', 0)} transfer(s)."
                        elif best_alt.get("transferCount", 0) < route.get("transferCount", 0):
                            alt_reason = "Requires fewer connections, making it a more direct but potentially slower choice."
                        else:
                            alt_reason = "An alternative route choice with a different time schedule."

                if best_alt:
                    alt_duration = get_duration_str(best_alt.get("durationMinutes"))
                    structured["bestAlternative"] = {
                        "source": best_alt.get("sourceName"),
                        "destination": best_alt.get("destName"),
                        "duration": alt_duration,
                        "transfers": best_alt.get("transferCount", 0),
                        "transferStation": best_alt.get("transferStopName") if best_alt.get("isTransfer") else None
                    }
                    # Clean bestAlternative dictionary of any invalid values
                    structured["bestAlternative"] = {k: v for k, v in structured["bestAlternative"].items() if is_valid(v)}
                    structured["alternativeReason"] = alt_reason

        # 9. Real Delay Data (only if real delay data exists)
        if "delayMinutes" in route and is_valid(route.get("delayMinutes")):
            structured["delayMinutes"] = route.get("delayMinutes")
        if "delayStatus" in route and is_valid(route.get("delayStatus")):
            structured["delayStatus"] = route.get("delayStatus")

        # 10. Stop Sequence (intermediate stations)
        stop_sequence = context.get('stopSequence') if isinstance(context, dict) else None
        if stop_sequence and isinstance(stop_sequence, list) and len(stop_sequence) > 0:
            valid_stops = []
            transfer_marker = {"stop_name": "--- TRANSFER ---", "stop_sequence": -1}
            for s in stop_sequence:
                if isinstance(s, dict):
                    name = s.get('stop_name', '')
                    seq = s.get('stop_sequence', 0)
                    if name == '---transfer---':
                        valid_stops.append(transfer_marker)
                    elif name:
                        valid_stops.append({"stop_name": name, "stop_sequence": seq})
            if valid_stops:
                self.logger.info("[BUILD-CTX] stopSequence: %d valid stops", len(valid_stops))
                structured["stopSequence"] = valid_stops

        return structured

    # ------------------------------------------------------------------
    # Main answer method
    # ------------------------------------------------------------------

    def answer(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Answer the user query using Foundry tool-calling when available.

        If the Foundry project endpoint is not configured, the method falls back to
        the existing planner logic so the API remains usable in local development.
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
        self.logger.warning("[ANSWER-DEBUG] context provided = %s", context is not None)
        if context:
            self.logger.warning("[ANSWER-DEBUG] context keys = %s", list(context.keys()) if isinstance(context, dict) else "N/A")

        if not isinstance(user_query, str) or not user_query.strip():
            return {"answer": "I can help with transit questions. Please provide a destination or location query.", "provider": "local"}

        if self._client is None:
            self.logger.warning("[GROQ] Client unavailable — using local planner fallback for query '%s'", user_query)
            return {
                "answer": ai_planner.answer_query(user_query).get("answer", "I could not find a matching destination."),
                "provider": "local",
            }

        system_prompt = (
            "You are TransitIQ, a professional railway transit assistant. "
            "Use the available GTFS tools when you need data about stops, feeds, or routes. "
            "Always use the loaded journey context when available.\n\n"
            "RESPONSE RULES (MANDATORY):\n"
            "1. **Answer the question first.** Lead with the direct answer. No preamble.\n"
            "2. **5-sentence maximum** unless the user explicitly asks for details or a breakdown. "
            "Most questions need 2-3 sentences.\n"
            "3. **Never repeat information the user already sees.** The UI shows the route, "
            "stations, departure/arrival times, duration, and transfer station in a context banner. "
            "Do NOT restate these unless the user specifically asks about them.\n"
            "4. **No filler.** Never say: 'Safe travels', 'Have a great journey', 'Happy traveling', "
            "'Set an alarm', 'Wishing you...', or any motivational/sign-off text. "
            "Do not add generic travel advice unless there is a real, specific risk.\n"
            "5. **No templates.** Do not force emoji-labeled sections (🚆 Departure, 🏁 Arrival) "
            "for every answer. Use structured formatting ONLY for timeline/timing breakdowns "
            "when the user asks 'what are the timings?' or similar.\n"
            "6. **Direct routes = short answers.** For direct (non-transfer) journeys, "
            "give a brief confirmation, mention the departure time, suggest an arrival buffer "
            "(5-10 min), and stop. Do not elaborate further.\n"
            "7. **Transfers = be specific.** For transfer journeys, state the transfer station, "
            "the connection window, and whether it is comfortable (>15 min), moderate (8-15 min), "
            "or tight (<8 min). One sentence of practical advice if tight. No more.\n"
            "8. **Grounding.** Always reference actual station names, times, and durations from context. "
            "Never answer generically.\n"
            "9. **Ambiguous follow-ups** (e.g., 'food?', 'luggage?', 'safety?') should be answered "
            "specifically for the loaded journey. Keep it to 2-3 sentences with actionable info.\n\n"
            "CRITICAL TOOL-CALLING RULES:\n"
            "- When you need external data, you MUST emit a proper tool_call using the OpenAI function-calling format.\n"
            "- NEVER write tool names or JSON arguments inside your reasoning or response text.\n"
            "- NEVER describe a tool call in prose instead of actually invoking it.\n"
            "- If you need to call a tool, use the tool_calls mechanism. Do NOT output the call as text.\n"
            "- Each tool call must include the function name and a valid JSON arguments object.\n"
            "- After receiving tool results, synthesize a concise answer following the rules above."
        )

        if context:
            try:
                # Format context clearly for the LLM using our Structured Context Builder
                structured_ctx = self.build_structured_route_context(context)
                self.logger.warning("[ANSWER-DEBUG] structured_ctx keys = %s", list(structured_ctx.keys()) if structured_ctx else "EMPTY")
                self.logger.warning("[ANSWER-DEBUG] has stopSequence in structured_ctx = %s", 'stopSequence' in structured_ctx if structured_ctx else False)
                
                if structured_ctx:
                    import json
                    ctx_json = json.dumps(structured_ctx, indent=2)
                    self.logger.warning("[ANSWER-DEBUG] system_prompt context JSON:\n%s", ctx_json)
                    system_prompt += (
                        f"\n\n--- Current Journey Context (JSON Structured Facts) ---\n"
                        f"{ctx_json}\n\n"
                        f"Answer the user's questions specifically referencing the loaded journey facts. "
                        f"Apply the journey context to all ambiguous queries (e.g., questions about food, safety, luggage, or timing)."
                    )
                    self.logger.info("Injected journey context JSON into system prompt.")
            except Exception as e:
                self.logger.warning("Failed to format context: %s", e)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        tool_calls_used: List[str] = []
        successful_tool_results: List[tuple] = []
        final_answer = "I could not generate a response from the model."

        self.logger.debug("[GROQ-DIAG] START query=%r", user_query)

        iteration = 0
        for _ in range(5):
            iteration += 1
            self.logger.debug("[GROQ-DIAG] Loop iteration %d, messages=%d", iteration, len(messages))

            try:
                self.logger.warning("[GROQ-DIAG] Calling Groq API: model=%s, messages_count=%d, tools_count=%d",
                    self.model, len(messages), len(self.tool_definitions()))
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tool_definitions(),
                    tool_choice="auto",
                    temperature=0.1,
                )
                self.logger.warning("[GROQ-DIAG] Groq API call succeeded")
            except Exception as api_exc:
                self.logger.error("[GROQ-DIAG] Groq API call failed: %s", api_exc)
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "answer": ai_planner.answer_query(user_query).get("answer", "I could not find a matching destination."),
                    "provider": "local",
                    "classification": "ERROR_FALLBACK",
                    "execution_time_ms": elapsed_ms,
                    "tools_used": [],
                }

            if not response.choices:
                self.logger.warning("[GROQ-DIAG] WARNING: response.choices is empty/None!")
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "answer": ai_planner.answer_query(user_query).get("answer", "I could not generate a response."),
                    "provider": "local",
                    "classification": "ERROR_FALLBACK",
                    "execution_time_ms": elapsed_ms,
                    "tools_used": [],
                }

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            self.logger.debug(
                "[GROQ-DIAG] iter=%d finish_reason=%s role=%s tool_calls=%s",
                iteration, finish_reason, getattr(message, 'role', 'N/A'),
                getattr(message, 'tool_calls', None)
            )

            # Check for reasoning_content
            reasoning_content = getattr(message, "reasoning_content", None) or ""
            if reasoning_content:
                self.logger.debug("[GROQ-DIAG] reasoning_content present (%d chars)", len(reasoning_content))

            assistant_message = message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else {
                "role": getattr(message, "role", "assistant"),
                "content": getattr(message, "content", None),
            }
            self.logger.debug("[GROQ-DIAG] assistant_message appended (role=%s)", assistant_message.get('role', 'N/A'))
            messages.append(assistant_message)

            self.logger.info(f"COMPLETION FINISH_REASON: {finish_reason}")
            self.logger.info(f"COMPLETION CONTENT: {getattr(message, 'content', None)}")
            self.logger.info(f"COMPLETION TOOL_CALLS: {getattr(message, 'tool_calls', None)}")
            self.logger.info(f"COMPLETION REASONING: {reasoning_content}")

            tool_calls = getattr(message, "tool_calls", None) or []
            self.logger.debug("[GROQ-DIAG] tool_calls count=%d", len(tool_calls))

            if not tool_calls:
                raw_content = getattr(message, "content", None)

                # ---------------------------------------------------------
                # RECOVERY: detect reasoning_content with embedded tool call
                # ---------------------------------------------------------
                if not raw_content and reasoning_content:
                    self.logger.debug("[RECOVERY] Model failed to emit tool_call (iter %d), reasoning_content detected (%d chars)", iteration, len(reasoning_content))
                    self.logger.warning(
                        "[RECOVERY] reasoning_content fallback triggered for query '%s'",
                        user_query,
                    )

                    recovered = self._recover_from_reasoning(reasoning_content, user_query)

                    if recovered is not None:
                        recovered_tool, recovered_args = recovered
                        self.logger.debug("[RECOVERY] Tool inferred: %s args=%s", recovered_tool, recovered_args)

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
                        self.logger.debug("[RECOVERY] Executing recovered tool: %s", recovered_tool)
                        tool_result = self.execute_tool_call(synthetic_tool_call)
                        self.logger.debug("[RECOVERY] Tool completed")
                        messages.append(tool_result)

                        try:
                            content_dict = json.loads(tool_result["content"])
                            if isinstance(content_dict, (dict, list)) and ("error" not in content_dict if isinstance(content_dict, dict) else True):
                                successful_tool_results.append((recovered_tool, content_dict))
                        except Exception:
                            pass

                        self.logger.debug("[RECOVERY] Continuing conversation loop")

                        # Continue — next iteration sends tool result to model.
                        continue
                    else:
                        self.logger.debug("[RECOVERY] All recovery tiers failed — no tool or args could be extracted")
                        self.logger.warning(
                            "[RECOVERY] All tiers failed for reasoning_content: %s",
                            reasoning_content[:500],
                        )

                # Normal exit: model returned text content (or nothing)
                self.logger.debug("[GROQ-DIAG] No tool calls — extracting final answer, raw_content bool=%s", bool(raw_content))
                
                # If raw_content is falsy, but reasoning_content has text (and we didn't recover a tool),
                # use reasoning_content as the final answer instead of falling back to default error.
                if not raw_content and reasoning_content:
                    final_answer = reasoning_content
                else:
                    final_answer = raw_content or final_answer
                
                if final_answer == "I could not generate a response from the model.":
                    self.logger.warning("[GROQ-DIAG] BUG: content was falsy, fell back to default error string. choices=%d", len(response.choices) if response.choices else 0)
                break

            for tool_call in tool_calls:
                tool_name = getattr(getattr(tool_call, "function", None), "name", None)
                self.logger.debug("[GROQ-DIAG] Executing tool: %s", tool_name)
                if tool_name:
                    tool_calls_used.append(tool_name)
                tool_result = self.execute_tool_call(tool_call.model_dump() if hasattr(tool_call, "model_dump") else tool_call)
                self.logger.debug("[GROQ-DIAG] TOOL RESULT (%s) received", tool_name)
                messages.append(tool_result)

                try:
                    content_dict = json.loads(tool_result["content"])
                    if isinstance(content_dict, (dict, list)) and ("error" not in content_dict if isinstance(content_dict, dict) else True):
                        successful_tool_results.append((tool_name, content_dict))
                except Exception:
                    pass
        else:
            self.logger.warning("[GROQ-DIAG] Exhausted max iterations (5)")
            self.logger.warning("Reached maximum tool-calling iterations for query '%s'", user_query)

        if final_answer == "I could not generate a response from the model." and successful_tool_results:
            self.logger.info("[FALLBACK] Building response from tool results")
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
                self.logger.info("[FALLBACK] Generated fallback answer")
                self.logger.info("[FALLBACK] Generated fallback answer")

        self.logger.debug("[GROQ-DIAG] RETURNING tools_used=%s is_default_err=%s", tool_calls_used, final_answer == 'I could not generate a response from the model.')

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
