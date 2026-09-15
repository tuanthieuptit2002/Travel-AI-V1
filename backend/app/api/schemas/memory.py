"""Public schemas for structured user travel memory."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.memory.models import MemoryEvidence, MemoryField


class UserMemoryOut(BaseModel):
    user_id: UUID
    preferred_destinations: List[str] = Field(default_factory=list)
    preferred_activities: List[str] = Field(default_factory=list)
    food_preferences: List[str] = Field(default_factory=list)
    disliked_activities: List[str] = Field(default_factory=list)
    preferred_trip_pace: Optional[str] = None
    budget_preference: Optional[str] = None
    accommodation_preference: Optional[str] = None
    transportation_preference: Optional[str] = None
    updated_at: datetime


class MemoryUpdateBody(BaseModel):
    field: MemoryField
    value: Union[str, List[str]]
    evidence: MemoryEvidence = MemoryEvidence.EXPLICIT_USER_STATEMENT
    source_excerpt: Optional[str] = Field(default=None, max_length=200)


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
