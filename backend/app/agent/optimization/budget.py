"""BudgetAgent — break down trip costs and flag expensive components."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from app.agent.models import ActivityKind, TripItinerary
from app.agent.optimization.models import BudgetBreakdown, CostCategory, CostLineItem

# Deterministic transport estimate: VND per minute of city transfer.
TRANSPORT_VND_PER_MINUTE = Decimal("2500")


class BudgetAgent:
    """Analyze flights, hotels, food, activities, and transportation against budget."""

    def analyze(
        self,
        itinerary: TripItinerary,
        *,
        hotel: Optional[Dict] = None,
        flight: Optional[Dict] = None,
        nights: Optional[int] = None,
    ) -> BudgetBreakdown:
        food_items: List[CostLineItem] = []
        activity_items: List[CostLineItem] = []
        transport_minutes = 0

        for day in itinerary.days:
            for activity in day.activities:
                transport_minutes += int(activity.travel_time_from_previous or 0)
                item = CostLineItem(
                    category=(
                        CostCategory.FOOD
                        if activity.kind == ActivityKind.RESTAURANT
                        else CostCategory.ACTIVITIES
                    ),
                    name=activity.name,
                    amount=Decimal(activity.estimated_cost),
                    reference_id=activity.place_id,
                    quality_rating=activity.rating,
                )
                if activity.kind == ActivityKind.RESTAURANT:
                    food_items.append(item)
                else:
                    activity_items.append(item)

        food = sum((item.amount for item in food_items), Decimal("0"))
        activities = sum((item.amount for item in activity_items), Decimal("0"))
        transportation = Decimal(transport_minutes) * TRANSPORT_VND_PER_MINUTE

        hotel_nights = nights
        if hotel_nights is None:
            hotel_nights = max(0, (itinerary.end_date - itinerary.start_date).days)
        hotels = Decimal("0")
        hotel_item: Optional[CostLineItem] = None
        if hotel and hotel_nights > 0:
            nightly = Decimal(str(hotel.get("nightly_price") or 0))
            hotels = nightly * Decimal(hotel_nights)
            hotel_item = CostLineItem(
                category=CostCategory.HOTELS,
                name=str(hotel.get("name") or "Hotel"),
                amount=hotels,
                reference_id=str(hotel.get("id")) if hotel.get("id") else None,
                quality_rating=float(hotel["rating"]) if hotel.get("rating") is not None else None,
            )

        flights = Decimal("0")
        flight_item: Optional[CostLineItem] = None
        if flight:
            unit = Decimal(str(flight.get("price") or 0))
            # One-way per traveler; round-trip assumed when return is not provided.
            flights = unit * Decimal(itinerary.travelers) * Decimal("2")
            flight_item = CostLineItem(
                category=CostCategory.FLIGHTS,
                name=f"{flight.get('airline', 'Flight')} {flight.get('flight_number', '')}".strip(),
                amount=flights,
                reference_id=str(flight.get("id")) if flight.get("id") else None,
            )

        transport_item = CostLineItem(
            category=CostCategory.TRANSPORTATION,
            name="Di chuyển nội thành",
            amount=transportation,
        )

        line_items: List[CostLineItem] = []
        if flight_item:
            line_items.append(flight_item)
        if hotel_item:
            line_items.append(hotel_item)
        line_items.extend(food_items)
        line_items.extend(activity_items)
        line_items.append(transport_item)

        total = flights + hotels + food + activities + transportation
        budget = Decimal(itinerary.total_budget)
        overage = max(Decimal("0"), total - budget)
        expensive = self.identify_expensive_components(line_items, overage=overage)

        return BudgetBreakdown(
            flights=flights,
            hotels=hotels,
            food=food,
            activities=activities,
            transportation=transportation,
            total=total,
            budget=budget,
            currency=itinerary.currency,
            within_budget=total <= budget,
            overage=overage,
            line_items=line_items,
            expensive_components=expensive,
        )

    def identify_expensive_components(
        self,
        line_items: Sequence[CostLineItem],
        *,
        overage: Decimal,
        limit: int = 5,
    ) -> List[CostLineItem]:
        """Rank costly components that are good swap candidates when over budget."""
        ranked = sorted(line_items, key=lambda item: item.amount, reverse=True)
        if overage <= 0:
            return list(ranked[: min(2, len(ranked))])
        selected: List[CostLineItem] = []
        covered = Decimal("0")
        for item in ranked:
            if item.category is CostCategory.TRANSPORTATION and item.amount < Decimal("200000"):
                continue
            selected.append(item)
            covered += item.amount
            if len(selected) >= limit or covered >= overage:
                break
        return selected
