"""Phase 9 intent, explainability, personalization, and scenario helpers."""

from ml.preprocessing import FEATURE_COLUMNS
from services.recommendations import MODE_COMMUTE, MODE_FARMER, MODE_GENERAL, MODE_OUTDOOR, MODE_TRAVEL, normalize_mode


INTENTS = {
    "current_weather",
    "tomorrow_weather",
    "forecast",
    "rain",
    "temperature",
    "humidity",
    "wind",
    "precipitation",
    "risk",
    "farmer_advice",
    "travel_advice",
    "commute_advice",
    "outdoor_advice",
    "best_time",
    "ml_prediction",
    "ml_explanation",
    "recommendation",
    "unsupported",
}


def detect_intent(question, user_mode=MODE_GENERAL):
    """Classify common weather requests without adding an external NLP dependency."""
    text = str(question or "").strip().lower()
    if not text:
        return "unsupported"
    if any(word in text for word in ("why", "explain", "feature importance", "model factor", "ఎందుకు", "వివరించ", "ఎలా అంచనా", "क्यों", "समझाएं", "कैसे भविष्यवाणी")):
        return "ml_explanation"
    if any(word in text for word in ("ml prediction", "model predict", "rain prediction", "predict rain", "మోడల్", "అంచనా", "मॉडल", "भविष्यवाणी")):
        return "ml_prediction"
    if any(word in text for word in ("best time", "lower-risk", "lower risk", "safest time", "comfortable time", "మంచి సమయం", "సురక్షిత సమయం", "सबसे अच्छा समय", "सुरक्षित समय")):
        return "best_time"
    if any(word in text for word in ("farmer", "farming", "farm", "irrigate", "irrigation", "crop", "పొలం", "పంట", "నీరు పెట్ట", "నీటిపారుదల", "రైతు", "खेत", "फसल", "पानी देना", "सिंचाई", "किसान")):
        return "farmer_advice"
    if any(word in text for word in ("commute", "office", "work", "school", "కామ్యూట్", "ఆఫీస్", "పాఠశాల", "आवागमन", "ऑफिस", "स्कूल", "काम पर")):
        return "commute_advice"
    if any(word in text for word in ("travel", "trip", "journey", "ప్రయాణం", "యాత్ర", "यात्रा", "सफ़र")):
        return "travel_advice"
    if any(word in text for word in ("cricket", "sports", "play", "outdoor", "outside", "బయట", "క్రికెట్", "ఆడ", "बाहर", "क्रिकेट", "खेल")):
        return "outdoor_advice"
    if any(word in text for word in ("risk", "danger", "disaster", "flood", "heatwave", "heat wave", "ప్రమాదం", "వరద", "విపత్తు", "जोखिम", "बाढ़", "आपदा")):
        return "risk"
    if any(word in text for word in ("tomorrow", "next day", "రేపు", "कल")):
        return "tomorrow_weather"
    if any(word in text for word in ("forecast", "next week", "coming days", "seven day", "7 day", "వాతావరణ అంచనా", "తదుపరి రోజులు", "पूर्वानुमान", "अगले दिन")):
        return "forecast"
    if any(word in text for word in ("rain", "rainfall", "shower", "umbrella", "వర్షం", "జల్లు", "గొడుగు", "बारिश", "बौछार", "छाता")):
        return "rain"
    if any(word in text for word in ("temperature", "hot", "cold", "ఉష్ణోగ్రత", "వేడి", "చలి", "तापमान", "गर्मी", "ठंड")):
        return "temperature"
    if any(word in text for word in ("humidity", "humid", "తేమ", "नमी")):
        return "humidity"
    if any(word in text for word in ("wind", "గాలి", "हवा")):
        return "wind"
    if any(word in text for word in ("precipitation", "వర్షపాతం", "वर्षा")):
        return "precipitation"
    if any(word in text for word in ("weather", "condition", "today", "వాతావరణం", "పరిస్థితి", "ఈరోజు", "నేడు", "मौसम", "स्थिति", "आज")):
        return "current_weather"
    return "recommendation" if normalize_mode(user_mode) else "unsupported"


def available_model_features(rain_prediction):
    """Return only feature names actually exposed by the persisted model output."""
    factors = (rain_prediction or {}).get("factors", [])
    available = {str(factor.get("name", "")).lower().replace(" ", "_") for factor in factors}
    return [feature for feature in FEATURE_COLUMNS if feature in available]


def explain_prediction(rain_prediction):
    """Build a factual explanation from persisted-model feature importances."""
    if not rain_prediction:
        return {"available": False, "factors": [], "probability_percent": None}
    factors = rain_prediction.get("factors", [])
    return {
        "available": bool(factors),
        "factors": factors,
        "probability_percent": rain_prediction.get("probability_percent"),
        "model_name": rain_prediction.get("model_name"),
        "feature_columns": FEATURE_COLUMNS,
    }


def intelligence_context(weather, user_mode):
    """Return structured facts for a mode-aware, non-technical weather explanation."""
    current = (weather or {}).get("current", {})
    forecast = (weather or {}).get("forecast", [])
    rain_probability = forecast[0].get("rain_probability", 0) if forecast else 0
    temperature = current.get("temperature")
    humidity = current.get("humidity")
    mode = normalize_mode(user_mode)
    if mode == MODE_FARMER:
        recommendation = "Monitor rainfall and irrigation needs before field work."
    elif mode == MODE_TRAVEL:
        recommendation = "Allow flexibility for rain or wind during travel."
    elif mode == MODE_COMMUTE:
        recommendation = "Check rain readiness and allow extra commute time if needed."
    elif mode == MODE_OUTDOOR:
        recommendation = "Use the rain and heat signals to plan outdoor activity safely."
    else:
        recommendation = "Use the current conditions and forecast to plan your day."
    return {
        "condition": current.get("condition", "Unknown conditions"),
        "temperature": temperature,
        "humidity": humidity,
        "rain_probability": rain_probability,
        "mode": mode,
        "recommendation": recommendation,
    }


def simulate_scenario(scenario, weather):
    """Evaluate a clearly labeled what-if scenario without modifying live weather."""
    text = str(scenario or "").strip().lower()
    if not text:
        raise ValueError("Enter a what-if scenario.")
    if "rain" in text:
        value = 70
        scenario_name = "rainfall probability becomes 70%"
        impact = "Higher rain probability may disrupt outdoor activities, farming schedules, travel, and commutes."
    elif "temperature" in text or "°c" in text or "degree" in text:
        digits = "".join(character for character in text if character.isdigit())
        if not digits:
            raise ValueError("Include a temperature value in the scenario.")
        value = int(digits)
        scenario_name = f"temperature reaches {value}°C"
        impact = "Higher temperature may increase heat stress and make prolonged outdoor activity less comfortable."
    else:
        raise ValueError("Use a rainfall or temperature what-if scenario.")
    return {
        "label": "Simulation / What-if scenario — not an actual forecast.",
        "scenario": scenario_name,
        "value": value,
        "impact": impact,
        "location": (weather or {}).get("location", {}),
    }