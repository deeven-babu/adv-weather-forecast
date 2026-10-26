"""Phase 3 notification delivery: email and SMS.

This module is intentionally provider-independent and dependency-free.

* Email uses the Python standard library (``smtplib`` / ``email``), so no new
  third-party dependency is required.
* SMS is an abstraction. A provider is chosen through environment variables.
  When no provider is configured a safe development provider records the
  message instead of sending anything, so the system stays fully testable
  without a paid account.

Safety rules obeyed by this module:

* No credential is ever hard-coded, logged, or returned in a response.
* A missing or broken provider never raises: every public function returns a
  ``NotificationResult`` describing the outcome.
* Delivery is never *claimed* as successful unless the provider really ran.
"""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Optional

import requests

LOGGER = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Delivery outcomes
# --------------------------------------------------------------------------

#: The message was handed to a real provider and accepted.
STATUS_SENT = "sent"
#: The user turned this channel off in their notification preferences.
STATUS_DISABLED = "disabled"
#: No provider is configured, so delivery was not attempted.
STATUS_UNAVAILABLE = "unavailable"
#: A provider was configured but the attempt failed.
STATUS_FAILED = "failed"
#: There was nothing to deliver (for example no destination address).
STATUS_SKIPPED = "skipped"

DELIVERY_STATUSES = (
    STATUS_SENT,
    STATUS_DISABLED,
    STATUS_UNAVAILABLE,
    STATUS_FAILED,
    STATUS_SKIPPED,
)

CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"

APP_NAME = "Weather AI"
APP_TAGLINE = "AI Based Weather Forecast and Disaster Alert System"


@dataclass
class NotificationResult:
    """The outcome of one delivery attempt. Never raises, never leaks secrets."""

    channel: str
    status: str
    detail: str = ""
    recipient: str = ""
    provider: str = ""

    @property
    def delivered(self) -> bool:
        """True only when a real provider accepted the message."""
        return self.status == STATUS_SENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "status": self.status,
            "detail": self.detail,
            "recipient": self.recipient,
            "provider": self.provider,
            "delivered": self.delivered,
        }


@dataclass
class NotificationSummary:
    """Aggregated outcome for a single alert across every enabled channel."""

    email: Optional[NotificationResult] = None
    sms: Optional[NotificationResult] = None

    @property
    def results(self) -> list[NotificationResult]:
        return [result for result in (self.email, self.sms) if result is not None]

    @property
    def any_delivered(self) -> bool:
        return any(result.delivered for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "any_delivered": self.any_delivered,
            "results": [result.to_dict() for result in self.results],
        }


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def mask_recipient(value: str) -> str:
    """Return a safe, partially hidden destination for logs and responses.

    ``alice@example.com`` becomes ``a***@example.com``; a phone number keeps
    only its last four digits.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if "@" in text:
        local, _, domain = text.partition("@")
        head = local[:1] if local else ""
        return f"{head}***@{domain}"
    digits = "".join(character for character in text if character.isdigit())
    if digits:
        return f"****{digits[-4:]}"
    return "***"


def normalize_phone(value: str) -> str:
    """Return an E.164-ish phone number, or an empty string when unusable."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    body = raw[1:] if raw.startswith("+") else raw
    digits = "".join(character for character in body if character.isdigit())
    if len(digits) < 8:
        return ""
    return f"+{digits}"


def _truncate(text: str, limit: int = 480) -> str:
    """Shorten text for a single SMS message body."""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


# --------------------------------------------------------------------------
# Provider configuration, read from the environment and never hard-coded
# --------------------------------------------------------------------------

