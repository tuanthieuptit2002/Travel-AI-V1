"""Knowledge ingestion and retrieval service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence

from app.knowledge.chunking import chunk_documents
from app.knowledge.embeddings import EmbeddingProvider, HashEmbeddingProvider
from app.knowledge.loader import load_knowledge_documents
from app.knowledge.models import KnowledgeChunk, KnowledgeHit, KnowledgeSearchRequest
from app.knowledge.store import InMemoryKnowledgeStore, KnowledgeStore

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        *,
        store: Optional[KnowledgeStore] = None,
        embeddings: Optional[EmbeddingProvider] = None,
        knowledge_root: Optional[Path | str] = None,
    ) -> None:
        self.store = store or InMemoryKnowledgeStore()
        self.embeddings = embeddings or HashEmbeddingProvider()
        self.knowledge_root = Path(knowledge_root) if knowledge_root else None

    def ingest_directory(self, root: Optional[Path | str] = None) -> int:
        path = Path(root or self.knowledge_root or "knowledge")
        documents = load_knowledge_documents(path)
        chunks = chunk_documents(documents)
        return self.ingest_chunks(chunks)

    def ingest_chunks(self, chunks: Sequence[KnowledgeChunk]) -> int:
        if not chunks:
            return 0
        vectors = self.embeddings.embed_documents([chunk.content for chunk in chunks])
        embedded: List[KnowledgeChunk] = []
        for chunk, vector in zip(chunks, vectors):
            embedded.append(chunk.model_copy(update={"embedding": vector}))
        count = self.store.upsert_chunks(embedded)
        logger.info("Ingested %s knowledge chunks", count)
        return count

    def search(
        self,
        query: str,
        *,
        destination: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 5,
    ) -> List[KnowledgeHit]:
        request = KnowledgeSearchRequest(
            query=query,
            destination=destination,
            category=category,
            top_k=top_k,
        )
        query_embedding = self.embeddings.embed_query(query)
        hits = self.store.search(request, query_embedding)
        logger.info(
            "Knowledge search query_len=%s destination=%s hits=%s",
            len(query),
            destination,
            len(hits),
        )
        return hits
