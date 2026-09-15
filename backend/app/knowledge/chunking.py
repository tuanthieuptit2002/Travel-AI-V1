"""Split loaded documents into overlapping text chunks for embedding."""

from __future__ import annotations

from typing import List

from app.knowledge.models import KnowledgeChunk, LoadedDocument


def chunk_documents(
    documents: List[LoadedDocument],
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> List[KnowledgeChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    chunks: List[KnowledgeChunk] = []
    for document in documents:
        pieces = _split_text(document.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for index, piece in enumerate(pieces):
            chunks.append(
                KnowledgeChunk(
                    title=document.title,
                    content=piece,
                    source=document.source,
                    destination=document.destination,
                    category=document.category,
                    chunk_index=index,
                    metadata={**document.metadata, "chunk_index": index},
                )
            )
    return chunks


def _split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> List[str]:
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if len(normalized) <= chunk_size:
        return [normalized]

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    if not paragraphs:
        return _window_split(normalized, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= chunk_size:
            current = paragraph
        else:
            chunks.extend(_window_split(paragraph, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
            current = ""
    if current:
        chunks.append(current)

    if chunk_overlap <= 0 or len(chunks) <= 1:
        return chunks
    return _apply_overlap(chunks, chunk_overlap=chunk_overlap)


def _window_split(text: str, *, chunk_size: int, chunk_overlap: int) -> List[str]:
    step = max(chunk_size - chunk_overlap, 1)
    return [text[index : index + chunk_size].strip() for index in range(0, len(text), step) if text[index : index + chunk_size].strip()]


def _apply_overlap(chunks: List[str], *, chunk_overlap: int) -> List[str]:
    overlapped: List[str] = [chunks[0]]
    for index in range(1, len(chunks)):
        previous_tail = chunks[index - 1][-chunk_overlap:]
        overlapped.append(f"{previous_tail}\n{chunks[index]}".strip())
    return overlapped
