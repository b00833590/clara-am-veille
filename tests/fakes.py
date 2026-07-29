from src.models import JobPosting
from src.storage.repository import JobRepository


class FakeFetcher:
    def __init__(self, postings=None, error: Exception | None = None):
        self._postings = postings or []
        self._error = error

    def fetch(self) -> list[JobPosting]:
        if self._error:
            raise self._error
        return self._postings


class InMemoryJobRepository(JobRepository):
    def __init__(self):
        self._seen: dict[str, JobPosting] = {}
        self.letters: dict[str, str] = {}

    def exists(self, stable_id: str) -> bool:
        return stable_id in self._seen

    def add(self, posting: JobPosting) -> None:
        self._seen[posting.stable_id()] = posting

    def update_letter(self, stable_id: str, letter_text: str) -> None:
        self.letters[stable_id] = letter_text

    def postings_missing_letter(self, category: str = "A") -> list[JobPosting]:
        return [
            posting
            for stable_id, posting in self._seen.items()
            if posting.category == category and not self.letters.get(stable_id)
        ]
