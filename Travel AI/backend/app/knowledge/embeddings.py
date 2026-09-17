"""Embedding providers for travel knowledge chunks."""

from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        ...

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        ...


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embeddings for tests and offline development."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: List[float] = []
        seed = digest
        while len(values) < self.dimensions:
            seed = hashlib.sha256(seed).digest()
            for index in range(0, len(seed), 4):
                chunk = seed[index : index + 4]
                if len(chunk) < 4:
                    break
                number = int.from_bytes(chunk, "big") / 0xFFFFFFFF
                values.append((number * 2.0) - 1.0)
                if len(values) >= self.dimensions:
                    break
        return _l2_normalize(values[: self.dimensions])


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings via the official SDK with timeout + cost tracking."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIEmbeddingProvider.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install the openai package to use OpenAI embeddings.") from exc
        self._client = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        from app.core.config import get_settings
        from app.observability.context import (
            CostEvent,
            estimate_embedding_cost,
            get_cost_tracker,
        )
        from app.observability.tracing import trace_llm

        response = self._client.embeddings.create(
            model=self.model,
            input=list(texts),
            dimensions=self.dimensions,
            timeout=self.timeout_seconds,
        )
        usage_tokens = int(getattr(getattr(response, "usage", None), "total_tokens", 0) or 0)
        settings = get_settings()
        cost = estimate_embedding_cost(
            tokens=usage_tokens or max(1, sum(len(t.split()) for t in texts)),
            per_1k=settings.cost_openai_embedding_per_1k,
        )
        tracker = get_cost_tracker()
        if tracker:
            tracker.add(
                CostEvent(
                    component="embedding",
                    model_or_provider=self.model,
                    input_tokens=usage_tokens,
                    estimated_usd=cost,
                )
            )
        trace_llm(self.model, input_tokens=usage_tokens, output_tokens=0)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


def build_embedding_provider(
    *,
    api_key: str = "",
    model: str = "text-embedding-3-small",
    dimensions: int = 1536,
    force_hash: bool = False,
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
) -> EmbeddingProvider:
    if force_hash or not api_key:
        logger.info("Using HashEmbeddingProvider for knowledge embeddings")
        return HashEmbeddingProvider(dimensions=dimensions)
    try:
        logger.info("Using OpenAIEmbeddingProvider model=%s", model)
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    except Exception as exc:  # noqa: BLE001 - keep API bootable without openai package
        logger.warning(
            "OpenAI embeddings unavailable (%s); falling back to HashEmbeddingProvider",
            type(exc).__name__,
        )
        return HashEmbeddingProvider(dimensions=dimensions)


def _l2_normalize(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
