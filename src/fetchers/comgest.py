from bs4 import BeautifulSoup

import requests

from src.fetchers.base import looks_like_internship
from src.models import JobPosting

GENERIC_FALLBACK_TITLE = "don't see your position?"


class ComgestFetcher:
    """Fetcher for Comgest's own careers page (server-rendered HTML accordion).

    NOTE: at the time this was written, Comgest had zero open positions —
    only verified against the generic "don't see your position?" fallback
    entry. The real-posting item structure below mirrors that same accordion
    markup (dt/dd pair, .accordion__header__button__text, .cta-link) but
    hasn't been spot-checked against an actual open role yet. Re-verify once
    Comgest publishes a real internship posting.
    """

    def __init__(self, url: str, display_name: str, session: requests.Session | None = None):
        self._url = url
        self._display_name = display_name
        self._session = session or requests

    def fetch(self) -> list[JobPosting]:
        response = self._session.get(self._url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        # `.content` (raw bytes) + BeautifulSoup's own HTML-aware encoding
        # detection, not `.text` — requests falls back to guessing the
        # encoding when the server's Content-Type omits a charset, and can
        # guess wrong (confirmed live: produces "é" -> "Ã©" mojibake).
        soup = BeautifulSoup(response.content, "lxml")

        accordion = soup.select_one("dl#JobListings")
        if not accordion:
            return []

        postings = []
        for dt in accordion.find_all("dt", recursive=False):
            title_el = dt.select_one(".accordion__header__button__text")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if title.strip().lower() == GENERIC_FALLBACK_TITLE:
                continue
            if not looks_like_internship(title):
                continue

            dd = dt.find_next_sibling("dd")
            link = dd.select_one("a") if dd else None
            url = link.get("href") if link else None

            postings.append(
                JobPosting(
                    company=self._display_name,
                    title=title,
                    url=url,
                    description=title,
                    source_platform="site_maison_comgest",
                )
            )

        return postings
