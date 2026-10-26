from datetime import datetime

import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10


class WeatherServiceError(Exception):
    """Expected error raised when weather data cannot be retrieved or processed."""


WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}


def _get_json(url, params):
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        raise WeatherServiceError("The weather service is temporarily unavailable.") from error


def geocode_city(city):
    city = city.strip()
    if not city:
        raise WeatherServiceError("Enter a city or town to search.")

    data = _get_json(GEOCODING_URL, {"name": city, "count": 1, "language": "en", "format": "json"})
    results = data.get("results")
    if not results:
        raise WeatherServiceError("We could not find that city or town.")

    result = results[0]
    if not all(key in result for key in ("latitude", "longitude", "name")):
        raise WeatherServiceError("The location response was incomplete.")
    return {
        "name": result["name"],
        "country": result.get("country", ""),
        "latitude": result["latitude"],
        "longitude": result["longitude"],
    }


def reverse_geocode(latitude, longitude):
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 10},
            headers={"User-Agent": "WeatherAI/1.0 (college-weather-dashboard)"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WeatherServiceError("We could not identify that map location.") from error

    address = data.get("address", {})
    name = address.get("city") or address.get("town") or address.get("village") or address.get("county")
    if not name:
        raise WeatherServiceError("We could not identify that map location.")
    return {"name": name, "country": address.get("country", ""), "latitude": latitude, "longitude": longitude}


def _build_hourly(data):
    """Normalize the Open-Meteo hourly block into a list of usable hour records.

    Hourly data is optional. Any missing or malformed field is skipped so a
    partial response never breaks the current-conditions and forecast output.
    """
    hourly = data.get("hourly")
    if not isinstance(hourly, dict):
        return []
    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        return []

    def series(name):
        values = hourly.get(name)
        return values if isinstance(values, list) else []

    temperatures = series("temperature_2m")
    rain_probabilities = series("precipitation_probability")
    precipitation_values = series("precipitation")
    wind_speeds = series("wind_speed_10m")

    def at(values, index):
        if index >= len(values):
            return None
        value = values[index]
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    records = []
    for index, time_text in enumerate(times):
        temperature = at(temperatures, index)
        rain_probability = at(rain_probabilities, index)
        precipitation = at(precipitation_values, index)
        wind_speed = at(wind_speeds, index)
        if None in (temperature, rain_probability, precipitation):
            continue
        hour = None
        try:
            hour = datetime.fromisoformat(time_text).hour
        except (TypeError, ValueError):
            hour = None
        records.append(
            {
                "time": time_text,
                "hour": hour,
                "temperature": temperature,
                "rain_probability": rain_probability,
                "precipitation": precipitation,
                "wind_speed": wind_speed if wind_speed is not None else 0.0,
            }
        )
    return records


def _get_weather_for_location(location):
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,sunrise,sunset",
            "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m",
            "forecast_days": 7,
            "forecast_hours": 48,
            "timezone": "auto",
        },
    )
    current = data.get("current")
    daily = data.get("daily")
    if not current or not daily or not daily.get("time"):
        raise WeatherServiceError("The weather response was incomplete.")

    def current_value(key):
        if key not in current or current[key] is None:
            raise WeatherServiceError("The weather response was incomplete.")
        return current[key]

    forecast = []
    for index, date_text in enumerate(daily["time"][:7]):
        try:
            forecast.append(
                {
                    "date": datetime.fromisoformat(date_text).strftime("%a, %b %d"),
                    "condition": WEATHER_CODES.get(daily["weather_code"][index], "Unknown conditions"),
                    "temperature_max": daily["temperature_2m_max"][index],
                    "temperature_min": daily["temperature_2m_min"][index],
                    "rain_probability": daily["precipitation_probability_max"][index],
                    "precipitation": daily["precipitation_sum"][index],
                }
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise WeatherServiceError("The forecast response was incomplete.") from error

    return {
        "location": location,
        "current": {
            "temperature": current_value("temperature_2m"),
            "feels_like": current_value("apparent_temperature"),
            "humidity": current_value("relative_humidity_2m"),
            "wind_speed": current_value("wind_speed_10m"),
            "wind_direction": current_value("wind_direction_10m"),
            "precipitation": current_value("precipitation"),
            "pressure": current_value("pressure_msl"),
            "condition": WEATHER_CODES.get(current_value("weather_code"), "Unknown conditions"),
            "sunrise": daily.get("sunrise", [""])[0],
            "sunset": daily.get("sunset", [""])[0],
        },
        "forecast": forecast,
        "hourly": _build_hourly(data),
        "units": {"temperature": "°C", "wind_speed": "km/h", "precipitation": "mm", "pressure": "hPa"},
    }


def get_weather(city):
    return _get_weather_for_location(geocode_city(city))


def get_weather_by_coordinates(latitude, longitude, location=None):
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise WeatherServiceError("The selected map coordinates are invalid.")
    return _get_weather_for_location(location or reverse_geocode(latitude, longitude))