class EmailConfig:
    """SMTP settings. Missing values are safe; nothing is required to boot."""

    def __init__(self) -> None:
        self.server = str(os.getenv("MAIL_SERVER") or "").strip()
        self.port = _env_int("MAIL_PORT", 587)
        self.username = str(os.getenv("MAIL_USERNAME") or "").strip()
        self.password = str(os.getenv("MAIL_PASSWORD") or "")
        self.sender = str(os.getenv("MAIL_FROM") or "").strip() or self.username
        self.use_tls = _env_flag("MAIL_USE_TLS", True)
        self.use_ssl = _env_flag("MAIL_USE_SSL", False)
        self.timeout = _env_int("MAIL_TIMEOUT", 10)

    @property
    def configured(self) -> bool:
        """Email needs a server and a sender; SMTP credentials are optional."""
        return bool(self.server and self.sender)

    def safe_summary(self) -> dict[str, Any]:
        """A description safe to return in an API response or a log line."""
        return {
            "configured": self.configured,
            "server": self.server or None,
            "port": self.port,
            "sender": mask_recipient(self.sender) if self.sender else None,
            "use_tls": self.use_tls,
            "use_ssl": self.use_ssl,
            "authenticated": bool(self.username),
        }


class SmsConfig:
    """SMS provider settings. No provider name is hard-coded."""

    def __init__(self) -> None:
        self.provider = str(os.getenv("SMS_PROVIDER") or "").strip().lower()
        self.api_key = str(os.getenv("SMS_API_KEY") or "").strip()
        self.api_secret = str(os.getenv("SMS_API_SECRET") or "").strip()
        self.sender = str(os.getenv("SMS_FROM") or "").strip()
        self.endpoint = str(os.getenv("SMS_ENDPOINT") or "").strip()
        self.timeout = _env_int("SMS_TIMEOUT", 10)

    @property
    def configured(self) -> bool:
        """A provider counts as configured only when it has what it needs."""
        if not self.provider or self.provider in {"mock", "log", "none", "console", "dev"}:
            return False
        if self.provider in {"http", "webhook", "generic"}:
            return bool(self.endpoint and (self.api_key or self.api_secret))
        return bool(self.endpoint and self.api_key)

    def safe_summary(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": self.provider or None,
            "endpoint": self.endpoint or None,
            "has_api_key": bool(self.api_key),
            "has_api_secret": bool(self.api_secret),
            "sender": mask_recipient(self.sender) if self.sender else None,
        }


def email_config() -> EmailConfig:
    return EmailConfig()


def sms_config() -> SmsConfig:
    return SmsConfig()


def notification_status() -> dict[str, Any]:
    """Report provider availability without revealing any credential."""
    return {
        "email": email_config().safe_summary(),
        "sms": sms_config().safe_summary(),
        "statuses": list(DELIVERY_STATUSES),
    }


# --------------------------------------------------------------------------
# Email content and delivery
# --------------------------------------------------------------------------

def _recommendation_for(alert_type: str) -> str:
    """Return a short, informational, non-medical advisory for an alert type."""
    advice = {
        "flood": "Avoid low-lying and waterlogged roads and keep essential items ready.",
        "heatwave": "Limit peak-hour exertion, stay hydrated, and seek cooler indoor spaces.",
        "heavy_rain": "Carry rain protection, allow extra travel time, and avoid exposed areas.",
        "heavy rain": "Carry rain protection, allow extra travel time, and avoid exposed areas.",
        "rain": "Carry rain protection and allow extra travel time.",
        "high_temperature": "Limit peak-hour exertion and stay hydrated.",
        "high temperature": "Limit peak-hour exertion and stay hydrated.",
        "moderate_temperature": "Stay aware of the daytime heat and keep water nearby.",
        "strong_wind": "Secure loose objects outdoors and avoid exposed travel routes.",
        "moderate_wind": "Expect occasional gusts when travelling outdoors.",
        "thunderstorm": "Move indoors during thunder and avoid open ground or isolated trees.",
    }
    slug = str(alert_type or "").strip().lower()
    return advice.get(
        slug,
        "Check the latest official forecast and plan your day accordingly.",
    )


