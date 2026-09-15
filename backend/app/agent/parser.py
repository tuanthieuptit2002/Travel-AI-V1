"""Deterministic natural-language travel request parser.

Supports English and Vietnamese demo patterns so offline tests stay stable.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Protocol

from app.agent.models import ParsedTravelRequest
from app.providers.mock.catalog import (
    DESTINATION_ALIASES,
    VIETNAM_DESTINATIONS,
    normalize_destination,
)


class RequestParser(Protocol):
    def parse(self, user_request: str, *, reference_date: date) -> ParsedTravelRequest:
        ...


_PREFERENCE_MAP = {
    "biển": "beaches",
    "bãi biển": "beaches",
    "beaches": "beaches",
    "ẩm thực địa phương": "local food",
    "món địa phương": "local food",
    "local food": "local food",
    "chụp ảnh": "photography",
    "nhiếp ảnh": "photography",
    "photography": "photography",
    "hải sản": "seafood",
    "seafood": "seafood",
    "cafe": "cafe",
    "cà phê": "cafe",
}


class DeterministicRequestParser:
    """Rule-based parser covering Vietnam demo request patterns (EN + VI)."""

    def parse(self, user_request: str, *, reference_date: date) -> ParsedTravelRequest:
        text = " ".join(user_request.strip().split())
        lowered = text.casefold()

        destination = self._extract_destination(lowered)
        if destination is None:
            raise ValueError("Không xác định được điểm đến được hỗ trợ từ yêu cầu.")

        travelers = self._extract_travelers(lowered)
        days, nights = self._extract_duration(lowered)
        budget_per_person, budget_total = self._extract_budget(lowered, travelers)
        preferences = self._extract_preferences(text)
        origin = self._extract_origin(lowered, destination)

        start_date = reference_date
        end_date = start_date + timedelta(days=max(days - 1, 0))

        return ParsedTravelRequest(
            destination=destination,
            origin=origin,
            start_date=start_date,
            end_date=end_date,
            travelers=travelers,
            budget_total=budget_total,
            budget_per_person=budget_per_person,
            currency="VND",
            preferences=preferences,
            nights=nights,
            days=days,
        )

    def _extract_destination(self, lowered: str) -> Optional[str]:
        # Prefer explicit "to / đến / visit" targets before a raw city scan so
        # "from Ho Chi Minh City to Phu Quoc" resolves to Phu Quoc.
        directed = self._extract_directed_destination(lowered)
        if directed:
            return directed

        candidates = sorted(
            ((key, value[0]) for key, value in VIETNAM_DESTINATIONS.items()),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for key, display_name in candidates:
            if key in lowered or display_name.casefold() in lowered:
                return display_name
        for alias, key in sorted(DESTINATION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if alias in lowered:
                return VIETNAM_DESTINATIONS[key][0]
        # Accent-insensitive fallback.
        folded = _strip_accents(lowered)
        for alias, key in {
            "da nang": "da nang",
            "ha noi": "hanoi",
            "hoi an": "hoi an",
            "ho chi minh": "ho chi minh city",
            "sai gon": "ho chi minh city",
            "da lat": "da lat",
            "nha trang": "nha trang",
            "phu quoc": "phu quoc",
            "ha long": "ha long",
        }.items():
            if alias in folded:
                return VIETNAM_DESTINATIONS[key][0]
        return None

    def _extract_directed_destination(self, lowered: str) -> Optional[str]:
        patterns = [
            r"(?:from|từ)\s+.+?\s+(?:to|đến)\s+([a-zàáạảãăằắặẳẵâầấậẩẫèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]+?)(?:\s+for\s+|\s+cho\s+|[.,]|$)",
            r"(?:travel to|visit|go to|đi\s+đến|đi)\s+([a-zàáạảãăằắặẳẵâầấậẩẫèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]+?)(?:\s+for\s+|\s+cho\s+|[.,]|$)",
            r"(?:muốn\s+đi|muốn\s+đến)\s+([a-zàáạảãăằắặẳẵâầấậẩẫèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]+?)(?:\s+trong|\s+cho|[.,]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            resolved = self._resolve_place_name(match.group(1))
            if resolved:
                return resolved
        return None

    def _resolve_place_name(self, raw: str) -> Optional[str]:
        candidate = " ".join(raw.strip().casefold().split())
        # Truncate trailing preference/budget noise if captured.
        for stop in (" for ", " cho ", " with ", " budget", " ngân "):
            if stop in candidate:
                candidate = candidate.split(stop, 1)[0].strip()
        if candidate in VIETNAM_DESTINATIONS:
            return VIETNAM_DESTINATIONS[candidate][0]
        mapped = DESTINATION_ALIASES.get(candidate) or DESTINATION_ALIASES.get(
            _strip_accents(candidate)
        )
        if mapped and mapped in VIETNAM_DESTINATIONS:
            return VIETNAM_DESTINATIONS[mapped][0]
        folded = _strip_accents(candidate)
        for key, value in VIETNAM_DESTINATIONS.items():
            if key == folded or value[0].casefold() == candidate:
                return value[0]
        return None

    def _extract_origin(self, lowered: str, destination: str) -> Optional[str]:
        patterns = [
            r"from\s+([a-zàáạảãăằắặẳẵâầấậẩẫèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]+?)\s+to\s+",
            r"từ\s+([a-zàáạảãăằắặẳẵâầấậẩẫèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]+?)\s+đến\s+",
            r"đi từ\s+([a-zàáạảãăằắặẳẵâầấậẩẫèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]+?)\s+đến\s+",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            name = self._resolve_place_name(match.group(1))
            if name and name != destination:
                return name
        return None

    def _extract_travelers(self, lowered: str) -> int:
        patterns = [
            r"for\s+(\d+)\s+people",
            r"for\s+(\d+)\s+persons",
            r"(\d+)\s+travelers",
            r"(\d+)\s+adults",
            r"cho\s+(\d+)\s+người",
            r"(\d+)\s+người",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                return max(1, int(match.group(1)))
        if "solo" in lowered or "just me" in lowered or "một mình" in lowered:
            return 1
        if "couple" in lowered or "cặp đôi" in lowered:
            return 2
        return 2

    def _extract_duration(self, lowered: str) -> tuple[int, int]:
        days_match = re.search(r"(\d+)\s+(?:days?|ngày)", lowered)
        nights_match = re.search(r"(\d+)\s+(?:nights?|đêm)", lowered)
        days = int(days_match.group(1)) if days_match else None
        nights = int(nights_match.group(1)) if nights_match else None
        if days is None and nights is not None:
            days = nights + 1
        if nights is None and days is not None:
            nights = max(days - 1, 0)
        if days is None:
            days = 3
            nights = 2
        return days, nights if nights is not None else max(days - 1, 0)

    def _extract_budget(self, lowered: str, travelers: int) -> tuple[Optional[Decimal], Decimal]:
        million_match = re.search(
            r"(?:budget|ngân sách)\s+(\d+(?:\.\d+)?)\s*(?:million|trieu|triệu)?\s*(?:vnd)?"
            r"(?:\s+(?:per\s+person|mỗi\s+người|\/\s*người))?",
            lowered,
        )
        if million_match:
            amount = Decimal(million_match.group(1))
            per_person = amount * Decimal("1000000") if amount < Decimal("1000") else amount
            if (
                re.search(r"\bper\s+person\b", lowered)
                or re.search(r"\beach\b", lowered)
                or "mỗi người" in lowered
                or "/người" in lowered
            ):
                return per_person, per_person * Decimal(travelers)
            return None, per_person

        raw_match = re.search(r"(?:budget|ngân sách)\s+(\d[\d,\.]*)\s*vnd", lowered)
        if raw_match:
            total = Decimal(raw_match.group(1).replace(",", ""))
            return None, total

        return None, Decimal("10000000")

    def _extract_preferences(self, text: str) -> List[str]:
        like_match = re.search(
            r"(?:i like|we like|prefer|interested in|tôi thích|chúng tôi thích|ưa thích)\s+(.+?)(?:\.|$)",
            text,
            flags=re.IGNORECASE,
        )
        if not like_match:
            return []
        chunk = like_match.group(1)
        parts = re.split(r",| and | & | và ", chunk)
        prefs: List[str] = []
        for part in parts:
            cleaned = part.strip().casefold()
            if not cleaned:
                continue
            prefs.append(_PREFERENCE_MAP.get(cleaned, cleaned))
        return prefs


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn").replace("đ", "d")
