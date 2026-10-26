"""Tests for Phase 3: email, SMS, scheduling, personalization, and the
context-aware assistant.

Nothing here sends a real message. Email and SMS are exercised through the
standard library / requests seams with the providers either unconfigured
(graceful failure) or stubbed (delivery recorded as ``sent``).
"""

import logging
from unittest.mock import patch

import pytest
import requests

from app import create_app
from models import Alert, Location, NotificationPreference, User, WeatherRecord, db
from services import notifications
from services.alerts import generate_alerts
from services.assistant_context import is_follow_up, new_context, resolve_question, update_context
from services.notifications import (
    CHANNEL_EMAIL,
    CHANNEL_SMS,
    DELIVERY_STATUSES,
    STATUS_DISABLED,
    STATUS_FAILED,
    STATUS_SENT,
    STATUS_SKIPPED,
    STATUS_UNAVAILABLE,
    build_alert_email,
    build_sms_message,
    deliver_alert_notifications,
    mask_recipient,
    normalize_phone,
    send_email,
    send_sms,
)
from services.personalization import personalized_guidance
from services.risk import assess_risks
from services.scheduler import run_scheduled_alert_check
from services.weather_service import WeatherServiceError

PASSWORD = "strong-pass-123"

MAIL_ENV = ("MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_USE_TLS", "MAIL_USE_SSL")
SMS_ENV = ("SMS_PROVIDER", "SMS_API_KEY", "SMS_API_SECRET", "SMS_FROM", "SMS_ENDPOINT")


@pytest.fixture(autouse=True)
def clean_provider_env(monkeypatch):
    """Every test starts with no mail or SMS provider configured."""
    for name in MAIL_ENV + SMS_ENV:
        monkeypatch.delenv(name, raising=False)


