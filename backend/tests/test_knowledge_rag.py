from __future__ import annotations

from pathlib import Path

from app.knowledge.chunking import chunk_documents
from app.knowledge.embeddings import HashEmbeddingProvider
from app.knowledge.loader import load_knowledge_documents
from app.knowledge.models import LoadedDocument
from app.knowledge.service import KnowledgeService
from app.knowledge.store import InMemoryKnowledgeStore
from app.tools import ToolDependencies, create_agent_tools


REPO_KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"


def test_loader_reads_vietnam_tree_with_metadata() -> None:
    documents = load_knowledge_documents(REPO_KNOWLEDGE)
    assert documents
    danang = [doc for doc in documents if doc.destination == "Da Nang"]
    assert danang
    assert any(doc.category == "food" for doc in documents)
    assert any(doc.category == "transportation" for doc in documents)


def test_chunking_produces_overlapping_chunks() -> None:
    documents = [
        LoadedDocument(
            title="Long Guide",
            content=("Paragraph one about beaches.\n\n" * 20) + ("Paragraph two about food.\n\n" * 20),
            source="vietnam/danang/guide.md",
            destination="Da Nang",
            category="destination_guide",
        )
    ]
    chunks = chunk_documents(documents, chunk_size=120, chunk_overlap=30)
    assert len(chunks) > 1
    assert chunks[0].chunk_index == 0
    assert chunks[1].title == "Long Guide"


def test_ingestion_and_embedding_storage() -> None:
    store = InMemoryKnowledgeStore()
    service = KnowledgeService(
        store=store,
        embeddings=HashEmbeddingProvider(dimensions=64),
        knowledge_root=REPO_KNOWLEDGE,
    )
    count = service.ingest_directory()
    assert count > 0
    assert len(store._chunks) == count
    assert all(chunk.embedding for chunk in store._chunks)


def test_retrieval_returns_relevant_destination_knowledge() -> None:
    service = KnowledgeService(
        store=InMemoryKnowledgeStore(),
        embeddings=HashEmbeddingProvider(dimensions=64),
        knowledge_root=REPO_KNOWLEDGE,
    )
    service.ingest_directory()
    # Use distinctive phrasing present in the Da Nang guide for hash embeddings.
    hits = service.search(
        "My Khe Beach Marble Mountains Dragon Bridge photography",
        destination="Da Nang",
        top_k=5,
    )
    assert hits
    assert any("Da Nang" in (hit.destination or "") or "danang" in hit.source for hit in hits)
    assert hits[0].citation


def test_metadata_filtering_by_destination() -> None:
    service = KnowledgeService(
        store=InMemoryKnowledgeStore(),
        embeddings=HashEmbeddingProvider(dimensions=64),
    )
    service.ingest_chunks(
        chunk_documents(
            [
                LoadedDocument(
                    title="Da Nang Beach Note",
                    content="My Khe Beach is excellent for sunrise swimming and photography.",
                    source="vietnam/danang/guide.md",
                    destination="Da Nang",
                    category="destination_guide",
                ),
                LoadedDocument(
                    title="Hanoi Lake Note",
                    content="Hoan Kiem Lake is a calm walking loop in the historic center.",
                    source="vietnam/hanoi/guide.md",
                    destination="Hanoi",
                    category="destination_guide",
                ),
            ]
        )
    )
    hits = service.search("sunrise swimming beach", destination="Da Nang", top_k=5)
    assert hits
    assert all(hit.destination in {None, "Da Nang"} for hit in hits)
    assert any(hit.destination == "Da Nang" for hit in hits)


def test_search_travel_knowledge_tool() -> None:
    knowledge = KnowledgeService(
        store=InMemoryKnowledgeStore(),
        embeddings=HashEmbeddingProvider(dimensions=64),
        knowledge_root=REPO_KNOWLEDGE,
    )
    knowledge.ingest_directory()
    dependencies = ToolDependencies.with_mocks()
    dependencies.knowledge = knowledge
    tools = {tool.name: tool for tool in create_agent_tools(dependencies)}
    result = tools["search_travel_knowledge"].invoke(
        {
            "query": "temple dress code safety customs seasonal rain",
            "destination": None,
            "top_k": 3,
        }
    )
    assert result["success"] is True
    assert result["results"]
    assert "citation" in result["results"][0]
