"""Phase 3 scheduled alert processing.

The scheduler is a plain, independently testable callable. It deliberately
does NOT start a background thread or register a cron job inside
``create_app``: Flask's debug reloader spawns a second process, which would run
any auto-started job twice and send duplicate notifications.

Run it from its own process instead, for example::

    python -m services.scheduler          # one pass, then exit
    python -m services.scheduler --loop   # repeat every SCHEDULER_INTERVAL_MINUTES

Every step reuses the existing Phase 1 / Phase 2 code:

* ``services.risk.assess_risks`` -> the single source of risk truth
* ``services.alerts.generate_alerts`` -> alert creation and duplicate prevention
* ``services.notifications`` -> email / SMS delivery
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_INTERVAL_MINUTES = 30

STATUS_SENT = "sent"
STATUS_DISABLED = "disabled"
STATUS_UNAVAILABLE = "unavailable"
STATUS_FAILED = "failed"


@dataclass
class SchedulerReport:
    """The outcome of one scheduled pass, safe to log or return as JSON."""

    started_at: str = ""
    finished_at: str = ""
    users_checked: int = 0
    locations_checked: int = 0
    weather_failures: int = 0
    alerts_created: int = 0
    notifications_sent: int = 0
    notifications_disabled: int = 0
    notifications_unavailable: int = 0
    notifications_failed: int = 0
    per_user: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "users_checked": self.users_checked,
            "locations_checked": self.locations_checked,
            "weather_failures": self.weather_failures,
            "alerts_created": self.alerts_created,
            "notifications_sent": self.notifications_sent,
            "notifications_disabled": self.notifications_disabled,
            "notifications_unavailable": self.notifications_unavailable,
            "notifications_failed": self.notifications_failed,
            "per_user": self.per_user,
            "errors": self.errors,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _subscribed_users():
    """Return the users that have an account-wide notification preference."""
    from models import NotificationPreference, User

    return (
        User.query.join(NotificationPreference, NotificationPreference.user_id == User.id)
        .filter(NotificationPreference.location_id.is_(None))
        .distinct()
        .all()
    )


def _target_location(user):
    """Return the saved location a user should be checked for.

    The most recent saved location is used, falling back to the
    ``default_location`` name stored on the user when one is set.
    """
    from models import Location

    location = (
        Location.query.filter(Location.user_id == user.id)
        .order_by(Location.created_at.desc(), Location.id.desc())
        .first()
    )
    if location is not None:
        return location
    name = getattr(user, "default_location", None)
    if name:
        return Location(user_id=user.id, name=str(name))
    return None


def _count_deliveries(report: SchedulerReport, summaries) -> None:
    for summary in summaries:
        for result in summary.results:
            if result.status == STATUS_SENT:
                report.notifications_sent += 1
            elif result.status == STATUS_DISABLED:
                report.notifications_disabled += 1
            elif result.status == STATUS_UNAVAILABLE:
                report.notifications_unavailable += 1
            elif result.status == STATUS_FAILED:
                report.notifications_failed += 1


def process_user(user, weather_fetcher, report: Optional[SchedulerReport] = None) -> dict[str, Any]:
    """Check one user's saved location, create alerts, and deliver them.

    Every failure is contained: a weather error, a database error, or a
    provider error is recorded and processing continues with the next user.
    """
    from models import db
    from services.alerts import generate_alerts
    from services.notifications import deliver_alerts
    from services.weather_service import WeatherServiceError

    outcome: dict[str, Any] = {
        "user_id": getattr(user, "id", None),
        "location": None,
        "alerts_created": 0,
        "error": None,
    }
    if report is None:
        report = SchedulerReport()

    location = _target_location(user)
    if location is None:
        return outcome
    outcome["location"] = location.name
    report.locations_checked += 1

    try:
        weather = weather_fetcher(location.name)
    except WeatherServiceError as error:
        report.weather_failures += 1
        outcome["error"] = str(error)
        LOGGER.warning("Scheduler: weather unavailable for %s: %s", location.name, error)
        return outcome
    except Exception as error:
        report.weather_failures += 1
        outcome["error"] = "Unexpected weather error."
        LOGGER.error("Scheduler: unexpected weather error %s", type(error).__name__)
        return outcome

    try:
        created = generate_alerts(user, location, weather)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        report.errors.append(f"alert generation failed for user {user.id}")
        outcome["error"] = "Alert generation failed."
        LOGGER.error("Scheduler: alert generation failed: %s", type(error).__name__)
        return outcome

    outcome["alerts_created"] = len(created)
    report.alerts_created += len(created)
    if not created:
        return outcome

    try:
        _count_deliveries(report, deliver_alerts(user, created, location=location, weather=weather))
    except Exception as error:
        db.session.rollback()
        report.errors.append(f"notification delivery failed for user {user.id}")
        LOGGER.error("Scheduler: delivery failed: %s", type(error).__name__)
    return outcome


def run_scheduled_alert_check(weather_fetcher=None, users=None) -> SchedulerReport:
    """Run one scheduled alert pass for every subscribed user.

    ``weather_fetcher`` defaults to the real weather service and is injectable
    so the scheduler is testable without network access. The function never
    raises: problems are reported in the returned ``SchedulerReport``.
    """
    from services.weather_service import get_weather

    report = SchedulerReport(started_at=_now_iso())
    fetcher = weather_fetcher or get_weather

    if users is None:
        try:
            users = _subscribed_users()
        except Exception as error:
            report.errors.append("could not load subscribed users")
            LOGGER.error("Scheduler: could not load users: %s", type(error).__name__)
            users = []

    for user in users:
        report.users_checked += 1
        try:
            result = process_user(user, fetcher, report)
        except Exception as error:
            report.errors.append(f"unexpected failure for user {user.id}")
            LOGGER.error("Scheduler: user %s failed: %s", user.id, type(error).__name__)
            continue
        if result.get("error"):
            report.errors.append(f"user {user.id}: {result['error']}")
        report.per_user.append(result)

    report.finished_at = _now_iso()
    LOGGER.info(
        "Scheduler pass complete: users=%s locations=%s alerts=%s sent=%s unavailable=%s",
        report.users_checked,
        report.locations_checked,
        report.alerts_created,
        report.notifications_sent,
        report.notifications_unavailable,
    )
    return report


def main() -> int:
    """Command-line entry point so the scheduler runs as its own process."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run the weather alert scheduler.")
    parser.add_argument("--loop", action="store_true", help="Keep running instead of a single pass.")
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=DEFAULT_INTERVAL_MINUTES,
        help=f"Minutes between passes (default {DEFAULT_INTERVAL_MINUTES}).",
    )
    args = parser.parse_args()

    from app import create_app

    app = create_app()
    with app.app_context():
        if not args.loop:
            print(run_scheduled_alert_check().to_dict())
            return 0
        while True:
            print(run_scheduled_alert_check().to_dict())
            time.sleep(max(1, args.interval_minutes) * 60)


if __name__ == "__main__":
    raise SystemExit(main())
