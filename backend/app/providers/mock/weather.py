from typing import Dict, Tuple

from app.providers.base.weather import WeatherProvider
from app.providers.mock.catalog import normalize_destination
from app.providers.models import WeatherRequest, WeatherResult


class MockWeatherProvider(WeatherProvider):
    """Predictable seasonal Vietnam forecasts suitable for development only."""

    _CLIMATES: Dict[str, Tuple[float, float, int, int]] = {
        "hanoi": (18.0, 27.0, 35, 70),
        "da nang": (23.0, 31.0, 30, 76),
        "hoi an": (23.0, 30.0, 35, 78),
        "ho chi minh city": (25.0, 33.0, 40, 75),
        "da lat": (14.0, 24.0, 35, 78),
        "nha trang": (24.0, 32.0, 25, 74),
        "phu quoc": (25.0, 32.0, 45, 80),
        "ha long": (19.0, 28.0, 35, 76),
    }

    def get_weather(self, request: WeatherRequest) -> WeatherResult:
        key = normalize_destination(request.destination)
        if key not in self._CLIMATES:
            raise ValueError("Mock weather is available only for supported Vietnam destinations.")

        low, high, rain, humidity = self._CLIMATES[key]
        rainy_season = request.forecast_date.month in (6, 7, 8, 9, 10)
        precipitation = min(95, rain + 20) if rainy_season else rain
        condition = "scattered showers" if precipitation >= 50 else "partly cloudy"
        return WeatherResult(
            destination=request.destination.strip(), forecast_date=request.forecast_date, condition=condition,
            temperature_min_c=low, temperature_max_c=high, precipitation_probability=precipitation,
            humidity_percent=humidity, wind_speed_kph=14.0 if rainy_season else 9.0,
        )
