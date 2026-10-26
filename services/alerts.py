"""Phase 2 disaster alert persistence and alert management.

This module connects the existing Phase 1 rule-based systems
(``services.risk`` and ``services.recommendations.generate_weather_alerts``)
to the existing database models (``Prediction``, ``RiskAssessment``, ``Alert``
and ``NotificationPreference``).

Design rules kept deliberately simple and reliable:

* The rule thresholds are NOT re-implemented here. ``assess_risks`` from
  ``services.risk`` remains the single source of truth.
* Every write is deduplicated on the fields the schema actually provides, so
  refreshing the dashboard never produces an endless stream of rows.
* Nothing is emailed or texted. Notification preferences are only stored.
"""

from datetime import datetime, timedelta, timezone

from models import (
    Alert,
    Location,
    NotificationPreference,
    Prediction,
    RiskAssessment,
    WeatherRecord,
    db,
)
from services.recommendations import generate_weather_alerts
from services.risk import RISK_CATEGORIES, assess_risks, risk_advice

# --------------------------------------------------------------------------
# Phase 2 constants
# --------------------------------------------------------------------------

#: The existing Phase 1 severity ladder, ordered so alerts can be filtered.
SEVERITY_ORDER = ("Low", "Moderate", "High", "Critical")

#: A risk at or above this level raises a persistent alert. "Low" never does,
#: which matches the existing Phase 1 behaviour where calm weather is silent.
ALERT_SEVERITY_THRESHOLD = "Moderate"

#: Duplicate-prevention window. Refreshing the dashboard inside this window for
#: the same user, location, alert type and severity updates nothing.
ALERT_DEDUPLICATION_WINDOW = timedelta(hours=6)
PREDICTION_DEDUPLICATION_WINDOW = timedelta(hours=1)
RISK_DEDUPLICATION_WINDOW = timedelta(hours=6)

#: Risk category -> stored ``RiskAssessment.risk_type`` label.
RISK_TYPE_LABELS = {
    "flood": "Flood",
    "heatwave": "Heatwave",
    "rain": "Heavy rain",
}

#: Risk category -> ``Alert.alert_type`` used for the persistent disaster alert.
RISK_ALERT_TYPES = {
    "flood": "Flood",
    "heatwave": "Heatwave",
    "rain": "Heavy rain",
}

#: Display score stored in ``RiskAssessment.risk_score`` so the history has a
#: sortable number. This is a presentation scale only; the rule thresholds that
#: produced the level are unchanged.
RISK_LEVEL_SCORES = {"Low": 20.0, "Moderate": 50.0, "High": 75.0, "Critical": 95.0}

#: Default value for ``NotificationPreference.alert_types`` (model default).
DEFAULT_ALERT_TYPES = "heavy_rain,flood,heatwave"

#: Alert types the Phase 2 preferences UI offers to switch on and off.
PREFERENCE_ALERT_TYPES = (
    "flood",
    "heatwave",
    "heavy_rain",
    "high_temperature",
    "strong_wind",
    "thunderstorm",
)

PREFERENCE_ALERT_TYPE_LABELS = {
    "flood": "Flood alerts",
    "heatwave": "Heatwave alerts",
    "heavy_rain": "Heavy rain alerts",
    "high_temperature": "High temperature alerts",
    "strong_wind": "Strong wind alerts",
    "thunderstorm": "Thunderstorm alerts",
}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _now():
    """Return an aware UTC timestamp, matching the model column defaults."""
    return datetime.now(timezone.utc)


def severity_rank(severity):
    """Return a sortable rank for a severity label; unknown labels sort lowest."""
    try:
        return SEVERITY_ORDER.index(str(severity or "").strip())
    except ValueError:
        return -1


def reaches_alert_threshold(severity):
    """True when a Phase 1 level is serious enough to raise a persistent alert."""
    return severity_rank(severity) >= severity_rank(ALERT_SEVERITY_THRESHOLD)


def alert_type_slug(alert_type):
    """Normalise an alert type into the slug used by notification preferences."""
    return str(alert_type or "").strip().lower().replace(" ", "_").replace("-", "_")


