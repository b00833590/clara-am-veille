from src.fetchers.oracle_hcm import OracleHcmFetcher

API_URL = "https://icbpjb.fa.ocs.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"


def make_fetcher():
    return OracleHcmFetcher(host="icbpjb.fa.ocs.oraclecloud.com", site_number="LazardStudentCareers", display_name="Lazard")


def make_response(requisitions, total_jobs_count=None):
    return {"items": [{"TotalJobsCount": total_jobs_count if total_jobs_count is not None else len(requisitions), "requisitionList": requisitions}]}


def test_fetch_keeps_only_internship_titles(requests_mock):
    requests_mock.get(
        API_URL,
        json=make_response(
            [
                {"Id": "1", "Title": "Senior Portfolio Manager", "PrimaryLocation": "Paris, France"},
                {"Id": "2", "Title": "Summer Internship - Fixed Income", "PrimaryLocation": "Paris, France"},
            ]
        ),
    )

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Summer Internship - Fixed Income"


def test_fetch_builds_candidate_facing_url(requests_mock):
    requests_mock.get(API_URL, json=make_response([{"Id": "6252", "Title": "Stage Analyste", "PrimaryLocation": "Paris, France"}]))

    posting = make_fetcher().fetch()[0]

    assert posting.url == "https://icbpjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LazardStudentCareers/job/6252"
    assert posting.company == "Lazard"
    assert posting.location == "Paris, France"
    assert posting.source_platform == "oracle_hcm"


def test_fetch_paginates_using_total_jobs_count(requests_mock):
    page_1 = make_response([{"Id": str(i), "Title": f"Internship {i}", "PrimaryLocation": "Paris"} for i in range(25)], total_jobs_count=30)
    page_2 = make_response([{"Id": str(i), "Title": f"Internship {i}", "PrimaryLocation": "Paris"} for i in range(25, 30)], total_jobs_count=30)
    requests_mock.get(API_URL, [{"json": page_1}, {"json": page_2}])

    postings = make_fetcher().fetch()

    assert len(postings) == 30
    offsets = [call.qs.get("finder", [""])[0] for call in requests_mock.request_history]
    assert "offset=0" in offsets[0]
    assert "offset=25" in offsets[1]


def test_fetch_raises_on_http_error(requests_mock):
    requests_mock.get(API_URL, status_code=500)

    import pytest

    with pytest.raises(Exception):
        make_fetcher().fetch()


def test_fetch_sends_server_side_keyword_when_provided(requests_mock):
    requests_mock.get(API_URL, json=make_response([]))

    fetcher = OracleHcmFetcher(
        host="icbpjb.fa.ocs.oraclecloud.com", site_number="LazardStudentCareers", display_name="Lazard", keyword="internship"
    )
    fetcher.fetch()

    finder = requests_mock.request_history[0].qs["finder"][0]
    assert "keyword=internship" in finder


def test_fetch_omits_keyword_from_finder_when_not_provided(requests_mock):
    requests_mock.get(API_URL, json=make_response([]))

    make_fetcher().fetch()

    finder = requests_mock.request_history[0].qs["finder"][0]
    assert "keyword=" not in finder
