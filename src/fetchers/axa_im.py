import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting

API_URL = "https://careers.axa.com/api/jobs"
ENTITY_TAG = "AXA Investment Managers"


class AxaIMFetcher:
    """Fetcher for AXA Investment Managers via the AXA group's shared careers
    site (careers.axa.com, iCIMS-backed, ~1500 postings across every AXA
    entity worldwide). Reverse-engineered `tags3` facet filter scopes the
    query to the AXA IM entity specifically server-side.

    As of writing, AXA IM has zero postings on this shared platform (its
    entity tag simply doesn't appear in the group's facet list) — confirmed
    the filter itself works correctly (verified against "AXA France",
    479 results) rather than being silently broken. This connector stays
    correctly silent until AXA IM starts posting here.
    """

    def __init__(self, display_name: str = "Axa Investment Managers", session: requests.Session | None = None):
        self._display_name = display_name
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        response = self._session.get(
            API_URL,
            params={"tags3": ENTITY_TAG, "page": 1, "sortBy": "relevance", "internal": "false", "limit": 50},
            timeout=20,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        jobs = response.json().get("jobs", [])

        return [self._to_job_posting(item["data"]) for item in jobs if looks_like_internship(item["data"].get("title", ""))]

    def _to_job_posting(self, data: dict) -> JobPosting:
        location = ", ".join(part for part in (data.get("city"), data.get("country")) if part) or None
        return JobPosting(
            company=self._display_name,
            title=data.get("title", ""),
            url=data.get("apply_url"),
            description=data.get("title", ""),
            location=location,
            source_platform="axa_careers",
        )
