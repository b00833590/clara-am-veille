from src.fetchers.goldman_sachs import GoldmanSachsFetcher

API_URL = "https://api-higher.gs.com/gateway/api/v1/graphql"


def role(role_id, source_id, title, division, city=None, country=None):
    return {
        "roleId": role_id,
        "jobTitle": title,
        "division": division,
        "locations": [{"primary": True, "city": city, "state": None, "country": country}],
        "externalSource": {"sourceId": source_id},
    }


def response(items, total_count=None):
    return {"data": {"roleSearch": {"totalCount": total_count if total_count is not None else len(items), "items": items}}}


def make_fetcher():
    return GoldmanSachsFetcher(display_name="Goldman Sachs Asset Management")


def test_fetch_keeps_only_relevant_divisions_and_internship_titles(requests_mock):
    requests_mock.post(
        API_URL,
        json=response(
            [
                role("1", "1001", "2027 | Paris | Asset & Wealth Management | Off-Cycle Internship", "Asset & Wealth Management", "Paris", "France"),
                role("2", "1002", "2027 | Singapore | Operations | Summer Analyst", "Operations Division", "Singapore", "Singapore"),
                role("3", "1003", "2027 | Paris | Asset & Wealth Management | New Analyst", "Asset & Wealth Management", "Paris", "France"),
            ]
        ),
    )

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "2027 | Paris | Asset & Wealth Management | Off-Cycle Internship"


def test_fetch_also_keeps_global_banking_and_research_divisions(requests_mock):
    requests_mock.post(
        API_URL,
        json=response(
            [
                role("1", "1001", "2027 | Paris | Global Banking & Markets | Summer Internship", "Global Banking & Markets", "Paris", "France"),
                role("2", "1002", "2027 | London | Research | Summer Internship", "Global Investment Research Division", "London", "United Kingdom"),
            ]
        ),
    )

    postings = make_fetcher().fetch()

    assert len(postings) == 2


def test_fetch_builds_job_posting_with_expected_fields(requests_mock):
    requests_mock.post(
        API_URL,
        json=response([role("1", "170602", "Internship - Asset & Wealth Management", "Asset & Wealth Management", "Paris", "France")]),
    )

    posting = make_fetcher().fetch()[0]

    assert posting.company == "Goldman Sachs Asset Management"
    assert posting.url == "https://higher.gs.com/roles/170602"
    assert posting.location == "Paris, France"
    assert posting.source_platform == "goldman_sachs_higher"


def test_fetch_paginates_using_total_count(requests_mock):
    page_1 = response(
        [role(str(i), str(i), f"Internship - AWM {i}", "Asset & Wealth Management") for i in range(20)],
        total_count=25,
    )
    page_2 = response(
        [role(str(i), str(i), f"Internship - AWM {i}", "Asset & Wealth Management") for i in range(20, 25)],
        total_count=25,
    )
    requests_mock.post(API_URL, [{"json": page_1}, {"json": page_2}])

    postings = make_fetcher().fetch()

    assert len(postings) == 25
    page_numbers = [call.json()["variables"]["searchQueryInput"]["page"]["pageNumber"] for call in requests_mock.request_history]
    assert page_numbers == [0, 1]


def test_fetch_raises_on_http_error(requests_mock):
    requests_mock.post(API_URL, status_code=500)

    import pytest

    with pytest.raises(Exception):
        make_fetcher().fetch()
