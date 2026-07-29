from src.models import JobPosting


def test_stable_id_uses_url_when_present():
    posting = JobPosting(
        company="Sycomore Asset Management",
        title="Stage Analyste Financier",
        url="https://careers.smartrecruiters.com/SycomoreAssetManagement/job/123",
        description="...",
    )

    assert posting.stable_id() == posting.stable_id()
    assert len(posting.stable_id()) == 16


def test_stable_id_is_deterministic_for_same_url():
    posting_a = JobPosting(company="Amundi", title="Stage Gérant", url="https://jobs.amundi.com/offre/1", description="")
    posting_b = JobPosting(company="Amundi", title="Stage Gérant", url="https://jobs.amundi.com/offre/1", description="")

    assert posting_a.stable_id() == posting_b.stable_id()


def test_stable_id_differs_for_different_urls():
    posting_a = JobPosting(company="Amundi", title="Stage Gérant", url="https://jobs.amundi.com/offre/1", description="")
    posting_b = JobPosting(company="Amundi", title="Stage Gérant", url="https://jobs.amundi.com/offre/2", description="")

    assert posting_a.stable_id() != posting_b.stable_id()


def test_stable_id_falls_back_to_company_and_title_hash_when_no_url():
    posting_a = JobPosting(company="Carmignac", title="Stage Analyste", url=None, description="")
    posting_b = JobPosting(company="Carmignac", title="Stage Analyste", url=None, description="")

    assert posting_a.stable_id() == posting_b.stable_id()


def test_stable_id_fallback_differs_when_title_differs():
    posting_a = JobPosting(company="Carmignac", title="Stage Analyste", url=None, description="")
    posting_b = JobPosting(company="Carmignac", title="Stage Gérant", url=None, description="")

    assert posting_a.stable_id() != posting_b.stable_id()


def test_default_status_is_nouvelle():
    posting = JobPosting(company="Comgest", title="Stage", url="https://comgest.com/1", description="")

    assert posting.status == "Nouvelle"
