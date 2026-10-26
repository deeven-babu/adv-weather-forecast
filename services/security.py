"""Phase 4 security hardening helpers.

Everything here is additive. The existing session-based authentication is
unchanged; these helpers only add defensive layers around it:

* response security headers
* JSON (never HTML/stack-trace) error bodies for ``/api/*`` routes
* lightweight in-process login throttling
* strict input parsing for dates, integers, and enumerations

No external security framework is introduced.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Optional

from flask import jsonify, request

LOGGER = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Response headers
# --------------------------------------------------------------------------

#: Headers that are safe for this application and do not affect rendering.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}

#: A permissive-but-real CSP. It is only sent when ``ENABLE_CSP`` is set,
#: because the dashboard intentionally loads Leaflet and Three.js from unpkg
#: and fonts from Google, so a stricter policy would break the UI.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "img-src 'self' data: blob: https:",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com",
        "script-src 'self' 'unsafe-inline' https://unpkg.com",
        "font-src 'self' data: https://fonts.gstatic.com",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
    )
)


def apply_security_headers(response, enable_csp: bool = False):
    """Attach the defensive headers to an outgoing response."""
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if enable_csp:
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    return response


# --------------------------------------------------------------------------
# Safe error responses
# --------------------------------------------------------------------------

def wants_json() -> bool:
    """True when the caller expects a JSON error rather than an HTML page."""
    if request.path.startswith("/api/"):
        return True
    if request.is_json:
        return True
    best = request.accept_mimetypes.best
    return (
        best == "application/json"
        and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]
    )


def safe_error(message: str, status: int, code: Optional[str] = None):
    """Return a JSON error that never leaks internals."""
    payload = {"error": message}
    if code:
        payload["code"] = code
    return jsonify(payload), status


# --------------------------------------------------------------------------
# Input parsing
# --------------------------------------------------------------------------

def clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    """Parse an integer and clamp it into a safe range.

    Invalid input returns ``default`` rather than raising, so a malformed
    query string can never produce a 500.
    """
    if value is None or str(value).strip() == "":
        return default
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def parse_iso_date(value) -> Optional[date]:
    """Parse ``YYYY-MM-DD``; return ``None`` for anything else."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def date_range(args, default_days: int = 30, max_days: int = 365):
    """Resolve ``start``/``end``/``days`` parameters into a validated range.

    Returns ``(start_datetime, end_datetime, days, error)``. ``error`` is a
    short message when the caller supplied an unusable range.
    """
    days = clamp_int(args.get("days"), default_days, 1, max_days)
    today = date.today()

    raw_start = args.get("start")
    raw_end = args.get("end")
    start_date = parse_iso_date(raw_start)
    end_date = parse_iso_date(raw_end)

    if raw_start and start_date is None:
        return None, None, days, "Invalid start date. Use YYYY-MM-DD."
    if raw_end and end_date is None:
        return None, None, days, "Invalid end date. Use YYYY-MM-DD."

    if start_date is None and end_date is None:
        end_date = today
        start_date = end_date - timedelta(days=days - 1)
    elif start_date is None:
        start_date = end_date - timedelta(days=days - 1)
    elif end_date is None:
        end_date = min(today, start_date + timedelta(days=days - 1))

    if start_date > end_date:
        return None, None, days, "Start date must be on or before the end date."
    if (end_date - start_date).days + 1 > max_days:
        return None, None, days, f"Date range cannot exceed {max_days} days."

    return (
        datetime.combine(start_date, datetime.min.time()),
        datetime.combine(end_date, datetime.max.time()),
        (end_date - start_date).days + 1,
        None,
    )


# --------------------------------------------------------------------------
# Login throttling
# --------------------------------------------------------------------------

class LoginThrottle:
    """A tiny in-process attempt counter.

    It does no database work and needs no dependency. One process is enough
    for this application; counters reset on restart. Tests can call
    :meth:`reset`.
    """

    def __init__(self, max_attempts: int = 8, window_seconds: int = 300, lockout_seconds: int = 300):
        self.max_attempts = max(1, max_attempts)
        self.window_seconds = max(1, window_seconds)
        self.lockout_seconds = max(1, lockout_seconds)
        self._attempts: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(identifier: str) -> str:
        return str(identifier or "").strip().lower()[:255] or "anonymous"

    def _now(self) -> float:
        return time.monotonic()

    def is_locked(self, identifier: str) -> bool:
        """True when this identifier is currently blocked."""
        key = self._key(identifier)
        with self._lock:
            until = self._locked_until.get(key)
            if until is None:
                return False
            if until <= self._now():
                self._locked_until.pop(key, None)
                self._attempts.pop(key, None)
                return False
            return True

    def retry_after(self, identifier: str) -> int:
        """Seconds until the lockout expires (0 when not locked)."""
        key = self._key(identifier)
        with self._lock:
            until = self._locked_until.get(key)
            return 0 if until is None else max(0, int(until - self._now()))

    def record_failure(self, identifier: str) -> None:
        """Record one failed attempt and lock out after too many."""
        key = self._key(identifier)
        now = self._now()
        with self._lock:
            history = [stamp for stamp in self._attempts.get(key, []) if now - stamp <= self.window_seconds]
            history.append(now)
            self._attempts[key] = history
            if len(history) >= self.max_attempts:
                self._locked_until[key] = now + self.lockout_seconds
                LOGGER.warning("Login throttled for %s after %s failures", key, len(history))

    def reset(self, identifier: Optional[str] = None) -> None:
        """Clear counters for one identifier, or all of them."""
        with self._lock:
            if identifier is None:
                self._attempts.clear()
                self._locked_until.clear()
                return
            key = self._key(identifier)
            self._attempts.pop(key, None)
            self._locked_until.pop(key, None)


#: Module-level throttle used by the login route.
login_throttle = LoginThrottle()


def configure_login_throttle(max_attempts: int, window_seconds: int, lockout_seconds: int) -> LoginThrottle:
    """Reconfigure the shared throttle from application config."""
    login_throttle.max_attempts = max(1, max_attempts)
    login_throttle.window_seconds = max(1, window_seconds)
    login_throttle.lockout_seconds = max(1, lockout_seconds)
    return login_throttle


def client_identifier() -> str:
    """A best-effort client key for throttling (never a credential)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "anonymous"
