from dataclasses import dataclass, field, replace
from typing import Protocol

from src.classification.models import ClassificationResult
from src.fetchers.base import Fetcher
from src.gemini_retry import GeminiQuotaExhausted
from src.generation.gemini_letter_generator import LetterDraft
from src.location_priority import location_priority
from src.models import JobPosting
from src.storage.repository import JobRepository

CATEGORY_TRIGGERING_LETTER_GENERATION = "A"
CATEGORY_OFF_TOPIC = "N"


class Classifier(Protocol):
    def classify(self, posting: JobPosting) -> ClassificationResult: ...


class Notifier(Protocol):
    def notify_new_posting(self, posting: JobPosting) -> None: ...


class LetterGenerator(Protocol):
    def generate(self, posting: JobPosting) -> LetterDraft: ...


class DraftCreator(Protocol):
    def create_draft(self, posting: JobPosting, letter: LetterDraft) -> str: ...


@dataclass
class PollingSummary:
    new_postings: list[JobPosting] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)


def run_polling_pass(
    sources: list[tuple[str, Fetcher]],
    repository: JobRepository,
    classifier: Classifier,
    notifier: Notifier,
    letter_generator: LetterGenerator | None = None,
    draft_creator: DraftCreator | None = None,
) -> PollingSummary:
    summary = PollingSummary()

    for name, fetcher in sources:
        print(f"[{name}] interrogation...", flush=True)
        try:
            postings = fetcher.fetch()
        except Exception as exc:
            summary.errors.append((name, str(exc)))
            print(f"[{name}] erreur : {exc}", flush=True)
            continue

        print(f"[{name}] {len(postings)} offre(s) trouvée(s)", flush=True)
        for posting in postings:
            try:
                _process_posting(name, posting, repository, classifier, notifier, letter_generator, draft_creator, summary)
            except GeminiQuotaExhausted as exc:
                summary.errors.append((name, f"quota Gemini épuisé pour la journée, arrêt du run : {exc}"))
                print(f"[{name}] quota Gemini épuisé — arrêt du run, offres restantes retraitées au prochain passage", flush=True)
                return summary

    return summary


def _process_posting(
    source_name: str,
    posting: JobPosting,
    repository: JobRepository,
    classifier: Classifier,
    notifier: Notifier,
    letter_generator: LetterGenerator | None,
    draft_creator: DraftCreator | None,
    summary: PollingSummary,
) -> None:
    if repository.exists(posting.stable_id()):
        return

    print(f"  [{source_name}] classification : {posting.title}", flush=True)
    try:
        result = classifier.classify(posting)
    except GeminiQuotaExhausted:
        raise
    except Exception as exc:
        summary.errors.append((f"{source_name} (classification)", str(exc)))
        print(f"  [{source_name}] échec classification : {exc}", flush=True)
        return

    classified_posting = replace(
        posting,
        category=result.category,
        language=result.language,
        to_verify=result.to_verify,
        classification_reason=result.reason,
        team_division=result.team_division,
        location_priority=location_priority(posting.location),
    )

    # Every category-A posting is emailed, confident match or not — the
    # 2026-07-30 version gated email on a confident match (to_verify=False)
    # to stop real noise (M&A/IB internships, "Contrôleur financier", "Team
    # Assistant" defaulting to A before the exclude list caught up). But a
    # live diagnostic on 2026-08-04 found that gate had overcorrected: with
    # the keyword lists as they stood, 12/12 genuinely new AM offers between
    # 2026-07-31 and 2026-08-03 fell into the "no signal" default
    # (to_verify=True) and were silently never emailed — including clear
    # AM roles like "Investment Risk Data Analyst" and "Quantitative
    # Research". Any keyword list will always miss real-world phrasing, so
    # relying on it to gate *visibility* is too brittle. Visibility (email)
    # is now unconditional on category; confidence (to_verify) only gates
    # the *auto-lettered* subset — see build_notification_message, which
    # already flags to_verify postings in the subject/body so Clara can
    # triage at a glance without them requiring a manual Sheet check.
    is_am_category = classified_posting.category == CATEGORY_TRIGGERING_LETTER_GENERATION
    is_confident_am_match = is_am_category and not classified_posting.to_verify

    if is_am_category:
        try:
            notifier.notify_new_posting(classified_posting)
        except Exception as exc:
            summary.errors.append((f"{source_name} (notification)", str(exc)))
            return

    repository.add(classified_posting)
    summary.new_postings.append(classified_posting)

    if is_confident_am_match and letter_generator and draft_creator:
        _generate_letter(source_name, classified_posting, repository, letter_generator, draft_creator, summary)


def _generate_letter(
    source_name: str,
    posting: JobPosting,
    repository: JobRepository,
    letter_generator: LetterGenerator,
    draft_creator: DraftCreator,
    summary: PollingSummary,
) -> None:
    print(f"  [{source_name}] génération de la lettre : {posting.title}", flush=True)
    try:
        letter = letter_generator.generate(posting)
        draft_creator.create_draft(posting, letter)
        repository.update_letter(posting.stable_id(), letter.letter_text)
    except GeminiQuotaExhausted:
        raise
    except Exception as exc:
        summary.errors.append((f"{source_name} (lettre)", str(exc)))
        print(f"  [{source_name}] échec génération de la lettre : {exc}", flush=True)


def retry_missing_letters(
    repository: JobRepository,
    letter_generator: LetterGenerator,
    draft_creator: DraftCreator,
) -> PollingSummary:
    """Category-A postings already stored but still missing a letter (first
    attempt failed — Gemini quota exhaustion, confirmed live on 2026-07-22)
    never get revisited by run_polling_pass, since its exists() check skips
    anything already known. Without this, a genuinely good opportunity stays
    letter-less forever the moment its first attempt fails, with no signal
    to anyone that it needs a retry. Doesn't re-scrape or re-classify —
    only fills in the missing letter once Gemini quota is available again.
    """
    summary = PollingSummary()

    for posting in repository.postings_missing_letter():
        print(f"[retry lettre] {posting.company} : {posting.title}", flush=True)
        try:
            letter = letter_generator.generate(posting)
            draft_creator.create_draft(posting, letter)
            repository.update_letter(posting.stable_id(), letter.letter_text)
            summary.new_postings.append(posting)
        except GeminiQuotaExhausted as exc:
            summary.errors.append((f"{posting.company} (lettre - retry)", f"quota Gemini épuisé, arrêt du rattrapage : {exc}"))
            print("[retry lettre] quota Gemini épuisé — arrêt, offres restantes retraitées au prochain passage", flush=True)
            return summary
        except Exception as exc:
            summary.errors.append((f"{posting.company} (lettre - retry)", str(exc)))
            print(f"[retry lettre] échec pour {posting.company} : {exc}", flush=True)

    return summary
