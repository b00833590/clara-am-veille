import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting


class WorkdayFetcher:
    """Fetcher for the Workday CXS jobs API, shared by BlackRock, Wellington,
    Capital Group and Pimco (see CLAUDE.md — Périmètre). Paginates with
    limit=20 — Workday's CXS API rejects requests with a larger limit (empirically
    confirmed: limit=100 returns HTTP 400, limit=20 works).
    """

    PAGE_SIZE = 20

    def __init__(self, tenant: str, wd_host: str, site: str, display_name: str, session: requests.Session | None = None):
        self._tenant = tenant
        self._wd_host = wd_host
        self._site = site
        self._display_name = display_name
        self._session = session or requests

    @property
    def _api_url(self) -> str:
        return f"https://{self._wd_host}/wday/cxs/{self._tenant}/{self._site}/jobs"

    @property
    def _site_base_url(self) -> str:
        return f"https://{self._wd_host}/{self._site}"

    def fetch(self) -> list[JobPosting]:
        raw_postings = []
        offset = 0

        while True:
            response = self._session.post(
                self._api_url,
                json={"appliedFacets": {}, "limit": self.PAGE_SIZE, "offset": offset, "searchText": ""},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            batch = data.get("jobPostings", [])
            raw_postings.extend(batch)

            offset += self.PAGE_SIZE
            if not batch or offset >= data.get("total", 0):
                break

        return [self._to_job_posting(item) for item in raw_postings if looks_like_internship(item.get("title", ""))]

    def _to_job_posting(self, item: dict) -> JobPosting:
        return JobPosting(
            company=self._display_name,
            title=item.get("title", ""),
            url=f"{self._site_base_url}{item.get('externalPath', '')}",
            description=item.get("title", ""),
            location=item.get("locationsText"),
            source_platform="workday",
        )
