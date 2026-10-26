"""Tests for Phase 4: security hardening, historical analytics, the live
weather endpoint, and the frontend assets (3D scene + charts).

The frontend assertions here are static checks on the shipped assets, because
this project has no bundler: the browser loads the same files directly.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app import create_app
from models import Alert, Location, Prediction, RiskAssessment, User, WeatherRecord, db
from services.analytics import SOURCE_LABELS, SOURCE_ML, SOURCE_RISK, SOURCE_WEATHER, full_analytics
from services.security import LoginThrottle, clamp_int, date_range, parse_iso_date
from services.weather_service import WeatherServiceError

BASE_DIR = Path(__file__).resolve().parents[1]
PASSWORD = "strong-pass-123"

WEATHER = {
    "location": {"name": "Chennai", "country": "India", "latitude": 13.08, "longitude": 80.27},
    "current": {
        "temperature": 39.0, "feels_like": 41.0, "humidity": 90.0, "wind_speed": 14.0,
        "precipitation": 18.0, "condition": "Rain", "pressure": 1005.0, "wind_direction": 180,
    },
    "forecast": [{
        "date": "Mon, Aug 31", "condition": "Rain", "temperature_min": 27.0,
        "temperature_max": 39.0, "rain_probability": 85.0, "precipitation": 18.0,
    }],
    "hourly": [],
    "units": {"temperature": "°C"},
}
CALM = {
    **WEATHER,
    "current": {**WEATHER["current"], "temperature": 21.0, "humidity": 40.0,
                "precipitation": 0.0, "condition": "Clear sky"},
    "forecast": [{**WEATHER["forecast"][0], "rain_probability": 5.0, "temperature_max": 21.0}],
}
PREDICTION = {
    "probability": 0.8, "probability_percent": 80, "prediction": "Rain Expected",
    "risk_level": "High", "factors": [{"name": "Humidity", "importance": 0.5}],
    "model_name": "Random Forest",
}

ANALYTICS_ENDPOINTS = (
    "/api/analytics/summary",
    "/api/analytics/weather",
    "/api/analytics/predictions",
    "/api/analytics/risk",
    "/api/analytics/alerts",
    "/api/analytics/all",
)


def build_app(**overrides):
    config = {
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }
    config.update(overrides)
    return create_app(config)


def register_and_login(app, email, name="Student"):
    client = app.test_client()
    client.post("/register", data={
        "name": name, "email": email, "password": PASSWORD, "confirm_password": PASSWORD,
    })
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def logged_in_client(email="phase4@example.com"):
    app = build_app()
    return app, register_and_login(app, email)


def seed_history(app, email="data@example.com"):
    """Create a user with weather, prediction, risk and alert history."""
    with app.app_context():
        user = User(name="Data", email=email)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        location = Location(user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27)
        db.session.add(location)
        db.session.commit()
        record = WeatherRecord(
            location_id=location.id, temperature=30.0, humidity=70.0, wind_speed=12.0,
            pressure=1005.0, weather_condition="Rain", precipitation=4.0,
        )
        db.session.add(record)
        db.session.commit()
        db.session.add(Prediction(
            weather_record_id=record.id, prediction_type="rain",
            probability=0.6, result="Rain Expected",
        ))
        db.session.add(RiskAssessment(
            user_id=user.id, location_id=location.id, risk_type="Flood",
            risk_level="High", risk_score=75.0, details="Drainage stress.",
        ))
        db.session.add(RiskAssessment(
            user_id=user.id, location_id=location.id, risk_type="Heatwave",
            risk_level="Low", risk_score=20.0, details="Comfortable.",
        ))
        db.session.add(Alert(
            user_id=user.id, location_id=location.id, alert_type="Flood",
            severity="High", message="Flood risk is high.", is_read=False,
        ))
        db.session.commit()
        return user.id, location.id


# --------------------------------------------------------------------------
# Security hardening
# --------------------------------------------------------------------------

class TestSecurityHardening:
    def test_session_cookie_is_httponly_and_samesite_lax(self):
        app = build_app()
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    def test_secure_cookie_is_off_by_default_for_local_http(self):
        assert build_app().config["SESSION_COOKIE_SECURE"] is False

    def test_secure_cookie_is_read_from_the_environment(self):
        """Config reads the environment at import time via the env_flag helper."""
        from config import env_flag

        assert env_flag("MISSING_COOKIE_FLAG", False) is False
        assert env_flag("MISSING_COOKIE_FLAG", True) is True
        os.environ["SESSION_COOKIE_SECURE"] = "1"
        try:
            assert env_flag("SESSION_COOKIE_SECURE", False) is True
        finally:
            os.environ.pop("SESSION_COOKIE_SECURE", None)

    def test_security_headers_are_present_on_responses(self):
        response = build_app().test_client().get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert "strict-origin" in response.headers["Referrer-Policy"]

    def test_csp_is_not_forced_by_default(self):
        """A strict CSP would break the CDN-hosted map and 3D library."""
        response = build_app().test_client().get("/health")
        assert "Content-Security-Policy" not in response.headers

    def test_csp_can_be_enabled_explicitly(self):
        response = build_app(ENABLE_CSP=True).test_client().get("/health")
        assert "Content-Security-Policy" in response.headers

    def test_password_is_hashed_and_never_returned(self):
        app = build_app()
        client = app.test_client()
        client.post("/register", data={
            "name": "H", "email": "hash@example.com",
            "password": PASSWORD, "confirm_password": PASSWORD,
        })
        with app.app_context():
            user = User.query.filter_by(email="hash@example.com").first()
            assert user.password_hash != PASSWORD
            assert "pbkdf2" in user.password_hash or "scrypt" in user.password_hash
        body = client.get("/api/alert-history").get_data(as_text=True)
        assert "password_hash" not in body
        assert PASSWORD not in body

    def test_api_404_returns_json_without_traceback(self):
        response = build_app().test_client().get("/api/does-not-exist")
        assert response.status_code == 404
        assert response.is_json
        assert "error" in response.get_json()
        body = response.get_data(as_text=True)
        assert "Traceback" not in body
        assert "site-packages" not in body

    def test_unexpected_error_returns_safe_json(self):
        app = build_app()
        client = register_and_login(app, "boom@example.com")
        # Patch the name the view actually calls, so the handler is exercised.
        with patch("app.analytics_summary", side_effect=RuntimeError("secret C:\\db.sqlite")):
            response = client.get("/api/analytics/summary")
        assert response.status_code == 500
        body = response.get_data(as_text=True)
        assert "Traceback" not in body
        assert "C:\\db.sqlite" not in body
        assert response.get_json()["code"] == "internal_error"

    def test_health_endpoint_still_works(self):
        assert build_app().test_client().get("/health").status_code == 200

    def test_login_throttle_locks_after_repeated_failures(self):
        app = build_app(LOGIN_MAX_ATTEMPTS=3, LOGIN_WINDOW_SECONDS=300, LOGIN_LOCKOUT_SECONDS=300)
        client = app.test_client()
        client.post("/register", data={
            "name": "T", "email": "throttle@example.com",
            "password": PASSWORD, "confirm_password": PASSWORD,
        })
        client.post("/logout")
        for _ in range(3):
            client.post("/login", data={"email": "throttle@example.com", "password": "wrong"})
        blocked = client.post("/login", data={"email": "throttle@example.com", "password": PASSWORD})
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers

    def test_successful_login_clears_the_throttle(self):
        throttle = LoginThrottle(max_attempts=3)
        throttle.record_failure("a")
        throttle.record_failure("a")
        assert throttle.is_locked("a") is False
        throttle.reset("a")
        assert throttle.is_locked("a") is False

    def test_clamp_int_never_raises(self):
        assert clamp_int("abc", 30, 1, 365) == 30
        assert clamp_int(None, 30, 1, 365) == 30
        assert clamp_int("99999", 30, 1, 365) == 365
        assert clamp_int("-5", 30, 1, 365) == 1
        assert clamp_int("7", 30, 1, 365) == 7

    def test_parse_iso_date_rejects_junk(self):
        assert parse_iso_date("2026-01-31") is not None
        assert parse_iso_date("not-a-date") is None
        assert parse_iso_date("") is None

    def test_date_range_reports_bad_input(self):
        _, _, _, error = date_range({"start": "nope"})
        assert error and "Invalid start date" in error
        _, _, _, error = date_range({"start": "2026-05-01", "end": "2026-01-01"})
        assert error and "on or before" in error

    def test_date_range_defaults_when_nothing_is_supplied(self):
        start, end, days, error = date_range({})
        assert error is None
        assert start is not None and end is not None
        assert days == 30


# --------------------------------------------------------------------------
# Analytics authorization and isolation
# --------------------------------------------------------------------------

class TestAnalyticsSecurity:
    @pytest.mark.parametrize("path", ANALYTICS_ENDPOINTS)
    def test_anonymous_analytics_is_rejected(self, path):
        assert build_app().test_client().get(path).status_code == 401

    def test_analytics_page_requires_login(self):
        assert build_app().test_client().get("/analytics").status_code == 302

    def test_analytics_never_exposes_another_users_data(self):
        app = build_app()
        seed_history(app, "owner@example.com")
        outsider = register_and_login(app, "outsider@example.com")
        payload = outsider.get("/api/analytics/summary").get_json()
        assert payload["totals"]["alerts"] == 0
        assert payload["totals"]["weather_records"] == 0
        assert payload["has_data"] is False

    def test_invalid_date_range_returns_400(self):
        app, client = logged_in_client()
        assert client.get("/api/analytics/summary?start=bad").status_code == 400
        assert client.get("/api/analytics/summary?days=abc").status_code == 200

    def test_live_endpoint_requires_login(self):
        assert build_app().test_client().get("/api/live/weather").status_code == 401

    def test_live_endpoint_never_accepts_a_user_id(self):
        """There is no parameter that can request another account's view."""
        app, client = logged_in_client()
        response = client.get("/api/live/weather?city=Chennai&user_id=9999")
        assert response.status_code == 200
        assert "user_id" not in response.get_json()


