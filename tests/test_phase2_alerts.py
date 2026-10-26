"""Tests for Phase 2: persistent disaster alerts, alert history, read/unread,
notification preferences, duplicate prevention, and API security.

Phase 1 behaviour is not re-tested here beyond the integration checks that
confirm the existing weather pipeline now feeds the database.
"""

from unittest.mock import patch

from app import create_app
from models import Alert, Location, NotificationPreference, Prediction, RiskAssessment, User, WeatherRecord, db
from services.alerts import (
    alert_history,
    generate_alerts,
    persist_prediction,
    persist_risk_assessments,
    process_weather_observations,
    unread_alert_count,
)

PASSWORD = "strong-pass-123"


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------

def build_app():
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )


def register_and_login(app, email, name="Student"):
    client = app.test_client()
    client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def logged_in_client(email="phase2@example.com"):
    """Return a logged-in client for a fresh in-memory application."""
    app = build_app()
    return app, register_and_login(app, email)


def weather_for(temperature=32.0, humidity=78.0, precipitation=1.2, rain_probability=70.0, wind_speed=14.0):
    """Build a weather payload shaped exactly like the weather service output."""
    return {
        "location": {"name": "Chennai", "country": "India", "latitude": 13.08, "longitude": 80.27},
        "current": {
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "precipitation": precipitation,
            "feels_like": temperature + 2,
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
                "temperature_max": temperature,
                "rain_probability": rain_probability,
                "precipitation": 3.5,
            }
        ],
        "hourly": [
            {
                "time": "2026-08-31T15:00",
                "hour": 15,
                "temperature": 26.0,
                "rain_probability": 0.0,
                "precipitation": 0.0,
                "wind_speed": 8.0,
            }
        ],
        "units": {"temperature": "°C", "wind_speed": "km/h", "precipitation": "mm", "pressure": "hPa"},
    }


RAIN_PREDICTION = {
    "probability": 0.72,
    "probability_percent": 72,
    "prediction": "Rain Expected",
    "risk_level": "Moderate",
    "factors": [{"name": "Humidity", "importance": 0.4}],
    "model_name": "Random Forest",
}


def visit_dashboard(client, weather=None, prediction=RAIN_PREDICTION):
    """Run the existing dashboard workflow with weather and ML stubbed out."""
    weather = weather or weather_for()
    with patch("app.get_weather", return_value=weather), patch("app.predict_rain", return_value=prediction):
        return client.get("/dashboard?city=Chennai")


def seed_context(app, name="Chennai"):
    """Create a user + location + weather record and return them."""
    with app.app_context():
        user = User(name="Student", email="seed@example.com")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        location = Location(user_id=user.id, name=name, latitude=13.08, longitude=80.27)
        db.session.add(location)
        db.session.commit()
        record = WeatherRecord(location_id=location.id, temperature=30.0)
        db.session.add(record)
        db.session.commit()
        return user.id, location.id, record.id


# --------------------------------------------------------------------------
# Steps 2 + 3: prediction and risk persistence
# --------------------------------------------------------------------------

