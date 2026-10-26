"""Smart weather recommendations, alerts, and summaries based on weather data and user mode."""


# User modes
MODE_GENERAL = "general"
MODE_FARMER = "farmer"
MODE_TRAVEL = "travel"
MODE_COMMUTE = "daily_commute"
MODE_OUTDOOR = "outdoor_activity"

VALID_MODES = {MODE_GENERAL, MODE_FARMER, MODE_TRAVEL, MODE_COMMUTE, MODE_OUTDOOR}
MODE_ORDER = [MODE_GENERAL, MODE_FARMER, MODE_TRAVEL, MODE_COMMUTE, MODE_OUTDOOR]
MODE_ALIASES = {
    MODE_GENERAL: MODE_GENERAL,
    MODE_FARMER: MODE_FARMER,
    MODE_TRAVEL: MODE_TRAVEL,
    MODE_COMMUTE: MODE_COMMUTE,
    "commute": MODE_COMMUTE,
    MODE_OUTDOOR: MODE_OUTDOOR,
    "outdoor": MODE_OUTDOOR,
    "outdoor-activity": MODE_OUTDOOR,
}
DEFAULT_MODE = MODE_GENERAL


def normalize_mode(user_mode):
    """Normalize a user-provided mode to the canonical app value."""
    if user_mode is None:
        return DEFAULT_MODE
    mode_name = str(user_mode).strip().lower()
    return MODE_ALIASES.get(mode_name, None)


class WeatherAlert:
    """Represents a weather alert with type, severity, and message."""

    def __init__(self, alert_type, severity, message):
        self.type = alert_type
        self.severity = severity  # "Low", "Moderate", "High"
        self.message = message


def _get_rain_probability(weather):
    """Extract rain probability from weather data."""
    if not weather or not weather.get("forecast"):
        return 0
    return float(weather["forecast"][0].get("rain_probability", 0))


def _get_precipitation(weather):
    """Extract precipitation from weather data."""
    if not weather:
        return 0
    current = weather.get("current", {})
    return float(current.get("precipitation", 0))


def _get_temperature(weather):
    """Extract current temperature from weather data."""
    if not weather:
        return None
    current = weather.get("current", {})
    try:
        return float(current.get("temperature"))
    except (TypeError, ValueError):
        return None


def _get_wind_speed(weather):
    """Extract wind speed from weather data."""
    if not weather:
        return 0
    current = weather.get("current", {})
    return float(current.get("wind_speed", 0))


def _get_condition(weather):
    """Extract current weather condition."""
    if not weather:
        return ""
    current = weather.get("current", {})
    return str(current.get("condition", "")).lower()


def _get_humidity(weather):
    """Extract humidity from weather data."""
    if not weather:
        return 0
    current = weather.get("current", {})
    return float(current.get("humidity", 0))


def generate_weather_alerts(weather):
    """Generate weather alerts based on actual available weather data."""
    if not weather:
        return []

    alerts = []
    rain_prob = _get_rain_probability(weather)
    precipitation = _get_precipitation(weather)
    temperature = _get_temperature(weather)
    wind_speed = _get_wind_speed(weather)
    condition = _get_condition(weather)
    humidity = _get_humidity(weather)

    # Heavy Rain alert
    if precipitation >= 15:
        alerts.append(
            WeatherAlert(
                "Heavy Rain",
                "High",
                "Heavier rainfall is expected. Consider postponing non-essential outdoor activities.",
            )
        )
    elif precipitation >= 8:
        alerts.append(
            WeatherAlert(
                "Moderate Rain",
                "Moderate",
                "Rain is possible. Carry rain protection if you are going outside.",
            )
        )

    # High rain probability alert
    if rain_prob >= 75 and precipitation < 15:
        alerts.append(
            WeatherAlert(
                "High Rain Probability",
                "High",
                "High chance of rainfall is expected. Carry rain protection.",
            )
        )
    elif rain_prob >= 50 and precipitation < 8 and rain_prob < 75:
        alerts.append(
            WeatherAlert(
                "Moderate Rain Probability",
                "Moderate",
                "Rainfall is possible. Consider carrying rain protection.",
            )
        )

    # High temperature alert
    if temperature is not None:
        if temperature >= 38:
            alerts.append(
                WeatherAlert(
                    "High Temperature",
                    "High",
                    "Extremely high temperatures are expected. Stay hydrated and avoid prolonged outdoor exposure.",
                )
            )
        elif temperature >= 32:
            alerts.append(
                WeatherAlert(
                    "Warm Temperature",
                    "Moderate",
                    "Warm temperatures are expected. Use sun protection if going outside.",
                )
            )

    # Strong wind alert
    if wind_speed >= 40:
        alerts.append(
            WeatherAlert(
                "Strong Wind",
                "High",
                "Strong winds are expected. Exercise caution during outdoor activities.",
            )
        )
    elif wind_speed >= 25:
        alerts.append(
            WeatherAlert(
                "Moderate Wind",
                "Moderate",
                "Moderate winds are expected. Be cautious if traveling.",
            )
        )

    # Thunderstorm alert
    if "thunderstorm" in condition or "storm" in condition:
        alerts.append(
            WeatherAlert(
                "Thunderstorm",
                "High",
                "Thunderstorms are possible. Avoid outdoor activities and secure loose objects.",
            )
        )

    # Poor outdoor conditions alert
    if (rain_prob >= 60 and temperature is not None and temperature >= 25) or humidity >= 80:
        if not any(a.type == "Heavy Rain" for a in alerts):
            alerts.append(
                WeatherAlert(
                    "Poor Outdoor Conditions",
                    "Moderate",
                    "Weather conditions may not be favorable for outdoor activities.",
                )
            )

    # Travel caution alert
    if rain_prob >= 50 and wind_speed >= 20:
        alerts.append(
            WeatherAlert(
                "Travel Caution",
                "Moderate",
                "Rain and wind are expected. Exercise extra caution during travel.",
            )
        )

    return alerts


