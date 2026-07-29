import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting

API_URL = "https://recrutement.natixis.com/app/wp-json/bpce/v1/search/jobs"
BASE_URL = "https://recrutement.natixis.com"
PAGE_SIZE = 100


class NatixisGroupFetcher:
    """Fetcher for the Natixis / Groupe BPCE careers site (custom WordPress
    REST API, `bpce` namespace — reverse-engineered via network inspection,
    no auth required). Covers all Natixis brands in one feed (CIB, Ostrum
    Asset Management, Natixis Interépargne...), not filtered by brand — the
    downstream Gemini classifier sorts AM-relevant (A) from other finance (B).
    """

    def __init__(self, display_name: str = "Natixis", session: requests.Session | None = None):
        self._display_name = display_name
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        raw_items: list[dict] = []
        offset = 0

        while True:
            data = self._fetch_page(offset)
            batch = data.get("items", [])
            raw_items.extend(batch)

            offset += PAGE_SIZE
            if not batch or offset >= data.get("total", 0):
                break

        return [self._to_job_posting(item) for item in raw_items if looks_like_internship(item.get("title", ""))]

    def _fetch_page(self, offset: int) -> dict:
        payload = {"lang": "fr", "keyword": "", "from": offset, "size": PAGE_SIZE}
        response = self._session.post(API_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        response.raise_for_status()
        return response.json()["data"]

    def _to_job_posting(self, item: dict) -> JobPosting:
        relative_url = (item.get("link") or {}).get("url", "")
        return JobPosting(
            company=self._display_name,
            title=item.get("title", ""),
            url=f"{BASE_URL}{relative_url}",
            description=item.get("title", ""),
            source_platform="natixis_group",
        )
