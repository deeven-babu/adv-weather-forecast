"""Tests for the Phase 1 fixes: best-time hourly logic, risk centralization,
rain-probability alert regression, and dashboard rendering.
"""

from unittest.mock import patch

import pytest

from app import create_app
from services.recommendations import (
    MODE_COMMUTE,
    MODE_FARMER,
    MODE_GENERAL,
    MODE_OUTDOOR,
    MODE_TRAVEL,
    generate_weather_alerts,
    get_best_time_window,
    get_recommendation_by_mode,
)
from services.risk import assess_risks, flood_level, heatwave_level, rain_level
from services.weather_service import _build_hourly
from services.weather_assistant import _risk_levels


def hour(time, temperature, rain_probability, precipitation=0.0, wind_speed=8.0):
    return {
        "time": time,
        "hour": int(time[11:13]),
        "temperature": temperature,
        "rain_probability": rain_probability,
        "precipitation": precipitation,
        "wind_speed": wind_speed,
    }


def hourly_weather(records, location="Chennai", rain_probability=20.0):
    """Build a weather payload containing an hourly block."""
    return {
        "location": {"name": location, "country": "India", "latitude": 13.08, "longitude": 80.27},
        "current": {
            "temperature": 30.0,
            "humidity": 70.0,
            "wind_speed": 12.0,
            "precipitation": 0.0,
            "condition": "Partly cloudy",
            "pressure": 1010.0,
        },
        "forecast": [
            {
                "date": "2026-08-31",
                "condition": "Partly cloudy",
                "temperature_min": 24.0,
                "temperature_max": 31.0,
                "rain_probability": rain_probability,
                "precipitation": 0.0,
            }
        ],
        "hourly": records,
    }


# --------------------------------------------------------------------------
# Step 2: best-time window
# --------------------------------------------------------------------------

class TestBestTimeWindowHourly:
    def test_returns_real_window_when_hourly_available(self):
        """A dry, mild afternoon must produce a real afternoon window.

        Contract: the reported rain chance and temperatures describe the
        *selected window* (the three hours starting at the best-scoring hour),
        averaged over the window, not the single best hour. This mirrors the
        original day-level implementation, which reported the chosen day's
        min/max temperature and rain probability.
        """
        records = [
            hour("2026-08-31T06:00", 20.0, 80.0, precipitation=4.0),
            hour("2026-08-31T07:00", 20.0, 85.0, precipitation=6.0),
            hour("2026-08-31T15:00", 26.0, 0.0, precipitation=0.0),
            hour("2026-08-31T16:00", 27.0, 5.0, precipitation=0.0),
            hour("2026-08-31T17:00", 28.0, 10.0, precipitation=0.0),
        ]
        result = get_best_time_window(hourly_weather(records))
        assert result.startswith("Best time for outdoor plans in Chennai is")
        # The dry afternoon hours (15:00-17:00) must beat the wet morning.
        assert "early afternoon" in result
        # Window-level aggregate: (0 + 5 + 10) / 3 = 5, not the best hour's 0.
        assert "5% rain chance" in result
        # Window min/max temperature across the same three hours.
        assert "26°C to 28°C" in result
        # The sentence must keep the format the translation layer parses.
        assert ", when rainfall risk is lower" in result
        assert result.endswith(".")

    def test_window_avoids_heavy_rain_hours(self):
        records = [
            hour("2026-08-31T11:00", 26.0, 95.0, precipitation=9.0),
            hour("2026-08-31T12:00", 26.0, 95.0, precipitation=9.0),
            hour("2026-08-31T19:00", 24.0, 0.0, precipitation=0.0),
        ]
        result = get_best_time_window(hourly_weather(records))
        assert "early afternoon" in result
        assert "0% rain chance" in result

    def test_midday_hours_map_to_midday_label(self):
        records = [
            hour("2026-08-31T13:00", 26.0, 0.0, precipitation=0.0),
            hour("2026-08-31T14:00", 26.0, 0.0, precipitation=0.0),
        ]
        result = get_best_time_window(hourly_weather(records))
        assert " is midday," in result

    def test_missing_hourly_returns_friendly_fallback(self):
        result = get_best_time_window(hourly_weather([]))
        assert "hourly" in result.lower()
        assert "not available" in result.lower()

    def test_empty_weather_returns_friendly_fallback(self):
        result = get_best_time_window(None)
        assert isinstance(result, str)
        assert "not available" in result.lower()


