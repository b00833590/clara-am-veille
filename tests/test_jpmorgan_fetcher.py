from src.fetchers.jpmorgan import JPMorganFetcher
from src.models import JobPosting


class FakeSubFetcher:
    def __init__(self, postings):
        self._postings = postings

    def fetch(self):
        return self._postings


def posting(url, title="Stage Analyste"):
    return JobPosting(company="JP Morgan Asset Management", title=title, url=url, description="")


def test_fetch_merges_results_from_both_keyword_searches():
    fetcher = JPMorganFetcher(sub_fetchers=[FakeSubFetcher([posting("https://x/1")]), FakeSubFetcher([posting("https://x/2")])])

    postings = fetcher.fetch()

    assert {p.url for p in postings} == {"https://x/1", "https://x/2"}


def test_fetch_dedupes_postings_found_by_both_keyword_searches():
    fetcher = JPMorganFetcher(
        sub_fetchers=[FakeSubFetcher([posting("https://x/1")]), FakeSubFetcher([posting("https://x/1"), posting("https://x/2")])]
    )

    postings = fetcher.fetch()

    assert len(postings) == 2
    assert {p.url for p in postings} == {"https://x/1", "https://x/2"}


def test_default_construction_targets_cx_1001_with_internship_and_stage_keywords():
    fetcher = JPMorganFetcher()

    keywords = {getattr(f, "_keyword", None) for f in fetcher._sub_fetchers}
    hosts = {getattr(f, "_host", None) for f in fetcher._sub_fetchers}
    site_numbers = {getattr(f, "_site_number", None) for f in fetcher._sub_fetchers}

    assert keywords == {"internship", "stage"}
    assert hosts == {"jpmc.fa.oraclecloud.com"}
    assert site_numbers == {"CX_1001"}
