from src.fetchers.flatchr import FlatchrFetcher


def make_fetcher():
    return FlatchrFetcher(url="https://ofiinvestassetmanagement.flatchr.io/", display_name="OFI Invest")


def test_parse_links_filters_internship_titles():
    links = [
        ("https://x/fr/company/ofi/vacancy/1-cdi/", "Analyste Quantitatif ESG (H/F) CDI"),
        ("https://x/fr/company/ofi/vacancy/2-alt/", "Alternant Data Engineer / Data Analyst"),
        ("https://x/#", "Politique de confidentialité candidats"),
    ]

    postings = make_fetcher()._parse_links(links)

    assert len(postings) == 1
    assert postings[0].title == "Alternant Data Engineer / Data Analyst"


def test_parse_links_ignores_non_vacancy_links():
    links = [
        ("https://www.ofi-invest-am.com/fr", "Ofi Invest AM"),
        ("https://x/fr/company/ofi/vacancy/1-stage/", "Stage Analyste Gestion"),
    ]

    postings = make_fetcher()._parse_links(links)

    assert len(postings) == 1
    assert postings[0].url == "https://x/fr/company/ofi/vacancy/1-stage/"


def test_parse_links_dedupes_by_href():
    links = [
        ("https://x/fr/company/ofi/vacancy/1-stage/", "Stage Analyste"),
        ("https://x/fr/company/ofi/vacancy/1-stage/", "Stage Analyste"),
    ]

    postings = make_fetcher()._parse_links(links)

    assert len(postings) == 1


def test_parse_links_builds_job_posting_with_expected_fields():
    links = [("https://x/fr/company/ofi/vacancy/1-stage/", "Stage Analyste Gestion")]

    posting = make_fetcher()._parse_links(links)[0]

    assert posting.company == "OFI Invest"
    assert posting.source_platform == "flatchr"


def test_fetch_delegates_to_collect_links_then_parses(monkeypatch):
    fetcher = make_fetcher()
    monkeypatch.setattr(fetcher, "_collect_links", lambda: [("https://x/fr/company/ofi/vacancy/1-stage/", "Stage Analyste")])

    postings = fetcher.fetch()

    assert len(postings) == 1
