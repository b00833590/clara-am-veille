from src.models import JobPosting
from src.storage.sqlite_repository import SQLiteJobRepository


def make_posting(**overrides):
    defaults = dict(
        company="Sycomore Asset Management",
        title="Stage Analyste Financier",
        url="https://careers.smartrecruiters.com/SycomoreAssetManagement/job/123",
        description="Stage au sein de l'équipe gestion...",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def test_add_creates_db_file(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")

    repo.add(make_posting())

    assert (tmp_path / "postings.db").exists()


def test_exists_returns_false_for_unknown_stable_id(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")

    assert repo.exists("unknown-id") is False


def test_exists_returns_true_after_add(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(category="A")

    repo.add(posting)

    assert repo.exists(posting.stable_id()) is True


def test_exists_persists_when_reopening_repository_from_disk(tmp_path):
    path = tmp_path / "postings.db"
    posting = make_posting(category="B")
    SQLiteJobRepository(path).add(posting)

    reopened = SQLiteJobRepository(path)

    assert reopened.exists(posting.stable_id()) is True


def test_add_is_idempotent_for_same_stable_id(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(category="A")

    repo.add(posting)
    repo.add(posting)

    rows = repo.all_postings()
    assert len(rows) == 1


def test_add_persists_all_fields_correctly(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(
        category="A",
        language="fr",
        to_verify=True,
        classification_reason="Analyse de portefeuille",
        location="Paris, France",
        location_priority=1,
        source_platform="smartrecruiters",
    )

    repo.add(posting)

    row = repo.all_postings()[0]
    assert row["company"] == "Sycomore Asset Management"
    assert row["category"] == "A"
    assert row["to_verify"] == 1
    assert row["classification_reason"] == "Analyse de portefeuille"
    assert row["location"] == "Paris, France"
    assert row["location_priority"] == 1
    assert row["source_platform"] == "smartrecruiters"
    assert row["url"] == posting.url

def test_update_letter_sets_cover_letter_link_for_matching_stable_id(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(category="A")
    repo.add(posting)

    repo.update_letter(posting.stable_id(), "Madame, Monsieur, corps de la lettre...")

    row = repo.all_postings()[0]
    assert row["cover_letter_link"] == "Madame, Monsieur, corps de la lettre..."


def test_update_letter_does_nothing_for_unknown_stable_id(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    repo.add(make_posting(category="A"))

    repo.update_letter("unknown-id", "texte")

    row = repo.all_postings()[0]
    assert not row["cover_letter_link"]


def test_all_postings_orders_by_detection_time(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    repo.add(make_posting(url="https://example.com/1", title="First"))
    repo.add(make_posting(url="https://example.com/2", title="Second"))

    rows = repo.all_postings()

    assert [row["title"] for row in rows] == ["First", "Second"]


def test_update_status_sets_status_for_matching_stable_id(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    posting = make_posting(category="A")
    repo.add(posting)

    repo.update_status(posting.stable_id(), "Expirée")

    row = repo.all_postings()[0]
    assert row["status"] == "Expirée"


def test_postings_with_url_and_status_returns_only_matching_status(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    repo.add(make_posting(url="https://example.com/1", title="A"))
    repo.add(make_posting(url="https://example.com/2", title="B"))
    repo.update_status(make_posting(url="https://example.com/2", title="B").stable_id(), "Expirée")

    rows = repo.postings_with_url_and_status("Nouvelle")

    assert [r["title"] for r in rows] == ["A"]


def test_postings_missing_letter_returns_category_a_without_a_letter(tmp_path):
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    with_letter = make_posting(url="https://example.com/1", title="Has letter", category="A")
    without_letter = make_posting(url="https://example.com/2", title="No letter", category="A")
    not_category_a = make_posting(url="https://example.com/3", title="Category N", category="N")
    repo.add(with_letter)
    repo.add(without_letter)
    repo.add(not_category_a)
    repo.update_letter(with_letter.stable_id(), "Corps de la lettre...")

    results = repo.postings_missing_letter()

    # Returns JobPosting objects, not raw dicts — this method is consumed
    # through the JobRepository interface by orchestrator.retry_missing_letters,
    # which needs real objects to hand to the letter generator/draft creator,
    # unlike all_postings()/postings_with_url_and_status() which are only
    # used by standalone scripts and return dicts for convenience.
    assert [p.title for p in results] == ["No letter"]
    assert results[0].category == "A"


def test_exists_check_does_not_full_scan_every_row(tmp_path):
    # Regression guard for the Excel-era O(n)-per-call scan: exists() must
    # use an indexed lookup (primary key), not iterate every stored row.
    repo = SQLiteJobRepository(tmp_path / "postings.db")
    for i in range(50):
        repo.add(make_posting(url=f"https://example.com/{i}", title=f"Posting {i}"))

    with repo._connect() as conn:
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT 1 FROM postings WHERE stable_id = ?", ("anything",)
        ).fetchall()
    plan_text = " ".join(str(row) for row in plan)

    assert "SCAN" not in plan_text.upper()
