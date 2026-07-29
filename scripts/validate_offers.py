"""Periodic sweep: re-checks stored postings still marked "Nouvelle" and
flags confirmed-dead URLs as "Expirée", so Clara doesn't waste time on offers
that closed between detection and when she gets around to applying. Meant to
run on its own schedule (e.g. once a day), separate from the main scrape/
classify pipeline — re-checking every stored URL on every hourly run would be
both wasteful and impolite to the target sites.

Deliberately conservative (see src/validation/url_validator.py): only a
confirmed 404/410 marks a posting expired. Anything inconclusive (network
error, an ATS's own "position closed" page that still returns 200, a 403 from
anti-bot protection) leaves the posting untouched rather than guessing.
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.storage.sqlite_repository import SQLiteJobRepository  # noqa: E402
from src.validation.url_validator import is_url_expired  # noqa: E402

DELAY_BETWEEN_CHECKS_SECONDS = 1.0
STATUS_NOUVELLE = "Nouvelle"
STATUS_EXPIRED = "Expirée"


@dataclass
class SweepSummary:
    checked: int = 0
    marked_expired: int = 0


def sweep_expired_postings(
    repository: SQLiteJobRepository,
    checker: Callable[[str], bool | None] = is_url_expired,
    sleep_fn: Callable[[float], None] = time.sleep,
    delay_seconds: float = DELAY_BETWEEN_CHECKS_SECONDS,
) -> SweepSummary:
    summary = SweepSummary()

    for posting in repository.postings_with_url_and_status(STATUS_NOUVELLE):
        summary.checked += 1
        if checker(posting["url"]) is True:
            repository.update_status(posting["stable_id"], STATUS_EXPIRED)
            summary.marked_expired += 1
        sleep_fn(delay_seconds)

    return summary


if __name__ == "__main__":
    for db_name in ("offres.db", "offres_preview.db"):
        db_path = ROOT / "data" / db_name
        if not db_path.exists():
            print(f"  ({db_name} n'existe pas, ignoré)")
            continue
        repository = SQLiteJobRepository(db_path)
        print(f"Vérification des offres de {db_name}...")
        result = sweep_expired_postings(repository)
        print(f"  {result.checked} offre(s) vérifiée(s), {result.marked_expired} marquée(s) expirée(s)")
