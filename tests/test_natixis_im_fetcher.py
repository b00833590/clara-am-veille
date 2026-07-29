from src.fetchers.natixis_im import NatixisIMFetcher

URL = "https://jobs.jobvite.com/natixis"


def page_html(rows_html: str) -> str:
    return f"""
    <html><body>
    <article class="jv-page-body">
      <h3 class="h2">Distribution Enablement Group</h3>
      <table class="jv-job-list">
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </article>
    </body></html>
    """


ROW_TEMPLATE = """
<tr>
  <td class="jv-job-list-name"><a href="{href}">{title}</a></td>
  <td class="jv-job-list-location">
    {city},
    {state}
  </td>
</tr>
"""


def make_fetcher():
    return NatixisIMFetcher()


def test_fetch_keeps_only_internship_titles(requests_mock):
    row = ROW_TEMPLATE.format(href="/natixis/job/abc123", title="Summer Intern - Investment Research", city="Boston", state="Massachusetts")
    requests_mock.get(URL, text=page_html(row))

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Summer Intern - Investment Research"


def test_fetch_filters_out_non_internship_titles(requests_mock):
    row = ROW_TEMPLATE.format(href="/natixis/job/xyz", title="Associate Distribution Consultant", city="Boston", state="Massachusetts")
    requests_mock.get(URL, text=page_html(row))

    postings = make_fetcher().fetch()

    assert postings == []


def test_fetch_builds_absolute_url_and_location(requests_mock):
    row = ROW_TEMPLATE.format(href="/natixis/job/abc123", title="Internship - Data Analytics", city="Boston", state="Massachusetts")
    requests_mock.get(URL, text=page_html(row))

    posting = make_fetcher().fetch()[0]

    assert posting.url == "https://jobs.jobvite.com/natixis/job/abc123"
    assert posting.company == "Natixis Investment Managers"
    assert posting.source_platform == "jobvite"
    assert "Boston" in posting.location


def test_fetch_returns_empty_list_when_no_positions(requests_mock):
    requests_mock.get(URL, text=page_html(""))

    postings = make_fetcher().fetch()

    assert postings == []


def test_fetch_decodes_accented_titles_correctly_when_server_omits_charset(requests_mock):
    # Regression test for the "é becomes Ã©" mojibake bug — see comgest test
    # for the full explanation. A server serving UTF-8 bytes without a
    # charset in Content-Type must still decode correctly via `.content`.
    row = ROW_TEMPLATE.format(href="/natixis/job/dev1", title="Summer Intern - Développement Durable", city="Paris", state="France")
    requests_mock.get(URL, content=page_html(row).encode("utf-8"), headers={"Content-Type": "text/html"})

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Summer Intern - Développement Durable"
