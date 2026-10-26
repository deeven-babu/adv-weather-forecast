"""Single source of truth for the rule-based disaster risk assessment.

The thresholds below are the existing Phase 1 business rules. They are defined
once here so the dashboard template, the weather assistant, and the JSON APIs
can never disagree about the risk level for the same weather payload.
"""

FLOOD_HIGH_PRECIPITATION = 15
FLOOD_MODERATE_PRECIPITATION = 8
FLOOD_HIGH_HUMIDITY = 80
FLOOD_MODERATE_HUMIDITY = 70

HEAT_CRITICAL_TEMPERATURE = 38
HEAT_HIGH_TEMPERATURE = 32
HEAT_MODERATE_TEMPERATURE = 28

RAIN_HIGH_PROBABILITY = 75
RAIN_MODERATE_PROBABILITY = 50

RISK_CATEGORIES = ("flood", "heatwave", "rain")

FLOOD_ADVICE = {
    "Moderate": "Elevated runoff and drainage stress likely.",
    "High": "Elevated runoff and drainage stress likely.",
    "Critical": "Elevated runoff and drainage stress likely.",
    "Low": "Conditions remain manageable at the moment.",
}
HEAT_ADVICE = {
    "Moderate": "Heat burden is elevated; stay hydrated and limit peak exposure.",
    "High": "Heat burden is elevated; stay hydrated and limit peak exposure.",
    "Critical": "Heat burden is elevated; stay hydrated and limit peak exposure.",
    "Low": "No significant heat stress indicated by current readings.",
}
RAIN_ADVICE = {
    "Moderate": "Rain intensity may affect travel and drainage.",
    "High": "Rain intensity may affect travel and drainage.",
    "Low": "Forecast precipitation remains relatively stable.",
}


def _to_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def flood_level(precipitation, humidity):
    """Flood risk level from current precipitation and humidity."""
    if precipitation >= FLOOD_HIGH_PRECIPITATION or humidity >= FLOOD_HIGH_HUMIDITY:
        return "High"
    if precipitation >= FLOOD_MODERATE_PRECIPITATION or humidity >= FLOOD_MODERATE_HUMIDITY:
        return "Moderate"
    return "Low"


def heatwave_level(temperature):
    """Heatwave risk level from the current temperature."""
    if temperature >= HEAT_CRITICAL_TEMPERATURE:
        return "Critical"
    if temperature >= HEAT_HIGH_TEMPERATURE:
        return "High"
    if temperature >= HEAT_MODERATE_TEMPERATURE:
        return "Moderate"
    return "Low"


def rain_level(rain_probability):
    """Heavy-rain risk level from the forecast rain probability for today."""
    if rain_probability >= RAIN_HIGH_PROBABILITY:
        return "High"
    if rain_probability >= RAIN_MODERATE_PROBABILITY:
        return "Moderate"
    return "Low"


def assess_risks(weather):
    """Return the flood, heatwave, and heavy-rain levels for a weather payload.

    ``weather`` is the structure produced by ``services.weather_service``. Missing
    or malformed values fall back to zero rather than raising, so a partial API
    response still renders the dashboard.
    """
    if not isinstance(weather, dict):
        return {"flood": "Low", "heatwave": "Low", "rain": "Low"}

    current = weather.get("current") or {}
    forecast = weather.get("forecast") or []
    today = forecast[0] if forecast else {}

    precipitation = _to_float(current.get("precipitation"))
    humidity = _to_float(current.get("humidity"))
    temperature = _to_float(current.get("temperature"))
    rain_probability = _to_float(today.get("rain_probability"))

    return {
        "flood": flood_level(precipitation, humidity),
        "heatwave": heatwave_level(temperature),
        "rain": rain_level(rain_probability),
    }


def risk_advice(risk):
    """Return the existing explanatory sentence for each risk category."""
    risks = risk or {}
    return {
        "flood": FLOOD_ADVICE.get(risks.get("flood", "Low"), FLOOD_ADVICE["Low"]),
        "heatwave": HEAT_ADVICE.get(risks.get("heatwave", "Low"), HEAT_ADVICE["Low"]),
        "rain": RAIN_ADVICE.get(risks.get("rain", "Low"), RAIN_ADVICE["Low"]),
    }