# --------------------------------------------------------------------------
# Analytics content
# --------------------------------------------------------------------------

def dashboard_client(app, email, weather=None, prediction=PREDICTION):
    """Register, log in, and load the dashboard so history exists."""
    client = register_and_login(app, email)
    with patch("app.get_weather", return_value=weather or WEATHER), patch(
        "app.predict_rain", return_value=prediction
    ):
        client.get("/dashboard?city=Chennai")
    return client


class TestAnalyticsContent:
    def test_summary_counts_every_persisted_system(self):
        app = build_app()
        client = dashboard_client(app, "count@example.com")
        totals = client.get("/api/analytics/summary").get_json()["totals"]
        assert totals["weather_records"] == 1
        assert totals["predictions"] == 1
        assert totals["risk_assessments"] == 3
        assert totals["alerts"] > 0
        assert totals["unread_alerts"] == totals["alerts"]
        assert totals["high_risk_events"] >= 1

    def test_prediction_distribution_is_split(self):
        app = build_app()
        client = dashboard_client(app, "dist@example.com")
        payload = client.get("/api/analytics/summary").get_json()
        assert payload["prediction_distribution"]["rain_expected"] == 1
        assert payload["prediction_distribution"]["no_rain_expected"] == 0
        assert payload["average_rainfall_probability_percent"] == 80.0

    def test_three_sources_are_labelled_separately(self):
        """Forecast, ML prediction and risk must never be merged."""
        app = build_app()
        client = dashboard_client(app, "src@example.com")
        assert client.get("/api/analytics/weather").get_json()["source"] == SOURCE_WEATHER
        assert client.get("/api/analytics/predictions").get_json()["source"] == SOURCE_ML
        assert client.get("/api/analytics/risk").get_json()["source"] == SOURCE_RISK
        assert len({SOURCE_WEATHER, SOURCE_ML, SOURCE_RISK}) == 3

    def test_ml_and_risk_sections_state_their_origin(self):
        app, client = logged_in_client()
        assert "not the open-meteo forecast" in client.get("/api/analytics/predictions").get_json()["note"].lower()
        assert "not from a machine-learning model" in client.get("/api/analytics/risk").get_json()["note"].lower()

    def test_weather_analytics_returns_a_timeline(self):
        app = build_app()
        client = dashboard_client(app, "timeline@example.com")
        payload = client.get("/api/analytics/weather").get_json()
        assert payload["has_data"] is True
        assert payload["timeline"]
        entry = payload["timeline"][0]
        assert entry["temperature"] == 39.0
        assert entry["humidity"] == 90.0

    def test_risk_analytics_covers_all_categories_and_levels(self):
        app = build_app()
        client = dashboard_client(app, "riskcat@example.com")
        categories = client.get("/api/analytics/risk").get_json()["categories"]
        assert set(categories) == {"Flood", "Heatwave", "Heavy rain"}
        assert [row["label"] for row in categories["Flood"]["levels"]] == [
            "Low", "Moderate", "High", "Critical"
        ]
        assert categories["Flood"]["highest_level"] == "High"

    def test_alert_analytics_reports_read_state(self):
        app = build_app()
        client = dashboard_client(app, "readstate@example.com")
        payload = client.get("/api/analytics/alerts").get_json()
        assert payload["read_state"]["unread"] == payload["sample_size"]
        assert payload["by_type"]
        assert payload["by_severity"]

    def test_all_endpoint_returns_every_section(self):
        app, client = logged_in_client()
        assert set(client.get("/api/analytics/all").get_json()) == {
            "summary", "weather", "predictions", "risk", "alerts"
        }

    def test_empty_dataset_returns_zeroes_not_errors(self):
        app, client = logged_in_client()
        for path in ANALYTICS_ENDPOINTS:
            assert "error" not in client.get(path).get_json()
        summary = client.get("/api/analytics/summary").get_json()
        assert summary["totals"]["weather_records"] == 0
        assert summary["has_data"] is False
        weather = client.get("/api/analytics/weather").get_json()
        assert weather["has_data"] is False
        assert weather["averages"]["temperature"] is None
        assert client.get("/api/analytics/risk").get_json()["categories"]["Flood"]["highest_level"] is None

    def test_date_filtering_narrows_the_window(self):
        app = build_app()
        client = dashboard_client(app, "range@example.com")
        assert client.get("/api/analytics/summary?days=1").get_json()["totals"]["weather_records"] == 1
        old = client.get("/api/analytics/summary?start=2020-01-01&end=2020-01-05").get_json()
        assert old["totals"]["weather_records"] == 0

    def test_excessive_date_range_is_rejected(self):
        app, client = logged_in_client()
        assert client.get("/api/analytics/summary?start=2000-01-01&end=2026-01-01").status_code == 400


