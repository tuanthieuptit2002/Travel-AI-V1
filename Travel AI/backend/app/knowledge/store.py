"""Knowledge vector stores: in-memory (tests) and PostgreSQL/pgvector (runtime)."""

from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeChunk, KnowledgeHit, KnowledgeSearchRequest
from app.models.travel import TravelKnowledgeDocument


class KnowledgeStore(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: Sequence[KnowledgeChunk]) -> int:
        ...

    @abstractmethod
    def search(self, request: KnowledgeSearchRequest, query_embedding: Sequence[float]) -> List[KnowledgeHit]:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...


class InMemoryKnowledgeStore(KnowledgeStore):
    """Cosine-similarity store used by unit tests and offline demos."""

    def __init__(self) -> None:
        self._chunks: List[KnowledgeChunk] = []
        self._ids: List[UUID] = []

    def upsert_chunks(self, chunks: Sequence[KnowledgeChunk]) -> int:
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError("Chunk embedding is required before storage.")
            self._chunks.append(chunk)
            self._ids.append(uuid.uuid4())
        return len(chunks)

    def search(self, request: KnowledgeSearchRequest, query_embedding: Sequence[float]) -> List[KnowledgeHit]:
        scored: List[tuple[float, UUID, KnowledgeChunk]] = []
        for chunk_id, chunk in zip(self._ids, self._chunks):
            if request.destination and (chunk.destination or "").casefold() != request.destination.casefold():
                # Allow destination-agnostic tips (None destination) through.
                if chunk.destination is not None:
                    continue
            if request.category and (chunk.category or "").casefold() != request.category.casefold():
                continue
            if not chunk.embedding:
                continue
            score = _cosine_similarity(query_embedding, chunk.embedding)
            scored.append((score, chunk_id, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits: List[KnowledgeHit] = []
        for score, chunk_id, chunk in scored[: request.top_k]:
            hits.append(
                KnowledgeHit(
                    id=chunk_id,
                    title=chunk.title,
                    content=chunk.content,
                    source=chunk.source,
                    destination=chunk.destination,
                    category=chunk.category,
                    score=round(score, 4),
                    citation=_citation_for(chunk),
                )
            )
        return hits

    def clear(self) -> None:
        self._chunks.clear()
        self._ids.clear()


class PostgresKnowledgeStore(KnowledgeStore):
    """pgvector-backed persistence for travel knowledge chunks."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_chunks(self, chunks: Sequence[KnowledgeChunk]) -> int:
        count = 0
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError("Chunk embedding is required before storage.")
            row = TravelKnowledgeDocument(
                title=chunk.title,
                content=chunk.content,
                source=chunk.source,
                destination=chunk.destination,
                category=chunk.category,
                chunk_index=chunk.chunk_index,
                metadata_=chunk.metadata,
                embedding=list(chunk.embedding),
            )
            self.session.add(row)
            count += 1
        self.session.flush()
        return count

    def search(self, request: KnowledgeSearchRequest, query_embedding: Sequence[float]) -> List[KnowledgeHit]:
        distance = TravelKnowledgeDocument.embedding.cosine_distance(list(query_embedding))
        stmt: Select = (
            select(TravelKnowledgeDocument, distance.label("distance"))
            .where(TravelKnowledgeDocument.embedding.is_not(None))
            .order_by(distance)
            .limit(request.top_k)
        )
        if request.destination:
            stmt = stmt.where(
                (TravelKnowledgeDocument.destination.is_(None))
                | (TravelKnowledgeDocument.destination.ilike(request.destination))
            )
        if request.category:
            stmt = stmt.where(TravelKnowledgeDocument.category.ilike(request.category))

        rows = self.session.execute(stmt).all()
        hits: List[KnowledgeHit] = []
        for document, dist in rows:
            score = 1.0 - float(dist or 0.0)
            chunk = KnowledgeChunk(
                title=document.title,
                content=document.content,
                source=document.source or "",
                destination=document.destination,
                category=document.category,
                chunk_index=document.chunk_index or 0,
            )
            hits.append(
                KnowledgeHit(
                    id=document.id,
                    title=document.title,
                    content=document.content,
                    source=document.source or "",
                    destination=document.destination,
                    category=document.category,
                    score=round(score, 4),
                    citation=_citation_for(chunk),
                )
            )
        return hits

    def clear(self) -> None:
        self.session.query(TravelKnowledgeDocument).delete()
        self.session.flush()


def _citation_for(chunk: KnowledgeChunk) -> str:
    parts = [chunk.title]
    if chunk.destination:
        parts.append(chunk.destination)
    if chunk.source:
        parts.append(chunk.source)
    return " — ".join(parts)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size])) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right[:size])) or 1.0
    return dot / (left_norm * right_norm)
