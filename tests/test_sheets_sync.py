from src.storage.sqlite_repository import SQLiteJobRepository
from src.tracking.sheets_sync import HEADERS, SheetsSync
from src.models import JobPosting


def posting(**overrides):
    defaults = dict(
        company="Amundi",
        title="Stage Analyste Gestion Actions",
        url="https://jobs.amundi.com/1",
        description="...",
        category="A",
        location="Paris, France",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


class FakeExecutable:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeValuesResource:
    def __init__(self, initial_rows=None):
        self.stored_rows: list[list[str]] = initial_rows or []

    def get(self, spreadsheetId, range):
        return FakeExecutable({"values": self.stored_rows})

    def clear(self, spreadsheetId, range, body):
        self.stored_rows = []
        return FakeExecutable({})

    def update(self, spreadsheetId, range, valueInputOption, body):
        self.stored_rows = body["values"]
        return FakeExecutable({})


class FakeSpreadsheetsResource:
    def __init__(self, values_resource):
        self._values = values_resource

    def values(self):
        return self._values


class FakeSheetsService:
    def __init__(self, initial_rows=None):
        self._spreadsheets = FakeSpreadsheetsResource(FakeValuesResource(initial_rows))

    def spreadsheets(self):
        return self._spreadsheets


def test_sync_writes_new_category_a_postings_to_an_empty_sheet(tmp_path):
    repository = SQLiteJobRepository(tmp_path / "postings.db")
    repository.add(posting())
    service = FakeSheetsService()
    sync = SheetsSync(service, "fake-spreadsheet-id")

    sync.sync(repository)

    rows = service.spreadsheets().values().stored_rows
    assert rows[0] == HEADERS
    assert rows[1][1] == "Amundi"
    assert rows[1][2] == "Stage Analyste Gestion Actions"


def test_sync_excludes_off_topic_postings_from_the_sheet(tmp_path):
    repository = SQLiteJobRepository(tmp_path / "postings.db")
    repository.add(posting(category="N", url="https://jobs.amundi.com/2", title="Stage Marketing"))
    service = FakeSheetsService()
    sync = SheetsSync(service, "fake-spreadsheet-id")

    sync.sync(repository)

    rows = service.spreadsheets().values().stored_rows
    assert len(rows) == 1  # header only, no N posting


def test_sync_pulls_claras_manual_edits_into_the_repository(tmp_path):
    repository = SQLiteJobRepository(tmp_path / "postings.db")
    a_posting = posting()
    repository.add(a_posting)
    existing_sheet_rows = [
        HEADERS,
        [a_posting.stable_id(), "Amundi", "Stage Analyste Gestion Actions", "Paris, France", "...", a_posting.url, "Entretien", "2026-08-01", "2026-08-15", "Relancer par tel."],
    ]
    service = FakeSheetsService(existing_sheet_rows)
    sync = SheetsSync(service, "fake-spreadsheet-id")

    sync.sync(repository)

    stored = repository.all_postings()[0]
    assert stored["application_status"] == "Entretien"
    assert stored["application_date"] == "2026-08-01"
    assert stored["follow_up_date"] == "2026-08-15"
    assert stored["notes"] == "Relancer par tel."


def test_sync_never_overwrites_the_system_managed_status_column(tmp_path):
    repository = SQLiteJobRepository(tmp_path / "postings.db")
    a_posting = posting()
    repository.add(a_posting)
    existing_sheet_rows = [
        HEADERS,
        [a_posting.stable_id(), "Amundi", "Stage Analyste Gestion Actions", "Paris, France", "...", a_posting.url, "Entretien", "", "", ""],
    ]
    service = FakeSheetsService(existing_sheet_rows)
    sync = SheetsSync(service, "fake-spreadsheet-id")

    sync.sync(repository)

    assert repository.all_postings()[0]["status"] == "Nouvelle"


def test_sync_roundtrips_claras_edits_back_into_the_regenerated_sheet(tmp_path):
    # The regression this whole feature exists to prevent: an edit Clara made
    # must survive the sheet being rebuilt from the repository, not just be
    # captured in SQLite and then dropped when the sheet is rewritten.
    repository = SQLiteJobRepository(tmp_path / "postings.db")
    a_posting = posting()
    repository.add(a_posting)
    existing_sheet_rows = [
        HEADERS,
        [a_posting.stable_id(), "Amundi", "Stage Analyste Gestion Actions", "Paris, France", "...", a_posting.url, "Candidature envoyée", "2026-08-01", "", "À suivre"],
    ]
    service = FakeSheetsService(existing_sheet_rows)
    sync = SheetsSync(service, "fake-spreadsheet-id")

    sync.sync(repository)

    rows = service.spreadsheets().values().stored_rows
    written_row = rows[1]
    assert written_row[6] == "Candidature envoyée"
    assert written_row[7] == "2026-08-01"
    assert written_row[9] == "À suivre"


def test_sync_ignores_sheet_rows_missing_an_id():
    class NoRepositoryCallsExpected:
        def update_tracking_fields(self, *args, **kwargs):
            raise AssertionError("should not be called for a row without an ID")

        def all_postings(self):
            return []

    existing_sheet_rows = [HEADERS, ["", "Une entreprise sans ID valide", "", "", "", "", "", "", "", ""]]
    service = FakeSheetsService(existing_sheet_rows)
    sync = SheetsSync(service, "fake-spreadsheet-id")

    sync.sync(NoRepositoryCallsExpected())  # must not raise