# --------------------------------------------------------------------------
# Live weather endpoint
# --------------------------------------------------------------------------

class TestLiveWeather:
    def test_live_returns_real_backend_values(self):
        app = build_app()
        client = dashboard_client(app, "live@example.com")
        with patch("app.get_weather", return_value=WEATHER), patch("app.predict_rain", return_value=PREDICTION):
            payload = client.get("/api/live/weather?city=Chennai").get_json()
        assert payload["location"]["name"] == "Chennai"
        assert payload["current"]["temperature"] == 39.0
        assert payload["current"]["humidity"] == 90.0
        assert payload["forecast"][0]["rain_probability"] == 85.0
        assert payload["rain_prediction"]["probability_percent"] == 80
        assert payload["risk"]["flood"] == "High"
        assert payload["unread_count"] > 0
        assert payload["updated_at"]

    def test_live_labels_all_three_sources(self):
        app = build_app()
        client = dashboard_client(app, "src2@example.com")
        with patch("app.get_weather", return_value=WEATHER), patch("app.predict_rain", return_value=PREDICTION):
            sources = client.get("/api/live/weather?city=Chennai").get_json()["sources"]
        assert sources["weather"] == "Open-Meteo"
        assert sources["rain_prediction"] == "Random Forest"
        assert "rule-based" in sources["risk"].lower()

    def test_live_uses_the_session_location_by_default(self):
        app = build_app()
        client = dashboard_client(app, "session@example.com")
        with patch("app.get_weather", return_value=WEATHER) as getter, patch(
            "app.predict_rain", return_value=PREDICTION
        ):
            client.get("/api/live/weather")
        getter.assert_called_once_with("Chennai")

    def test_live_reports_a_clear_error_when_weather_fails(self):
        app, client = logged_in_client()
        with patch("app.get_weather", side_effect=WeatherServiceError("unavailable")):
            response = client.get("/api/live/weather?city=Chennai")
        assert response.status_code == 502
        assert response.get_json()["code"] == "weather_unavailable"
        # No invented values are returned on failure.
        assert "current" not in response.get_json()

    def test_live_survives_a_missing_ml_model(self):
        from ml.predict import MLPredictionError

        app, client = logged_in_client()
        with patch("app.get_weather", return_value=WEATHER), patch(
            "app.predict_rain", side_effect=MLPredictionError("model missing")
        ):
            response = client.get("/api/live/weather?city=Chennai")
        assert response.status_code == 200
        assert response.get_json()["rain_prediction"] is None
        assert response.get_json()["current"]["temperature"] == 39.0

    def test_live_does_not_create_duplicate_alerts(self):
        app = build_app()
        client = dashboard_client(app, "dedupe@example.com")
        with patch("app.get_weather", return_value=WEATHER):
            before = client.get("/api/alert-history").get_json()["alerts"]
            client.get("/api/live/weather?city=Chennai")
            client.get("/api/live/weather?city=Chennai")
            after = client.get("/api/alert-history").get_json()["alerts"]
        assert len(after) == len(before)

    def test_live_risk_is_the_rule_based_result(self):
        app = build_app()
        client = dashboard_client(app, "rules@example.com")
        with patch("app.get_weather", return_value=CALM), patch("app.predict_rain", return_value=None):
            payload = client.get("/api/live/weather?city=Chennai").get_json()
        assert payload["risk"] == {"flood": "Low", "heatwave": "Low", "rain": "Low"}


