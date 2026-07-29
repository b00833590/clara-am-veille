import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting

PAGE_SIZE = 25


class OracleHcmFetcher:
    """Fetcher for Oracle Recruiting Cloud (Fusion Cloud HCM) candidate
    experience sites, shared by Lazard and Edmond de Rothschild (see
    CLAUDE.md — Périmètre). Uses the public recruitingCEJobRequisitions REST
    resource that backs the candidate-facing site — no auth required.
    """

    def __init__(
        self,
        host: str,
        site_number: str,
        display_name: str,
        locale: str = "en",
        keyword: str | None = None,
        session: requests.Session | None = None,
    ):
        self._host = host
        self._site_number = site_number
        self._display_name = display_name
        self._locale = locale
        self._keyword = keyword
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        raw_items: list[dict] = []
        offset = 0

        while True:
            search_result = self._fetch_page(offset)
            batch = search_result.get("requisitionList") or []
            raw_items.extend(batch)

            offset += PAGE_SIZE
            if not batch or offset >= search_result.get("TotalJobsCount", 0):
                break

        return [self._to_job_posting(item) for item in raw_items if looks_like_internship(item.get("Title", ""))]

    def _fetch_page(self, offset: int) -> dict:
        url = f"https://{self._host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        finder = f"findReqs;siteNumber={self._site_number},limit={PAGE_SIZE},offset={offset},sortBy=POSTING_DATES_DESC"
        if self._keyword:
            finder += f",keyword={self._keyword}"
        params = {
            "onlyData": "true",
            "expand": "requisitionList.secondaryLocations",
            "finder": finder,
        }
        response = self._session.get(url, params=params, timeout=20, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()["items"][0]

    def _to_job_posting(self, item: dict) -> JobPosting:
        return JobPosting(
            company=self._display_name,
            title=item.get("Title", ""),
            url=f"https://{self._host}/hcmUI/CandidateExperience/{self._locale}/sites/{self._site_number}/job/{item.get('Id')}",
            description=item.get("ShortDescriptionStr") or "",
            location=item.get("PrimaryLocation"),
            source_platform="oracle_hcm",
        )
