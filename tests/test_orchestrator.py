from src.classification.models import ClassificationResult
from src.gemini_retry import GeminiQuotaExhausted
from src.generation.gemini_letter_generator import LetterDraft
from src.models import JobPosting
from src.orchestrator import retry_missing_letters, run_polling_pass
from tests.fakes import FakeFetcher, InMemoryJobRepository


def posting(company="Comgest", title="Stage Analyste", url="https://comgest.com/1", location=None, category=None):
    return JobPosting(company=company, title=title, url=url, description="", location=location, category=category)


class FakeClassifier:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result or ClassificationResult(category="A", language="fr", to_verify=False)
        self._error = error
        self.classified: list[JobPosting] = []

    def classify(self, posting: JobPosting) -> ClassificationResult:
        if self._error:
            raise self._error
        self.classified.append(posting)
        return self._result


class FakeNotifier:
    def __init__(self, error: Exception | None = None):
        self._error = error
        self.notified: list[JobPosting] = []

    def notify_new_posting(self, posting: JobPosting) -> None:
        if self._error:
            raise self._error
        self.notified.append(posting)


def test_new_postings_are_classified_stored_and_notified():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(result=ClassificationResult(category="A", language="fr", to_verify=False))
    notifier = FakeNotifier()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert len(summary.new_postings) == 1
    assert summary.new_postings[0].category == "A"
    assert repository.exists(posting().stable_id())
    assert len(notifier.notified) == 1


def test_classified_posting_gets_location_priority_from_its_location():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(result=ClassificationResult(category="A", language="fr", to_verify=False))
    notifier = FakeNotifier()
    sources = [("Comgest", FakeFetcher(postings=[posting(location="Paris, France")]))]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert summary.new_postings[0].location_priority == 1


def test_already_known_postings_are_skipped_without_classifying_or_notifying():
    repository = InMemoryJobRepository()
    repository.add(posting())
    classifier = FakeClassifier()
    notifier = FakeNotifier()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert summary.new_postings == []
    assert classifier.classified == []
    assert notifier.notified == []


def test_a_failing_source_does_not_stop_other_sources():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier()
    notifier = FakeNotifier()
    sources = [
        ("Broken ATS", FakeFetcher(error=ConnectionError("timeout"))),
        ("Comgest", FakeFetcher(postings=[posting()])),
    ]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert len(summary.new_postings) == 1
    assert ("Broken ATS", "timeout") in summary.errors


def test_summary_reports_no_errors_when_all_sources_succeed():
    repository = InMemoryJobRepository()
    sources = [("Comgest", FakeFetcher(postings=[]))]

    summary = run_polling_pass(sources, repository, FakeClassifier(), FakeNotifier())

    assert summary.errors == []


def test_classification_failure_is_not_stored_and_will_retry_next_run():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(error=RuntimeError("gemini down"))
    notifier = FakeNotifier()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert summary.new_postings == []
    assert not repository.exists(posting().stable_id())
    assert ("Comgest (classification)", "gemini down") in summary.errors
    assert notifier.notified == []


def test_gemini_quota_exhaustion_aborts_the_rest_of_the_run():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(error=GeminiQuotaExhausted("quota gone"))
    notifier = FakeNotifier()
    second_posting = posting(url="https://comgest.com/2")
    other_source_posting = posting(company="Amundi", url="https://amundi.com/1")
    sources = [
        ("Comgest", FakeFetcher(postings=[posting(), second_posting])),
        ("Amundi", FakeFetcher(postings=[other_source_posting])),
    ]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert summary.new_postings == []
    assert not repository.exists(second_posting.stable_id())
    assert not repository.exists(other_source_posting.stable_id())
    assert any("quota Gemini épuisé" in message for _, message in summary.errors)


def test_off_topic_posting_is_stored_but_not_notified():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(result=ClassificationResult(category="N", language="fr", to_verify=False))
    notifier = FakeNotifier()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert len(summary.new_postings) == 1
    assert repository.exists(posting().stable_id())
    assert notifier.notified == []


def test_notification_failure_is_not_stored_and_will_retry_next_run():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier()
    notifier = FakeNotifier(error=RuntimeError("gmail down"))
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert summary.new_postings == []
    assert not repository.exists(posting().stable_id())
    assert ("Comgest (notification)", "gmail down") in summary.errors


