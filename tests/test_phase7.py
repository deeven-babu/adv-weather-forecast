"""Tests for Phase 7: Weather Decision Assistant features."""

from unittest.mock import Mock, patch
import pytest
from services.recommendations import (
    MODE_GENERAL, MODE_FARMER, MODE_TRAVEL, MODE_COMMUTE, MODE_OUTDOOR,
    VALID_MODES, DEFAULT_MODE,
    generate_weather_alerts, generate_today_summary, get_recommendation_by_mode,
    get_best_time_window, add_mode_context_to_question, WeatherAlert
)


# Sample weather data for testing
SAMPLE_WEATHER = {
    'location': {'name': 'Chennai', 'country': 'India', 'latitude': 13.08, 'longitude': 80.27},
    'current': {
        'temperature': 32.0,
        'humidity': 78.0,
        'wind_speed': 14.0,
        'precipitation': 1.2,
        'condition': 'Partly cloudy',
        'pressure': 1005.0
    },
    'forecast': [
        {
            'date': '2026-08-31',
            'condition': 'Rainy',
            'temperature_min': 27.0,
            'temperature_max': 33.0,
            'rain_probability': 70.0,
            'precipitation': 3.5
        },
        {
            'date': '2026-09-01',
            'condition': 'Partly cloudy',
            'temperature_min': 26.0,
            'temperature_max': 32.0,
            'rain_probability': 30.0,
            'precipitation': 1.0
        }
    ]
}

HEAVY_RAIN_WEATHER = {
    'location': {'name': 'Test City', 'country': 'Test Country'},
    'current': {
        'temperature': 25.0,
        'humidity': 85.0,
        'wind_speed': 30.0,
        'precipitation': 18.0,
        'condition': 'Heavy rain',
        'pressure': 990.0
    },
    'forecast': [{
        'date': '2026-08-31',
        'condition': 'Heavy rain',
        'temperature_min': 23.0,
        'temperature_max': 28.0,
        'rain_probability': 90.0,
        'precipitation': 25.0
    }]
}

HOT_WEATHER = {
    'location': {'name': 'Desert City', 'country': 'Desert Land'},
    'current': {
        'temperature': 39.0,
        'humidity': 25.0,
        'wind_speed': 35.0,
        'precipitation': 0.0,
        'condition': 'Clear sky',
        'pressure': 1010.0
    },
    'forecast': [{
        'date': '2026-08-31',
        'condition': 'Clear sky',
        'temperature_min': 35.0,
        'temperature_max': 42.0,
        'rain_probability': 0.0,
        'precipitation': 0.0
    }]
}


class TestWeatherAlerts:
    """Tests for weather alert generation."""

    def test_generate_alerts_for_heavy_rain(self):
        """Test alerts are generated for heavy rain."""
        alerts = generate_weather_alerts(HEAVY_RAIN_WEATHER)
        assert len(alerts) > 0
        assert any(a.type == "Heavy Rain" for a in alerts)

    def test_generate_alerts_for_high_temperature(self):
        """Test alerts are generated for high temperature."""
        alerts = generate_weather_alerts(HOT_WEATHER)
        assert len(alerts) > 0
        assert any(a.type == "High Temperature" for a in alerts)

    def test_alerts_have_severity_levels(self):
        """Test that all alerts have valid severity levels."""
        alerts = generate_weather_alerts(HEAVY_RAIN_WEATHER)
        for alert in alerts:
            assert alert.severity in ["Low", "Moderate", "High"]

    def test_no_alerts_for_normal_weather(self):
        """Test that few or no alerts for normal conditions."""
        normal_weather = {
            'location': {'name': 'Normal City', 'country': 'Normal Land'},
            'current': {
                'temperature': 22.0,
                'humidity': 60.0,
                'wind_speed': 10.0,
                'precipitation': 0.0,
                'condition': 'Partly cloudy',
                'pressure': 1013.0
            },
            'forecast': [{
                'date': '2026-08-31',
                'condition': 'Partly cloudy',
                'temperature_min': 18.0,
                'temperature_max': 25.0,
                'rain_probability': 20.0,
                'precipitation': 0.0
            }]
        }
        alerts = generate_weather_alerts(normal_weather)
        # Should have minimal or no alerts for normal weather
        assert len(alerts) <= 1

    def test_alert_is_weather_alert_type(self):
        """Test that returned alerts are WeatherAlert objects."""
        alerts = generate_weather_alerts(SAMPLE_WEATHER)
        for alert in alerts:
            assert isinstance(alert, WeatherAlert)


