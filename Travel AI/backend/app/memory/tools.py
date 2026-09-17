"""LangChain tools for retrieving and updating structured user travel memory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.tools import StructuredTool
from pydantic import Field

from app.memory.models import MemoryEvidence, MemoryField, MemoryUpdateRequest
from app.memory.service import MemoryService
from app.tools.safe import run_safely
from app.tools.schemas import ToolInput, ToolOutput


class RetrieveUserMemoryInput(ToolInput):
    user_id: UUID


class RetrieveUserMemoryOutput(ToolOutput):
    memory: Optional[Dict[str, Any]] = None
    planning_hints: List[str] = Field(default_factory=list)


class UpdateUserMemoryInput(ToolInput):
    user_id: UUID
    field: MemoryField
    value: Union[str, List[str]]
    evidence: MemoryEvidence = MemoryEvidence.EXPLICIT_USER_STATEMENT
    source_excerpt: Optional[str] = Field(default=None, max_length=200)


class UpdateUserMemoryOutput(ToolOutput):
    memory: Optional[Dict[str, Any]] = None
    updated_field: Optional[str] = None


class MemoryRetrievalTool:
    """Read-only tool: load validated long-term preferences before planning."""

    name = "retrieve_user_memory"
    description = (
        "Retrieve structured long-term travel preferences for a user "
        "(destinations, activities, food, pace, budget, accommodation, transport). "
        "Does not return conversation history or RAG knowledge documents."
    )

    def __init__(self, service: Optional[MemoryService] = None) -> None:
        self.service = service or MemoryService()

    def invoke(self, user_id: UUID) -> RetrieveUserMemoryOutput:
        memory = self.service.get_memory(user_id)
        return RetrieveUserMemoryOutput(
            success=True,
            memory=memory.model_dump(mode="json"),
            planning_hints=memory.as_planning_hints(),
        )

    def as_langchain_tool(self) -> StructuredTool:
        def retrieve_user_memory(user_id: UUID) -> dict:
            return run_safely(
                lambda: self.invoke(user_id),
                RetrieveUserMemoryOutput,
                "Unable to retrieve user memory right now.",
            )

        return StructuredTool.from_function(
            func=retrieve_user_memory,
            name=self.name,
            description=self.description,
            args_schema=RetrieveUserMemoryInput,
        )


class MemoryUpdateTool:
    """Controlled write tool: store only validated explicit preferences."""

    name = "update_user_memory"
    description = (
        "Store one validated long-term travel preference. Only use for explicit user "
        "statements or confirmed stable preferences. Never invent preferences and never "
        "store raw conversation text."
    )

    def __init__(self, service: Optional[MemoryService] = None) -> None:
        self.service = service or MemoryService()

    def invoke(
        self,
        *,
        user_id: UUID,
        field: MemoryField,
        value: Union[str, List[str]],
        evidence: MemoryEvidence = MemoryEvidence.EXPLICIT_USER_STATEMENT,
        source_excerpt: Optional[str] = None,
    ) -> UpdateUserMemoryOutput:
        request = MemoryUpdateRequest(
            user_id=user_id,
            field=field,
            value=value,
            evidence=evidence,
            source_excerpt=source_excerpt,
        )
        memory = self.service.update_memory(request)
        return UpdateUserMemoryOutput(
            success=True,
            memory=memory.model_dump(mode="json"),
            updated_field=field.value,
        )

    def as_langchain_tool(self) -> StructuredTool:
        def update_user_memory(
            user_id: UUID,
            field: MemoryField,
            value: Union[str, List[str]],
            evidence: MemoryEvidence = MemoryEvidence.EXPLICIT_USER_STATEMENT,
            source_excerpt: Optional[str] = None,
        ) -> dict:
            return run_safely(
                lambda: self.invoke(
                    user_id=user_id,
                    field=field,
                    value=value,
                    evidence=evidence,
                    source_excerpt=source_excerpt,
                ),
                UpdateUserMemoryOutput,
                "Unable to update user memory right now.",
            )

        return StructuredTool.from_function(
            func=update_user_memory,
            name=self.name,
            description=self.description,
            args_schema=UpdateUserMemoryInput,
        )
