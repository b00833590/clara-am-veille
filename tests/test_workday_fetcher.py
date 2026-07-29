import pytest

from src.fetchers.workday import WorkdayFetcher

API_URL = "https://wellington.wd5.myworkdayjobs.com/wday/cxs/wellington/Campus/jobs"


def make_fetcher():
    return WorkdayFetcher(
        tenant="wellington",
        wd_host="wellington.wd5.myworkdayjobs.com",
        site="Campus",
        display_name="Wellington Management",
    )


def test_fetch_filters_non_internship_titles(requests_mock):
    requests_mock.post(
        API_URL,
        json={
            "total": 2,
            "jobPostings": [
                {"title": "Senior Portfolio Manager", "externalPath": "/job/Boston/Senior-PM_R1"},
                {"title": "Summer Internship - Investment Team", "externalPath": "/job/Boston/Intern_R2"},
            ],
        },
    )

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Summer Internship - Investment Team"


def test_fetch_builds_full_url_from_site_base_and_external_path(requests_mock):
    requests_mock.post(
        API_URL,
        json={"total": 1, "jobPostings": [{"title": "Internship - Data Team", "externalPath": "/job/Boston/Intern_R2"}]},
    )

    posting = make_fetcher().fetch()[0]

    assert posting.url == "https://wellington.wd5.myworkdayjobs.com/Campus/job/Boston/Intern_R2"
    assert posting.company == "Wellington Management"
    assert posting.source_platform == "workday"


def test_fetch_sends_expected_post_payload(requests_mock):
    requests_mock.post(API_URL, json={"total": 0, "jobPostings": []})

    make_fetcher().fetch()

    sent_body = requests_mock.request_history[0].json()
    assert sent_body["limit"] == 20
    assert sent_body["offset"] == 0
    assert sent_body["appliedFacets"] == {}


def test_fetch_raises_on_http_error(requests_mock):
    requests_mock.post(API_URL, status_code=500)

    with pytest.raises(Exception):
        make_fetcher().fetch()


def test_fetch_paginates_when_more_postings_than_page_size(requests_mock):
    page_1 = {
        "total": 25,
        "jobPostings": [{"title": f"Internship {i}", "externalPath": f"/job/Boston/Intern_{i}"} for i in range(20)],
    }
    page_2 = {
        "total": 25,
        "jobPostings": [{"title": f"Internship {i}", "externalPath": f"/job/Boston/Intern_{i}"} for i in range(20, 25)],
    }
    requests_mock.post(API_URL, [{"json": page_1}, {"json": page_2}])

    postings = make_fetcher().fetch()

    assert len(postings) == 25
    offsets = [call.json()["offset"] for call in requests_mock.request_history]
    assert offsets == [0, 20]
