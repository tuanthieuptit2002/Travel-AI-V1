from abc import ABC, abstractmethod

from app.providers.models import RouteRequest, RouteResult


class RouteProvider(ABC):
    @abstractmethod
    def calculate_route(self, request: RouteRequest) -> RouteResult:
        """Calculate distance and duration using TripMind route terminology."""
