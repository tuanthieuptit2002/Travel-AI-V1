from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    """Immutable models returned to application services and future agents."""

    model_config = ConfigDict(frozen=True)


class PlaceCategory(str, Enum):
    ATTRACTION = "attraction"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    LANDMARK = "landmark"


class PlaceSearchRequest(DomainModel):
    query: str = ""
    destination: Optional[str] = None
    category: Optional[PlaceCategory] = None
    limit: int = Field(default=10, ge=1, le=50)


class PlaceSearchResult(DomainModel):
    id: str
    name: str
    category: PlaceCategory
    destination: str
    description: str
    latitude: float
    longitude: float
    address: str
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    tags: List[str] = Field(default_factory=list)


class PlaceDetails(PlaceSearchResult):
    opening_hours: Optional[str] = None
    price_level: Optional[str] = None
    website: Optional[str] = None


class WeatherRequest(DomainModel):
    destination: str
    forecast_date: date


class WeatherResult(DomainModel):
    destination: str
    forecast_date: date
    condition: str
    temperature_min_c: float
    temperature_max_c: float
    precipitation_probability: int = Field(ge=0, le=100)
    humidity_percent: int = Field(ge=0, le=100)
    wind_speed_kph: float = Field(ge=0)


class TravelMode(str, Enum):
    DRIVING = "driving"
    WALKING = "walking"
    BICYCLING = "bicycling"
    TRANSIT = "transit"


class RouteRequest(DomainModel):
    origin: str
    destination: str
    travel_mode: TravelMode = TravelMode.DRIVING


class RouteResult(DomainModel):
    origin: str
    destination: str
    travel_mode: TravelMode
    distance_km: float = Field(ge=0)
    duration_minutes: int = Field(ge=0)


class FlightSearchRequest(DomainModel):
    origin: str
    destination: str
    departure_date: date
    travelers: int = Field(default=1, ge=1, le=9)
    currency: str = Field(default="VND", min_length=3, max_length=3)


class FlightSearchResult(DomainModel):
    id: str
    airline: str
    flight_number: str
    departure_at: datetime
    arrival_at: datetime
    origin: str
    destination: str
    price: float = Field(ge=0)
    currency: str
    stops: int = Field(ge=0)


class HotelSearchRequest(DomainModel):
    destination: str
    check_in: date
    check_out: date
    guests: int = Field(default=1, ge=1, le=20)
    rooms: int = Field(default=1, ge=1, le=10)
    currency: str = Field(default="VND", min_length=3, max_length=3)


class HotelSearchResult(DomainModel):
    id: str
    name: str
    destination: str
    address: str
    latitude: float
    longitude: float
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    nightly_price: float = Field(ge=0)
    currency: str
    amenities: List[str] = Field(default_factory=list)
