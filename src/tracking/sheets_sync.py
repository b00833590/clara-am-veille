SHEET_NAME = "Suivi candidatures"

HEADERS = [
    "ID",
    "Entreprise",
    "Titre du poste",
    "Lieu",
    "Date de publication",
    "Lien",
    "Statut",
    "Date de candidature",
    "Relance",
    "Remarques",
]

_RANGE = f"{SHEET_NAME}!A:J"


class SheetsSync:
    """Two-way sync between the SQLite repository and a Google Sheet Clara
    edits by hand. SQLite stays the source of truth for posting data
    (company, title, url...); the sheet is the source of truth for the
    columns Clara owns (Statut, Date de candidature, Relance, Remarques) — a
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
                follow_up_date=row.get("Relance", ""),
                notes=row.get("Remarques", ""),
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
        rows = [HEADERS] + [_row_for(p) for p in postings]

        self._service.spreadsheets().values().clear(spreadsheetId=self._spreadsheet_id, range=_RANGE, body={}).execute()
        self._service.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()


def _row_for(posting: dict) -> list[str]:
    return [
        posting["stable_id"],
        posting["company"],
        posting["title"],
        posting["location"] or "",
        posting["detected_at"],
        posting["url"] or "",
        posting["application_status"],
        posting["application_date"],
        posting["follow_up_date"],
        posting["notes"],
    ]
