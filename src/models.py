import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class JobPosting:
    company: str
    title: str
    url: str | None
    description: str
    location: str | None = None
    start_date: str | None = None
    category: str | None = None
    language: str | None = None
    to_verify: bool = False
    classification_reason: str = ""
    team_division: str = ""
    location_priority: int = 4
    status: str = "Nouvelle"
    cover_letter_link: str | None = None
    source_platform: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def stable_id(self) -> str:
        basis = self.url if self.url else f"{self.company}|{self.title}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
