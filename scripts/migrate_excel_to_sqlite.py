"""One-off migration: imports existing offres*.xlsx data into the new
SQLite-backed repository, so the dedup history built up today isn't lost and
tomorrow's run doesn't re-scrape/re-classify (and re-burn Gemini quota on)
postings already processed. Excel is no longer the source of truth after
this — see main.py / preview_run.py, which now write to SQLite and only
regenerate Excel as a read-only export.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.storage.excel_repository import ExcelJobRepository, SHEET_AM, SHEET_FINANCE, SHEET_OFF_TOPIC  # noqa: E402
from src.storage.sqlite_repository import SQLiteJobRepository  # noqa: E402


def migrate(xlsx_path: Path, db_path: Path) -> int:
    if not xlsx_path.exists():
        print(f"  (rien à migrer, {xlsx_path.name} n'existe pas)")
        return 0

    excel_repo = ExcelJobRepository(xlsx_path)  # triggers the schema migration fix on open
    sqlite_repo = SQLiteJobRepository(db_path)

    imported = 0
    for sheet_name in (SHEET_AM, SHEET_FINANCE, SHEET_OFF_TOPIC):
        for row in excel_repo._read_sheet_rows(sheet_name):
            stable_id = row.get("ID")
            if not stable_id or sqlite_repo.exists(stable_id):
                continue
            with sqlite_repo._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO postings (
                        stable_id, company, title, url, description, location, start_date,
                        category, language, to_verify, classification_reason, location_priority,
                        status, cover_letter_link, source_platform, detected_at
                    ) VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?)
                    """,
                    (
                        stable_id,
                        row.get("Entreprise") or "",
                        row.get("Titre du poste") or "",
                        row.get("Lien vers l'offre") or None,
                        row.get("Lieu") or None,
                        row.get("Date de début du stage") or None,
                        row.get("Catégorie (A/B)") or None,
                        row.get("Langue de l'annonce") or None,
                        1 if row.get("À vérifier") else 0,
                        row.get("Raison (classification)") or "",
                        row.get("Priorité géo") if isinstance(row.get("Priorité géo"), int) else 4,
                        row.get("Statut") or "Nouvelle",
                        row.get("Lettre de motivation générée") or None,
                        row.get("Date de détection") or datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
            imported += 1

    return imported


if __name__ == "__main__":
    for xlsx_name, db_name in [("offres.xlsx", "offres.db"), ("offres_preview.xlsx", "offres_preview.db")]:
        print(f"Migration {xlsx_name} -> {db_name}...")
        count = migrate(ROOT / "data" / xlsx_name, ROOT / "data" / db_name)
        print(f"  {count} offre(s) importée(s)")
