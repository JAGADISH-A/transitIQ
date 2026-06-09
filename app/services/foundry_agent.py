"""Microsoft Foundry / Azure AI Foundry tool-calling integration for TransitIQ.

This service keeps the existing FastAPI and TransitAgentTools architecture intact,
while adding a Foundry-compatible tool-calling layer powered by the Azure AI
Projects SDK. The model can decide which transit tool to invoke, and this class
executes those tool calls and returns a final natural-language response.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.config import get_settings
from app.services.agent_tools import agent_tools
from app.services.ai_planner import ai_planner


class FoundryTransitAgent:
    """Use Azure AI Foundry tool-calling to answer transit questions.

    The service intentionally uses the existing TransitAgentTools wrapper as the
    source of truth for GTFS lookups. Foundry only decides which tool to call and
    receives structured outputs back from the tool layer.
    """

    def __init__(self, project_endpoint: Optional[str] = None, model_deployment: Optional[str] = None) -> None:
        """Initialize the Foundry integration.

        Args:
            project_endpoint: Azure AI Foundry project endpoint. If omitted,
                the value is read from environment settings.
            model_deployment: Model deployment name for the Foundry chat model.
                If omitted, the setting value is used or a safe default is chosen.
        """
        self.logger = logging.getLogger(__name__)
        settings = get_settings()
        

        self.project_endpoint = project_endpoint or getattr(settings, "FOUNDRY_PROJECT_ENDPOINT", None)
        self.openai_endpoint = getattr(settings, "FOUNDRY_AZURE_OPENAI_ENDPOINT", None)
        
        if not self.openai_endpoint:
            self.openai_endpoint = getattr(settings, "FOUNDRY_PROJECT_OPENAI_ENDPOINT", None)
        if not self.openai_endpoint:
            self.openai_endpoint = self.project_endpoint
        self.model_deployment = model_deployment or getattr(settings, "FOUNDRY_MODEL_DEPLOYMENT", "gpt-4o-mini")
        self._openai_client = None

        print("OPENAI_ENDPOINT =", self.openai_endpoint)
        print("DEPLOYMENT =", self.model_deployment)
        print("API_KEY_PRESENT =", bool(settings.FOUNDRY_API_KEY))

        self.logger.info("Using Azure OpenAI endpoint: %s", self.openai_endpoint)
        self.logger.info("Using deployment: %s", self.model_deployment)

        if self.openai_endpoint:
            try:
                self._openai_client = OpenAI(
                    base_url=self.openai_endpoint,
                    api_key=settings.FOUNDRY_API_KEY,
                )
                self.logger.info("Foundry client initialized for endpoint %s", self.openai_endpoint)
            except Exception as exc:  # pragma: no cover - runtime integration path
                self.logger.warning("Foundry client initialization failed: %s", exc)
                self._openai_client = None

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

    def _tool_handler(self, name: str) -> Any:
        """Return a callable for the named tool, using the existing wrapper class."""
        handlers = {
            "get_available_feeds": agent_tools.get_available_feeds,
            "search_stops": agent_tools.search_stops,
            "search_stops_in_feed": agent_tools.search_stops_in_feed,
            "nearby_stops": agent_tools.nearby_stops,
        }
        if name not in handlers:
            raise ValueError(f"Unsupported tool '{name}'.")
        return handlers[name]

    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a model-requested function call and return the tool result.

        The returned structure is compatible with the OpenAI/Foundry tool-calling
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

    def answer(self, user_query: str) -> Dict[str, Any]:
        """Answer the user query using Foundry tool-calling when available.

        If the Foundry project endpoint is not configured, the method falls back to
        the existing planner logic so the API remains usable in local development.
        """
        if not isinstance(user_query, str) or not user_query.strip():
            return {"answer": "I can help with transit questions. Please provide a destination or location query.", "provider": "local"}

        if self._openai_client is None:
            print("OPENAI CLIENT IS NONE")
            self.logger.warning("Foundry client unavailable; using local planner fallback for query '%s'", user_query)
            return {
                "answer": ai_planner.answer_query(user_query).get("answer", "I could not find a matching destination."),
                "provider": "local",
            }

        system_prompt = (
            "You are TransitIQ, a helpful transit assistant. "
            "Use the available GTFS tools to answer questions about stops, feeds, and nearby locations. "
            "Prefer concise, natural-language answers based on the tool results."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        tool_calls_used: List[str] = []
        final_answer = "I could not generate a response from the Foundry model."

        for _ in range(5):
            response = self._openai_client.chat.completions.create(
                model=self.model_deployment,
                messages=messages,
                tools=self.tool_definitions(),
                tool_choice="auto",
                temperature=0.1,
            )

            message = response.choices[0].message
            assistant_message = message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else {
                "role": getattr(message, "role", "assistant"),
                "content": getattr(message, "content", None),
            }
            messages.append(assistant_message)

            tool_calls = getattr(message, "tool_calls", None) or []
            if not tool_calls:
                final_answer = getattr(message, "content", None) or final_answer
                break

            for tool_call in tool_calls:
                tool_name = getattr(getattr(tool_call, "function", None), "name", None)
                if tool_name:
                    tool_calls_used.append(tool_name)
                tool_result = self.execute_tool_call(tool_call.model_dump() if hasattr(tool_call, "model_dump") else tool_call)
                messages.append(tool_result)
        else:
            self.logger.warning("Reached maximum tool-calling iterations for query '%s'", user_query)

        return {
            "answer": final_answer,
            "provider": "foundry",
            "tools_used": tool_calls_used,
        }


foundry_transit_agent = FoundryTransitAgent()


def _json_default(value: Any) -> Any:
    """Serialize Pydantic models and other non-JSON-native values safely."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)
