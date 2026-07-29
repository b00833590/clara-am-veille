from src.fetchers.blackrock import BlackRockFetcher

ENDPOINT = "https://careers.blackrock.com/search-jobs/results"


def results_fragment(items_html: str, total_results=None, total_pages=1) -> str:
    count = total_results if total_results is not None else 1
    return f"""
    <section id="search-results" data-total-results="{count}" data-total-pages="{total_pages}">
      <section id="search-results-list">
        <ul>
          {items_html}
        </ul>
      </section>
    </section>
    """


ITEM_TEMPLATE = """
<li>
  <a href="{href}" data-job-id="{job_id}">
    <h2>{title}</h2>
    <span class="job-location">{location}</span>
  </a>
</li>
"""


def make_fetcher():
    return BlackRockFetcher(display_name="BlackRock")


def test_fetch_keeps_only_internship_titles(requests_mock):
    items = ITEM_TEMPLATE.format(href="/job/paris/2027-summer-internship/45831/1", job_id="1", title="2027 Summer Internship Program - EMEA", location="Paris, France")
    items += ITEM_TEMPLATE.format(href="/job/paris/international-relations-associate/45831/2", job_id="2", title="International Relations Associate", location="Paris, France")
    requests_mock.get(ENDPOINT, json={"results": results_fragment(items, total_results=2), "filters": ""})

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "2027 Summer Internship Program - EMEA"


def test_fetch_builds_job_posting_with_expected_fields(requests_mock):
    items = ITEM_TEMPLATE.format(href="/job/new-york/2027-summer-internship-program-amers/45831/90628276544", job_id="90628276544", title="2027 Summer Internship Program - AMERS", location="New York, NY")
    requests_mock.get(ENDPOINT, json={"results": results_fragment(items), "filters": ""})

    posting = make_fetcher().fetch()[0]

    assert posting.company == "BlackRock"
    assert posting.url == "https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/45831/90628276544"
    assert posting.location == "New York, NY"
    assert posting.source_platform == "talentbrew_blackrock"


def test_fetch_paginates_using_total_pages(requests_mock):
    page_1_items = "".join(
        ITEM_TEMPLATE.format(href=f"/job/x/{i}", job_id=str(i), title=f"Internship {i}", location="Paris") for i in range(15)
    )
    page_2_items = "".join(
        ITEM_TEMPLATE.format(href=f"/job/x/{i}", job_id=str(i), title=f"Internship {i}", location="Paris") for i in range(15, 20)
    )
    requests_mock.get(
        ENDPOINT,
        [
            {"json": {"results": results_fragment(page_1_items, total_results=20, total_pages=2), "filters": ""}},
            {"json": {"results": results_fragment(page_2_items, total_results=20, total_pages=2), "filters": ""}},
        ],
    )

    postings = make_fetcher().fetch()

    assert len(postings) == 20
    pages = [call.qs.get("currentpage", [""])[0] for call in requests_mock.request_history]
    assert pages == ["1", "2"]


def test_fetch_raises_on_http_error(requests_mock):
    requests_mock.get(ENDPOINT, status_code=500)

    import pytest

    with pytest.raises(Exception):
        make_fetcher().fetch()