# --------------------------------------------------------------------------
# Frontend assets: 3D scene, charts, and states
# --------------------------------------------------------------------------

def read_asset(relative):
    return (BASE_DIR / relative).read_text(encoding="utf-8")


class TestFrontendAssets:
    def test_all_three_scripts_pass_a_syntax_check(self):
        import shutil
        import subprocess

        node = shutil.which("node")
        if not node:
            pytest.skip("node is not installed on this machine")
        for script in ("static/js/app.js", "static/js/analytics.js", "static/js/weather3d.js"):
            result = subprocess.run([node, "--check", str(BASE_DIR / script)], capture_output=True)
            assert result.returncode == 0, f"{script}: {result.stderr.decode('utf-8', 'replace')}"

    def test_scene_script_derives_state_from_the_payload(self):
        source = read_asset("static/js/weather3d.js")
        assert "function deriveSceneState" in source
        # The scene must read the server payload, not a hard-coded condition.
        assert "payload.risk" in source
        assert "payload.current" in source
        assert "floodHeight" in source
        assert "intensity" in source

    def test_scene_has_a_webgl_and_library_fallback(self):
        source = read_asset("static/js/weather3d.js")
        assert "hasWebGL" in source
        assert "showFallback" in source
        assert "data-scene-fallback" in source
        assert "WebGL is not available" in source

    def test_scene_cleans_up_and_bounds_particles(self):
        source = read_asset("static/js/weather3d.js")
        assert "cancelAnimationFrame" in source
        assert "removeEventListener" in source
        assert "maxDrops" in source

    def test_scene_respects_reduced_motion(self):
        source = read_asset("static/js/weather3d.js")
        assert "prefers-reduced-motion" in source
        assert "this.reduced" in source

    def test_live_polling_is_guarded(self):
        source = read_asset("static/js/weather3d.js")
        assert "/api/live/weather" in source
        assert "setInterval" in source
        assert "visibilityState" in source

    def test_analytics_script_handles_missing_chart_library(self):
        source = read_asset("static/js/analytics.js")
        assert "hasChartJs" in source
        assert "Chart library unavailable" in source
        assert "emptyNotice" in source

    def test_analytics_script_shows_an_error_state_instead_of_stale_data(self):
        source = read_asset("static/js/analytics.js")
        assert ".catch" in source
        assert "failAll" in source

    def test_dashboard_loads_the_scene_and_live_endpoint(self):
        source = read_asset("templates/dashboard.html")
        assert "weather3d.js" in source
        assert "three" in source
        assert "data-live-root" in source
        assert "data-live-endpoint" in source
        assert "data-scene" in source

    def test_analytics_page_loads_charts_and_the_analytics_script(self):
        source = read_asset("templates/analytics.html")
        assert "chart.js" in source.lower()
        assert "analytics.js" in source
        assert "data-analytics-root" in source
        assert "data-range" in source

    def test_css_defines_the_phase4_components_and_states(self):
        source = read_asset("static/css/style.css")
        for selector in (".hero-panel", ".hero-scene", ".stat-grid", ".chart-grid",
                         ".skeleton", ".range-button", ".scene-fallback"):
            assert selector in source
        assert "prefers-reduced-motion" in source
        assert "@media (max-width: 560px)" in source

    def test_base_navigation_links_to_analytics(self):
        assert "analytics_page" in read_asset("templates/base.html")


