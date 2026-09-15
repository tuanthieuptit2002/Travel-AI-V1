"""Tests for structured user travel memory (separate from RAG and chat history)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agent.graph import run_travel_agent
from app.main import app
from app.memory.models import MemoryEvidence, MemoryField, MemoryUpdateRequest
from app.memory.service import MemoryService
from app.memory.store import InMemoryMemoryStore
from app.memory.tools import MemoryRetrievalTool, MemoryUpdateTool
from app.tools import ALL_TOOL_NAMES, ToolDependencies, create_agent_tools


@pytest.fixture
def memory_service() -> MemoryService:
    return MemoryService(store=InMemoryMemoryStore())


def test_update_rejects_conversation_dump(memory_service: MemoryService) -> None:
    user_id = uuid4()
    with pytest.raises(ValueError):
        MemoryUpdateRequest(
            user_id=user_id,
            field=MemoryField.PREFERRED_ACTIVITIES,
            value=["beaches"],
            evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
            source_excerpt=(
                "Hello. I went to Da Nang. Then we ate dinner. After that we walked. "
                "Later we swam. Finally we slept."
            ),
        )


def test_update_rejects_invalid_pace(memory_service: MemoryService) -> None:
    user_id = uuid4()
    with pytest.raises(ValueError):
        MemoryUpdateRequest(
            user_id=user_id,
            field=MemoryField.PREFERRED_TRIP_PACE,
            value="chaotic sprint",
            evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
            source_excerpt="I want a chaotic sprint trip",
        )


def test_memory_service_stores_only_structured_fields(memory_service: MemoryService) -> None:
    user_id = uuid4()
    memory_service.update_memory(
        MemoryUpdateRequest(
            user_id=user_id,
            field=MemoryField.FOOD_PREFERENCES,
            value=["seafood"],
            evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
            source_excerpt="I like seafood",
        )
    )
    memory_service.update_memory(
        MemoryUpdateRequest(
            user_id=user_id,
            field=MemoryField.PREFERRED_TRIP_PACE,
            value="relaxed",
            evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
            source_excerpt="relaxed pace",
        )
    )
    memory = memory_service.get_memory(user_id)
    assert memory.food_preferences == ["seafood"]
    assert memory.preferred_trip_pace == "relaxed"
    assert memory.preferred_activities == []


def test_extract_explicit_updates_does_not_invent(memory_service: MemoryService) -> None:
    user_id = uuid4()
    updates = memory_service.extract_explicit_updates(
        user_id=user_id,
        user_request="Plan 3 days in Da Nang for 2 people with budget 8 million VND.",
    )
    assert updates == []


def test_extract_explicit_like_and_dislike(memory_service: MemoryService) -> None:
    user_id = uuid4()
    updates = memory_service.extract_explicit_updates(
        user_id=user_id,
        user_request=(
            "I want Da Nang for 3 days. I like beaches and photography. "
            "I don't like nightlife. Prefer relaxed pace. Prefer hotel."
        ),
    )
    fields = {item.field for item in updates}
    assert MemoryField.PREFERRED_ACTIVITIES in fields
    assert MemoryField.DISLIKED_ACTIVITIES in fields
    assert MemoryField.PREFERRED_TRIP_PACE in fields
    assert MemoryField.ACCOMMODATION_PREFERENCE in fields


def test_memory_tools_round_trip(memory_service: MemoryService) -> None:
    user_id = uuid4()
    update_tool = MemoryUpdateTool(memory_service)
    retrieve_tool = MemoryRetrievalTool(memory_service)

    written = update_tool.invoke(
        user_id=user_id,
        field=MemoryField.BUDGET_PREFERENCE,
        value="medium",
        evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
        source_excerpt="prefer medium budget",
    )
    assert written.success is True

    loaded = retrieve_tool.invoke(user_id)
    assert loaded.success is True
    assert loaded.memory is not None
    assert loaded.memory["budget_preference"] == "medium"
    assert "medium budget" in loaded.planning_hints


def test_create_agent_tools_includes_memory_tools() -> None:
    tools = {tool.name for tool in create_agent_tools(ToolDependencies.with_mocks())}
    assert "retrieve_user_memory" in tools
    assert "update_user_memory" in tools
    assert tools == ALL_TOOL_NAMES


def test_agent_retrieves_and_updates_memory(memory_service: MemoryService) -> None:
    user_id = uuid4()
    memory_service.update_memory(
        MemoryUpdateRequest(
            user_id=user_id,
            field=MemoryField.PREFERRED_ACTIVITIES,
            value=["photography"],
            evidence=MemoryEvidence.CONFIRMED_PREFERENCE,
            source_excerpt="photography",
        )
    )
    deps = ToolDependencies.with_mocks()
    deps.memory = memory_service

    state = run_travel_agent(
        (
            "I want to travel to Da Nang for 3 days and 2 nights for 2 people. "
            "Budget 8 million VND. I like beaches and local food. I don't like nightlife. "
            "Prefer relaxed pace."
        ),
        user_id=str(user_id),
        dependencies=deps,
    )
    assert state.get("user_memory") is not None
    assert "photography" in (state.get("preferences") or [])
    assert state.get("memory_updates")
    memory = memory_service.get_memory(user_id)
    assert "beaches" in memory.preferred_activities
    assert "nightlife" in memory.disliked_activities
    assert memory.preferred_trip_pace == "relaxed"


def test_agent_without_user_id_skips_memory(memory_service: MemoryService) -> None:
    deps = ToolDependencies.with_mocks()
    deps.memory = memory_service
    state = run_travel_agent(
        "I want to travel to Da Nang for 3 days for 2 people. Budget 8 million VND. I like beaches.",
        dependencies=deps,
    )
    assert state.get("user_memory") is None
    assert state.get("memory_updates") == []


def test_memory_api_view_update_delete() -> None:
    client = TestClient(app)
    user_id = str(uuid4())

    empty = client.get(f"/api/v1/memory/{user_id}")
    assert empty.status_code == 200
    assert empty.json()["preferred_activities"] == []

    created = client.post(
        f"/api/v1/memory/{user_id}",
        json={
            "field": "preferred_destinations",
            "value": ["da nang", "hoi an"],
            "evidence": "explicit_user_statement",
            "source_excerpt": "favorite destinations are Da Nang and Hoi An",
        },
    )
    assert created.status_code == 200
    assert created.json()["preferred_destinations"] == ["da nang", "hoi an"]

    cleared_field = client.delete(f"/api/v1/memory/{user_id}/preferred_destinations")
    assert cleared_field.status_code == 200
    assert cleared_field.json()["preferred_destinations"] == []

    client.post(
        f"/api/v1/memory/{user_id}",
        json={
            "field": "food_preferences",
            "value": ["seafood"],
            "evidence": "explicit_user_statement",
            "source_excerpt": "I like seafood",
        },
    )
    deleted = client.delete(f"/api/v1/memory/{user_id}")
    assert deleted.status_code == 204
    after = client.get(f"/api/v1/memory/{user_id}")
    assert after.json()["food_preferences"] == []
