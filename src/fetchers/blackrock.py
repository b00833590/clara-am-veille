from urllib.parse import urljoin

from bs4 import BeautifulSoup

import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting

BASE_URL = "https://careers.blackrock.com"
ENDPOINT = f"{BASE_URL}/search-jobs/results"
RECORDS_PER_PAGE = 50


class BlackRockFetcher:
    """Fetcher for BlackRock's TalentBrew careers site — reverse-engineered
    the AJAX search endpoint (`/search-jobs/results`, returns an HTML
    fragment wrapped in JSON) via network inspection. Public, unauthenticated
    GET. Server-side keyword search for "intern" already narrows results, but
    we still apply our own word-boundary title filter as defense-in-depth —
    TalentBrew's own keyword match may not be word-boundary aware either.
    """

    def __init__(self, display_name: str = "BlackRock", session: requests.Session | None = None):
        self._display_name = display_name
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        page_number = 1

        while True:
            fragment_html, total_pages = self._fetch_page(page_number)
            items = self._parse_items(fragment_html)
            postings.extend(items)

            if page_number >= total_pages:
                break
            page_number += 1

        return postings

    def _fetch_page(self, page_number: int) -> tuple[str, int]:
        params = {
            "ActiveFacetID": "",
            "CurrentPage": page_number,
            "RecordsPerPage": RECORDS_PER_PAGE,
            "Distance": 50,
            "RadiusUnitType": 0,
            "Keywords": "intern",
            "Location": "",
            "ShowRadius": "False",
            "IsPagination": "True" if page_number > 1 else "False",
            "CustomFacetName": "",
            "FacetTerm": "",
            "FacetType": 0,
            "SearchResultsModuleName": "Search Results",
            "SearchFiltersModuleName": "Search Filters",
            "SortCriteria": 0,
            "SortDirection": 0,
            "SearchType": 5,
            "LocationType": 3,
        }
        response = self._session.get(ENDPOINT, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        fragment_html = response.json().get("results", "")

        soup = BeautifulSoup(fragment_html, "lxml")
        section = soup.select_one("#search-results")
        total_pages = int(section.get("data-total-pages", 1)) if section else 1
        return fragment_html, total_pages

    def _parse_items(self, fragment_html: str) -> list[JobPosting]:
        soup = BeautifulSoup(fragment_html, "lxml")
        postings = []

        for link in soup.select("#search-results-list li a"):
            title_el = link.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else ""
            if not looks_like_internship(title):
                continue

            location_el = link.select_one(".job-location")
            location = location_el.get_text(strip=True) if location_el else None

            postings.append(
                JobPosting(
                    company=self._display_name,
                    title=title,
                    url=urljoin(BASE_URL, link.get("href", "")),
                    description=title,
                    location=location,
                    source_platform="talentbrew_blackrock",
                )
            )

        return postings
