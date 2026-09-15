"""Ingest Vietnam travel knowledge into the configured knowledge store.

Usage from backend/:
    PYTHONPATH=. python scripts/ingest_knowledge.py
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.knowledge.embeddings import build_embedding_provider
from app.knowledge.service import KnowledgeService
from app.knowledge.store import InMemoryKnowledgeStore


def main() -> None:
    settings = get_settings()
    root = Path(settings.knowledge_root)
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()

    service = KnowledgeService(
        store=InMemoryKnowledgeStore(),
        embeddings=build_embedding_provider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
            force_hash=not bool(settings.openai_api_key),
        ),
        knowledge_root=root,
    )
    count = service.ingest_directory(root)
    sample = service.search("Da Nang beach food customs", destination="Da Nang", top_k=3)
    print(f"Ingested {count} chunks from {root}")
    print("Sample retrieval:")
    for hit in sample:
        print(f"- {hit.citation} (score={hit.score})")


if __name__ == "__main__":
    main()
