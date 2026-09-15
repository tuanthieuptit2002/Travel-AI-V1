from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.agent import build_travel_agent_graph, run_travel_agent
from app.agent.models import TripItinerary
from app.agent.parser import DeterministicRequestParser
from app.agent.planner import build_grounded_itinerary
from app.agent.validator import validate_itinerary
from app.providers.mock import MockPlacesProvider
from app.tools import ToolDependencies


EXAMPLE_REQUEST = (
    "I want to travel to Da Nang for 4 days and 3 nights for 2 people. "
    "Budget 8 million VND per person. I like beaches, local food and photography."
)


def test_deterministic_parser_extracts_da_nang_request() -> None:
    parsed = DeterministicRequestParser().parse(
        EXAMPLE_REQUEST, reference_date=date(2026, 10, 12)
    )

    assert parsed.destination == "Da Nang"
    assert parsed.travelers == 2
    assert parsed.days == 4
    assert parsed.nights == 3
    assert parsed.budget_per_person == Decimal("8000000")
    assert parsed.budget_total == Decimal("16000000")
    assert parsed.preferences == ["beaches", "local food", "photography"]
    assert parsed.start_date == date(2026, 10, 12)
    assert parsed.end_date == date(2026, 10, 15)


def test_parser_from_to_prefers_destination_over_origin_city() -> None:
    parsed = DeterministicRequestParser().parse(
        "Travel from Ho Chi Minh City to Phu Quoc for 4 days for 2 people. "
        "Budget 18 million VND. I like beaches, seafood and relaxed.",
        reference_date=date(2026, 10, 12),
    )
    assert parsed.destination == "Phu Quoc"
    assert parsed.origin == "Ho Chi Minh City"
    assert parsed.budget_total == Decimal("18000000")
    assert parsed.budget_per_person is None


def test_grounded_itinerary_only_uses_catalog_place_ids() -> None:
    provider = MockPlacesProvider()
    places = [
        provider.get_place_details("vn-danang-my-khe").model_dump(mode="json"),
        provider.get_place_details("vn-danang-marble-mountains").model_dump(mode="json"),
        provider.get_place_details("vn-danang-dragon-bridge").model_dump(mode="json"),
    ]
    restaurants = [
        provider.get_place_details("vn-danang-com-nieu").model_dump(mode="json"),
        provider.get_place_details("vn-danang-madam-lan").model_dump(mode="json"),
    ]
    known_ids = {item["id"] for item in places + restaurants}

    itinerary = build_grounded_itinerary(
        destination="Da Nang",
        origin=None,
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 13),
        travelers=2,
        total_budget=Decimal("16000000"),
        currency="VND",
        preferences=["beaches", "photography"],
        candidate_places=places,
        candidate_restaurants=restaurants,
    )

    assert len(itinerary.days) == 2
    for day in itinerary.days:
        assert day.activities
        for activity in day.activities:
            assert activity.place_id in known_ids
            assert activity.estimated_cost >= 0
            assert activity.latitude and activity.longitude


def test_validator_flags_budget_and_duplicate_issues() -> None:
    provider = MockPlacesProvider()
    place = provider.get_place_details("vn-danang-my-khe").model_dump(mode="json")
    restaurant = provider.get_place_details("vn-danang-com-nieu").model_dump(mode="json")
    itinerary = build_grounded_itinerary(
        destination="Da Nang",
        origin=None,
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 12),
        travelers=2,
        total_budget=Decimal("1000"),
        currency="VND",
        preferences=["beaches"],
        candidate_places=[place],
        candidate_restaurants=[restaurant],
    )
    # Force a same-day duplicate to verify the check.
    itinerary.days[0].activities[0].place_id = itinerary.days[0].activities[-1].place_id

    errors = validate_itinerary(
        itinerary,
        known_place_ids=[place["id"], restaurant["id"]],
        weather_available=True,
    )

    assert any("vượt ngân sách" in error or "exceeds budget" in error for error in errors)
    assert any("Trùng place_id" in error or "Duplicate place_id" in error for error in errors)


def test_travel_agent_graph_builds_valid_da_nang_plan() -> None:
    result = run_travel_agent(
        EXAMPLE_REQUEST,
        dependencies=ToolDependencies.with_mocks(),
        reference_date=date(2026, 10, 12),
    )

    assert result["destination"] == "Da Nang"
    assert result["travelers"] == 2
    assert result["budget"] == "16000000"
    assert result["candidate_places"]
    assert result["candidate_restaurants"]
    assert result["weather"]
    assert len(result["weather"]) == 4

    itinerary = TripItinerary.model_validate(result["itinerary"])
    assert len(itinerary.days) == 4
    assert itinerary.estimated_total_cost <= itinerary.total_budget

    catalog_ids = {
        item["id"] for item in result["candidate_places"] + result["candidate_restaurants"]
    }
    for day in itinerary.days:
        day_ids = [activity.place_id for activity in day.activities]
        assert len(day_ids) == len(set(day_ids))
        for activity in day.activities:
            assert activity.place_id in catalog_ids
            assert "reason" in activity.model_dump()

    final = result["final_response"]
    assert final["is_valid"] is True
    assert final["validation_errors"] == []
    assert "Da Nang" in final["headline"]
    assert final["weather_notes"]
    assert final["budget_notes"]


def test_travel_agent_graph_node_order() -> None:
    app = build_travel_agent_graph(reference_date=date(2026, 10, 12))
    graph = app.get_graph()
    node_ids = set(graph.nodes)
    for name in {
        "bootstrap",
        "supervisor",
        "flight",
        "hotel",
        "place",
        "weather",
        "itinerary",
        "budget",
        "validation",
        "fallback",
        "finalize",
        "update_memory",
    }:
        assert name in node_ids


def test_multi_agent_skips_flight_without_origin() -> None:
    result = run_travel_agent(
        EXAMPLE_REQUEST,
        dependencies=ToolDependencies.with_mocks(),
        reference_date=date(2026, 10, 12),
    )
    assert "flight" not in (result.get("completed_agents") or [])
    assert "hotel" in (result.get("completed_agents") or [])
    assert "place" in (result.get("completed_agents") or [])
    assert "validation" in (result.get("completed_agents") or [])
    assert result.get("iteration", 0) > 0
    assert result.get("fallback_used") is False


def test_multi_agent_includes_flight_when_origin_present() -> None:
    result = run_travel_agent(
        "Travel from Hanoi to Da Nang for 3 days for 2 people. Budget 20 million VND. "
        "I like beaches and local food.",
        dependencies=ToolDependencies.with_mocks(),
        reference_date=date(2026, 10, 12),
    )
    assert "flight" in (result.get("completed_agents") or [])
    assert result.get("candidate_flights") is not None
    assert result["final_response"]["is_valid"] is True


def test_travel_agent_includes_knowledge_citations_when_seeded() -> None:
    from pathlib import Path

    from app.knowledge.embeddings import HashEmbeddingProvider
    from app.knowledge.service import KnowledgeService
    from app.knowledge.store import InMemoryKnowledgeStore

    knowledge = KnowledgeService(
        store=InMemoryKnowledgeStore(),
        embeddings=HashEmbeddingProvider(dimensions=64),
        knowledge_root=Path(__file__).resolve().parents[2] / "knowledge",
    )
    knowledge.ingest_directory()
    dependencies = ToolDependencies.with_mocks()
    dependencies.knowledge = knowledge

    result = run_travel_agent(
        EXAMPLE_REQUEST,
        dependencies=dependencies,
        reference_date=date(2026, 10, 12),
    )
    assert result["knowledge_hits"] is not None
    final = result["final_response"]
    assert "citations" in final