class TestBuildHourly:
    def test_normalizes_complete_hourly_block(self):
        data = {
            "hourly": {
                "time": ["2026-08-31T13:00", "2026-08-31T14:00"],
                "temperature_2m": [26.0, 27.0],
                "precipitation_probability": [10, 20],
                "precipitation": [0.0, 0.5],
                "wind_speed_10m": [8, 9],
            }
        }
        records = _build_hourly(data)
        assert len(records) == 2
        assert records[0]["hour"] == 13
        assert records[0]["temperature"] == 26.0
        assert records[1]["rain_probability"] == 20.0
        assert records[1]["precipitation"] == 0.5

    def test_missing_hourly_block_returns_empty_list(self):
        assert _build_hourly({}) == []
        assert _build_hourly({"hourly": None}) == []
        assert _build_hourly({"hourly": {"time": []}}) == []

    def test_incomplete_hourly_block_skips_bad_rows(self):
        data = {
            "hourly": {
                "time": ["2026-08-31T13:00", "2026-08-31T14:00"],
                "temperature_2m": [26.0, None],
                "precipitation_probability": [10, 20],
                "precipitation": [0.0, 0.5],
                "wind_speed_10m": [8, 9],
            }
        }
        records = _build_hourly(data)
        assert len(records) == 1
        assert records[0]["hour"] == 13

    def test_missing_wind_speed_defaults_to_zero(self):
        data = {
            "hourly": {
                "time": ["2026-08-31T13:00"],
                "temperature_2m": [26.0],
                "precipitation_probability": [10],
                "precipitation": [0.0],
            }
        }
        records = _build_hourly(data)
        assert records[0]["wind_speed"] == 0.0

    def test_unparseable_time_does_not_raise(self):
        data = {
            "hourly": {
                "time": ["not-a-timestamp"],
                "temperature_2m": [26.0],
                "precipitation_probability": [10],
                "precipitation": [0.0],
                "wind_speed_10m": [8],
            }
        }
        records = _build_hourly(data)
        assert records[0]["hour"] is None


# --------------------------------------------------------------------------
# Step 5: centralized disaster risk
# --------------------------------------------------------------------------

class TestCentralizedRisk:
    def test_flood_thresholds(self):
        assert flood_level(20.0, 50.0) == "High"
        assert flood_level(0.0, 85.0) == "High"
        assert flood_level(9.0, 50.0) == "Moderate"
        assert flood_level(0.0, 72.0) == "Moderate"
        assert flood_level(1.0, 40.0) == "Low"

    def test_heatwave_thresholds(self):
        assert heatwave_level(40.0) == "Critical"
        assert heatwave_level(33.0) == "High"
        assert heatwave_level(29.0) == "Moderate"
        assert heatwave_level(22.0) == "Low"

    def test_rain_thresholds(self):
        assert rain_level(80.0) == "High"
        assert rain_level(60.0) == "Moderate"
        assert rain_level(10.0) == "Low"

    def test_assess_risks_returns_all_three_categories(self):
        risks = assess_risks(
            {
                "current": {"precipitation": 16.0, "humidity": 85.0, "temperature": 39.0},
                "forecast": [{"rain_probability": 80.0}],
            }
        )
        assert risks == {"flood": "High", "heatwave": "Critical", "rain": "High"}

    def test_assess_risks_handles_missing_data(self):
        assert assess_risks({}) == {"flood": "Low", "heatwave": "Low", "rain": "Low"}
        assert assess_risks(None) == {"flood": "Low", "heatwave": "Low", "rain": "Low"}

    def test_assess_risks_handles_missing_forecast(self):
        risks = assess_risks(
            {"current": {"precipitation": 0.0, "humidity": 30.0, "temperature": 20.0}}
        )
        assert risks["rain"] == "Low"


# --------------------------------------------------------------------------
# Step 4: rain-probability alert regression
# --------------------------------------------------------------------------

def weather_with_rain(rain_probability, precipitation=0.0):
    return {
        "location": {"name": "Test City", "country": "Test Land"},
        "current": {
            "temperature": 24.0,
            "humidity": 60.0,
            "wind_speed": 8.0,
            "precipitation": precipitation,
            "condition": "Cloudy",
            "pressure": 1010.0,
        },
        "forecast": [
            {
                "date": "2026-08-31",
                "condition": "Cloudy",
                "temperature_min": 20.0,
                "temperature_max": 27.0,
                "rain_probability": rain_probability,
                "precipitation": 0.0,
            }
        ],
    }


def alert_types(alerts):
    return {alert.type for alert in alerts}


