"""Structured models for parsed requests and grounded itineraries."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ActivityKind(str, Enum):
    ACTIVITY = "activity"
    RESTAURANT = "restaurant"


class ParsedTravelRequest(BaseModel):
    """Intent extracted from natural language. Facts still come from tools later."""

    destination: str
    origin: Optional[str] = None
    start_date: date
    end_date: date
    travelers: int = Field(ge=1, le=20)
    budget_total: Decimal = Field(ge=0)
    budget_per_person: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = "VND"
    preferences: List[str] = Field(default_factory=list)
    nights: Optional[int] = Field(default=None, ge=0)
    days: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_date_range(self) -> ParsedTravelRequest:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ItineraryActivity(BaseModel):
    place_id: str
    name: str
    kind: ActivityKind
    start_time: time
    end_time: time
    estimated_cost: Decimal = Field(ge=0)
    reason: str
    travel_time_from_previous: int = Field(ge=0, description="Minutes from the previous stop")
    latitude: float
    longitude: float
    rating: Optional[float] = None
    opening_hours: Optional[str] = None


class ItineraryDay(BaseModel):
    day_number: int = Field(ge=1)
    date: date
    theme: str = ""
    activities: List[ItineraryActivity] = Field(default_factory=list)


class TripItinerary(BaseModel):
    destination: str
    origin: Optional[str] = None
    start_date: date
    end_date: date
    travelers: int
    total_budget: Decimal
    currency: str = "VND"
    preferences: List[str] = Field(default_factory=list)
    days: List[ItineraryDay] = Field(default_factory=list)
    estimated_total_cost: Decimal = Field(default=Decimal("0"), ge=0)
    summary: str = ""


class WeatherForecast(BaseModel):
    """Weather data retained from the provider for clients, not only a text note."""

    destination: str
    forecast_date: date
    condition: str
    temperature_min_c: float
    temperature_max_c: float
    precipitation_probability: int = Field(ge=0, le=100)
    humidity_percent: int = Field(ge=0, le=100)
    wind_speed_kph: float = Field(ge=0)


class FinalTravelResponse(BaseModel):
    headline: str
    overview: str
    itinerary: TripItinerary
    weather: List[WeatherForecast] = Field(default_factory=list)
    weather_notes: List[str] = Field(default_factory=list)
    budget_notes: List[str] = Field(default_factory=list)
    knowledge_notes: List[str] = Field(default_factory=list)
    optimization_notes: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    is_valid: bool = True