def alert_type_matches_preference(alert_type, allowed_types):
    """True when an alert type is covered by the stored preference slugs."""
    slug = alert_type_slug(alert_type)
    if not slug:
        return False
    allowed = {str(item).strip().lower().replace(" ", "_") for item in allowed_types if str(item).strip()}
    # A directly toggleable type is only enabled when it is switched on.
    if slug in PREFERENCE_ALERT_TYPES:
        return slug in allowed
    # Rain / temperature / wind / thunderstorm warnings are governed by their
    # family switch, so "High Rain Probability" follows "heavy_rain".
    if "rain" in slug.split("_"):
        return "heavy_rain" in allowed
    if "temperature" in slug:
        return "high_temperature" in allowed
    if "wind" in slug:
        return "strong_wind" in allowed
    if "storm" in slug:
        return "thunderstorm" in allowed
    # Advisory warnings such as "Poor Outdoor Conditions" and "Travel Caution"
    # are not a toggleable family, so they stay enabled.
    return True


def parse_alert_types(raw):
    """Return a clean list of preference slugs from a comma string or a list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        candidates = [part for part in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        candidates = list(raw)
    else:
        candidates = [raw]
    slugs = []
    for candidate in candidates:
        slug = alert_type_slug(candidate)
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def _coerce_bool(value, default=None):
    """Accept JSON booleans and form strings such as "on"/"true"."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on", "enabled"}:
        return True
    if text in {"false", "0", "no", "off", "disabled", ""}:
        return False
    return default


# --------------------------------------------------------------------------
# Step 2: ML prediction persistence
# --------------------------------------------------------------------------

def _prediction_exists(location, prediction_type, window):
    """Return an existing recent prediction for this location and type.

    The user is implied by the location, because ``Location`` already carries
    ``user_id``. This keeps the dedup rule inside the existing schema.
    """
    cutoff = _now() - window
    return (
        Prediction.query.join(WeatherRecord, Prediction.weather_record_id == WeatherRecord.id)
        .filter(WeatherRecord.location_id == location.id)
        .filter(Prediction.prediction_type == prediction_type)
        .filter(Prediction.created_at >= cutoff)
        .order_by(Prediction.created_at.desc())
        .first()
    )


def persist_prediction(user, location, weather_record, rain_prediction):
    """Persist a valid ML rainfall prediction using the existing Prediction model.

    Deduplication uses the fields the schema provides: the same user (through
    the location), the same location, the same prediction type, and a recent
    timestamp window. The ML model, its features, and its thresholds are never
    touched here.
    """
    if user is None or location is None or weather_record is None or not rain_prediction:
        return None

    prediction_type = "rain"
    existing = _prediction_exists(location, prediction_type, PREDICTION_DEDUPLICATION_WINDOW)
    if existing is not None:
        return existing

    prediction = Prediction(
        weather_record=weather_record,
        prediction_type=prediction_type,
        probability=rain_prediction.get("probability"),
        result=rain_prediction.get("prediction"),
    )
    db.session.add(prediction)
    db.session.flush()
    return prediction


# --------------------------------------------------------------------------
# Step 3: rule-based disaster risk persistence
# --------------------------------------------------------------------------

def _risk_assessment_exists(user, location, risk_type, risk_level, window):
    """Return an existing recent assessment for this user/location/category."""
    cutoff = _now() - window
    return (
        RiskAssessment.query.filter(RiskAssessment.user_id == user.id)
        .filter(RiskAssessment.location_id == location.id)
        .filter(RiskAssessment.risk_type == risk_type)
        .filter(RiskAssessment.risk_level == risk_level)
        .filter(RiskAssessment.created_at >= cutoff)
        .order_by(RiskAssessment.created_at.desc())
        .first()
    )


def persist_risk_assessments(user, location, weather, prediction=None):
    """Persist the Phase 1 rule-based risk levels for all three categories.

    ``services.risk.assess_risks`` decides the level; this function only stores
    the outcome. No new threshold is introduced and nothing becomes machine
    learned.
    """
    if user is None or location is None or not weather:
        return []

    risks = assess_risks(weather)
    advice = risk_advice(risks)
    saved = []
    for category in RISK_CATEGORIES:
        level = risks.get(category, "Low")
        existing = _risk_assessment_exists(
            user, location, RISK_TYPE_LABELS[category], level, RISK_DEDUPLICATION_WINDOW
        )
        if existing is not None:
            saved.append(existing)
            continue
        assessment = RiskAssessment(
            prediction_id=prediction.id if prediction is not None else None,
            user_id=user.id,
            location_id=location.id,
            risk_type=RISK_TYPE_LABELS[category],
            risk_level=level,
            risk_score=RISK_LEVEL_SCORES.get(level, 0.0),
            details=advice.get(category, ""),
        )
        db.session.add(assessment)
        saved.append(assessment)
    db.session.flush()
    return saved


