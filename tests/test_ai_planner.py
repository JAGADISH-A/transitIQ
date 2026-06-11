"""Tests for the AI planner functionality."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.schemas import StopResult
from app.services.ai_planner import ai_planner


@pytest.fixture()
def sample_stop() -> StopResult:
    """Create a representative stop result used by planner tests."""
    return StopResult(
        stop_id="STOP_1",
        stop_name="Chennai Central",
        lat=13.0827,
        lon=80.2707,
    )


def test_answer_query_handles_take_me_to_destination(monkeypatch, sample_stop):
    """A natural-language query should resolve to the destination stop."""
    calls = {}

    def fake_search_stops(query: str):
        calls["query"] = query
        return [sample_stop]

    monkeypatch.setattr("app.services.agent_tools.agent_tools.search_stops", fake_search_stops)

    response = ai_planner.answer_query("Take me to Chennai Central")

    assert response["success"] is True
    assert response["destination"] == "Chennai Central"
    assert response["stop_id"] == "STOP_1"
    assert calls["query"] == "Chennai Central"


def test_answer_query_handles_go_to_destination(monkeypatch):
    """Queries using 'Go to' should also resolve the destination phrase."""
    fake_stop = StopResult(stop_id="STOP_2", stop_name="Egmore", lat=13.0837, lon=80.2702)

    def fake_search_stops(query: str):
        assert query == "Egmore"
        return [fake_stop]

    monkeypatch.setattr("app.services.agent_tools.agent_tools.search_stops", fake_search_stops)

    response = ai_planner.answer_query("Go to Egmore")

    assert response["success"] is True
    assert response["destination"] == "Egmore"
    assert response["stop_id"] == "STOP_2"


def test_answer_query_returns_error_for_empty_input():
    """Empty user input should return a structured failure response."""
    response = ai_planner.answer_query("   ")

    assert response == {
        "success": False,
        "answer": "I could not find a matching destination.",
    }


def test_answer_query_returns_error_for_unknown_destination(monkeypatch):
    """Unknown destinations should return a failure response instead of raising."""

    def fake_search_stops(query: str):
        return []

    monkeypatch.setattr("app.services.agent_tools.agent_tools.search_stops", fake_search_stops)

    response = ai_planner.answer_query("Take me to Unknown Station")

    assert response == {
        "success": False,
        "answer": "I could not find a matching destination.",
    }


def test_answer_query_handles_search_failures_gracefully(monkeypatch):
    """Planner lookup exceptions should not crash the caller."""

    def fake_search_stops(query: str):
        raise RuntimeError("lookup failed")

    monkeypatch.setattr("app.services.agent_tools.agent_tools.search_stops", fake_search_stops)

    response = ai_planner.answer_query("Take me to Chennai Central")

    assert response["success"] is False
    assert response["answer"] == "I could not find a matching destination."
