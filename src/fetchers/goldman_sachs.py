import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting

API_URL = "https://api-higher.gs.com/gateway/api/v1/graphql"
PAGE_SIZE = 20

# Goldman Sachs' campus portal (higher.gs.com) lists every division worldwide
# (Engineering, Compliance, HR...), not just finance. Restricting to these
# three divisions upfront avoids forcing the Gemini classifier (which only
# outputs A/B, no "not relevant" option) to mislabel obviously irrelevant
# postings like a Singapore Operations internship.
RELEVANT_DIVISIONS = {
    "Asset & Wealth Management",
    "Global Banking & Markets",
    "Global Investment Research Division",
}

QUERY = """query GetCampusRoles($searchQueryInput: RoleSearchQueryInput!) {
  roleSearch(searchQueryInput: $searchQueryInput) {
    totalCount
    items {
      roleId
      jobTitle
      division
      locations { primary state country city __typename }
      externalSource { sourceId __typename }
      __typename
    }
    __typename
  }
}"""


class GoldmanSachsFetcher:
    """Fetcher for Goldman Sachs' campus recruiting portal (higher.gs.com).

    Reverse-engineered from the portal's GraphQL API (captured via network
    inspection, no public docs) — the endpoint accepts plain unauthenticated
    POST requests, no browser/session token required despite the SPA
    front-end being client-rendered.
    """

    def __init__(self, display_name: str = "Goldman Sachs Asset Management", session: requests.Session | None = None):
        self._display_name = display_name
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        raw_items: list[dict] = []
        page_number = 0

        while True:
            result = self._fetch_page(page_number)
            batch = result.get("items", [])
            raw_items.extend(batch)

            page_number += 1
            if not batch or page_number * PAGE_SIZE >= result.get("totalCount", 0):
                break

        relevant = [
            item
            for item in raw_items
            if item.get("division") in RELEVANT_DIVISIONS and looks_like_internship(item.get("jobTitle", ""))
        ]
        return [self._to_job_posting(item) for item in relevant]

    def _fetch_page(self, page_number: int) -> dict:
        payload = {
            "operationName": "GetCampusRoles",
            "variables": {
                "searchQueryInput": {
                    "page": {"pageSize": PAGE_SIZE, "pageNumber": page_number},
                    "sort": {"sortStrategy": "RELEVANCE", "sortOrder": "DESC"},
                    "filters": [],
                    "experiences": ["CAMPUS"],
                    "searchTerm": "",
                }
            },
            "query": QUERY,
        }
        headers = {"content-type": "application/json", "accept": "*/*", "referer": "https://higher.gs.com/"}
        response = self._session.post(API_URL, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()["data"]["roleSearch"]

    def _to_job_posting(self, item: dict) -> JobPosting:
        locations = item.get("locations") or [{}]
        location = locations[0] or {}
        location_str = ", ".join(part for part in (location.get("city"), location.get("country")) if part) or None
        source_id = (item.get("externalSource") or {}).get("sourceId", "")

        return JobPosting(
            company=self._display_name,
            title=item.get("jobTitle", ""),
            url=f"https://higher.gs.com/roles/{source_id}",
            description=item.get("jobTitle", ""),
            location=location_str,
            source_platform="goldman_sachs_higher",
        )