# --------------------------------------------------------------------------
# Step 8: notification preferences
# --------------------------------------------------------------------------

def get_notification_preference(user, location=None):
    """Return the user's preference row, creating a default one on first use.

    ``location=None`` means the account-wide preference. Nothing is sent; the
    row only records what the user wants for Phase 3.
    """
    if user is None:
        return None
    query = NotificationPreference.query.filter(NotificationPreference.user_id == user.id)
    if location is None:
        query = query.filter(NotificationPreference.location_id.is_(None))
    else:
        query = query.filter(NotificationPreference.location_id == location.id)
    preference = query.first()
    if preference is None:
        preference = NotificationPreference(
            user_id=user.id,
            location_id=location.id if location is not None else None,
            email_enabled=True,
            sms_enabled=False,
            alert_types=DEFAULT_ALERT_TYPES,
        )
        db.session.add(preference)
        db.session.flush()
    return preference


def alert_type_enabled(user, alert_type):
    """True when the user has not disabled this alert type.

    An account with no saved preference is treated as "the default alert types
    are enabled" so the Phase 2 alert system works out of the box.
    """
    if user is None:
        return False
    preference = NotificationPreference.query.filter(NotificationPreference.user_id == user.id).first()
    if preference is None:
        return True
    return alert_type_matches_preference(alert_type, parse_alert_types(preference.alert_types))


def serialize_preference(preference):
    """Return the JSON shape for a notification preference row."""
    if preference is None:
        return {
            "email_enabled": True,
            "sms_enabled": False,
            "alert_types": parse_alert_types(DEFAULT_ALERT_TYPES),
            "available_alert_types": list(PREFERENCE_ALERT_TYPES),
        }
    return {
        "email_enabled": bool(preference.email_enabled),
        "sms_enabled": bool(preference.sms_enabled),
        "alert_types": parse_alert_types(preference.alert_types),
        "available_alert_types": list(PREFERENCE_ALERT_TYPES),
    }


def update_notification_preference(user, payload, location=None):
    """Create or update the stored notification preference. Stores only.

    No email and no SMS is sent in Phase 2.
    """
    if user is None:
        return None
    data = payload or {}
    preference = get_notification_preference(user, location=location)

    email_enabled = _coerce_bool(data.get("email_enabled"), default=None)
    if email_enabled is not None:
        preference.email_enabled = email_enabled
    sms_enabled = _coerce_bool(data.get("sms_enabled"), default=None)
    if sms_enabled is not None:
        preference.sms_enabled = sms_enabled
    if "alert_types" in data:
        slugs = parse_alert_types(data.get("alert_types"))
        preference.alert_types = ",".join(slugs)
    db.session.flush()
    return preference


# --------------------------------------------------------------------------
# Steps 4 + 5: alert generation with duplicate prevention
# --------------------------------------------------------------------------

def _recent_alert_keys(user, location, window):
    """Return the (slug, severity) keys of this user's recent alerts.

    Matching on the slug rather than the raw type keeps "Heavy rain" (from the
    risk rules) and "Heavy Rain" (from the weather warnings) as one event, so
    the same condition can never be stored twice under two spellings.
    """
    cutoff = _now() - window
    recent = (
        Alert.query.filter(Alert.user_id == user.id)
        .filter(Alert.location_id == location.id)
        .filter(Alert.created_at >= cutoff)
        .all()
    )
    return {(alert_type_slug(alert.alert_type), alert.severity) for alert in recent}


def _alert_candidates(weather):
    """Build alert candidates from the existing Phase 1 rules only.

    The sources are the centralized ``services.risk`` levels and the existing
    ``generate_weather_alerts`` weather warnings. No new dangerous-weather
    threshold is defined here.
    """
    candidates = []
    risks = assess_risks(weather)
    advice = risk_advice(risks)
    for category in RISK_CATEGORIES:
        level = risks.get(category, "Low")
        if not reaches_alert_threshold(level):
            continue
        label = RISK_ALERT_TYPES[category]
        candidates.append(
            {
                "alert_type": label,
                "severity": level,
                "message": "{} risk is {}. {}".format(label, level, advice.get(category, "")).strip(),
            }
        )
    for weather_alert in generate_weather_alerts(weather):
        candidates.append(
            {
                "alert_type": weather_alert.type,
                "severity": weather_alert.severity,
                "message": weather_alert.message,
            }
        )
    return candidates


