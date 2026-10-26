import re

from services.recommendations import (
    MODE_COMMUTE,
    MODE_FARMER,
    MODE_GENERAL,
    MODE_OUTDOOR,
    MODE_TRAVEL,
    get_best_time_window,
    get_recommendation_by_mode,
    normalize_mode,
)
from services.phase9 import detect_intent
from services.risk import assess_risks


LOCATION_PATTERNS = (
    re.compile(r"\b(?:weather|forecast|conditions?|temperature|rain|rainfall)\s+(?:in|at|for)\s+([^?!.,]+)", re.IGNORECASE),
    re.compile(r"\b(?:in|at)\s+([^?!.,]+)\s*\??$", re.IGNORECASE),
)


def explicit_location(question):
    """Return a location only when the question contains a weather location phrase."""
    for pattern in LOCATION_PATTERNS:
        match = pattern.search(question.strip())
        if match:
            location = match.group(1).strip()
            if location.lower() not in {"the weather", "outdoor activities", "the weekend"}:
                return location
    return None


def _tomorrow_forecast(forecast):
    return forecast[1] if len(forecast) > 1 else None


def _risk_levels(weather):
    """Return flood, heatwave, and rain levels from the centralized risk rules."""
    risks = assess_risks(weather)
    return risks["flood"], risks["heatwave"], risks["rain"]


def _mode_note(user_mode):
    """Translate a user mode into a short decision context for the assistant."""
    normalized_mode = normalize_mode(user_mode)
    mode_notes = {
        MODE_GENERAL: "For a general plan,",
        MODE_FARMER: "For farm planning,",
        MODE_TRAVEL: "For travel planning,",
        MODE_COMMUTE: "For commute planning,",
        MODE_OUTDOOR: "For outdoor activity planning,",
    }
    return mode_notes.get(normalized_mode, "For planning,")


def answer_question(question, weather, rain_prediction, user_mode=MODE_GENERAL):
    """Answer supported questions using only the supplied live weather payload."""
    normalized = question.strip().lower()
    if not normalized:
        return "Please ask a weather question so I can check the selected location."

    location = weather["location"]["name"]
    current = weather["current"]
    forecast = weather["forecast"]
    feels_like = current.get("feels_like", current.get("temperature", 0))
    flood, heat, rain = _risk_levels(weather)
    rain_probability = forecast[0]["rain_probability"] if forecast else None
    tomorrow = _tomorrow_forecast(forecast)
    intent = detect_intent(question, user_mode)
    prediction_text = ""
    mode_note = _mode_note(user_mode)
    if rain_prediction:
        prediction_text = (
            f" The separate ML rainfall prediction is {rain_prediction.get('prediction', 'available')} "
            f"with {rain_prediction['probability_percent']}% probability from the "
            f"{rain_prediction.get('model_name', 'the persisted model')} model; it is not an official forecast."
        )

    if intent == "farmer_advice":
        return f"{mode_note} {get_recommendation_by_mode(weather, MODE_FARMER)}"
    if intent == "travel_advice":
        return f"{mode_note} {get_recommendation_by_mode(weather, MODE_TRAVEL)}"
    if intent == "commute_advice":
        return f"{mode_note} {get_recommendation_by_mode(weather, MODE_COMMUTE)}"
    if intent == "outdoor_advice":
        if "best" in normalized or "time" in normalized or "evening" in normalized:
            return f"{mode_note} {get_best_time_window(weather)}"
        return f"{mode_note} {get_recommendation_by_mode(weather, MODE_OUTDOOR)}"

    if intent == "tomorrow_weather":
        if tomorrow is None:
            return f"Tomorrow’s forecast is not available for {location}."
        answer = (
            f"Tomorrow in {location}: {tomorrow['condition']}, temperatures from "
            f"{tomorrow['temperature_min']} to {tomorrow['temperature_max']}°C, "
            f"rain probability {tomorrow['rain_probability']}%, and precipitation "
            f"{tomorrow['precipitation']} mm."
        )
        answer = answer + prediction_text if "rain" in normalized else answer
        return f"{mode_note} {answer}"
    if intent == "current_weather":
        return (
            f"{mode_note} Today in {location}: {current['condition']}, {current['temperature']}°C "
            f"(feels like {feels_like}°C), humidity {current['humidity']}%, "
            f"wind {current['wind_speed']} km/h, and precipitation {current['precipitation']} mm."
        )

    if intent == "rain" and any(phrase in normalized for phrase in ("umbrella", "outdoor", "outside", "outdoor activities", "outdoor work", "sports event")):
        if tomorrow and "tomorrow" in normalized:
            day = tomorrow
            day_label = "Tomorrow"
        else:
            day = forecast[0] if forecast else None
            day_label = "Today"
        if day is None:
            return f"I cannot assess outdoor conditions for {location} because the forecast is unavailable."
        rain_advice = "Carry an umbrella and have an indoor option" if day["rain_probability"] >= 50 or day["precipitation"] > 0 else "An umbrella is unlikely to be needed"
        heat_advice = "take heat precautions and plan breaks" if float(day["temperature_max"]) >= 32 else "conditions look moderate for outdoor plans"
        return f"{mode_note} {day_label} in {location}, {rain_advice}; {heat_advice}. Check local official guidance if conditions become severe."

    if intent in ("ml_explanation", "ml_prediction"):
        factors = ", ".join(factor["name"] for factor in (rain_prediction or {}).get("factors", []))
        if factors:
            return f"The ML rainfall estimate for {location} is based on the supplied weather inputs. The model's leading available factors are {factors}.{prediction_text}"
        return f"The available weather and model inputs are used to estimate rainfall for {location}; feature importance details are not available for this prediction.{prediction_text}"

    if intent == "risk":
        return (
            f"{mode_note} For {location}, the current rule-based risk outlook is: flood {flood}, "
            f"heatwave {heat}, and heavy rain {rain}. This is an indication from the "
            "available weather readings, not an official emergency warning."
        )
    if intent == "rain" and any(word in normalized for word in ("rain probability", "rain chance", "chance of rain", "rainfall probability")):
        if rain_probability is None:
            return f"Rain probability is not available for {location} in the current forecast."
        return f"Today’s rain probability for {location} is {rain_probability}%." + prediction_text
    if intent == "forecast":
        if not forecast:
            return f"The forecast is not available for {location}."
        days = "; ".join(f"{day['date']}: {day['condition']}, {day['temperature_min']} to {day['temperature_max']}°C, rain {day['rain_probability']}%" for day in forecast)
        return f"Here is the available seven-day forecast for {location}: {days}."
    if intent in ("temperature", "humidity", "wind", "precipitation", "rain"):
        return (
            f"Current conditions in {location}: {current['condition']}, {current['temperature']}°C "
            f"(feels like {feels_like}°C), humidity {current['humidity']}%, "
            f"wind {current['wind_speed']} km/h, and precipitation {current['precipitation']} mm."
        )
    return "I can answer about current conditions, the seven-day forecast, rain probability, or the available disaster-risk indicators."
