from abc import ABC, abstractmethod

from src.models import JobPosting


class JobRepository(ABC):
    @abstractmethod
    def exists(self, stable_id: str) -> bool: ...

    @abstractmethod
    def add(self, posting: JobPosting) -> None: ...

    @abstractmethod
    def update_letter(self, stable_id: str, letter_text: str) -> None: ...

    def postings_missing_letter(self, category: str = "A") -> list[JobPosting]:
        """Postings of the given category still lacking a generated letter —
        used to retry letter generation for postings whose first attempt
        failed (e.g. Gemini quota exhaustion) without re-scraping/re-
        classifying them. Default no-op for implementations that don't need
        this (e.g. the legacy Excel repository, no longer the source of
        truth)."""
        return []

    def update_tracking_fields(self, stable_id: str, application_status: str, application_date: str, follow_up_date: str, notes: str) -> None:
        """Clara-owned tracking columns synced back from the Google Sheet
        (Phase 4) — distinct from `status`, the system-managed posting
        lifecycle field. Default no-op for implementations that don't track
        these."""
