from scripts.validate_offers import sweep_expired_postings
from src.models import JobPosting
from src.storage.sqlite_repository import SQLiteJobRepository


def make_posting(**overrides):
    defaults = dict(company="Amundi", title="Stage Analyste", url="https://example.com/1", description="")
    defaults.update(overrides)
    return JobPosting(**defaults)


def test_marks_confirmed_dead_url_as_expired(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(url="https://example.com/dead")
    repo.add(posting)

    summary = sweep_expired_postings(repo, checker=lambda url: True, sleep_fn=lambda _: None)

    assert repo.all_postings()[0]["status"] == "Expirée"
    assert summary.marked_expired == 1
    assert summary.checked == 1


def test_leaves_still_live_url_untouched(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(url="https://example.com/alive")
    repo.add(posting)

    summary = sweep_expired_postings(repo, checker=lambda url: False, sleep_fn=lambda _: None)

    assert repo.all_postings()[0]["status"] == "Nouvelle"
    assert summary.marked_expired == 0
    assert summary.checked == 1


def test_leaves_inconclusive_check_untouched(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(url="https://example.com/unknown")
    repo.add(posting)

    summary = sweep_expired_postings(repo, checker=lambda url: None, sleep_fn=lambda _: None)

    assert repo.all_postings()[0]["status"] == "Nouvelle"
    assert summary.marked_expired == 0
    assert summary.checked == 1


def test_skips_postings_already_marked_expired(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(url="https://example.com/already-gone")
    repo.add(posting)
    repo.update_status(posting.stable_id(), "Expirée")

    calls = []
    summary = sweep_expired_postings(repo, checker=lambda url: calls.append(url) or True, sleep_fn=lambda _: None)

    assert calls == []
    assert summary.checked == 0
