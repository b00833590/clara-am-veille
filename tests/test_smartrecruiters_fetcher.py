import pytest

from src.fetchers.smartrecruiters import SmartRecruitersFetcher

API_URL = "https://api.smartrecruiters.com/v1/companies/SycomoreAssetManagement/postings"


def make_response(content):
    return {"totalFound": len(content), "offset": 0, "limit": 100, "content": content}


def test_fetch_keeps_only_internship_postings(requests_mock):
    requests_mock.get(
        API_URL,
        json=make_response(
            [
                {
                    "id": "744000130551915",
                    "name": "CDD Juriste Asset Management junior",
                    "experienceLevel": {"id": "entry_level", "label": "Entry Level"},
                    "location": {"city": "Paris", "country": "fr"},
                },
                {
                    "id": "744000128684809",
                    "name": "Stage 6 mois en Conformité / Contrôle interne",
                    "experienceLevel": {"id": "internship", "label": "Internship"},
                    "location": {"city": "Paris", "country": "fr"},
                },
            ]
        ),
    )

    fetcher = SmartRecruitersFetcher(company_identifier="SycomoreAssetManagement", display_name="Sycomore Asset Management")
    postings = fetcher.fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stage 6 mois en Conformité / Contrôle interne"


def test_fetch_builds_job_posting_with_expected_fields(requests_mock):
    requests_mock.get(
        API_URL,
        json=make_response(
            [
                {
                    "id": "744000128684809",
                    "name": "Stage Analyste",
                    "experienceLevel": {"id": "internship", "label": "Internship"},
                    "location": {"city": "Paris", "country": "fr"},
                }
            ]
        ),
    )

    fetcher = SmartRecruitersFetcher(company_identifier="SycomoreAssetManagement", display_name="Sycomore Asset Management")
    posting = fetcher.fetch()[0]

    assert posting.company == "Sycomore Asset Management"
    assert posting.url == "https://jobs.smartrecruiters.com/SycomoreAssetManagement/744000128684809"
    assert posting.location == "Paris, fr"
    assert posting.source_platform == "smartrecruiters"


def test_fetch_falls_back_to_title_keyword_when_experience_level_missing(requests_mock):
    requests_mock.get(
        API_URL,
        json=make_response(
            [
                {
                    "id": "1",
                    "name": "Internship - Portfolio Analyst",
                    "location": {"city": "Paris", "country": "fr"},
                }
            ]
        ),
    )

    fetcher = SmartRecruitersFetcher(company_identifier="SycomoreAssetManagement", display_name="Sycomore Asset Management")
    postings = fetcher.fetch()

    assert len(postings) == 1


def test_fetch_raises_on_http_error(requests_mock):
    requests_mock.get(API_URL, status_code=500)

    fetcher = SmartRecruitersFetcher(company_identifier="SycomoreAssetManagement", display_name="Sycomore Asset Management")

    with pytest.raises(Exception):
        fetcher.fetch()
