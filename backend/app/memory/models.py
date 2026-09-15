"""Structured long-term travel preference memory (not conversation logs, not RAG)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class MemoryEvidence(str, Enum):
    EXPLICIT_USER_STATEMENT = "explicit_user_statement"
    CONFIRMED_PREFERENCE = "confirmed_preference"


class MemoryField(str, Enum):
    PREFERRED_DESTINATIONS = "preferred_destinations"
    PREFERRED_ACTIVITIES = "preferred_activities"
    FOOD_PREFERENCES = "food_preferences"
    DISLIKED_ACTIVITIES = "disliked_activities"
    PREFERRED_TRIP_PACE = "preferred_trip_pace"
    BUDGET_PREFERENCE = "budget_preference"
    ACCOMMODATION_PREFERENCE = "accommodation_preference"
    TRANSPORTATION_PREFERENCE = "transportation_preference"


LIST_FIELDS = {
    MemoryField.PREFERRED_DESTINATIONS,
    MemoryField.PREFERRED_ACTIVITIES,
    MemoryField.FOOD_PREFERENCES,
    MemoryField.DISLIKED_ACTIVITIES,
}

SCALAR_FIELDS = {
    MemoryField.PREFERRED_TRIP_PACE,
    MemoryField.BUDGET_PREFERENCE,
    MemoryField.ACCOMMODATION_PREFERENCE,
    MemoryField.TRANSPORTATION_PREFERENCE,
}

ALLOWED_PACE = {"relaxed", "balanced", "packed"}
ALLOWED_BUDGET = {"low", "medium", "high", "flexible"}
ALLOWED_ACCOMMODATION = {"hotel", "hostel", "resort", "homestay", "apartment", "flexible"}
ALLOWED_TRANSPORT = {"flight", "train", "bus", "car", "motorbike", "walk", "flexible"}

_MAX_LIST_ITEMS = 20
_MAX_TOKEN_LEN = 60
_MAX_EXCERPT_LEN = 200


class UserMemory(BaseModel):
    user_id: UUID
    preferred_destinations: List[str] = Field(default_factory=list)
    preferred_activities: List[str] = Field(default_factory=list)
    food_preferences: List[str] = Field(default_factory=list)
    disliked_activities: List[str] = Field(default_factory=list)
    preferred_trip_pace: Optional[str] = None
    budget_preference: Optional[str] = None
    accommodation_preference: Optional[str] = None
    transportation_preference: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def as_planning_hints(self) -> List[str]:
        hints: List[str] = []
        hints.extend(self.preferred_activities)
        hints.extend(self.food_preferences)
        if self.preferred_trip_pace:
            hints.append(f"{self.preferred_trip_pace} pace")
        if self.budget_preference:
            hints.append(f"{self.budget_preference} budget")
        return hints


class MemoryUpdateRequest(BaseModel):
    """Validated preference write. Rejects free-form conversation dumps."""

    user_id: UUID
    field: MemoryField
    value: Union[str, List[str]]
    evidence: MemoryEvidence
    source_excerpt: Optional[str] = Field(default=None, max_length=_MAX_EXCERPT_LEN)

    @field_validator("source_excerpt")
    @classmethod
    def reject_long_conversation_dumps(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if len(cleaned) > _MAX_EXCERPT_LEN:
            raise ValueError("source_excerpt is too long; store preferences, not chat logs")
        if cleaned.count(".") > 4:
            raise ValueError("source_excerpt looks like conversation text, not a preference")
        return cleaned

    @model_validator(mode="after")
    def validate_value_shape(self) -> MemoryUpdateRequest:
        if self.field in LIST_FIELDS:
            values = self.value if isinstance(self.value, list) else [self.value]
            normalized = [_normalize_token(item) for item in values]
            normalized = [item for item in normalized if item]
            if not normalized:
                raise ValueError("list preference value is empty")
            if len(normalized) > _MAX_LIST_ITEMS:
                raise ValueError("too many preference values")
            self.value = normalized
            return self

        if not isinstance(self.value, str):
            raise ValueError("scalar preference value must be a string")
        token = _normalize_token(self.value)
        if not token:
            raise ValueError("scalar preference value is empty")
        if self.field is MemoryField.PREFERRED_TRIP_PACE and token not in ALLOWED_PACE:
            raise ValueError(f"preferred_trip_pace must be one of {sorted(ALLOWED_PACE)}")
        if self.field is MemoryField.BUDGET_PREFERENCE and token not in ALLOWED_BUDGET:
            raise ValueError(f"budget_preference must be one of {sorted(ALLOWED_BUDGET)}")
        if self.field is MemoryField.ACCOMMODATION_PREFERENCE and token not in ALLOWED_ACCOMMODATION:
            raise ValueError(
                f"accommodation_preference must be one of {sorted(ALLOWED_ACCOMMODATION)}"
            )
        if self.field is MemoryField.TRANSPORTATION_PREFERENCE and token not in ALLOWED_TRANSPORT:
            raise ValueError(
                f"transportation_preference must be one of {sorted(ALLOWED_TRANSPORT)}"
            )
        self.value = token
        return self


def _normalize_token(value: str) -> str:
    cleaned = " ".join(str(value).casefold().split())
    if len(cleaned) > _MAX_TOKEN_LEN:
        raise ValueError("preference token exceeds maximum length")
    if "\n" in str(value):
        raise ValueError("preference tokens cannot contain newlines")
    return cleaned


def empty_memory(user_id: UUID) -> UserMemory:
    return UserMemory(user_id=user_id)


def memory_to_dict(memory: UserMemory) -> Dict[str, Any]:
    return memory.model_dump(mode="json")