def generate_today_summary(weather):
    """Generate a simple AI summary of today's weather."""
    if not weather:
        return "Weather information is not available."

    location = weather.get("location", {}).get("name", "this location")
    current = weather.get("current", {})
    forecast = weather.get("forecast", [])

    temperature = _get_temperature(weather)
    condition = _get_condition(weather)
    rain_prob = _get_rain_probability(weather)
    wind_speed = _get_wind_speed(weather)
    humidity = _get_humidity(weather)

    # Build summary parts
    parts = []

    # Temperature part
    if temperature is not None:
        if temperature >= 32:
            parts.append(f"Today in {location} will be warm ({temperature:.0f}°C)")
        elif temperature >= 20:
            parts.append(f"Today in {location} will be pleasant ({temperature:.0f}°C)")
        else:
            parts.append(f"Today in {location} will be cool ({temperature:.0f}°C)")
    else:
        parts.append(f"Today in {location}")

    # Condition part
    if condition:
        parts.append(f"with {condition} conditions")
    else:
        parts.append("with mixed conditions")

    # Rain part
    if rain_prob >= 75:
        parts.append("and high likelihood of rain")
    elif rain_prob >= 50:
        parts.append("and possible rain")
    elif rain_prob >= 25:
        parts.append("and low chance of rain")
    else:
        parts.append("with low chance of rain")

    # Wind part
    if wind_speed >= 30:
        parts.append("Strong winds are expected")
    elif wind_speed >= 20:
        parts.append("Moderate winds are expected")

    summary = ". ".join(parts) + "."

    # Add recommendation based on conditions
    if rain_prob >= 50:
        summary += " Carry rain protection if going outside."
    elif temperature is not None and temperature >= 32:
        summary += " Use sun protection if going outside."
    elif temperature is not None and temperature <= 15:
        summary += " Wear appropriate layers when going outside."
    else:
        summary += " Conditions are generally suitable for outdoor activities."

    return summary


def get_recommendation_by_mode(weather, user_mode):
    """Get personalized recommendation based on user mode and weather data."""
    if user_mode not in VALID_MODES:
        user_mode = DEFAULT_MODE

    if user_mode == MODE_GENERAL:
        return _general_recommendation(weather)
    elif user_mode == MODE_FARMER:
        return _farmer_recommendation(weather)
    elif user_mode == MODE_TRAVEL:
        return _travel_recommendation(weather)
    elif user_mode == MODE_COMMUTE:
        return _commute_recommendation(weather)
    elif user_mode == MODE_OUTDOOR:
        return _outdoor_recommendation(weather)
    else:
        return _general_recommendation(weather)


