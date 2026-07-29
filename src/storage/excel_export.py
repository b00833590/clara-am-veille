from pathlib import Path

from openpyxl import Workbook

from src.scoring.relevance_scorer import score_posting
from src.storage.excel_repository import HEADERS, SHEET_AM, SHEET_FINANCE, SHEET_OFF_TOPIC
from src.storage.sqlite_repository import SQLiteJobRepository

EXPORT_HEADERS = HEADERS + ["Score", "Score - Détail"]


def _sheet_for_category(category: str | None) -> str:
    if category == "A":
        return SHEET_AM
    if category == "B":
        return SHEET_FINANCE
    return SHEET_OFF_TOPIC


def _row_values(posting: dict, score_result) -> list:
    return [
        posting["stable_id"],
        posting["company"],
        posting["title"],
        posting["category"] or "",
        "Oui" if posting["to_verify"] else "",
        posting["classification_reason"],
        posting["detected_at"],
        posting["start_date"] or "",
        posting["language"] or "",
        posting["location"] or "",
        posting["location_priority"],
        posting["url"] or "",
        posting["status"],
        posting["cover_letter_link"] or "",
        score_result.score,
        score_result.justification,
    ]


def export_to_excel(repository: SQLiteJobRepository, path: Path) -> None:
    """Regenerates a read-only human-facing Excel snapshot from the SQLite
    store (the source of truth). Always rebuilt from scratch — this is a
    view, not something to hand-edit or accumulate independent state in.
    Rows are sorted by relevance score (descending) within each sheet so the
    best-fit, most actionable postings surface first.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)
    sheets = {}
    for sheet_name in (SHEET_AM, SHEET_FINANCE, SHEET_OFF_TOPIC):
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(EXPORT_HEADERS)
        sheets[sheet_name] = sheet

    scored_postings = [(posting, score_posting(posting)) for posting in repository.all_postings()]
    scored_postings.sort(key=lambda pair: (pair[1].score, pair[0]["detected_at"] or ""), reverse=True)

    for posting, score_result in scored_postings:
        sheet = sheets[_sheet_for_category(posting["category"])]
        sheet.append(_row_values(posting, score_result))

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