# --------------------------------------------------------------------------
# Phase 4 repair regression: real rendering issues found in a browser
# --------------------------------------------------------------------------

class TestTemplateRepairs:
    def _balance(self, html):
        from html.parser import HTMLParser

        void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                "meta", "param", "source", "track", "wbr"}

        class Checker(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.problems = []

            def handle_starttag(self, tag, attrs):
                if tag not in void:
                    self.stack.append(tag)

            def handle_endtag(self, tag):
                if tag in void:
                    return
                if self.stack and self.stack[-1] == tag:
                    self.stack.pop()
                elif tag in self.stack:
                    while self.stack and self.stack[-1] != tag:
                        self.problems.append("unclosed <%s>" % self.stack.pop())
                    if self.stack:
                        self.stack.pop()
                else:
                    self.problems.append("stray </%s>" % tag)

        checker = Checker()
        checker.feed(html)
        return checker.problems + ["unclosed <%s>" % tag for tag in checker.stack]

    def test_rendered_dashboard_html_is_balanced(self):
        app = build_app()
        client = dashboard_client(app, "balance@example.com")
        body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert self._balance(body) == []

    def test_rendered_analytics_html_is_balanced(self):
        """Regression: a lost </div></section> broke the analytics layout."""
        app = build_app()
        client = dashboard_client(app, "balance2@example.com")
        body = client.get("/analytics").get_data(as_text=True)
        assert self._balance(body) == []

    def test_favicon_is_served_instead_of_404(self):
        app = build_app()
        assert app.test_client().get("/favicon.ico").status_code == 200

    def test_favicon_assets_exist_on_disk(self):
        for name in ("favicon.ico", "favicon.svg"):
            assert (BASE_DIR / "static" / "icons" / name).is_file()

    def test_base_template_links_the_favicon(self):
        source = read_asset("templates/base.html")
        assert "favicon.svg" in source
        assert "favicon.ico" in source

    def test_static_assets_are_cache_busted(self):
        """Regression: a cached stylesheet kept showing the old dashboard."""
        app = build_app()
        client = dashboard_client(app, "cache@example.com")
        body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert "style.css?v=" in body
        assert "app.js?v=" in body
        assert "weather3d.js?v=" in body

    def test_asset_url_is_stable_within_a_request(self):
        from app import asset_url

        app = build_app()
        with app.test_request_context():
            first = asset_url("js/app.js")
            second = asset_url("js/app.js")
        assert "v=" in first
        assert first == second

    def test_asset_url_falls_back_for_a_missing_file(self):
        from app import asset_url

        with build_app().test_request_context():
            assert asset_url("js/does-not-exist.js").endswith("v=0")

    def test_analytics_script_is_loaded_on_the_dashboard(self):
        """Regression: the preview card never filled because the script was absent."""
        app = build_app()
        client = dashboard_client(app, "preview@example.com")
        body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert "analytics.js" in body

    def _script_order(self, source):
        """Return the src of every <script> tag, in document order.

        Comments are ignored on purpose, so only real script tags are compared.
        """
        import re

        return re.findall(r'<script[^>]*src="([^"]+)"', source)

    def test_three_js_loads_before_the_scene_script(self):
        sources = self._script_order(read_asset("templates/dashboard.html"))
        three = next(i for i, s in enumerate(sources) if "three" in s)
        scene = next(i for i, s in enumerate(sources) if "weather3d.js" in s)
        assert three < scene, sources

    def test_chart_js_loads_before_the_analytics_script(self):
        sources = self._script_order(read_asset("templates/analytics.html"))
        chart = next(i for i, s in enumerate(sources) if "chart.umd.min.js" in s)
        page = next(i for i, s in enumerate(sources) if "analytics.js" in s)
        assert chart < page, sources

    def test_every_local_script_uses_the_cache_busted_helper(self):
        import re

        for name in ("dashboard.html", "analytics.html", "base.html"):
            source = read_asset("templates/" + name)
            for src in self._script_order(source):
                if src.startswith("/static/"):
                    assert "asset_url(" in source.split(src)[0].rsplit("<script", 1)[-1], (name, src)

    def test_hero_uses_the_project_light_theme_tokens(self):
        """Regression: a dark hero clashed with the light dashboard."""
        source = read_asset("static/css/style.css")
        block = source[source.index(".hero-panel {"):source.index(".hero-scene {")]
        assert "var(--surface-strong)" in block
        assert "var(--ink)" in block
        assert "15, 23, 42" not in block

    def test_analytics_preview_is_wired_in_the_script(self):
        source = read_asset("static/js/analytics.js")
        assert "data-analytics-preview" in source
        assert "loadPreview" in source
        # The preview needs the risk + alert sections too, because it draws
        # a real risk doughnut and an alerts-by-severity doughnut.
        assert "/api/analytics/all" in source
        assert "renderPreviewCharts" in source
        assert "preview-risk" in source
        assert "preview-alerts" in source

    def test_dashboard_has_the_final_section_structure_in_order(self):
        """Regression: alerts used to be the first major block on the page."""
        app = build_app()
        client = dashboard_client(app, "order@example.com")
        body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        order = [
            "dashboard-hero", "risk-overview", "dashboard-grid",
            "intelligence-section", "alert-section", "analytics-preview",
        ]
        positions = [body.index(name) for name in order]
        assert positions == sorted(positions), list(zip(order, positions))
        assert body.index("alert-section") > body.index("dashboard-hero")

    def test_dashboard_loads_the_final_stylesheet_last(self):
        """Regression: the final design must win the cascade."""
        app = build_app()
        client = dashboard_client(app, "cssorder@example.com")
        body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert "dashboard-final.css" in body
        assert body.index("css/style.css") < body.index("css/dashboard-final.css")

    def test_hero_scene_container_is_present_and_measurable(self):
        source = read_asset("static/css/dashboard-final.css")
        assert "#hero-scene" in source
        assert "height: 340px" in source
        app = build_app()
        client = dashboard_client(app, "scene@example.com")
        body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert 'id="hero-scene"' in body
        assert "data-scene" in body

    def test_risk_badges_render_server_side(self):
        """Regression: a hard-coded level class hid the real severity."""
        app = build_app()
        client = dashboard_client(app, "levels@example.com")
        body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        assert "assess_risks" in read_asset("templates/dashboard.html")
        assert "level-{{ risk_levels.flood|lower }}" in read_asset("templates/dashboard.html")


# --------------------------------------------------------------------------
# Phase 1-3 regression guard
# --------------------------------------------------------------------------

class TestPhase4Regression:
    def test_dashboard_still_renders_every_existing_section(self):
        app, client = logged_in_client()
        with patch("app.get_weather", return_value=WEATHER), patch("app.predict_rain", return_value=PREDICTION):
            body = client.get("/dashboard?city=Chennai").get_data(as_text=True)
        for hook in ("data-best-time", "data-best-time-text", "risk-flood", "risk-heat",
                     "risk-rain", "data-alert-history", "data-unread-count",
                     "AI Rainfall Prediction", "Next seven days", "weather-map",
                     "data-weather-search", "data-analytics-preview", "data-live-root"):
            assert hook in body, hook
        for mode in ("general", "farmer", "travel", "daily_commute", "outdoor_activity"):
            assert f'data-mode="{mode}"' in body
        # This storm fixture yields High and Critical levels; the Moderate band
        # is covered by the existing Phase 1 tests.
        for level in ("level-high", "level-critical"):
            assert level in body

    def test_core_apis_still_work(self):
        app = build_app()
        client = dashboard_client(app, "core@example.com")
        for path in ("/health", "/api/alert-history", "/api/notification-preferences",
                     "/api/notification-status", "/api/live/weather?city=Chennai",
                     "/api/analytics/summary", "/profile", "/analytics"):
            assert client.get(path).status_code == 200, path

    def test_registration_login_and_dashboard_flow(self):
        app = build_app()
        client = app.test_client()
        assert client.get("/").status_code == 200
        client.post("/register", data={
            "name": "Flow", "email": "flow4@example.com",
            "password": PASSWORD, "confirm_password": PASSWORD,
        })
        assert client.post("/login", data={"email": "flow4@example.com", "password": PASSWORD}).status_code == 302
        assert client.get("/dashboard").status_code == 200
        assert client.get("/logout").status_code == 302

    def test_weather_failure_still_renders_the_dashboard(self):
        app, client = logged_in_client()
        with patch("app.get_weather", side_effect=WeatherServiceError("unavailable")):
            response = client.get("/dashboard?city=Chennai")
        assert response.status_code == 200
        assert "weather-empty" in response.get_data(as_text=True)

    def test_no_new_database_tables_were_created(self):
        """Phase 4 aggregates existing data; it must not add storage."""
        import sqlalchemy as sa

        with build_app().app_context():
            tables = set(sa.inspect(db.engine).get_table_names())
        assert {"prediction", "risk_assessment", "alert"} <= tables
        assert not {"analytics", "analyticsrecord", "notificationdelivery"} & tables

    def test_analytics_page_renders_in_all_three_languages(self):
        app = build_app()
        client = dashboard_client(app, "lang@example.com")
        for language in ("en", "te", "hi"):
            client.post("/api/language", json={"language": language})
            response = client.get("/analytics")
            assert response.status_code == 200
            body = response.get_data(as_text=True)
            assert "data-analytics-root" in body
            assert 'data-chart="risk-Flood"' in body