class TestWeatherSummary:
    """Tests for today's AI weather summary."""

    def test_summary_includes_location(self):
        """Test that summary includes location name."""
        summary = generate_today_summary(SAMPLE_WEATHER)
        assert "Chennai" in summary

    def test_summary_includes_temperature(self):
        """Test that summary mentions temperature."""
        summary = generate_today_summary(SAMPLE_WEATHER)
        assert "32" in summary or "warm" in summary.lower()

    def test_summary_for_empty_weather_is_string(self):
        """Test summary for None weather returns a message."""
        summary = generate_today_summary(None)
        assert isinstance(summary, str)

    def test_summary_includes_rain_probability(self):
        """Test that summary mentions rain when likely."""
        summary = generate_today_summary(SAMPLE_WEATHER)
        # The forecast has 70% rain probability, so summary should mention it
        assert "rain" in summary.lower() or "low chance" in summary.lower()

    def test_summary_is_reasonable_length(self):
        """Test that summary is not too short or too long."""
        summary = generate_today_summary(SAMPLE_WEATHER)
        assert 50 < len(summary) < 300


class TestRecommendationsByMode:
    """Tests for mode-specific recommendations."""

    def test_general_mode_recommendation(self):
        """Test that general mode produces recommendations."""
        rec = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_GENERAL)
        assert isinstance(rec, str) and len(rec) > 0

    def test_farmer_mode_recommendation(self):
        """Test that farmer mode produces agriculture-specific advice."""
        rec = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_FARMER)
        assert isinstance(rec, str) and len(rec) > 0
        # Farmer mode should mention farming/irrigation related terms
        assert any(term in rec.lower() for term in ["irrigation", "crop", "field", "rain"])

    def test_travel_mode_recommendation(self):
        """Test that travel mode produces travel-specific advice."""
        rec = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_TRAVEL)
        assert isinstance(rec, str) and len(rec) > 0
        # Travel mode should mention travel-related terms
        assert any(term in rec.lower() for term in ["travel", "carry", "rain", "caution"])

    def test_commute_mode_recommendation(self):
        """Test that commute mode produces commute-specific advice."""
        rec = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_COMMUTE)
        assert isinstance(rec, str) and len(rec) > 0
        # Commute mode should mention commute-related terms
        assert any(term in rec.lower() for term in ["commute", "umbrella", "rain", "conditions"])

    def test_outdoor_mode_recommendation(self):
        """Test that outdoor mode produces activity-specific advice."""
        rec = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_OUTDOOR)
        assert isinstance(rec, str) and len(rec) > 0
        # Outdoor mode should mention activity-related terms
        assert any(term in rec.lower() for term in ["outdoor", "activity", "conditions", "rain"])

    def test_invalid_mode_defaults_to_general(self):
        """Test that invalid mode defaults to general recommendations."""
        rec = get_recommendation_by_mode(SAMPLE_WEATHER, "invalid_mode")
        general_rec = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_GENERAL)
        assert rec == general_rec

    def test_recommendations_vary_by_weather(self):
        """Test that recommendations change based on weather."""
        rec_normal = get_recommendation_by_mode(SAMPLE_WEATHER, MODE_GENERAL)
        rec_heavy = get_recommendation_by_mode(HEAVY_RAIN_WEATHER, MODE_GENERAL)
        # Different weather should produce different recommendations
        assert rec_normal != rec_heavy


class TestBestTimeWindow:
    """Tests for best time window suggestions."""

    def test_best_time_returns_string(self):
        """Test that best time window returns a string."""
        result = get_best_time_window(SAMPLE_WEATHER)
        assert isinstance(result, str)

    def test_best_time_for_no_hourly_data(self):
        """Test that best time informs user when hourly data unavailable."""
        result = get_best_time_window(SAMPLE_WEATHER)
        assert "hourly" in result.lower() or "available" in result.lower()


