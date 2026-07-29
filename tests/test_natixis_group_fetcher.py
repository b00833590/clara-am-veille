from src.fetchers.natixis_group import NatixisGroupFetcher

API_URL = "https://recrutement.natixis.com/app/wp-json/bpce/v1/search/jobs"


def item(post_id, title, url):
    return {"post_id": post_id, "title": title, "link": {"url": url}}


def response(items, total=None):
    return {"code": "all_good", "data": {"total": total if total is not None else len(items), "items": items}}


def make_fetcher():
    return NatixisGroupFetcher()


def test_fetch_keeps_only_internship_titles(requests_mock):
    requests_mock.post(
        API_URL,
        json=response(
            [
                item(1, "Auditeur Interne (F/H)", "/job/auditeur-interne"),
                item(2, "Stagiaire Analyste Quantitatif", "/job/stagiaire-analyste-quantitatif"),
            ]
        ),
    )

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stagiaire Analyste Quantitatif"


def test_fetch_builds_job_posting_with_expected_fields(requests_mock):
    requests_mock.post(API_URL, json=response([item(1, "Stage Analyste Marchés Émergents", "/job/stage-analyste-marches-emergents")]))

    posting = make_fetcher().fetch()[0]

    assert posting.company == "Natixis"
    assert posting.url == "https://recrutement.natixis.com/job/stage-analyste-marches-emergents"
    assert posting.source_platform == "natixis_group"


def test_fetch_paginates_using_total(requests_mock):
    page_1 = response([item(i, f"Stage {i}", f"/job/{i}") for i in range(100)], total=150)
    page_2 = response([item(i, f"Stage {i}", f"/job/{i}") for i in range(100, 150)], total=150)
    requests_mock.post(API_URL, [{"json": page_1}, {"json": page_2}])

    postings = make_fetcher().fetch()

    assert len(postings) == 150
    froms = [call.json()["from"] for call in requests_mock.request_history]
    assert froms == [0, 100]


def test_fetch_raises_on_http_error(requests_mock):
    requests_mock.post(API_URL, status_code=500)

    import pytest

    with pytest.raises(Exception):
        make_fetcher().fetch()