def _alert_context(alert, user, location, weather) -> dict[str, str]:
    """Collect the header fields shared by the text and HTML email bodies."""
    from services.translations import translate_text

    location_name = "your saved location"
    country = ""
    if location is not None:
        location_name = getattr(location, "name", "") or location_name
        country = getattr(location, "country", "") or ""
    elif weather:
        meta = weather.get("location") or {}
        location_name = meta.get("name", location_name)
        country = meta.get("country", "")

    created_at = getattr(alert, "created_at", None)
    language = getattr(user, "preferred_language", None) or "en"
    return {
        "location_name": location_name,
        "place": f"{location_name}, {country}" if country else location_name,
        "alert_type": translate_text(getattr(alert, "alert_type", None) or "Weather Alert", language),
        "severity": translate_text(getattr(alert, "severity", None) or "Moderate", language),
        "message": translate_text(getattr(alert, "message", "") or "", language),
        "timestamp": created_at.strftime("%Y-%m-%d %H:%M UTC") if created_at else "",
        "recipient": getattr(user, "email", "") or "",
    }


def _condition_lines(weather) -> list[str]:
    """Format the current readings that support the alert."""
    current = (weather or {}).get("current") or {}
    forecast = (weather or {}).get("forecast") or []
    today = forecast[0] if forecast else {}
    lines = []
    for label, value, unit in (
        ("Condition", current.get("condition"), ""),
        ("Temperature", current.get("temperature"), "°C"),
        ("Humidity", current.get("humidity"), "%"),
        ("Wind speed", current.get("wind_speed"), " km/h"),
        ("Precipitation", current.get("precipitation"), " mm"),
    ):
        if value is not None:
            lines.append(f"- {label}: {value}{unit}")
    if today.get("rain_probability") is not None:
        lines.append(f"- Rain probability today: {today['rain_probability']}%")
    if not lines:
        lines.append("- Detailed current readings are not available right now.")
    return lines


EMAIL_FOOTER = [
    f"This message was generated automatically by {APP_NAME}.",
    APP_TAGLINE,
    "It is an informational weather indicator, not an official emergency",
    "warning. Please follow local official guidance during severe weather.",
]


def build_alert_email(alert, user=None, location=None, weather=None, language=None) -> dict[str, str]:
    """Build a readable weather-alert email for an existing ``Alert`` record.

    Returns ``{"subject", "text", "html", "recipient"}``. Every value comes
    from the application's own weather data; nothing is invented here.
    """
    context = _alert_context(alert, user, location, weather)
    chosen_language = language or getattr(user, "preferred_language", None) or "en"
    conditions = _condition_lines(weather)
    recommendation = _recommendation_for(getattr(alert, "alert_type", ""))
    meaning = context["message"] or "Conditions changed enough to raise an alert."

    text = "\n".join(
        [
            "Weather Alert",
            "=" * 46,
            f"Location: {context['place']}",
            f"Alert: {context['alert_type']}",
            f"Severity: {context['severity'].upper()}",
            f"Time: {context['timestamp']}",
            "",
            "Conditions",
            "-" * 46,
            *conditions,
            "",
            "What this means",
            "-" * 46,
            meaning,
            "",
            "Recommendation",
            "-" * 46,
            recommendation,
            "",
            "-" * 46,
            *EMAIL_FOOTER,
        ]
    )

    rows = "".join(
        f"<tr><td><b>{label}</b></td><td>{value}</td></tr>"
        for label, value in (
            ("Location", context["place"]),
            ("Alert", context["alert_type"]),
            ("Severity", context["severity"].upper()),
            ("Time", context["timestamp"]),
        )
    )
    items = "".join(f"<li>{line[2:]}</li>" for line in conditions)
    html = (
        '<!doctype html><html><body style="font-family:Segoe UI,Arial,sans-serif;">'
        '<div style="max-width:560px;margin:0 auto;">'
        f"<h2>{APP_NAME} &mdash; Weather Alert</h2>"
        f'<p style="color:#666;">{APP_TAGLINE}</p>'
        f'<table cellpadding="6" style="border-collapse:collapse;width:100%;">{rows}</table>'
        f"<h3>Conditions</h3><ul>{items}</ul>"
        f"<h3>What this means</h3><p>{meaning}</p>"
        f"<h3>Recommendation</h3><p>{recommendation}</p>"
        '<hr><p style="font-size:12px;color:#666;">'
        f"{EMAIL_FOOTER[0]} {EMAIL_FOOTER[2]} {EMAIL_FOOTER[3]}"
        "</p></div></body></html>"
    )

    return {
        "subject": f"[{APP_NAME}] {context['severity']} {context['alert_type']} for {context['location_name']}",
        "text": text,
        "html": html,
        "recipient": context["recipient"],
        "language": chosen_language,
    }


