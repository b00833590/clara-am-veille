from dataclasses import dataclass, field, replace
from typing import Protocol

from src.classification.gemini_classifier import ClassificationResult
from src.fetchers.base import Fetcher
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
        try:
            postings = fetcher.fetch()
        except Exception as exc:
            summary.errors.append((name, str(exc)))
            continue

        for posting in postings:
            _process_posting(name, posting, repository, classifier, notifier, letter_generator, draft_creator, summary)

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

    try:
        result = classifier.classify(posting)
    except Exception as exc:
        summary.errors.append((f"{source_name} (classification)", str(exc)))
        return

    classified_posting = replace(
        posting,
        category=result.category,
        language=result.language,
        to_verify=result.to_verify,
        classification_reason=result.reason,
        location_priority=location_priority(posting.location),
    )

    if classified_posting.category != CATEGORY_OFF_TOPIC:
        try:
            notifier.notify_new_posting(classified_posting)
        except Exception as exc:
            summary.errors.append((f"{source_name} (notification)", str(exc)))
            return

    repository.add(classified_posting)
    summary.new_postings.append(classified_posting)

    if classified_posting.category == CATEGORY_TRIGGERING_LETTER_GENERATION and letter_generator and draft_creator:
        _generate_letter(source_name, classified_posting, repository, letter_generator, draft_creator, summary)


def _generate_letter(
    source_name: str,
    posting: JobPosting,
    repository: JobRepository,
    letter_generator: LetterGenerator,
    draft_creator: DraftCreator,
    summary: PollingSummary,
) -> None:
    try:
        letter = letter_generator.generate(posting)
        draft_creator.create_draft(posting, letter)
        repository.update_letter(posting.stable_id(), letter.letter_text)
    except Exception as exc:
        summary.errors.append((f"{source_name} (lettre)", str(exc)))


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
        try:
            letter = letter_generator.generate(posting)
            draft_creator.create_draft(posting, letter)
            repository.update_letter(posting.stable_id(), letter.letter_text)
            summary.new_postings.append(posting)
        except Exception as exc:
            summary.errors.append((f"{posting.company} (lettre - retry)", str(exc)))

    return summary
