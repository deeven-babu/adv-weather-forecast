import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import (
    Flask,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy import inspect, text

from config import Config
from ml.predict import MLPredictionError, predict_rain
from models import Location, User, WeatherRecord, db
from services.recommendations import (
    DEFAULT_MODE,
    MODE_ORDER,
    VALID_MODES,
    add_mode_context_to_question,
    generate_today_summary,
    generate_weather_alerts,
    get_best_time_window,
    get_recommendation_by_mode,
    normalize_mode,
)
from services.translations import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_ui_text,
    normalize_language,
    translate_alert,
    translate_answer_text,
    translate_best_time,
    translate_recommendation,
    translate_summary,
    translate_text,
)
from services.risk import assess_risks, risk_advice
from services.weather_service import WeatherServiceError, get_weather, get_weather_by_coordinates, reverse_geocode
from services.weather_assistant import answer_question, explicit_location
from services.phase9 import detect_intent, explain_prediction, intelligence_context, simulate_scenario
from services.assistant_context import new_context, resolve_question, update_context
from services.analytics import (
    alert_analytics,
    analytics_preview,
    analytics_summary,
    full_analytics,
    prediction_analytics,
    risk_analytics,
    weather_analytics,
)
from services.notifications import notification_status
from services.personalization import personalized_guidance
from services.security import (
    apply_security_headers,
    clamp_int,
    client_identifier,
    configure_login_throttle,
    date_range,
    login_throttle,
    safe_error,
    wants_json,
)
from services.alerts import (
    PREFERENCE_ALERT_TYPE_LABELS,
    PREFERENCE_ALERT_TYPES,
    alert_history,
    get_notification_preference,
    mark_all_alerts_read,
    mark_alert_read,
    parse_alert_types,
    process_weather_observations,
    resolve_location,
    serialize_alert,
    serialize_preference,
    unread_alert_count,
    update_notification_preference,
)

load_dotenv()

