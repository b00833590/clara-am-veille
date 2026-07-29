from src.fetchers.base import looks_like_internship
from src.models import JobPosting

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


class FlatchrFetcher:
    """Fetcher for Flatchr career sites (React/Next.js SPA — the job list is
    loaded client-side, not present in the initial HTML, so this uses
    Playwright rather than a plain HTTP request. Used by OFI Invest (see
    CLAUDE.md — Périmètre).
    """

    def __init__(self, url: str, display_name: str):
        self._url = url
        self._display_name = display_name

    def fetch(self) -> list[JobPosting]:
        return self._parse_links(self._collect_links())

    def _collect_links(self) -> list[tuple[str, str]]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self._url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(1500)
                return page.eval_on_selector_all("a", "els => els.map(e => [e.href, e.innerText.trim()])")
            finally:
                browser.close()

    def _parse_links(self, links: list[tuple[str, str]]) -> list[JobPosting]:
        postings = []
        seen_urls: set[str] = set()

        for href, title in links:
            if "/vacancy/" not in href or href in seen_urls:
                continue
            seen_urls.add(href)
            if not title or not looks_like_internship(title):
                continue

            postings.append(
                JobPosting(
                    company=self._display_name,
                    title=title,
                    url=href,
                    description=title,
                    source_platform="flatchr",
                )
            )

        return postings
