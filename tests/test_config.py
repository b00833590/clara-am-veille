from src.config import SOURCES, active_sources, pending_sources


def test_every_source_has_a_company_name():
    assert all(source.company for source in SOURCES)


def test_active_and_pending_sources_partition_all_sources():
    assert len(active_sources()) + len(pending_sources()) == len(SOURCES)


def test_active_sources_all_have_a_fetcher():
    assert all(fetcher is not None for _, fetcher in active_sources())


def test_pending_sources_have_no_fetcher_and_a_note():
    assert all(source.fetcher is None and source.note for source in pending_sources())