class FakeLetterGenerator:
    def __init__(self, letter=None, error: Exception | None = None):
        self._letter = letter or LetterDraft(letter_text="Madame, Monsieur,...")
        self._error = error
        self.generated_for: list[JobPosting] = []

    def generate(self, posting: JobPosting) -> LetterDraft:
        if self._error:
            raise self._error
        self.generated_for.append(posting)
        return self._letter


class FakeDraftCreator:
    def __init__(self, error: Exception | None = None):
        self._error = error
        self.created_for: list[JobPosting] = []

    def create_draft(self, posting: JobPosting, letter: LetterDraft) -> str:
        if self._error:
            raise self._error
        self.created_for.append(posting)
        return "fake-draft-id"


def test_category_a_posting_triggers_letter_generation_and_draft_creation():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(result=ClassificationResult(category="A", language="fr", to_verify=False))
    notifier = FakeNotifier()
    letter_generator = FakeLetterGenerator()
    draft_creator = FakeDraftCreator()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier, letter_generator, draft_creator)

    assert len(letter_generator.generated_for) == 1
    assert len(draft_creator.created_for) == 1
    assert repository.letters[posting().stable_id()] == "Madame, Monsieur,..."
    assert summary.errors == []


def test_off_topic_posting_does_not_trigger_letter_generation():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(result=ClassificationResult(category="N", language="fr", to_verify=False))
    notifier = FakeNotifier()
    letter_generator = FakeLetterGenerator()
    draft_creator = FakeDraftCreator()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    run_polling_pass(sources, repository, classifier, notifier, letter_generator, draft_creator)

    assert letter_generator.generated_for == []
    assert draft_creator.created_for == []


def test_letter_generation_failure_does_not_undo_notification_or_storage():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(result=ClassificationResult(category="A", language="fr", to_verify=False))
    notifier = FakeNotifier()
    letter_generator = FakeLetterGenerator(error=RuntimeError("gemini down"))
    draft_creator = FakeDraftCreator()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier, letter_generator, draft_creator)

    assert len(summary.new_postings) == 1
    assert repository.exists(posting().stable_id())
    assert ("Comgest (lettre)", "gemini down") in summary.errors


def test_no_letter_generation_when_generator_not_provided():
    repository = InMemoryJobRepository()
    classifier = FakeClassifier(result=ClassificationResult(category="A", language="fr", to_verify=False))
    notifier = FakeNotifier()
    sources = [("Comgest", FakeFetcher(postings=[posting()]))]

    summary = run_polling_pass(sources, repository, classifier, notifier)

    assert len(summary.new_postings) == 1
    assert summary.errors == []


def test_retry_missing_letters_generates_and_stores_letter_for_stuck_posting():
    # Reproduces the real 2026-07-22 case: a category-A posting whose first
    # letter-generation attempt failed (Gemini quota exhausted) must not stay
    # stuck forever just because it's already in the repository — a later
    # run has to be able to pick it back up without re-scraping/re-classifying.
    repository = InMemoryJobRepository()
    repository.add(posting(title="JPM Equity Research Intern", category="A"))
    letter_generator = FakeLetterGenerator()
    draft_creator = FakeDraftCreator()

    summary = retry_missing_letters(repository, letter_generator, draft_creator)

    assert len(letter_generator.generated_for) == 1
    assert letter_generator.generated_for[0].title == "JPM Equity Research Intern"
    assert len(draft_creator.created_for) == 1
    assert repository.letters[posting(title="JPM Equity Research Intern", category="A").stable_id()] == "Madame, Monsieur,..."
    assert len(summary.new_postings) == 1
    assert summary.errors == []


def test_retry_missing_letters_skips_postings_that_already_have_one():
    repository = InMemoryJobRepository()
    already_done = posting(title="Already has a letter", category="A")
    repository.add(already_done)
    repository.update_letter(already_done.stable_id(), "Existing letter")
    letter_generator = FakeLetterGenerator()
    draft_creator = FakeDraftCreator()

    retry_missing_letters(repository, letter_generator, draft_creator)

    assert letter_generator.generated_for == []
    assert draft_creator.created_for == []


def test_retry_missing_letters_records_error_and_leaves_posting_retryable_again():
    repository = InMemoryJobRepository()
    stuck_posting = posting(title="Still stuck", category="A")
    repository.add(stuck_posting)
    letter_generator = FakeLetterGenerator(error=RuntimeError("gemini still down"))
    draft_creator = FakeDraftCreator()

    summary = retry_missing_letters(repository, letter_generator, draft_creator)

    assert summary.new_postings == []
    assert ("Comgest (lettre - retry)", "gemini still down") in summary.errors
    assert stuck_posting.stable_id() not in repository.letters
