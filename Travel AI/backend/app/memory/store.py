"""In-memory preference store for the pre-auth phase (separate from RAG)."""

from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Dict, Optional, Protocol
from uuid import UUID

from app.memory.models import UserMemory, empty_memory


class MemoryStore(Protocol):
    def get(self, user_id: UUID) -> UserMemory:
        ...

    def save(self, memory: UserMemory) -> UserMemory:
        ...

    def delete(self, user_id: UUID) -> bool:
        ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: Dict[UUID, UserMemory] = {}
        self._lock = Lock()

    def get(self, user_id: UUID) -> UserMemory:
        with self._lock:
            memory = self._items.get(user_id)
            return deepcopy(memory) if memory else empty_memory(user_id)

    def save(self, memory: UserMemory) -> UserMemory:
        with self._lock:
            stored = deepcopy(memory)
            self._items[memory.user_id] = stored
            return deepcopy(stored)

    def delete(self, user_id: UUID) -> bool:
        with self._lock:
            return self._items.pop(user_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_store = InMemoryMemoryStore()


def get_memory_store() -> InMemoryMemoryStore:
    return _store
