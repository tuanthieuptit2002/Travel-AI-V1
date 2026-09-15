from abc import ABC, abstractmethod
from typing import List

from app.providers.models import HotelSearchRequest, HotelSearchResult


class HotelProvider(ABC):
    @abstractmethod
    def search_hotels(self, request: HotelSearchRequest) -> List[HotelSearchResult]:
        """Search hotels and return normalized offer summaries."""
