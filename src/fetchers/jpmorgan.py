from src.fetchers.base import Fetcher
from src.fetchers.oracle_hcm import OracleHcmFetcher
from src.models import JobPosting

HOST = "jpmc.fa.oraclecloud.com"
SITE_NUMBER = "CX_1001"


class JPMorganFetcher:
    """Fetcher for JP Morgan (Oracle Cloud HCM, same family as Lazard and
    Edmond de Rothschild — confirmed via the "Apply now" link on
    careers.jpmorgan.com, resolving the earlier Workday-vs-Oracle ambiguity).

    JPM's CX_1001 site lists 7000+ requisitions worldwide across every
    business — fetching every page before filtering client-side (as the
    other Oracle HCM connectors do) would mean ~300 sequential requests.
    Instead this runs the search server-side with "keyword=internship" and
    "keyword=stage" (English and French postings use different wording) and
    merges the two result sets, deduplicating by URL.
    """

    def __init__(self, display_name: str = "JP Morgan Asset Management", sub_fetchers: list[Fetcher] | None = None):
        self._sub_fetchers = sub_fetchers or [
            OracleHcmFetcher(host=HOST, site_number=SITE_NUMBER, display_name=display_name, keyword="internship"),
            OracleHcmFetcher(host=HOST, site_number=SITE_NUMBER, display_name=display_name, keyword="stage"),
        ]

    def fetch(self) -> list[JobPosting]:
        seen_urls: set[str] = set()
        postings: list[JobPosting] = []

        for sub_fetcher in self._sub_fetchers:
            for posting in sub_fetcher.fetch():
                if posting.url in seen_urls:
                    continue
                seen_urls.add(posting.url)
                postings.append(posting)

        return postings
