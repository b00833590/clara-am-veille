import base64
from email import message_from_bytes
from email.header import decode_header

from src.generation.gemini_letter_generator import LetterDraft
from src.models import JobPosting
from src.notifications.gmail_draft import GmailDraftCreator, build_draft_message


def make_posting():
    return JobPosting(
        company="Amundi",
        title="Stage Analyste Gestion Actions",
        url="https://jobs.amundi.com/1",
        description="...",
        category="A",
    )


def decode_message(raw_message: dict):
    raw_bytes = base64.urlsafe_b64decode(raw_message["message"]["raw"])
    return message_from_bytes(raw_bytes)


def decoded_subject(parsed) -> str:
    parts = decode_header(parsed["Subject"])
    return "".join(part.decode(charset or "utf-8") if isinstance(part, bytes) else part for part, charset in parts)


def text_body(parsed) -> str:
    for part in parsed.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode("utf-8")
    raise AssertionError("no text/plain part found")


def attachment_filenames(parsed) -> list[str]:
    return [part.get_filename() for part in parsed.walk() if part.get_filename()]


def test_build_draft_message_subject_matches_expected_format():
    letter = LetterDraft(letter_text="Madame, Monsieur,...")
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    assert decoded_subject(parsed) == "Candidature Stage AM — Amundi — Stage Analyste Gestion Actions"


def test_build_draft_message_body_contains_letter_text():
    letter = LetterDraft(letter_text="Madame, Monsieur, corps de la lettre.")
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    assert "Madame, Monsieur, corps de la lettre." in text_body(parsed)


def test_build_draft_message_body_flags_uncertain_elements_when_present():
    letter = LetterDraft(letter_text="Corps.", uncertain_elements=["Nom du recruteur", "Date de début"])
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    body = text_body(parsed)
    assert "Nom du recruteur" in body
    assert "Date de début" in body
    assert body.index("Nom du recruteur") < body.index("Corps.")


def test_build_draft_message_omits_verification_block_when_no_uncertain_elements():
    letter = LetterDraft(letter_text="Corps.", uncertain_elements=[])
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    assert "À vérifier" not in text_body(parsed)


def test_build_draft_message_body_includes_cv_emphasis_advice_when_present():
    letter = LetterDraft(letter_text="Corps.", cv_emphasis_advice="Mets en avant l'expérience Castignac.")
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    assert "Mets en avant l'expérience Castignac." in text_body(parsed)


def test_build_draft_message_always_attaches_the_letter_as_pdf():
    letter = LetterDraft(letter_text="Corps de la lettre.")
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    filenames = attachment_filenames(parsed)
    assert any(name.endswith(".pdf") and "Lettre" in name for name in filenames)


def test_build_draft_message_attaches_the_unmodified_cv_pdf_when_provided():
    letter = LetterDraft(letter_text="Corps.")
    message = build_draft_message(make_posting(), letter, cv_pdf_bytes=b"%PDF-1.4 fake cv bytes")

    parsed = decode_message(message)
    filenames = attachment_filenames(parsed)
    assert any(name.endswith(".pdf") and "CV" in name for name in filenames)

    for part in parsed.walk():
        if part.get_filename() and "CV" in part.get_filename():
            assert part.get_payload(decode=True) == b"%PDF-1.4 fake cv bytes"


def test_build_draft_message_omits_cv_attachment_when_not_provided():
    letter = LetterDraft(letter_text="Corps.")
    message = build_draft_message(make_posting(), letter, cv_pdf_bytes=None)

    parsed = decode_message(message)
    filenames = attachment_filenames(parsed)
    assert not any("CV" in name for name in filenames)


class FakeDraftsResource:
    def __init__(self):
        self.created_calls: list[dict] = []

    def create(self, userId, body):
        self.created_calls.append({"userId": userId, "body": body})
        return FakeExecutable({"id": "fake-draft-id"})


class FakeExecutable:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeUsersResource:
    def __init__(self):
        self._drafts = FakeDraftsResource()

    def drafts(self):
        return self._drafts


class FakeGmailService:
    def __init__(self):
        self._users = FakeUsersResource()

    def users(self):
        return self._users


def test_create_draft_calls_gmail_drafts_create_and_returns_draft_id():
    service = FakeGmailService()
    creator = GmailDraftCreator(service)
    letter = LetterDraft(letter_text="Corps.")

    draft_id = creator.create_draft(make_posting(), letter)

    assert draft_id == "fake-draft-id"
    sent = service.users().drafts().created_calls[0]
    assert sent["userId"] == "me"
    assert "raw" in sent["body"]["message"]


def test_create_draft_passes_through_configured_cv_pdf_bytes():
    service = FakeGmailService()
    creator = GmailDraftCreator(service, cv_pdf_bytes=b"%PDF-1.4 fake cv bytes")
    letter = LetterDraft(letter_text="Corps.")

    creator.create_draft(make_posting(), letter)

    raw_message = service.users().drafts().created_calls[0]["body"]
    parsed = decode_message(raw_message)
    filenames = attachment_filenames(parsed)
    assert any("CV" in name for name in filenames)