def build_app():
    return create_app(
        {"TESTING": True, "SECRET_KEY": "test-secret", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
    )


def register_and_login(app, email, name="Student"):
    client = app.test_client()
    client.post(
        "/register",
        data={"name": name, "email": email, "password": PASSWORD, "confirm_password": PASSWORD},
    )
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def logged_in_client(email="phase3@example.com"):
    app = build_app()
    return app, register_and_login(app, email)


def weather_for(temperature=32.0, humidity=78.0, precipitation=1.2, rain_probability=70.0, wind_speed=14.0):
    return {
        "location": {"name": "Chennai", "country": "India", "latitude": 13.08, "longitude": 80.27},
        "current": {
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "precipitation": precipitation,
            "feels_like": temperature + 2,
            "condition": "Rain",
            "pressure": 1005.0,
            "wind_direction": 180,
        },
        "forecast": [
            {
                "date": "Mon, Aug 31",
                "condition": "Rain",
                "temperature_min": 27.0,
                "temperature_max": temperature,
                "rain_probability": rain_probability,
                "precipitation": precipitation,
            }
        ],
        "hourly": [],
    }


RAIN_PREDICTION = {
    "probability": 0.8,
    "probability_percent": 80,
    "prediction": "Rain Expected",
    "risk_level": "High",
    "factors": [{"name": "Humidity", "importance": 0.5}],
    "model_name": "Random Forest",
}


def seed_alert(app, email="seed@example.com", severity="High", alert_type="Flood"):
    """Create a user with one persistent alert, and return the ids."""
    with app.app_context():
        user = User(name="Student", email=email)
        user.set_password(PASSWORD)
        user.email = email
        db.session.add(user)
        db.session.commit()
        location = Location(user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27)
        db.session.add(location)
        db.session.commit()
        record = WeatherRecord(location_id=location.id, temperature=30.0)
        db.session.add(record)
        db.session.commit()
        alert = Alert(
            user_id=user.id,
            location_id=location.id,
            alert_type=alert_type,
            severity=severity,
            message="Flood risk is High. Elevated runoff and drainage stress likely.",
            is_read=False,
        )
        db.session.add(alert)
        db.session.commit()
        return user.id, location.id, alert.id


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------

class TestEmailService:
    def test_email_content_contains_alert_information(self):
        app = build_app()
        user_id, location_id, alert_id = seed_alert(app)
        with app.app_context():
            user = db.session.get(User, user_id)
            alert = db.session.get(Alert, alert_id)
            location = db.session.get(Location, location_id)
            content = build_alert_email(alert, user=user, location=location, weather=weather_for())
        assert "Chennai" in content["text"]
        assert "Flood" in content["text"]
        assert "HIGH" in content["text"]
        assert "Rain probability today" in content["text"]
        assert "Recommendation" in content["text"]
        assert "Weather AI" in content["text"]
        assert "not an official emergency" in content["text"]
        assert content["recipient"] == "seed@example.com"

    def test_missing_smtp_config_is_graceful(self):
        result = send_email("someone@example.com", "Subject", "Body")
        assert result.status == STATUS_UNAVAILABLE
        assert result.delivered is False
        assert result.channel == CHANNEL_EMAIL

    def test_missing_smtp_config_logs_without_credentials(self, caplog):
        with caplog.at_level(logging.WARNING, logger="services.notifications"):
            send_email("someone@example.com", "Subject", "Body")
        text = caplog.text
        assert "not configured" in text
        assert "someone@example.com" not in text
        assert "s***@example.com" in text

    def test_no_recipient_is_skipped(self):
        assert send_email("", "Subject", "Body").status == STATUS_SKIPPED

    def test_configured_email_is_sent(self, monkeypatch):
        monkeypatch.setenv("MAIL_SERVER", "smtp.example.com")
        monkeypatch.setenv("MAIL_FROM", "alerts@weather.ai")
        with patch("services.notifications.smtplib.SMTP") as smtp:
            result = send_email("someone@example.com", "Subject", "Body")
        assert result.status == STATUS_SENT
        assert result.delivered is True
        smtp.assert_called_once()

    def test_smtp_error_is_reported_as_failed(self, monkeypatch):
        monkeypatch.setenv("MAIL_SERVER", "smtp.example.com")
        monkeypatch.setenv("MAIL_FROM", "alerts@weather.ai")
        import smtplib

        with patch("services.notifications.smtplib.SMTP", side_effect=smtplib.SMTPException("boom")):
            result = send_email("someone@example.com", "Subject", "Body")
        assert result.status == STATUS_FAILED
        assert result.delivered is False

    def test_safe_summary_never_exposes_the_password(self, monkeypatch):
        monkeypatch.setenv("MAIL_SERVER", "smtp.example.com")
        monkeypatch.setenv("MAIL_USERNAME", "mailer@weather.ai")
        monkeypatch.setenv("MAIL_PASSWORD", "super-secret-value")
        summary = notifications.email_config().safe_summary()
        rendered = repr(summary)
        assert "super-secret-value" not in rendered
        assert summary["configured"] is True
        assert "m***@weather.ai" == summary["sender"]

    def test_email_disabled_is_not_attempted(self):
        app = build_app()
        user_id, _, alert_id = seed_alert(app)
        with app.app_context():
            preference = NotificationPreference(
                user_id=user_id, location_id=None, email_enabled=False, sms_enabled=False
            )
            db.session.add(preference)
            db.session.commit()
            user = db.session.get(User, user_id)
            alert = db.session.get(Alert, alert_id)
            with patch("services.notifications.send_email") as sender:
                summary = deliver_alert_notifications(user, alert)
        sender.assert_not_called()
        assert summary.email.status == STATUS_DISABLED
        assert summary.any_delivered is False

    def test_email_enabled_attempts_delivery(self):
        app = build_app()
        user_id, _, alert_id = seed_alert(app)
        with app.app_context():
            preference = NotificationPreference(
                user_id=user_id, location_id=None, email_enabled=True, sms_enabled=False
            )
            db.session.add(preference)
            db.session.commit()
            user = db.session.get(User, user_id)
            alert = db.session.get(Alert, alert_id)
            with patch("services.notifications.send_email") as sender:
                sender.return_value = notifications.NotificationResult(
                    CHANNEL_EMAIL, STATUS_SENT, "Email sent.", "s***@example.com"
                )
                summary = deliver_alert_notifications(user, alert)
        sender.assert_called_once()
        assert summary.email.status == STATUS_SENT
        assert summary.any_delivered is True


# --------------------------------------------------------------------------
# SMS
# --------------------------------------------------------------------------

class TestSmsService:
    def _alert(self, app):
        user_id, location_id, alert_id = seed_alert(app)
        with app.app_context():
            return db.session.get(Alert, alert_id)

    def test_missing_provider_config_is_graceful(self):
        app = build_app()
        alert = self._alert(app)
        result = send_sms("+919876543210", alert)
        assert result.status == STATUS_UNAVAILABLE
        assert result.delivered is False
        assert result.channel == CHANNEL_SMS

    def test_no_phone_number_is_skipped(self):
        app = build_app()
        alert = self._alert(app)
        assert send_sms("", alert).status == STATUS_SKIPPED
        assert send_sms("123", alert).status == STATUS_SKIPPED

    def test_mock_provider_is_not_treated_as_configured(self, monkeypatch):
        monkeypatch.setenv("SMS_PROVIDER", "mock")
        monkeypatch.setenv("SMS_ENDPOINT", "https://sms.example.com/send")
        monkeypatch.setenv("SMS_API_KEY", "dev-key")
        assert notifications.sms_config().configured is False

    def test_configured_provider_posts_the_message(self, monkeypatch):
        monkeypatch.setenv("SMS_PROVIDER", "http")
        monkeypatch.setenv("SMS_ENDPOINT", "https://sms.example.com/send")
        monkeypatch.setenv("SMS_API_KEY", "test-key")
        app = build_app()
        alert = self._alert(app)
        with patch("services.notifications.requests.post") as post:
            post.return_value = requests.Response()
            post.return_value.status_code = 200
            result = send_sms("+919876543210", alert)
        assert result.status == STATUS_SENT
        assert result.delivered is True
        post.assert_called_once()

    def test_provider_failure_is_reported_as_failed(self, monkeypatch):
        monkeypatch.setenv("SMS_PROVIDER", "http")
        monkeypatch.setenv("SMS_ENDPOINT", "https://sms.example.com/send")
        monkeypatch.setenv("SMS_API_KEY", "test-key")
        app = build_app()
        alert = self._alert(app)
        with patch("services.notifications.requests.post", side_effect=requests.RequestException("down")):
            result = send_sms("+919876543210", alert)
        assert result.status == STATUS_FAILED
        assert result.delivered is False

    def test_sms_summary_never_exposes_keys(self, monkeypatch):
        monkeypatch.setenv("SMS_PROVIDER", "http")
        monkeypatch.setenv("SMS_ENDPOINT", "https://sms.example.com/send")
        monkeypatch.setenv("SMS_API_KEY", "sms-secret-key")
        monkeypatch.setenv("SMS_API_SECRET", "sms-secret-value")
        summary = notifications.sms_config().safe_summary()
        rendered = repr(summary)
        assert "sms-secret-key" not in rendered
        assert "sms-secret-value" not in rendered
        assert summary["has_api_key"] is True

    def test_sms_message_contains_alert_information(self):
        app = build_app()
        _, location_id, alert_id = seed_alert(app)
        with app.app_context():
            alert = db.session.get(Alert, alert_id)
            location = db.session.get(Location, location_id)
            body = build_sms_message(alert, location=location)
        assert "Flood" in body
        assert "Chennai" in body
        assert len(body) <= 481

    def test_sms_disabled_is_not_attempted(self):
        app = build_app()
        user_id, _, alert_id = seed_alert(app)
        with app.app_context():
            preference = NotificationPreference(
                user_id=user_id, location_id=None, email_enabled=False, sms_enabled=False
            )
            db.session.add(preference)
            db.session.commit()
            user = db.session.get(User, user_id)
            user.phone = "+919876543210"
            db.session.commit()
            alert = db.session.get(Alert, alert_id)
            with patch("services.notifications.send_sms") as sender:
                summary = deliver_alert_notifications(user, alert)
        sender.assert_not_called()
        assert summary.sms.status == STATUS_DISABLED

    def test_sms_enabled_attempts_delivery(self):
        app = build_app()
        user_id, _, alert_id = seed_alert(app)
        with app.app_context():
            preference = NotificationPreference(
                user_id=user_id, location_id=None, email_enabled=False, sms_enabled=True
            )
            db.session.add(preference)
            user = db.session.get(User, user_id)
            user.phone = "+919876543210"
            db.session.commit()
            alert = db.session.get(Alert, alert_id)
            with patch("services.notifications.send_sms") as sender:
                sender.return_value = notifications.NotificationResult(
                    CHANNEL_SMS, STATUS_SENT, "SMS sent.", "****3210"
                )
                summary = deliver_alert_notifications(user, alert)
        sender.assert_called_once()
        assert summary.sms.status == STATUS_SENT

    def test_phone_normalisation(self):
        assert normalize_phone("+91 98765 43210") == "+919876543210"
        assert normalize_phone("9876543210") == "+9876543210"
        assert normalize_phone("123") == ""
        assert normalize_phone("") == ""

    def test_recipient_masking(self):
        assert mask_recipient("alice@example.com") == "a***@example.com"
        assert "+919876543210" not in mask_recipient("+919876543210")
        assert mask_recipient("+919876543210") == "****3210"

    def test_all_statuses_are_declared(self):
        for status in (STATUS_SENT, STATUS_DISABLED, STATUS_UNAVAILABLE, STATUS_FAILED, STATUS_SKIPPED):
            assert status in DELIVERY_STATUSES


# --------------------------------------------------------------------------
# Scheduler
# --------------------------------------------------------------------------

STORM = weather_for(temperature=39.0, humidity=90.0, precipitation=18.0, rain_probability=85.0)
CALM = weather_for(temperature=21.0, humidity=40.0, precipitation=0.0, rain_probability=5.0, wind_speed=4.0)


class TestScheduler:
    def _subscribed_user(self, app, email="sched@example.com", seed_type="Flood"):
        user_id, location_id, _ = seed_alert(app, email=email, alert_type=seed_type)
        with app.app_context():
            db.session.add(
                NotificationPreference(
                    user_id=user_id, location_id=None, email_enabled=True, sms_enabled=False
                )
            )
            db.session.commit()
        return user_id, location_id

    def test_scheduled_check_creates_alerts(self):
        app = build_app()
        self._subscribed_user(app)
        with app.app_context():
            seeded = Alert.query.count()
            report = run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            assert report.users_checked == 1
            assert report.alerts_created > 0
            assert report.weather_failures == 0
            # The scheduler adds its own alerts on top of the seeded one.
            assert Alert.query.count() == seeded + report.alerts_created

    def test_scheduled_check_does_not_duplicate_alerts(self):
        app = build_app()
        self._subscribed_user(app)
        with app.app_context():
            run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            first = Alert.query.count()
            run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            assert Alert.query.count() == first
            assert first > 0

    def test_scheduled_check_reuses_the_risk_service(self):
        """The scheduler must not define its own thresholds."""
        app = build_app()
        self._subscribed_user(app)
        with app.app_context():
            with patch("services.alerts.assess_risks", wraps=assess_risks) as assessor:
                run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            assert assessor.called

    def test_scheduled_check_respects_disabled_alert_types(self):
        app = build_app()
        # Seed an unrelated alert type so the assertion only sees new alerts.
        user_id, location_id = self._subscribed_user(app, seed_type="Strong wind")
        with app.app_context():
            preference = NotificationPreference.query.filter_by(user_id=user_id).first()
            preference.alert_types = "heavy_rain"
            db.session.commit()
            run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            types = {row.alert_type for row in Alert.query.all()}
        assert "Flood" not in types
        assert "Heatwave" not in types
        assert "Heavy rain" in types

    def test_weather_failure_does_not_crash_the_scheduler(self):
        app = build_app()
        self._subscribed_user(app)

        def failing(name):
            raise WeatherServiceError("The weather service is temporarily unavailable.")

        with app.app_context():
            report = run_scheduled_alert_check(weather_fetcher=failing)
            assert report.weather_failures == 1
            assert report.alerts_created == 0
            assert report.errors

    def test_unexpected_weather_error_is_contained(self):
        app = build_app()
        self._subscribed_user(app)

        def boom(name):
            raise ValueError("unexpected")

        with app.app_context():
            report = run_scheduled_alert_check(weather_fetcher=boom)
            assert report.weather_failures == 1

    def test_alert_generation_failure_is_contained(self):
        app = build_app()
        self._subscribed_user(app)
        with app.app_context():
            with patch("services.alerts.generate_alerts", side_effect=RuntimeError("db down")):
                report = run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            assert report.alerts_created == 0
            assert report.errors

    def test_delivery_outcome_is_reported_not_claimed(self):
        app = build_app()
        self._subscribed_user(app)
        with app.app_context():
            report = run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            # No provider is configured, so nothing may be reported as sent.
            assert report.notifications_sent == 0
            assert report.notifications_unavailable > 0

    def test_user_without_a_location_is_skipped(self):
        app = build_app()
        with app.app_context():
            user = User(name="NoLocation", email="nolocation@example.com")
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.commit()
            db.session.add(
                NotificationPreference(user_id=user.id, location_id=None, email_enabled=True)
            )
            db.session.commit()
            report = run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            assert report.locations_checked == 0

    def test_scheduler_is_a_plain_callable_not_a_background_thread(self):
        """No import of create_app at module import time means no auto-start."""
        import services.scheduler as scheduler_module

        assert not hasattr(scheduler_module, "_scheduler_thread")
        assert callable(scheduler_module.run_scheduled_alert_check)


# --------------------------------------------------------------------------
# Notification preferences API and security
# --------------------------------------------------------------------------

class TestNotificationPreferencesApi:
    def test_anonymous_requests_are_rejected(self):
        client = build_app().test_client()
        assert client.get("/api/notification-preferences").status_code == 401
        assert client.post("/api/notification-preferences", json={}).status_code == 401
        assert client.get("/api/notification-status").status_code == 401
        assert client.post("/api/notifications/run-check", json={}).status_code == 401

    def test_authenticated_get_returns_defaults(self):
        app, client = logged_in_client()
        response = client.get("/api/notification-preferences")
        assert response.status_code == 200
        preferences = response.get_json()["preferences"]
        assert preferences["email_enabled"] is True
        assert preferences["sms_enabled"] is False

    def test_authenticated_post_saves_preferences(self):
        app, client = logged_in_client()
        response = client.post(
            "/api/notification-preferences",
            json={"email_enabled": False, "sms_enabled": True, "alert_types": ["flood"]},
        )
        assert response.status_code == 200
        assert response.get_json()["preferences"]["email_enabled"] is False
        with app.app_context():
            stored = NotificationPreference.query.first()
            assert stored.email_enabled is False
            assert stored.sms_enabled is True
            assert stored.alert_types == "flood"

    def test_preferences_are_isolated_between_users(self):
        app = build_app()
        first = register_and_login(app, "first@example.com")
        first.post("/api/notification-preferences", json={"sms_enabled": True})
        second = register_and_login(app, "second@example.com")
        assert second.get("/api/notification-preferences").get_json()["preferences"]["sms_enabled"] is False

    def test_phone_is_normalized_and_masked(self):
        app, client = logged_in_client()
        response = client.post("/api/notification-preferences", json={"phone": "+91 98765 43210"})
        assert response.get_json()["preferences"]["phone"] == "****3210"
        with app.app_context():
            assert db.session.query(User).first().phone == "+919876543210"

    def test_invalid_phone_is_not_stored(self):
        app, client = logged_in_client()
        response = client.post("/api/notification-preferences", json={"phone": "abc"})
        assert response.status_code == 200
        with app.app_context():
            assert db.session.query(User).first().phone is None

    def test_invalid_language_falls_back_to_english(self):
        app, client = logged_in_client()
        response = client.post("/api/notification-preferences", json={"preferred_language": "xx"})
        assert response.get_json()["preferences"]["preferred_language"] == "en"

    def test_malformed_request_is_handled_safely(self):
        app, client = logged_in_client()
        response = client.post(
            "/api/notification-preferences", data="not json", content_type="application/json"
        )
        assert response.status_code == 200
        assert "preferences" in response.get_json()

    def test_notification_status_never_leaks_secrets(self, monkeypatch):
        monkeypatch.setenv("MAIL_SERVER", "smtp.example.com")
        monkeypatch.setenv("MAIL_USERNAME", "mailer@weather.ai")
        monkeypatch.setenv("MAIL_PASSWORD", "top-secret-password")
        monkeypatch.setenv("SMS_PROVIDER", "http")
        monkeypatch.setenv("SMS_ENDPOINT", "https://sms.example.com")
        monkeypatch.setenv("SMS_API_KEY", "top-secret-key")
        app, client = logged_in_client()
        response = client.get("/api/notification-status")
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "top-secret-password" not in body
        assert "top-secret-key" not in body

    def test_foreign_location_id_is_rejected(self):
        app = build_app()
        first = register_and_login(app, "first@example.com")
        with patch("app.get_weather", return_value=STORM), patch("app.predict_rain", return_value=None):
            first.get("/dashboard?city=Chennai")
        with app.app_context():
            other_location_id = Location.query.first().id
        second = register_and_login(app, "second@example.com")
        response = second.get(f"/api/notification-preferences?location_id={other_location_id}")
        assert response.status_code == 404


    def test_profile_page_renders_phase3_controls(self):
        app, client = logged_in_client()
        body = client.get("/profile").get_data(as_text=True)
        assert "Notification preferences" in body
        assert 'name="sms_enabled"' in body
        assert 'name="phone"' in body
        assert "Delivery status" in body

    def test_profile_page_saves_everything(self):
        app, client = logged_in_client()
        response = client.post(
            "/profile",
            data={
                "email_enabled": "on",
                "sms_enabled": "on",
                "phone": "+919876543210",
                "preferred_language": "hi",
                "preferred_mode": "travel",
                "alert_types": ["flood", "heatwave"],
            },
        )
        assert response.status_code == 302
        with app.app_context():
            user = db.session.query(User).first()
            assert user.phone == "+919876543210"
            assert user.preferred_language == "hi"
            assert user.preferred_mode == "travel"
            assert NotificationPreference.query.first().alert_types == "flood,heatwave"

    def test_profile_page_gives_feedback_after_saving(self):
        app, client = logged_in_client()
        response = client.post("/profile", data={"email_enabled": "on"}, follow_redirects=True)
        assert response.status_code == 200
        assert "saved" in response.get_data(as_text=True).lower()


# --------------------------------------------------------------------------
# Assistant: context, intents, personalization, languages
# --------------------------------------------------------------------------

def ask(client, question, weather=None, city="Chennai", prediction=RAIN_PREDICTION):
    weather = weather or STORM
    with patch("app.get_weather", return_value=weather), patch("app.predict_rain", return_value=prediction):
        return client.post("/api/assistant", json={"city": city, "question": question})


class TestAssistantContext:
    def test_first_question_is_not_a_follow_up(self):
        app, client = logged_in_client()
        response = ask(client, "Will it rain today?")
        assert response.status_code == 200
        assert response.get_json()["context_used"] is False

    def test_follow_up_reuses_the_previous_location(self):
        app, client = logged_in_client()
        vijayawada = {**STORM, "location": {**STORM["location"], "name": "Vijayawada Rural"}}
        ask(client, "Will it rain today?", weather=vijayawada, city="Vijayawada Rural")
        with patch("app.get_weather", return_value=vijayawada) as getter, patch(
            "app.predict_rain", return_value=RAIN_PREDICTION
        ):
            response = client.post("/api/assistant", json={"question": "What about tomorrow?"})
        assert response.status_code == 200
        assert response.get_json()["context_used"] is True
        assert "Vijayawada Rural" in response.get_json()["answer"]
        getter.assert_called_once_with("Vijayawada Rural")

    def test_existing_intents_still_work(self):
        app, client = logged_in_client()
        expectations = {
            "What's the weather today?": "current_weather",
            "Will it rain?": "rain",
            "What is the 7 day forecast?": "forecast",
            "What is the temperature?": "temperature",
            "What is the humidity?": "humidity",
            "What is the wind like?": "wind",
            "What is the risk?": "risk",
            "When is the best time?": "best_time",
            "Explain the ML prediction": "ml_explanation",
        }
        for question, intent in expectations.items():
            response = ask(client, question)
            assert response.status_code == 200, question
            assert response.get_json()["intent"] == intent, question

    def test_mode_aware_response(self):
        app, client = logged_in_client()
        response = ask(client, "Give me advice for today.")
        assert response.status_code == 200
        assert response.get_json()["recommendation"]
        assert response.get_json()["user_mode"] == "general"

    def test_risk_response_uses_the_rule_service(self):
        app, client = logged_in_client()
        answer = ask(client, "What is the risk?").get_json()["answer"].lower()
        assert "flood" in answer and "heatwave" in answer

    def test_assistant_works_without_any_optional_provider(self):
        """No LLM is integrated, so the rule-based answer must always work."""
        app, client = logged_in_client()
        assert ask(client, "What's the weather today?").get_json()["answer"]

    def test_empty_question_is_still_rejected(self):
        app, client = logged_in_client()
        assert client.post("/api/assistant", json={"city": "Chennai", "question": ""}).status_code == 400

    def test_missing_location_is_still_rejected(self):
        app, client = logged_in_client()
        assert client.post("/api/assistant", json={"question": "What's the weather today?"}).status_code == 400

    def test_assistant_requires_login(self):
        app = build_app()
        assert app.test_client().post("/api/assistant", json={"question": "hi"}).status_code == 401

    def test_alerts_are_surfaced_to_the_assistant(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=STORM), patch("app.predict_rain", return_value=RAIN_PREDICTION):
            client.get("/dashboard?city=Chennai")
        assert ask(client, "What's the weather today?").get_json()["alerts"]


class TestAssistantContextHelpers:
    def test_is_follow_up_detects_continuations(self):
        assert is_follow_up("What about tomorrow?")
        assert is_follow_up("and today")
        assert not is_follow_up("What is the seven day forecast for Hyderabad?")

    def test_resolve_question_uses_remembered_city(self):
        context = new_context(city="Chennai", intent="rain", language="en", mode="general")
        question, city, used = resolve_question("What about tomorrow?", context)
        assert city == "Chennai"
        assert used == "true"
        assert "tomorrow" in question

    def test_resolve_question_without_context_is_unchanged(self):
        question, city, used = resolve_question("What about tomorrow?", new_context())
        assert (city, used, question) == ("", "false", "What about tomorrow?")

    def test_update_context_remembers_a_contextual_turn(self):
        context = update_context(new_context(), "Chennai", "rain", "en", "general")
        assert context["intent"] == "rain"
        assert context["city"] == "Chennai"

    def test_update_context_keeps_previous_subject_for_other_intents(self):
        first = update_context(new_context(), "Chennai", "rain", "en", "general")
        assert update_context(first, "Chennai", "unsupported", "en", "general")["intent"] == "rain"


# --------------------------------------------------------------------------
# Personalization for all five modes
# --------------------------------------------------------------------------

MODES = ("general", "farmer", "travel", "daily_commute", "outdoor_activity")


class TestPersonalization:
    def test_every_mode_produces_guidance(self):
        for mode in MODES:
            guidance = personalized_guidance(STORM, RAIN_PREDICTION, user_mode=mode)
            assert guidance["mode"] == mode
            assert guidance["text"]

    def test_modes_produce_different_guidance(self):
        texts = {
            mode: personalized_guidance(STORM, RAIN_PREDICTION, user_mode=mode)["text"]
            for mode in MODES
        }
        assert len(set(texts.values())) == len(MODES)

    def test_farmer_guidance_mentions_farm_factors(self):
        text = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="farmer")["text"]
        assert "Rain probability" in text
        assert "Flood risk" in text

    def test_travel_guidance_mentions_heavy_rain(self):
        text = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="travel")["text"]
        assert "Heavy-rain risk" in text

    def test_outdoor_guidance_mentions_heat(self):
        text = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="outdoor_activity")["text"]
        assert "Temperature" in text
        assert "Heat stress" in text

    def test_commute_guidance_mentions_conditions(self):
        text = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="daily_commute")["text"]
        assert "Current conditions" in text

    def test_guidance_uses_the_rule_based_risk_levels(self):
        guidance = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="general")
        assert guidance["risk_levels"] == assess_risks(STORM)
        assert guidance["risk_levels"]["heatwave"] == "Critical"

    def test_guidance_uses_the_ml_estimate_when_available(self):
        guidance = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="farmer")
        assert guidance["uses_ml"] is True
        assert guidance["factors"]["ml_probability"] == 80

    def test_guidance_works_without_ml(self):
        guidance = personalized_guidance(STORM, None, user_mode="farmer")
        assert guidance["uses_ml"] is False
        assert guidance["text"]

    def test_active_alerts_are_contextualized(self):
        app = build_app()
        _, _, alert_id = seed_alert(app)
        with app.app_context():
            alert = db.session.get(Alert, alert_id)
            guidance = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="general", active_alerts=[alert])
        assert guidance["alerts_contextualized"] is True
        assert "Flood" in guidance["text"]

    def test_guidance_contains_no_medical_or_emergency_claims(self):
        forbidden = ("diagnos", "prescrib", "medication", "evacuate immediately", "life threatening")
        for mode in MODES:
            text = personalized_guidance(STORM, RAIN_PREDICTION, user_mode=mode)["text"].lower()
            for term in forbidden:
                assert term not in text

    def test_calm_weather_still_produces_guidance(self):
        for mode in MODES:
            assert personalized_guidance(CALM, None, user_mode=mode)["text"]


