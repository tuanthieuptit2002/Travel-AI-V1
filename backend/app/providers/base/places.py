from abc import ABC, abstractmethod
from typing import List, Optional

from app.providers.models import PlaceDetails, PlaceSearchRequest, PlaceSearchResult


class PlacesProvider(ABC):
    @abstractmethod
    def search_places(self, request: PlaceSearchRequest) -> List[PlaceSearchResult]:
        """Find normalized places without leaking an upstream response shape."""

    @abstractmethod
    def get_place_details(self, place_id: str) -> Optional[PlaceDetails]:
        """Return normalized details for an opaque TripMind place identifier."""
