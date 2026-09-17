"""Public API schemas for trip planning. Internal LangGraph state is never exposed."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PlanTripRequest(BaseModel):
    user_request: str = Field(min_length=1, max_length=4000)
    user_id: Optional[UUID] = None
    origin: Optional[str] = Field(default=None, max_length=255)
    destination: Optional[str] = Field(default=None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    travelers: Optional[int] = Field(default=None, ge=1, le=20)
    budget: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = Field(default="VND", min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_optional_date_range(self) -> PlanTripRequest:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class CreateTripRequest(BaseModel):
    user_id: Optional[UUID] = None
    destination: str = Field(min_length=1, max_length=255)
    origin: Optional[str] = Field(default=None, max_length=255)
    start_date: date
    end_date: date
    travelers: int = Field(default=1, ge=1, le=20)
    budget: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = Field(default="VND", min_length=3, max_length=3)
    status: str = Field(default="draft", max_length=50)
    summary: Optional[str] = Field(default=None, max_length=2000)
    estimated_total_cost: Optional[Decimal] = Field(default=None, ge=0)
    itinerary: Optional[List["ItineraryDayOut"]] = None
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    weather_notes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_date_range(self) -> CreateTripRequest:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ProgressStepOut(BaseModel):
    id: str
    label: str
    status: str = Field(description="pending | running | completed | failed | skipped")


class ItineraryActivityOut(BaseModel):
    place_id: str
    name: str
    kind: str
    start_time: time
    end_time: time
    estimated_cost: Decimal
    reason: str
    travel_time_from_previous: int
    rating: Optional[float] = None
    opening_hours: Optional[str] = None


class ItineraryDayOut(BaseModel):
    day_number: int
    date: date
    theme: str = ""
    activities: List[ItineraryActivityOut] = Field(default_factory=list)


class WeatherForecastOut(BaseModel):
    destination: str
    forecast_date: date
    condition: str
    temperature_min_c: float
    temperature_max_c: float
    precipitation_probability: int = Field(ge=0, le=100)
    humidity_percent: int = Field(ge=0, le=100)
    wind_speed_kph: float = Field(ge=0)


class TripPlanResponse(BaseModel):
    """Structured planning result returned to clients."""

    trip_id: Optional[UUID] = None
    summary: str
    destination: str
    origin: Optional[str] = None
    start_date: date
    end_date: date
    travelers: int
    budget: Decimal
    currency: str
    estimated_total_cost: Decimal
    itinerary: List[ItineraryDayOut]
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    weather: List[WeatherForecastOut] = Field(default_factory=list)
    weather_notes: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    optimization_notes: List[str] = Field(default_factory=list)
    progress: List[ProgressStepOut] = Field(default_factory=list)
    is_valid: bool = True


class TripSummaryOut(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    destination: str
    origin: Optional[str] = None
    start_date: date
    end_date: date
    travelers: int
    budget: Optional[Decimal] = None
    currency: str
    status: str
    summary: Optional[str] = None
    estimated_total_cost: Optional[Decimal] = None
    created_at: datetime


class TripDetailOut(TripSummaryOut):
    itinerary: List[ItineraryDayOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    weather: List[WeatherForecastOut] = Field(default_factory=list)
    weather_notes: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)


class TripListOut(BaseModel):
    items: List[TripSummaryOut]
    total: int


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"


CreateTripRequest.model_rebuild()
