from src.fetchers.talentsoft import TalentsoftFetcher

BASE_URL = "https://jobs.amundi.com"
PAGE_1_URL = f"{BASE_URL}/offre-de-emploi/liste-toutes-offres.aspx?page=1&LCID=1036"
PAGE_2_URL = f"{BASE_URL}/offre-de-emploi/liste-toutes-offres.aspx?page=2&LCID=1036"

ITEM_TEMPLATE = """
<li class="ts-offer-list-item offerlist-item ">
  <h3 class="ts-offer-list-item__title styleh3">
    <a class="ts-offer-list-item__title-link" href="{href}" title="ref">{title}</a>
  </h3>
  <ul class="ts-offer-list-item__description ">
    <li>{contract}</li><li>{entity}</li><li>{country}</li><li class="noBorder">{city}</li>
  </ul>
</li>
"""


def page_html(items: list[str]) -> str:
    return f"""<html><body><div id="main"><ul class="ts-related-offers__row">{"".join(items)}</ul></div></body></html>"""


def make_fetcher():
    return TalentsoftFetcher(base_url=BASE_URL, display_name="Amundi")


def test_fetch_keeps_only_stage_contract_type(requests_mock):
    items = [
        ITEM_TEMPLATE.format(href="/offre-de-emploi/cdi_1.aspx", title="Data Engineer", contract="CDI", entity="Amundi IT Services", country="France", city="Paris"),
        ITEM_TEMPLATE.format(href="/offre-de-emploi/stage_2.aspx", title="Stage Analyste Gestion", contract="Stage", entity="Amundi Asset Management", country="France", city="Paris"),
        ITEM_TEMPLATE.format(href="/offre-de-emploi/alt_3.aspx", title="Alternant Contrôle de Gestion", contract="Alternance / Apprentissage", entity="Amundi Asset Management", country="France", city="Paris"),
    ]
    requests_mock.get(PAGE_1_URL, text=page_html(items))
    requests_mock.get(PAGE_2_URL, text=page_html([]))

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stage Analyste Gestion"


def test_fetch_builds_absolute_url_from_relative_href(requests_mock):
    items = [ITEM_TEMPLATE.format(href="/offre-de-emploi/stage_2.aspx", title="Stage Analyste", contract="Stage", entity="Amundi AM", country="France", city="Paris")]
    requests_mock.get(PAGE_1_URL, text=page_html(items))
    requests_mock.get(PAGE_2_URL, text=page_html([]))

    posting = make_fetcher().fetch()[0]

    assert posting.url == "https://jobs.amundi.com/offre-de-emploi/stage_2.aspx"
    assert posting.company == "Amundi"
    assert posting.source_platform == "talentsoft"
    assert posting.location == "Paris, France"


def test_fetch_paginates_across_multiple_pages(requests_mock):
    page_1_items = [ITEM_TEMPLATE.format(href="/offre-de-emploi/stage_1.aspx", title="Stage A", contract="Stage", entity="Amundi AM", country="France", city="Paris")]
    page_2_items = [ITEM_TEMPLATE.format(href="/offre-de-emploi/stage_2.aspx", title="Stage B", contract="Stage", entity="Amundi AM", country="France", city="Lyon")]
    page_3_url = f"{BASE_URL}/offre-de-emploi/liste-toutes-offres.aspx?page=3&LCID=1036"
    requests_mock.get(PAGE_1_URL, text=page_html(page_1_items))
    requests_mock.get(PAGE_2_URL, text=page_html(page_2_items))
    requests_mock.get(page_3_url, text=page_html([]))

    postings = make_fetcher().fetch()

    assert {p.title for p in postings} == {"Stage A", "Stage B"}


def test_fetch_stops_at_first_empty_page(requests_mock):
    requests_mock.get(PAGE_1_URL, text=page_html([]))

    postings = make_fetcher().fetch()

    assert postings == []


def test_fetch_stops_when_page_beyond_last_loops_back_to_first_page(requests_mock):
    # Real Talentsoft behaviour: requesting a page number beyond the last real
    # page silently re-serves page 1's content instead of an empty list. If
    # page 3 isn't mocked at all, a fetcher that doesn't detect the loop-back
    # at page 2 will crash trying to fetch it — proving the stop condition
    # kicked in correctly, not just that pagination happened to end.
    page_1_item = ITEM_TEMPLATE.format(href="/offre-de-emploi/stage_1.aspx", title="Stage A", contract="Stage", entity="Amundi AM", country="France", city="Paris")
    requests_mock.get(PAGE_1_URL, text=page_html([page_1_item]))
    requests_mock.get(PAGE_2_URL, text=page_html([page_1_item]))

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stage A"


def test_fetch_decodes_accented_titles_correctly_when_server_omits_charset(requests_mock):
    # Regression test for the "é becomes Ã©" mojibake bug — see comgest test
    # for the full explanation. A server serving UTF-8 bytes without a
    # charset in Content-Type must still decode correctly via `.content`.
    items = [ITEM_TEMPLATE.format(href="/offre-de-emploi/stage_dev.aspx", title="Stage Développement Économique", contract="Stage", entity="Amundi AM", country="France", city="Paris")]
    requests_mock.get(PAGE_1_URL, content=page_html(items).encode("utf-8"), headers={"Content-Type": "text/html"})
    requests_mock.get(PAGE_2_URL, content=page_html([]).encode("utf-8"), headers={"Content-Type": "text/html"})

    postings = make_fetcher().fetch()

    assert len(postings) == 1
    assert postings[0].title == "Stage Développement Économique"
