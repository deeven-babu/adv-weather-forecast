"""Phase 3 assistant conversation context.

The Phase 1 assistant is rule-based and is NOT an LLM. This module adds a
lightweight conversation memory so a follow-up question such as "What about
tomorrow?" can reuse the location and topic from the previous exchange.

It is deliberately conservative:

* ``detect_intent`` from ``services.phase9`` is still the authority; this
  module never introduces a new intent, so all existing behaviour is kept.
* A follow-up is only expanded when the user clearly omitted the subject and
  there is real prior context to reuse.
* The stored context is plain data (city, intent, language, mode) and holds no
  sensitive information.
"""

from __future__ import annotations

from typing import Any, Optional

#: Phrases that mean "same subject as before". Kept short and explicit.
FOLLOW_UP_PREFIXES = (
    "what about",
    "and tomorrow",
    "and today",
    "how about",
    "what then",
    "and the",
    "same for",
    "what about that",
    "there",
    "అదే",
    "అప్పుడు",
    "उसके बारे",
    "वहाँ",
)

#: A follow-up must also be short, otherwise it is a new question.
FOLLOW_UP_MAX_WORDS = 7

#: Intents that make a useful follow-up subject.
CONTEXTUAL_INTENTS = {
    "rain",
    "tomorrow_weather",
    "current_weather",
    "forecast",
    "temperature",
    "humidity",
    "wind",
    "precipitation",
    "risk",
    "best_time",
    "ml_prediction",
    "ml_explanation",
    "recommendation",
}


def is_follow_up(question: str) -> bool:
    """Return True when a question clearly refers to the previous subject."""
    text = str(question or "").strip().lower().rstrip("?।.!")
    if not text or len(text.split()) > FOLLOW_UP_MAX_WORDS:
        return False
    return any(text.startswith(prefix) or f" {prefix} " in f" {text} " for prefix in FOLLOW_UP_PREFIXES)


def new_context(city: str = "", intent: str = "", language: str = "en", mode: str = "general") -> dict[str, Any]:
    """Return a fresh conversation context record."""
    return {
        "city": city or "",
        "intent": intent or "",
        "language": language or "en",
        "mode": mode or "general",
        "turns": 0,
    }


def update_context(context: Optional[dict[str, Any]], city: str, intent: str, language: str, mode: str) -> dict[str, Any]:
    """Return an updated context that remembers the most recent useful turn."""
    previous = dict(context or {})
    turns = int(previous.get("turns") or 0) + 1
    if intent in CONTEXTUAL_INTENTS:
        # A concrete, contextual turn replaces the remembered subject.
        return {
            "city": city or previous.get("city", ""),
            "intent": intent,
            "language": language or previous.get("language", "en"),
            "mode": mode or previous.get("mode", "general"),
            "turns": turns,
        }
    # Otherwise keep the previous subject so a later follow-up still works.
    return {
        "city": previous.get("city", "") or city or "",
        "intent": previous.get("intent", ""),
        "language": language or previous.get("language", "en"),
        "mode": mode or previous.get("mode", "general"),
        "turns": turns,
    }


def resolve_question(question: str, context: Optional[dict[str, Any]]) -> tuple[str, str, str]:
    """Expand a follow-up using the remembered context.

    Returns ``(resolved_question, city, used_context)``. ``city`` is the
    location the assistant should use and ``used_context`` is ``"true"`` only
    when prior context actually changed the request.
    """
    remembered = dict(context or {})
    text = str(question or "").strip()
    city = remembered.get("city", "") or ""
    used = "false"

    if not is_follow_up(text) or not city:
        return text, city, used

    topic = _topic_from_intent(remembered.get("intent", ""))
    if not topic:
        return text, city, used

    lowered = text.lower()
    if topic in lowered:
        # The user already named the subject, so only the location is reused.
        return text, city, "true"

    resolved = f"{text.rstrip('?।.!')} {topic}".strip()
    return resolved, city, "true"


def _topic_from_intent(intent: str) -> str:
    """Map a remembered intent back to a short subject phrase."""
    return {
        "rain": "rain",
        "tomorrow_weather": "tomorrow",
        "current_weather": "today",
        "forecast": "forecast",
        "temperature": "temperature",
        "humidity": "humidity",
        "wind": "wind",
        "precipitation": "precipitation",
        "risk": "risk",
        "best_time": "best time",
        "ml_prediction": "rain prediction",
        "ml_explanation": "why",
        "recommendation": "weather",
    }.get(intent, "")
