from bs4 import BeautifulSoup

import requests

from src.models import JobPosting

MAX_PAGES = 20


class TalentsoftFetcher:
    """Fetcher for Cegid Talentsoft career sites, shared by Amundi and Candriam
    (see CLAUDE.md — Périmètre). The listing page is server-rendered HTML;
    contract type ("Stage", "CDI", "Alternance / Apprentissage"...) is the
    first item of each posting's ts-offer-list-item__description list —
    filtering on that exact label is far more reliable than a title keyword
    match, so it's used instead of the generic looks_like_internship helper.
    """

    def __init__(self, base_url: str, display_name: str, session: requests.Session | None = None, lcid: int = 1036):
        self._base_url = base_url.rstrip("/")
        self._display_name = display_name
        self._session = session or requests
        self._lcid = lcid

    def fetch(self) -> list[JobPosting]:
        raw_items: list[dict] = []
        page = 1

        while page <= MAX_PAGES:
            html = self._fetch_page(page)
            items = self._parse_items(html)
            if not items:
                break
            if raw_items and items[0]["href"] == raw_items[0]["href"]:
                # Beyond the last real page, Talentsoft silently re-serves page 1
                # instead of an empty list — stop rather than loop forever.
                break
            raw_items.extend(items)
            page += 1

        return [self._to_job_posting(item) for item in raw_items if item["contract_type"].strip().lower() == "stage"]

    def _fetch_page(self, page: int) -> bytes:
        url = f"{self._base_url}/offre-de-emploi/liste-toutes-offres.aspx?page={page}&LCID={self._lcid}"
        response = self._session.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        # `.content` + BeautifulSoup's own encoding detection, not `.text` —
        # see comgest.py for why (`.text` guesses wrong when Content-Type
        # omits a charset, producing "é" -> "Ã©" mojibake).
        return response.content

    def _parse_items(self, html: bytes) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        items = []
        for li in soup.select("li.ts-offer-list-item"):
            link = li.select_one("a.ts-offer-list-item__title-link")
            if not link:
                continue
            description_fields = [d.get_text(strip=True) for d in li.select("ul.ts-offer-list-item__description li")]
            items.append(
                {
                    "title": link.get_text(strip=True),
                    "href": link.get("href", ""),
                    "contract_type": description_fields[0] if len(description_fields) > 0 else "",
                    "entity": description_fields[1] if len(description_fields) > 1 else "",
                    "country": description_fields[2] if len(description_fields) > 2 else "",
                    "city": description_fields[3] if len(description_fields) > 3 else "",
                }
            )
        return items

    def _to_job_posting(self, item: dict) -> JobPosting:
        href = item["href"]
        url = f"{self._base_url}{href}" if href.startswith("/") else href
        location = ", ".join(part for part in (item["city"], item["country"]) if part) or None

        return JobPosting(
            company=self._display_name,
            title=item["title"],
            url=url,
            description=item["entity"],
            location=location,
            source_platform="talentsoft",
        )
