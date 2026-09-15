"""Deterministic tests for BudgetAgent and ItineraryOptimizer."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.agent.models import ActivityKind, ItineraryActivity, ItineraryDay, TripItinerary
from app.agent.optimization import BudgetAgent, ItineraryOptimizer
from app.agent.planner import build_grounded_itinerary
from app.providers.mock import MockPlacesProvider
from app.providers.mock.travel import MockFlightProvider, MockHotelProvider
from app.providers.models import FlightSearchRequest, HotelSearchRequest


def _hotel_payloads(destination: str = "Da Nang"):
    provider = MockHotelProvider()
    hotels = provider.search_hotels(
        HotelSearchRequest(
            destination=destination,
            check_in=date(2026, 10, 12),
            check_out=date(2026, 10, 15),
            guests=2,
            currency="VND",
        )
    )
    return [hotel.model_dump(mode="json") for hotel in hotels]


def _flight_payloads():
    provider = MockFlightProvider()
    flights = provider.search_flights(
        FlightSearchRequest(
            origin="HAN",
            destination="DAD",
            departure_date=date(2026, 10, 12),
            travelers=2,
            currency="VND",
        )
    )
    return [flight.model_dump(mode="json") for flight in flights]


def _catalog():
    provider = MockPlacesProvider()
    places = [
        provider.get_place_details("vn-danang-my-khe").model_dump(mode="json"),
        provider.get_place_details("vn-danang-marble-mountains").model_dump(mode="json"),
        provider.get_place_details("vn-danang-dragon-bridge").model_dump(mode="json"),
    ]
    restaurants = [
        provider.get_place_details("vn-danang-com-nieu").model_dump(mode="json"),
        provider.get_place_details("vn-danang-madam-lan").model_dump(mode="json"),
    ]
    return places, restaurants


def test_budget_agent_breaks_down_flights_hotels_food_activities_transport() -> None:
    places, restaurants = _catalog()
    itinerary = build_grounded_itinerary(
        destination="Da Nang",
        origin="Hanoi",
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 14),
        travelers=2,
        total_budget=Decimal("20000000"),
        currency="VND",
        preferences=["beaches"],
        candidate_places=places,
        candidate_restaurants=restaurants,
    )
    hotels = _hotel_payloads()
    flights = _flight_payloads()
    breakdown = BudgetAgent().analyze(
        itinerary,
        hotel=hotels[0],
        flight=flights[0],
        nights=2,
    )

    assert breakdown.flights > 0
    assert breakdown.hotels > 0
    assert breakdown.food >= 0
    assert breakdown.activities >= 0
    assert breakdown.transportation >= 0
    assert breakdown.total == (
        breakdown.flights
        + breakdown.hotels
        + breakdown.food
        + breakdown.activities
        + breakdown.transportation
    )
    assert breakdown.expensive_components


def test_optimizer_swaps_hotel_a_for_hotel_b_with_explanation() -> None:
    places, restaurants = _catalog()
    # Tight budget forces lodging swap while quality/distance constraints remain.
    itinerary = build_grounded_itinerary(
        destination="Da Nang",
        origin="Hanoi",
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 15),
        travelers=2,
        total_budget=Decimal("12000000"),
        currency="VND",
        preferences=["beaches", "local food"],
        candidate_places=places,
        candidate_restaurants=restaurants,
    )
    hotels = _hotel_payloads()
    flights = _flight_payloads()

    result = ItineraryOptimizer().optimize(
        itinerary,
        candidate_places=places,
        candidate_restaurants=restaurants,
        candidate_hotels=hotels,
        candidate_flights=flights,
        weather=[],
        preferences=["beaches", "local food"],
        trip_pace="balanced",
    )

    assert result.selected_hotel is not None
    assert result.selected_hotel["id"] == "hotel-b-da-nang"
    assert result.selected_hotel["id"] != "hotel-c-da-nang"
    hotel_notes = [note.text for note in result.explanations if note.category.value == "hotels"]
    assert hotel_notes
    assert "Hotel B" in hotel_notes[0]
    assert "Hotel A" in hotel_notes[0]
    assert "tiết kiệm" in hotel_notes[0].casefold() or "saves" in hotel_notes[0].casefold()
    assert "biển" in hotel_notes[0].casefold() or "beach" in hotel_notes[0].casefold()
    assert "4." in hotel_notes[0]
    assert result.budget_breakdown.within_budget or result.budget_breakdown.hotels < Decimal(
        str(hotels[0]["nightly_price"])
    ) * 3


def test_optimizer_does_not_blindly_pick_cheapest_far_hotel() -> None:
    places, restaurants = _catalog()
    itinerary = build_grounded_itinerary(
        destination="Da Nang",
        origin=None,
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 14),
        travelers=2,
        total_budget=Decimal("5000000"),
        currency="VND",
        preferences=["beaches"],
        candidate_places=places,
        candidate_restaurants=restaurants,
    )
    result = ItineraryOptimizer().optimize(
        itinerary,
        candidate_places=places,
        candidate_restaurants=restaurants,
        candidate_hotels=_hotel_payloads(),
        candidate_flights=[],
        preferences=["beaches"],
    )
    assert result.selected_hotel is not None
    assert result.selected_hotel["id"] != "hotel-c-budget-far"
    assert float(result.selected_hotel["rating"]) >= 4.0


def test_optimizer_removes_duplicate_activities() -> None:
    places, restaurants = _catalog()
    beach = places[0]
    restaurant = restaurants[0]
    itinerary = TripItinerary(
        destination="Da Nang",
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 13),
        travelers=2,
        total_budget=Decimal("10000000"),
        currency="VND",
        preferences=["beaches"],
        days=[
            ItineraryDay(
                day_number=1,
                date=date(2026, 10, 12),
                theme="Beach",
                activities=[
                    ItineraryActivity(
                        place_id=beach["id"],
                        name=beach["name"],
                        kind=ActivityKind.ACTIVITY,
                        start_time=datetime.strptime("09:00", "%H:%M").time(),
                        end_time=datetime.strptime("11:30", "%H:%M").time(),
                        estimated_cost=Decimal("360000"),
                        reason="Beach day",
                        travel_time_from_previous=0,
                        latitude=beach["latitude"],
                        longitude=beach["longitude"],
                        rating=beach.get("rating"),
                        opening_hours=beach.get("opening_hours"),
                    ),
                    ItineraryActivity(
                        place_id=restaurant["id"],
                        name=restaurant["name"],
                        kind=ActivityKind.RESTAURANT,
                        start_time=datetime.strptime("12:00", "%H:%M").time(),
                        end_time=datetime.strptime("13:30", "%H:%M").time(),
                        estimated_cost=Decimal("440000"),
                        reason="Lunch",
                        travel_time_from_previous=15,
                        latitude=restaurant["latitude"],
                        longitude=restaurant["longitude"],
                        rating=restaurant.get("rating"),
                    ),
                ],
            ),
            ItineraryDay(
                day_number=2,
                date=date(2026, 10, 13),
                theme="Repeat",
                activities=[
                    ItineraryActivity(
                        place_id=beach["id"],
                        name=beach["name"],
                        kind=ActivityKind.ACTIVITY,
                        start_time=datetime.strptime("09:00", "%H:%M").time(),
                        end_time=datetime.strptime("11:30", "%H:%M").time(),
                        estimated_cost=Decimal("360000"),
                        reason="Duplicate beach",
                        travel_time_from_previous=0,
                        latitude=beach["latitude"],
                        longitude=beach["longitude"],
                        rating=4.0,
                        opening_hours=beach.get("opening_hours"),
                    )
                ],
            ),
        ],
        estimated_total_cost=Decimal("1160000"),
        summary="Duplicate test",
    )
    result = ItineraryOptimizer().optimize(
        itinerary,
        candidate_places=places,
        candidate_restaurants=restaurants,
        preferences=["beaches"],
    )
    beach_visits = [
        activity.place_id
        for day in result.itinerary.days
        for activity in day.activities
        if activity.place_id == beach["id"]
    ]
    assert len(beach_visits) == 1
    assert all(day.activities for day in result.itinerary.days)
    assert any("trùng" in note.text.casefold() or "duplicate" in note.text.casefold() for note in result.explanations)


def test_optimizer_respects_relaxed_pace() -> None:
    places, restaurants = _catalog()
    itinerary = build_grounded_itinerary(
        destination="Da Nang",
        origin=None,
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 12),
        travelers=2,
        total_budget=Decimal("10000000"),
        currency="VND",
        preferences=["beaches", "relaxed pace"],
        candidate_places=places,
        candidate_restaurants=restaurants,
    )
    before = sum(len(day.activities) for day in itinerary.days)
    result = ItineraryOptimizer().optimize(
        itinerary,
        candidate_places=places,
        candidate_restaurants=restaurants,
        preferences=["beaches", "relaxed pace"],
        trip_pace="relaxed",
    )
    after = sum(len(day.activities) for day in result.itinerary.days)
    assert after <= before
    assert any("thư thả" in note.text.casefold() or "relaxed" in note.text.casefold() for note in result.explanations)


def test_optimizer_swaps_outdoor_stop_when_rain_likely() -> None:
    places, restaurants = _catalog()
    itinerary = build_grounded_itinerary(
        destination="Da Nang",
        origin=None,
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 12),
        travelers=2,
        total_budget=Decimal("10000000"),
        currency="VND",
        preferences=["beaches"],
        candidate_places=places,
        candidate_restaurants=restaurants,
    )
    # Ensure an outdoor beach stop exists on the rainy day.
    assert any(act.place_id == "vn-danang-my-khe" for day in itinerary.days for act in day.activities)

    # Add an indoor-tagged place the optimizer can swap to.
    indoor = dict(places[1])
    indoor["id"] = "vn-danang-indoor-museum"
    indoor["name"] = "Da Nang Museum"
    indoor["tags"] = ["museum", "indoor", "culture"]
    indoor["price_level"] = "low"
    indoor["rating"] = 4.5
    enriched_places = places + [indoor]

    result = ItineraryOptimizer().optimize(
        itinerary,
        candidate_places=enriched_places,
        candidate_restaurants=restaurants,
        weather=[
            {
                "destination": "Da Nang",
                "forecast_date": "2026-10-12",
                "condition": "rain",
                "temperature_min_c": 24,
                "temperature_max_c": 28,
                "precipitation_probability": 80,
                "humidity_percent": 85,
                "wind_speed_kph": 12,
            }
        ],
        preferences=["beaches"],
    )
    rainy_ids = {act.place_id for day in result.itinerary.days for act in day.activities}
    assert "vn-danang-indoor-museum" in rainy_ids or any(
        "rain" in note.text.casefold() for note in result.explanations
    )