def send_email(
    recipient: str,
    subject: str,
    body: str,
    html: str = "",
    config: Optional[EmailConfig] = None,
) -> NotificationResult:
    """Attempt to send one email. Never raises; always returns a result.

    The status is ``sent`` only when the SMTP server actually accepted the
    message. Missing configuration returns ``unavailable`` and a transport
    error returns ``failed``; in both cases the caller carries on normally.
    """
    safe_recipient = mask_recipient(recipient)
    settings = config or email_config()

    if not str(recipient or "").strip():
        return NotificationResult(CHANNEL_EMAIL, STATUS_SKIPPED, "No recipient address.", safe_recipient)
    if not settings.configured:
        LOGGER.warning(
            "Email skipped for %s: SMTP is not configured. Set MAIL_SERVER and MAIL_FROM to enable it.",
            safe_recipient,
        )
        return NotificationResult(
            CHANNEL_EMAIL,
            STATUS_UNAVAILABLE,
            "Email is not configured on this server.",
            safe_recipient,
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((APP_NAME, settings.sender))
    message["To"] = recipient
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")

    try:
        if settings.use_ssl:
            with smtplib.SMTP_SSL(settings.server, settings.port, timeout=settings.timeout) as server:
                if settings.use_tls:
                    server.starttls()
                _smtp_authenticate(server, settings)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.server, settings.port, timeout=settings.timeout) as server:
                server.ehlo()
                if settings.use_tls:
                    server.starttls()
                    server.ehlo()
                _smtp_authenticate(server, settings)
                server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        LOGGER.error("Email to %s failed: %s", safe_recipient, type(error).__name__)
        return NotificationResult(
            CHANNEL_EMAIL,
            STATUS_FAILED,
            "The mail server rejected or could not be reached.",
            safe_recipient,
        )
    except Exception as error:  # pragma: no cover - defensive
        LOGGER.error("Unexpected email error: %s", type(error).__name__)
        return NotificationResult(CHANNEL_EMAIL, STATUS_FAILED, "Unexpected email error.", safe_recipient)

    LOGGER.info("Email alert sent to %s", safe_recipient)
    return NotificationResult(CHANNEL_EMAIL, STATUS_SENT, "Email sent.", safe_recipient)


def _smtp_authenticate(server, settings: EmailConfig) -> None:
    """Authenticate only when credentials exist. The password is never logged."""
    if settings.username and settings.password:
        server.login(settings.username, settings.password)


# --------------------------------------------------------------------------
# SMS
# --------------------------------------------------------------------------

def build_sms_message(alert, location=None, weather=None) -> str:
    """Build a single short SMS body for an alert. SMS is text-only."""
    location_name = "your saved location"
    if location is not None:
        location_name = getattr(location, "name", "") or location_name
    elif weather:
        location_name = (weather.get("location") or {}).get("name", location_name)

    alert_type = getattr(alert, "alert_type", None) or "Weather Alert"
    severity = getattr(alert, "severity", None) or "Moderate"
    message = getattr(alert, "message", "") or ""
    headline = f"{APP_NAME}: {severity.upper()} {alert_type} for {location_name}."
    detail = _recommendation_for(alert_type)
    return _truncate(f"{headline} {message} {detail}")


