"""Phase 3 personalization: mode-aware guidance combining every signal.

The existing Phase 1 ``services.recommendations.get_recommendation_by_mode`` is
left completely untouched. This module *layers* the Phase 2/3 context on top:

* the ML rainfall estimate
* the rule-based disaster risk levels
* the user's active alerts
* the user's saved preferences (mode, language, location)

Everything here is informational. No medical, legal, or emergency claim is ever
produced, and every number comes from the application's own weather data.
"""

from __future__ import annotations

from typing import Any, Optional

from services.recommendations import (
    MODE_COMMUTE,
    MODE_FARMER,
    MODE_GENERAL,
    MODE_OUTDOOR,
    MODE_TRAVEL,
    normalize_mode,
)
from services.risk import assess_risks

#: The five supported weather modes, in the order the UI presents them.
SUPPORTED_MODES = (MODE_GENERAL, MODE_FARMER, MODE_TRAVEL, MODE_COMMUTE, MODE_OUTDOOR)

ELEVATED = {"Moderate", "High", "Critical"}


def to_number(value) -> float:
    """Return a float for a value that may be missing or non-numeric."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def personalization_factors(weather, rain_prediction=None, user_mode=MODE_GENERAL) -> dict[str, Any]:
    """Collect the signals used to build personalized guidance.

    Risk levels come from ``services.risk.assess_risks`` so the thresholds stay
    defined in exactly one place.
    """
    current = (weather or {}).get("current") or {}
    forecast = (weather or {}).get("forecast") or []
    today = forecast[0] if forecast else {}
    risks = assess_risks(weather) if weather else {"flood": "Low", "heatwave": "Low", "rain": "Low"}

    ml_probability = None
    if rain_prediction:
        ml_probability = rain_prediction.get("probability_percent")
        if ml_probability is None and rain_prediction.get("probability") is not None:
            ml_probability = round(to_float(rain_prediction.get("probability")) * 100)

    return {
        "mode": normalize_mode(user_mode),
        "condition": current.get("condition", ""),
        "temperature": current.get("temperature"),
        "humidity": current.get("humidity"),
        "wind_speed": current.get("wind_speed"),
        "precipitation": current.get("precipitation"),
        "rain_probability": today.get("rain_probability"),
        "ml_probability": ml_probability,
        "ml_prediction": (rain_prediction or {}).get("prediction"),
        "risks": risks,
        "highest_risk": max(risks.values()) if risks else "Low",
        "risk_categories_elevated": [name for name, level in risks.items() if level in ELEVATED],
    }


def _sentence(parts) -> str:
    text = " ".join(part for part in parts if part)
    return text[:1].upper() + text[1:] if text else ""


def _mode_factors(mode, factors) -> list[str]:
    """Return the mode-relevant factor sentences, highest signal first."""
    risks = factors["risks"]
    rain = factors["rain_probability"]
    temperature = factors["temperature"]
    wind = factors["wind_speed"]
    rain_text = f"Rain probability today is {rain}%." if rain is not None else "Rain probability is unavailable."
    sentences: list[str] = []

    if mode == MODE_FARMER:
        sentences.append(rain_text)
        if factors["ml_probability"] is not None:
            sentences.append(f"The ML rainfall estimate is {factors['ml_probability']}%.")
        if risks.get("flood") in ELEVATED:
            sentences.append(f"Flood risk is {risks['flood'].lower()}, so drainage and field access need attention.")
        if temperature is not None and to_number(temperature) >= 32:
            sentences.append("Field heat exposure is high, so schedule heavier work in cooler hours.")
        if risks.get("heatwave") in {"High", "Critical"}:
            sentences.append("Heatwave conditions are present; irrigate early and avoid midday fieldwork.")
    elif mode == MODE_TRAVEL:
        sentences.append(rain_text)
        if wind is not None and to_number(wind) >= 25:
            sentences.append(f"Wind is strong at {wind} km/h, which may affect travel comfort.")
        if risks.get("rain") in ELEVATED:
            sentences.append(f"Heavy-rain risk is {risks['rain'].lower()}, so allow buffer time.")
        if risks.get("flood") in {"High", "Critical"}:
            sentences.append("Avoid low-lying routes while flood risk is elevated.")
    elif mode == MODE_COMMUTE:
        sentences.append(rain_text)
        if wind is not None and to_number(wind) >= 20:
            sentences.append(f"Wind at {wind} km/h may slow the commute.")
        if factors["condition"]:
            sentences.append(f"Current conditions are {str(factors['condition']).lower()}.")
    elif mode == MODE_OUTDOOR:
        if temperature is not None:
            sentences.append(f"Temperature is {temperature}°C.")
        sentences.append(rain_text)
        if wind is not None and to_number(wind) >= 25:
            sentences.append("Wind is strong, so secure loose items before going out.")
        if risks.get("heatwave") in {"High", "Critical"}:
            sentences.append("Heat stress is high, so prefer the cooler parts of the day.")
    else:
        sentences.append(rain_text)
        if temperature is not None:
            sentences.append(f"Temperature is {temperature}°C.")
        if factors["risk_categories_elevated"]:
            labels = ", ".join(factors["risk_categories_elevated"])
            sentences.append(f"The rule-based risk outlook flags {labels}.")
    return [sentence for sentence in sentences if sentence]


def personalized_guidance(
    weather,
    rain_prediction=None,
    user_mode=MODE_GENERAL,
    active_alerts: Optional[list] = None,
    language: str = "en",
) -> dict[str, Any]:
    """Return mode-aware guidance plus the signals that produced it.

    The returned ``text`` is safe, informational, and derived only from the
    application's own weather, ML and rule-based risk data.
    """
    from services.translations import translate_phase3_sentence

    factors = personalization_factors(weather, rain_prediction, user_mode)
    mode = factors["mode"]
    # Each factor sentence is translated on its own, because the Phase 3
    # translation table is keyed per sentence rather than for the whole
    # combined paragraph. Unknown sentences keep the English fallback.
    sentences = [translate_phase3_sentence(part, language) for part in _mode_factors(mode, factors)]
    text = _sentence(sentences) or "Conditions are stable; use the forecast to plan your day."

    alert_types: list[str] = []
    for alert in active_alerts or []:
        alert_type = getattr(alert, "alert_type", None)
        if alert_type and alert_type not in alert_types:
            alert_types.append(alert_type)
    if alert_types:
        text = (
            f"{text} "
            + translate_phase3_sentence(f"Active alerts: {', '.join(alert_types)}.", language)
        )

    return {
        "mode": mode,
        "text": text,
        "factors": factors,
        "active_alert_types": alert_types,
        "alerts_contextualized": bool(alert_types),
        "uses_ml": factors["ml_probability"] is not None,
        "risk_levels": factors["risks"],
    }
