"""Pydantic models for the Vietnam travel knowledge RAG layer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoadedDocument(BaseModel):
    title: str
    content: str
    source: str
    destination: Optional[str] = None
    category: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    title: str
    content: str
    source: str
    destination: Optional[str] = None
    category: Optional[str] = None
    chunk_index: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None


class KnowledgeHit(BaseModel):
    id: Optional[UUID] = None
    title: str
    content: str
    source: str
    destination: Optional[str] = None
    category: Optional[str] = None
    score: float = 0.0
    citation: str = ""


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    destination: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)
