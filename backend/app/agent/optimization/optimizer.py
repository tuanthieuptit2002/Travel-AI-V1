"""ItineraryOptimizer — balance cost, quality, distance, and preferences."""

from __future__ import annotations

from copy import deepcopy
from datetime import time
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.agent.costs import estimate_place_cost
from app.agent.models import ActivityKind, ItineraryActivity, TripItinerary
from app.agent.optimization.budget import BudgetAgent
from app.agent.optimization.models import (
    CostCategory,
    OptimizationExplanation,
    OptimizationResult,
)
from app.agent.planner import travel_minutes_between
from app.providers.models import PlaceCategory, PlaceDetails

# Multi-objective weights — cost is never the only signal.
_W_QUALITY = 0.30
_W_PREFERENCE = 0.25
_W_DISTANCE = 0.20
_W_COST = 0.25

_MIN_HOTEL_RATING = 4.0
_BEACH_ANCHOR = (16.0590, 108.2467)  # My Khe beach area (Da Nang)


class ItineraryOptimizer:
    """Optimize a grounded itinerary without blindly minimizing cost."""

    def __init__(self, budget_agent: Optional[BudgetAgent] = None) -> None:
        self.budget_agent = budget_agent or BudgetAgent()

    def optimize(
        self,
        itinerary: TripItinerary,
        *,
        candidate_places: Sequence[Dict[str, Any]],
        candidate_restaurants: Sequence[Dict[str, Any]],
        candidate_hotels: Sequence[Dict[str, Any]] | None = None,
        candidate_flights: Sequence[Dict[str, Any]] | None = None,
        weather: Sequence[Dict[str, Any]] | None = None,
        preferences: Sequence[str] | None = None,
        trip_pace: Optional[str] = None,
    ) -> OptimizationResult:
        prefs = list(preferences or itinerary.preferences or [])
        pace = (trip_pace or _infer_pace(prefs)).casefold()
        hotels = [dict(item) for item in candidate_hotels or []]
        flights = [dict(item) for item in candidate_flights or []]
        places = [_as_place(item) for item in candidate_places]
        restaurants = [_as_place(item) for item in candidate_restaurants]
        weather_by_date = {
            str(item.get("forecast_date")): item for item in (weather or []) if item.get("forecast_date")
        }

        working = TripItinerary.model_validate(itinerary.model_dump())
        explanations: List[OptimizationExplanation] = []
        regenerated = False

        # 1) Remove duplicate place visits across the trip (keep highest-rated occurrence).
        working, dup_notes = self._deduplicate_activities(working, places, restaurants, prefs)
        explanations.extend(dup_notes)

        # 2) Weather-aware swaps for rainy days.
        working, weather_notes = self._apply_weather_swaps(
            working, places, restaurants, prefs, weather_by_date
        )
        explanations.extend(weather_notes)

        # 3) Trip pace adjustments.
        working, pace_notes = self._apply_pace(working, pace)
        explanations.extend(pace_notes)

        # 4) Opening-hours corrections when parseable.
        working, hours_notes = self._enforce_opening_hours(working, places + restaurants, prefs)
        explanations.extend(hours_notes)

        # 5) Select hotel/flight with balanced score (not cheapest alone).
        selected_hotel = self._select_hotel(hotels, prefs) if hotels else None
        selected_flight = self._select_flight(flights) if flights else None

        nights = max(0, (working.end_date - working.start_date).days)
        breakdown = self.budget_agent.analyze(
            working, hotel=selected_hotel, flight=selected_flight, nights=nights
        )

        # 6) If over budget: identify expensive parts, compare alternatives, swap, regenerate travel times.
        if not breakdown.within_budget:
            working, selected_hotel, selected_flight, swap_notes, regenerated = self._resolve_over_budget(
                working,
                breakdown=breakdown,
                places=places,
                restaurants=restaurants,
                hotels=hotels,
                flights=flights,
                preferences=prefs,
                selected_hotel=selected_hotel,
                selected_flight=selected_flight,
                nights=nights,
            )
            explanations.extend(swap_notes)
            breakdown = self.budget_agent.analyze(
                working, hotel=selected_hotel, flight=selected_flight, nights=nights
            )

        # Recompute activity subtotal into itinerary.estimated_total_cost as full trip total.
        working.estimated_total_cost = breakdown.total
        working.summary = _refresh_summary(working, breakdown.within_budget)

        return OptimizationResult(
            itinerary=working,
            budget_breakdown=breakdown,
            explanations=explanations,
            selected_hotel=selected_hotel,
            selected_flight=selected_flight,
            regenerated=regenerated,
        )

    def _resolve_over_budget(
        self,
        itinerary: TripItinerary,
        *,
        breakdown,
        places: List[PlaceDetails],
        restaurants: List[PlaceDetails],
        hotels: List[Dict[str, Any]],
        flights: List[Dict[str, Any]],
        preferences: Sequence[str],
        selected_hotel: Optional[Dict[str, Any]],
        selected_flight: Optional[Dict[str, Any]],
        nights: int,
    ) -> Tuple[TripItinerary, Optional[Dict], Optional[Dict], List[OptimizationExplanation], bool]:
        explanations: List[OptimizationExplanation] = []
        working = TripItinerary.model_validate(itinerary.model_dump())
        hotel = deepcopy(selected_hotel) if selected_hotel else None
        flight = deepcopy(selected_flight) if selected_flight else None
        regenerated = False
        current = breakdown

        for component in current.expensive_components:
            if current.within_budget:
                break

            if component.category is CostCategory.HOTELS and hotel and hotels:
                alternative = self._best_hotel_alternative(hotel, hotels, preferences)
                if alternative:
                    savings = Decimal(str(hotel.get("nightly_price") or 0)) * Decimal(nights) - Decimal(
                        str(alternative.get("nightly_price") or 0)
                    ) * Decimal(nights)
                    distance_m = int(
                        round(
                            _haversine_km(
                                float(alternative["latitude"]),
                                float(alternative["longitude"]),
                                _BEACH_ANCHOR[0],
                                _BEACH_ANCHOR[1],
                            )
                            * 1000
                        )
                    )
                    rating = float(alternative.get("rating") or 0)
                    explanations.append(
                        OptimizationExplanation(
                            category=CostCategory.HOTELS,
                            replaced_id=str(hotel.get("id")),
                            selected_id=str(alternative.get("id")),
                            savings=max(Decimal("0"), savings),
                            text=(
                                f"{alternative['name']} được chọn thay cho {hotel['name']} "
                                f"vì tiết kiệm {int(savings):,} VND, vẫn trong bán kính "
                                f"{distance_m}m tới biển và giữ đánh giá trên "
                                f"{rating:.1f}."
                            ),
                        )
                    )
                    hotel = alternative
                    current = self.budget_agent.analyze(
                        working, hotel=hotel, flight=flight, nights=nights
                    )
                    continue

            if component.category in {CostCategory.ACTIVITIES, CostCategory.FOOD}:
                swapped, note = self._swap_expensive_stop(
                    working,
                    component.reference_id,
                    places=places,
                    restaurants=restaurants,
                    preferences=preferences,
                    category=component.category,
                )
                if swapped and note:
                    working = swapped
                    regenerated = True
                    explanations.append(note)
                    working = self._recompute_travel_times(working)
                    current = self.budget_agent.analyze(
                        working, hotel=hotel, flight=flight, nights=nights
                    )
                    continue

            if component.category is CostCategory.FLIGHTS and flight and flights:
                alternative = self._best_flight_alternative(flight, flights)
                if alternative:
                    old_cost = Decimal(str(flight.get("price") or 0)) * Decimal(working.travelers) * 2
                    new_cost = (
                        Decimal(str(alternative.get("price") or 0)) * Decimal(working.travelers) * 2
                    )
                    savings = old_cost - new_cost
                    explanations.append(
                        OptimizationExplanation(
                            category=CostCategory.FLIGHTS,
                            replaced_id=str(flight.get("id")),
                            selected_id=str(alternative.get("id")),
                            savings=max(Decimal("0"), savings),
                            text=(
                                f"{alternative.get('airline')} {alternative.get('flight_number')} "
                                f"được chọn thay cho {flight.get('airline')} "
                                f"{flight.get('flight_number')} vì tiết kiệm "
                                f"{int(savings):,} VND và giữ số điểm dừng là "
                                f"{alternative.get('stops', 0)}."
                            ),
                        )
                    )
                    flight = alternative
                    current = self.budget_agent.analyze(
                        working, hotel=hotel, flight=flight, nights=nights
                    )

        return working, hotel, flight, explanations, regenerated

    def _deduplicate_activities(
        self,
        itinerary: TripItinerary,
        places: List[PlaceDetails],
        restaurants: List[PlaceDetails],
        preferences: Sequence[str],
    ) -> Tuple[TripItinerary, List[OptimizationExplanation]]:
        """Replace repeated stops with unused alternatives instead of leaving empty days."""
        explanations: List[OptimizationExplanation] = []
        working = TripItinerary.model_validate(itinerary.model_dump())
        used: set[str] = set()

        for day in working.days:
            updated: List[ItineraryActivity] = []
            for activity in day.activities:
                if activity.place_id not in used:
                    used.add(activity.place_id)
                    updated.append(activity)
                    continue

                pool = restaurants if activity.kind == ActivityKind.RESTAURANT else places
                alternative = _best_unused_candidate(
                    pool,
                    used=used,
                    preferences=preferences,
                    require_indoor=False,
                    exclude_ids={activity.place_id},
                    travelers=working.travelers,
                    min_rating=max(3.5, float(activity.rating or 0) - 0.6),
                )
                if alternative is None:
                    # Keep the duplicate rather than emptying the day.
                    updated.append(activity)
                    continue

                replacement = _activity_from_place(
                    alternative, activity, activity.kind, working.travelers, preferences
                )
                used.add(alternative.id)
                updated.append(replacement)
                explanations.append(
                    OptimizationExplanation(
                        category=(
                            CostCategory.FOOD
                            if activity.kind == ActivityKind.RESTAURANT
                            else CostCategory.ACTIVITIES
                        ),
                        replaced_id=activity.place_id,
                        selected_id=alternative.id,
                        text=(
                            f"{alternative.name} thay cho điểm trùng {activity.name} "
                            f"để đa dạng lịch trình mà vẫn giữ chất lượng tương đương."
                        ),
                    )
                )
            day.activities = updated

        working = self._recompute_travel_times(working)
        working.estimated_total_cost = _activity_subtotal(working)
        return working, explanations

    def _apply_weather_swaps(
        self,
        itinerary: TripItinerary,
        places: List[PlaceDetails],
        restaurants: List[PlaceDetails],
        preferences: Sequence[str],
        weather_by_date: Dict[str, Dict[str, Any]],
    ) -> Tuple[TripItinerary, List[OptimizationExplanation]]:
        explanations: List[OptimizationExplanation] = []
        working = TripItinerary.model_validate(itinerary.model_dump())
        outdoor_tags = {"beach", "beaches", "outdoor", "viewpoint", "hiking"}
        used = {act.place_id for day in working.days for act in day.activities}

        for day in working.days:
            forecast = weather_by_date.get(day.date.isoformat())
            if not forecast:
                continue
            rainy = str(forecast.get("condition", "")).casefold() in {
                "rain",
                "showers",
                "thunderstorm",
            } or int(forecast.get("precipitation_probability") or 0) >= 60
            if not rainy:
                continue

            for index, activity in enumerate(list(day.activities)):
                if activity.kind is ActivityKind.RESTAURANT:
                    continue
                place = next((item for item in places if item.id == activity.place_id), None)
                tags = {tag.casefold() for tag in (place.tags if place else [])}
                if not tags.intersection(outdoor_tags):
                    continue
                alternative = _best_unused_candidate(
                    places,
                    used=used,
                    preferences=preferences,
                    require_indoor=True,
                    exclude_ids={activity.place_id},
                    travelers=working.travelers,
                )
                if alternative is None:
                    continue
                replacement = _activity_from_place(
                    alternative, activity, ActivityKind.ACTIVITY, working.travelers, preferences
                )
                day.activities[index] = replacement
                used.discard(activity.place_id)
                used.add(alternative.id)
                explanations.append(
                    OptimizationExplanation(
                        category=CostCategory.ACTIVITIES,
                        replaced_id=activity.place_id,
                        selected_id=alternative.id,
                        text=(
                            f"{alternative.name} thay {activity.name} vào ngày {day.date.isoformat()} "
                            f"vì khả năng mưa cao và điểm trong nhà phù hợp hơn."
                        ),
                    )
                )
        working = self._recompute_travel_times(working)
        working.estimated_total_cost = _activity_subtotal(working)
        return working, explanations

    def _apply_pace(
        self, itinerary: TripItinerary, pace: str
    ) -> Tuple[TripItinerary, List[OptimizationExplanation]]:
        explanations: List[OptimizationExplanation] = []
        working = TripItinerary.model_validate(itinerary.model_dump())
        if pace != "relaxed":
            return working, explanations

        for day in working.days:
            if len(day.activities) <= 2:
                continue
            # Drop the lowest-rated non-restaurant stop to create breathing room.
            candidates = [
                (idx, act)
                for idx, act in enumerate(day.activities)
                if act.kind != ActivityKind.RESTAURANT
            ]
            if not candidates:
                continue
            drop_idx, dropped = min(candidates, key=lambda pair: float(pair[1].rating or 0))
            day.activities.pop(drop_idx)
            explanations.append(
                OptimizationExplanation(
                    category=CostCategory.ACTIVITIES,
                    replaced_id=dropped.place_id,
                    selected_id=None,
                    text=(
                        f"Đã bỏ {dropped.name} để giữ nhịp độ thư thả "
                        f"với ít điểm dừng hơn vào ngày {day.day_number}."
                    ),
                )
            )
        working = self._recompute_travel_times(working)
        working.estimated_total_cost = _activity_subtotal(working)
        return working, explanations

    def _enforce_opening_hours(
        self,
        itinerary: TripItinerary,
        catalog: List[PlaceDetails],
        preferences: Sequence[str],
    ) -> Tuple[TripItinerary, List[OptimizationExplanation]]:
        explanations: List[OptimizationExplanation] = []
        working = TripItinerary.model_validate(itinerary.model_dump())
        by_id = {place.id: place for place in catalog}
        used = {act.place_id for day in working.days for act in day.activities}

        for day in working.days:
            for index, activity in enumerate(list(day.activities)):
                place = by_id.get(activity.place_id)
                if place is None or not place.opening_hours:
                    continue
                window = _parse_hours(place.opening_hours)
                if window is None:
                    continue
                open_at, close_at = window
                if open_at <= activity.start_time and activity.end_time <= close_at:
                    continue
                pool = [
                    item
                    for item in catalog
                    if item.id not in used
                    and (
                        (activity.kind == ActivityKind.RESTAURANT and "restaurant" in item.category.value)
                        or (activity.kind != ActivityKind.RESTAURANT and "restaurant" not in item.category.value)
                    )
                ]
                alternative = _best_unused_candidate(
                    pool,
                    used=used,
                    preferences=preferences,
                    require_indoor=False,
                    exclude_ids={activity.place_id},
                    travelers=working.travelers,
                    required_open_at=activity.start_time,
                    required_close_by=activity.end_time,
                )
                if alternative is None:
                    continue
                replacement = _activity_from_place(
                    alternative, activity, activity.kind, working.travelers, preferences
                )
                day.activities[index] = replacement
                used.discard(activity.place_id)
                used.add(alternative.id)
                explanations.append(
                    OptimizationExplanation(
                        category=(
                            CostCategory.FOOD
                            if activity.kind == ActivityKind.RESTAURANT
                            else CostCategory.ACTIVITIES
                        ),
                        replaced_id=activity.place_id,
                        selected_id=alternative.id,
                        text=(
                            f"{alternative.name} thay {activity.name} vì giờ mở cửa "
                            f"({place.opening_hours}) không khớp khung giờ đã xếp."
                        ),
                    )
                )
        working = self._recompute_travel_times(working)
        working.estimated_total_cost = _activity_subtotal(working)
        return working, explanations

    def _swap_expensive_stop(
        self,
        itinerary: TripItinerary,
        place_id: Optional[str],
        *,
        places: List[PlaceDetails],
        restaurants: List[PlaceDetails],
        preferences: Sequence[str],
        category: CostCategory,
    ) -> Tuple[Optional[TripItinerary], Optional[OptimizationExplanation]]:
        if not place_id:
            return None, None
        working = TripItinerary.model_validate(itinerary.model_dump())
        used = {act.place_id for day in working.days for act in day.activities}
        pool = restaurants if category is CostCategory.FOOD else places

        for day in working.days:
            for index, activity in enumerate(day.activities):
                if activity.place_id != place_id:
                    continue
                current = next((item for item in pool if item.id == place_id), None)
                alternative = _best_unused_candidate(
                    pool,
                    used=used,
                    preferences=preferences,
                    require_indoor=False,
                    exclude_ids={place_id},
                    travelers=working.travelers,
                    max_cost=activity.estimated_cost,
                    min_rating=max(3.8, float(activity.rating or 0) - 0.4),
                )
                if alternative is None or current is None:
                    return None, None
                replacement = _activity_from_place(
                    alternative, activity, activity.kind, working.travelers, preferences
                )
                savings = activity.estimated_cost - replacement.estimated_cost
                if savings <= 0:
                    return None, None
                # Require preference/quality balance: alternative score must stay competitive.
                if _place_score(alternative, preferences, anchor=_activity_anchor(day.activities, index)) < (
                    _place_score(current, preferences, anchor=_activity_anchor(day.activities, index)) * 0.75
                ):
                    return None, None
                day.activities[index] = replacement
                note = OptimizationExplanation(
                    category=category,
                    replaced_id=place_id,
                    selected_id=alternative.id,
                    savings=savings,
                    text=(
                        f"{alternative.name} được chọn thay cho {activity.name} vì "
                        f"tiết kiệm {int(savings):,} VND, giữ đánh giá "
                        f"{alternative.rating or 'N/A'} và vẫn khớp sở thích của bạn."
                    ),
                )
                return working, note
        return None, None

    def _select_hotel(
        self, hotels: Sequence[Dict[str, Any]], preferences: Sequence[str]
    ) -> Dict[str, Any]:
        # Initial pick leans quality; BudgetAgent may later swap if over budget.
        ranked = sorted(
            hotels,
            key=lambda hotel: (
                float(hotel.get("rating") or 0),
                self._hotel_score(hotel, preferences),
            ),
            reverse=True,
        )
        return dict(ranked[0])

    def _best_hotel_alternative(
        self,
        current: Dict[str, Any],
        hotels: Sequence[Dict[str, Any]],
        preferences: Sequence[str],
    ) -> Optional[Dict[str, Any]]:
        current_price = Decimal(str(current.get("nightly_price") or 0))
        candidates = []
        for hotel in hotels:
            if hotel.get("id") == current.get("id"):
                continue
            price = Decimal(str(hotel.get("nightly_price") or 0))
            rating = float(hotel.get("rating") or 0)
            if price >= current_price:
                continue
            if rating < _MIN_HOTEL_RATING:
                continue
            # Must remain reasonably close to the beach anchor.
            distance_km = _haversine_km(
                float(hotel["latitude"]),
                float(hotel["longitude"]),
                _BEACH_ANCHOR[0],
                _BEACH_ANCHOR[1],
            )
            if distance_km > 1.5:
                continue
            candidates.append(hotel)
        if not candidates:
            return None
        return dict(
            max(candidates, key=lambda hotel: self._hotel_score(hotel, preferences))
        )

    def _hotel_score(self, hotel: Dict[str, Any], preferences: Sequence[str]) -> float:
        rating = float(hotel.get("rating") or 0) / 5.0
        price = float(hotel.get("nightly_price") or 1)
        # Normalize cost against a soft ceiling so cheaper is better but not dominant.
        cost_norm = min(1.0, price / 3_000_000.0)
        distance_km = _haversine_km(
            float(hotel.get("latitude") or _BEACH_ANCHOR[0]),
            float(hotel.get("longitude") or _BEACH_ANCHOR[1]),
            _BEACH_ANCHOR[0],
            _BEACH_ANCHOR[1],
        )
        distance_norm = min(1.0, distance_km / 5.0)
        amenities = " ".join(hotel.get("amenities") or []).casefold()
        pref_hits = sum(1 for pref in preferences if pref.casefold() in amenities or pref.casefold() in str(hotel.get("name", "")).casefold())
        pref_norm = min(1.0, pref_hits / 2.0) if preferences else 0.5
        return (
            _W_QUALITY * rating
            + _W_PREFERENCE * pref_norm
            + _W_DISTANCE * (1.0 - distance_norm)
            - _W_COST * cost_norm
        )

    def _select_flight(self, flights: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        return dict(max(flights, key=self._flight_score))

    def _best_flight_alternative(
        self, current: Dict[str, Any], flights: Sequence[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        current_price = float(current.get("price") or 0)
        options = [
            flight
            for flight in flights
            if flight.get("id") != current.get("id")
            and float(flight.get("price") or 0) < current_price
            and int(flight.get("stops") or 0) <= int(current.get("stops") or 0) + 1
        ]
        if not options:
            return None
        return dict(max(options, key=self._flight_score))

    def _flight_score(self, flight: Dict[str, Any]) -> float:
        price = float(flight.get("price") or 1)
        cost_norm = min(1.0, price / 4_000_000.0)
        stops = int(flight.get("stops") or 0)
        quality = 1.0 - min(1.0, stops / 2.0)
        return _W_QUALITY * quality - _W_COST * cost_norm

    def _recompute_travel_times(self, itinerary: TripItinerary) -> TripItinerary:
        working = TripItinerary.model_validate(itinerary.model_dump())
        for day in working.days:
            previous = None
            for activity in day.activities:
                if previous is None:
                    activity.travel_time_from_previous = 0
                else:
                    fake_prev = PlaceDetails(
                        id=previous.place_id,
                        name=previous.name,
                        category=PlaceCategory.ATTRACTION,
                        destination=working.destination,
                        description="",
                        latitude=previous.latitude,
                        longitude=previous.longitude,
                        address="",
                    )
                    fake_curr = PlaceDetails(
                        id=activity.place_id,
                        name=activity.name,
                        category=PlaceCategory.ATTRACTION,
                        destination=working.destination,
                        description="",
                        latitude=activity.latitude,
                        longitude=activity.longitude,
                        address="",
                    )
                    activity.travel_time_from_previous = travel_minutes_between(fake_prev, fake_curr)
                previous = activity
        return working


def _as_place(payload: Dict[str, Any]) -> PlaceDetails:
    return PlaceDetails.model_validate(payload)


def _infer_pace(preferences: Sequence[str]) -> str:
    joined = " ".join(preferences).casefold()
    mapping = {
        "relaxed": "relaxed",
        "thư thả": "relaxed",
        "packed": "packed",
        "dày đặc": "packed",
        "balanced": "balanced",
        "cân bằng": "balanced",
    }
    for key, value in mapping.items():
        if key in joined:
            return value
    return "balanced"


def _haversine_km(lat_one: float, lon_one: float, lat_two: float, lon_two: float) -> float:
    latitude_delta = radians(lat_two - lat_one)
    longitude_delta = radians(lon_two - lon_one)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(lat_one)) * cos(radians(lat_two)) * sin(longitude_delta / 2) ** 2
    )
    return 6371.0 * 2 * asin(sqrt(value))


def _preference_bonus(place: Optional[PlaceDetails], preferences: Sequence[str]) -> float:
    if place is None or not preferences:
        return 0.0
    haystack = " ".join([place.name, place.description] + place.tags).casefold()
    return float(sum(3 for pref in preferences if pref.casefold() in haystack))


def _place_score(
    place: PlaceDetails,
    preferences: Sequence[str],
    *,
    anchor: Optional[Tuple[float, float]] = None,
) -> float:
    rating = float(place.rating or 0) / 5.0
    pref = min(1.0, _preference_bonus(place, preferences) / 6.0)
    cost = estimate_place_cost(
        category=place.category, price_level=place.price_level, travelers=1
    )
    cost_norm = min(1.0, float(cost) / 500_000.0)
    distance_norm = 0.5
    if anchor is not None:
        distance_norm = min(
            1.0,
            _haversine_km(place.latitude, place.longitude, anchor[0], anchor[1]) / 8.0,
        )
    return (
        _W_QUALITY * rating
        + _W_PREFERENCE * pref
        + _W_DISTANCE * (1.0 - distance_norm)
        - _W_COST * cost_norm
    )


def _activity_anchor(
    activities: Sequence[ItineraryActivity], index: int
) -> Optional[Tuple[float, float]]:
    if index > 0:
        previous = activities[index - 1]
        return previous.latitude, previous.longitude
    if index + 1 < len(activities):
        nxt = activities[index + 1]
        return nxt.latitude, nxt.longitude
    return None


def _best_unused_candidate(
    catalog: Sequence[PlaceDetails],
    *,
    used: set[str],
    preferences: Sequence[str],
    require_indoor: bool,
    exclude_ids: set[str],
    travelers: int,
    max_cost: Optional[Decimal] = None,
    min_rating: float = 0.0,
    required_open_at: Optional[time] = None,
    required_close_by: Optional[time] = None,
) -> Optional[PlaceDetails]:
    indoor_tags = {"museum", "cafe", "indoor", "mall", "gallery", "market"}
    outdoor_tags = {"beach", "beaches", "outdoor", "viewpoint", "hiking"}
    ranked: List[Tuple[float, PlaceDetails]] = []
    for place in catalog:
        if place.id in used or place.id in exclude_ids:
            continue
        tags = {tag.casefold() for tag in place.tags}
        if require_indoor and tags.intersection(outdoor_tags) and not tags.intersection(indoor_tags):
            continue
        if require_indoor and not tags.intersection(indoor_tags) and "beach" in " ".join(tags):
            continue
        if float(place.rating or 0) < min_rating:
            continue
        cost = estimate_place_cost(
            category=place.category, price_level=place.price_level, travelers=travelers
        )
        if max_cost is not None and cost >= max_cost:
            continue
        if required_open_at and place.opening_hours:
            window = _parse_hours(place.opening_hours)
            if window and not (window[0] <= required_open_at and required_close_by <= window[1]):
                continue
        ranked.append((_place_score(place, preferences), place))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1]


