"""Controlled travel-preference memory service.

Stores only structured, validated preferences — never raw conversation transcripts.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from app.memory.models import (
    LIST_FIELDS,
    MemoryEvidence,
    MemoryField,
    MemoryUpdateRequest,
    UserMemory,
    empty_memory,
)
from app.memory.store import InMemoryMemoryStore, MemoryStore, get_memory_store

logger = logging.getLogger(__name__)

_LIKE_RE = re.compile(
    r"(?:i like|we like|i prefer|we prefer|i love|tôi thích|chúng tôi thích|tôi ưa|tôi yêu)\s+(.+?)(?:\.|$)",
    flags=re.IGNORECASE,
)
_DISLIKE_RE = re.compile(
    r"(?:i (?:do not|don't) like|we (?:do not|don't) like|i hate|avoid|tôi không thích|không thích|ghét)\s+(.+?)(?:\.|$)",
    flags=re.IGNORECASE,
)
_PACE_RE = re.compile(
    r"(?:nhịp độ\s+)?(relaxed|balanced|packed|thư thả|cân bằng|dày đặc)"
    r"(?:\s+(?:travel\s+)?(?:pace|trip)|)?",
    flags=re.IGNORECASE,
)
_BUDGET_RE = re.compile(
    r"(?:budget|prefer|ngân sách|ưa thích)\s+(low|medium|high|flexible|thấp|trung bình|cao|linh hoạt)"
    r"(?:\s+budget)?",
    flags=re.IGNORECASE,
)
_ACCOMMODATION_RE = re.compile(
    r"(?:prefer|stay in|staying in|ưu tiên|ở|nghỉ tại)\s+(hotel|hostel|resort|homestay|apartment|khách sạn)",
    flags=re.IGNORECASE,
)
_TRANSPORT_RE = re.compile(
    r"(?:prefer|travel by|traveling by|đi bằng|ưu tiên)\s+(flight|train|bus|car|motorbike|walk|máy bay|tàu|xe bus|ô tô|xe máy|đi bộ)",
    flags=re.IGNORECASE,
)

_PACE_MAP = {
    "thư thả": "relaxed",
    "cân bằng": "balanced",
    "dày đặc": "packed",
}
_BUDGET_MAP = {
    "thấp": "low",
    "trung bình": "medium",
    "cao": "high",
    "linh hoạt": "flexible",
}
_ACCOMMODATION_MAP = {"khách sạn": "hotel"}
_TRANSPORT_MAP = {
    "máy bay": "flight",
    "tàu": "train",
    "xe bus": "bus",
    "ô tô": "car",
    "xe máy": "motorbike",
    "đi bộ": "walk",
}
_ACTIVITY_MAP = {
    "biển": "beaches",
    "bãi biển": "beaches",
    "ẩm thực địa phương": "local food",
    "món địa phương": "local food",
    "chụp ảnh": "photography",
    "nhiếp ảnh": "photography",
    "hải sản": "seafood",
    "cuộc sống về đêm": "nightlife",
    "nightlife": "nightlife",
}


class MemoryService:
    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self.store = store or get_memory_store()

    def get_memory(self, user_id: UUID) -> UserMemory:
        return self.store.get(user_id)

    def update_memory(self, request: MemoryUpdateRequest) -> UserMemory:
        """Apply one validated preference update. Rejects invented or chat-dump values."""
        memory = self.store.get(request.user_id)
        field = request.field
        if field in LIST_FIELDS:
            current = list(getattr(memory, field.value))
            incoming = request.value if isinstance(request.value, list) else [request.value]
            merged = list(dict.fromkeys([*current, *incoming]))
            setattr(memory, field.value, merged)
        else:
            setattr(memory, field.value, request.value)
        memory.updated_at = datetime.now(timezone.utc)
        saved = self.store.save(memory)
        logger.info(
            "Updated user memory user_id=%s field=%s evidence=%s",
            request.user_id,
            field.value,
            request.evidence.value,
        )
        return saved

    def replace_memory(self, memory: UserMemory) -> UserMemory:
        memory.updated_at = datetime.now(timezone.utc)
        return self.store.save(memory)

    def clear_memory(self, user_id: UUID) -> bool:
        deleted = self.store.delete(user_id)
        logger.info("Cleared user memory user_id=%s deleted=%s", user_id, deleted)
        return deleted

    def clear_field(self, user_id: UUID, field: MemoryField) -> UserMemory:
        memory = self.store.get(user_id)
        if field in LIST_FIELDS:
            setattr(memory, field.value, [])
        else:
            setattr(memory, field.value, None)
        memory.updated_at = datetime.now(timezone.utc)
        return self.store.save(memory)

    def extract_explicit_updates(
        self, *, user_id: UUID, user_request: str
    ) -> List[MemoryUpdateRequest]:
        """Extract only explicit preference statements from a user request.

        Never invents memories from agent itineraries or inferred vibes.
        """
        text = " ".join(user_request.split())
        updates: List[MemoryUpdateRequest] = []

        like_match = _LIKE_RE.search(text)
        if like_match:
            tokens = _normalize_activity_tokens(_split_preference_list(like_match.group(1)))
            if tokens:
                updates.append(
                    MemoryUpdateRequest(
                        user_id=user_id,
                        field=MemoryField.PREFERRED_ACTIVITIES,
                        value=tokens,
                        evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                        source_excerpt=like_match.group(0)[:200],
                    )
                )
                foodish = [
                    token
                    for token in tokens
                    if "food" in token or "seafood" in token or "ẩm thực" in token
                ]
                if foodish:
                    updates.append(
                        MemoryUpdateRequest(
                            user_id=user_id,
                            field=MemoryField.FOOD_PREFERENCES,
                            value=foodish,
                            evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                            source_excerpt=like_match.group(0)[:200],
                        )
                    )

        dislike_match = _DISLIKE_RE.search(text)
        if dislike_match:
            tokens = _normalize_activity_tokens(_split_preference_list(dislike_match.group(1)))
            if tokens:
                updates.append(
                    MemoryUpdateRequest(
                        user_id=user_id,
                        field=MemoryField.DISLIKED_ACTIVITIES,
                        value=tokens,
                        evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                        source_excerpt=dislike_match.group(0)[:200],
                    )
                )

        pace_match = _PACE_RE.search(text)
        if pace_match:
            pace = _PACE_MAP.get(pace_match.group(1).casefold(), pace_match.group(1).casefold())
            if pace in {"relaxed", "balanced", "packed"}:
                updates.append(
                    MemoryUpdateRequest(
                        user_id=user_id,
                        field=MemoryField.PREFERRED_TRIP_PACE,
                        value=pace,
                        evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                        source_excerpt=pace_match.group(0)[:200],
                    )
                )

        budget_match = _BUDGET_RE.search(text)
        if budget_match:
            budget = _BUDGET_MAP.get(
                budget_match.group(1).casefold(), budget_match.group(1).casefold()
            )
            if budget in {"low", "medium", "high", "flexible"}:
                updates.append(
                    MemoryUpdateRequest(
                        user_id=user_id,
                        field=MemoryField.BUDGET_PREFERENCE,
                        value=budget,
                        evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                        source_excerpt=budget_match.group(0)[:200],
                    )
                )

        accommodation_match = _ACCOMMODATION_RE.search(text)
        if accommodation_match:
            lodging = _ACCOMMODATION_MAP.get(
                accommodation_match.group(1).casefold(),
                accommodation_match.group(1).casefold(),
            )
            updates.append(
                MemoryUpdateRequest(
                    user_id=user_id,
                    field=MemoryField.ACCOMMODATION_PREFERENCE,
                    value=lodging,
                    evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                    source_excerpt=accommodation_match.group(0)[:200],
                )
            )

        transport_match = _TRANSPORT_RE.search(text)
        if transport_match:
            transport = _TRANSPORT_MAP.get(
                transport_match.group(1).casefold(),
                transport_match.group(1).casefold(),
            )
            updates.append(
                MemoryUpdateRequest(
                    user_id=user_id,
                    field=MemoryField.TRANSPORTATION_PREFERENCE,
                    value=transport,
                    evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                    source_excerpt=transport_match.group(0)[:200],
                )
            )

        destination_match = re.search(
            r"(?:favorite|preferred)\s+destination(?:s)?\s+(?:is|are|:)?\s+(.+?)(?:\.|$)",
            text,
            flags=re.IGNORECASE,
        )
        if destination_match:
            tokens = _split_preference_list(destination_match.group(1))
            if tokens:
                updates.append(
                    MemoryUpdateRequest(
                        user_id=user_id,
                        field=MemoryField.PREFERRED_DESTINATIONS,
                        value=tokens,
                        evidence=MemoryEvidence.EXPLICIT_USER_STATEMENT,
                        source_excerpt=destination_match.group(0)[:200],
                    )
                )

        return updates

    def apply_explicit_extractions(self, *, user_id: UUID, user_request: str) -> UserMemory:
        updates = self.extract_explicit_updates(user_id=user_id, user_request=user_request)
        memory = self.get_memory(user_id)
        for update in updates:
            memory = self.update_memory(update)
        return memory


def _split_preference_list(chunk: str) -> List[str]:
    parts = re.split(r",| and | & | và ", chunk)
    return [part.strip(" .") for part in parts if part.strip(" .")]


def _normalize_activity_tokens(tokens: List[str]) -> List[str]:
    normalized: List[str] = []
    for token in tokens:
        key = token.casefold().strip()
        normalized.append(_ACTIVITY_MAP.get(key, key))
    return normalized