class TestRainProbabilityAlerts:
    def test_low_rain_probability_has_no_probability_alert(self):
        alerts = generate_weather_alerts(weather_with_rain(20.0))
        assert "High Rain Probability" not in alert_types(alerts)
        assert "Moderate Rain Probability" not in alert_types(alerts)

    def test_moderate_band_raises_moderate_alert(self):
        """Regression: the 50-74% band must raise the moderate alert.

        This previously failed because of the chained comparison
        ``rain_prob >= 75 is False``, which always evaluated to False.
        """
        alerts = generate_weather_alerts(weather_with_rain(60.0))
        assert "Moderate Rain Probability" in alert_types(alerts)
        assert "High Rain Probability" not in alert_types(alerts)
        moderate = next(a for a in alerts if a.type == "Moderate Rain Probability")
        assert moderate.severity == "Moderate"

    def test_low_edge_of_moderate_band_raises_alert(self):
        assert "Moderate Rain Probability" in alert_types(
            generate_weather_alerts(weather_with_rain(50.0))
        )

    def test_high_band_raises_high_alert(self):
        alerts = generate_weather_alerts(weather_with_rain(80.0))
        assert "High Rain Probability" in alert_types(alerts)
        assert "Moderate Rain Probability" not in alert_types(alerts)
        high = next(a for a in alerts if a.type == "High Rain Probability")
        assert high.severity == "High"

    def test_heavy_current_rain_suppresses_probability_alerts(self):
        """Existing rule: heavy current precipitation suppresses these alerts."""
        alerts = generate_weather_alerts(weather_with_rain(60.0, precipitation=18.0))
        assert "Moderate Rain Probability" not in alert_types(alerts)

    def test_all_bands_are_distinct(self):
        low = alert_types(generate_weather_alerts(weather_with_rain(20.0)))
        moderate = alert_types(generate_weather_alerts(weather_with_rain(60.0)))
        high = alert_types(generate_weather_alerts(weather_with_rain(90.0)))
        assert "Moderate Rain Probability" in moderate
        assert "Moderate Rain Probability" not in low
        assert "High Rain Probability" in high
        assert "Moderate Rain Probability" not in high



# --------------------------------------------------------------------------
# Step 3 + 7: dashboard rendering, mode refresh, intelligence endpoint
# --------------------------------------------------------------------------

def logged_in_client():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    client = app.test_client()
    client.post(
        "/register",
        data={
            "name": "Student",
            "email": "phase1@example.com",
            "password": "strong-pass-123",
            "confirm_password": "strong-pass-123",
        },
    )
    client.post("/login", data={"email": "phase1@example.com", "password": "strong-pass-123"})
    return app, client


DASHBOARD_WEATHER = {
    "location": {"name": "Chennai", "country": "India", "latitude": 13.08, "longitude": 80.27},
    "current": {
        "temperature": 32.0,
        "humidity": 78.0,
        "wind_speed": 14.0,
        "precipitation": 1.2,
        "feels_like": 36.0,
        "condition": "Partly cloudy",
        "pressure": 1005.0,
        "wind_direction": 180,
        "sunrise": "06:00",
        "sunset": "18:30",
    },
    "forecast": [
        {
            "date": "Mon, Aug 31",
            "condition": "Rain",
            "temperature_min": 27.0,
            "temperature_max": 33.0,
            "rain_probability": 70.0,
            "precipitation": 3.5,
        }
    ],
    "hourly": [
        hour("2026-08-31T15:00", 26.0, 0.0),
        hour("2026-08-31T16:00", 27.0, 5.0),
    ],
    "units": {"temperature": "°C", "wind_speed": "km/h", "precipitation": "mm", "pressure": "hPa"},
}


