from datetime import datetime, timedelta, timezone

from scripts.check_notification_health import check_notification_health
from src.models import JobPosting
from src.storage.sqlite_repository import SQLiteJobRepository

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


def make_posting(**overrides):
    defaults = dict(company="Amundi", title="Stage Analyste", url="https://example.com/1", description="")
    defaults.update(overrides)
    return JobPosting(**defaults)


def row(category: str, detected_at: datetime) -> dict:
    return {"category": category, "detected_at": detected_at.isoformat()}


def test_no_alert_when_recent_postings_include_a_category_a():
    postings = [row("A", NOW - timedelta(days=1)), row("N", NOW - timedelta(days=2))]

    assert check_notification_health(postings, now=NOW) is None


def test_alert_when_recent_postings_are_all_off_topic():
    # The exact 2026-08-04 failure mode: offers detected and stored, none
    # confident enough to reach category A, zero emails sent — but every
    # scheduled run still reports "success", so nothing else surfaces it.
    postings = [row("N", NOW - timedelta(days=1)), row("N", NOW - timedelta(days=3))]

    alert = check_notification_health(postings, now=NOW)

    assert alert is not None
    assert "2 offre" in alert


def test_no_alert_when_nothing_detected_in_the_window():
    # Distinct concern from notification health (scraper/scheduler, not
    # classification) — silent here on purpose so the alert message stays
    # accurate rather than misleadingly blaming the classifier.
    postings = [row("N", NOW - timedelta(days=30))]

    assert check_notification_health(postings, now=NOW) is None


def test_postings_outside_the_window_are_ignored():
    postings = [row("A", NOW - timedelta(days=30)), row("N", NOW - timedelta(days=1))]

    alert = check_notification_health(postings, now=NOW)

    assert alert is not None
    assert "1 offre" in alert


def test_integration_with_real_repository(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    repo.add(make_posting(category="N"))

    alert = check_notification_health(repo.all_postings(), now=datetime.now(timezone.utc))

    assert alert is not None
