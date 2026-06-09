"""Tests for the Foundry-facing transit agent service."""

from app.services.foundry_agent import FoundryTransitAgent


def test_foundry_agent_exposes_expected_tool_names() -> None:
    """The Foundry tool contract should expose the required transit tools."""
    service = FoundryTransitAgent()

    tool_names = {tool["function"]["name"] for tool in service.tool_definitions()}

    assert {"get_available_feeds", "search_stops", "search_stops_in_feed", "nearby_stops"} <= tool_names


def test_foundry_agent_can_execute_tool_calls() -> None:
    """The service should execute a tool call via the existing tool wrapper layer."""
    service = FoundryTransitAgent()

    result = service.execute_tool_call(
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "search_stops",
                "arguments": '{"query": "Egmore"}',
            },
        }
    )

    assert isinstance(result, dict)
    assert "content" in result