# --------------------------------------------------------------------------
# Multilingual
# --------------------------------------------------------------------------

class TestMultilingual:
    @pytest.mark.parametrize("language", ["en", "te", "hi"])
    def test_assistant_answers_in_each_language(self, language):
        app, client = logged_in_client()
        client.post("/api/language", json={"language": language})
        response = ask(client, "What's the weather today?")
        assert response.status_code == 200
        assert response.get_json()["answer"]

    @pytest.mark.parametrize("language", ["en", "te", "hi"])
    def test_personalized_guidance_is_translated(self, language):
        guidance = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="farmer", language=language)
        assert guidance["text"]
        if language == "en":
            assert "Rain probability" in guidance["text"]
        else:
            assert "Rain probability" not in guidance["text"]

    def test_unsupported_language_falls_back_to_english(self):
        guidance = personalized_guidance(STORM, RAIN_PREDICTION, user_mode="farmer", language="xx")
        assert "Rain probability" in guidance["text"]

    @pytest.mark.parametrize("language", ["en", "te", "hi"])
    def test_profile_page_renders_in_each_language(self, language):
        app, client = logged_in_client()
        client.post("/api/language", json={"language": language})
        body = client.get("/profile").get_data(as_text=True)
        # The label itself is translated, so assert on the stable markup instead.
        assert "delivery-status" in body
        assert 'name="sms_enabled"' in body
        assert 'name="phone"' in body
        assert 'name="alert_types"' in body


