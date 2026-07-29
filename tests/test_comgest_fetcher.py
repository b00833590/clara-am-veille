from src.fetchers.comgest import ComgestFetcher

URL = "https://www.comgest.com/en/about-us/our-people/careers/job-offers"


def accordion_html(items_html: str) -> str:
    return f"""
    <html><body>
    <dl id="JobListings">
      {items_html}
      <dt role="heading" class="accordion__header">
        <button class="accordion__header__button js-accordion__header__button">
          <span class="accordion__header__button__text">DON'T SEE YOUR POSITION?</span>
        </button>
      </dt>
      <dd role="region" class="accordion__content">
        <div class="rich-text">
          <a href="https://www.comgest.com/en/about-us/our-people/careers/job-offers/application-form?jobID=generic" class="cta-link">Send us your CV</a>
        </div>
      </dd>
    </dl>
    </body></html>
    """


ITEM_TEMPLATE = """
<dt role="heading" class="accordion__header">
  <button class="accordion__header__button js-accordion__header__button">
    <span class="accordion__header__button__text">{title}</span>
  </button>
</dt>
<dd role="region" class="accordion__content">
  <div class="rich-text">
    <a href="{href}" class="cta-link">Apply</a>
  </div>
</dd>
"""


def make_fetcher():
    return ComgestFetcher(url=URL, display_name="Comgest")


def test_fetch_returns_empty_list_when_only_generic_fallback_present(requests_mock):
    requests_mock.get(URL, text=accordion_html(""))

    postings = make_fetcher().fetch()

    assert postings == []


def test_fetch_skips_the_generic_dont_see_your_position_entry(requests_mock):
    item = ITEM_TEMPLATE.format(title="Stage Analyste Actions", href="https://www.comgest.com/en/.../application-form?jobID=1234")
    requests_mock.get(URL, text=accordion_html(item))

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stage Analyste Actions"


def test_fetch_builds_job_posting_with_expected_fields(requests_mock):
    item = ITEM_TEMPLATE.format(title="Stage Analyste Actions", href="https://www.comgest.com/en/.../application-form?jobID=1234")
    requests_mock.get(URL, text=accordion_html(item))

    posting = make_fetcher().fetch()[0]

    assert posting.company == "Comgest"
    assert posting.url == "https://www.comgest.com/en/.../application-form?jobID=1234"
    assert posting.source_platform == "site_maison_comgest"


def test_fetch_filters_out_non_internship_titles(requests_mock):
    item = ITEM_TEMPLATE.format(title="Senior Portfolio Manager", href="https://www.comgest.com/en/.../application-form?jobID=5678")
    requests_mock.get(URL, text=accordion_html(item))

    postings = make_fetcher().fetch()

    assert postings == []


def test_fetch_decodes_accented_titles_correctly_when_server_omits_charset(requests_mock):
    # Regression test for the "é becomes Ã©" mojibake bug: a server that
    # serves UTF-8 bytes but doesn't declare charset in Content-Type forces
    # requests' `.text` to guess the encoding, which can guess wrong. Using
    # `.content` (raw bytes) and letting BeautifulSoup's own HTML-aware
    # encoding detection handle it must decode correctly regardless.
    item = ITEM_TEMPLATE.format(title="Stage Développement Durable", href="https://www.comgest.com/en/.../application-form?jobID=9999")
    requests_mock.get(URL, content=accordion_html(item).encode("utf-8"), headers={"Content-Type": "text/html"})

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stage Développement Durable"