class TestPredictionPersistence:
    def test_dashboard_persists_prediction(self):
        app, client = logged_in_client()
        response = visit_dashboard(client)
        assert response.status_code == 200
        with app.app_context():
            predictions = Prediction.query.all()
            assert len(predictions) == 1
            assert predictions[0].prediction_type == "rain"
            assert predictions[0].result == "Rain Expected"
            assert predictions[0].probability == 0.72

    def test_prediction_is_linked_to_the_weather_record(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        with app.app_context():
            prediction = Prediction.query.first()
            assert prediction.weather_record is not None
            assert prediction.weather_record.location.name == "Chennai"

    def test_refreshing_does_not_duplicate_the_prediction(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        visit_dashboard(client)
        visit_dashboard(client)
        with app.app_context():
            assert Prediction.query.count() == 1

    def test_no_prediction_row_when_ml_is_unavailable(self):
        app, client = logged_in_client()
        visit_dashboard(client, prediction=None)
        with app.app_context():
            assert Prediction.query.count() == 0


class TestRiskPersistence:
    def test_all_three_risk_categories_are_persisted(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        with app.app_context():
            types = {row.risk_type for row in RiskAssessment.query.all()}
            assert types == {"Flood", "Heatwave", "Heavy rain"}

    def test_risk_levels_match_the_centralized_rules(self):
        """humidity 78 -> Moderate flood, temp 32 -> High heat, rain 70 -> Moderate."""
        app, client = logged_in_client()
        visit_dashboard(client)
        with app.app_context():
            levels = {row.risk_type: row.risk_level for row in RiskAssessment.query.all()}
            assert levels["Flood"] == "Moderate"
            assert levels["Heatwave"] == "High"
            assert levels["Heavy rain"] == "Moderate"

    def test_risk_assessment_stores_owner_and_details(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        with app.app_context():
            row = RiskAssessment.query.filter_by(risk_type="Heatwave").first()
            assert row.user_id is not None
            assert row.location_id is not None
            assert row.details
            assert row.risk_score and row.risk_score > 0

    def test_critical_heatwave_is_stored_with_its_level(self):
        app, client = logged_in_client()
        visit_dashboard(client, weather=weather_for(temperature=39.0))
        with app.app_context():
            row = RiskAssessment.query.filter_by(risk_type="Heatwave").first()
            assert row.risk_level == "Critical"

    def test_risk_rows_are_not_duplicated_on_refresh(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        visit_dashboard(client)
        with app.app_context():
            assert RiskAssessment.query.count() == 3


# --------------------------------------------------------------------------
# Steps 4 + 5: alert generation and duplicate prevention
# --------------------------------------------------------------------------

class TestAlertGeneration:
    def test_flood_alert_is_persisted(self):
        app, client = logged_in_client()
        visit_dashboard(client, weather=weather_for(humidity=90.0, precipitation=18.0))
        with app.app_context():
            assert Alert.query.filter_by(alert_type="Flood").first() is not None

    def test_heatwave_alert_is_persisted(self):
        app, client = logged_in_client()
        visit_dashboard(client, weather=weather_for(temperature=39.0, humidity=40.0, rain_probability=5.0))
        with app.app_context():
            assert Alert.query.filter_by(alert_type="Heatwave").first() is not None

    def test_heavy_rain_alert_is_persisted(self):
        app, client = logged_in_client()
        visit_dashboard(client, weather=weather_for(rain_probability=85.0, humidity=40.0, temperature=20.0))
        with app.app_context():
            assert Alert.query.filter_by(alert_type="Heavy rain").first() is not None

    def test_alert_severity_is_stored(self):
        app, client = logged_in_client()
        visit_dashboard(client, weather=weather_for(temperature=39.0))
        with app.app_context():
            heatwave = Alert.query.filter_by(alert_type="Heatwave").first()
            assert heatwave.severity == "Critical"

    def test_alert_stores_message_owner_and_location(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        with app.app_context():
            alert = Alert.query.filter_by(alert_type="Heatwave").first()
            assert alert.message
            assert alert.user_id is not None
            assert alert.location_id is not None
            assert alert.is_read is False

    def test_existing_weather_alerts_are_also_persisted(self):
        """The existing Phase 1 weather warnings become persistent alerts too."""
        app, client = logged_in_client()
        visit_dashboard(client, weather=weather_for(temperature=39.0))
        with app.app_context():
            assert Alert.query.filter_by(alert_type="High Temperature").first() is not None

    def test_low_risk_weather_creates_no_disaster_alert(self):
        app, client = logged_in_client()
        calm = weather_for(temperature=21.0, humidity=40.0, precipitation=0.0, rain_probability=5.0, wind_speed=4.0)
        visit_dashboard(client, weather=calm)
        with app.app_context():
            assert Alert.query.count() == 0


class TestDuplicatePrevention:
    def test_refreshing_does_not_create_duplicate_alerts(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        first = None
        with app.app_context():
            first = Alert.query.count()
        visit_dashboard(client)
        visit_dashboard(client)
        with app.app_context():
            assert Alert.query.count() == first

    def test_generate_alerts_is_idempotent_within_the_window(self):
        app = build_app()
        with app.app_context():
            user_id, location_id, record_id = seed_context(app)
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            weather = weather_for()
            first = generate_alerts(user, location, weather)
            db.session.commit()
            second = generate_alerts(user, location, weather)
            db.session.commit()
            assert len(first) > 0
            assert second == []
            assert Alert.query.count() == len(first)

    def test_a_changed_severity_is_a_new_event(self):
        app = build_app()
        with app.app_context():
            user_id, location_id, _ = seed_context(app)
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            generate_alerts(user, location, weather_for(temperature=32.0, humidity=40.0, rain_probability=5.0))
            db.session.commit()
            # A heatwave that escalates to Critical must raise a new alert.
            generate_alerts(user, location, weather_for(temperature=39.0, humidity=40.0, rain_probability=5.0))
            db.session.commit()
            severities = {
                row.severity
                for row in Alert.query.filter_by(alert_type="Heatwave").all()
            }
            assert severities == {"High", "Critical"}

    def test_different_users_get_their_own_alerts(self):
        app = build_app()
        with app.app_context():
            user_id, location_id, _ = seed_context(app)
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            generate_alerts(user, location, weather_for())
            db.session.commit()
            before = Alert.query.count()
            other = User(name="Other", email="other@example.com")
            other.set_password(PASSWORD)
            db.session.add(other)
            db.session.commit()
            other_location = Location(user_id=other.id, name="Chennai", latitude=13.08, longitude=80.27)
            db.session.add(other_location)
            db.session.commit()
            generated = generate_alerts(other, other_location, weather_for())
            db.session.commit()
            assert len(generated) > 0
            assert Alert.query.count() > before

    def test_same_weather_twice_creates_no_new_alerts(self):
        """Regression: the risk "Heavy rain" alert and the Phase 1 "Heavy Rain"
        warning share a slug, so one storm must never raise two rain alerts."""
        app, client = logged_in_client()
        storm = weather_for(temperature=39.0, humidity=90.0, precipitation=18.0, rain_probability=85.0)
        visit_dashboard(client, weather=storm)
        with app.app_context():
            first = Alert.query.count()
        visit_dashboard(client, weather=storm)
        visit_dashboard(client, weather=storm)
        with app.app_context():
            assert Alert.query.count() == first

    def test_rain_slugs_never_produce_two_rain_alerts(self):
        app = build_app()
        with app.app_context():
            user_id, location_id, _ = seed_context(app)
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            storm = weather_for(temperature=39.0, humidity=90.0, precipitation=18.0, rain_probability=85.0)
            generate_alerts(user, location, storm)
            db.session.commit()
            rain_alerts = Alert.query.filter(Alert.alert_type.ilike("%rain%")).all()
            assert rain_alerts
            assert len({row.alert_type for row in rain_alerts}) == 1


# --------------------------------------------------------------------------
# Steps 6 + 7: alert history and read/unread
# --------------------------------------------------------------------------

class TestAlertHistory:
    def test_history_endpoint_returns_alerts(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        response = client.get("/api/alert-history")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["alerts"]
        first = payload["alerts"][0]
        assert first["alert_type"]
        assert first["severity"]
        assert first["message"]
        assert first["is_read"] is False
        assert first["created_at"]

    def test_history_is_newest_first(self):
        app = build_app()
        with app.app_context():
            user_id, location_id, _ = seed_context(app)
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            generate_alerts(user, location, weather_for(temperature=32.0, humidity=40.0, rain_probability=5.0))
            db.session.commit()
            generate_alerts(user, location, weather_for(temperature=39.0, humidity=40.0, rain_probability=5.0))
            db.session.commit()
            history = alert_history(user)
            timestamps = [row.created_at for row in history]
            assert timestamps == sorted(timestamps, reverse=True)

    def test_history_can_be_filtered_to_unread(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        alerts = client.get("/api/alert-history").get_json()["alerts"]
        client.post(f"/api/alert-history/{alerts[0]['id']}/read")
        unread = client.get("/api/alert-history?unread=true").get_json()["alerts"]
        assert all(row["is_read"] is False for row in unread)
        assert len(unread) == len(alerts) - 1

    def test_unread_count_is_reported(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        total = len(client.get("/api/alert-history").get_json()["alerts"])
        assert client.get("/api/alert-history").get_json()["unread_count"] == total

    def test_mark_all_as_read_endpoint(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        response = client.post("/api/alert-history/read-all")
        assert response.status_code == 200
        assert response.get_json()["unread_count"] == 0
        assert all(row["is_read"] for row in client.get("/api/alert-history").get_json()["alerts"])

    def test_dashboard_renders_the_alert_history(self):
        app, client = logged_in_client()
        response = visit_dashboard(client)
        body = response.get_data(as_text=True)
        assert "data-alert-history" in body
        assert "Alert history" in body
        assert "Heatwave" in body

    def test_dashboard_still_renders_the_phase1_sections(self):
        """The new section must not remove any existing dashboard content."""
        app, client = logged_in_client()
        body = visit_dashboard(client).get_data(as_text=True)
        assert "data-best-time" in body
        assert "risk-flood" in body and "risk-heat" in body and "risk-rain" in body
        assert "AI Rainfall Prediction" in body
        assert 'data-mode="farmer"' in body
        assert "Next seven days" in body


class TestReadUnread:
    def test_new_alert_starts_unread(self):
        app = build_app()
        with app.app_context():
            user_id, location_id, _ = seed_context(app)
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            generate_alerts(user, location, weather_for())
            db.session.commit()
            assert all(row.is_read is False for row in Alert.query.all())
            assert unread_alert_count(user) == Alert.query.count()

    def test_mark_single_alert_as_read(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        alert_id = client.get("/api/alert-history").get_json()["alerts"][0]["id"]
        response = client.post(f"/api/alert-history/{alert_id}/read")
        assert response.status_code == 200
        assert response.get_json()["alert"]["is_read"] is True
        with app.app_context():
            assert db.session.get(Alert, alert_id).is_read is True

    def test_marking_read_reduces_the_unread_count(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        alert_id = client.get("/api/alert-history").get_json()["alerts"][0]["id"]
        before = client.get("/api/alert-history").get_json()["unread_count"]
        client.post(f"/api/alert-history/{alert_id}/read")
        assert client.get("/api/alert-history").get_json()["unread_count"] == before - 1

    def test_marking_an_unknown_alert_returns_404(self):
        app, client = logged_in_client()
        assert client.post("/api/alert-history/999999/read").status_code == 404

    def test_dashboard_read_all_form_marks_everything_read(self):
        app, client = logged_in_client()
        visit_dashboard(client)
        response = client.post("/alerts/read-all")
        assert response.status_code == 302
        assert client.get("/api/alert-history").get_json()["unread_count"] == 0


# --------------------------------------------------------------------------
# Step 12: API security
# --------------------------------------------------------------------------

class TestAlertSecurity:
    def test_history_requires_login(self):
        app = build_app()
        assert app.test_client().get("/api/alert-history").status_code == 401

    def test_mark_as_read_requires_login(self):
        app = build_app()
        assert app.test_client().post("/api/alert-history/1/read").status_code == 401

    def test_read_all_requires_login(self):
        app = build_app()
        assert app.test_client().post("/api/alert-history/read-all").status_code == 401

    def test_preferences_require_login(self):
        app = build_app()
        client = app.test_client()
        assert client.get("/api/notification-preferences").status_code == 401
        assert client.post("/api/notification-preferences", json={}).status_code == 401

    def test_history_never_exposes_another_users_alerts(self):
        app = build_app()
        first = register_and_login(app, "first@example.com")
        visit_dashboard(first)
        second = register_and_login(app, "second@example.com")
        response = second.get("/api/alert-history")
        assert response.status_code == 200
        assert response.get_json()["alerts"] == []

    def test_user_cannot_modify_another_users_alert(self):
        app = build_app()
        first = register_and_login(app, "first@example.com")
        visit_dashboard(first)
        with app.app_context():
            other_id = Alert.query.first().id
        second = register_and_login(app, "second@example.com")
        response = second.post(f"/api/alert-history/{other_id}/read")
        assert response.status_code == 404
        with app.app_context():
            assert db.session.get(Alert, other_id).is_read is False

    def test_read_all_does_not_touch_another_users_alerts(self):
        app = build_app()
        first = register_and_login(app, "first@example.com")
        visit_dashboard(first)
        second = register_and_login(app, "second@example.com")
        second.post("/api/alert-history/read-all")
        with app.app_context():
            assert all(row.is_read is False for row in Alert.query.all())

    def test_user_cannot_use_another_users_location_id(self):
        app = build_app()
        first = register_and_login(app, "first@example.com")
        visit_dashboard(first)
        with app.app_context():
            other_location_id = Location.query.first().id
        second = register_and_login(app, "second@example.com")
        response = second.get(f"/api/notification-preferences?location_id={other_location_id}")
        assert response.status_code == 404


# --------------------------------------------------------------------------
# Step 8: notification preferences
# --------------------------------------------------------------------------

class TestNotificationPreferences:
    def test_defaults_are_created_on_first_read(self):
        app, client = logged_in_client()
        response = client.get("/api/notification-preferences")
        assert response.status_code == 200
        preferences = response.get_json()["preferences"]
        assert preferences["email_enabled"] is True
        assert preferences["sms_enabled"] is False
        assert "flood" in preferences["alert_types"]
        with app.app_context():
            assert NotificationPreference.query.count() == 1

    def test_preferences_can_be_created(self):
        app, client = logged_in_client()
        response = client.post(
            "/api/notification-preferences",
            json={"email_enabled": False, "sms_enabled": True, "alert_types": ["flood", "heatwave"]},
        )
        assert response.status_code == 200
        preferences = response.get_json()["preferences"]
        assert preferences["email_enabled"] is False
        assert preferences["sms_enabled"] is True
        assert preferences["alert_types"] == ["flood", "heatwave"]

    def test_preferences_can_be_updated(self):
        app, client = logged_in_client()
        client.post("/api/notification-preferences", json={"email_enabled": True, "sms_enabled": True})
        response = client.post("/api/notification-preferences", json={"sms_enabled": False})
        assert response.get_json()["preferences"]["sms_enabled"] is False

    def test_preferences_are_persisted(self):
        app, client = logged_in_client()
        client.post("/api/notification-preferences", json={"alert_types": ["heatwave"]})
        with app.app_context():
            assert NotificationPreference.query.first().alert_types == "heatwave"

    def test_preferences_are_retrieved_after_saving(self):
        app, client = logged_in_client()
        client.post("/api/notification-preferences", json={"email_enabled": False})
        assert client.get("/api/notification-preferences").get_json()["preferences"]["email_enabled"] is False

    def test_preferences_are_isolated_between_users(self):
        app = build_app()
        first = register_and_login(app, "first@example.com")
        first.post("/api/notification-preferences", json={"sms_enabled": True})
        second = register_and_login(app, "second@example.com")
        assert second.get("/api/notification-preferences").get_json()["preferences"]["sms_enabled"] is False

    def test_profile_page_saves_preferences(self):
        app, client = logged_in_client()
        response = client.post(
            "/profile",
            data={"email_enabled": "on", "sms_enabled": "on", "alert_types": ["flood", "heatwave"]},
        )
        assert response.status_code == 302
        with app.app_context():
            stored = NotificationPreference.query.first()
            assert stored.sms_enabled is True
            assert stored.alert_types == "flood,heatwave"

    def test_profile_page_renders_the_preferences_form(self):
        app, client = logged_in_client()
        body = client.get("/profile").get_data(as_text=True)
        assert "Notification preferences" in body
        assert 'name="alert_types"' in body
        assert 'name="sms_enabled"' in body

    def test_disabled_alert_type_is_not_persisted(self):
        """A user who turns off heatwave alerts must not get heatwave alerts."""
        app = build_app()
        with app.app_context():
            user_id, location_id, _ = seed_context(app)
        client = app.test_client()
        client.post("/login", data={"email": "seed@example.com", "password": PASSWORD})
        client.post("/api/notification-preferences", json={"alert_types": ["flood", "heavy_rain"]})
        with app.app_context():
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            storm = weather_for(temperature=39.0, humidity=90.0, precipitation=18.0, rain_probability=5.0)
            generate_alerts(user, location, storm)
            db.session.commit()
            assert Alert.query.filter_by(alert_type="Heatwave").first() is None
            assert Alert.query.filter_by(alert_type="Flood").first() is not None


# --------------------------------------------------------------------------
# Step 9: integration of the whole workflow
# --------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_weather_to_risk_to_alert_persistence(self):
        app, client = logged_in_client()
        weather = weather_for(temperature=39.0, humidity=90.0, precipitation=18.0, rain_probability=85.0)
        assert visit_dashboard(client, weather=weather).status_code == 200
        with app.app_context():
            assert Prediction.query.count() == 1
            assert RiskAssessment.query.count() == 3
            types = {row.alert_type for row in Alert.query.all()}
            assert {"Flood", "Heatwave", "Heavy rain"} <= types

    def test_process_weather_observations_runs_the_full_chain(self):
        app = build_app()
        with app.app_context():
            user_id, location_id, record_id = seed_context(app)
            user = db.session.get(User, user_id)
            location = db.session.get(Location, location_id)
            record = db.session.get(WeatherRecord, record_id)
            result = process_weather_observations(
                user,
                location,
                weather_for(temperature=39.0),
                weather_record=record,
                rain_prediction=RAIN_PREDICTION,
            )
            assert result["prediction"] is not None
            assert len(result["risk_assessments"]) == 3
            assert len(result["alerts"]) > 0
            assert Prediction.query.count() == 1
            assert Alert.query.count() > 0

    def test_weather_failure_does_not_break_the_dashboard(self):
        from services.weather_service import WeatherServiceError

        app, client = logged_in_client()
        with patch("app.get_weather", side_effect=WeatherServiceError("unavailable")):
            response = client.get("/dashboard?city=Chennai")
        # The weather error path must still render the page, not crash.
        assert response.status_code == 200
        assert "data-best-time" not in response.get_data(as_text=True)
        assert "weather-empty" in response.get_data(as_text=True)

    def test_existing_weather_alert_endpoint_still_works(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=weather_for()):
            response = client.get("/api/alerts?city=Chennai")
        assert response.status_code == 200
        assert "alerts" in response.get_json()

    def test_persistence_helpers_ignore_missing_arguments(self):
        """The service must never raise when the workflow is partially complete."""
        app = build_app()
        with app.app_context():
            assert persist_prediction(None, None, None, None) is None
            assert persist_risk_assessments(None, None, None) == []
            assert generate_alerts(None, None, None) == []
            assert alert_history(None) == []
            assert unread_alert_count(None) == 0
