import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from src.classification.rule_based_classifier import RuleBasedClassifier
from src.config import active_sources, pending_sources
from src.generation.gemini_letter_generator import GeminiLetterGenerator
from src.notifications.gmail_auth import get_gmail_service, get_sheets_service
from src.notifications.gmail_draft import GmailDraftCreator
from src.notifications.gmail_notifier import GmailNotifier
from src.orchestrator import retry_missing_letters, run_polling_pass
from src.storage.excel_export import export_to_excel
from src.storage.sqlite_repository import SQLiteJobRepository
from src.tracking.sheets_sync import SheetsSync

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "offres.db"
EXCEL_EXPORT_PATH = ROOT / "data" / "offres.xlsx"
CV_PATH = ROOT / "data" / "cv.txt"
CV_PDF_PATH = ROOT / "data" / "cv.pdf"
REFERENCE_LETTER_PATH = ROOT / "data" / "reference_letter.txt"
CLIENT_SECRET_PATH = ROOT / "client_secret.json"
TOKEN_PATH = ROOT / "token.json"


def main() -> None:
    load_dotenv(ROOT / ".env")

    gemini_api_key = os.environ["GEMINI_API_KEY"]
    recipient_email = os.environ["RECIPIENT_EMAIL"]

    DB_PATH.parent.mkdir(exist_ok=True)
    repository = SQLiteJobRepository(DB_PATH)
    classifier = RuleBasedClassifier()
    gmail_service = get_gmail_service(CLIENT_SECRET_PATH, TOKEN_PATH)
    notifier = GmailNotifier(gmail_service, recipient_email=recipient_email)
    letter_generator = GeminiLetterGenerator.from_api_key(
        gemini_api_key,
        cv_text=CV_PATH.read_text(encoding="utf-8"),
        reference_letter_text=REFERENCE_LETTER_PATH.read_text(encoding="utf-8"),
    )
    if CV_PDF_PATH.exists():
        cv_pdf_bytes = CV_PDF_PATH.read_bytes()
    else:
        cv_pdf_bytes = None
        print(f"Attention : {CV_PDF_PATH} introuvable — les brouillons de lettres n'auront pas le CV en pièce jointe.")
    draft_creator = GmailDraftCreator(gmail_service, cv_pdf_bytes=cv_pdf_bytes)

    sources = active_sources()
    summary = run_polling_pass(sources, repository, classifier, notifier, letter_generator, draft_creator)

    print(f"Sources actives interrogées : {len(sources)}")
    print(f"Nouvelles offres détectées, classées et notifiées : {len(summary.new_postings)}")
    for posting in summary.new_postings:
        flag = " [À VÉRIFIER]" if posting.to_verify else ""
        letter_note = " — brouillon de lettre déposé dans Gmail" if posting.category == "A" else ""
        print(f"  - [{posting.company}] ({posting.category}){flag} {posting.title} -> {posting.url}{letter_note}")

    if summary.errors:
        print(f"Erreurs ({len(summary.errors)}) :")
        for source_name, error in summary.errors:
            print(f"  - {source_name}: {error}")

    pending = pending_sources()
    print(f"Sources en attente de connecteur ({len(pending)}/{len(pending) + len(sources)}) :")
    for source in pending:
        print(f"  - {source.company}: {source.note}")

    retry_summary = retry_missing_letters(repository, letter_generator, draft_creator)
    if retry_summary.new_postings:
        print(f"Lettres générées pour des offres déjà connues (échec précédent) : {len(retry_summary.new_postings)}")
        for posting in retry_summary.new_postings:
            print(f"  - [{posting.company}] {posting.title}")
    if retry_summary.errors:
        print(f"Erreurs lors du rattrapage des lettres ({len(retry_summary.errors)}) :")
        for source_name, error in retry_summary.errors:
            print(f"  - {source_name}: {error}")

    export_to_excel(repository, EXCEL_EXPORT_PATH)
    print(f"Base de données : {DB_PATH}")
    print(f"Fichier de suivi (export lecture seule) : {EXCEL_EXPORT_PATH}")

    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    if spreadsheet_id:
        sheets_service = get_sheets_service(CLIENT_SECRET_PATH, TOKEN_PATH)
        SheetsSync(sheets_service, spreadsheet_id).sync(repository)
        print("Tableau de suivi Google Sheets synchronisé.")
    else:
        print("SPREADSHEET_ID non configuré — synchronisation Google Sheets ignorée.")


if __name__ == "__main__":
    main()
