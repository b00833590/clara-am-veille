"""Health check: fails loudly if postings are being detected but none of
them are reaching category A over a rolling window — the exact failure
mode found live on 2026-08-04 (see CLAUDE.md), where a keyword-coverage
gap in the classifier silently swallowed 12/12 genuinely new AM offers
between 2026-07-31 and 2026-08-03 with zero visible error anywhere: every
scheduled run reported "success", every source scraped fine, offers were
correctly stored — nothing surfaced that Clara's inbox had gone silent
until she noticed herself, days later.

Deliberately coarse and dependency-free: src/orchestrator.py only stores a
posting after notify_new_posting() succeeds when it's category A (see
_process_posting), so "a category-A posting exists in the window" is a
reasonable proxy for "an email was attempted" without needing direct
access to Gmail's send history.

Run once a day (see .github/workflows/validate.yml) — a rolling 7-day
window checked daily is more responsive than a literal weekly check and
costs nothing extra since validate.yml already runs on that cadence. A
nonzero exit code fails the GitHub Actions step, which is enough to
surface the problem (repo watchers get a workflow-failure notification)
without adding a second email channel alongside Clara's.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.storage.sqlite_repository import SQLiteJobRepository  # noqa: E402

WINDOW_DAYS = 7


def check_notification_health(postings: list[dict], now: datetime, window_days: int = WINDOW_DAYS) -> str | None:
    """Returns an alert message if postings were detected in the window but
    none reached category A (i.e. none would have been emailed), else None.

    Deliberately silent (returns None) when nothing at all was detected in
    the window — that's a scraper/scheduler concern, not a notification
    one, and conflating the two would make the alert message misleading.
    """
    cutoff = now - timedelta(days=window_days)
    recent = [p for p in postings if datetime.fromisoformat(p["detected_at"]) >= cutoff]
    if not recent:
        return None

    category_a = [p for p in recent if p["category"] == "A"]
    if category_a:
        return None

    return (
        f"{len(recent)} offre(s) détectée(s) dans les {window_days} derniers jours, "
        "mais aucune classée catégorie A — aucun email n'a donc été envoyé à Clara. "
        "Vérifier le classificateur (src/classification/rule_based_classifier.py) "
        "et le tableau de suivi Google Sheets."
    )


if __name__ == "__main__":
    alerts: list[str] = []
    for db_name in ("offres.db", "offres_preview.db"):
        db_path = ROOT / "data" / db_name
        if not db_path.exists():
            print(f"  ({db_name} n'existe pas, ignoré)")
            continue
        repository = SQLiteJobRepository(db_path)
        alert = check_notification_health(repository.all_postings(), datetime.now(timezone.utc))
        if alert:
            print(f"ALERTE [{db_name}] {alert}")
            alerts.append(alert)
        else:
            print(f"[{db_name}] OK — pas d'anomalie de notification détectée sur les {WINDOW_DAYS} derniers jours.")

    if alerts:
        sys.exit(1)
