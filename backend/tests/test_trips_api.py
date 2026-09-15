from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_planning_service, reset_planning_service_cache
from app.main import app
from app.services.planning_service import PlanningService
from app.services.trip_store import InMemoryTripStore
from app.tools import ToolDependencies


EXAMPLE_REQUEST = (
    "I want to travel to Da Nang for 4 days and 3 nights for 2 people. "
    "Budget 8 million VND per person. I like beaches, local food and photography."
)


@pytest.fixture()
def client() -> TestClient:
    store = InMemoryTripStore()
    service = PlanningService(
        store=store,
        dependencies=ToolDependencies.with_mocks(),
        reference_date=date(2026, 10, 12),
    )
    reset_planning_service_cache()
    app.dependency_overrides[get_planning_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    reset_planning_service_cache()


def test_plan_trip_returns_structured_public_response(client: TestClient) -> None:
    response = client.post(
        "/api/v1/trips/plan",
        json={
            "user_request": EXAMPLE_REQUEST,
            "user_id": str(uuid4()),
            "destination": "Da Nang",
            "travelers": 2,
            "budget": 16000000,
            "currency": "VND",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["destination"] == "Da Nang"
    assert payload["travelers"] == 2
    assert payload["budget"] == "16000000"
    assert payload["currency"] == "VND"
    assert payload["trip_id"]
    assert payload["summary"]
    assert payload["itinerary"]
    assert payload["estimated_total_cost"] is not None
    assert "warnings" in payload
    assert payload["recommendations"]
    assert "weather_notes" in payload
    assert payload["progress"]
    assert {step["id"] for step in payload["progress"]} >= {
        "bootstrap",
        "supervisor",
        "place",
        "itinerary",
        "budget",
        "validation",
        "finalize",
    }
    # Never leak internal LangGraph candidate catalogs.
    assert "candidate_places" not in payload
    assert "candidate_restaurants" not in payload
    assert "final_response" not in payload


def test_plan_trip_validation_error(client: TestClient) -> None:
    response = client.post("/api/v1/trips/plan", json={"user_request": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_create_list_and_get_trips(client: TestClient) -> None:
    user_id = str(uuid4())
    create = client.post(
        "/api/v1/trips",
        json={
            "user_id": user_id,
            "destination": "Hoi An",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "travelers": 2,
            "budget": 9000000,
            "currency": "VND",
            "summary": "Manual draft",
            "estimated_total_cost": 1200000,
            "itinerary": [],
            "warnings": [],
            "recommendations": ["Try lantern streets after sunset."],
        },
    )
    assert create.status_code == 201
    trip_id = create.json()["id"]

    listed = client.get("/api/v1/trips", params={"user_id": user_id})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == trip_id

    detail = client.get(f"/api/v1/trips/{trip_id}")
    assert detail.status_code == 200
    assert detail.json()["destination"] == "Hoi An"
    assert detail.json()["recommendations"][0].startswith("Try lantern")


def test_get_missing_trip_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/trips/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Không tìm thấy chuyến đi."


def test_plan_then_fetch_persisted_trip(client: TestClient) -> None:
    planned = client.post(
        "/api/v1/trips/plan",
        json={"user_request": EXAMPLE_REQUEST, "currency": "VND"},
    )
    assert planned.status_code == 200
    trip_id = planned.json()["trip_id"]

    detail = client.get(f"/api/v1/trips/{trip_id}")
    assert detail.status_code == 200
    assert detail.json()["destination"] == "Da Nang"
    assert detail.json()["itinerary"]