#: How many persistent alerts the dashboard shows in its history section.
ALERT_HISTORY_LIMIT = 20


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)
    # The dashboard reads disaster risk from the same service the assistant uses.
    app.jinja_env.globals["assess_risks"] = assess_risks
    app.jinja_env.globals["risk_advice"] = risk_advice
    # Cache-busted static URLs so a browser never renders a stale CSS/JS build.
    app.jinja_env.globals["asset_url"] = asset_url

    if test_config is not None:
        app.config.update(test_config)

    @app.before_request
    def ensure_language():
        session.setdefault("language", DEFAULT_LANGUAGE)
        session["language"] = normalize_language(session.get("language"))

    @app.context_processor
    def inject_language_helpers():
        language = normalize_language(session.get("language"))
        return {
            "current_language": language,
            "t": lambda key, default=None: get_ui_text(language, key, default),
            "translate": lambda text: translate_text(text, language),
            "supported_languages": SUPPORTED_LANGUAGES,
        }

    configure_login_throttle(
        app.config.get("LOGIN_MAX_ATTEMPTS", 8),
        app.config.get("LOGIN_WINDOW_SECONDS", 300),
        app.config.get("LOGIN_LOCKOUT_SECONDS", 300),
    )

    @app.after_request
    def add_security_headers(response):
        """Phase 4: attach defensive headers to every response."""
        return apply_security_headers(response, enable_csp=app.config.get("ENABLE_CSP", False))

    db.init_app(app)
    with app.app_context():
        db.create_all()
        ensure_weather_columns()
        ensure_alert_columns()
        ensure_user_columns()

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/favicon.ico")
    def favicon():
        """Serve the site icon from the static folder.

        Browsers request /favicon.ico by default, so this route prevents the
        404 that otherwise shows up in the console on every page.
        """
        return send_from_directory(
            os.path.join(app.root_path, "static", "icons"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
            max_age=86400,
        )

    @app.get("/site.webmanifest")
    def site_manifest():
        return jsonify(
            name="Weather AI",
            short_name="WeatherAI",
            icons=[{
                "src": url_for("static", filename="icons/favicon.svg"),
                "sizes": "any",
                "type": "image/svg+xml",
            }],
            theme_color="#0b1226",
            background_color="#0b1226",
            display="standalone",
        )

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            errors = []

            if not name:
                errors.append("Name is required.")
            if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                errors.append("Enter a valid email address.")
            if len(password) < 8:
                errors.append("Password must be at least 8 characters long.")
            if password != confirm_password:
                errors.append("Passwords do not match.")
            if User.query.filter_by(email=email).first():
                errors.append("An account with that email already exists.")

            if errors:
                for error in errors:
                    flash(translate_text(error, session.get("language")), "error")
                return render_template("register.html", name=name, email=email), 400

            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(translate_text("Account created. You can now log in.", session.get("language")), "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            # Phase 4: lightweight throttle keyed on the client plus the
            # attempted account. It never logs the password.
            throttle_key = f"{client_identifier()}:{email}"
            if login_throttle.is_locked(throttle_key):
                retry_after = login_throttle.retry_after(throttle_key)
                flash(
                    translate_text(
                        "Too many failed attempts. Please wait a moment and try again.",
                        session.get("language"),
                    ),
                    "error",
                )
                response = make_response(render_template("login.html", email=email), 429)
                response.headers["Retry-After"] = str(max(1, retry_after))
                return response

            user = User.query.filter_by(email=email).first()
            if user is None or not user.check_password(password):
                login_throttle.record_failure(throttle_key)
                flash(translate_text("Invalid email or password.", session.get("language")), "error")
                return render_template("login.html", email=email), 401

            login_throttle.reset(throttle_key)
            session.clear()
            session["user_id"] = user.id
            flash(translate_text("Welcome back, {0}.".format(user.name), session.get("language")), "success")
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.get("/logout")
    def logout():
        session.clear()
        flash(translate_text("You have been logged out.", session.get("language")), "success")
        return redirect(url_for("home"))

    @app.get("/dashboard")
    def dashboard():
        user = current_user()
        if user is None:
            flash(translate_text("Please log in to view your dashboard.", session.get("language")), "error")
            return redirect(url_for("login"))
        city = request.args.get("city", "Chennai").strip() or "Chennai"
        user_mode = session.get("user_mode", DEFAULT_MODE)
        language = normalize_language(session.get("language"))
        weather = None
        rain_prediction = None
        prediction_error = None
        alerts = []
        summary = ""
        recommendation = ""
        best_time = ""
        try:
            latitude_text = request.args.get("latitude")
            longitude_text = request.args.get("longitude")
            if latitude_text is not None or longitude_text is not None:
                try:
                    latitude = float(latitude_text)
                    longitude = float(longitude_text)
                except (TypeError, ValueError) as error:
                    raise WeatherServiceError("Enter valid map coordinates.") from error
                location = reverse_geocode(latitude, longitude)
                weather = get_weather_by_coordinates(latitude, longitude, location)
                city = location["name"]
            else:
                weather = get_weather(city)
            session["selected_city"] = weather["location"]["name"]
            location_data = weather["location"]
            location = Location.query.filter_by(
                user_id=user.id, name=location_data["name"]
            ).first()
            if location is None:
                location = Location(user_id=user.id, name=location_data["name"])
                db.session.add(location)
            location.latitude = location_data["latitude"]
            location.longitude = location_data["longitude"]
            current = weather["current"]
            weather_record = WeatherRecord(
                location=location,
                latitude=location_data["latitude"],
                longitude=location_data["longitude"],
                temperature=current["temperature"],
                humidity=current["humidity"],
                wind_speed=current["wind_speed"],
                pressure=current["pressure"],
                weather_condition=current["condition"],
                precipitation=current["precipitation"],
            )
            db.session.add(weather_record)
            db.session.commit()
            try:
                rain_prediction = predict_rain(weather["current"])
            except MLPredictionError as error:
                prediction_error = str(error)
            language = normalize_language(session.get("language"))
            # Generate alerts and summary
            alerts = generate_weather_alerts(weather)
            summary = generate_today_summary(weather)
            recommendation = get_recommendation_by_mode(weather, user_mode)
            best_time = get_best_time_window(weather)
            summary = translate_summary(summary, language)
            recommendation = translate_recommendation(recommendation, language)
            best_time = translate_best_time(best_time, language)
            alerts = [translate_alert(alert, language) for alert in alerts]
            # Phase 2: weather -> ML prediction -> rule-based risk -> alerts.
            # The service deduplicates every write, so a dashboard refresh
            # never produces the same alert again.
            process_weather_observations(
                user,
                location,
                weather,
                weather_record=weather_record,
                rain_prediction=rain_prediction,
            )
            stored_alerts = alert_history(user, limit=ALERT_HISTORY_LIMIT)
            unread_alerts = unread_alert_count(user)
        except WeatherServiceError as error:
            db.session.rollback()
            flash(translate_text(str(error), language), "error")
            stored_alerts = []
            unread_alerts = 0
        return render_template(
            "dashboard.html",
            user=user,
            weather=weather,
            searched_city=city,
            rain_prediction=rain_prediction,
            prediction_error=prediction_error,
            user_mode=user_mode,
            alerts=alerts,
            stored_alerts=stored_alerts,
            unread_alerts=unread_alerts,
            summary=summary,
            recommendation=recommendation,
            best_time=best_time,
            language=language,
        )

    @app.get("/api/weather")
    def weather_api():
        city = request.args.get("city", "").strip()
        try:
            return jsonify(get_weather(city))
        except WeatherServiceError as error:
            return jsonify(error=str(error)), 400

    @app.get("/api/weather/location")
    def weather_location_api():
        try:
            latitude = float(request.args.get("latitude", ""))
            longitude = float(request.args.get("longitude", ""))
            location = reverse_geocode(latitude, longitude)
            return jsonify(get_weather_by_coordinates(latitude, longitude, location))
        except (TypeError, ValueError):
            return jsonify(error="Enter valid map coordinates."), 400
        except WeatherServiceError as error:
            return jsonify(error=str(error)), 400

    @app.post("/api/user-mode")
    def set_user_mode():
        """Set the user's mode preference for the session."""
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        payload = request.get_json(silent=True) or {}
        requested_mode = str(payload.get("mode", "")).strip().lower()
        mode = normalize_mode(requested_mode)
        if mode is None or mode not in VALID_MODES:
            return jsonify(error=translate_text(f"Invalid mode. Valid modes are: {', '.join(MODE_ORDER)}", session.get("language"))), 400
        session["user_mode"] = mode
        return jsonify(mode=mode, message=translate_text("Mode updated successfully", session.get("language")))

    @app.get("/api/user-mode")
    def get_user_mode():
        """Get the current user mode from session."""
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        mode = session.get("user_mode", DEFAULT_MODE)
        return jsonify(mode=mode)

    @app.get("/api/language")
    @app.post("/api/language")
    def set_language():
        """Set the user's active UI language for the current session."""
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            requested = payload.get("language", session.get("language", DEFAULT_LANGUAGE))
        else:
            requested = session.get("language", DEFAULT_LANGUAGE)
        language = normalize_language(requested)
        session["language"] = language
        return jsonify(language=language, message=translate_text("Language updated successfully", language))

    @app.get("/api/alerts")
    def alerts_api():
        """Get weather alerts for a location."""
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        city = request.args.get("city", "").strip()
        if not city:
            return jsonify(error=translate_text("Select a location first.", session.get("language"))), 400
        try:
            weather = get_weather(city)
            language = normalize_language(session.get("language"))
            alerts = [translate_alert(alert, language) for alert in generate_weather_alerts(weather)]
            return jsonify(
                alerts=alerts,
                location=weather["location"],
            )
        except WeatherServiceError as error:
            return jsonify(error=translate_text(str(error), session.get("language"))), 400

    @app.post("/alerts/read-all")
    def dashboard_mark_all_alerts_read():
        """Form handler used by the dashboard alert history section."""
        user = current_user()
        if user is None:
            flash(translate_text("Please log in.", session.get("language")), "error")
            return redirect(url_for("login"))
        mark_all_alerts_read(user)
        return redirect(url_for("dashboard", city=session.get("selected_city", "Chennai")))

    @app.route("/api/alert-history", methods=["GET"])
    def alert_history_api():
        """Return the signed-in user's persistent alerts, newest first.

        The response is always scoped to the session user, so one user can
        never read another user's alerts.
        """
        user = current_user()
        if user is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        unread_only = str(request.args.get("unread", "")).strip().lower() in {"1", "true", "yes", "on"}
        alert_type = request.args.get("type", "").strip() or None
        try:
            limit = int(request.args.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        alerts = alert_history(user, unread_only=unread_only, limit=limit, alert_type=alert_type)
        return jsonify(
            alerts=[serialize_alert(alert) for alert in alerts],
            unread_count=unread_alert_count(user),
        )

    @app.post("/api/alert-history/<int:alert_id>/read")
    def mark_alert_read_api(alert_id):
        """Mark one of the signed-in user's alerts as read."""
        user = current_user()
        if user is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        alert = mark_alert_read(user, alert_id)
        if alert is None:
            return jsonify(error=translate_text("Alert not found.", session.get("language"))), 404
        return jsonify(alert=serialize_alert(alert), unread_count=unread_alert_count(user))

    @app.post("/api/alert-history/read-all")
    def mark_all_alerts_read_api():
        """Mark every alert owned by the signed-in user as read."""
        user = current_user()
        if user is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        updated = mark_all_alerts_read(user)
        return jsonify(updated=updated, unread_count=unread_alert_count(user))

    @app.route("/api/notification-preferences", methods=["GET", "POST"])
    def notification_preferences_api():
        """Read or store the signed-in user's notification preferences.

        Phase 2 only stores the preferences. Nothing is emailed or texted.
        """
        user = current_user()
        if user is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        location = _requested_preference_location(user)
        if location is None and _requested_preference_location_id() is not None:
            return jsonify(error=translate_text("Location not found.", session.get("language"))), 404
        if request.method == "GET":
            preference = get_notification_preference(user, location=location)
            db.session.commit()
        else:
            payload = request.get_json(silent=True) or request.form.to_dict() or {}
            _apply_user_notification_settings(user, payload)
            preference = update_notification_preference(user, payload, location=location)
            db.session.commit()
        response = serialize_preference(preference)
        response["phone"] = _masked_phone(user.phone)
        response["preferred_language"] = user.preferred_language
        response["preferred_mode"] = user.preferred_mode
        return jsonify(preferences=response)

    @app.get("/api/notification-status")
    def notification_status_api():
        """Report which delivery providers are configured.

        Requires a session and returns only masked, non-secret information so
        no SMTP password, API key, or SMS secret can ever leak.
        """
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        preference = get_notification_preference(current_user())
        status = notification_status()
        status["preferences"] = serialize_preference(preference)
        return jsonify(status)

    @app.post("/api/notifications/run-check")
    def run_alert_check_api():
        """Run one scheduled alert pass for the signed-in user on demand.

        This is a manual trigger for the same code path the scheduler uses; it
        is not a background job, so it never duplicates itself.
        """
        user = current_user()
        if user is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        from services.scheduler import process_user

        payload = request.get_json(silent=True) or {}
        city = str(payload.get("city", "") or "").strip()
        fetcher = get_weather
        if city:
            fetcher = lambda name: get_weather(city)  # noqa: E731 - explicit override
        report = process_user(user, fetcher)
        return jsonify(
            result={
                "location": report.get("location"),
                "alerts_created": report.get("alerts_created", 0),
                "error": report.get("error"),
            }
        )

    # ------------------------------------------------------------------
    # Phase 4: historical analytics
    # ------------------------------------------------------------------

    def _analytics_scope():
        """Resolve the signed-in user and validated date range for analytics.

        Returns ``(user, start, end, error_response)``. Ownership is enforced
        inside the analytics service by scoping every query to ``user.id``.
        """
        user = current_user()
        if user is None:
            return None, None, None, safe_error(
                translate_text("Please log in.", session.get("language")), 401, "unauthenticated"
            )
        start, end, _days, error = date_range(request.args)
        if error:
            return None, None, None, safe_error(error, 400, "invalid_range")
        return user, start, end, None

    @app.get("/analytics")
    def analytics_page():
        user = current_user()
        if user is None:
            flash(translate_text("Please log in to view analytics.", session.get("language")), "error")
            return redirect(url_for("login"))
        days = clamp_int(request.args.get("days"), 30, 1, 365)
        return render_template(
            "analytics.html",
            user=user,
            selected_city=session.get("selected_city", ""),
            unread_alerts=unread_alert_count(user),
            analytics_days=days,
        )

    @app.get("/api/analytics/summary")
    def analytics_summary_api():
        user, start, end, error = _analytics_scope()
        if error:
            return error
        return jsonify(analytics_summary(user, start, end))

    @app.get("/api/analytics/weather")
    def analytics_weather_api():
        user, start, end, error = _analytics_scope()
        if error:
            return error
        return jsonify(weather_analytics(user, start, end))

    @app.get("/api/analytics/predictions")
    def analytics_predictions_api():
        user, start, end, error = _analytics_scope()
        if error:
            return error
        return jsonify(prediction_analytics(user, start, end))

    @app.get("/api/analytics/risk")
    def analytics_risk_api():
        user, start, end, error = _analytics_scope()
        if error:
            return error
        return jsonify(risk_analytics(user, start, end))

    @app.get("/api/analytics/alerts")
    def analytics_alerts_api():
        user, start, end, error = _analytics_scope()
        if error:
            return error
        return jsonify(alert_analytics(user, start, end))

    @app.get("/api/analytics/all")
    def analytics_all_api():
        """Every analytics section in one request, used by the page."""
        user, start, end, error = _analytics_scope()
        if error:
            return error
        return jsonify(full_analytics(user, start, end))

    @app.get("/api/live/weather")
    def live_weather_api():
        """Phase 4: one poll endpoint for the live dashboard.

        It returns the current conditions, forecast, ML prediction, rule-based
        risk and unread alert count together so the browser makes a single
        request per refresh instead of one per widget.
        """
        user = current_user()
        if user is None:
            return safe_error(
                translate_text("Please log in.", session.get("language")), 401, "unauthenticated"
            )
        city = request.args.get("city", "").strip() or session.get("selected_city", "") or "Chennai"
        if not city:
            return safe_error(
                translate_text("Select a location first.", session.get("language")), 400, "missing_location"
            )
        try:
            weather = get_weather(city)
        except WeatherServiceError as error:
            # A clear error state is returned so the UI never shows stale or
            # invented values after a failed refresh.
            return safe_error(str(error), 502, "weather_unavailable")

        session["selected_city"] = weather["location"]["name"]
        try:
            rain_prediction = predict_rain(weather["current"])
        except MLPredictionError:
            rain_prediction = None

        language = normalize_language(session.get("language"))
        user_mode = session.get("user_mode", DEFAULT_MODE)
        risks = assess_risks(weather)
        guidance = personalized_guidance(
            weather,
            rain_prediction=rain_prediction,
            user_mode=user_mode,
            active_alerts=alert_history(user, unread_only=True, limit=5),
            language=language,
        )

        return jsonify(
            location=weather["location"],
            current=weather["current"],
            forecast=weather["forecast"][:7],
            units=weather.get("units", {}),
            rain_prediction=rain_prediction,
            risk=risks,
            risk_advice=risk_advice(risks),
            mode=user_mode,
            recommendation=guidance["text"],
            alerts=guidance["active_alert_types"],
            unread_count=unread_alert_count(user),
            updated_at=datetime.now(timezone.utc).isoformat() + "Z",
            sources={
                "weather": "Open-Meteo",
                "rain_prediction": (rain_prediction or {}).get("model_name") or "ML rainfall model",
                "risk": "Rule-based risk engine",
            },
        )

    @app.get("/api/summary")
    def summary_api():
        """Get today's AI weather summary."""
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        city = request.args.get("city", "").strip()
        if not city:
            return jsonify(error=translate_text("Select a location first.", session.get("language"))), 400
        try:
            weather = get_weather(city)
            language = normalize_language(session.get("language"))
            summary = translate_summary(generate_today_summary(weather), language)
            return jsonify(summary=summary, location=weather["location"])
        except WeatherServiceError as error:
            return jsonify(error=translate_text(str(error), session.get("language"))), 400

    @app.get("/api/recommendations")
    def recommendations_api():
        """Get personalized recommendations based on user mode and weather."""
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        city = request.args.get("city", "").strip()
        if not city:
            return jsonify(error=translate_text("Select a location first.", session.get("language"))), 400
        user_mode = session.get("user_mode", DEFAULT_MODE)
        try:
            weather = get_weather(city)
            language = normalize_language(session.get("language"))
            recommendation = translate_recommendation(get_recommendation_by_mode(weather, user_mode), language)
            best_time = translate_best_time(get_best_time_window(weather), language)
            return jsonify(
                recommendation=recommendation, best_time=best_time, mode=user_mode, location=weather["location"]
            )
        except WeatherServiceError as error:
            return jsonify(error=translate_text(str(error), session.get("language"))), 400

    @app.get("/assistant")
    def assistant():
        user = current_user()
        if user is None:
            flash(translate_text("Please log in to use the weather assistant.", session.get("language")), "error")
            return redirect(url_for("login"))
        city = request.args.get("city", "").strip() or session.get("selected_city", "")
        return render_template("assistant.html", user=user, selected_city=city)

    @app.post("/api/assistant")
    def assistant_api():
        user = current_user()
        if user is None:
            return jsonify(error=translate_text("Please log in to use the weather assistant.", session.get("language"))), 401
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        selected_city = str(payload.get("city", "")).strip() or session.get("selected_city", "")
        user_mode = session.get("user_mode", DEFAULT_MODE)
        if not question:
            return jsonify(error=translate_text("Ask a weather question to continue.", session.get("language"))), 400
        # Phase 3: a short follow-up such as "What about tomorrow?" reuses the
        # location and topic remembered from the previous turn.
        question, remembered_city, used_context = resolve_question(question, session.get("assistant_context"))
        if not selected_city:
            selected_city = remembered_city
        if not selected_city:
            return jsonify(error=translate_text("Select a location before asking a question.", session.get("language"))), 400
        try:
            city = explicit_location(question) or selected_city
            weather = get_weather(city)
            session["selected_city"] = weather["location"]["name"]
            try:
                rain_prediction = predict_rain(weather["current"])
            except MLPredictionError:
                rain_prediction = None
            mode_info = add_mode_context_to_question(question, user_mode)
            answer = answer_question(question, weather, rain_prediction, user_mode=user_mode)
            language = normalize_language(session.get("language"))
            answer = translate_answer_text(answer, language)
            intent = detect_intent(question, user_mode)
            session["assistant_context"] = update_context(
                session.get("assistant_context"),
                weather["location"]["name"],
                intent,
                language,
                user_mode,
            )
            guidance = personalized_guidance(
                weather,
                rain_prediction=rain_prediction,
                user_mode=user_mode,
                active_alerts=alert_history(user, unread_only=True, limit=5),
                language=language,
            )
            return jsonify(
                answer=answer,
                location=weather["location"],
                user_mode=user_mode,
                intent=intent,
                context_used=used_context == "true",
                recommendation=guidance["text"],
                alerts=guidance["active_alert_types"],
                mode_context=translate_text(mode_info, language),
            )
        except (WeatherServiceError, MLPredictionError) as error:
            return jsonify(error=translate_text(str(error), session.get("language"))), 400

    @app.get("/api/phase9/intelligence")
    def phase9_intelligence_api():
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        city = request.args.get("city", "").strip() or session.get("selected_city", "")
        if not city:
            return jsonify(error=translate_text("Select a location first.", session.get("language"))), 400
        try:
            weather = get_weather(city)
            session["selected_city"] = weather["location"]["name"]
            context = intelligence_context(weather, session.get("user_mode", DEFAULT_MODE))
            language = normalize_language(session.get("language"))
            context["condition"] = translate_text(context["condition"], language)
            context["recommendation"] = translate_text(context["recommendation"], language)
            context["location"] = weather["location"]
            return jsonify(context=context)
        except WeatherServiceError as error:
            return jsonify(error=translate_text(str(error), session.get("language"))), 400

    @app.get("/api/phase9/ml-explanation")
    def phase9_ml_explanation_api():
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        city = request.args.get("city", "").strip() or session.get("selected_city", "") or "Chennai"
        try:
            weather = get_weather(city)
            session["selected_city"] = weather["location"]["name"]
            try:
                prediction = predict_rain(weather["current"])
            except MLPredictionError:
                prediction = None
            explanation = explain_prediction(prediction)
            language = normalize_language(session.get("language"))
            explanation["message"] = translate_text(
                "Feature importance is unavailable for this prediction." if not explanation["available"] else "The prediction uses the available weather inputs; higher-importance factors contribute more to the model estimate.",
                language,
            )
            explanation["factors"] = [
                {**factor, "name": translate_text(factor.get("name", ""), language)}
                for factor in explanation["factors"]
            ]
            return jsonify(explanation=explanation, location=weather["location"])
        except WeatherServiceError as error:
            return jsonify(error=translate_text(str(error), session.get("language"))), 400

    @app.post("/api/phase9/scenario")
    def phase9_scenario_api():
        if current_user() is None:
            return jsonify(error=translate_text("Please log in.", session.get("language"))), 401
        payload = request.get_json(silent=True) or {}
        scenario = str(payload.get("scenario", "")).strip()
        city = str(payload.get("city", "")).strip() or session.get("selected_city", "") or "Chennai"
        if not city:
            return jsonify(error=translate_text("Select a location first.", session.get("language"))), 400
        try:
            weather = get_weather(city)
            session["selected_city"] = weather["location"]["name"]
            result = simulate_scenario(scenario, weather)
            language = normalize_language(session.get("language"))
            result["label"] = translate_text(result["label"], language)
            result["scenario"] = translate_text(result["scenario"], language)
            result["impact"] = translate_text(result["impact"], language)
            return jsonify(result=result)
        except (WeatherServiceError, ValueError) as error:
            return jsonify(error=translate_text(str(error), session.get("language"))), 400

    @app.route("/profile", methods=["GET", "POST"])
    def profile():
        user = current_user()
        if user is None:
            flash(translate_text("Please log in to view your profile.", session.get("language")), "error")
            return redirect(url_for("login"))
        if request.method == "POST":
            form = request.form
            # getlist is required: a checkbox group submits repeated keys and
            # form.to_dict() would silently keep only the first value.
            _apply_user_notification_settings(
                user,
                {
                    "email_enabled": form.get("email_enabled"),
                    "sms_enabled": form.get("sms_enabled"),
                    "phone": form.get("phone"),
                    "preferred_language": form.get("preferred_language"),
                    "preferred_mode": form.get("preferred_mode"),
                },
            )
            update_notification_preference(
                user,
                {
                    "email_enabled": form.get("email_enabled"),
                    "sms_enabled": form.get("sms_enabled"),
                    "alert_types": form.getlist("alert_types"),
                },
            )
            db.session.commit()
            flash(translate_text("Notification preferences saved.", session.get("language")), "success")
            return redirect(url_for("profile"))
        preference = get_notification_preference(user)
        db.session.commit()
        return render_template(
            "profile.html",
            user=user,
            preference=preference,
            preference_alert_types=PREFERENCE_ALERT_TYPES,
            preference_alert_type_labels=PREFERENCE_ALERT_TYPE_LABELS,
            selected_alert_types=set(parse_alert_types(preference.alert_types)),
            unread_alerts=unread_alert_count(user),
            delivery_status=notification_status(),
            supported_languages=SUPPORTED_LANGUAGES,
            supported_modes=MODE_ORDER,
        )

    @app.errorhandler(404)
    def page_not_found(error):
        language = normalize_language(session.get("language"))
        if wants_json():
            return safe_error(translate_text("The requested resource was not found.", language), 404, "not_found")
        return render_template("error.html", code=404, message=translate_text("The page you requested was not found.", language)), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        language = normalize_language(session.get("language"))
        if wants_json():
            return safe_error(translate_text("That method is not allowed here.", language), 405, "method_not_allowed")
        return render_template("error.html", code=405, message=translate_text("That method is not allowed here.", language)), 405

    @app.errorhandler(413)
    def payload_too_large(error):
        language = normalize_language(session.get("language"))
        if wants_json():
            return safe_error(translate_text("The request body is too large.", language), 413, "payload_too_large")
        return render_template("error.html", code=413, message=translate_text("The request body is too large.", language)), 413

    @app.errorhandler(500)
    def internal_server_error(error):
        # Phase 4: the client never receives a traceback, a path, or a secret.
        # The full detail stays in the server log for the operator.
        app.logger.error("Unhandled server error: %s", type(error).__name__)
        language = normalize_language(session.get("language"))
        if wants_json():
            return safe_error("Something went wrong on our side.", 500, "internal_error")
        return render_template("error.html", code=500, message=translate_text("Something went wrong on our side.", language)), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        """Catch-all so an unexpected failure returns a safe response.

        HTTP exceptions keep their own status; everything else becomes a
        logged 500 with no internal detail exposed to the caller.
        """
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unhandled exception on %s", request.path)
        if wants_json():
            return safe_error("Something went wrong on our side.", 500, "internal_error")
        language = normalize_language(session.get("language"))
        return render_template("error.html", code=500, message=translate_text("Something went wrong on our side.", language)), 500

    return app


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id is not None else None


def asset_url(filename):
    """Return a static URL with a cache-busting version query.

    The version is the asset's modification time, so a hard refresh (or a new
    deployment) always picks up the current file. This is deliberately derived
    from the filesystem rather than hard-coded, so it can never go stale.
    """
    static_root = os.path.join(current_app.root_path, "static")
    path = os.path.join(static_root, filename)
    try:
        version = int(os.path.getmtime(path))
    except OSError:
        version = 0
    return url_for("static", filename=filename, v=version)


def _masked_phone(phone):
    """Return a phone number safe to show in an API response or a form."""
    from services.notifications import mask_recipient

    return mask_recipient(phone)


def _apply_user_notification_settings(user, payload):
    """Store the Phase 3 per-user settings that live on the User model.

    Unknown keys are ignored and invalid values leave the stored value
    untouched, so a malformed request can never corrupt a profile.
    """
    from services.recommendations import normalize_mode
    from services.translations import normalize_language

    if user is None or not isinstance(payload, dict):
        return

    if "phone" in payload:
        from services.notifications import normalize_phone

        phone = normalize_phone(payload.get("phone") or "")
        user.phone = phone or None

    if "preferred_language" in payload and payload.get("preferred_language"):
        user.preferred_language = normalize_language(payload.get("preferred_language"))

    if "preferred_mode" in payload and payload.get("preferred_mode"):
        user.preferred_mode = normalize_mode(payload.get("preferred_mode"))


def _requested_preference_location_id():
    """Read an optional location id from the query string or the JSON body."""
    raw = request.args.get("location_id")
    if raw is None:
        payload = request.get_json(silent=True) or {}
        raw = payload.get("location_id") if isinstance(payload, dict) else None
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _requested_preference_location(user):
    """Resolve the requested location, enforcing that it belongs to the user."""
    location_id = _requested_preference_location_id()
    if location_id is None:
        return None
    return resolve_location(user, location_id)


def ensure_weather_columns():
    """Add Phase 3 fields to a database created during Phase 2."""
    existing_columns = {column["name"] for column in inspect(db.engine).get_columns("weather_record")}
    new_columns = {
        "latitude": "FLOAT",
        "longitude": "FLOAT",
        "weather_condition": "VARCHAR(120)",
        "precipitation": "FLOAT",
    }
    for column_name, column_type in new_columns.items():
        if column_name not in existing_columns:
            db.session.execute(text(f"ALTER TABLE weather_record ADD COLUMN {column_name} {column_type}"))
    db.session.commit()


def ensure_alert_columns():
    """Add the Phase 2 alert columns to a database created before Phase 2.

    Every added column is nullable, so existing users, weather records, and
    alerts keep their data. No table is dropped and no data is deleted.
    """
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    new_columns = {
        "risk_assessment": {
            "user_id": "INTEGER",
            "location_id": "INTEGER",
            "details": "TEXT",
        },
        "alert": {"severity": "VARCHAR(30)"},
    }
    for table_name, columns in new_columns.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, column_type in columns.items():
            if column_name not in existing_columns:
                db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
    db.session.commit()


def ensure_user_columns():
    """Add the Phase 3 personalization columns to a pre-Phase-3 database.

    Every column is nullable, so existing users keep all of their data. No
    table is dropped and nothing is deleted.
    """
    inspector = inspect(db.engine)
    if "user" not in set(inspector.get_table_names()):
        return
    existing_columns = {column["name"] for column in inspector.get_columns("user")}
    new_columns = {
        "phone": "VARCHAR(32)",
        "preferred_language": "VARCHAR(8)",
        "preferred_mode": "VARCHAR(32)",
        "default_location": "VARCHAR(120)",
    }
    for column_name, column_type in new_columns.items():
        if column_name not in existing_columns:
            db.session.execute(text(f"ALTER TABLE user ADD COLUMN {column_name} {column_type}"))
    db.session.commit()


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")