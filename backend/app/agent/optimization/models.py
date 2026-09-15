"""Structured budget and optimization result models."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agent.models import TripItinerary


class CostCategory(str, Enum):
    FLIGHTS = "flights"
    HOTELS = "hotels"
    FOOD = "food"
    ACTIVITIES = "activities"
    TRANSPORTATION = "transportation"


class CostLineItem(BaseModel):
    category: CostCategory
    name: str
    amount: Decimal = Field(ge=0)
    reference_id: Optional[str] = None
    quality_rating: Optional[float] = None


class BudgetBreakdown(BaseModel):
    flights: Decimal = Field(default=Decimal("0"), ge=0)
    hotels: Decimal = Field(default=Decimal("0"), ge=0)
    food: Decimal = Field(default=Decimal("0"), ge=0)
    activities: Decimal = Field(default=Decimal("0"), ge=0)
    transportation: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(default=Decimal("0"), ge=0)
    budget: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = "VND"
    within_budget: bool = True
    overage: Decimal = Field(default=Decimal("0"), ge=0)
    line_items: List[CostLineItem] = Field(default_factory=list)
    expensive_components: List[CostLineItem] = Field(default_factory=list)

    def as_notes(self) -> List[str]:
        notes = [
            (
                f"Phân bổ ngân sách — vé máy bay {self.flights}, khách sạn {self.hotels}, "
                f"ăn uống {self.food}, hoạt động {self.activities}, "
                f"di chuyển {self.transportation} {self.currency}."
            ),
            f"Tổng ước tính {self.total} so với ngân sách {self.budget} {self.currency}.",
        ]
        if not self.within_budget:
            notes.append(f"Vượt ngân sách {self.overage} {self.currency}.")
            for item in self.expensive_components[:3]:
                notes.append(
                    f"Hạng mục đắt: {item.name} ({item.category.value}) "
                    f"khoảng {item.amount} {self.currency}."
                )
        return notes


class OptimizationExplanation(BaseModel):
    text: str
    category: CostCategory
    replaced_id: Optional[str] = None
    selected_id: Optional[str] = None
    savings: Decimal = Field(default=Decimal("0"))


class OptimizationResult(BaseModel):
    itinerary: TripItinerary
    budget_breakdown: BudgetBreakdown
    explanations: List[OptimizationExplanation] = Field(default_factory=list)
    selected_hotel: Optional[dict] = None
    selected_flight: Optional[dict] = None
    regenerated: bool = False