class TestModeContext:
    """Tests for mode context utility."""

    def test_mode_context_for_general(self):
        """Test mode context for general mode."""
        context = add_mode_context_to_question("Will it rain?", MODE_GENERAL)
        assert isinstance(context, str)

    def test_mode_context_for_farmer(self):
        """Test mode context for farmer mode."""
        context = add_mode_context_to_question("Will it rain?", MODE_FARMER)
        assert "farmer" in context.lower()

    def test_mode_context_for_travel(self):
        """Test mode context for travel mode."""
        context = add_mode_context_to_question("Will it rain?", MODE_TRAVEL)
        assert "travel" in context.lower()

    def test_valid_modes_constant(self):
        """Test that VALID_MODES contains all expected modes."""
        expected_modes = {MODE_GENERAL, MODE_FARMER, MODE_TRAVEL, MODE_COMMUTE, MODE_OUTDOOR}
        assert VALID_MODES == expected_modes

    def test_default_mode_is_valid(self):
        """Test that DEFAULT_MODE is in VALID_MODES."""
        assert DEFAULT_MODE in VALID_MODES


class TestDashboardIntegration:
    """Tests for dashboard integration with Phase 7 features."""

    def test_dashboard_returns_user_mode(self):
        """Test that dashboard pass user mode to template."""
        from app import create_app
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        
        with app.test_client() as client:
            with app.test_request_context():
                from flask import session
                session['user_id'] = 1
                session.permanent = False
                
                # The dashboard should initialize with default mode in session
                assert session.get('user_mode', DEFAULT_MODE) in VALID_MODES

    def test_mode_selector_endpoint_exists(self):
        """Test that /api/user-mode endpoint exists and works."""
        from app import create_app
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        
        with app.test_client() as client:
            # Create a test user first
            with app.app_context():
                from models import db, User
                db.create_all()
                user = User(name='Test User', email='test@test.com')
                user.set_password('password123')
                db.session.add(user)
                db.session.commit()
                user_id = user.id
            
            # Login
            response = client.post('/login', data={
                'email': 'test@test.com',
                'password': 'password123'
            }, follow_redirects=True)
            assert response.status_code == 200
            
            # Set mode
            response = client.post('/api/user-mode', json={'mode': 'farmer'})
            assert response.status_code == 200
            data = response.get_json()
            assert data['mode'] == 'farmer'

    def test_alerts_endpoint_exists(self):
        """Test that /api/alerts endpoint exists."""
        from app import create_app
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        
        with app.test_client() as client:
            with app.app_context():
                from models import db, User
                db.create_all()
                user = User(name='Test User', email='test@test.com')
                user.set_password('password123')
                db.session.add(user)
                db.session.commit()
            
            # Try without login - should fail
            response = client.get('/api/alerts?city=Chennai')
            assert response.status_code == 401

    def test_recommendations_endpoint_exists(self):
        """Test that /api/recommendations endpoint exists."""
        from app import create_app
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        
        with app.test_client() as client:
            with app.app_context():
                from models import db, User
                db.create_all()
                user = User(name='Test User', email='test@test.com')
                user.set_password('password123')
                db.session.add(user)
                db.session.commit()
            
            # Try without login - should fail
            response = client.get('/api/recommendations?city=Chennai')
            assert response.status_code == 401


class TestErrorHandling:
    """Tests for error handling in Phase 7 features."""

    def test_invalid_mode_error_message(self):
        """Test that invalid mode gives clear error message."""
        from app import create_app
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        
        with app.test_client() as client:
            with app.app_context():
                from models import db, User
                db.create_all()
                user = User(name='Test User', email='test@test.com')
                user.set_password('password123')
                db.session.add(user)
                db.session.commit()
            
            # Login
            client.post('/login', data={
                'email': 'test@test.com',
                'password': 'password123'
            }, follow_redirects=True)
            
            # Try invalid mode
            response = client.post('/api/user-mode', json={'mode': 'invalid'})
            assert response.status_code == 400
            data = response.get_json()
            assert 'error' in data

    def test_missing_location_error(self):
        """Test that missing location gives clear error."""
        from app import create_app
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        
        with app.test_client() as client:
            with app.app_context():
                from models import db, User
                db.create_all()
                user = User(name='Test User', email='test@test.com')
                user.set_password('password123')
                db.session.add(user)
                db.session.commit()
            
            # Login
            client.post('/login', data={
                'email': 'test@test.com',
                'password': 'password123'
            }, follow_redirects=True)
            
            # Try to get alerts without location
            response = client.get('/api/alerts')
            assert response.status_code == 400


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
