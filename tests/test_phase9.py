from copy import deepcopy
from unittest.mock import patch

from app import create_app
from services.phase9 import available_model_features, detect_intent, explain_prediction, simulate_scenario
from services.recommendations import MODE_FARMER
from services.translations import translate_recommendation


WEATHER = {
    "location": {"name": "Chennai", "country": "India"},
    "current": {
        "temperature": 32,
        "humidity": 78,
        "wind_speed": 14,
        "precipitation": 1.2,
        "pressure": 1005,
        "condition": "Partly cloudy",
    },
    "forecast": [
        {"condition": "Rain", "temperature_min": 27, "temperature_max": 33, "rain_probability": 70, "precipitation": 3.5}
    ],
}


def test_phase9_intent_detection_examples():
    assert detect_intent("What is the weather today?") == "current_weather"
    assert detect_intent("Will it rain tomorrow?") == "tomorrow_weather"
    assert detect_intent("Should I irrigate today?") == "farmer_advice"
    assert detect_intent("Should I travel today?") == "travel_advice"
    assert detect_intent("Should I carry rain protection for my commute?") == "commute_advice"
    assert detect_intent("Can I play cricket this evening?") == "outdoor_advice"
    assert detect_intent("Why does the model predict rain?") == "ml_explanation"
    assert detect_intent("ఈరోజు నేను పొలానికి నీరు పెట్టాలా?") == "farmer_advice"
    assert detect_intent("क्या मुझे आज खेत में पानी देना चाहिए?") == "farmer_advice"


def test_phase9_explanation_uses_only_available_model_factors():
    prediction = {
        "probability_percent": 68,
        "model_name": "random_forest",
        "factors": [{"name": "Humidity", "importance": 0.42}, {"name": "Wind Speed", "importance": 0.2}],
    }
    explanation = explain_prediction(prediction)
    assert explanation["available"] is True
    assert available_model_features(prediction) == ["humidity", "wind_speed"]
    assert "cloud_cover" in explanation["feature_columns"]


def test_phase9_simulation_is_labeled_and_does_not_change_weather():
    original = deepcopy(WEATHER)
    result = simulate_scenario("What if rainfall probability becomes 70%?", WEATHER)
    assert "not an actual forecast" in result["label"]
    assert result["value"] == 70
    assert WEATHER == original


def test_phase9_simulation_rejects_invalid_input():
    try:
        simulate_scenario("Tell me a joke", WEATHER)
    except ValueError as error:
        assert "rainfall or temperature" in str(error)
    else:
        raise AssertionError("invalid scenario should be rejected")


def test_phase9_scenario_endpoint_uses_session_language():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as client:
        client.post("/register", data={"name": "Student", "email": "phase9@example.com", "password": "strong-pass-123", "confirm_password": "strong-pass-123"})
        client.post("/login", data={"email": "phase9@example.com", "password": "strong-pass-123"})
        client.post("/api/language", json={"language": "hi"})
        with patch("app.get_weather", return_value=WEATHER):
            response = client.post(
                "/api/phase9/scenario",
                json={"scenario": "What if temperature reaches 40°C?", "city": "Chennai"},
            )
        assert response.status_code == 200
        result = response.get_json()["result"]
        assert "सिमुलेशन" in result["label"]
        assert "40°C" in result["scenario"]


def test_phase9_ml_explanation_endpoint_uses_existing_prediction():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    prediction = {
        "probability_percent": 62,
        "model_name": "random_forest",
        "factors": [{"name": "Humidity", "importance": 0.42}],
    }
    with app.test_client() as client:
        client.post("/register", data={"name": "Student", "email": "explain@example.com", "password": "strong-pass-123", "confirm_password": "strong-pass-123"})
        client.post("/login", data={"email": "explain@example.com", "password": "strong-pass-123"})
        with patch("app.get_weather", return_value=WEATHER), patch("app.predict_rain", return_value=prediction):
            response = client.get("/api/phase9/ml-explanation?city=Chennai")
        assert response.status_code == 200
        explanation = response.get_json()["explanation"]
        assert explanation["model_name"] == "random_forest"
        assert explanation["feature_columns"] == ["temperature", "humidity", "pressure", "wind_speed", "precipitation", "cloud_cover"]
        assert explanation["available"] is True


def test_multilingual_farmer_recommendation_keeps_complete_sentences():
    source = "Rainfall (70.0% probability) is expected. Monitor crop conditions. Warm conditions expected. Ensure adequate water supply for crops."
    telugu = translate_recommendation(source, "te")
    hindi = translate_recommendation(source, "hi")
    assert "70.0%" in telugu and "70.0%" in hindi
    assert "probability" not in telugu and "expected" not in telugu
    assert "probability" not in hindi and "expected" not in hindi


def test_multilingual_farmer_chat_uses_same_logic_and_selected_language():
    cases = (
        ("te", "ఈరోజు నేను పొలానికి నీరు పెట్టాలా?", "farmer_advice", "probability", "expected"),
        ("hi", "क्या मुझे आज खेत में पानी देना चाहिए?", "farmer_advice", "probability", "expected"),
        ("en", "Should I irrigate today?", "farmer_advice", None, None),
    )
    for index, (language, question, expected_intent, forbidden_one, forbidden_two) in enumerate(cases):
        app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        with app.test_client() as client:
            email = f"chat{index}@example.com"
            client.post("/register", data={"name": "Student", "email": email, "password": "strong-pass-123", "confirm_password": "strong-pass-123"})
            client.post("/login", data={"email": email, "password": "strong-pass-123"})
            client.post("/api/language", json={"language": language})
            with patch("app.get_weather", return_value=WEATHER), patch("app.predict_rain", return_value=None):
                response = client.post("/api/assistant", json={"question": question, "city": "Chennai"})
            payload = response.get_json()
            assert response.status_code == 200
            assert payload["intent"] == expected_intent
            assert payload["location"]["name"] == "Chennai"
            if forbidden_one:
                assert forbidden_one not in payload["answer"]
                assert forbidden_two not in payload["answer"]


def test_all_multilingual_chat_examples_use_canonical_intents():
    examples = {
        "en": (
            ("Will it rain tomorrow?", "tomorrow_weather"),
            ("Should I irrigate today?", "farmer_advice"),
            ("Should I travel today?", "travel_advice"),
            ("Can I go outside this evening?", "outdoor_advice"),
            ("Why does the model predict rain?", "ml_explanation"),
        ),
        "te": (
            ("రేపు వర్షం పడుతుందా?", "tomorrow_weather"),
            ("ఈరోజు నేను పొలానికి నీరు పెట్టాలా?", "farmer_advice"),
            ("ఈరోజు ప్రయాణం చేయడం మంచిదేనా?", "travel_advice"),
            ("ఈ సాయంత్రం బయటకు వెళ్లవచ్చా?", "outdoor_advice"),
            ("మోడల్ వర్షం పడుతుందని ఎందుకు అంచనా వేసింది?", "ml_explanation"),
        ),
        "hi": (
            ("क्या कल बारिश होगी?", "tomorrow_weather"),
            ("क्या मुझे आज खेत में पानी देना चाहिए?", "farmer_advice"),
            ("क्या आज यात्रा करना ठीक है?", "travel_advice"),
            ("क्या मैं आज शाम बाहर जा सकता हूँ?", "outdoor_advice"),
            ("मॉडल बारिश की भविष्यवाणी क्यों कर रहा है?", "ml_explanation"),
        ),
    }
    for language, questions in examples.items():
        for question, expected_intent in questions:
            assert detect_intent(question) == expected_intent
