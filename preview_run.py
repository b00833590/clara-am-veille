"""Lance le pipeline complet (scraping + classification + génération de
lettres) sans toucher à Gmail — utile pour vérifier concrètement ce que le
système produit avant le premier test avec le consentement OAuth de Clara.
Les étapes qui enverraient un email ou créeraient un brouillon Gmail sont
remplacées par des versions à blanc ; tout le reste (repository Excel,
classification, génération de lettres) est le vrai code de production.
"""

import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from src.classification.gemini_classifier import GeminiClassifier
from src.classification.hybrid_classifier import HybridClassifier
from src.config import active_sources, pending_sources
from src.generation.gemini_letter_generator import GeminiLetterGenerator, LetterDraft
from src.models import JobPosting
from src.orchestrator import retry_missing_letters, run_polling_pass
from src.storage.excel_export import export_to_excel
from src.storage.sqlite_repository import SQLiteJobRepository

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "offres_preview.db"
EXCEL_EXPORT_PATH = ROOT / "data" / "offres_preview.xlsx"
CV_PATH = ROOT / "data" / "cv.txt"
REFERENCE_LETTER_PATH = ROOT / "data" / "reference_letter.txt"


class DryRunNotifier:
    def notify_new_posting(self, posting: JobPosting) -> None:
        print(f"  [notification à blanc, pas d'email envoyé] {posting.company} — {posting.title}")


class DryRunDraftCreator:
    def create_draft(self, posting: JobPosting, letter: LetterDraft) -> str:
        print(f"  [brouillon Gmail à blanc, pas de dépôt réel] {posting.company} — {posting.title}")
        return "preview-no-gmail"


def main() -> None:
    load_dotenv(ROOT / ".env")
    gemini_api_key = os.environ["GEMINI_API_KEY"]

    DB_PATH.parent.mkdir(exist_ok=True)
    repository = SQLiteJobRepository(DB_PATH)
    classifier = HybridClassifier(gemini_classifier=GeminiClassifier.from_api_key(gemini_api_key))
    letter_generator = GeminiLetterGenerator.from_api_key(
        gemini_api_key,
        cv_text=CV_PATH.read_text(encoding="utf-8"),
        reference_letter_text=REFERENCE_LETTER_PATH.read_text(encoding="utf-8"),
    )

    sources = active_sources()
    print(f"Sources actives interrogées : {len(sources)}")

    summary = run_polling_pass(sources, repository, classifier, DryRunNotifier(), letter_generator, DryRunDraftCreator())

    print(f"\nNouvelles offres détectées et classées : {len(summary.new_postings)}")
    for posting in summary.new_postings:
        flag = " [À VÉRIFIER]" if posting.to_verify else ""
        print(f"  - [{posting.company}] ({posting.category}, {posting.language}){flag} {posting.title}")

    if summary.errors:
        print(f"\nErreurs ({len(summary.errors)}) :")
        for source_name, error in summary.errors:
            print(f"  - {source_name}: {error}")

    pending = pending_sources()
    print(f"\nSources en attente de connecteur ({len(pending)}/{len(pending) + len(sources)})")

    retry_summary = retry_missing_letters(repository, letter_generator, DryRunDraftCreator())
    if retry_summary.new_postings:
        print(f"\nLettres générées pour des offres déjà connues (échec précédent) : {len(retry_summary.new_postings)}")
        for posting in retry_summary.new_postings:
            print(f"  - [{posting.company}] {posting.title}")
    if retry_summary.errors:
        print(f"\nErreurs lors du rattrapage des lettres ({len(retry_summary.errors)}) :")
        for source_name, error in retry_summary.errors:
            print(f"  - {source_name}: {error}")

    export_to_excel(repository, EXCEL_EXPORT_PATH)
    print(f"\nBase de données (preview) : {DB_PATH}")
    print(f"Fichier de suivi (export lecture seule) : {EXCEL_EXPORT_PATH}")


if __name__ == "__main__":
    main()
