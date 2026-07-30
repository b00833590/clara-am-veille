from src.scoring.relevance_scorer import score_posting

SHEET_NAME = "📋 Offres"

# Three visual groups (see scripts/setup_tracking_sheet.py for the header
# color bands that make this grouping visible in the sheet itself):
#   🔵 Auto        — written by the pipeline, Clara never edits these
#   🟣 Décision     — Clara's fast triage of a new posting
#   🟡 Suivi        — Clara's ongoing application tracking
HEADERS = [
    "ID",
    "Entreprise",
    "Division / Équipe",
    "Titre du poste",
    "Localisation",
    "Lien",
    "Source",
    "Date de découverte",
    "Score de pertinence",
    "Confiance",
    "Niveau d'intérêt",
    "Adéquation profil",
    "Statut",
    "Date limite candidature",
    "Date de candidature",
    "Prochaine relance",
    "Contact / Recruteur",
    "Email contact",
    "Commentaires",
    "Prochaine action",
]

# Quoted: the tab title contains a space and an emoji, both of which require
# quoting in an A1 range reference.
_RANGE = f"'{SHEET_NAME}'!A:T"


class SheetsSync:
    """Two-way sync between the SQLite repository and a Google Sheet Clara
    edits by hand. SQLite stays the source of truth for posting data
    (company, title, url, division, score...); the sheet is the source of
    truth for the columns Clara owns (Niveau d'intérêt, Adéquation profil,
    Statut, Date limite candidature, Date de candidature, Prochaine relance,
    Contact/Recruteur, Email contact, Commentaires, Prochaine action) — a
    sync always reads those back into SQLite BEFORE regenerating the sheet,
    so her edits are never overwritten by the run that follows. Only
    category-A postings are tracked here (the ones she actually applies to)
    — the full read-only snapshot of everything else stays in
    excel_export.py, unchanged and unaffected by this.
    """

    def __init__(self, sheets_service, spreadsheet_id: str):
        self._service = sheets_service
        self._spreadsheet_id = spreadsheet_id

    def sync(self, repository) -> None:
        self._pull_claras_edits_into_repository(repository)
        self._push_repository_state_to_sheet(repository)

    def _pull_claras_edits_into_repository(self, repository) -> None:
        for row in self._read_existing_rows():
            stable_id = row.get("ID", "").strip()
            if not stable_id:
                continue
            repository.update_tracking_fields(
                stable_id,
                application_status=row.get("Statut", ""),
                application_date=row.get("Date de candidature", ""),
                follow_up_date=row.get("Prochaine relance", ""),
                notes=row.get("Commentaires", ""),
                deadline_date=row.get("Date limite candidature", ""),
                contact_name=row.get("Contact / Recruteur", ""),
                contact_email=row.get("Email contact", ""),
                interest_level=row.get("Niveau d'intérêt", ""),
                fit_level=row.get("Adéquation profil", ""),
                next_action=row.get("Prochaine action", ""),
            )

    def _read_existing_rows(self) -> list[dict]:
        result = self._service.spreadsheets().values().get(spreadsheetId=self._spreadsheet_id, range=_RANGE).execute()
        values = result.get("values", [])
        if not values:
            return []
        header, *data_rows = values
        return [dict(zip(header, row)) for row in data_rows]

    def _push_repository_state_to_sheet(self, repository) -> None:
        postings = [p for p in repository.all_postings() if p["category"] == "A"]
        scored = [(p, score_posting(p).score) for p in postings]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        rows = [HEADERS] + [_row_for(p, score) for p, score in scored]

        self._service.spreadsheets().values().clear(spreadsheetId=self._spreadsheet_id, range=_RANGE, body={}).execute()
        self._service.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"'{SHEET_NAME}'!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()


def _row_for(posting: dict, score: int) -> list[str]:
    return [
        posting["stable_id"],
        posting["company"],
        posting["team_division"] or "",
        posting["title"],
        posting["location"] or "",
        posting["url"] or "",
        posting["source_platform"] or "",
        posting["detected_at"],
        str(score),
        "À vérifier" if posting["to_verify"] else "Confiant",
        posting["interest_level"],
        posting["fit_level"],
        posting["application_status"],
        posting["deadline_date"],
        posting["application_date"],
        posting["follow_up_date"],
        posting["contact_name"],
        posting["contact_email"],
        posting["notes"],
        posting["next_action"],
    ]
