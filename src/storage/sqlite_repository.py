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
    detected_at TEXT NOT NULL
);
"""


class SQLiteJobRepository(JobRepository):
    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(SCHEMA)

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
                    status, cover_letter_link, source_platform, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def all_postings(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM postings ORDER BY detected_at").fetchall()
        return [dict(row) for row in rows]

    def postings_missing_letter(self, category: str = "A") -> list[JobPosting]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM postings WHERE category = ? AND (cover_letter_link IS NULL OR cover_letter_link = '') "
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
        location_priority=row["location_priority"],
        status=row["status"],
        cover_letter_link=row["cover_letter_link"],
        source_platform=row["source_platform"],
        detected_at=datetime.fromisoformat(row["detected_at"]),
    )