def _general_recommendation(weather):
    """General mode recommendations."""
    if not weather:
        return "Weather information is not available."

    rain_prob = _get_rain_probability(weather)
    precipitation = _get_precipitation(weather)
    temperature = _get_temperature(weather)
    wind_speed = _get_wind_speed(weather)

    recommendations = []

    if rain_prob >= 75 or precipitation >= 8:
        recommendations.append("Consider carrying an umbrella or rain protection.")

    if temperature is not None:
        if temperature >= 35:
            recommendations.append("Use appropriate sun protection and stay hydrated.")
        elif temperature >= 30:
            recommendations.append("Use sun protection if spending time outdoors.")

    if wind_speed >= 30:
        recommendations.append("Strong winds are expected. Secure loose items outdoors.")

    if not recommendations:
        recommendations.append("Weather conditions appear suitable for outdoor activities.")

    return " ".join(recommendations)


def _farmer_recommendation(weather):
    """Farmer mode recommendations."""
    if not weather:
        return "Weather information is not available for farming guidance."

    rain_prob = _get_rain_probability(weather)
    precipitation = _get_precipitation(weather)
    temperature = _get_temperature(weather)
    forecast = weather.get("forecast", [])

    recommendations = []

    # Rain and irrigation guidance
    if rain_prob >= 75:
        recommendations.append(f"Heavy rainfall ({rain_prob}% probability) is expected. Plan irrigation accordingly.")
    elif rain_prob >= 50:
        recommendations.append(f"Rainfall ({rain_prob}% probability) is expected. Monitor crop conditions.")
    elif precipitation >= 5:
        recommendations.append("Adequate precipitation detected. Check irrigation needs.")
    else:
        recommendations.append("No significant rainfall expected. Consider irrigation planning.")

    # Temperature guidance
    if temperature is not None:
        if temperature >= 35:
            recommendations.append("High temperatures expected. Monitor crops for heat stress.")
        elif temperature >= 28:
            recommendations.append("Warm conditions expected. Ensure adequate water supply for crops.")

    # Activity suggestion
    if rain_prob <= 30 and temperature is not None and 20 <= temperature <= 30:
        recommendations.append("Weather conditions may be favorable for field activities.")
    elif rain_prob >= 60:
        recommendations.append("Defer non-critical field activities due to expected rainfall.")

    return " ".join(recommendations) if recommendations else "Monitor weather conditions for farming decisions."


def _travel_recommendation(weather):
    """Travel mode recommendations."""
    if not weather:
        return "Weather information is not available for travel planning."

    rain_prob = _get_rain_probability(weather)
    precipitation = _get_precipitation(weather)
    temperature = _get_temperature(weather)
    wind_speed = _get_wind_speed(weather)
    condition = _get_condition(weather)

    recommendations = []

    if precipitation >= 10 or rain_prob >= 70:
        recommendations.append("Heavy rainfall is possible. Plan extra travel time and carry rain protection.")
    elif rain_prob >= 50:
        recommendations.append("Rain is expected during part of the day. Carry rain protection.")

    if wind_speed >= 35:
        recommendations.append("Strong winds are expected. Exercise additional caution during outdoor travel.")

    if "thunderstorm" in condition or "storm" in condition:
        recommendations.append("Thunderstorms possible. Consider rescheduling outdoor travel if possible.")

    if temperature is not None and temperature >= 35:
        recommendations.append("Extreme heat expected. Ensure adequate hydration during travel.")

    if not recommendations:
        recommendations.append("Weather conditions appear suitable for travel plans.")

    return " ".join(recommendations)


def _commute_recommendation(weather):
    """Daily commute mode recommendations."""
    if not weather:
        return "Weather information is not available for commute planning."

    rain_prob = _get_rain_probability(weather)
    precipitation = _get_precipitation(weather)
    temperature = _get_temperature(weather)
    wind_speed = _get_wind_speed(weather)

    recommendations = []

    if rain_prob >= 50 or precipitation >= 5:
        recommendations.append("Rain is possible during the commute. Consider carrying an umbrella.")

    if wind_speed >= 25:
        recommendations.append("Moderate to strong winds expected. Allow extra time for commute.")

    if temperature is not None:
        if temperature >= 35:
            recommendations.append("Extreme heat expected. Stay hydrated during commute.")
        elif temperature <= 10:
            recommendations.append("Cold conditions expected. Dress warmly for commute.")

    if not recommendations:
        recommendations.append("Commute conditions appear normal. No special preparations needed.")

    return " ".join(recommendations)