class TestDashboardBestTime:
    def test_dashboard_renders_best_time(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            response = client.get("/dashboard?city=Chennai")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "data-best-time" in body
        assert "data-best-time-text" in body
        assert "Best time for outdoor plans in Chennai is" in body

    def test_dashboard_renders_all_five_modes(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        for mode in ("general", "farmer", "travel", "daily_commute", "outdoor_activity"):
            assert f'data-mode="{mode}"' in body

    def test_dashboard_renders_centralized_risk_levels(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        # humidity 78 -> Moderate flood; temp 32 -> High heat; rain 70 -> Moderate rain
        assert "risk-flood" in body
        assert "risk-heat" in body
        assert "risk-rain" in body
        assert "level-moderate" in body
        assert "level-high" in body


class TestModeEndpoints:
    @pytest.mark.parametrize(
        "mode", ["general", "farmer", "travel", "daily_commute", "outdoor_activity"]
    )
    def test_every_mode_returns_its_own_recommendation(self, mode):
        app, client = logged_in_client()
        client.post("/api/user-mode", json={"mode": mode})
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            response = client.get("/api/recommendations?city=Chennai")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["mode"] == mode
        assert payload["recommendation"]
        assert payload["best_time"]

    def test_recommendations_change_between_modes(self):
        app, client = logged_in_client()
        client.post("/api/user-mode", json={"mode": "farmer"})
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            farmer = client.get("/api/recommendations?city=Chennai").get_json()["recommendation"]
        client.post("/api/user-mode", json={"mode": "travel"})
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            travel = client.get("/api/recommendations?city=Chennai").get_json()["recommendation"]
        assert farmer != travel

    def test_invalid_mode_is_rejected(self):
        app, client = logged_in_client()
        response = client.post("/api/user-mode", json={"mode": "invalid"})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_user_mode_is_persisted_in_session(self):
        app, client = logged_in_client()
        client.post("/api/user-mode", json={"mode": "outdoor_activity"})
        assert client.get("/api/user-mode").get_json()["mode"] == "outdoor_activity"


class TestIntelligenceEndpoint:
    def test_requires_login(self):
        app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        response = app.test_client().get("/api/phase9/intelligence?city=Chennai")
        assert response.status_code == 401

    def test_combines_weather_and_mode(self):
        app, client = logged_in_client()
        client.post("/api/user-mode", json={"mode": "farmer"})
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            response = client.get("/api/phase9/intelligence?city=Chennai")
        assert response.status_code == 200
        context = response.get_json()["context"]
        assert context["mode"] == "farmer"
        assert context["temperature"] == 32.0
        assert context["humidity"] == 78.0
        assert context["rain_probability"] == 70.0
        assert context["condition"]
        assert context["recommendation"]

    def test_falls_back_to_session_city(self):
        app, client = logged_in_client()
        with client.session_transaction() as session:
            session["selected_city"] = "Chennai"
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER):
            response = client.get("/api/phase9/intelligence")
        assert response.status_code == 200
        assert response.get_json()["context"]["location"]["name"] == "Chennai"


class TestAssistantRiskConsistency:
    def test_assistant_risk_answer_uses_centralized_levels(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=DASHBOARD_WEATHER), patch(
            "app.predict_rain", return_value=None
        ):
            response = client.post(
                "/api/assistant", json={"question": "Is there any risk today?", "city": "Chennai"}
            )
        assert response.status_code == 200
        answer = response.get_json()["answer"].lower()
        assert "flood moderate" in answer
        assert "heatwave high" in answer
        assert "heavy rain moderate" in answer


class TestModeRecommendationsUnchanged:
    """Confirm the Phase 1 fixes did not alter existing mode behaviour."""

    @pytest.mark.parametrize(
        "mode,expected_terms",
        [
            (MODE_GENERAL, ["weather", "plan", "suitable", "rain", "outdoor"]),
            (MODE_FARMER, ["irrigation", "crop", "field", "rain"]),
            (MODE_TRAVEL, ["travel", "carry", "rain", "caution"]),
            (MODE_COMMUTE, ["commute", "umbrella", "rain", "conditions"]),
            (MODE_OUTDOOR, ["outdoor", "activity", "conditions", "rain"]),
        ],
    )
    def test_each_mode_still_produces_its_own_advice(self, mode, expected_terms):
        recommendation = get_recommendation_by_mode(DASHBOARD_WEATHER, mode)
        assert isinstance(recommendation, str) and recommendation
        assert any(term in recommendation.lower() for term in expected_terms)


    def test_dashboard_uses_centralized_heat_threshold(self):
        """A 39C reading must produce the Critical level from services.risk."""
        hot = {**DASHBOARD_WEATHER, "current": {**DASHBOARD_WEATHER["current"], "temperature": 39.0}}
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=hot):
            body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert "level-critical" in body

    def test_dashboard_still_renders_when_hourly_missing(self):
        without_hourly = {**DASHBOARD_WEATHER, "hourly": []}
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=without_hourly):
            response = client.get("/dashboard?city=Chennai")
        assert response.status_code == 200
        assert "data-best-time-text" in response.get_data(as_text=True)


    def test_assistant_and_service_agree_on_risk(self):
        """The assistant must use the same thresholds as the dashboard."""
        weather = {
            "current": {"precipitation": 16.0, "humidity": 85.0, "temperature": 33.0},
            "forecast": [{"rain_probability": 55.0}],
        }
        flood, heat, rain = _risk_levels(weather)
        risks = assess_risks(weather)
        assert (flood, heat, rain) == (risks["flood"], risks["heatwave"], risks["rain"])
        assert (flood, heat, rain) == ("High", "High", "Moderate")


    def test_hourly_rows_without_temperature_fall_back(self):
        records = [
            {"time": "2026-08-31T15:00", "hour": 15, "temperature": None,
             "rain_probability": 0.0, "precipitation": 0.0, "wind_speed": 5.0}
        ]
        result = get_best_time_window(hourly_weather(records))
        assert "not available" in result.lower()

    def test_non_dict_hourly_entries_are_ignored(self):
        result = get_best_time_window(hourly_weather(["oops", None, 42]))
        assert "not available" in result.lower()