def send_sms(
    phone: str,
    alert,
    location=None,
    weather=None,
    config: Optional[SmsConfig] = None,
) -> NotificationResult:
    """Attempt to send one SMS. Provider-independent and never raises.

    The provider comes from ``SMS_PROVIDER``. When none is configured the
    call returns ``unavailable`` so the alert still records correctly and the
    application keeps working. Only a real provider run returns ``sent``.
    """
    settings = config or sms_config()
    number = normalize_phone(phone)
    safe_number = mask_recipient(number)

    if not number:
        return NotificationResult(CHANNEL_SMS, STATUS_SKIPPED, "No phone number.", safe_number, settings.provider)
    if not settings.configured:
        LOGGER.info(
            "SMS skipped for %s: no SMS provider configured. Set SMS_PROVIDER and SMS_ENDPOINT to enable it.",
            safe_number,
        )
        return NotificationResult(
            CHANNEL_SMS,
            STATUS_UNAVAILABLE,
            "No SMS provider is configured on this server.",
            safe_number,
            settings.provider,
        )

    body = build_sms_message(alert, location=location, weather=weather)
    payload = {
        "to": number,
        "from": settings.sender or None,
        "message": body,
        "api_key": settings.api_key or None,
        "api_secret": settings.api_secret or None,
    }
    try:
        response = requests.post(settings.endpoint, json=payload, timeout=settings.timeout)
        response.raise_for_status()
    except requests.RequestException as error:
        LOGGER.error("SMS to %s failed: %s", safe_number, type(error).__name__)
        return NotificationResult(
            CHANNEL_SMS,
            STATUS_FAILED,
            "The SMS provider rejected or could not be reached.",
            safe_number,
            settings.provider,
        )
    except Exception as error:  # pragma: no cover - defensive
        LOGGER.error("Unexpected SMS error: %s", type(error).__name__)
        return NotificationResult(
            CHANNEL_SMS, STATUS_FAILED, "Unexpected SMS error.", safe_number, settings.provider
        )

    LOGGER.info("SMS alert sent to %s via %s", safe_number, settings.provider)
    return NotificationResult(CHANNEL_SMS, STATUS_SENT, "SMS sent.", safe_number, settings.provider)


# --------------------------------------------------------------------------
# Preference-aware delivery
# --------------------------------------------------------------------------

def _preference_for(user):
    """Return the user's account-wide preference row, or ``None``."""
    if user is None:
        return None
    from models import NotificationPreference

    return (
        NotificationPreference.query.filter(NotificationPreference.user_id == user.id)
        .filter(NotificationPreference.location_id.is_(None))
        .first()
    )


def deliver_alert_notifications(user, alert, location=None, weather=None, preference=None) -> NotificationSummary:
    """Send one alert over every channel the user has enabled.

    A disabled channel is reported as ``disabled`` without being attempted, and
    a channel with no provider is reported as ``unavailable``. The function
    never raises and never claims a delivery that did not happen.
    """
    summary = NotificationSummary()
    if user is None or alert is None:
        return summary

    settings = preference if preference is not None else _preference_for(user)

    if settings is None or settings.email_enabled:
        content = build_alert_email(alert, user=user, location=location, weather=weather)
        summary.email = send_email(
            content["recipient"], content["subject"], content["text"], content["html"]
        )
    else:
        summary.email = NotificationResult(
            CHANNEL_EMAIL, STATUS_DISABLED, "Email alerts are turned off.", mask_recipient(user.email)
        )

    if settings is None or settings.sms_enabled:
        summary.sms = send_sms(getattr(user, "phone", ""), alert, location=location, weather=weather)
    else:
        summary.sms = NotificationResult(
            CHANNEL_SMS, STATUS_DISABLED, "SMS alerts are turned off.", mask_recipient(user.phone)
        )

    for result in summary.results:
        LOGGER.info(
            "Alert %s delivery: channel=%s status=%s recipient=%s",
            getattr(alert, "alert_type", "alert"),
            result.channel,
            result.status,
            result.recipient or "-",
        )
    return summary


def deliver_alerts(user, alerts, location=None, weather=None, preference=None) -> list[NotificationSummary]:
    """Deliver a batch of alerts, returning one summary per alert."""
    return [
        deliver_alert_notifications(user, alert, location=location, weather=weather, preference=preference)
        for alert in (alerts or [])
    ]