def _outdoor_recommendation(weather):
    """Outdoor activity mode recommendations."""
    if not weather:
        return "Weather information is not available for activity planning."

    rain_prob = _get_rain_probability(weather)
    precipitation = _get_precipitation(weather)
    temperature = _get_temperature(weather)
    wind_speed = _get_wind_speed(weather)
    condition = _get_condition(weather)

    recommendations = []

    if rain_prob >= 70:
        recommendations.append("High chance of rain. Outdoor activities may be unfavorable.")
    elif rain_prob >= 50:
        recommendations.append("Moderate chance of rain. Be prepared for possible showers.")

    if "thunderstorm" in condition or "storm" in condition:
        recommendations.append("Thunderstorms possible. Avoid outdoor activities.")

    if wind_speed >= 35:
        recommendations.append("Strong winds expected. Avoid exposure during outdoor activities.")

    if temperature is not None:
        if temperature >= 38:
            recommendations.append("Extreme heat. Outdoor activities not recommended.")
        elif temperature >= 32:
            recommendations.append("High temperature. Limit outdoor activity duration and use sun protection.")
        elif temperature <= 5:
            recommendations.append("Cold conditions. Dress warmly and limit outdoor exposure time.")

    if not recommendations or (
        rain_prob <= 30 and precipitation <= 2 and (temperature is None or 15 <= temperature <= 30) and wind_speed < 20
    ):
        recommendations.append("Weather conditions appear suitable for outdoor activities.")

    return " ".join(recommendations)


def _window_label(hour):
    """Map an hour of day to one of the window labels the translation layer knows."""
    if hour is None:
        return "late morning"
    if hour <= 8:
        return "early morning"
    if hour <= 11:
        return "late morning"
    if hour <= 14:
        return "midday"
    return "early afternoon"


def _hour_score(record):
    """Lower is better. Balances rain, precipitation, temperature, and wind."""
    rain_penalty = float(record.get("rain_probability") or 0) * 1.0
    precipitation_penalty = float(record.get("precipitation") or 0) * 12.0
    temperature = record.get("temperature")
    if temperature is None:
        temperature_penalty = 0.0
    else:
        temperature_penalty = abs(float(temperature) - 26.0) * 1.5
    wind_speed = float(record.get("wind_speed") or 0)
    wind_penalty = max(0.0, wind_speed - 20.0) * 0.5
    return rain_penalty + precipitation_penalty + temperature_penalty + wind_penalty


def get_best_time_window(weather):
    """Identify the safest or most comfortable time window for outdoor activity.

    Uses the hourly Open-Meteo block. Hourly data is optional; when it is absent
    the function returns the existing friendly fallback instead of raising.
    """
    if not weather:
        return "Weather information is not available to suggest a best time window."

    hourly = [record for record in (weather.get("hourly") or []) if isinstance(record, dict)]
    if not hourly:
        return "Detailed hourly forecast is not available. Check the 7-day forecast for better planning."

    location = weather.get("location") or {}
    location_name = location.get("name", "this location") if isinstance(location, dict) else "this location"

    best_index = min(range(len(hourly)), key=lambda index: _hour_score(hourly[index]))
    window_records = hourly[best_index : best_index + 3] or [hourly[best_index]]

    temperatures = [
        float(record["temperature"])
        for record in window_records
        if record.get("temperature") is not None
    ]
    if not temperatures:
        return "Detailed hourly forecast is not available. Check the 7-day forecast for better planning."

    rain_probability = sum(
        float(record.get("rain_probability") or 0) for record in window_records
    ) / len(window_records)
    minimum_temperature = min(temperatures)
    maximum_temperature = max(temperatures)
    window = _window_label(hourly[best_index].get("hour"))

    return (
        f"Best time for outdoor plans in {location_name} is {window}, when rainfall risk is lower "
        f"and temperatures are more comfortable ({minimum_temperature:.0f}°C to {maximum_temperature:.0f}°C, "
        f"{rain_probability:.0f}% rain chance)."
    )


def add_mode_context_to_question(question, user_mode):
    """Add mode-aware guidance to a question so the assistant can respond appropriately."""
    mode_name = normalize_mode(user_mode)
    mode_context = {
        MODE_FARMER: "crop, irrigation, and field timing",
        MODE_TRAVEL: "travel timing and route safety",
        MODE_COMMUTE: "commute timing and rain readiness",
        MODE_OUTDOOR: "outdoor safety and activity planning",
        MODE_GENERAL: "general comfort and safety",
    }
    question_text = str(question or "").strip()
    focus = mode_context.get(mode_name, mode_context[MODE_GENERAL])
    if not question_text:
        return f"{mode_name}-focused context: {focus}"
    return f"{question_text} (mode: {mode_name}; focus on {focus})"
