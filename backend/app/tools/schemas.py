"""Typed input/output contracts for agent tools.

Tools return these structured payloads only. Raw provider SDK responses and
database rows must never be forwarded to the agent.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.providers.models import (
    FlightSearchResult,
    HotelSearchResult,
    PlaceDetails,
    PlaceSearchResult,
    RouteResult,
    TravelMode,
    WeatherResult,
)


class ToolInput(BaseModel):
    """Base type for validated tool arguments."""


class ToolOutput(BaseModel):
    success: bool
    error: Optional[str] = None


class SearchPlacesInput(ToolInput):
    destination: str = Field(min_length=1, max_length=255)
    query: str = Field(default="", max_length=255)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    radius_km: Optional[float] = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def require_coordinate_pair(self) -> SearchPlacesInput:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class SearchPlacesOutput(ToolOutput):
    places: List[PlaceSearchResult] = Field(default_factory=list)


class PlaceDetailsInput(ToolInput):
    place_id: str = Field(min_length=1, max_length=255)


class PlaceDetailsOutput(ToolOutput):
    place: Optional[PlaceDetails] = None


class SearchRestaurantsInput(ToolInput):
    destination: str = Field(min_length=1, max_length=255)
    cuisine: Optional[str] = Field(default=None, max_length=100)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    max_price_level: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")


class SearchRestaurantsOutput(ToolOutput):
    restaurants: List[PlaceDetails] = Field(default_factory=list)


class SearchAttractionsInput(ToolInput):
    destination: str = Field(min_length=1, max_length=255)
    query: str = Field(default="", max_length=255)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)


class SearchAttractionsOutput(ToolOutput):
    attractions: List[PlaceSearchResult] = Field(default_factory=list)


class SearchHotelsInput(ToolInput):
    destination: str = Field(min_length=1, max_length=255)
    check_in: date = Field(description="Check-in date in ISO YYYY-MM-DD format")
    check_out: date = Field(description="Check-out date in ISO YYYY-MM-DD format")
    guests: int = Field(default=1, ge=1, le=20)
    rooms: int = Field(default=1, ge=1, le=10)
    currency: str = Field(default="VND", min_length=3, max_length=3)


class SearchHotelsOutput(ToolOutput):
    hotels: List[HotelSearchResult] = Field(default_factory=list)


class SearchFlightsInput(ToolInput):
    origin: str = Field(min_length=1, max_length=10)
    destination: str = Field(min_length=1, max_length=10)
    departure_date: date = Field(description="Departure date in ISO YYYY-MM-DD format")
    travelers: int = Field(default=1, ge=1, le=9)
    currency: str = Field(default="VND", min_length=3, max_length=3)


class SearchFlightsOutput(ToolOutput):
    flights: List[FlightSearchResult] = Field(default_factory=list)


class GetWeatherInput(ToolInput):
    destination: str = Field(min_length=1, max_length=255)
    forecast_date: date = Field(description="Forecast date in ISO YYYY-MM-DD format")


class GetWeatherOutput(ToolOutput):
    weather: Optional[WeatherResult] = None


class CalculateRouteInput(ToolInput):
    origin_latitude: float = Field(ge=-90, le=90)
    origin_longitude: float = Field(ge=-180, le=180)
    destination_latitude: float = Field(ge=-90, le=90)
    destination_longitude: float = Field(ge=-180, le=180)
    travel_mode: TravelMode = TravelMode.DRIVING


class CalculateRouteOutput(ToolOutput):
    route: Optional[RouteResult] = None


class GetTripBudgetInput(ToolInput):
    trip_id: UUID


class GetTripBudgetOutput(ToolOutput):
    trip_id: Optional[UUID] = None
    total_budget: Optional[Decimal] = None
    scheduled_cost: Optional[Decimal] = None
    remaining_budget: Optional[Decimal] = None
    currency: Optional[str] = None


class SaveTripActivityInput(ToolInput):
    trip_day_id: UUID
    activity_type: str = Field(min_length=1, max_length=100)
    place_id: Optional[UUID] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    estimated_cost: Optional[Decimal] = Field(default=None, ge=0)
    order_index: Optional[int] = Field(default=None, ge=1)


class SaveTripActivityOutput(ToolOutput):
    activity: Optional[dict[str, Any]] = None


class SearchTravelKnowledgeInput(ToolInput):
    query: str = Field(
        min_length=1,
        max_length=2000,
        description=(
            "Contextual travel-knowledge question about destinations, food, customs, "
            "safety, seasonal advice, or transportation tips. Do not use for live weather, "
            "live flights, or live traffic/routes."
        ),
    )
    destination: Optional[str] = Field(default=None, max_length=255)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeCitationOut(BaseModel):
    title: str
    source: str
    destination: Optional[str] = None
    category: Optional[str] = None
    score: float = 0.0
    excerpt: str = ""
    citation: str = ""


class SearchTravelKnowledgeOutput(ToolOutput):
    results: List[KnowledgeCitationOut] = Field(default_factory=list)