def _activity_from_place(
    place: PlaceDetails,
    template: ItineraryActivity,
    kind: ActivityKind,
    travelers: int,
    preferences: Sequence[str],
) -> ItineraryActivity:
    cost = estimate_place_cost(
        category=place.category, price_level=place.price_level, travelers=travelers
    )
    matched = [pref for pref in preferences if pref.casefold() in " ".join(place.tags).casefold()]
    reason = (
        f"Điểm tối ưu khớp sở thích {matched[0]}, đánh giá {place.rating}."
        if matched
        else f"Phương án thay thế cân bằng chi phí và chất lượng ({place.rating})."
    )
    return ItineraryActivity(
        place_id=place.id,
        name=place.name,
        kind=kind,
        start_time=template.start_time,
        end_time=template.end_time,
        estimated_cost=cost,
        reason=reason,
        travel_time_from_previous=0,
        latitude=place.latitude,
        longitude=place.longitude,
        rating=place.rating,
        opening_hours=place.opening_hours,
    )


def _parse_hours(value: str) -> Optional[Tuple[time, time]]:
    cleaned = value.replace("–", "-").replace("—", "-")
    if "-" not in cleaned:
        return None
    left, right = [part.strip() for part in cleaned.split("-", 1)]
    try:
        open_at = time.fromisoformat(left if len(left) == 5 else left.zfill(5))
        close_at = time.fromisoformat(right if len(right) == 5 else right.zfill(5))
        return open_at, close_at
    except ValueError:
        return None


def _activity_subtotal(itinerary: TripItinerary) -> Decimal:
    return sum(
        (activity.estimated_cost for day in itinerary.days for activity in day.activities),
        Decimal("0"),
    )


def _refresh_summary(itinerary: TripItinerary, within_budget: bool) -> str:
    base = itinerary.summary or f"Kế hoạch cho {itinerary.destination}."
    if within_budget:
        return base.rstrip(".") + ". Đã tối ưu để nằm trong ngân sách mà vẫn giữ chất lượng."
    return base.rstrip(".") + ". Đã tối ưu có đánh đổi; hãy xem lại áp lực ngân sách còn lại."