# --------------------------------------------------------------------------
# Integration and Phase 1 / Phase 2 regression
# --------------------------------------------------------------------------

class TestPhase3Integration:
    def test_weather_to_alert_to_delivery_pipeline(self):
        app = build_app()
        user_id, _, _ = seed_alert(app, email="integration@example.com")
        with app.app_context():
            db.session.add(
                NotificationPreference(
                    user_id=user_id, location_id=None, email_enabled=True, sms_enabled=True
                )
            )
            db.session.commit()
        with app.app_context():
            report = run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            assert report.alerts_created > 0
            # No provider is configured, so nothing may be reported as sent.
            assert report.notifications_sent == 0
            assert report.notifications_unavailable > 0
            assert Alert.query.count() == report.alerts_created + 1  # +1 seeded alert

    def test_dashboard_still_renders_all_phase1_sections(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=STORM), patch("app.predict_rain", return_value=RAIN_PREDICTION):
            body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert "data-best-time" in body
        assert "risk-flood" in body and "risk-heat" in body and "risk-rain" in body
        assert "data-alert-history" in body
        assert "AI Rainfall Prediction" in body
        for mode in MODES:
            assert f'data-mode="{mode}"' in body

    def test_dashboard_and_scheduler_share_the_same_alert_rules(self):
        """The scheduler must not invent a second alert path."""
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=STORM), patch("app.predict_rain", return_value=RAIN_PREDICTION):
            client.get("/dashboard?city=Chennai")
        with app.app_context():
            dashboard_count = Alert.query.count()
            assert dashboard_count > 0
            report = run_scheduled_alert_check(weather_fetcher=lambda name: STORM)
            assert report.alerts_created == 0
            assert Alert.query.count() == dashboard_count

    def test_registration_login_dashboard_logout(self):
        app = build_app()
        client = app.test_client()
        assert client.get("/").status_code == 200
        client.post(
            "/register",
            data={"name": "A", "email": "flow@example.com", "password": PASSWORD, "confirm_password": PASSWORD},
        )
        assert client.post("/login", data={"email": "flow@example.com", "password": PASSWORD}).status_code == 302
        assert client.get("/dashboard").status_code == 200
        assert client.get("/logout").status_code == 302
        assert client.get("/dashboard").status_code == 302

    def test_health_endpoint(self):
        assert build_app().test_client().get("/health").status_code == 200

    def test_mode_endpoints_still_work(self):
        app, client = logged_in_client()
        for mode in MODES:
            assert client.post("/api/user-mode", json={"mode": mode}).status_code == 200
        assert client.post("/api/user-mode", json={"mode": "invalid"}).status_code == 400

    def test_phase2_alert_history_still_works(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=STORM), patch("app.predict_rain", return_value=RAIN_PREDICTION):
            client.get("/dashboard?city=Chennai")
        history = client.get("/api/alert-history")
        assert history.status_code == 200
        alerts = history.get_json()["alerts"]
        assert alerts
        first = alerts[0]
        assert client.post(f"/api/alert-history/{first['id']}/read").status_code == 200
        assert client.post("/api/alert-history/read-all").get_json()["unread_count"] == 0
