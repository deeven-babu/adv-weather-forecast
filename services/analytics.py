"""Phase 4 historical analytics over the data Phases 1-3 already persist.

This module adds NO new tables. It aggregates the existing models and always
scopes results to the signed-in user, so one account can never see another
account's history.

Three genuinely different sources are kept explicitly separate and are
labelled as such in every response, because they are not the same system:

* ``SOURCE_WEATHER``  - Open-Meteo observations/forecast stored in
  ``WeatherRecord``.
* ``SOURCE_ML``       - the trained rainfall model stored in ``Prediction``.
* ``SOURCE_RISK``     - the rule-based thresholds in ``services.risk``,
  stored in ``RiskAssessment``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from models import Alert, Location, Prediction, RiskAssessment, WeatherRecord, db
from services.risk import RISK_CATEGORIES

#: Timezone-aware UTC now, used for the "generated at" stamp in responses.
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SOURCE_WEATHER = "open_meteo_forecast"
SOURCE_ML = "ml_rainfall_model"
SOURCE_RISK = "rule_based_risk_engine"

SOURCE_LABELS = {
    SOURCE_WEATHER: "Weather forecast (Open-Meteo)",
    SOURCE_ML: "ML rainfall prediction (trained model)",
    SOURCE_RISK: "Disaster risk (rule-based engine)",
}

#: A risk at or above this level counts as a high-risk event.
HIGH_RISK_LEVELS = ("High", "Critical")

#: Risk category key -> the label stored in ``RiskAssessment.risk_type``.
RISK_TYPE_LABELS = {
    "flood": "Flood",
    "heatwave": "Heatwave",
    "rain": "Heavy rain",
}


def user_location_ids(user) -> list[int]:
    """Return the ids of the locations owned by this user."""
    if user is None:
        return []
    rows = db.session.query(Location.id).filter(Location.user_id == user.id).all()
    return [row[0] for row in rows]


def _empty() -> dict[str, Any]:
    """Return the canonical 'no data in range' payload."""
    return {
        "sample_size": 0,
        "has_data": False,
        "generated_at": _utc_now_iso(),
    }


def _round(value, digits: int = 1):
    """Round a number, tolerating ``None``."""
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _average(values) -> Optional[float]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


# --------------------------------------------------------------------------
# Shared query helpers
# --------------------------------------------------------------------------

def _weather_records(location_ids, start, end):
    """WeatherRecord rows for these locations inside the range."""
    if not location_ids:
        return []
    return (
        WeatherRecord.query.filter(WeatherRecord.location_id.in_(location_ids))
        .filter(WeatherRecord.recorded_at >= start)
        .filter(WeatherRecord.recorded_at <= end)
        .order_by(WeatherRecord.recorded_at.asc())
        .all()
    )


def _predictions(location_ids, start, end):
    """Prediction rows joined through WeatherRecord to the user's locations.

    ``Prediction`` has no direct owner column, so ownership is resolved through
    its ``WeatherRecord`` -> ``Location`` relation, which already carries
    ``user_id``.
    """
    if not location_ids:
        return []
    return (
        Prediction.query.join(WeatherRecord, Prediction.weather_record_id == WeatherRecord.id)
        .filter(WeatherRecord.location_id.in_(location_ids))
        .filter(WeatherRecord.recorded_at >= start)
        .filter(WeatherRecord.recorded_at <= end)
        .order_by(WeatherRecord.recorded_at.asc())
        .all()
    )


def _risk_rows(user, location_ids, start, end):
    """RiskAssessment rows owned by this user inside the range."""
    if user is None or not location_ids:
        return []
    return (
        RiskAssessment.query.filter(RiskAssessment.user_id == user.id)
        .filter(RiskAssessment.location_id.in_(location_ids))
        .filter(RiskAssessment.created_at >= start)
        .filter(RiskAssessment.created_at <= end)
        .order_by(RiskAssessment.created_at.asc())
        .all()
    )


def _alerts(user, start, end):
    """Alert rows owned by this user inside the range."""
    if user is None:
        return []
    return (
        Alert.query.filter(Alert.user_id == user.id)
        .filter(Alert.created_at >= start)
        .filter(Alert.created_at <= end)
        .order_by(Alert.created_at.asc())
        .all()
    )


def _bucket_by_day(rows, stamp_getter, series: dict[str, Any]) -> list[dict]:
    """Group rows into per-day buckets with averaged/min/max series.

    ``series`` maps an output field name to a callable that reads the value
    from a row. Returns a list ordered by date.
    """
    buckets: dict[str, dict[str, list]] = {}
    for row in rows:
        stamp = stamp_getter(row)
        if stamp is None:
            continue
        key = stamp.strftime("%Y-%m-%d")
        bucket = buckets.setdefault(key, {name: [] for name in series})
        for name, getter in series.items():
            bucket[name].append(getter(row))

    timeline = []
    for day in sorted(buckets):
        bucket = buckets[day]
        entry: dict[str, Any] = {"date": day}
        for name, values in bucket.items():
            clean = [value for value in values if value is not None]
            entry[name] = _round(_average(clean)) if clean else None
            entry[f"{name}_min"] = _round(min(clean)) if clean else None
            entry[f"{name}_max"] = _round(max(clean)) if clean else None
            entry[f"{name}_count"] = len(clean)
        timeline.append(entry)
    return timeline


def _counts_by(rows, getter) -> list[dict]:
    """Return a sorted ``[{label, count}]`` breakdown."""
    counts: dict[str, int] = {}
    for row in rows:
        label = getter(row) or "Unknown"
        counts[str(label)] = counts.get(str(label), 0) + 1
    return [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

def analytics_summary(user, start, end) -> dict[str, Any]:
    """Headline counts across every persisted system for this user."""
    location_ids = user_location_ids(user)
    records = _weather_records(location_ids, start, end)
    predictions = _predictions(location_ids, start, end)
    risks = _risk_rows(user, location_ids, start, end)
    alerts = _alerts(user, start, end)

    probabilities = [row.probability for row in predictions if row.probability is not None]
    average_probability = _round(_average(probabilities) * 100) if probabilities else None
    rain_expected = sum(1 for row in predictions if (row.result or "").lower().startswith("rain"))
    no_rain = len(predictions) - rain_expected
    high_risk_events = sum(1 for row in risks if row.risk_level in HIGH_RISK_LEVELS)
    unread = sum(1 for row in alerts if not row.is_read)

    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "generated_at": _utc_now_iso(),
        "has_data": bool(records or predictions or risks or alerts),
        "sources": SOURCE_LABELS,
        "totals": {
            "weather_records": len(records),
            "predictions": len(predictions),
            "risk_assessments": len(risks),
            "alerts": len(alerts),
            "unread_alerts": unread,
            "high_risk_events": high_risk_events,
        },
        "average_rainfall_probability_percent": average_probability,
        "prediction_distribution": {
            "rain_expected": rain_expected,
            "no_rain_expected": max(0, no_rain),
        },
        "risk_distribution": _counts_by(risks, lambda row: row.risk_level),
        "alerts_by_type": _counts_by(alerts, lambda row: row.alert_type),
    }


# --------------------------------------------------------------------------
# Weather (Open-Meteo)
# --------------------------------------------------------------------------

def weather_analytics(user, start, end) -> dict[str, Any]:
    """Historical temperature, humidity, wind and rain probability."""
    location_ids = user_location_ids(user)
    records = _weather_records(location_ids, start, end)

    timeline = _bucket_by_day(
        records,
        lambda row: row.recorded_at,
        {
            "temperature": lambda row: row.temperature,
            "humidity": lambda row: row.humidity,
            "wind_speed": lambda row: row.wind_speed,
            "pressure": lambda row: row.pressure,
        },
    )
    temperatures = [row.temperature for row in records if row.temperature is not None]
    humidities = [row.humidity for row in records if row.humidity is not None]

    return {
        "source": SOURCE_WEATHER,
        "source_label": SOURCE_LABELS[SOURCE_WEATHER],
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "sample_size": len(records),
        "has_data": bool(records),
        "averages": {
            "temperature": _round(_average(temperatures)),
            "humidity": _round(_average(humidities)),
            "wind_speed": _round(_average([row.wind_speed for row in records])),
        },
        "extremes": {
            "temperature_min": _round(min(temperatures)) if temperatures else None,
            "temperature_max": _round(max(temperatures)) if temperatures else None,
        },
        "conditions": _counts_by(records, lambda row: row.weather_condition),
        "timeline": timeline,
    }


# --------------------------------------------------------------------------
# ML rainfall predictions (trained model)
# --------------------------------------------------------------------------

def prediction_analytics(user, start, end) -> dict[str, Any]:
    """Distribution of the trained model's rainfall predictions.

    This is explicitly NOT the Open-Meteo forecast and NOT the rule-based
    disaster risk.
    """
    location_ids = user_location_ids(user)
    predictions = _predictions(location_ids, start, end)

    probabilities = [row.probability for row in predictions if row.probability is not None]
    bands = {"0-25%": 0, "25-50%": 0, "50-75%": 0, "75-100%": 0}
    for probability in probabilities:
        percent = float(probability) * 100
        if percent < 25:
            bands["0-25%"] += 1
        elif percent < 50:
            bands["25-50%"] += 1
        elif percent < 75:
            bands["50-75%"] += 1
        else:
            bands["75-100%"] += 1

    rain_expected = sum(1 for row in predictions if (row.result or "").lower().startswith("rain"))

    return {
        "source": SOURCE_ML,
        "source_label": SOURCE_LABELS[SOURCE_ML],
        "note": "This is the project's trained rainfall model, not the Open-Meteo forecast.",
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "sample_size": len(predictions),
        "has_data": bool(predictions),
        "average_probability_percent": _round(_average(probabilities) * 100) if probabilities else None,
        "distribution": {
            "rain_expected": rain_expected,
            "no_rain_expected": max(0, len(predictions) - rain_expected),
        },
        "probability_bands": [{"label": label, "count": count} for label, count in bands.items()],
        "timeline": _bucket_by_day(
            predictions,
            lambda row: row.weather_record.recorded_at if row.weather_record else row.created_at,
            {"probability_percent": lambda row: (row.probability or 0) * 100},
        ),
    }


# --------------------------------------------------------------------------
# Rule-based disaster risk
# --------------------------------------------------------------------------

def risk_analytics(user, start, end) -> dict[str, Any]:
    """Risk level distribution and trend for flood, heatwave and heavy rain.

    The levels come from the existing ``services.risk`` thresholds; this
    function only counts what was persisted.
    """
    location_ids = user_location_ids(user)
    rows = _risk_rows(user, location_ids, start, end)

    categories = {}
    for key in RISK_CATEGORIES:
        label = RISK_TYPE_LABELS[key]
        category_rows = [row for row in rows if row.risk_type == label]
        categories[label] = {
            "total": len(category_rows),
            "levels": _level_counts(category_rows),
            "highest_level": _highest_level(category_rows),
            "average_score": _round(_average([row.risk_score for row in category_rows])),
        }

    return {
        "source": SOURCE_RISK,
        "source_label": SOURCE_LABELS[SOURCE_RISK],
        "note": "Levels come from the rule-based threshold engine, not from a machine-learning model.",
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "sample_size": len(rows),
        "has_data": bool(rows),
        "categories": categories,
        "overall_levels": _level_counts(rows),
        "high_risk_events": sum(1 for row in rows if row.risk_level in HIGH_RISK_LEVELS),
        "timeline": _bucket_by_day(
            [row for row in rows if row.risk_type == RISK_TYPE_LABELS["flood"]],
            lambda row: row.created_at,
            {"flood_score": lambda row: row.risk_score},
        ),
    }


def _level_counts(rows) -> list[dict]:
    """Count rows per risk level, always including all four levels."""
    counts = {"Low": 0, "Moderate": 0, "High": 0, "Critical": 0}
    for row in rows:
        level = str(row.risk_level or "Low")
        counts[level] = counts.get(level, 0) + 1
    return [{"label": label, "count": counts[label]} for label in ("Low", "Moderate", "High", "Critical")]


def _highest_level(rows) -> Optional[str]:
    """The most severe level present, or ``None`` when there are no rows."""
    order = ("Low", "Moderate", "High", "Critical")
    present = [str(row.risk_level) for row in rows if row.risk_level in order]
    if not present:
        return None
    return max(present, key=order.index)


# --------------------------------------------------------------------------
# Alerts
# --------------------------------------------------------------------------

def alert_analytics(user, start, end) -> dict[str, Any]:
    """Alerts by type, by severity, over time, and read/unread counts."""
    alerts = _alerts(user, start, end)
    unread = sum(1 for row in alerts if not row.is_read)

    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "sample_size": len(alerts),
        "has_data": bool(alerts),
        "by_type": _counts_by(alerts, lambda row: row.alert_type),
        "by_severity": _counts_by(alerts, lambda row: row.severity or "Moderate"),
        "read_state": {
            "read": len(alerts) - unread,
            "unread": unread,
        },
        "timeline": _bucket_by_day(
            alerts,
            lambda row: row.created_at,
            {"alerts": lambda row: 1},
        ),
        "recent": [
            {
                "id": row.id,
                "alert_type": row.alert_type,
                "severity": row.severity or "Moderate",
                "is_read": bool(row.is_read),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "location": row.location.name if row.location else None,
            }
            for row in alerts[-10:][::-1]
        ],
    }


# --------------------------------------------------------------------------
# Combined dashboard payload
# --------------------------------------------------------------------------

def full_analytics(user, start, end) -> dict[str, Any]:
    """Every analytics section in one response, for the analytics dashboard."""
    return {
        "summary": analytics_summary(user, start, end),
        "weather": weather_analytics(user, start, end),
        "predictions": prediction_analytics(user, start, end),
        "risk": risk_analytics(user, start, end),
        "alerts": alert_analytics(user, start, end),
    }


def analytics_preview(user, start, end) -> dict[str, Any]:
    """A compact subset used by the dashboard's analytics preview card."""
    summary = analytics_summary(user, start, end)
    alerts = alert_analytics(user, start, end)
    return {
        "totals": summary["totals"],
        "has_data": summary["has_data"],
        "alerts_by_type": alerts["by_type"][:5],
        "risk_distribution": summary["risk_distribution"],
        "alert_timeline": alerts["timeline"][-14:],
    }
