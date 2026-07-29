from urllib.parse import urljoin

from bs4 import BeautifulSoup

import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting

BASE_URL = "https://jobs.jobvite.com"
URL = f"{BASE_URL}/natixis"


class NatixisIMFetcher:
    """Fetcher for Natixis Investment Managers' Jobvite careers page — a
    distinct entity from the Natixis group site (see CLAUDE.md — Périmètre,
    both scraped per explicit decision). Server-rendered HTML table, no API
    needed. Listings observed so far are almost entirely US-based.
    """

    def __init__(self, display_name: str = "Natixis Investment Managers", session: requests.Session | None = None):
        self._display_name = display_name
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        response = self._session.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        # `.content` + BeautifulSoup's own encoding detection, not `.text` —
        # see comgest.py for why (`.text` guesses wrong when Content-Type
        # omits a charset, producing "é" -> "Ã©" mojibake).
        soup = BeautifulSoup(response.content, "lxml")

        postings = []
        for row in soup.select("table.jv-job-list tbody tr"):
            link = row.select_one("td.jv-job-list-name a")
            if not link:
                continue
            title = link.get_text(strip=True)
            if not looks_like_internship(title):
                continue

            location_cell = row.select_one("td.jv-job-list-location")
            location = " ".join(location_cell.get_text(" ", strip=True).split()) if location_cell else None

            postings.append(
                JobPosting(
                    company=self._display_name,
                    title=title,
                    url=urljoin(BASE_URL, link.get("href", "")),
                    description=title,
                    location=location,
                    source_platform="jobvite",
                )
            )

        return postings
