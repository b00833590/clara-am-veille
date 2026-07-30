import sqlite3
from datetime import datetime
from pathlib import Path

from src.models import JobPosting
from src.storage.repository import JobRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    stable_id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    description TEXT NOT NULL,
    location TEXT,
    start_date TEXT,
    category TEXT,
    language TEXT,
    to_verify INTEGER NOT NULL DEFAULT 0,
    classification_reason TEXT NOT NULL DEFAULT '',
    location_priority INTEGER NOT NULL DEFAULT 4,
    status TEXT NOT NULL DEFAULT 'Nouvelle',
    cover_letter_link TEXT,
    source_platform TEXT NOT NULL DEFAULT '',
    detected_at TEXT NOT NULL,
    application_status TEXT NOT NULL DEFAULT '',
    application_date TEXT NOT NULL DEFAULT '',
    follow_up_date TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    team_division TEXT NOT NULL DEFAULT '',
    deadline_date TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT '',
    interest_level TEXT NOT NULL DEFAULT '',
    fit_level TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT ''
);
"""

# Colonnes ajoutées après la création initiale de la table (suivi manuel,
# Phase 4) — CREATE TABLE IF NOT EXISTS ne les ajoute pas à une base déjà
# existante, d'où cette migration explicite au démarrage (idempotente,
# jamais destructive). Même bug de fond que la migration Excel de Phase 2bis
# (CLAUDE.md) : un schéma qui change dans le temps doit toujours prévoir
# comment une base déjà peuplée le rattrape.
#
# application_status est délibérément distincte de `status` : `status` reste
# un champ système (Nouvelle/Expirée, géré par validate_offers.py) —
# application_status est la progression de candidature que Clara pilote
# elle-même depuis le Google Sheet (À postuler/Envoyée/Entretien/...).
# Les confondre ferait entrer en conflit deux écrivains sur la même colonne.
_MIGRATION_COLUMNS = {
    "application_status": "TEXT NOT NULL DEFAULT ''",
    "application_date": "TEXT NOT NULL DEFAULT ''",
    "follow_up_date": "TEXT NOT NULL DEFAULT ''",
    "notes": "TEXT NOT NULL DEFAULT ''",
    # Phase 4bis (2026-07-30) — richer tracking sheet. team_division is
    # system-derived (src/classification/division.py); the rest are Clara-
    # owned, synced back from the sheet exactly like the columns above.
    "team_division": "TEXT NOT NULL DEFAULT ''",
    "deadline_date": "TEXT NOT NULL DEFAULT ''",
    "contact_name": "TEXT NOT NULL DEFAULT ''",
    "contact_email": "TEXT NOT NULL DEFAULT ''",
    "interest_level": "TEXT NOT NULL DEFAULT ''",
    "fit_level": "TEXT NOT NULL DEFAULT ''",
    "next_action": "TEXT NOT NULL DEFAULT ''",
}


class SQLiteJobRepository(JobRepository):
    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(postings)").fetchall()}
        for column, definition in _MIGRATION_COLUMNS.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE postings ADD COLUMN {column} {definition}")
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def exists(self, stable_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM postings WHERE stable_id = ?", (stable_id,)).fetchone()
        return row is not None

    def add(self, posting: JobPosting) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO postings (
                    stable_id, company, title, url, description, location, start_date,
                    category, language, to_verify, classification_reason, location_priority,
                    status, cover_letter_link, source_platform, detected_at, team_division
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    posting.stable_id(),
                    posting.company,
                    posting.title,
                    posting.url,
                    posting.description,
                    posting.location,
                    posting.start_date,
                    posting.category,
                    posting.language,
                    int(posting.to_verify),
                    posting.classification_reason,
                    posting.location_priority,
                    posting.status,
                    posting.cover_letter_link,
                    posting.source_platform,
                    posting.detected_at.isoformat(),
                    posting.team_division,
                ),
            )
            conn.commit()

    def update_letter(self, stable_id: str, letter_text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE postings SET cover_letter_link = ? WHERE stable_id = ?",
                (letter_text, stable_id),
            )
            conn.commit()

    def update_status(self, stable_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE postings SET status = ? WHERE stable_id = ?",
                (status, stable_id),
            )
            conn.commit()

    def update_classification(self, stable_id: str, category: str, language: str, to_verify: bool, classification_reason: str, team_division: str = "") -> None:
        """Used by scripts/reclassify_existing.py — a one-off pass to catch
        already-stored postings up to date after a classifier rule change,
        e.g. the 2026-07-30 keyword fix (M&A/IB, contrôleur financier,
        team assistant... were previously falling through to a false-
        positive A default). Never touches cover_letter_link/status/
        application_* — a re-run of an existing letter or a manual status
        Clara already set are left alone."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE postings SET category = ?, language = ?, to_verify = ?, classification_reason = ?, team_division = ? WHERE stable_id = ?",
                (category, language, int(to_verify), classification_reason, team_division, stable_id),
            )
            conn.commit()

    def update_tracking_fields(
        self,
        stable_id: str,
        application_status: str,
        application_date: str,
        follow_up_date: str,
        notes: str,
        deadline_date: str = "",
        contact_name: str = "",
        contact_email: str = "",
        interest_level: str = "",
        fit_level: str = "",
        next_action: str = "",
    ) -> None:
        """Clara-owned columns (see src/tracking/sheets_sync.py) — the Google
        Sheet is their source of truth, so a sync always overwrites these
        with exactly what's in the sheet, blank cells included, rather than
        merging field-by-field. Deliberately never touches `status`, the
        system-managed posting lifecycle field (Nouvelle/Expirée)."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE postings SET
                    application_status = ?, application_date = ?, follow_up_date = ?, notes = ?,
                    deadline_date = ?, contact_name = ?, contact_email = ?,
                    interest_level = ?, fit_level = ?, next_action = ?
                WHERE stable_id = ?
                """,
                (
                    application_status, application_date, follow_up_date, notes,
                    deadline_date, contact_name, contact_email,
                    interest_level, fit_level, next_action,
                    stable_id,
                ),
            )
            conn.commit()

    def all_postings(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM postings ORDER BY detected_at").fetchall()
        return [dict(row) for row in rows]

    def postings_missing_letter(self, category: str = "A") -> list[JobPosting]:
        # to_verify=1 postings are deliberately never given a letter (see
        # src/orchestrator.py — only confident matches get one) — excluded
        # here too, or this retry would silently undo that on the next run.
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM postings WHERE category = ? AND to_verify = 0 "
                "AND (cover_letter_link IS NULL OR cover_letter_link = '') "
                "ORDER BY detected_at",
                (category,),
            ).fetchall()
        return [_posting_from_row(dict(row)) for row in rows]

    def postings_with_url_and_status(self, status: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM postings WHERE status = ? AND url IS NOT NULL ORDER BY detected_at",
                (status,),
            ).fetchall()
        return [dict(row) for row in rows]


def _posting_from_row(row: dict) -> JobPosting:
    return JobPosting(
        company=row["company"],
        title=row["title"],
        url=row["url"],
        description=row["description"],
        location=row["location"],
        start_date=row["start_date"],
        category=row["category"],
        language=row["language"],
        to_verify=bool(row["to_verify"]),
        classification_reason=row["classification_reason"],
        team_division=row["team_division"],
        location_priority=row["location_priority"],
        status=row["status"],
        cover_letter_link=row["cover_letter_link"],
        source_platform=row["source_platform"],
        detected_at=datetime.fromisoformat(row["detected_at"]),
    )
