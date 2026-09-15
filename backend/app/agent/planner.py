"""Grounded itinerary planning from tool-backed candidate catalogs only."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Sequence

from app.agent.costs import estimate_place_cost
from app.agent.models import (
    ActivityKind,
    ItineraryActivity,
    ItineraryDay,
    TripItinerary,
)
from app.providers.models import PlaceCategory, PlaceDetails


_DAY_SLOTS = [
    (time(9, 0), time(11, 30), ActivityKind.ACTIVITY),
    (time(12, 0), time(13, 30), ActivityKind.RESTAURANT),
    (time(14, 30), time(17, 0), ActivityKind.ACTIVITY),
]


def _haversine_km(lat_one: float, lon_one: float, lat_two: float, lon_two: float) -> float:
    latitude_delta = radians(lat_two - lat_one)
    longitude_delta = radians(lon_two - lon_one)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(lat_one)) * cos(radians(lat_two)) * sin(longitude_delta / 2) ** 2
    )
    return 6371.0 * 2 * asin(sqrt(value))


def travel_minutes_between(previous: PlaceDetails, current: PlaceDetails) -> int:
    """Estimate city travel time from tool-provided coordinates (not LLM guesses)."""
    distance = _haversine_km(
        previous.latitude, previous.longitude, current.latitude, current.longitude
    )
    # Assume mixed urban transfer ~25 km/h with a short fixed buffer.
    return max(5, int(round((distance / 25.0) * 60)) + 5) if distance > 0.05 else 0


def _preference_score(place: PlaceDetails, preferences: Sequence[str]) -> float:
    if not preferences:
        return float(place.rating or 0)
    haystack = " ".join([place.name, place.description] + place.tags).casefold()
    overlap = sum(1 for pref in preferences if pref in haystack)
    return overlap * 10 + float(place.rating or 0)


def _as_details(payload: Dict) -> PlaceDetails:
    return PlaceDetails.model_validate(payload)


def build_grounded_itinerary(
    *,
    destination: str,
    origin: Optional[str],
    start_date: date,
    end_date: date,
    travelers: int,
    total_budget: Decimal,
    currency: str,
    preferences: Sequence[str],
    candidate_places: Sequence[Dict],
    candidate_restaurants: Sequence[Dict],
) -> TripItinerary:
    """Select and schedule only place IDs present in tool results."""
    places = sorted(
        (_as_details(item) for item in candidate_places),
        key=lambda place: _preference_score(place, preferences),
        reverse=True,
    )
    restaurants = sorted(
        (_as_details(item) for item in candidate_restaurants),
        key=lambda place: _preference_score(place, preferences),
        reverse=True,
    )
    if not places:
        raise ValueError("Công cụ không trả về địa điểm ứng viên nào.")

    day_count = (end_date - start_date).days + 1
    place_index = 0
    restaurant_index = 0
    days: List[ItineraryDay] = []
    total_cost = Decimal("0")

    for offset in range(day_count):
        day_date = start_date + timedelta(days=offset)
        theme = _day_theme(preferences, offset)
        activities: List[ItineraryActivity] = []
        previous: Optional[PlaceDetails] = None
        # Uniqueness is enforced per day so multi-day trips can revisit highlights.
        used_ids: set[str] = set()

        for start_time, end_time, kind in _DAY_SLOTS:
            selected: Optional[PlaceDetails] = None
            if kind is ActivityKind.RESTAURANT:
                selected, restaurant_index = _next_unused(restaurants, used_ids, restaurant_index)
                if selected is None:
                    selected, place_index = _next_unused(
                        [p for p in places if p.category == PlaceCategory.RESTAURANT],
                        used_ids,
                        0,
                    )
            else:
                selected, place_index = _next_unused(places, used_ids, place_index)

            if selected is None:
                continue

            used_ids.add(selected.id)
            travel = travel_minutes_between(previous, selected) if previous else 0
            cost = estimate_place_cost(
                category=selected.category,
                price_level=selected.price_level,
                travelers=travelers,
            )
            total_cost += cost
            activities.append(
                ItineraryActivity(
                    place_id=selected.id,
                    name=selected.name,
                    kind=kind
                    if selected.category != PlaceCategory.RESTAURANT
                    else ActivityKind.RESTAURANT,
                    start_time=start_time,
                    end_time=end_time,
                    estimated_cost=cost,
                    reason=_reason_for(selected, preferences, kind),
                    travel_time_from_previous=travel,
                    latitude=selected.latitude,
                    longitude=selected.longitude,
                    rating=selected.rating,
                    opening_hours=selected.opening_hours,
                )
            )
            previous = selected

        days.append(
            ItineraryDay(
                day_number=offset + 1,
                date=day_date,
                theme=theme,
                activities=activities,
            )
        )

    summary = (
        f"Kế hoạch {day_count} ngày tại {destination}, tập trung vào "
        f"{', '.join(preferences) if preferences else 'tham quan cân bằng'}."
    )
    return TripItinerary(
        destination=destination,
        origin=origin,
        start_date=start_date,
        end_date=end_date,
        travelers=travelers,
        total_budget=total_budget,
        currency=currency,
        preferences=list(preferences),
        days=days,
        estimated_total_cost=total_cost,
        summary=summary,
    )


def _next_unused(
    catalog: Sequence[PlaceDetails],
    used_ids: set[str],
    start_index: int,
) -> tuple[Optional[PlaceDetails], int]:
    if not catalog:
        return None, start_index
    for offset in range(len(catalog)):
        index = (start_index + offset) % len(catalog)
        candidate = catalog[index]
        if candidate.id not in used_ids:
            return candidate, index + 1
    return None, start_index


def _day_theme(preferences: Sequence[str], offset: int) -> str:
    if not preferences:
        return "Ngày cân bằng"
    return preferences[offset % len(preferences)].title() + " trọng tâm"


def _reason_for(place: PlaceDetails, preferences: Sequence[str], kind: ActivityKind) -> str:
    matched = [pref for pref in preferences if pref in " ".join(place.tags).casefold()]
    if matched:
        return f"Khớp sở thích {matched[0]} và được đánh giá {place.rating or 'tốt'}."
    if kind is ActivityKind.RESTAURANT:
        return f"Điểm ăn uống địa phương: {place.name}."
    return f"Điểm nổi bật tại {place.destination} theo xếp hạng danh mục."


def iso_to_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
