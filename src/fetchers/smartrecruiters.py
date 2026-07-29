import requests

from src.fetchers.base import label_of, looks_like_internship
from src.models import JobPosting


class SmartRecruitersFetcher:
    """Fetcher for companies hosted on SmartRecruiters (public postings API).

    Verified live against Sycomore Asset Management during Phase 0 discovery
    (api.smartrecruiters.com/v1/companies/{slug}/postings).
    """

    def __init__(self, company_identifier: str, display_name: str, session: requests.Session | None = None):
        self._company_identifier = company_identifier
        self._display_name = display_name
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        url = f"https://api.smartrecruiters.com/v1/companies/{self._company_identifier}/postings"
        response = self._session.get(url, timeout=15)
        response.raise_for_status()
        content = response.json().get("content", [])

        return [self._to_job_posting(item) for item in content if self._is_internship(item)]

    def _is_internship(self, item: dict) -> bool:
        experience_level = label_of(item.get("experienceLevel"))
        return looks_like_internship(experience_level, item.get("name", ""))

    def _to_job_posting(self, item: dict) -> JobPosting:
        posting_id = item["id"]
        location = item.get("location") or {}
        location_str = ", ".join(part for part in (location.get("city"), location.get("country")) if part) or None

        return JobPosting(
            company=self._display_name,
            title=item.get("name", ""),
            url=f"https://jobs.smartrecruiters.com/{self._company_identifier}/{posting_id}",
            description=item.get("name", ""),
            location=location_str,
            source_platform="smartrecruiters",
        )
