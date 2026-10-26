from unittest.mock import patch

import pytest

from app import create_app
from services.weather_service import WeatherServiceError
from models import db


WEATHER = {
    "location": {"name": "Chennai", "country": "India", "latitude": 13.08, "longitude": 80.27},
    "current": {
        "temperature": 32,
        "feels_like": 36,
        "humidity": 78,
        "wind_speed": 14,
        "precipitation": 1.2,
        "pressure": 1005,
        "condition": "Partly cloudy",
    },
    "forecast": [
        {"date": "Tue, Aug 25", "condition": "Rain", "temperature_min": 27, "temperature_max": 33, "rain_probability": 70, "precipitation": 3.5},
        {"date": "Wed, Aug 26", "condition": "Clear sky", "temperature_min": 26, "temperature_max": 34, "rain_probability": 20, "precipitation": 0.0},
    ],
}


@pytest.fixture()
def client():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.drop_all()


def login(client):
    client.post("/register", data={"name": "Student", "email": "student@example.com", "password": "strong-pass-123", "confirm_password": "strong-pass-123"})
    client.post("/login", data={"email": "student@example.com", "password": "strong-pass-123"})


def test_assistant_requires_login(client):
    assert client.get("/assistant").status_code == 302
    assert client.post("/api/assistant", json={"city": "Chennai", "question": "What is the weather?"}).status_code == 401


def test_assistant_answers_from_selected_location(client):
    login(client)
    prediction = {"probability_percent": 42, "model_name": "random_forest"}
    with patch("app.get_weather", return_value=WEATHER), patch("app.predict_rain", return_value=prediction) as predict:
        response = client.post("/api/assistant", json={"city": "Chennai", "question": "What are the current conditions?"})

    assert response.status_code == 200
    assert "32°C" in response.get_json()["answer"]
    assert "Partly cloudy" in response.get_json()["answer"]
    predict.assert_called_once_with(WEATHER["current"])


def test_assistant_rejects_empty_question(client):
    login(client)
    response = client.post("/api/assistant", json={"city": "Chennai", "question": ""})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Ask a weather question to continue."


@pytest.mark.parametrize("question, expected", [
    ("Will it rain tomorrow?", "Tomorrow in Vijayawada Rural"),
    ("today weather", "Today in Vijayawada Rural"),
])
def test_assistant_uses_selected_location_for_relative_questions(client, question, expected):
    login(client)
    prediction = {"probability_percent": 42, "model_name": "random_forest"}
    with patch("app.get_weather", return_value={**WEATHER, "location": {**WEATHER["location"], "name": "Vijayawada Rural"}}) as get_weather, patch("app.predict_rain", return_value=prediction):
        response = client.post("/api/assistant", json={"city": "Vijayawada Rural", "question": question})

    assert response.status_code == 200
    assert expected in response.get_json()["answer"]
    get_weather.assert_called_once_with("Vijayawada Rural")


def test_assistant_explicit_location_overrides_selected_location(client):
    login(client)
    prediction = {"probability_percent": 42, "model_name": "random_forest"}
    chennai_weather = {**WEATHER, "location": {**WEATHER["location"], "name": "Chennai"}}
    with patch("app.get_weather", return_value=chennai_weather) as get_weather, patch("app.predict_rain", return_value=prediction):
        response = client.post("/api/assistant", json={"city": "Vijayawada Rural", "question": "Weather in Chennai?"})

    assert response.status_code == 200
    get_weather.assert_called_once_with("Chennai")


def test_assistant_uses_session_location_when_city_is_omitted(client):
    login(client)
    prediction = {"probability_percent": 42, "model_name": "random_forest"}
    vijayawada_weather = {**WEATHER, "location": {**WEATHER["location"], "name": "Vijayawada Rural"}}
    with client.session_transaction() as session:
        session["selected_city"] = "Vijayawada Rural"
    with patch("app.get_weather", return_value=vijayawada_weather) as get_weather, patch("app.predict_rain", return_value=prediction):
        response = client.post("/api/assistant", json={"question": "Will it rain tomorrow?"})

    assert response.status_code == 200
    assert "Vijayawada Rural" in response.get_json()["answer"]
    get_weather.assert_called_once_with("Vijayawada Rural")


def test_assistant_rejects_missing_location(client):
    login(client)
    response = client.post("/api/assistant", json={"question": "What's the weather today?"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Select a location before asking a question."


def test_assistant_handles_weather_service_failure(client):
    login(client)
    with patch("app.get_weather", side_effect=WeatherServiceError("The weather service is temporarily unavailable.")):
        response = client.post("/api/assistant", json={"city": "Chennai", "question": "What's the weather today?"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "The weather service is temporarily unavailable."
