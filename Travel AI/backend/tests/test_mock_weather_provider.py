from datetime import date

import pytest

from app.providers.mock import MockWeatherProvider
from app.providers.models import WeatherRequest, WeatherResult


def test_weather_provider_returns_typed_seasonal_vietnam_forecast() -> None:
    provider = MockWeatherProvider()

    result = provider.get_weather(WeatherRequest(destination="Da Lat", forecast_date=date(2026, 8, 10)))

    assert isinstance(result, WeatherResult)
    assert result.condition == "scattered showers"
    assert result.temperature_max_c == 24.0
    assert result.precipitation_probability == 55


def test_weather_provider_rejects_unknown_destination() -> None:
    with pytest.raises(ValueError, match="supported Vietnam destinations"):
        MockWeatherProvider().get_weather(WeatherRequest(destination="Tokyo", forecast_date=date(2026, 1, 1)))
