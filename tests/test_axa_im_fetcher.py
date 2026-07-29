from src.fetchers.axa_im import AxaIMFetcher

API_URL = "https://careers.axa.com/api/jobs"


def job(title, slug, city=None, country=None):
    return {
        "data": {
            "title": title,
            "slug": slug,
            "city": city,
            "country": country,
            "apply_url": f"https://careers-en-axa.icims.com/jobs/{slug}/login",
        }
    }


def response(jobs, total_count=None):
    return {"jobs": jobs, "totalCount": total_count if total_count is not None else len(jobs)}


def make_fetcher():
    return AxaIMFetcher()


def test_fetch_filters_to_axa_investment_managers_entity(requests_mock):
    requests_mock.get(API_URL, json=response([job("Stage Analyste ISR", "1001", "Paris", "France")]))

    make_fetcher().fetch()

    sent_params = requests_mock.request_history[0].qs
    assert sent_params["tags3"] == ["axa investment managers"]


def test_fetch_keeps_only_internship_titles(requests_mock):
    requests_mock.get(
        API_URL,
        json=response(
            [
                job("Portfolio Manager", "1001", "Paris", "France"),
                job("Stage - Analyste ESG", "1002", "Paris", "France"),
            ]
        ),
    )

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stage - Analyste ESG"


def test_fetch_returns_empty_list_when_no_current_postings(requests_mock):
    requests_mock.get(API_URL, json=response([], total_count=0))

    postings = make_fetcher().fetch()

    assert postings == []


def test_fetch_builds_job_posting_with_expected_fields(requests_mock):
    requests_mock.get(API_URL, json=response([job("Stage Analyste ISR", "1001", "Paris", "France")]))

    posting = make_fetcher().fetch()[0]

    assert posting.company == "Axa Investment Managers"
    assert posting.url == "https://careers-en-axa.icims.com/jobs/1001/login"
    assert posting.location == "Paris, France"
    assert posting.source_platform == "axa_careers"


def test_fetch_raises_on_http_error(requests_mock):
    requests_mock.get(API_URL, status_code=500)

    import pytest

    with pytest.raises(Exception):
        make_fetcher().fetch()
