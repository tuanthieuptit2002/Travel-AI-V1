from abc import ABC, abstractmethod

from app.providers.models import WeatherRequest, WeatherResult


class WeatherProvider(ABC):
    @abstractmethod
    def get_weather(self, request: WeatherRequest) -> WeatherResult:
        """Return a normalized daily forecast."""
