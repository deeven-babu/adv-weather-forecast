from app import create_app
from services.recommendations import (
    MODE_COMMUTE,
    MODE_FARMER,
    MODE_GENERAL,
    MODE_OUTDOOR,
    MODE_TRAVEL,
    WeatherAlert,
    generate_today_summary,
    get_recommendation_by_mode,
)
from services.translations import (
    DEFAULT_LANGUAGE,
    get_ui_text,
    normalize_language,
    translate_alert,
    translate_recommendation,
    translate_summary,
    translate_text,
)


SAMPLE_WEATHER = {
    "location": {"name": "Chennai", "country": "India", "latitude": 13.08, "longitude": 80.27},
    "current": {
        "temperature": 32.0,
        "humidity": 78.0,
        "wind_speed": 14.0,
        "precipitation": 1.2,
        "condition": "Partly cloudy",
        "pressure": 1005.0,
    },
    "forecast": [
        {
            "date": "2026-08-31",
            "condition": "Rainy",
            "temperature_min": 27.0,
            "temperature_max": 33.0,
            "rain_probability": 70.0,
            "precipitation": 3.5,
        }
    ],
}


def test_english_ui_translation():
    assert get_ui_text("en", "nav.dashboard") == "Dashboard"


def test_telugu_ui_translation():
    assert get_ui_text("te", "nav.dashboard") == "డాష్‌బోర్డ్"


def test_hindi_ui_translation():
    assert get_ui_text("hi", "nav.dashboard") == "डैशबोर्ड"


def test_language_normalization_and_fallback():
    assert normalize_language("te") == "te"
    assert normalize_language("fr") == DEFAULT_LANGUAGE
    assert normalize_language(None) == DEFAULT_LANGUAGE


def test_language_selection_persists_in_session():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as client:
        response = client.post("/api/language", json={"language": "te"})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["language"] == "te"
        with client.session_transaction() as session:
            assert session["language"] == "te"


def test_multilingual_alert_translation():
    alert = WeatherAlert("Heavy Rain", "High", "Heavier rainfall is expected.")
    translated = translate_alert(alert, "hi")
    assert "तेज़ बारिश" in translated["type"]
    assert "उच्च" in translated["severity"]


def test_multilingual_recommendation_translation():
    text = "Consider carrying an umbrella or rain protection."
    telugu = translate_recommendation(text, "te")
    hindi = translate_recommendation(text, "hi")
    assert "చెట్టు" in telugu or "వర్షరక్షణ" in telugu
    assert "छाता" in hindi or "बारिश" in hindi


def test_multilingual_ai_response_uses_selected_language():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as client:
        client.post("/register", data={"name": "Student", "email": "student@example.com", "password": "strong-pass-123", "confirm_password": "strong-pass-123"})
        client.post("/login", data={"email": "student@example.com", "password": "strong-pass-123"})
        with client.session_transaction() as session:
            session["language"] = "te"
        from unittest.mock import patch

        with patch("app.get_weather", return_value=SAMPLE_WEATHER), patch("app.predict_rain", return_value={"probability_percent": 42, "model_name": "random_forest"}):
            response = client.post("/api/assistant", json={"city": "Chennai", "question": "What's the weather today?"})

        assert response.status_code == 200
        answer = response.get_json()["answer"]
        assert "నేడు" in answer or "ఈ రోజు" in answer


def test_phase7_recommendations_still_work_with_language_layer():
    rec = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_FARMER)
    assert isinstance(rec, str) and len(rec) > 0
    translated = translate_recommendation(rec, "hi")
    assert isinstance(translated, str) and len(translated) > 0

    travel = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_TRAVEL)
    assert isinstance(travel, str) and len(travel) > 0
    travel_translated = translate_recommendation(travel, "te")
    assert isinstance(travel_translated, str) and len(travel_translated) > 0


def test_summary_preserves_dynamic_values_in_supported_languages():
    summary = generate_today_summary(SAMPLE_WEATHER)
    for language, script in (("te", "నేడు"), ("hi", "आज")):
        translated = translate_summary(summary, language)
        assert script in translated
        assert "32" in translated and "Chennai" in translated
        assert "Today" not in translated


def test_all_phase7_modes_translate_without_english_source_phrases():
    for mode in (MODE_GENERAL, MODE_FARMER, MODE_TRAVEL, MODE_COMMUTE, MODE_OUTDOOR):
        source = get_recommendation_by_mode(SAMPLE_WEATHER, mode)
        for language in ("te", "hi"):
            translated = translate_recommendation(source, language)
            assert translated
            assert translated != source


def test_unsupported_language_falls_back_to_original_english():
    source = "Weather conditions appear suitable for outdoor activities."
    assert translate_text(source, "fr") == source
