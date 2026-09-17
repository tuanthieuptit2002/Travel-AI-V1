from abc import ABC, abstractmethod
from typing import List

from app.providers.models import FlightSearchRequest, FlightSearchResult


class FlightProvider(ABC):
    @abstractmethod
    def search_flights(self, request: FlightSearchRequest) -> List[FlightSearchResult]:
        """Search flights and return normalized offer summaries."""
