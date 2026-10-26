from unittest.mock import Mock, patch

import pytest
import requests

from services.weather_service import WeatherServiceError, get_weather, geocode_city


GEOCODE_RESULT = {"results": [{"name": "Chennai", "country": "India", "latitude": 13.08, "longitude": 80.27}]}
FORECAST_RESULT = {
    "current": {"temperature_2m": 32, "relative_humidity_2m": 78, "apparent_temperature": 36, "precipitation": 1.2, "weather_code": 2, "wind_speed_10m": 14, "wind_direction_10m": 180, "pressure_msl": 1005},
    "daily": {"time": ["2026-08-25"], "weather_code": [2], "temperature_2m_max": [33], "temperature_2m_min": [27], "precipitation_probability_max": [70], "precipitation_sum": [3.5], "sunrise": ["06:00"], "sunset": ["18:30"]},
}


def response_with(data):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = data
    return response


@patch("services.weather_service.requests.get")
def test_city_search_returns_coordinates(mock_get):
    mock_get.return_value = response_with(GEOCODE_RESULT)
    assert geocode_city("Chennai")["latitude"] == 13.08


@patch("services.weather_service.requests.get")
def test_weather_response_is_processed(mock_get):
    mock_get.side_effect = [response_with(GEOCODE_RESULT), response_with(FORECAST_RESULT)]
    weather = get_weather("Chennai")
    assert weather["current"]["condition"] == "Partly cloudy"
    assert weather["forecast"][0]["rain_probability"] == 70


@patch("services.weather_service.requests.get")
def test_invalid_city_is_friendly_error(mock_get):
    mock_get.return_value = response_with({"results": []})
    with pytest.raises(WeatherServiceError, match="could not find"):
        geocode_city("Not A Real Place")


@patch("services.weather_service.requests.get")
def test_api_failure_is_friendly_error(mock_get):
    mock_get.side_effect = requests.RequestException("offline")
    with pytest.raises(WeatherServiceError, match="temporarily unavailable"):
        geocode_city("Chennai")