def generate_alerts(user, location, weather, window=ALERT_DEDUPLICATION_WINDOW):
    """Create persistent alerts for the current weather, skipping duplicates.

    Returns the alerts that were actually created.
    """
    if user is None or location is None or not weather:
        return []

    created = []
    existing_keys = _recent_alert_keys(user, location, window)
    for candidate in _alert_candidates(weather):
        alert_type = candidate["alert_type"]
        severity = candidate["severity"]
        if not alert_type_enabled(user, alert_type):
            continue
        # Duplicate rule: same user + location + alert type + severity within
        # the same active weather/risk event window. "Heavy rain" and "Heavy
        # Rain" share a slug, so one storm never raises two rain alerts.
        event_key = (alert_type_slug(alert_type), severity)
        if event_key in existing_keys:
            continue
        existing_keys.add(event_key)
        alert = Alert(
            user_id=user.id,
            location_id=location.id,
            alert_type=alert_type,
            severity=severity,
            message=candidate["message"],
            is_read=False,
        )
        db.session.add(alert)
        created.append(alert)
    db.session.flush()
    return created


# --------------------------------------------------------------------------
# Step 9: the full weather -> prediction -> risk -> alert workflow
# --------------------------------------------------------------------------

def process_weather_observations(user, location, weather, weather_record=None, rain_prediction=None):
    """Run the complete Phase 2 persistence pipeline for one weather payload.

    weather -> ML prediction -> rule-based risk -> alert evaluation ->
    duplicate check -> save. A single commit is issued at the end, and any
    failure rolls back without leaving a half-written row behind.
    """
    if user is None or location is None or not weather:
        return {"prediction": None, "risk_assessments": [], "alerts": []}

    try:
        prediction = persist_prediction(user, location, weather_record, rain_prediction)
        assessments = persist_risk_assessments(user, location, weather, prediction=prediction)
        alerts = generate_alerts(user, location, weather)
        db.session.commit()
        return {"prediction": prediction, "risk_assessments": assessments, "alerts": alerts}
    except Exception:
        db.session.rollback()
        return {"prediction": None, "risk_assessments": [], "alerts": []}


# --------------------------------------------------------------------------
# Steps 6 + 7: alert history and read/unread
# --------------------------------------------------------------------------

def serialize_alert(alert):
    """Return the JSON shape for a persistent alert."""
    return {
        "id": alert.id,
        "alert_type": alert.alert_type,
        "severity": alert.severity or "Moderate",
        "message": alert.message,
        "is_read": bool(alert.is_read),
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "location": alert.location.name if alert.location else None,
    }


def alert_history(user, unread_only=False, limit=50, alert_type=None):
    """Return a user's own alerts, newest first.

    The query is always scoped to ``user.id`` so one user can never read
    another user's alerts.
    """
    if user is None:
        return []
    query = Alert.query.filter(Alert.user_id == user.id)
    if unread_only:
        query = query.filter(Alert.is_read.is_(False))
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    query = query.order_by(Alert.created_at.desc(), Alert.id.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def unread_alert_count(user):
    """Number of unread alerts owned by this user."""
    if user is None:
        return 0
    return Alert.query.filter(Alert.user_id == user.id).filter(Alert.is_read.is_(False)).count()


def owned_alert(user, alert_id):
    """Return the alert only when it belongs to this user, otherwise None."""
    if user is None or alert_id is None:
        return None
    return Alert.query.filter(Alert.id == alert_id).filter(Alert.user_id == user.id).first()


def mark_alert_read(user, alert_id):
    """Mark one owned alert as read. Returns the alert, or None if not owned."""
    alert = owned_alert(user, alert_id)
    if alert is None:
        return None
    if not alert.is_read:
        alert.is_read = True
        db.session.commit()
    return alert


def mark_all_alerts_read(user):
    """Mark every owned alert as read and return how many changed."""
    if user is None:
        return 0
    updated = (
        Alert.query.filter(Alert.user_id == user.id)
        .filter(Alert.is_read.is_(False))
        .update({Alert.is_read: True}, synchronize_session=False)
    )
    db.session.commit()
    return updated


def resolve_location(user, location_id):
    """Return a location only when it belongs to this user."""
    if user is None or not location_id:
        return None
    return Location.query.filter(Location.id == location_id).filter(Location.user_id == user.id).first()
