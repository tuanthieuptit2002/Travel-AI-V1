"""Deterministic cost estimates derived from catalog price levels.

These amounts are application-controlled defaults, not LLM inventions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.providers.models import PlaceCategory

# Per-person VND estimates keyed by normalized price_level.
_ATTRACTION_COSTS = {
    "low": Decimal("80000"),
    "medium": Decimal("180000"),
    "high": Decimal("350000"),
}
_RESTAURANT_COSTS = {
    "low": Decimal("90000"),
    "medium": Decimal("220000"),
    "high": Decimal("450000"),
}
_LANDMARK_COSTS = {
    "low": Decimal("0"),
    "medium": Decimal("50000"),
    "high": Decimal("150000"),
}


def estimate_place_cost(
    *,
    category: PlaceCategory | str,
    price_level: Optional[str],
    travelers: int,
) -> Decimal:
    level = (price_level or "low").casefold()
    category_value = category.value if isinstance(category, PlaceCategory) else str(category)
    if category_value == PlaceCategory.RESTAURANT.value:
        unit = _RESTAURANT_COSTS.get(level, _RESTAURANT_COSTS["medium"])
    elif category_value == PlaceCategory.LANDMARK.value:
        unit = _LANDMARK_COSTS.get(level, _LANDMARK_COSTS["low"])
    else:
        unit = _ATTRACTION_COSTS.get(level, _ATTRACTION_COSTS["medium"])
    return unit * Decimal(travelers)
